"""src.services.modules.ollama_llm
Ollama API를 사용하여 텍스트에서 장소명을 추출합니다.
ai.suhsaechan.kr 서버의 gemma3:1b-it-qat 모델을 사용합니다.
"""

import json
import logging
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.exceptions import CustomError
from src.utils.common import http_post_json

logger = logging.getLogger(__name__)


# =============================================
# Pydantic 모델
# =============================================
class OllamaPlaceResult(BaseModel):
    """Ollama 장소명 추출 결과"""
    place_names: list[str] = Field(default_factory=list, description="추출된 장소명 리스트")
    has_places: bool = Field(default=False, description="장소 존재 여부")


# =============================================
# JSON Schema (Ollama format 파라미터용)
# =============================================
PLACE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "place_names": {
            "type": "array",
            "items": {"type": "string"}
        },
        "has_places": {
            "type": "boolean"
        }
    },
    "required": ["place_names", "has_places"],
    "additionalProperties": False
}


# =============================================
# 프롬프트 템플릿
# =============================================
PLACE_EXTRACTION_PROMPT = """당신은 인스타그램 게시물에서 **실제 방문할 수 있는 장소명**을 추출하는 전문가입니다.

## 당신의 임무
텍스트를 읽고, 사람들이 **네이버 지도에서 검색해서 찾아갈 수 있는 장소명**을 추출하세요.

## 중요: 정확한 장소명 추출
- 지점명이 있으면 **지점명까지 포함**해서 추출하세요
- "스타벅스" (X) → "스타벅스 종합운동장역점" (O)
- "블루보틀" (X) → "블루보틀 성수" (O)

## 예시

### 예시 1
입력: "강남역 근처 파스타 맛집 #라라브레드 다녀왔어요! 분위기 좋고 맛있음"
출력: ["라라브레드"]
이유: "라라브레드"가 가게명. "강남역", "파스타", "맛집"은 장소명 아님

### 예시 2
입력: "1. #스시호 -위치_서울 송파구 2. #멘야하나비 강남점"
출력: ["스시호", "멘야하나비 강남점"]
이유: 지점명이 있으면 포함. "송파구"는 주소일 뿐

### 예시 3
입력: "스타벅스 종합운동장역점에서 커피 마시고 블루보틀 성수 갔다옴"
출력: ["스타벅스 종합운동장역점", "블루보틀 성수"]
이유: 지점명까지 포함된 전체 이름이 장소명

### 예시 4
입력: "서울 카페 추천! 요즘 핫한 곳들 #성수동카페투어"
출력: []
이유: 구체적인 가게명 없음. "성수동카페투어"는 해시태그 키워드

### 예시 5
입력: "홍대 맛집 리스트 정리 중... 맛집, 카페, 술집 다 모아봄"
출력: []
이유: "맛집", "카페", "술집"은 카테고리, 가게명 아님

## 주의사항
- 해시태그(#)는 제거하고 반환
- 인스타 계정(@username)은 가게명이 아님
- 단독 지역명(송파구, 강남역)은 장소명 아님
- 하지만 "스타벅스 강남역점"처럼 지점명의 일부면 포함

<Context>
{caption}
</Context>"""


# =============================================
# Ollama API 호출 함수
# =============================================
async def extract_place_names_with_ollama(
    caption: str,
    max_retries: int = 3
) -> OllamaPlaceResult:
    """
    Ollama API를 사용하여 텍스트에서 장소명을 추출합니다.

    Args:
        caption: 인스타그램 게시물 본문 텍스트
        max_retries: 최대 재시도 횟수 (기본 3회)

    Returns:
        OllamaPlaceResult: 추출된 장소명 리스트와 존재 여부

    Raises:
        CustomError: API 호출 실패 또는 파싱 실패 시
    """
    if not caption or not caption.strip():
        logger.warning("빈 caption이 전달되었습니다.")
        return OllamaPlaceResult(place_names=[], has_places=False)

    prompt = PLACE_EXTRACTION_PROMPT.format(caption=caption)

    request_body = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "format": PLACE_EXTRACTION_SCHEMA
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": settings.OLLAMA_API_KEY
    }

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Ollama API 호출 시도 {attempt}/{max_retries} (model={settings.OLLAMA_MODEL})")

            response = await http_post_json(
                url=settings.OLLAMA_API_URL,
                json_body=request_body,
                headers=headers
            )

            # 응답에서 content 추출
            message = response.get("message", {})
            content = message.get("content", "")

            if not content:
                logger.warning(f"Ollama 응답에 content가 없습니다: {response}")
                last_error = CustomError("Ollama 응답에 content가 없습니다")
                continue

            # JSON 파싱
            try:
                parsed = json.loads(content)
                parsed_place_names = parsed.get("place_names", [])

                # has_places는 place_names 길이로 자동 계산 (LLM 응답 무시)
                result = OllamaPlaceResult(
                    place_names=parsed_place_names,
                    has_places=len(parsed_place_names) > 0
                )

                logger.info(f"장소명 추출 성공: {result.place_names}")
                return result

            except json.JSONDecodeError as json_error:
                logger.warning(f"JSON 파싱 실패 (시도 {attempt}): {json_error}")
                last_error = CustomError(f"JSON 파싱 실패: {json_error}")
                continue

        except CustomError as error:
            logger.warning(f"Ollama API 호출 실패 (시도 {attempt}): {error.message}")
            last_error = error
            continue

        except Exception as error:
            logger.error(f"예기치 않은 오류 (시도 {attempt}): {error}")
            last_error = CustomError(f"예기치 않은 오류: {error}")
            continue

    # 모든 재시도 실패
    logger.error(f"Ollama API 호출 {max_retries}회 모두 실패")

    # 실패 시 빈 결과 반환 (에러를 던지지 않음)
    return OllamaPlaceResult(place_names=[], has_places=False)
