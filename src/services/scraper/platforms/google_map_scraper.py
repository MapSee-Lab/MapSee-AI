"""src.services.scraper.platforms.google_map_scraper
구글 지도 장소 스크래핑 로직
"""
import logging
import asyncio
from urllib.parse import quote

from playwright.async_api import async_playwright
from fastapi import HTTPException

from src.services.scraper.playwright_browser import PlaywrightBrowser
from src.services.scraper.common_util import (
    parse_review_count,
    parse_rating,
    parse_aria_label_value,
    parse_price_level,
    extract_coordinates_from_url,
    extract_google_place_id_from_url,
    SCRAPE_TIMEOUT_MS,
    PAGE_LOAD_WAIT_SEC,
    ELEMENT_WAIT_TIMEOUT_MS,
    MAX_IMAGE_COUNT,
)
from src.models.google_place_info import GooglePlaceInfo

logger = logging.getLogger(__name__)


class GoogleMapScraper:
    """구글 지도 장소 스크래퍼"""

    def __init__(self):
        self.browser_controller = PlaywrightBrowser()

    async def search_and_scrape(self, query: str) -> GooglePlaceInfo:
        """
        구글 지도에서 장소 검색 후 첫 번째 결과의 상세 정보 스크래핑

        Args:
            query: 검색어 (예: "늘푸른목장")

        Returns:
            GooglePlaceInfo: 추출된 장소 정보

        Raises:
            HTTPException: 스크래핑 실패 시
        """
        logger.info(f"[1/7] 구글 지도 검색 시작: query='{query}'")

        # 검색 URL 생성
        encoded_query = quote(query)
        search_url = f"https://www.google.com/maps/search/{encoded_query}"
        logger.info(f"검색 URL: {search_url}")

        async with async_playwright() as playwright:
            try:
                # [2/7] 브라우저 생성
                logger.info("[2/7] 브라우저 초기화...")
                await self.browser_controller.create_browser_and_context(playwright)

                # [3/7] 검색 페이지 로드
                logger.info("[3/7] 검색 페이지 로드...")
                await self.browser_controller.load_page(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=SCRAPE_TIMEOUT_MS
                )

                page = self.browser_controller.page

                # 검색 결과 또는 직접 장소 페이지 로드 대기
                logger.info("검색 결과 대기...")
                await asyncio.sleep(PAGE_LOAD_WAIT_SEC)

                # [4/7] 첫 번째 검색 결과 클릭 (검색 결과 목록이 있는 경우)
                logger.info("[4/7] 첫 번째 검색 결과 확인...")

                current_url = page.url

                # 이미 상세 페이지인지 확인 (URL에 /place/가 있으면 상세 페이지)
                if '/maps/place/' not in current_url:
                    try:
                        # 검색 결과 목록에서 첫 번째 결과 클릭
                        result_selector = 'div[role="feed"] > div:first-child a[href*="/maps/place/"]'
                        await page.wait_for_selector(result_selector, timeout=ELEMENT_WAIT_TIMEOUT_MS)
                        first_result = page.locator(result_selector).first
                        await first_result.click()
                        logger.info("첫 번째 검색 결과 클릭 완료")
                    except Exception as error:
                        logger.debug(f"셀렉터 1 실패: {error}, 대안 셀렉터 시도...")
                        try:
                            # 방법 2: 일반적인 장소 링크
                            alt_selector = 'a[href*="/maps/place/"]'
                            await page.wait_for_selector(alt_selector, timeout=5000)
                            first_result = page.locator(alt_selector).first
                            await first_result.click()
                        except Exception as fallback_error:
                            logger.debug(f"셀렉터 2 실패: {fallback_error}, 직접 장소 페이지로 간주")
                else:
                    logger.info("이미 장소 상세 페이지에 있음")

                # [5/7] 상세 페이지 로드 대기
                logger.info("[5/7] 상세 페이지 로드 대기...")
                await asyncio.sleep(PAGE_LOAD_WAIT_SEC)

                # 장소명 요소 대기 (상세 페이지 로드 확인)
                try:
                    await page.wait_for_selector('h1.DUwDvf', timeout=ELEMENT_WAIT_TIMEOUT_MS)
                    logger.info("상세 페이지 로드 완료")
                except Exception:
                    logger.debug("h1.DUwDvf를 찾을 수 없음, 대안 셀렉터 시도")

                # URL에서 정보 추출
                current_url = page.url
                place_id = extract_google_place_id_from_url(current_url) or "unknown"
                latitude, longitude = extract_coordinates_from_url(current_url)
                logger.info(f"Place ID: {place_id}, 좌표: ({latitude}, {longitude})")

                # [6/7] 장소 정보 추출
                logger.info("[6/7] 장소 정보 추출...")

                # 영업시간 드롭다운 펼치기 시도
                try:
                    hours_selectors = [
                        '[aria-expanded="false"][jsaction*="openhours"]',
                        '.OMl5r.hH0dDd',
                        'div[jsaction*="openhours.wfvdle141.dropdown"]',
                        '[data-hide-tooltip-on-mouse-move="true"][role="button"]'
                    ]
                    for selector in hours_selectors:
                        hours_button = page.locator(selector)
                        if await hours_button.count() > 0:
                            await hours_button.first.click()
                            try:
                                await page.wait_for_selector('table.eK4R0e tr', timeout=3000)
                                logger.debug(f"영업시간 드롭다운 펼침 (셀렉터: {selector})")
                            except Exception:
                                pass
                            break
                except Exception as error:
                    logger.debug(f"영업시간 드롭다운 클릭 실패 (무시): {error}")

                info = await page.evaluate(f'''() => {{
                    const result = {{}};
                    const MAX_IMAGES = {MAX_IMAGE_COUNT};

                    // 장소명
                    const nameElement = document.querySelector('h1.DUwDvf');
                    result.name = nameElement ? nameElement.textContent.trim() : null;

                    // 별점
                    const ratingElement = document.querySelector('.F7nice span[aria-hidden="true"]');
                    result.rating = ratingElement ? ratingElement.textContent.trim() : null;

                    // 리뷰 수 (aria-label에서 추출)
                    const reviewElement = document.querySelector('span[role="img"][aria-label*="리뷰"]');
                    result.review_aria = reviewElement ? reviewElement.getAttribute('aria-label') : null;

                    // 가격대
                    const priceElement = document.querySelector('.mgr77e span[role="img"]') ||
                                         document.querySelector('span[role="img"][aria-label*="₩"]') ||
                                         document.querySelector('span[role="img"][aria-label*="비싸"]') ||
                                         document.querySelector('span[role="img"][aria-label*="저렴"]');
                    if (priceElement) {{
                        const priceText = priceElement.textContent;
                        if (priceText && priceText.includes('₩')) {{
                            result.price_aria = priceText.trim();
                        }} else {{
                            result.price_aria = priceElement.getAttribute('aria-label');
                        }}
                    }} else {{
                        result.price_aria = null;
                    }}

                    // 카테고리
                    const categoryElement = document.querySelector('button.DkEaL');
                    result.category = categoryElement ? categoryElement.textContent.trim() : null;

                    // 주소 (aria-label에서 추출)
                    const addressButton = document.querySelector('button[data-item-id="address"]');
                    result.address_aria = addressButton ? addressButton.getAttribute('aria-label') : null;

                    // 전화번호 (aria-label에서 추출)
                    const phoneButton = document.querySelector('button[data-item-id^="phone"]');
                    result.phone_aria = phoneButton ? phoneButton.getAttribute('aria-label') : null;

                    // 영업 상태
                    const statusElement = document.querySelector('.ZDu9vd span');
                    result.business_status = statusElement ? statusElement.textContent.trim() : null;

                    // 영업 시간 (테이블에서 추출)
                    const businessHours = {{}};
                    const hoursRows = document.querySelectorAll('tr.y0skZc');
                    hoursRows.forEach(row => {{
                        const dayElement = row.querySelector('td.ylH6lf div');
                        const timeElement = row.querySelector('td.mxowUb');
                        if (dayElement && timeElement) {{
                            const day = dayElement.textContent.trim();
                            let time = timeElement.getAttribute('aria-label');
                            if (!time) {{
                                const timeList = timeElement.querySelector('li.G8aQO');
                                time = timeList ? timeList.textContent.trim() : timeElement.textContent.trim();
                            }}
                            if (day && time) {{
                                businessHours[day] = time;
                            }}
                        }}
                    }});
                    result.business_hours = Object.keys(businessHours).length > 0 ? businessHours : null;

                    // Plus Code (aria-label에서 추출)
                    const plusCodeButton = document.querySelector('button[data-item-id="oloc"]');
                    result.plus_code_aria = plusCodeButton ? plusCodeButton.getAttribute('aria-label') : null;

                    // 웹사이트 URL
                    const websiteLink = document.querySelector('a[data-item-id="authority"]');
                    result.website_url = websiteLink ? websiteLink.href : null;

                    // 대표 이미지 URL
                    const imageElement = document.querySelector('button[jsaction*="heroHeaderImage"] img') ||
                                         document.querySelector('img.sGi3W') ||
                                         document.querySelector('div[role="img"] img');
                    result.image_url = imageElement ? imageElement.src : null;

                    // 이미지 목록 (최대 MAX_IMAGES개)
                    const imageElements = document.querySelectorAll('img[src*="googleusercontent.com"]');
                    const imageUrls = [];
                    const seenUrls = new Set();
                    for (const img of imageElements) {{
                        if (img.src && !seenUrls.has(img.src) && imageUrls.length < MAX_IMAGES) {{
                            if (!img.src.includes('=s') || img.src.includes('=w') || img.src.includes('=h')) {{
                                seenUrls.add(img.src);
                                imageUrls.push(img.src);
                            }}
                        }}
                    }}
                    result.image_urls = imageUrls;

                    // 장소 설명/소개 (About 섹션)
                    const descElement = document.querySelector('[aria-label*="정보"] .PYvSYb') ||
                                        document.querySelector('.WeS02d.fontBodyMedium') ||
                                        document.querySelector('div[data-attrid="description"]');
                    result.description = descElement ? descElement.textContent.trim() : null;

                    // 편의시설/서비스 옵션
                    const amenities = [];
                    const serviceButtons = document.querySelectorAll('.E0DTEd');
                    serviceButtons.forEach(btn => {{
                        const text = btn.textContent.trim();
                        if (text && !amenities.includes(text)) {{
                            amenities.push(text);
                        }}
                    }});
                    const amenityElements = document.querySelectorAll('.hpLkke span, .LTs0Rc span');
                    amenityElements.forEach(el => {{
                        const text = el.textContent.trim();
                        if (text && text.length > 1 && text.length < 30 && !amenities.includes(text)) {{
                            amenities.push(text);
                        }}
                    }});
                    result.amenities = amenities;

                    // 인기 시간대 정보
                    const popularTimesElement = document.querySelector('.g2BVhd');
                    result.popular_times = popularTimesElement ? popularTimesElement.textContent.trim() : null;

                    return result;
                }}''')

                logger.info(f"추출 완료: name={info.get('name')}, category={info.get('category')}")

                # aria-label 값 파싱
                address = parse_aria_label_value(info.get('address_aria'), '주소: ')
                phone_number = parse_aria_label_value(info.get('phone_aria'), '전화: ')
                plus_code = parse_aria_label_value(info.get('plus_code_aria'), 'Plus Code: ')
                price_level = parse_price_level(info.get('price_aria'))

                # [7/7] GooglePlaceInfo 생성
                logger.info("[7/7] 스크래핑 완료")

                return GooglePlaceInfo(
                    place_id=place_id,
                    name=info.get('name') or query,
                    category=info.get('category'),
                    google_map_url=current_url,
                    latitude=latitude,
                    longitude=longitude,
                    address=address,
                    plus_code=plus_code,
                    rating=parse_rating(info.get('rating')),
                    review_count=parse_review_count(info.get('review_aria')),
                    price_level=price_level,
                    business_status=info.get('business_status'),
                    business_hours=info.get('business_hours'),
                    phone_number=phone_number,
                    website_url=info.get('website_url'),
                    description=info.get('description'),
                    amenities=info.get('amenities', []),
                    popular_times=info.get('popular_times'),
                    image_url=info.get('image_url'),
                    image_urls=info.get('image_urls', [])
                )

            except HTTPException:
                raise
            except Exception as error:
                logger.error(f"구글 지도 스크래핑 오류: {error}", exc_info=True)
                raise HTTPException(status_code=500, detail="구글 지도 스크래핑에 실패했습니다")
            finally:
                await self.browser_controller.close_browser()
