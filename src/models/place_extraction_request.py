"""src.models.place_extraction_request
장소 추출 요청 DTO
"""
from pydantic import BaseModel, Field
from uuid import UUID


class PlaceExtractionRequest(BaseModel):
    """
    장소 추출 요청 DTO
    백엔드로부터 받는 요청 데이터 구조
    """
    contentId: UUID = Field(..., description="Content UUID")
    snsUrl: str = Field(..., description="SNS URL (Instagram Reels)")

    class Config:
        json_schema_extra = {
            "example": {
                "contentId": "550e8400-e29b-41d4-a716-446655440000",
                "snsUrl": "https://www.instagram.com/p/ABC123/"
            }
        }

