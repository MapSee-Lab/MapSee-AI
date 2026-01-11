"""src.services.scraper.platforms.instagram_scraper
Instagram 스크래핑 로직
"""
import re
import logging
from playwright.async_api import async_playwright
from fastapi import HTTPException

from src.services.scraper.playwright_browser import PlaywrightBrowser
from src.utils.url_classifier import UrlClassification

logger = logging.getLogger(__name__)


class InstagramScraper:
    """Instagram 게시글/릴스 스크래퍼"""

    def __init__(self):
        self.browser_controller = PlaywrightBrowser()

    def parse_instagram_description(self, description: str) -> dict:
        """
        og:description에서 메타데이터 파싱

        예: "7,434 likes, 63 comments - jamsilism on September 24, 2025: \"캡션...\""

        Args:
            description: og:description 내용

        Returns:
            dict: 파싱된 메타데이터
        """
        if not description:
            return {
                "author": None,
                "likes_count": None,
                "comments_count": None,
                "posted_at": None,
                "caption": None,
                "hashtags": []
            }

        # 좋아요 수 파싱
        likes_match = re.search(r'([\d,]+)\s*likes?', description)
        likes_count = int(likes_match.group(1).replace(',', '')) if likes_match else None

        # 댓글 수 파싱
        comments_match = re.search(r'([\d,]+)\s*comments?', description)
        comments_count = int(comments_match.group(1).replace(',', '')) if comments_match else None

        # 작성자 파싱 (언더스코어, 점 포함)
        author_match = re.search(r'-\s*([\w.]+)\s+on\s+', description)
        author = author_match.group(1) if author_match else None

        # 게시 날짜 파싱
        date_match = re.search(r'on\s+([\w\s,]+?):', description)
        posted_at = date_match.group(1).strip() if date_match else None

        # 캡션 본문 추출 (좋아요/댓글 정보 이후 부분)
        caption_match = re.search(r':\s*["\']?(.+)', description, re.DOTALL)
        caption = caption_match.group(1).rstrip('"\'') if caption_match else description

        # 해시태그 추출 (한글 해시태그 포함)
        hashtags = re.findall(r'#[\w가-힣]+', description)

        return {
            "author": author,
            "likes_count": likes_count,
            "comments_count": comments_count,
            "posted_at": posted_at,
            "caption": caption,
            "hashtags": hashtags
        }

    async def extract_instagram_image_urls(self) -> list[str]:
        """
        Instagram 이미지 URL 추출 (cdninstagram.com 도메인만)

        Returns:
            list[str]: 이미지 URL 목록
        """
        image_urls = await self.browser_controller.page.evaluate('''() => {
            const imgs = document.querySelectorAll('img[src*="cdninstagram.com"]');
            const urls = [];
            imgs.forEach(img => {
                const src = img.src;
                // 프로필 이미지 제외 (보통 작은 크기)
                if (src && !src.includes('150x150') && !src.includes('44x44')) {
                    urls.push(src);
                }
            });
            // 중복 제거
            return [...new Set(urls)];
        }''')
        logger.info(f"이미지 URL 추출: {len(image_urls)}개")
        return image_urls

    async def scrape_instagram_post(self, url: str, classification: UrlClassification) -> dict:
        """
        Instagram 게시글/릴스 스크래핑

        Args:
            url: Instagram URL
            classification: URL 분류 결과

        Returns:
            dict: 스크래핑 결과

        Raises:
            HTTPException: 스크래핑 실패 시
        """
        logger.info(f"[1/5] Instagram 스크래핑 시작: {url} (type={classification.content_type})")

        async with async_playwright() as playwright:
            try:
                # [2/5] 브라우저 생성
                logger.info("[2/5] 브라우저 초기화...")
                await self.browser_controller.create_browser_and_context(playwright)

                # [3/5] 페이지 로드
                logger.info("[3/5] 페이지 로드...")
                response = await self.browser_controller.load_page(url)

                if response and response.status >= 400:
                    logger.error(f"Instagram 응답 오류: {response.status}")
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Instagram 응답 오류: {response.status}"
                    )

                # [4/5] 메타데이터 추출
                logger.info("[4/5] 메타데이터 추출...")
                open_graph_metadata = await self.browser_controller.extract_open_graph_tags()

                # og:description 파싱
                parsed_metadata = self.parse_instagram_description(
                    open_graph_metadata.get('description', '')
                )
                logger.info(
                    f"메타데이터 파싱 완료: author={parsed_metadata['author']}, "
                    f"likes={parsed_metadata['likes_count']}, comments={parsed_metadata['comments_count']}"
                )

                # [5/5] 이미지 URL 추출
                logger.info("[5/5] 이미지 URL 추출...")
                image_urls = await self.extract_instagram_image_urls()

                return {
                    "platform": classification.platform,
                    "content_type": classification.content_type,
                    "url": url,
                    "author": parsed_metadata["author"],
                    "caption": parsed_metadata["caption"],
                    "likes_count": parsed_metadata["likes_count"],
                    "comments_count": parsed_metadata["comments_count"],
                    "posted_at": parsed_metadata["posted_at"],
                    "hashtags": parsed_metadata["hashtags"],
                    "og_image": open_graph_metadata.get('image'),
                    "image_urls": image_urls
                }

            except HTTPException:
                raise
            except Exception as error:
                logger.error(f"Instagram 스크래핑 오류: {error}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(error))
            finally:
                await self.browser_controller.close_browser()
