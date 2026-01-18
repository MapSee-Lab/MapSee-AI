"""src.services.scraper.common_util
지도 스크래퍼 공통 유틸리티 함수
"""
import re
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 타임아웃 설정 상수
# ============================================================
SCRAPE_TIMEOUT_MS = 60000  # 스크래핑 타임아웃 (밀리초)
PAGE_LOAD_WAIT_SEC = 3  # 페이지 로드 대기 시간 (초)
ELEMENT_WAIT_TIMEOUT_MS = 10000  # 요소 대기 타임아웃 (밀리초)
MAX_IMAGE_COUNT = 10  # 이미지 최대 추출 개수


# ============================================================
# 파싱 유틸리티 함수
# ============================================================
def parse_review_count(text: str | None) -> int | None:
    """
    리뷰 텍스트에서 숫자 추출

    Args:
        text: "(753)" 또는 "리뷰 753개" 또는 "방문자 리뷰 1,510" 형식의 텍스트

    Returns:
        int | None: 파싱된 숫자 또는 None
    """
    if not text:
        return None
    match = re.search(r'([\d,]+)', text)
    if match:
        return int(match.group(1).replace(',', ''))
    return None


def parse_rating(text: str | None) -> float | None:
    """
    별점 텍스트에서 숫자 추출

    Args:
        text: "4.2" 또는 "4.42" 형식의 텍스트

    Returns:
        float | None: 파싱된 별점 또는 None
    """
    if not text:
        return None
    try:
        return float(text.strip())
    except ValueError:
        return None


def parse_aria_label_value(aria_label: str | None, prefix: str) -> str | None:
    """
    aria-label에서 접두사 제거하고 값 추출

    Args:
        aria_label: "주소: 서울특별시 송파구..." 형식
        prefix: "주소: " 같은 접두사

    Returns:
        str | None: 추출된 값
    """
    if not aria_label:
        return None

    if aria_label.startswith(prefix):
        return aria_label[len(prefix):].strip()

    return aria_label.strip()


# ============================================================
# URL 파싱 유틸리티 함수
# ============================================================
def extract_coordinates_from_url(url: str) -> tuple[float | None, float | None]:
    """
    URL에서 위도/경도 추출

    지원 패턴:
    - 구글: !3d{latitude}!4d{longitude}
    - 네이버/구글: @{lat},{lng}

    Args:
        url: 지도 URL

    Returns:
        tuple[float | None, float | None]: (위도, 경도)
    """
    latitude = None
    longitude = None

    # 패턴 1: !3d{latitude}!4d{longitude} (구글 지도)
    lat_match = re.search(r'!3d(-?[\d.]+)', url)
    lng_match = re.search(r'!4d(-?[\d.]+)', url)

    if lat_match:
        try:
            latitude = float(lat_match.group(1))
        except ValueError:
            pass

    if lng_match:
        try:
            longitude = float(lng_match.group(1))
        except ValueError:
            pass

    # 패턴 2: @{lat},{lng} (네이버/구글 공통)
    if latitude is None or longitude is None:
        alt_match = re.search(r'@(-?[\d.]+),(-?[\d.]+)', url)
        if alt_match:
            try:
                latitude = float(alt_match.group(1))
                longitude = float(alt_match.group(2))
            except ValueError:
                pass

    return latitude, longitude


def extract_google_place_id_from_url(url: str) -> str | None:
    """
    URL에서 구글 Place ID 추출

    Args:
        url: 구글 지도 URL (예: ...!1s0x357ca44d6e36590b:0xc0019dfb09b9a4e2...)

    Returns:
        str | None: Place ID 또는 None
    """
    # 패턴 1: !1s 뒤의 Place ID (0x...형식)
    match = re.search(r'!1s(0x[a-f0-9]+:0x[a-f0-9]+)', url)
    if match:
        return match.group(1)

    # 패턴 2: /place/ 뒤의 인코딩된 이름
    match = re.search(r'/place/([^/]+)', url)
    if match:
        return match.group(1)

    return None


def extract_naver_place_id_from_url(url: str) -> str | None:
    """
    URL에서 네이버 Place ID 추출

    Args:
        url: 네이버 지도 URL (예: .../place/11679241?...)

    Returns:
        str | None: Place ID 또는 None
    """
    match = re.search(r'/place/(\d+)', url)
    return match.group(1) if match else None


# ============================================================
# 가격대 파싱 유틸리티
# ============================================================
def parse_price_level(price_aria: str | None) -> str | None:
    """
    가격대 aria-label에서 가격 수준 추출

    Args:
        price_aria: "비쌈", "₩₩₩" 등의 텍스트

    Returns:
        str | None: 가격대 문자열 (₩, ₩₩, ₩₩₩) 또는 None
    """
    if not price_aria:
        return None

    # ₩ 문자가 있으면 그대로 추출
    if '₩' in price_aria:
        price_match = re.search(r'(₩+)', price_aria)
        if price_match:
            return price_match.group(1)

    # 텍스트로 매핑
    if '비싸' in price_aria or '비쌈' in price_aria:
        return "₩₩₩"
    elif '보통' in price_aria:
        return "₩₩"
    elif '저렴' in price_aria:
        return "₩"

    return None
