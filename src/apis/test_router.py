"""src.apis.test_router
테스트 API 라우터 - Playwright 스크래핑 테스트용
"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel

from src.services.preprocess.playwright_scraper import scrape_instagram_html

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/test", tags=["테스트 API"])


class ScrapeRequest(BaseModel):
    url: str


@router.post("/scrape", status_code=200)
async def scrape_url(request: ScrapeRequest):
    """
    Instagram URL에서 HTML을 Playwright로 스크래핑

    - POST /api/test/scrape
    - Body: {"url": "https://www.instagram.com/p/..."}
    - 성공: 200 + HTML 데이터
    - 실패: 4xx/5xx + 에러 메시지
    """
    logger.info(f"스크래핑 요청: {request.url}")
    return await scrape_instagram_html(request.url)


@router.get("/health", status_code=200)
async def health_check():
    """Playwright 테스트 API 상태 확인"""
    return {"status": "ok"}
