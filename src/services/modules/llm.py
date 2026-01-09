"""src.modules.models.llm
콘텐츠의 텍스트 데이터를 기반으로 LLM을 통해 장소 정보를 구조적으로 추출합니다.
"""

import logging
from google import genai

from src.core.config import settings
from src.models.extraction_state import ExtractionState
from src.models.place_extraction_dict import PlaceExtractionDictList

logger = logging.getLogger(__name__)


# =============================================
# Prompt 완성 함수
def get_llm_prompt(state: ExtractionState):
    extracted_data = state.get('extractedData')
    caption_text = extracted_data.get("captionText", "")
    transcription_text = extracted_data.get('transcriptionText', "")
    ocr_text = extracted_data.get('ocrText', "")

    context = f"""
    ### 게시물 본문 텍스트
    {caption_text}

    ### 게시물 나레이션 텍스트
    {transcription_text}

    ### 게시물 자막 텍스트
    {ocr_text}
    """

    prompt = f"""
    <Context>를 토대로 장소의 상호명과 주소, 요약을 추출하라.
    모든 출력은 JSON 형식이어야 한다.

    <Context>
    {context}
    </Context>

    - name(str): 장소의 상호명
    - address(str): 장소의 주소
    - description(str): 장소에 대한 간단한 설명
    """
    return prompt

# =============================================
# LLM 호출 함수
# =============================================
def get_llm_response(state: ExtractionState) -> None:
    prompt = get_llm_prompt(state)

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": PlaceExtractionDictList.model_json_schema(),
        },
    )
    logger.info("LLM 응답 수신 완료")

    result = PlaceExtractionDictList.model_validate_json(response.text)
    logger.info(f"LLM 추출 결과: {result}")

    state.update({'result': result})


# =============================================
# Demo용 LLM 호출 함수
# =============================================
def get_llm_response_demo(caption: str):
    prompt = f"""
    <Context>를 토대로 장소의 상호명과 주소, 요약을 추출하라.
    모든 출력은 JSON 형식이어야 한다.

    <Context>
    {caption}
    </Context>

    - name(str): 장소의 상호명
    - address(str): 장소의 주소
    - description(str): 장소에 대한 간단한 설명
    """

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": PlaceExtractionDictList.model_json_schema(),
        },
    )
    logger.info("LLM 응답 수신 완료 (Demo)")

    result = PlaceExtractionDictList.model_validate_json(response.text)
    logger.info(f"LLM 데모 추출 결과: {result}")

    return result
