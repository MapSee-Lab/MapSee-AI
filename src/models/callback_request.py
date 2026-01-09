"""src.models.callback_request.py
AI -> 백엔드 요청 DTO
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional
from uuid import UUID
from src.models.content_info import ContentInfo
from src.models.place_extraction_dict import PlaceExtractionDict

class AiCallbackRequest(BaseModel):
    contentId: UUID = Field(..., description="Content UUID")
    resultStatus: Literal["SUCCESS", "FAILED"] = Field(..., description="처리 결과 상태")
    snsPlatform: Literal["INSTAGRAM", "YOUTUBE", "YOUTUBE_SHORTS", "TIKTOK", "FACEBOOK", "TWITTER"] = Field(
        ..., description="SNS 플랫폼"
    )
    contentInfo: Optional[ContentInfo] = Field(default=None, description="콘텐츠 정보 (SUCCESS 시 필수)")
    places: List[PlaceExtractionDict] = Field(default_factory=list, description="장소 정보 리스트")
    rawData: Optional[dict] = Field(default=None, description="AI 추출 원본 데이터")

    @model_validator(mode="after")
    def validate_success_payload(cls, model: "AiCallbackRequest") -> "AiCallbackRequest":
        if model.resultStatus == "SUCCESS":
            if model.contentInfo is None:
                raise ValueError("contentInfo is required when resultStatus is SUCCESS")
        else:
            model.places = []
        return model
