"""src.services.scraper.platforms
플랫폼별 스크래퍼 패키지
"""
from src.services.scraper.platforms.instagram_scraper import InstagramScraper
from src.services.scraper.platforms.youtube_scraper import YouTubeScraper

__all__ = ["InstagramScraper", "YouTubeScraper"]
