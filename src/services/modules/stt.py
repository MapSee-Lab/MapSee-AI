"""src.modules.models.stt.py
추출한 오디오를 STT를 이용해 텍스트로 변환합니다.
"""
import numpy as np
import tempfile
import logging
from io import BytesIO
from faster_whisper import WhisperModel
from src.models import ExtractionState
from src.core.exceptions import CustomError

logger = logging.getLogger(__name__)


def get_transcription(state: ExtractionState) -> None:
    """
    Faster-Whisper 모델을 사용해 오디오 파일을 텍스트로 변환합니다.

    Args:
        - audio_stream(BytesIO): 릴스 오디오 인메모리 바이너리 파일

    Returns:
        - full_text(str): 릴스 오디오의 텍스트 변환물
    """
    audio_stream = state['extractedData']['audioStream']

    logger.info("Faster-Whisper 모델을 초기화합니다...")
    model = WhisperModel(
        "small",
        device="cpu",   # NOTE: GPU 사용 시 "cuda"로 변경
        compute_type="int8"
    )

    try:
        segments, info = model.transcribe(audio_stream, language="ko", beam_size=5)
        logger.info(f"감지된 언어: '{info.language}' (정확도: {info.language_probability:.2f})")

        full_text = "".join(segment.text for segment in segments)
        state['extractedData'].update({'transcriptionText': full_text})
    except Exception as e:
        logger.error(f"STT 변환 중 오류 발생: {str(e)}")
        raise CustomError(f"STT 변환 실패: {str(e)}")
