"""src.utils.url_classifier
URL 분류 유틸리티 - SNS 플랫폼 및 콘텐츠 타입 감지
"""
from urllib.parse import urlparse
from dataclasses import dataclass
from fastapi import HTTPException


@dataclass
class UrlClassification:
    """URL 분류 결과"""
    platform: str      # "instagram", "youtube"
    content_type: str  # "post", "reel", "igtv", "video", "shorts"
    url: str


def classify_url(url: str) -> UrlClassification:
    """
    URL을 분석하여 플랫폼과 콘텐츠 타입을 분류

    Args:
        url: SNS URL

    Returns:
        UrlClassification: 분류 결과

    Raises:
        HTTPException(400): 지원하지 않는 URL인 경우
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()

    # Instagram
    if 'instagram.com' in domain:
        if '/p/' in path:
            return UrlClassification("instagram", "post", url)
        elif '/reel/' in path or '/reels/' in path:
            return UrlClassification("instagram", "reel", url)
        elif '/tv/' in path:
            return UrlClassification("instagram", "igtv", url)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 Instagram URL 형식: {path}"
            )

    # YouTube
    if 'youtube.com' in domain or 'youtu.be' in domain:
        if '/shorts/' in path:
            return UrlClassification("youtube", "shorts", url)
        else:
            return UrlClassification("youtube", "video", url)

    # 지원하지 않는 플랫폼
    raise HTTPException(
        status_code=400,
        detail=f"지원하지 않는 플랫폼: {domain}"
    )
