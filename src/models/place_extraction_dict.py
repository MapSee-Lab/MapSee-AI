"""src.models.place_extraction_dict
장소 추출 데이터 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional


class PlaceExtractionDict(BaseModel):
    """
    장소 추출 데이터 스키마

    Snippet
    {
      "name": "명동 교자",
      "address": "서울특별시 중구 명동길 29",
      "description": "칼국수와 만두로 유명한 맛집"
    }
    """
    name: str = Field(..., description="장소명")
    address: Optional[str] = Field(default=None, description="주소")
    country: Optional[str] = Field(default=None, description="국가 코드")
    latitude: Optional[str] = Field(default=None, description="위도")
    longitude: Optional[str] = Field(default=None, description="경도")
    description: Optional[str] = Field(default=None, description="장소 설명")
    rawData: Optional[str] = Field(default=None, description="AI 추출 원본 데이터")


class PlaceExtractionDictList(BaseModel):
    """
    장소 추출 데이터 리스트 스키마
    """
    places: list[PlaceExtractionDict] = Field(description="장소 추출 데이터 리스트")
