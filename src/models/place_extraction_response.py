"""src.models.place_extraction_response
장소 추출 응답 DTO
"""
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Literal
from src.models.place_extraction_dict import PlaceExtractionDict
from src.models.content_info import ContentInfo


class PlaceExtractionResponse(BaseModel):
    """
    장소 추출 응답 DTO
    백엔드로 반환하는 응답 데이터 구조
    """
    resultStatus: Literal["SUCCESS", "ERROR"] = Field(..., description="처리 결과 상태")
    contentInfo: ContentInfo = Field(..., description="콘텐츠 정보")
    places: list[PlaceExtractionDict] = Field(..., description="장소 추출 결과 리스트")

    class Config:
        json_schema_extra = {
            "example": {
                "resultStatus": "SUCCESS",
                "contentInfo": {
                    "contentId": "550e8400-e29b-41d4-a716-446655440000",
                    "thumbnailUrl": "https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg",
                    "platform": "YOUTUBE",
                    "title": "일본 전국 라멘 투어 - 개당 1200원의 가성비 초밥",
                    "summary": "샷포로 3대 스시 맛집 '토리톤' 방문..."
                },
                "places": [
                    {
                        "name": "명동 교자",
                        "address": "서울특별시 중구 명동길 29",
                        "description": "칼국수와 만두로 유명한 맛집"
                    }
                ]
            }
        }

