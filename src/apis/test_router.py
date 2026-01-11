"""src.apis.test_router
테스트 API 라우터 - SNS 스크래핑 테스트용
"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel

from src.services.scraper.scrape_router import route_and_scrape

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/test", tags=["테스트 API"])


class ScrapeRequest(BaseModel):
    url: str


@router.post("/scrape", status_code=200)
async def scrape_url(request: ScrapeRequest):
    """
    SNS URL에서 메타데이터를 Playwright로 스크래핑

    - POST /api/test/scrape
    - Body: {"url": "https://www.instagram.com/p/..."}
    - 성공: 200 + 메타데이터
    - 실패: 4xx/5xx + 에러 메시지
    """
    logger.info(f"스크래핑 요청: {request.url}")
    return await route_and_scrape(request.url)


@router.get("/health", status_code=200)
async def health_check():
    """스크래핑 테스트 API 상태 확인"""
    return {"status": "ok"}
