"""src.modules.audio.py
다운로드 된 릴스/숏츠 영상에서 오디오를 추출합니다.
"""
import subprocess
from io import BytesIO
from src.models import ExtractionState
from src.core.exceptions import CustomError

import logging

logger = logging.getLogger(__name__)

def get_audio(state: ExtractionState) -> None:
    """
    FFmpeg를 사용해 비디오 파일에서 오디오를 추출하여 state를 업데이트합니다.

    Args:
        state: ExtractionState 객체 (extractedData['audioStream'] 필드가 업데이트됨)

    Raises:
        CustomError: 오디오 추출 실패 시
    """
    video_stream: BytesIO = state['extractedData']['contentStream']

    # FFmpeg 명령어:
    # -i: 입력 파일
    # -vn: 비디오 스트림 비활성화
    # -acodec pcm_s16le: 16비트 WAV 포맷으로 인코딩 (Whisper에 적합)
    # -ar 16000: 샘플링 레이트를 16kHz로 설정
    # -ac 1: 오디오 채널을 모노(1)로 설정
    # -f wav: WAV 포맷으로 출력
    # pipe:0 (stdin), pipe:1 (stdout): 파이프 입출력

    command = [
        'ffmpeg',
        '-i', 'pipe:0',
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-f', 'wav',
        'pipe:1'
    ]

    try:
        # Popen을 사용하여 stdin으로 비디오 데이터를 전달하고, stdout으로 오디오 데이터를 받음
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        audio_bytes, err = process.communicate(input=video_stream.read())

        if process.returncode != 0:
            error_msg = err.decode() if err else "알 수 없는 오류"
            logger.error(f"오디오 추출 중 FFmpeg 오류 발생: {error_msg}")
            raise CustomError(f"FFmpeg 오디오 추출 실패: {error_msg}")

        # State 업데이트
        state['extractedData'].update({'audioStream': BytesIO(audio_bytes)})

        logger.info("오디오 추출 완료")

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.exception(f"오디오 추출 중 오류 발생: {error_msg}")
        raise CustomError(f"오디오 추출 실패: {error_msg}")
    except Exception as e:
        logger.exception(f"오디오 추출 중 예상치 못한 오류 발생")
        raise CustomError(f"오디오 추출 실패: {str(e)}")
