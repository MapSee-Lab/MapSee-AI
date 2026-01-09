"""src.apis.place_router
장소 추출 API 라우터 (Spring의 PlaceController와 유사한 역할)
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import requests

from src.models import PlaceExtractionRequest, PlaceExtractionResponse, ExtractionState
from src.services.workflow import run_image_workflow, run_media_workflow
from src.services.modules.llm import get_llm_response
# from src.services.workflow import demo_process  # FIXME: 임시로 데모 워크플로우 사용
from src.utils.common import verify_api_key
from src.core.exceptions import CustomError
from src.core.config import settings
from src.services.background_tasks import process_extraction_in_background

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["AI 서버 API"])

@router.post("/extract-places", status_code=200)
async def extract_places(
    request: PlaceExtractionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    인증(API Key): 필요

    기능
    SNS 콘텐츠 URL과 contentId를 입력받아 장소 추출 파이프라인을 비동기 방식으로 실행합니다.
    요청은 즉시 200 OK를 반환하며, 실제 처리 결과는 백엔드의 `/api/ai/callback`으로 전송됩니다.

    ------------------------------------------------------------
    요청 파라미터 (PlaceExtractionRequest)
    - contentId (UUID): 콘텐츠 고유 식별자
    - snsUrl (string): SNS 원본 URL (Instagram, YouTube 등)

    ------------------------------------------------------------
    반환값 (즉시 응답)
    ```json
    {
      "received": true,
      "message": "Processing started"
    }
    ```
    ------------------------------------------------------------
    비동기 처리 방식
    - 스크래핑, STT, LLM 분석 등 전체 파이프라인은 Background Task에서 처리됩니다.
    - 파이프라인 오류 발생 시에도 본 엔드포인트는 항상 200 OK를 반환하고, 오류는 내부 로그로만 기록됩니다.
    ------------------------------------------------------------
    에러 코드
    - 인증 실패 시:
        - 401 UNAUTHORIZED (API Key 누락 또는 불일치)

    """

    logger.info(
        f"extract-places 요청 수신: contentId={request.contentId}, url={request.snsUrl}"
    )

    # 1. 비동기 백그라운드 처리 시작
    asyncio.create_task(
        process_extraction_in_background(request)
    )

    # 2. 즉시 응답 반환
    return {
        "received": True,
        "message": "Processing started"
    }
