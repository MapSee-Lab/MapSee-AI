"""src.api.robust_router.py
실서비스용 인스타그램 릴스/이미지 전체 파이프라인 처리 라우터
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from src.models.place_extraction_response import PlaceExtractionResponse
from src.models.place_extraction_request import PlaceExtractionRequest
from src.models.extraction_state import ExtractionState
from src.models.place_extraction_dict import PlaceExtractionDict, PlaceExtractionDictList
from src.services.workflow import run_media_workflow
from src.utils.common import verify_api_key
from src.core.exceptions import CustomError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["AI 서버 동기 처리 API"])


@router.post("extract-places-sync", response_model=PlaceExtractionResponse, status_code=200)
def extract_places_robust(
    request: PlaceExtractionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    데모용: 백엔드로부터 장소 추출 요청을 받아 처리합니다.

    Args:
        request(LLMPlaceExtractionRequest): 장소 추출 요청 데이터 (snsUrl)
        api_key(str): 검증된 API Key

    Returns:
        LLMPlaceExtractionResponse: 처리 상태 응답

    Raises:
        HTTPException:
            - 401: API Key 불일치
            - 422: 릴스 처리 실패
            - 500: 서버 내부 오류
    """
    logger.info(f"데모용 장소 추출 요청: url={request.snsUrl}")

    # ExtractionState 초기화
    state = ExtractionState()
    state: ExtractionState = {
        'contentId': 'place-uuid-123',
        'snsUrl': 'https://www.instagram.com/reel/ABC123/',
        'snsPlatform': '',
        'contentType': '',
        'authorName': '',
        'authorHandle': '',
        'extractedData': {},
        'result': []
    }

    state.update({'contentId': request.contentId})
    state.update({'snsUrl': request.snsUrl})

    try:
        # 파이프라인 실행
        result = run_media_workflow(state)
        logger.info(f"워크플로우 실행 완료: 플랫폼={state.get('snsPlatform')}, 타입={state.get('contentType')}")


        return PlaceExtractionResponse(
            contentId=request.contentId,
            status="ACCEPTED",
            result=result
        )

    except CustomError as ce:
        logger.error(f"장소 추출 실패: {ce.message}")
        raise HTTPException(status_code=422, detail=ce.message)

    except Exception as e:
        logger.exception(f"장소 추출 중 서버 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다"
)
