"""src.services.scraper.playwright_browser
Playwright 브라우저 공통 제어 모듈
"""
import logging
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)


class PlaywrightBrowser:
    """Playwright 브라우저 공통 로직"""

    def __init__(self):
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def create_browser_and_context(self, playwright) -> None:
        """브라우저와 컨텍스트 생성"""
        logger.info("브라우저 실행 중...")
        self.browser = await playwright.chromium.launch(headless=True)

        logger.info("페이지 컨텍스트 생성...")
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        self.page = await self.context.new_page()

    async def load_page(self, url: str, wait_until: str = "networkidle", timeout: int = 30000):
        """
        페이지 로드

        Args:
            url: 로드할 URL
            wait_until: 대기 조건 (networkidle, load, domcontentloaded)
            timeout: 타임아웃 (밀리초)

        Returns:
            Response: 페이지 응답 객체
        """
        logger.info(f"페이지 로드 중: {url}")
        response = await self.page.goto(url, wait_until=wait_until, timeout=timeout)

        if response:
            logger.info(f"페이지 로드 완료: status={response.status}")
        else:
            logger.warning("페이지 로드 완료: response=None")

        return response

    async def extract_open_graph_tags(self) -> dict:
        """
        og 메타 태그 추출

        Returns:
            dict: og 태그 딕셔너리 (title, description, image, url)
        """
        metadata = await self.page.evaluate('''() => {
            const result = {};
            const ogTags = ['og:title', 'og:description', 'og:image', 'og:url'];
            ogTags.forEach(tag => {
                const meta = document.querySelector(`meta[property="${tag}"]`);
                if (meta) result[tag.replace('og:', '')] = meta.content;
            });
            return result;
        }''')
        logger.info(f"og 메타 태그 추출 완료: {list(metadata.keys())}")
        return metadata

    async def close_browser(self) -> None:
        """브라우저 종료"""
        if self.browser:
            logger.info("브라우저 종료")
            await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None
