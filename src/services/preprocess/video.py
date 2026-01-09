"""src.services.preprocess.video.py
본문 X, 오디오 X, 영상에만 정보가 담긴 릴스 분석 기능을 위한 모듈입니다.
다운로드 된 릴스 영상에서 유의미한 프레임을 추출합니다.

NOTE: OCR 기능은 제거되었습니다. 별도로 구현 예정입니다.
"""
# =============================================
# 설정 상수 (Constants)
# =============================================
ROI_Y_START_PERCENT = 0.60   # 하단 40%
ROI_HEIGHT_PERCENT = 0.40    # 높이 40%
SAMPLE_FPS = 2               # 초당 2 프레임 샘플링
HASH_THRESHOLD = 10          # 이미지 해시 유사도 임계값


import subprocess
from io import BytesIO
from typing import List, Tuple
from PIL import Image
import imagehash
import logging
from src.models import ExtractionState
from src.core.exceptions import CustomError
from src.utils.common import validate_image_stream

logger = logging.getLogger(__name__)


# =============================================
# Video 처리 유틸리티 함수
# =============================================
def extract_video_dimensions(video_stream: BytesIO) -> tuple[int | None, int | None]:
    """
    ffprobe를 사용하여 BytesIO의 비디오 너비와 높이를 반환합니다.

    Args:
        video_stream: BytesIO로 저장된 비디오 데이터

    Returns:
        (width: int, height: int) 또는 (None, None)
    """
    logger.info("영상 크기 분석 시도 중...")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        "pipe:0"  # stdin에서 읽음
    ]

    try:
        # BytesIO 내용을 ffprobe stdin으로 파이프
        video_stream.seek(0)  # 스트림 처음부터 시작
        result = subprocess.run(
            cmd,
            input=video_stream.read(),  # BytesIO의 바이너리 데이터 전송
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )

        output = result.stdout.decode('utf-8').strip()
        w, h = map(int, output.split('x'))
        logger.info(f"영상 크기: {w}x{h}")
        return w, h

    except FileNotFoundError:
        logger.error("심각한 오류: 'FileNotFoundError' 발생.")
        logger.error("   'ffprobe'를 찾을 수 없습니다. ffmpeg 설치 확인 필요.")
        return None, None

    except subprocess.CalledProcessError as e:
        logger.error("심각한 오류: 'CalledProcessError' 발생.")
        logger.error(f"   ffprobe가 오류를 내며 종료 (코드: {e.returncode}).")
        logger.error(f"   ffprobe 오류: {e.stderr.decode('utf-8')}")
        return None, None

    except Exception as e:
        logger.error(f"심각한 오류: {type(e).__name__} 발생")
        logger.error(f"   오류 내용: {e}")
        return None, None


def calculate_roi_coordinates(
        video_width: int,
        video_height: int,
        y_start_percent: float,
        height_percent: float
    ) ->Tuple[int, int, int, int]:
    """
    비디오의 크기와 시작점/높이 비율을 바탕으로 실제 ROI 좌표 (x, y, w, h)를 계산합니다.

    Args:
        video_width (int): 비디오 너비
        video_heigth (int): 비디오 높이
        y_start_percent (float): ROI 시작 Y좌표 (비율)
        height_percent (float): ROI 시작 높이 (비율)

    Returns:
        tuple[int, int, int, int]: (x, y, w, h)
    """
    roi_x = 0
    roi_y = int(video_height * y_start_percent)
    roi_w = video_width
    roi_h = int(video_height * height_percent)

    return (roi_x, roi_y, roi_w, roi_h)


