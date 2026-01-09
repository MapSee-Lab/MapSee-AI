"""src.utils.common
공통 유틸리티 함수 (Spring의 CommonUtil 스타일)
"""
import logging
from io import BytesIO
from typing import Union
from fastapi import Header, HTTPException
from src.core.config import settings

logger = logging.getLogger(__name__)


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    백엔드 요청의 API Key를 검증합니다.

    Args:
        x_api_key(str): Request Header의 X-API-Key 값

    Raises:
        HTTPException: API Key가 일치하지 않을 경우 401

    Returns:
        str: 검증된 API Key
    """
    if x_api_key != settings.AI_SERVER_API_KEY:
        logger.warning("유효하지 않은 API Key 시도")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid API Key"
        )
    return x_api_key


def validate_url_length(url: str, max_length: int = 2048) -> None:
    """
    URL 길이 검증

    Args:
        url: 검증할 URL
        max_length: 최대 길이 (기본 2048)

    Raises:
        CustomError: URL 길이 초과 시
    """
    from src.core.exceptions import CustomError

    if len(url) > max_length:
        raise CustomError(f"URL 길이가 {max_length}자를 초과했습니다")


def mask_sensitive_data(data: str, show_chars: int = 2) -> str:
    """
    민감 데이터 마스킹 (로그 출력 시 사용)

    Args:
        data: 마스킹할 문자열
        show_chars: 앞뒤로 보여줄 문자 수

    Returns:
        str: 마스킹된 문자열

    Examples:
        >>> mask_sensitive_data("my_secret_key_12345")
        'my***45'
    """
    if not data or len(data) <= show_chars * 2:
        return "****"

    return data[:show_chars] + "*" * (len(data) - show_chars * 2) + data[-show_chars:]


def convert_to_bytesio(data: Union[BytesIO, bytes]) -> BytesIO:
    """
    bytes 또는 BytesIO를 BytesIO로 변환합니다.
    OCR 모듈 등에서 타입 안전성을 보장하기 위해 사용합니다.

    Args:
        data: 변환할 bytes 또는 BytesIO 객체

    Returns:
        BytesIO: 변환된 BytesIO 객체

    Raises:
        TypeError: 지원하지 않는 타입인 경우

    Examples:
        >>> convert_to_bytesio(b"image data")
        <_io.BytesIO object>
        >>> convert_to_bytesio(BytesIO(b"image data"))
        <_io.BytesIO object>
    """
    if isinstance(data, bytes):
        return BytesIO(data)
    if isinstance(data, BytesIO):
        return data
    raise TypeError(f"지원하지 않는 타입입니다. bytes 또는 BytesIO만 가능합니다: {type(data)}")


def validate_image_stream(stream: Union[BytesIO, bytes, None]) -> tuple[bool, BytesIO | None]:
    """
    이미지 스트림의 유효성을 검증합니다.
    None 체크, 빈 데이터 체크, 타입 변환을 수행합니다.

    Args:
        stream: 검증할 스트림 (BytesIO, bytes, 또는 None)

    Returns:
        tuple[bool, BytesIO | None]: (유효 여부, 변환된 BytesIO 객체)
        - 유효한 경우: (True, BytesIO 객체)
        - 유효하지 않은 경우: (False, None)

    Examples:
        >>> validate_image_stream(BytesIO(b"image data"))
        (True, <_io.BytesIO object>)
        >>> validate_image_stream(None)
        (False, None)
        >>> validate_image_stream(b"")
        (False, None)
    """
    if stream is None:
        logger.warning("이미지 스트림이 None입니다.")
        return False, None

    try:
        # 타입 변환
        bytesio_stream = convert_to_bytesio(stream)

        # 빈 데이터 검증
        bytesio_stream.seek(0, 2)  # 끝으로 이동
        size = bytesio_stream.tell()
        if size == 0:
            logger.warning("이미지 스트림이 비어있습니다.")
            return False, None

        bytesio_stream.seek(0)  # 처음으로 복귀
        return True, bytesio_stream

    except (TypeError, AttributeError) as e:
        logger.warning(f"이미지 스트림 검증 실패: {e}")
        return False, None
    except Exception as e:
        logger.warning(f"이미지 스트림 검증 중 예기치 않은 오류: {e}")
        return False, None
