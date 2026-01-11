"""src.services.preprocess.playwright_scraper
Playwright를 사용한 Instagram 스크래핑 서비스
"""
import re
import logging
from playwright.async_api import async_playwright
from fastapi import HTTPException

from src.utils.url_classifier import classify_url

logger = logging.getLogger(__name__)


def _parse_description(description: str) -> dict:
    """
    og:description에서 메타데이터 파싱

    예: "7,434 likes, 63 comments - jamsilism on September 24, 2025: \"캡션...\""

    Returns:
        dict: {
            "author": str | None,
            "likes_count": int | None,
            "comments_count": int | None,
            "posted_at": str | None,
            "caption": str,
            "hashtags": list[str]
        }
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


async def scrape_instagram_html(url: str) -> dict:
    """
    Instagram URL에서 메타데이터를 스크래핑

    Args:
        url: Instagram 게시글 URL

    Returns:
        dict: {
            "platform": str,
            "content_type": str,
            "url": str,
            "author": str | None,
            "caption": str | None,
            "likes_count": int | None,
            "comments_count": int | None,
            "posted_at": str | None,
            "hashtags": list[str],
            "og_image": str | None,
            "image_urls": list[str]
        }

    Raises:
        HTTPException: 스크래핑 실패 또는 지원하지 않는 URL
    """
    # URL 분류 (지원하지 않는 URL이면 400 에러)
    classification = classify_url(url)
    logger.info(f"[1/5] 스크래핑 시작: {url} (platform={classification.platform}, type={classification.content_type})")

    async with async_playwright() as p:
        logger.info("[2/5] 브라우저 실행 중...")
        browser = await p.chromium.launch(headless=True)

        logger.info("[3/5] 페이지 컨텍스트 생성...")
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            logger.info("[4/5] 페이지 로드 중...")
            response = await page.goto(url, wait_until="networkidle", timeout=30000)

            if response:
                logger.info(f"[4/5] 페이지 로드 완료: status={response.status}")
            else:
                logger.warning("[4/5] 페이지 로드 완료: response=None")

            if response and response.status >= 400:
                logger.error(f"Instagram 응답 오류: {response.status}")
                raise HTTPException(
                    status_code=response.status,
                    detail=f"Instagram 응답 오류: {response.status}"
                )

            logger.info("[5/5] 데이터 추출 중...")

            # 모든 og 메타 태그 추출
            metadata = await page.evaluate('''() => {
                const result = {};
                const ogTags = ['og:title', 'og:description', 'og:image', 'og:url'];
                ogTags.forEach(tag => {
                    const meta = document.querySelector(`meta[property="${tag}"]`);
                    if (meta) result[tag.replace('og:', '')] = meta.content;
                });
                return result;
            }''')
            logger.info(f"og 메타 태그 추출 완료: {list(metadata.keys())}")

            # og:description 파싱
            parsed = _parse_description(metadata.get('description', ''))
            logger.info(f"메타데이터 파싱 완료: author={parsed['author']}, likes={parsed['likes_count']}, comments={parsed['comments_count']}")

            # 이미지 URL 추출 (cdninstagram.com 도메인만)
            image_urls = await page.evaluate('''() => {
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

            return {
                "platform": classification.platform,
                "content_type": classification.content_type,
                "url": url,
                "author": parsed["author"],
                "caption": parsed["caption"],
                "likes_count": parsed["likes_count"],
                "comments_count": parsed["comments_count"],
                "posted_at": parsed["posted_at"],
                "hashtags": parsed["hashtags"],
                "og_image": metadata.get('image'),
                "image_urls": image_urls
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Playwright 스크래핑 오류: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            logger.info("브라우저 종료")
            await browser.close()
