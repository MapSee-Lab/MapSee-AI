"""src.modules.preprocess.sns.py
- 인스타그램 릴스 게시물을 다운로드 합니다.
    (yt-dlp 사용 버전)
- 유튜브 숏츠를 다운로드 합니다.
    (Google API 및 yt-dlp 사용 버전)
"""
import os
import json
import requests
import tempfile
import subprocess
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
import yt_dlp
from yt_dlp import YoutubeDL
from src.core.config import settings
from src.models import ExtractionState

import logging

logger = logging.getLogger(__name__)


# =============================================
# URL 파싱
# =============================================
def extract_youtube_id(url:str):
    """
    유튜브 URL로부터 video_id를 추출합니다.
    /shorts/, /watch?v=, youtu.be 세 가지 패턴을 모두 지원합니다.
    """
    # Load URL
    parsed = urlparse(url)

    # /shorts/ 패턴
    if "shorts" in parsed.path:
        return parsed.path.split("/shorts/")[1].split("?")[0]
    # /watch/ 패턴
    elif "watch" in parsed.path:
        return parse_qs(parsed.query).get("v", [None])[0]
    elif parsed.netloc in ["youtu.be"]:
        return parsed.path.strip("/")
    else:
        raise ValueError("유효한 유튜브 URL이 아닙니다. (/shorts/, /watch/ 형식을 지원합니다)")


def extract_instagram_id(url: str) -> str:
    """
    인스타그램 URL로부터 shortcode(ID)를 추출합니다.
    /reel/, /reels/, /tv/, /p/ 네 가지 패턴을 모두 지원합니다.
    """
    # Load URL
    parsed = urlparse(url)

    prefix_list = ['/reel/', '/reels/', '/tv/', '/p/']
    for prefix in prefix_list:
        if prefix in parsed.path:
            short_code = parsed.path.split(prefix)[1].split("/")[0].split("?")[0]
            return short_code
    else:
        raise ValueError("유효한 인스타그램 URL이 아닙니다. (/reel/, /reels/, /p/ 형식을 지원합니다)")


