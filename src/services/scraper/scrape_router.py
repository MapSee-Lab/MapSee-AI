"""src.services.scraper.scrape_router
URL을 분석하여 적절한 플랫폼 스크래퍼로 라우팅
"""
import logging

from src.utils.url_classifier import classify_url
from src.services.scraper.platforms.instagram_scraper import InstagramScraper
from src.services.scraper.platforms.youtube_scraper import YouTubeScraper

logger = logging.getLogger(__name__)


async def route_and_scrape(url: str) -> dict:
    """
    URL을 분석하여 적절한 스크래퍼로 라우팅하고 스크래핑 수행

    Args:
        url: SNS URL

    Returns:
        dict: 스크래핑 결과

    Raises:
        HTTPException: 스크래핑 실패 또는 지원하지 않는 URL
    """
    # URL 분류 (지원하지 않는 URL이면 400 에러)
    classification = classify_url(url)
    logger.info(f"URL 분류 완료: platform={classification.platform}, type={classification.content_type}")

    # 플랫폼별 스크래퍼 라우팅
    if classification.platform == "instagram":
        scraper = InstagramScraper()
        return await scraper.scrape_instagram_post(url, classification)

    elif classification.platform == "youtube":
        scraper = YouTubeScraper()
        return await scraper.scrape_youtube_video(url, classification)

    # 이 코드는 classify_url에서 이미 예외를 던지므로 도달하지 않음
    # 하지만 타입 안전성을 위해 유지
    raise ValueError(f"지원하지 않는 플랫폼: {classification.platform}")
