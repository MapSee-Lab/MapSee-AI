"""src.services.background_tasks.py
비동기로 장소 추출 파이프라인을 실행하고 완료 결과를 백엔드에 callback으로 전달하는 모듈입니다.
"""

import asyncio
import logging
import json
import httpx
from src.core.config import settings
from src.services.workflow import run_media_workflow
from src.services.preprocess.sns import extract_instagram_metadata, extract_youtube_metadata

from src.models.place_extraction_request import PlaceExtractionRequest
from src.models import ExtractionState
from src.models.callback_request import AiCallbackRequest
from src.models.content_info import ContentInfo
from src.models.place_extraction_dict import PlaceExtractionDict

logging.getLogger("httpx").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


# 콜백 함수
async def send_callback(payload: AiCallbackRequest) -> bool:
    """
    백엔드 콜백 API로 최종 결과를 전송합니다.

    Args:
        payload: 콜백 요청 페이로드 (명세에 따른 필드 포함)

    Returns:
        bool: 전송 성공 여부 (200 같은 상태 코드 시 True)

    - API Key는 X-API-Key 헤더로 전달됩니다.
    - contentInfo는 SUCCESS 시에만 필수입니다.
    - places는 SUCESS 시에만 포함됩니다.

    """
    url = settings.BACKEND_CALLBACK_URL
    logger.info(f"[Callback] 전송 준비: {url} (Status: {payload.resultStatus})")

    headers = {
        "X-API-Key": settings.BACKEND_API_KEY
    }

    try:
        # httpx.AsyncClient를 사용해 백엔드 콜백 요청 보내기
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json=payload.model_dump(mode="json"),
                headers=headers
            )

        # HTTP 요청은 성공했으나 응답 코드가 200이 아닐 경우 (예: 400, 500)
        if 200 <= response.status_code < 300:
            logger.info(f"[Callback] 완료: {response.status_code}")
            logger.info(f"[Callback] 응답 본문: {response.text}")
            return True
        else:
            logger.error(f"[Callback] 전송 실패 (HTTP {response.status_code}): {response.text}")
            return False

    except httpx.TimeoutException:
        logger.error("[Callback] 전송 실패: HTTP 요청 타임아웃 발생")
        return False
    except Exception as e:
        logger.error(f"[Callback] 전송 중 예외 발생: {type(e).__name__} - {str(e)}")
        return False


# FAILED 콜백 전송을 위한 헬퍼 함수
async def send_failed_callback(request: PlaceExtractionRequest, exc: Exception):
    """
    예외 발생 시 FAILED 상태의 콜백을 전송하는 헬퍼 함수
    """
    # URL에서 플랫폼 추출 (간단한 추출)
    url = request.snsUrl.lower()
    if "youtube.com" in url or "youtu.be" in url:
        sns_platform = "YOUTUBE"
        platform = "YOUTUBE"
    elif "instagram.com" in url:
        sns_platform = "INSTAGRAM"
        platform = "INSTAGRAM"
    else:
        sns_platform = "INSTAGRAM"  # 기본값
        platform = "UNKNOWN"


    failed_payload = AiCallbackRequest(
        contentId=request.contentId,
        resultStatus="FAILED",
        snsPlatform=sns_platform,
        contentInfo=None, # FAILED 시에는 None
        places=[]
    )

    # send_callback 함수 호출
    await send_callback(failed_payload)

# 메인 비동기 처리 함수
async def process_extraction_in_background(request: PlaceExtractionRequest):
    """
    백엔드에서 전달받은 장소 추출 요청을 처리하고,
    완료되면 /api/ai/callback 으로 결과를 전송합니다.
    """

    try:
        # ExtractionState 준비
        state = ExtractionState(
            contentId=request.contentId,
            snsUrl=request.snsUrl,
            extractedData={}
        )

        logger.info(f"[Pipeline] 시작: {request.snsUrl}")

        # 파이프라인 실행
        result = await asyncio.to_thread(run_media_workflow, state)
        result_places = result.places

        logger.info(f"[Pipeline] 완료: 총 {len(result_places)}개 장소 추출됨")

        # 메타데이터 로드
        platform = state.get("snsPlatform")
        summary = state["extractedData"].get("captionText", "")

        if platform == "youtube":
            meta = await asyncio.to_thread(extract_youtube_metadata, state)
        else:
            meta = await asyncio.to_thread(extract_instagram_metadata, state)

        # 메타데이터 추출 결과 로깅
        logger.info(f"[Metadata] 추출 완료: {json.dumps(meta, separators=(',', ':'), ensure_ascii=False)}")
        logger.info(f"[Metadata] extractedData 확인 - thumbnailUrl: {state['extractedData'].get('thumbnailUrl')}, platformUploader: {state['extractedData'].get('platformUploader')}, contentUrl: {state['extractedData'].get('contentUrl')}")

        # ContentInfo 구성
        platform_value = (platform or "UNKNOWN").upper()
        content_info = ContentInfo(
            contentId=request.contentId,
            title=meta.get("title"),
            contentUrl=meta.get("contentUrl") or state.get("snsUrl"),
            thumbnailUrl=meta.get("thumbnailUrl"),
            platformUploader=meta.get("platformUploader"),
            summary=summary,
        )

        # ContentInfo 구성 결과 로깅
        logger.info(f"[ContentInfo] 구성 완료:")
        logger.info(f"  - title: {content_info.title}")
        logger.info(f"  - contentUrl: {content_info.contentUrl}")
        logger.info(f"  - thumbnailUrl: {content_info.thumbnailUrl}")
        logger.info(f"  - platformUploader: {content_info.platformUploader}")
        logger.info(f"  - summary: {len(summary)}자")

        # Place 리스트 구성
        places = [
            PlaceExtractionDict(
                name=p.name,
                address=p.address,
                country=p.country,
                latitude=p.latitude,
                longitude=p.longitude,
                description=p.description,
                rawData=p.rawData,
            )
            for p in result_places
        ]

        # Callback payload 구성 (SUCCESS)
        callback_payload = AiCallbackRequest(
            contentId=request.contentId,
            resultStatus="SUCCESS",
            snsPlatform=platform_value,
            contentInfo=content_info,
            places=places
        )

        # Callback 전송 전 ContentInfo 최종 확인 로깅
        logger.info(f"[Callback] ContentInfo 최종 확인:")
        logger.info(f"  - contentId: {callback_payload.contentInfo.contentId}")
        logger.info(f"  - title: {callback_payload.contentInfo.title}")
        logger.info(f"  - contentUrl: {callback_payload.contentInfo.contentUrl}")
        logger.info(f"  - thumbnailUrl: {callback_payload.contentInfo.thumbnailUrl}")
        logger.info(f"  - platformUploader: {callback_payload.contentInfo.platformUploader}")
        logger.info(f"  - summary: {len(callback_payload.contentInfo.summary) if callback_payload.contentInfo.summary else 0}자")

        # 백엔드 Callback 요청 보내기
        callback_success = await send_callback(callback_payload)

        return callback_success

    except Exception as e:
        logger.exception("[Background] 예외 발생")

        # 예외 발생 시 FAILED 콜백 전송 실패 헬퍼 함수 호출
        await send_failed_callback(request, e)

        # 파이프라인 실패했으므로 False 반환
        return False