# =============================================
# SNS 컨텐츠 다운로드
# =============================================
def get_instagram_content_ytdlp(state: ExtractionState) -> tuple[BytesIO | None, str]:
    """
    yt-dlp를 사용하여 Instagram 컨텐츠를 BytesIO로 다운로드
    - 릴스(/reel, /reels), IGTV(/tv): mp4 비디오 반환
    - 포스트(/p): 단일 이미지 또는 캐러셀의 특정 이미지를 BytesIO로 반환
      (여러 장이면 ?img_index=K를 존중; 없으면 첫 장)
    Returns: (stream: BytesIO | None, caption_txt: str)
    """
    url = state.get('snsUrl')

    def _media_type(u: str) -> str:
        path = urlparse(u).path.lower()
        if "/reel/" in path or "/reels/" in path:
            return "reel"
        if "/tv/" in path:
            return "tv"
        if "/p/" in path:
            return "post"
        return "other"

    def _get_img_index(u: str) -> int | None:
        q = parse_qs(urlparse(u).query)
        if "img_index" in q and q["img_index"]:
            try:
                return max(1, int(q["img_index"][0]))  # 1-based 가정
            except ValueError:
                return None
        return None

    def _bytes_from_url(u: str, timeout: int = 30) -> BytesIO | None:
        try:
            import requests
            r = requests.get(u, timeout=timeout)
            r.raise_for_status()
            b = BytesIO(r.content)
            b.seek(0)
            return b
        except Exception as e:
            logger.error(f"이미지/비디오 다운로드 실패: {e}")
            return None

    def _pick_image_from_info(info: dict, idx1: int | None) -> str | None:
        """
        info 또는 playlist entries에서 이미지 URL 선택
        - 캐러셀: entries[idx1-1] 우선
        - 단일: thumbnails 중 가장 큰 것 선택 (url 또는 'url' 필드)
        """
        # 캐러셀(playlist 형태)
        if info.get("_type") == "playlist" and "entries" in info and info["entries"]:
            entries = info["entries"]
            i = 0
            if idx1 is not None:
                i = max(0, min(len(entries) - 1, idx1 - 1))
            entry = entries[i] or {}
            # 1) entry에 직접 고화질 이미지 URL이 있으면
            if "url" in entry and entry.get("ext") in {"jpg", "jpeg", "png", "webp"}:
                return entry["url"]
            # 2) thumbnails 중 가장 큰 것
            thumbs = entry.get("thumbnails") or []
            if thumbs:
                # yt-dlp는 'width'/'height'가 큰 썸네일이 보통 원본에 가까움
                thumbs_sorted = sorted(
                    thumbs,
                    key=lambda t: (t.get("width", 0), t.get("height", 0), t.get("preference", 0)),
                    reverse=True,
                )
                if thumbs_sorted and "url" in thumbs_sorted[0]:
                    return thumbs_sorted[0]["url"]
            # 3) fallback: entry의 webpage_url (마지막 수단, 보통 불가)
            return None

        # 단일 포스트
        # 1) info.url이 이미지면 바로
        if "url" in info and info.get("ext") in {"jpg", "jpeg", "png", "webp"}:
            return info["url"]
        # 2) thumbnails 중 가장 큰 것
        thumbs = info.get("thumbnails") or []
        if thumbs:
            thumbs_sorted = sorted(
                thumbs,
                key=lambda t: (t.get("width", 0), t.get("height", 0), t.get("preference", 0)),
                reverse=True,
            )
            if thumbs_sorted and "url" in thumbs_sorted[0]:
                return thumbs_sorted[0]["url"]
        return None

    shortcode = extract_instagram_id(url)
    caption_txt = ""

    try:
        mt = _media_type(url)
        logger.info(f"[{shortcode}] 1/2 - yt-dlp 메타데이터 요청 중... (type={mt})")

        ydl_opts = {
            # 비디오는 mp4, 이미지는 info만 추출한 뒤 직접 다운로드
            "format": "best[ext=mp4]/best",
            "quiet": False,
            "no_warnings": False,
            "socket_timeout": 30,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            caption_txt = info.get("description", "") or info.get("title", "") or ""

            # ===== 1) 릴스/IGTV: 비디오 처리 =====
            if mt in {"reel", "tv"}:
                logger.info(f"[{shortcode}] 2/2 - 비디오 URL 선택 중...")
                video_url = None
                # 직접 url (best) 우선
                if "url" in info and info.get("ext") == "mp4":
                    video_url = info["url"]
                # formats 중 마지막(대개 최고 품질) 사용
                if not video_url and "formats" in info and info["formats"]:
                    # mp4 선호
                    mp4s = [f for f in info["formats"] if f.get("ext") == "mp4" and f.get("url")]
                    if mp4s:
                        video_url = mp4s[-1]["url"]
                    else:
                        video_url = info["formats"][-1].get("url")

                if not video_url:
                    logger.error(f"[{shortcode}] 비디오 URL을 찾을 수 없습니다.")
                    return None, caption_txt

                stream = _bytes_from_url(video_url)
                if not stream:
                    return None, caption_txt

                logger.info(f"[{shortcode}] 비디오 다운로드 완료 (메모리).")
                return stream, caption_txt

            # ===== 2) 포스트(/p): 이미지 처리 =====
            if mt == "post":
                idx1 = _get_img_index(url)  # 1-based
                logger.info(f"[{shortcode}] 2/2 - 이미지 URL 선택 중... (img_index={idx1})")

                img_url = _pick_image_from_info(info, idx1)
                if not img_url:
                    logger.error(f"[{shortcode}] 이미지 URL을 찾을 수 없습니다.")
                    return None, caption_txt

                stream = _bytes_from_url(img_url)
                if not stream:
                    return None, caption_txt

                logger.info(f"[{shortcode}] 이미지 다운로드 완료 (메모리).")
                return stream, caption_txt

            # ===== 3) 그 외: 미지원 =====
            logger.error(f"[{shortcode}] 미지원 Instagram URL 형식입니다.")
            return None, caption_txt

    except Exception as e:
        logger.error(f"yt-dlp 오류: {e}")
        return None, ""



def get_youtube_content(state: ExtractionState) -> tuple[BytesIO | None, str]:
    """
    주어진 Youtube Shorts URL로부터 동영상을 다운로드합니다.
    1. YouTube Data API v3를 사용하여 메타데이터(snippet) 가져오기
    2. yt-dlp로 비디오를 임시 파일에 다운로드 후 BytesIO로 로드

    url 예시
    https://youtube.com/shorts/KVIplqVteKE?si=Ld1KTdciGQSZeQJ0

    Args:
        url (str): 유튜브 URL (shorts / watch / youtu.be 형태)

    Returns:
        video_stream (BytesIO): 숏츠 영상 (메모리 내 mp4)
        caption_txt (str): 제목 + 설명 텍스트
    """
    url = state.get('snsUrl')
    logger.info(f"YouTube 숏츠 처리 시작: {url}")

    try:
        # video_id 추출
        video_id = extract_youtube_id(url)
        logger.info(f"[{video_id}] YouTube API 메타데이터 요청 중")

        metadata_url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet",
            "id": video_id,
            "key": settings.YOUTUBE_API_KEY
        }
        caption_txt = ""

        # Google API 요청
        r = requests.get(metadata_url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data.get("items"):
            logger.warning(f"[{video_id}] YouTube API에서 비디오 정보를 찾을 수 없습니다")
        else:
            snippet = data["items"][0]["snippet"]
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            caption_txt = f"{title}\n\n{description}".strip()
            logger.info(f"[{video_id}] 메타데이터 확보 완료")

        # yt-dlp 다운로드 (임시파일 사용)
        logger.info(f"[{video_id}] yt-dlp 다운로드 중")

        temp_path = tempfile.mktemp(suffix=".mp4")

        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": temp_path,
            "quiet": True,
            "noprogress": True,
            "no_warnings": True,
            "postprocessor_args": ["-loglevel", "panic"],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 파일 읽기 → 메모리 로드
        with open(temp_path, "rb") as f:
            video_bytes = f.read()

        try:
            os.remove(temp_path)
        except OSError:
            pass

        if not video_bytes:
            logger.error(f"yt-dlp가 [{video_id}] 영상을 다운로드하지 못했습니다 (0 bytes)")
            return None, caption_txt

        video_stream = BytesIO(video_bytes)
        logger.info(f"[{video_id}] 다운로드 완료 ({len(video_bytes)} bytes)")

        return video_stream, caption_txt

    except yt_dlp.utils.DownloadError as e:
        logger.exception("yt-dlp 다운로드 오류")
        return None, ""
    except requests.exceptions.RequestException as e:
        logger.exception("YouTube API 요청 오류")
        return None, ""
    except Exception as e:
        logger.exception("예기치 못한 오류 발생")
        return None, ""


# =============================================
# 메타데이터 추출 함수
# =============================================
def extract_youtube_metadata(state: ExtractionState) -> dict:
    """
    YouTube 콘텐츠의 메타데이터를 추출합니다.

    Args:
        state: ExtractionState 객체 (snsUrl 포함)

    Returns:
        dict: {
            "title": str,
            "thumbnailUrl": str,
            "videoId": str
        }
    """
    url = state.get('snsUrl')
    try:
        video_id = extract_youtube_id(url)

        # YouTube API로 제목 추출
        metadata_url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet",
            "id": video_id,
            "key": settings.YOUTUBE_API_KEY
        }

        r = requests.get(metadata_url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        title = ""
        channel_title = None
        channel_id = None
        if data.get("items"):
            snippet = data["items"][0]["snippet"]
            title = snippet.get("title", "")
            channel_title = snippet.get("channelTitle")
            channel_id = snippet.get("channelId")

        # 썸네일 및 콘텐츠 URL 생성
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        content_url = f"https://www.youtube.com/watch?v={video_id}"

        return {
            "title": title or f"YouTube Video - {video_id}",
            "thumbnailUrl": thumbnail_url,
            "videoId": video_id,
            "contentUrl": content_url,
            "platformUploader": channel_title,
            "platformUploaderId": channel_id,
        }
    except Exception as e:
        logger.exception(f"YouTube 메타데이터 추출 실패: {e}")
        # 기본값 반환
        video_id = extract_youtube_id(url) if url else "unknown"
        return {
            "title": f"YouTube Video - {video_id}",
            "thumbnailUrl": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            "videoId": video_id,
            "contentUrl": f"https://www.youtube.com/watch?v={video_id}" if video_id != "unknown" else None,
            "platformUploader": None,
            "platformUploaderId": None,
        }


def extract_instagram_metadata(state: ExtractionState) -> dict:
    """
    Instagram 콘텐츠의 메타데이터를 추출합니다.

    #FIXME: Instagram API에서 제목을 직접 제공하지 않아 임시로 생성합니다.
    향후 Instagram GraphQL API를 통해 제목을 추출할 수 있도록 개선 필요.

    Args:
        state: ExtractionState 객체 (snsUrl, extractedData 포함)

    Returns:
        dict: {
            "title": str,
            "thumbnailUrl": str | None,
            "shortcode": str,
            "contentUrl": str | None,
            "platformUploader": str | None
        }
    """
    url = state.get('snsUrl')
    extracted_data = state.get('extractedData', {})

    try:
        shortcode = extract_instagram_id(url)

        # extractedData 확인 로깅
        logger.info(f"[Metadata] extract_instagram_metadata 시작 - shortcode: {shortcode}")
        logger.info(f"[Metadata] extractedData 키 목록: {list(extracted_data.keys())}")
        logger.info(f"[Metadata] extractedData 값 확인:")
        logger.info(f"  - thumbnailUrl: {extracted_data.get('thumbnailUrl')}")
        logger.info(f"  - platformUploader: {extracted_data.get('platformUploader')}")
        logger.info(f"  - contentUrl: {extracted_data.get('contentUrl')}")
        logger.info(f"  - captionText: {len(extracted_data.get('captionText', ''))}자")

        # 제목 생성 (임시)
        #FIXME: Instagram 제목 생성 로직 - 현재는 캡션 첫 줄 또는 기본값 사용
        caption = extracted_data.get('captionText', '')
        if caption:
            # 캡션의 첫 줄을 제목으로 사용
            title = caption.split('\n')[0].strip()
            if not title:
                title = f"Instagram Post - {shortcode}"
        else:
            title = f"Instagram Post - {shortcode}"

        # 썸네일, 업로더, 콘텐츠 URL 구성
        thumbnail_url = extracted_data.get("thumbnailUrl")
        platform_uploader = extracted_data.get("platformUploader")
        content_url = extracted_data.get("contentUrl") or f"https://www.instagram.com/p/{shortcode}/"

        result = {
            "title": title,
            "thumbnailUrl": thumbnail_url,
            "shortcode": shortcode,
            "contentUrl": content_url,
            "platformUploader": platform_uploader,
        }

        # 메타데이터 추출 결과 로깅
        logger.info(f"[Metadata] extract_instagram_metadata 결과:")
        logger.info(f"  - title: {result['title']}")
        logger.info(f"  - thumbnailUrl: {result['thumbnailUrl']}")
        logger.info(f"  - contentUrl: {result['contentUrl']}")
        logger.info(f"  - platformUploader: {result['platformUploader']}")

        return result
    except Exception as e:
        logger.exception(f"Instagram 메타데이터 추출 실패: {e}")
        # 기본값 반환
        try:
            shortcode = extract_instagram_id(url) if url else "unknown"
        except:
            shortcode = "unknown"
        return {
            "title": f"Instagram Post - {shortcode}",
            "thumbnailUrl": extracted_data.get("thumbnailUrl"),
            "shortcode": shortcode,
            "contentUrl": extracted_data.get("contentUrl") or (f"https://www.instagram.com/p/{shortcode}/" if shortcode != "unknown" else None),
            "platformUploader": extracted_data.get("platformUploader"),
        }
