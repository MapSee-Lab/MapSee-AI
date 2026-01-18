"""src.models.naver_place_info
네이버 지도 장소 정보 스키마
"""
from pydantic import BaseModel, Field


class NaverPlaceInfo(BaseModel):
    """
    네이버 지도 장소 상세 정보

    네이버 지도 검색 결과에서 추출한 장소 정보를 담는 스키마입니다.
    """
    # 기본 정보
    place_id: str = Field(..., description="네이버 Place ID")
    name: str = Field(..., description="장소명")
    category: str | None = Field(default=None, description="카테고리 (예: 소고기구이)")

    # URL 정보 (라우팅용)
    naver_map_url: str | None = Field(default=None, description="네이버 지도 상세 페이지 URL")

    # 위치 정보
    latitude: float | None = Field(default=None, description="위도")
    longitude: float | None = Field(default=None, description="경도")
    address: str | None = Field(default=None, description="주소")
    road_address: str | None = Field(default=None, description="도로명 주소")
    subway_info: str | None = Field(default=None, description="지하철 정보 (예: 잠실새내역 4번 출구에서 412m)")
    directions_text: str | None = Field(default=None, description="찾아가는 길 설명")

    # 평점/리뷰
    rating: float | None = Field(default=None, description="별점 (0.0 ~ 5.0)")
    visitor_review_count: int | None = Field(default=None, description="방문자 리뷰 수")
    blog_review_count: int | None = Field(default=None, description="블로그 리뷰 수")

    # 영업 정보
    business_status: str | None = Field(default=None, description="영업 상태 (예: 영업 중)")
    business_hours: str | None = Field(default=None, description="영업 시간 요약")
    open_hours_detail: list[str] = Field(default_factory=list, description="요일별 상세 영업시간")
    holiday_info: str | None = Field(default=None, description="휴무일 정보")

    # 연락처/링크
    phone_number: str | None = Field(default=None, description="전화번호")
    homepage_url: str | None = Field(default=None, description="홈페이지 URL")
    reservation_available: bool = Field(default=False, description="예약 가능 여부")

    # 부가 정보
    description: str | None = Field(default=None, description="한줄 설명")
    amenities: list[str] = Field(default_factory=list, description="편의시설 목록")
    keywords: list[str] = Field(default_factory=list, description="키워드/태그")
    tv_appearances: list[str] = Field(default_factory=list, description="TV 방송 출연 정보")
    menu_info: list[str] = Field(default_factory=list, description="대표 메뉴")

    # 이미지
    image_url: str | None = Field(default=None, description="대표 이미지 URL")
    image_urls: list[str] = Field(default_factory=list, description="이미지 URL 목록 (최대 10개)")

    class Config:
        json_schema_extra = {
            "example": {
                "place_id": "11679241",
                "name": "늘푸른목장 잠실본점",
                "category": "소고기구이",
                "naver_map_url": "https://map.naver.com/p/search/늘푸른목장/place/11679241",
                "latitude": 37.5112,
                "longitude": 127.0867,
                "address": "서울 송파구 백제고분로9길 34 1F",
                "road_address": "서울 송파구 백제고분로9길 34 1F",
                "subway_info": "잠실새내역 4번 출구에서 412m",
                "directions_text": "잠실새내역 4번 출구에서 맥도널드 골목 끼고...",
                "rating": 4.42,
                "visitor_review_count": 1510,
                "blog_review_count": 1173,
                "business_status": "영업 중",
                "business_hours": "24:00에 영업 종료",
                "open_hours_detail": ["월 11:30 - 24:00", "화 11:30 - 24:00"],
                "holiday_info": "연중무휴",
                "phone_number": "02-3431-4520",
                "homepage_url": "http://example.com",
                "reservation_available": True,
                "description": "된장찌개와 냉면으로 완성하는 한상차림",
                "amenities": ["단체 이용 가능", "주차", "발렛파킹"],
                "keywords": ["소고기", "한우", "회식"],
                "tv_appearances": ["줄서는식당 14회 (24.05.13)"],
                "menu_info": ["경주갈비살", "한우된장밥"],
                "image_url": "https://...",
                "image_urls": ["https://...", "https://..."]
            }
        }
