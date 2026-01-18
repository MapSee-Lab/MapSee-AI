"""src.apis.test_router
테스트 API 라우터 - SNS 스크래핑 테스트용
"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.services.scraper.scrape_router import route_and_scrape
from src.services.scraper.platforms.naver_map_scraper import NaverMapScraper
from src.services.scraper.platforms.google_map_scraper import GoogleMapScraper

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/test", tags=["테스트 API"])


class ScrapeRequest(BaseModel):
    url: str


class NaverMapSearchRequest(BaseModel):
    """네이버 지도 검색 요청"""
    query: str = Field(..., description="검색어 (예: 늘푸른목장)", min_length=1)


class GoogleMapSearchRequest(BaseModel):
    """구글 지도 검색 요청"""
    query: str = Field(..., description="검색어 (예: 늘푸른목장)", min_length=1)


@router.post("/scrape", status_code=200)
async def scrape_url(request: ScrapeRequest):
    """
    SNS URL에서 메타데이터를 Playwright로 스크래핑

    - POST /api/test/scrape
    - Body: {"url": "https://www.instagram.com/p/..."}
    - 성공: 200 + 메타데이터
    - 실패: 4xx/5xx + 에러 메시지
    """
    logger.info(f"스크래핑 요청: {request.url}")
    return await route_and_scrape(request.url)


@router.get("/health", status_code=200)
async def health_check():
    """스크래핑 테스트 API 상태 확인"""
    return {"status": "ok"}


@router.post("/naver-map", status_code=200)
async def scrape_naver_map(request: NaverMapSearchRequest):
    """
    네이버 지도에서 장소 정보 스크래핑

    장소명을 검색하여 첫 번째 검색 결과의 상세 정보를 추출합니다.

    - POST /api/test/naver-map
    - Body: {"query": "늘푸른목장"}
    - 성공: 200 + NaverPlaceInfo
    - 실패: 4xx/5xx + 에러 메시지

    추출 정보:
    - 장소명, 카테고리
    - 별점, 리뷰 수 (방문자/블로그)
    - 주소, 지하철 정보
    - 영업 상태, 영업 시간
    - 전화번호, 편의시설
    """
    logger.info(f"네이버 지도 스크래핑 요청: query='{request.query}'")

    scraper = NaverMapScraper()
    result = await scraper.search_and_scrape(request.query)

    logger.info(f"스크래핑 완료: {result.name} ({result.place_id})")
    return result


@router.post("/google-map", status_code=200)
async def scrape_google_map(request: GoogleMapSearchRequest):
    """
    구글 지도에서 장소 정보 스크래핑

    장소명을 검색하여 첫 번째 검색 결과의 상세 정보를 추출합니다.

    - POST /api/test/google-map
    - Body: {"query": "늘푸른목장"}
    - 성공: 200 + GooglePlaceInfo
    - 실패: 4xx/5xx + 에러 메시지

    추출 정보:
    - 장소명, 카테고리
    - 별점, 리뷰 수
    - 가격대, 주소
    - 영업 상태, 요일별 영업 시간
    - 전화번호, Plus Code
    - 위도/경도, 웹사이트 URL
    - 대표 이미지 URL
    """
    logger.info(f"구글 지도 스크래핑 요청: query='{request.query}'")

    scraper = GoogleMapScraper()
    result = await scraper.search_and_scrape(request.query)

    logger.info(f"스크래핑 완료: {result.name} ({result.place_id})")
    return result
