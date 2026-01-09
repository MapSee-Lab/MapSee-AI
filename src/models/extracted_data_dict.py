"""src.models.extracted_data_dict
추출된 데이터 스키마
"""
from typing import TypedDict, List
from io import BytesIO

class ExtractedDataDict(TypedDict):
    """
    추출된 데이터 스키마

    total=False로 설정하여 모든 필드를 선택적으로 만듭니다.
    파이프라인 진행에 따라 점진적으로 필드가 채워집니다.
    """
    contentStream: BytesIO
    imageStream: List[BytesIO]
    captionText: str
    audioStream: BytesIO
    transcriptionText: str
    ocrText: str
