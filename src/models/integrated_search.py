"""src.models.integrated_search
통합 장소 검색 응답 모델
Instagram → LLM → 네이버 지도 파이프라인 결과
"""
from pydantic import BaseModel, Field

from src.models.naver_place_info import NaverPlaceInfo


class SnsInfo(BaseModel):
    """SNS 메타데이터"""
    platform: str = Field(..., description="플랫폼 (instagram, youtube 등)")
    content_type: str = Field(..., description="콘텐츠 타입 (post, reel, igtv 등)")
    url: str = Field(..., description="원본 URL")
    author: str | None = Field(default=None, description="작성자")
    caption: str | None = Field(default=None, description="게시물 본문")
    likes_count: int | None = Field(default=None, description="좋아요 수")
    comments_count: int | None = Field(default=None, description="댓글 수")
    posted_at: str | None = Field(default=None, description="게시 날짜")
    hashtags: list[str] = Field(default_factory=list, description="해시태그 리스트")
    og_image: str | None = Field(default=None, description="대표 이미지 URL")
    image_urls: list[str] = Field(default_factory=list, description="이미지 URL 리스트")
    author_profile_image_url: str | None = Field(default=None, description="작성자 프로필 이미지")


class IntegratedPlaceSearchResponse(BaseModel):
    """통합 장소 검색 결과"""

    # SNS 정보
    sns_info: SnsInfo = Field(..., description="SNS 메타데이터")

    # LLM 추출 결과
    extracted_place_names: list[str] = Field(default_factory=list, description="LLM이 추출한 장소명 리스트")
    has_places: bool = Field(default=False, description="장소 존재 여부")

    # 네이버 지도 검색 결과
    place_details: list[NaverPlaceInfo] = Field(default_factory=list, description="네이버 지도 검색 결과")

    # 처리 통계
    total_extracted: int = Field(default=0, description="추출된 장소 수")
    total_found: int = Field(default=0, description="네이버에서 찾은 장소 수")
    failed_searches: list[str] = Field(default_factory=list, description="검색 실패한 장소명")
