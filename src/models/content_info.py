"""src.models.content_info
콘텐츠 정보 DTO
"""
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional


class ContentInfo(BaseModel):
    """
    콘텐츠 정보 DTO
    SNS 콘텐츠의 메타데이터를 담는 스키마

    Snippet
    {
      "contentId": "550e8400-e29b-41d4-a716-446655440000",
      "thumbnailUrl": "https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg",
      "platform": "YOUTUBE",
      "title": "일본 전국 라멘 투어 - 개당 1200원의 가성비 초밥",
      "summary": "샷포로 3대 스시 맛집 '토리톤' 방문..."
    }
    """
    contentId: UUID = Field(..., description="콘텐츠 UUID")
    title: str = Field(..., description="콘텐츠 제목")
    contentUrl: Optional[str] = Field(default=None, description="콘텐츠 URL")
    thumbnailUrl: Optional[str] = Field(default=None, description="썸네일 URL")
    platformUploader: Optional[str] = Field(default=None, description="업로더 아이디")
    summary: Optional[str] = Field(default=None, description="AI 콘텐츠 요약")

    class Config:
        json_schema_extra = {
            "example": {
                "contentId": "550e8400-e29b-41d4-a716-446655440000",
                "thumbnailUrl": "https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg",
                "title": "일본 전국 라멘 투어 - 개당 1200원의 가성비 초밥",
                "summary": "샷포로 3대 스시 맛집 '토리톤' 방문...",
                "platformUploader": "tripgether_official",
                "contentUrl": "https://www.youtube.com/watch?v=VIDEO_ID"
            }
        }

