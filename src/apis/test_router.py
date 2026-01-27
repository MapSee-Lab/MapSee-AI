"""src.apis.test_router
테스트 API 라우터 - SNS 스크래핑 테스트용
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services.scraper.scrape_router import route_and_scrape
from src.services.scraper.platforms.naver_map_scraper import NaverMapScraper
from src.services.scraper.platforms.google_map_scraper import GoogleMapScraper
from src.models.geocoding_models import (
    GeocodingTestRequest,
    GeocodingResponse,
    GeocodingProvider
)
from src.services.geocoding_service import (
    geocode_with_kakao,
    geocode_with_nominatim
)
from src.services.modules.ollama_llm import extract_place_names_with_ollama, OllamaPlaceResult
from src.models.integrated_search import SnsInfo, IntegratedPlaceSearchResponse
from src.core.exceptions import CustomError

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


class LlmPlaceExtractRequest(BaseModel):
    """LLM 장소명 추출 요청"""
    caption: str = Field(..., description="인스타그램 게시물 본문 텍스트", min_length=1)


class IntegratedSearchRequest(BaseModel):
    """통합 장소 검색 요청"""
    url: str = Field(..., description="Instagram URL")


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


@router.post("/geocode", response_model=GeocodingResponse, status_code=200)
async def test_geocode(request: GeocodingTestRequest):
    """
    주소를 위도/경도로 변환 (테스트용 - provider 선택 가능)

    - POST /api/test/geocode
    - Body: {"address": "서울시 강남구", "provider": "kakao"}
    - provider: "kakao" (기본) | "nominatim"
    - 성공: 200 + GeocodingResponse
    - 실패: 404 (주소 못 찾음)
    """
    logger.info(f"Geocoding 테스트 요청: address='{request.address}', provider='{request.provider.value}'")

    try:
        if request.provider == GeocodingProvider.KAKAO:
            result = await geocode_with_kakao(request.address)
        else:
            result = await geocode_with_nominatim(request.address)

        return GeocodingResponse(
            address=request.address,
            latitude=result.latitude,
            longitude=result.longitude,
            provider=result.provider
        )
    except CustomError as error:
        raise HTTPException(status_code=404, detail=error.message)


@router.post("/llm-place-extract", response_model=OllamaPlaceResult, status_code=200)
async def extract_place_names(request: LlmPlaceExtractRequest):
    """
    Ollama LLM을 사용하여 텍스트에서 장소명을 추출

    인스타그램 caption에서 장소명(가게명, 상호명, 식당명 등)을 추출합니다.
    ai.suhsaechan.kr의 gemma3:1b-it-qat 모델을 사용합니다.

    - POST /api/test/llm-place-extract
    - Body: {"caption": "1. #스시호 -위치_서울 송파구 가락로 98길..."}
    - 성공: 200 + {"place_names": ["스시호", ...], "has_places": true}
    - 실패 시에도 빈 결과 반환 (에러 발생하지 않음)

    추출 규칙:
    - 해시태그(#) 붙은 장소명도 추출 (#스시호 → 스시호)
    - 일반 명사(맛집, 초밥 등)는 제외
    - 장소가 없으면 빈 배열 반환
    """
    logger.info(f"LLM 장소명 추출 요청: caption 길이={len(request.caption)}")

    result = await extract_place_names_with_ollama(request.caption)

    logger.info(f"장소명 추출 완료: {result.place_names}")
    return result


@router.post("/integrated-place-search", response_model=IntegratedPlaceSearchResponse, status_code=200)
async def integrated_place_search(request: IntegratedSearchRequest):
    """
    Instagram URL에서 장소 정보를 통합 추출

    전체 파이프라인:
    1. Instagram 파싱 → caption 추출
    2. Ollama LLM → 장소명 추출
    3. 네이버 지도 검색 → 상세 정보

    - POST /api/test/integrated-place-search
    - Body: {"url": "https://www.instagram.com/p/..."}
    - 성공: 200 + IntegratedPlaceSearchResponse
    - 실패: 400 (Instagram 파싱 실패)

    네이버 지도 검색은 개별 실패 허용 (failed_searches에 기록)
    """
    # Step 1: 요청 수신
    logger.info(f"[통합 검색] Step 1/5: 요청 수신 - url={request.url}")

    # Step 2: Instagram 파싱
    logger.info("[통합 검색] Step 2/5: Instagram 파싱 시작")
    try:
        sns_data = await route_and_scrape(request.url)
    except HTTPException:
        raise
    except Exception as error:
        logger.info(f"[통합 검색] Step 2/5: Instagram 파싱 실패 - {error}")
        raise HTTPException(status_code=400, detail=f"Instagram 파싱 실패: {error}")

    # SNS 정보 구성
    sns_info = SnsInfo(
        platform=sns_data.get("platform", "unknown"),
        content_type=sns_data.get("content_type", "unknown"),
        url=sns_data.get("url", request.url),
        author=sns_data.get("author"),
        caption=sns_data.get("caption"),
        likes_count=sns_data.get("likes_count"),
        comments_count=sns_data.get("comments_count"),
        posted_at=sns_data.get("posted_at"),
        hashtags=sns_data.get("hashtags", []),
        og_image=sns_data.get("og_image"),
        image_urls=sns_data.get("image_urls", []),
        author_profile_image_url=sns_data.get("author_profile_image_url")
    )

    caption = sns_data.get("caption") or ""
    logger.info(f"[통합 검색] Step 2/5: Instagram 파싱 완료 - author={sns_info.author}, caption 길이={len(caption)}")

    # Step 3: LLM 장소 추출
    logger.info(f"[통합 검색] Step 3/5: LLM 장소 추출 시작 - caption 길이={len(caption)}")

    if not caption.strip():
        logger.info("[통합 검색] Step 3/5: caption이 비어있어 장소 추출 스킵")
        extracted_place_names = []
        has_places = False
    else:
        llm_result = await extract_place_names_with_ollama(caption)
        extracted_place_names = llm_result.place_names
        has_places = llm_result.has_places

    logger.info(f"[통합 검색] Step 3/5: LLM 장소 추출 완료 - 추출된 장소 수={len(extracted_place_names)}")

    # Step 4: 네이버 지도 검색
    place_details = []
    failed_searches = []

    if extracted_place_names:
        logger.info(f"[통합 검색] Step 4/5: 네이버 지도 검색 시작 - 검색할 장소 수={len(extracted_place_names)}")
        scraper = NaverMapScraper()

        for index, place_name in enumerate(extracted_place_names, 1):
            logger.info(f"[통합 검색] Step 4/5: 네이버 지도 검색 ({index}/{len(extracted_place_names)}) - query={place_name}")
            try:
                place_info = await scraper.search_and_scrape(place_name)
                place_details.append(place_info)
                logger.info(f"[통합 검색] Step 4/5: 검색 성공 - {place_info.name} ({place_info.place_id})")
            except Exception as error:
                logger.info(f"[통합 검색] Step 4/5: 검색 실패 - query={place_name}, error={error}")
                failed_searches.append(place_name)

        logger.info(f"[통합 검색] Step 4/5: 네이버 지도 검색 완료 - 성공={len(place_details)}, 실패={len(failed_searches)}")
    else:
        logger.info("[통합 검색] Step 4/5: 추출된 장소가 없어 네이버 지도 검색 스킵")

    # Step 5: 결과 통합
    total_extracted = len(extracted_place_names)
    total_found = len(place_details)

    logger.info(f"[통합 검색] Step 5/5: 결과 통합 완료 - 총 추출={total_extracted}, 총 발견={total_found}")

    return IntegratedPlaceSearchResponse(
        sns_info=sns_info,
        extracted_place_names=extracted_place_names,
        has_places=has_places,
        place_details=place_details,
        total_extracted=total_extracted,
        total_found=total_found,
        failed_searches=failed_searches
    )