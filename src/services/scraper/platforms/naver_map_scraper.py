"""src.services.scraper.platforms.naver_map_scraper
네이버 지도 장소 스크래핑 로직
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
    extract_naver_place_id_from_url,
    SCRAPE_TIMEOUT_MS,
    PAGE_LOAD_WAIT_SEC,
    ELEMENT_WAIT_TIMEOUT_MS,
    MAX_IMAGE_COUNT,
)
from src.models.naver_place_info import NaverPlaceInfo

logger = logging.getLogger(__name__)


class NaverMapScraper:
    """네이버 지도 장소 스크래퍼"""

    def __init__(self):
        self.browser_controller = PlaywrightBrowser()

    async def search_and_scrape(self, query: str) -> NaverPlaceInfo:
        """
        네이버 지도에서 장소 검색 후 첫 번째 결과의 상세 정보 스크래핑

        Args:
            query: 검색어 (예: "늘푸른목장")

        Returns:
            NaverPlaceInfo: 추출된 장소 정보

        Raises:
            HTTPException: 스크래핑 실패 시
        """
        logger.info(f"[1/7] 네이버 지도 검색 시작: query='{query}'")

        # 검색 URL 생성
        encoded_query = quote(query)
        search_url = f"https://map.naver.com/p/search/{encoded_query}"
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
                    wait_until="networkidle",
                    timeout=SCRAPE_TIMEOUT_MS
                )

                # searchIframe 대기 (네이버 지도는 iframe 구조)
                logger.info("searchIframe 대기...")
                await self.browser_controller.page.wait_for_selector(
                    '#searchIframe',
                    timeout=ELEMENT_WAIT_TIMEOUT_MS
                )

                # searchIframe으로 전환
                search_iframe = self.browser_controller.page.frame_locator('#searchIframe')

                # 검색 결과 로드 대기
                logger.info("검색 결과 목록 대기...")

                # [4/7] 첫 번째 검색 결과 클릭
                logger.info("[4/7] 첫 번째 검색 결과 클릭...")

                try:
                    # 방법 1: li.VLTHu 내부의 place_bluelink
                    await search_iframe.locator('li.VLTHu a.place_bluelink').first.wait_for(
                        timeout=ELEMENT_WAIT_TIMEOUT_MS
                    )
                    place_link = search_iframe.locator('li.VLTHu a.place_bluelink').first
                    await place_link.click()
                except Exception as error:
                    logger.debug(f"셀렉터 1 실패: {error}, 대안 셀렉터 시도...")
                    try:
                        # 방법 2: 검색 결과 리스트의 첫 번째 링크
                        await search_iframe.locator('ul > li a[href="#"]').first.wait_for(
                            timeout=ELEMENT_WAIT_TIMEOUT_MS
                        )
                        place_link = search_iframe.locator('ul > li a[href="#"]').first
                        await place_link.click()
                    except Exception as fallback_error:
                        logger.debug(f"셀렉터 2 실패: {fallback_error}, 마지막 대안 시도...")
                        # 방법 3: 장소명 텍스트가 있는 span 클릭
                        await search_iframe.locator('span.YwYLL, span[class*="name"]').first.wait_for(
                            timeout=ELEMENT_WAIT_TIMEOUT_MS
                        )
                        place_span = search_iframe.locator('span.YwYLL, span[class*="name"]').first
                        await place_span.click()

                logger.info("첫 번째 결과 클릭 완료, 상세 페이지 로드 대기...")

                # [5/7] 상세 페이지 로드 대기
                logger.info("[5/7] 상세 페이지 로드 대기...")
                await asyncio.sleep(PAGE_LOAD_WAIT_SEC)

                # entryIframe 대기
                logger.info("entryIframe 대기...")
                await self.browser_controller.page.wait_for_selector(
                    '#entryIframe',
                    timeout=ELEMENT_WAIT_TIMEOUT_MS
                )

                # entryIframe으로 전환
                entry_iframe = self.browser_controller.page.frame_locator('#entryIframe')

                # 상세 정보 컨테이너 대기 (장소명이 나타날 때까지)
                await entry_iframe.locator('span.GHAhO').wait_for(timeout=ELEMENT_WAIT_TIMEOUT_MS)
                logger.info("상세 페이지 로드 완료")

                # [6/7] 장소 정보 추출
                logger.info("[6/7] 장소 정보 추출...")

                # 현재 URL에서 Place ID 추출
                current_url = self.browser_controller.page.url
                place_id = extract_naver_place_id_from_url(current_url) or "unknown"
                logger.info(f"Place ID: {place_id}")

                # entryIframe을 찾아야 함 (name으로 찾기)
                frames = self.browser_controller.page.frames
                entry_frame = self.browser_controller.page.frame(name='entryIframe')

                if not entry_frame:
                    # URL에 'entry' 포함된 frame 찾기
                    for frame in frames:
                        if frame.name == 'entryIframe' or (frame.url and '/entry/' in frame.url):
                            entry_frame = frame
                            break

                if not entry_frame:
                    raise HTTPException(status_code=500, detail="상세 페이지를 찾을 수 없습니다")

                logger.debug(f"entry_frame URL: {entry_frame.url}")

                # 추가 대기: DOM이 완전히 로드될 때까지
                await asyncio.sleep(2)

                # iframe 내에서 JavaScript 실행
                info = await entry_frame.evaluate(f'''() => {{
                    const result = {{}};
                    const MAX_IMAGES = {MAX_IMAGE_COUNT};

                    // 장소명 (여러 셀렉터 시도)
                    const nameElement = document.querySelector('span.GHAhO') ||
                                        document.querySelector('#_title span:first-child') ||
                                        document.querySelector('.place_section_header span');
                    result.name = nameElement ? nameElement.textContent.trim() : null;

                    // 카테고리
                    const categoryElement = document.querySelector('span.lnJFt') ||
                                            document.querySelector('#_title span:nth-child(2)');
                    result.category = categoryElement ? categoryElement.textContent.trim() : null;

                    // 별점 (PXMot 클래스 내부 텍스트에서 숫자 추출)
                    const ratingContainer = document.querySelector('.PXMot.LXIwF') ||
                                            document.querySelector('.dAsGb .PXMot:first-child');
                    if (ratingContainer) {{
                        const ratingText = ratingContainer.textContent;
                        const ratingMatch = ratingText.match(/([\\d.]+)/);
                        result.rating = ratingMatch ? ratingMatch[1] : null;
                    }}

                    // 방문자 리뷰 수
                    const visitorReviewLink = document.querySelector('a[href*="/review/visitor"]');
                    result.visitor_review_text = visitorReviewLink ? visitorReviewLink.textContent : null;

                    // 블로그 리뷰 수
                    const blogReviewLink = document.querySelector('a[href*="/review/ugc"]');
                    result.blog_review_text = blogReviewLink ? blogReviewLink.textContent : null;

                    // 한줄 설명
                    const descElement = document.querySelector('div.XtBbS') ||
                                        document.querySelector('.dAsGb > div:last-child');
                    result.description = descElement ? descElement.textContent.trim() : null;

                    // 주소 (여러 셀렉터 시도)
                    const addressElement = document.querySelector('span.LDgIH') ||
                                           document.querySelector('.O8qbU.tQY7D span') ||
                                           document.querySelector('[class*="address"]');
                    result.address = addressElement ? addressElement.textContent.trim() : null;

                    // 도로명 주소 (주소 복사 버튼 근처)
                    const roadAddressElement = document.querySelector('.LDgIH');
                    result.road_address = roadAddressElement ? roadAddressElement.textContent.trim() : null;

                    // 지하철 정보
                    const subwayElement = document.querySelector('div.nZapA');
                    result.subway_info = subwayElement ? subwayElement.textContent.trim() : null;

                    // 찾아가는 길
                    const directionsElement = document.querySelector('span.zPfVt') ||
                                              document.querySelector('.place_section_content .zPfVt');
                    result.directions_text = directionsElement ? directionsElement.textContent.trim() : null;

                    // 영업 상태
                    const businessStatusElement = document.querySelector('div.A_cdD em') ||
                                                  document.querySelector('.pSavy em');
                    result.business_status = businessStatusElement ? businessStatusElement.textContent.trim() : null;

                    // 영업 시간
                    const businessHoursElement = document.querySelector('span.U7pYf time') ||
                                                 document.querySelector('.pSavy time');
                    result.business_hours = businessHoursElement ? businessHoursElement.textContent.trim() : null;

                    // 요일별 상세 영업시간
                    const hoursDetailElements = document.querySelectorAll('.A_cdD .y6tNq');
                    result.open_hours_detail = Array.from(hoursDetailElements).map(el => el.textContent.trim());

                    // 휴무일 정보
                    const holidayElement = document.querySelector('.A_cdD .vV_z_') ||
                                           document.querySelector('[class*="holiday"]');
                    result.holiday_info = holidayElement ? holidayElement.textContent.trim() : null;

                    // 전화번호
                    const phoneElement = document.querySelector('span.xlx7Q') ||
                                         document.querySelector('.nbXkr span');
                    result.phone_number = phoneElement ? phoneElement.textContent.trim() : null;

                    // 홈페이지 URL
                    const homepageLink = document.querySelector('a.place_bluelink[href*="http"]') ||
                                         document.querySelector('a[class*="homepage"]') ||
                                         document.querySelector('.place_section_content a[href^="http"]:not([href*="naver"])');
                    result.homepage_url = homepageLink ? homepageLink.href : null;

                    // 예약 가능 여부 (네이버 예약 버튼 존재 확인)
                    const reservationButton = document.querySelector('a[href*="booking.naver"]') ||
                                              document.querySelector('a[href*="reserve.naver"]') ||
                                              document.querySelector('button[aria-label*="예약"]');
                    result.reservation_available = !!reservationButton;

                    // 편의시설
                    const amenitiesElement = document.querySelector('div.xPvPE') ||
                                             document.querySelector('.Uv6Eo div');
                    result.amenities_text = amenitiesElement ? amenitiesElement.textContent.trim() : null;

                    // 키워드/태그 (리뷰 링크 제외)
                    let keywordEls = document.querySelectorAll('.chip_group a, .place_section_content .chip a');
                    if (keywordEls.length === 0) {{
                        keywordEls = document.querySelectorAll('.place_section_content a[class*="tag"]');
                    }}
                    result.keywords = Array.from(keywordEls)
                        .map(el => el.textContent.trim())
                        .filter(text => text && !text.includes('리뷰'));

                    // TV 방송 출연 정보
                    let tvEls = document.querySelectorAll('div.TMK4W .A_cdD');
                    if (tvEls.length === 0) {{
                        tvEls = document.querySelectorAll('.place_section_content [class*="broadcast"]');
                    }}
                    result.tv_appearances = Array.from(tvEls).map(el => el.textContent.trim()).filter(Boolean);

                    // 대표 메뉴
                    let menuEls = document.querySelectorAll('.place_section_content .LNvHf');
                    if (menuEls.length === 0) {{
                        menuEls = document.querySelectorAll('.place_section_content [class*="menu"] .name');
                    }}
                    result.menu_info = Array.from(menuEls).map(el => el.textContent.trim()).filter(Boolean);

                    // 좌표 추출 (window state 또는 meta 태그에서)
                    try {{
                        // 방법 1: __APOLLO_STATE__ 에서 추출
                        const apolloState = window.__APOLLO_STATE__;
                        if (apolloState) {{
                            const placeKeys = Object.keys(apolloState).filter(k => k.startsWith('Place:'));
                            if (placeKeys.length > 0) {{
                                const placeData = apolloState[placeKeys[0]];
                                result.latitude = placeData?.y || placeData?.latitude || null;
                                result.longitude = placeData?.x || placeData?.longitude || null;
                            }}
                        }}
                        // 방법 2: meta 태그에서 추출
                        if (!result.latitude) {{
                            const geoMeta = document.querySelector('meta[name="geo.position"]');
                            if (geoMeta) {{
                                const [lat, lng] = geoMeta.content.split(';');
                                result.latitude = parseFloat(lat);
                                result.longitude = parseFloat(lng);
                            }}
                        }}
                    }} catch (e) {{
                        result.latitude = null;
                        result.longitude = null;
                    }}

                    // 대표 이미지
                    const imageElement = document.querySelector('div.fNygA img') ||
                                         document.querySelector('img.K0PDV') ||
                                         document.querySelector('.place_thumb img');
                    result.image_url = imageElement ? imageElement.src : null;

                    // 이미지 목록 (최대 MAX_IMAGES개, 필터링 개선)
                    const imageElements = document.querySelectorAll('img[src*="pstatic.net"]');
                    const imageUrls = [];
                    const seenUrls = new Set();
                    for (const img of imageElements) {{
                        if (img.src && !seenUrls.has(img.src) && imageUrls.length < MAX_IMAGES) {{
                            // 아이콘/로고/접근성 이미지 제외
                            const isValidImage = !img.src.includes('icon') &&
                                                 !img.src.includes('logo') &&
                                                 !img.src.includes('accessor') &&
                                                 !img.src.includes('sprite');
                            if (isValidImage) {{
                                seenUrls.add(img.src);
                                imageUrls.push(img.src);
                            }}
                        }}
                    }}
                    result.image_urls = imageUrls;

                    return result;
                }}''')

                logger.info(f"추출 완료: name={info.get('name')}, category={info.get('category')}, address={info.get('address')}")

                # 편의시설 파싱
                amenities = []
                if info.get('amenities_text'):
                    amenities = [a.strip() for a in info['amenities_text'].split(',')]

                # 네이버 지도 URL 생성
                naver_map_url = f"https://map.naver.com/p/search/{encoded_query}/place/{place_id}" if place_id != "unknown" else None

                # 좌표 추출 (JavaScript에서 추출한 값 사용)
                latitude = info.get('latitude')
                longitude = info.get('longitude')
                if latitude is not None:
                    try:
                        latitude = float(latitude)
                    except (TypeError, ValueError):
                        latitude = None
                if longitude is not None:
                    try:
                        longitude = float(longitude)
                    except (TypeError, ValueError):
                        longitude = None

                # [7/7] NaverPlaceInfo 생성
                logger.info(f"[7/7] 스크래핑 완료 (좌표: {latitude}, {longitude})")

                return NaverPlaceInfo(
                    place_id=place_id,
                    name=info.get('name') or query,
                    category=info.get('category'),
                    naver_map_url=naver_map_url,
                    latitude=latitude,
                    longitude=longitude,
                    rating=parse_rating(info.get('rating')),
                    visitor_review_count=parse_review_count(info.get('visitor_review_text')),
                    blog_review_count=parse_review_count(info.get('blog_review_text')),
                    description=info.get('description'),
                    address=info.get('address'),
                    road_address=info.get('road_address') or info.get('address'),
                    subway_info=info.get('subway_info'),
                    directions_text=info.get('directions_text'),
                    business_status=info.get('business_status'),
                    business_hours=info.get('business_hours'),
                    open_hours_detail=info.get('open_hours_detail', []),
                    holiday_info=info.get('holiday_info'),
                    phone_number=info.get('phone_number'),
                    homepage_url=info.get('homepage_url'),
                    reservation_available=info.get('reservation_available', False),
                    amenities=amenities,
                    keywords=info.get('keywords', []),
                    tv_appearances=info.get('tv_appearances', []),
                    menu_info=info.get('menu_info', []),
                    image_url=info.get('image_url'),
                    image_urls=info.get('image_urls', [])
                )

            except HTTPException:
                raise
            except Exception as error:
                logger.error(f"네이버 지도 스크래핑 오류: {error}", exc_info=True)
                raise HTTPException(status_code=500, detail="네이버 지도 스크래핑에 실패했습니다")
            finally:
                await self.browser_controller.close_browser()
