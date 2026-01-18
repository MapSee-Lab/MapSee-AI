"""src.models.google_place_info
구글 지도 장소 정보 스키마
"""
from pydantic import BaseModel, Field


class GooglePlaceInfo(BaseModel):
    """
    구글 지도 장소 상세 정보

    구글 지도 검색 결과에서 추출한 장소 정보를 담는 스키마입니다.
    """
    # 기본 정보
    place_id: str = Field(..., description="구글 Place ID (URL에서 추출)")
    name: str = Field(..., description="장소명")
    category: str | None = Field(default=None, description="카테고리 (예: 숯불구이/바베큐전문점)")

    # URL 정보
    google_map_url: str | None = Field(default=None, description="구글 지도 상세 페이지 URL")

    # 위치 정보
    latitude: float | None = Field(default=None, description="위도")
    longitude: float | None = Field(default=None, description="경도")
    address: str | None = Field(default=None, description="주소")
    plus_code: str | None = Field(default=None, description="Plus Code (예: G35M+R3 서울특별시)")

    # 평점/리뷰
    rating: float | None = Field(default=None, description="별점 (0.0 ~ 5.0)")
    review_count: int | None = Field(default=None, description="리뷰 수")
    price_level: str | None = Field(default=None, description="가격대 (예: ₩₩₩)")

    # 영업 정보
    business_status: str | None = Field(default=None, description="영업 상태 (예: 영업 중)")
    business_hours: dict[str, str] | None = Field(default=None, description="요일별 영업 시간")

    # 연락처/링크
    phone_number: str | None = Field(default=None, description="전화번호")
    website_url: str | None = Field(default=None, description="웹사이트 URL")

    # 부가 정보
    description: str | None = Field(default=None, description="장소 설명/소개")
    amenities: list[str] = Field(default_factory=list, description="편의시설/서비스 옵션")
    popular_times: str | None = Field(default=None, description="인기 시간대 정보")

    # 이미지
    image_url: str | None = Field(default=None, description="대표 이미지 URL")
    image_urls: list[str] = Field(default_factory=list, description="이미지 URL 목록 (최대 10개)")

    class Config:
        json_schema_extra = {
            "example": {
                "place_id": "0x357ca44d6e36590b:0xc0019dfb09b9a4e2",
                "name": "늘푸른목장 잠실본점",
                "category": "숯불구이/바베큐전문점",
                "google_map_url": "https://www.google.com/maps/place/...",
                "latitude": 37.509573,
                "longitude": 127.0826454,
                "address": "서울특별시 송파구 백제고분로9길 34",
                "plus_code": "G35M+R3 서울특별시",
                "rating": 4.2,
                "review_count": 753,
                "price_level": "₩₩₩",
                "business_status": "영업 중",
                "business_hours": {
                    "일요일": "24시간 영업",
                    "월요일": "PM 12:00~AM 12:00",
                    "화요일": "PM 12:00~AM 12:00",
                    "수요일": "PM 12:00~AM 12:00",
                    "목요일": "PM 12:00~AM 12:00",
                    "금요일": "PM 12:00~AM 12:00",
                    "토요일": "PM 12:00~AM 12:00"
                },
                "phone_number": "02-3431-4520",
                "website_url": "https://example.com",
                "description": "된장찌개와 냉면으로 완성하는 한상차림",
                "amenities": ["매장 내 식사", "테이크아웃", "배달"],
                "popular_times": "오후 7시~9시 가장 붐빔",
                "image_url": "https://lh5.googleusercontent.com/...",
                "image_urls": ["https://...", "https://..."]
            }
        }
