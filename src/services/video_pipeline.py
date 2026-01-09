"""src.services.video_pipeline.py

NOTE: OCR 기능은 제거되었습니다. 별도로 구현 예정입니다.
"""
from io import BytesIO
import logging

from src.services.preprocess.video import (
    get_video_dimensions,
    calculate_roi_coordinates,
    extract_unique_subtitle_frames
)
from src.core.exceptions import CustomError

logger = logging.getLogger(__name__)

# =============================================
# 설정 상수 (Constants)
# =============================================
ROI_Y_START_PERCENT = 0.60   # 하단 40%
ROI_HEIGHT_PERCENT = 0.40    # 높이 40%
SAMPLE_FPS = 2               # 초당 2 프레임 샘플링
HASH_THRESHOLD = 10          # 이미지 해시 유사도 임계값


# =============================================
# step functions (영상 분석 단계)
# =============================================
def get_video_dimensions_from_stream(video_stream: BytesIO):
    return get_video_dimensions(video_stream)


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
def run_video_pipeline(video_stream: BytesIO) -> str:
    """
    NOTE: OCR 기능이 제거되어 빈 문자열을 반환합니다.
    """
    try:
        # 4-1. 크기 분석
        logger.info("영상 크기 분석 중...")
        video_width, video_height = get_video_dimensions_from_stream(video_stream)
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

        return video_text

    except Exception as e:
        logger.exception("영상 분석 파이프라인 실패")
        raise CustomError(f"영상 분석 실패: {str(e)}")
