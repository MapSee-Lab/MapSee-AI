"""src.api.demo_router.py
데모 API 전용 라우터 입니다.
실제 파이프라인(run_media_workflow, run_image_workflow)을 실행하지 않고,
- SNS URL에서 '캡션'만 추출한 뒤 데모용 LLM을 통해 장소 정보를 생성하는 간소화 버전 엔드포인트 입니다.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from src.models.place_extraction_response import PlaceExtractionResponse
from src.models.place_extraction_request import PlaceExtractionRequest
from src.models.place_extraction_dict import PlaceExtractionDict, PlaceExtractionDictList
from src.services.workflow import demo_process
from src.utils.common import verify_api_key
from src.core.exceptions import CustomError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["AI 서버 데모 API"])


@router.post("/demo", response_model=PlaceExtractionResponse, status_code=200)
def demo_extraction(
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

    try:
        # 데모 파이프라인 실행
        result = demo_process(request.snsUrl)
        logger.info(f"데모용 장소 추출 성공 및 응답 준비 완료: contentId={request.contentId}")


        return PlaceExtractionResponse(
            contentId=request.contentId,
            status="ACCEPTED",
            result=result
        )

    except CustomError as ce:
        logger.error(f"데모용 장소 추출 실패: contentId={request.contentId}, 오류={ce.message}")
        raise HTTPException(status_code=422, detail=ce.message)

    except Exception as e:
        logger.exception(f"데모용 장소 추출 중 서버 오류 발생: contentId={request.contentId}, 오류={str(e)}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다"
)