def extract_unique_subtitle_frames(
    video_stream: BytesIO,
    roi_rect: Tuple[int, int, int, int],
    sample_fps: int = 2,
    hash_threshold: int = 5
) -> List[Tuple[float, BytesIO]]:
    """
    관심 영역(ROI)의 시각적 변화를 감지하여 자막이 변경된 것으로 추정되는 전체 프레임을 추출합니다.

    Args:
        video_stream: 동영상 데이터 스트림.
        roi_rect: (x, y, 너비, 높이) 형태의 관심 영역 사각형.
        sample_fps: 초당 샘플링할 프레임 수.
        hash_threshold: 이미지 해시 값의 차이 기준. 이 값보다 크면 다른 이미지로 판단.

    Returns:
        (타임스탬프, 전체 프레임 BytesIO) 형태의 튜플 리스트.
    """
    video_stream.seek(0)
    video_bytes = video_stream.read()

    # 1단계: ROI 영역만 샘플링하여 변화 시점 찾기
    logger.info("1단계: 관심 영역(자막 위치)의 변화를 감지하는 중...")

    x, y, w, h = roi_rect
    vf_crop = f"crop={w}:{h}:{x}:{y}"

    cmd_detect = [
        "ffmpeg", "-hide_banner", "-i", "pipe:0",
        "-vf", f"fps={sample_fps},{vf_crop}",
        "-c:v", "png", "-f", "image2pipe", "pipe:1"
    ]

    proc_detect = subprocess.Popen(cmd_detect, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out_bytes, _ = proc_detect.communicate(input=video_bytes)

    # FFmpeg 스트림을 개별 PNG 프레임으로 분리
    png_sig = b"\x89PNG\r\n\x1a\n"
    roi_frames = out_bytes.split(png_sig)[1:] # 첫 분리 결과는 비어있으므로 제외

    unique_timestamps = []
    last_hash = None

    for i, frame_data in enumerate(roi_frames):
        current_time = i / sample_fps

        try:
            # 해시 비교로 시각적 중복 제거
            frame_stream = BytesIO(png_sig + frame_data)
            current_hash = imagehash.phash(Image.open(frame_stream))

            if last_hash is None or (current_hash - last_hash) > hash_threshold:
                unique_timestamps.append(current_time)
                last_hash = current_hash
        except Exception:
            # 손상된 프레임 등 예외 처리
            continue

    logger.info(f"총 {len(unique_timestamps)}개의 의미 있는 변화 지점을 찾았습니다.")

    # 2단계: 감지된 시점의 '전체' 프레임 추출
    if not unique_timestamps:
        return []

    logger.info(f"2단계: {len(unique_timestamps)}개의 최종 프레임 추출 중...")

    final_frames = []
    for t in unique_timestamps:
        cmd_extract = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", str(t), "-i", "pipe:0", "-vframes", "1",
            "-c:v", "png", "-f", "image2pipe", "pipe:1"
        ]
        proc_extract = subprocess.Popen(cmd_extract, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        frame_bytes, _ = proc_extract.communicate(input=video_bytes)

        # 빈 프레임 검증 강화
        if frame_bytes and len(frame_bytes) > 0:
            try:
                # 유효한 이미지인지 검증
                test_stream = BytesIO(frame_bytes)
                Image.open(test_stream).verify()  # 이미지 유효성 검증
                test_stream.seek(0)
                final_frames.append((t, test_stream))
            except Exception as e:
                logger.warning(f"프레임 {t}초 유효성 검증 실패: {e}. 건너뜁니다.")
                continue

    return final_frames


# =============================================
# step functions (영상 분석 단계)
# =============================================
def extract_video_dimensions_from_stream(video_stream: BytesIO):
    return extract_video_dimensions(video_stream)

def calculate_roi(video_width: int, video_height: int):
    return calculate_roi_coordinates(
        video_width,
        video_height,
        ROI_Y_START_PERCENT,
        ROI_HEIGHT_PERCENT
    )

def extract_unique_frames(video_stream: BytesIO, roi_rect):
    return extract_unique_subtitle_frames(
        video_stream,
        roi_rect,
        sample_fps=SAMPLE_FPS,
        hash_threshold=HASH_THRESHOLD
    )

def extract_text_from_frames(unique_image_frames):
    """
    NOTE: OCR 기능이 제거되었습니다. 빈 문자열을 반환합니다.
    """
    logger.warning("OCR 기능이 비활성화되어 있습니다. 프레임에서 텍스트를 추출하지 않습니다.")
    return ""


# =============================================
# 메인 영상 분석 파이프라인
# =============================================
def get_video_narration(state: ExtractionState) -> None:
    """
    NOTE: OCR 기능이 제거되어 ocrText는 빈 문자열로 설정됩니다.
    """
    video_stream = state['extractedData']['contentStream']

    try:
        # 4-1. 크기 분석
        logger.info("영상 크기 분석 중...")
        video_width, video_height = extract_video_dimensions_from_stream(video_stream)
        if video_width is None:
            raise CustomError("ffprobe로 영상 크기를 분석하지 못했습니다.")

        # 4-2. ROI 계산
        logger.info("ROI 계산 중...")
        roi_rect = calculate_roi(video_width, video_height)

        # 4-3. 프레임 추출
        logger.info("의미 있는 프레임 추출 중...")
        unique_frames = extract_unique_frames(video_stream, roi_rect)

        # 4-4. OCR (비활성화됨)
        logger.info(f"({len(unique_frames)}개 프레임) - OCR 기능 비활성화됨")
        video_text = extract_text_from_frames(unique_frames)

        state['extractedData'].update({'ocrText': video_text})

    except Exception as e:
        logger.exception("영상 분석 파이프라인 실패")
        raise CustomError(f"영상 분석 실패: {str(e)}")
