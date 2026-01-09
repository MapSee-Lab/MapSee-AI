"""src.services.workflow.py
인스타그램 릴스 게시물 처리 파이프라인입니다.

NOTE: OCR 기능은 제거되었습니다. 별도로 구현 예정입니다.
"""
import logging
from urllib.parse import urlparse
from io import BytesIO

from src.services.content_router import sns_router
from src.services.preprocess.audio import get_audio
from src.services.modules.stt import get_transcription
from src.services.modules.llm import get_llm_response, get_llm_response_demo
from src.services.preprocess.video import get_video_narration
from src.services.preprocess.demo_download import extract_caption # NOTE: 데모용
from src.models import ExtractionState
from src.core.exceptions import CustomError

logger = logging.getLogger(__name__)

# =============================================
# 메인 처리 파이프라인 함수
# =============================================
def run_media_workflow(state: ExtractionState):
    """
    인스타그램 릴스 URL을 입력받아 모든 처리 파이프라인을 실행하고 최종 결과를 반환합니다.
    모든 단계에서 예외 처리를 수행하여 안정성을 확보합니다.

    Args:
        - url(str): 릴스 URL

    Returns:
        - result(str): 릴스의 장소 정보 정리본 문자열
    """
    try:
        # 1. 컨텐츠/캡션 가져오기
        sns_router(state)
        logger.info("비디오 및 캡션 스트림 획득 완료")

        # 이미지인 경우 별도 처리 (OCR 제거됨)
        if state['contentType'] == 'image':
            # NOTE: OCR 기능이 제거되어 이미지에서 텍스트를 추출하지 않습니다.
            logger.warning("이미지 OCR 기능이 비활성화되어 있습니다. 캡션만 사용합니다.")
            state['extractedData'].update({'ocrText': ''})
            # LLM으로 정보 가공
            get_llm_response(state)
            logger.info("LLM 응답 완료")
            return state["result"]

        # 2. 오디오 추출하기
        get_audio(state)
        logger.info("오디오 스트림 추출 완료")

        # 3. 음성 텍스트 변환 (STT)
        get_transcription(state)
        logger.info("음성 텍스트 변환 완료")

        # 4. 비디오 OCR 텍스트 추출 (OCR 제거됨)
        get_video_narration(state)
        logger.info("영상 기반 텍스트 추출 완료 (OCR 비활성화)")

        # 5. LLM으로 정보 가공
        get_llm_response(state)
        logger.info("LLM 응답 완료")

        return state["result"]
    except CustomError:
        raise  # CustomError는 그대로 전달

    except Exception as e:
        logger.exception(f"파이프라인 실행 중 예기치 않은 오류 발생")
        raise CustomError(f"파이프라인 처리 실패: {str(e)}")


def run_image_workflow(state: ExtractionState):
    """
    인스타그램 '사진(포스트/캐러셀)' URL을 입력받아
    이미지 OCR 텍스트와 캡션을 LLM에 전달해 장소 정보를 생성합니다.

    NOTE: OCR 기능이 제거되어 캡션만 사용합니다.
    """
    try:
        # 1) 이미지/캡션 가져오기
        image_stream, caption = sns_router(state)
        if not image_stream:
            raise CustomError("이미지 스트림을 가져오지 못했습니다")

        # 안전: 혹시 앞에서 읽혔을 수 있으니 스트림 포인터 리셋
        try:
            image_stream.seek(0)
        except Exception:
            pass

        # 2) 이미지 OCR (비활성화됨)
        image_text = ""
        logger.warning("이미지 OCR 기능이 비활성화되어 있습니다.")

        # 3) LLM 가공
        text_sources = {
            "caption": caption,
            "ocr": image_text
            # "stt" 키는 아예 전달하지 않음.
        }

        result = get_llm_response(text_sources)
        # if not result:
        #     raise CustomError("LLM 응답을 받지 못했습니다")

        logger.info("이미지 장소 추출 파이프라인 완료")
        return result

    except CustomError:
        raise  # CustomError는 그대로 전달

    except Exception as e:
        logger.exception(f"이미지 파이프라인 실행 중 예기치 않은 오류 발생")
        raise CustomError(f"이미지 처리 실패: {str(e)}")

# NOTE: 데모용 간소화 파이프라인
def demo_process(url: str):
    """
    데모용 간소화 파이프라인:
    인스타그램 릴스 URL에서 비디오와 캡션을 가져와
    캡션만 LLM에 전달해 장소 정보를 생성합니다.
    """
    try:
        caption = extract_caption(url)
        result = get_llm_response_demo(caption)

        logger.info(f"결과: {result}")
        if not result:
            raise CustomError("LLM 응답을 받지 못했습니다")

        logger.info("데모 장소 추출 파이프라인 완료")
        return result

    except CustomError:
        raise

    except Exception as e:
        logger.exception(f"데모 파이프라인 실행 중 예기치 않은 오류 발생")
        raise CustomError(f"데모 파이프라인 처리 실패: {str(e)}")
