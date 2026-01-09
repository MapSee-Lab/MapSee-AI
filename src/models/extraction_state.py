"""src.models.extraction_state
장소 추출 플로우 스키마
"""
from typing import TypedDict
from src.models.extracted_data_dict import ExtractedDataDict
from src.models.place_extraction_dict import PlaceExtractionDictList

class ExtractionState(TypedDict):
    """
    장소 추출 플로우 스키마

    Snippet
    {
        "contentId": "place-uuid-1",
        "snsUrl": "https://www.instagram.com/reel/ABC123/",
        "siteDomain": "instagram",
        "fileType": "video",
        "authorName": "Tripgether Official",
        "authorHandle": "@tripgether_official",
        "extractedData": {
            "contentStream": b'...',
            "captionText": "여행 중 만난 맛집!",
            "audioStream": b'...',
            "transcriptionText": "안녕하세요 여러분...",
            "ocrText": "특별 할인 행사 중!"
        },
        "result": [{
            "name": "명동 교자",
            "address": "서울특별시 중구 명동길 29",
            "description": "칼국수와 만두로 유명한 맛집",
        }]
    }
    """
    contentId: str # 장소 추출 고유 ID
    snsUrl: str # 원본 URL
    snsPlatform: str # 플랫폼 도메인 (예: "instagram", "youtube")
    contentType: str # 파일 유형 (예: "video", "image")
    authorName: str # 게시자 이름 (예: "Tripgether Official")
    authorHandle: str  # 게시자 아이디 또는 핸들 (예: "@tripgether_official")
    extractedData: ExtractedDataDict # 추출된 데이터 딕셔너리
    result: PlaceExtractionDictList # LLM을 통해 추출된 장소 정보 리스트

