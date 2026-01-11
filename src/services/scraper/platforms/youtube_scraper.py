"""src.services.scraper.platforms.youtube_scraper
YouTube 스크래핑 로직 (미구현)
"""
import logging
from fastapi import HTTPException

from src.utils.url_classifier import UrlClassification

logger = logging.getLogger(__name__)


class YouTubeScraper:
    """YouTube 비디오/쇼츠 스크래퍼 (미구현)"""

    async def scrape_youtube_video(self, url: str, classification: UrlClassification) -> dict:
        """
        YouTube 비디오/쇼츠 스크래핑 (미구현)

        Args:
            url: YouTube URL
            classification: URL 분류 결과

        Raises:
            HTTPException(501): 아직 구현되지 않음
        """
        logger.warning(f"YouTube 스크래핑 요청 (미구현): {url}")
        raise HTTPException(
            status_code=501,
            detail="YouTube 스크래핑은 아직 구현되지 않았습니다"
        )
