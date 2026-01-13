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
        Instagram 게시글 이미지 URL 추출 (캐러셀 슬라이드 네비게이션 포함)

        캐러셀의 경우 Next 버튼을 클릭하며 모든 이미지를 수집합니다.

        Returns:
            list[str]: 게시글 이미지 URL 목록 (다른 게시글 썸네일 제외)
        """
        page = self.browser_controller.page

        # 1. 캐러셀 존재 여부 확인
        has_carousel = await page.evaluate('''() => {
            return !!document.querySelector('ul._acay');
        }''')

        if has_carousel:
            # 2. 캐러셀: 슬라이드를 넘기며 모든 이미지 수집
            image_urls = await self._extract_carousel_images()
        else:
            # 3. 단일 이미지: article 내 메인 이미지 추출
            image_urls = await page.evaluate('''() => {
                const article = document.querySelector('article');
                if (!article) return [];

                const mainImg = article.querySelector('div._aagv img[src*="cdninstagram.com"]');
                return mainImg && mainImg.src ? [mainImg.src] : [];
            }''')

        logger.info(f"게시글 이미지 URL 추출: {len(image_urls)}개")
        return image_urls

    async def _extract_carousel_images(self) -> list[str]:
        """
        캐러셀 슬라이드를 넘기며 모든 이미지 URL 수집 (순서 유지)

        Returns:
            list[str]: 캐러셀 내 모든 이미지 URL (게시글 순서대로)
        """
        import asyncio
        page = self.browser_controller.page
        collected_urls: list[str] = []  # 순서 유지를 위해 리스트 사용
        seen_urls: set[str] = set()  # 중복 체크용

        # 현재 로드된 이미지 수집 함수
        async def collect_current_images():
            urls = await page.evaluate('''() => {
                const carousel = document.querySelector('ul._acay');
                if (!carousel) return [];

                const imgs = carousel.querySelectorAll('li._acaz img[src*="cdninstagram.com"]');
                return Array.from(imgs).map(img => img.src).filter(Boolean);
            }''')
            for url in urls:
                if url not in seen_urls:
                    seen_urls.add(url)
                    collected_urls.append(url)

        # 초기 이미지 수집
        await collect_current_images()

        # 슬라이드 개수 확인 (인디케이터 도트로 확인)
        total_slides = await page.evaluate('''() => {
            // 캐러셀 인디케이터 도트 개수로 전체 슬라이드 수 확인
            const dots = document.querySelectorAll('div._acnb');
            return dots.length || 1;
        }''')

        logger.info(f"캐러셀 슬라이드 개수: {total_slides}")

        # Next 버튼 클릭하며 이미지 수집
        for i in range(total_slides - 1):
            # JavaScript로 직접 Next 버튼 클릭 (가려진 요소 무시)
            clicked = await page.evaluate('''() => {
                const btn = document.querySelector('button[aria-label="Next"]');
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            }''')

            if not clicked:
                break

            await asyncio.sleep(0.4)  # 이미지 로드 대기
            await collect_current_images()

        return list(collected_urls)

    async def extract_author_profile_image(self) -> str | None:
        """
        Instagram 작성자 프로필 이미지 URL 추출

        Returns:
            str | None: 작성자 프로필 이미지 URL 또는 None
        """
        author_profile_url = await self.browser_controller.page.evaluate('''() => {
            // 프로필 이미지 셀렉터: alt 속성에 "profile picture" 포함
            const profileImg = document.querySelector('img[alt*="profile picture"]');
            return profileImg ? profileImg.src : null;
        }''')
        if author_profile_url:
            logger.info("작성자 프로필 이미지 URL 추출 완료")
        return author_profile_url

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
        logger.info(f"[1/6] Instagram 스크래핑 시작: {url} (type={classification.content_type})")

        async with async_playwright() as playwright:
            try:
                # [2/6] 브라우저 생성
                logger.info("[2/6] 브라우저 초기화...")
                await self.browser_controller.create_browser_and_context(playwright)

                # [3/6] 페이지 로드
                logger.info("[3/6] 페이지 로드...")
                response = await self.browser_controller.load_page(url)

                if response and response.status >= 400:
                    logger.error(f"Instagram 응답 오류: {response.status}")
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Instagram 응답 오류: {response.status}"
                    )

                # [4/6] 메타데이터 추출
                logger.info("[4/6] 메타데이터 추출...")
                open_graph_metadata = await self.browser_controller.extract_open_graph_tags()

                # og:description 파싱
                parsed_metadata = self.parse_instagram_description(
                    open_graph_metadata.get('description', '')
                )
                logger.info(
                    f"메타데이터 파싱 완료: author={parsed_metadata['author']}, "
                    f"likes={parsed_metadata['likes_count']}, comments={parsed_metadata['comments_count']}"
                )

                # [5/6] 이미지 URL 추출
                logger.info("[5/6] 게시글 이미지 URL 추출...")
                image_urls = await self.extract_instagram_image_urls()

                # [6/6] 작성자 프로필 이미지 URL 추출
                logger.info("[6/6] 작성자 프로필 이미지 URL 추출...")
                author_profile_image_url = await self.extract_author_profile_image()

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
                    "image_urls": image_urls,
                    "author_profile_image_url": author_profile_image_url
                }

            except HTTPException:
                raise
            except Exception as error:
                logger.error(f"Instagram 스크래핑 오류: {error}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(error))
            finally:
                await self.browser_controller.close_browser()
