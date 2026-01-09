"""src.services.content_router.py
SNS URL을 기반으로 플랫폼 및 콘텐츠 유형(이미지/비디오)을 감지하고,
해당 컨텐츠를 다운로드하는 적절한 다운로드 모듈 호출하여
ExtractionState에 필요한 스트링 데이터를 채워주는 라우터 입니다.

NOTE: Instagram 이미지 다운로드 기능은 제거되었습니다. (ScrapFly 제거)
"""
import logging
from urllib.parse import urlparse

from src.services.preprocess.sns import(
    get_youtube_content,
    get_instagram_content_ytdlp
)

from src.models import ExtractionState
from src.core.exceptions import CustomError

logger = logging.getLogger(__name__)


# =============================================
# Content Type 별 라우팅 함수
# =============================================
def type_router(state: ExtractionState) -> None:
    """
    Instagram의 Video, Image에 따른 분기하여 state를 직접 업데이트합니다.

    Args:
        state: ExtractionState 객체 (직접 수정됨)

    Returns:
        None
    """
    sns_platform = state.get('snsPlatform')
    content_type = state.get('contentType')

    stream = None
    caption = ""

    try:
        if sns_platform == 'youtube':
            stream, caption = get_youtube_content(state)
            # State 업데이트
            state['extractedData'].update({
                'contentStream': stream,
                'captionText': caption
            })

        elif sns_platform == 'instagram':
            if content_type == 'image':
                # NOTE: Instagram 이미지 다운로드 기능 제거됨 (ScrapFly 제거)
                # yt-dlp로 시도
                try:
                    ytdlp_stream, caption = get_instagram_content_ytdlp(state)
                    # 워크플로우는 리스트를 기대하므로 yt-dlp 반환값 리스트로 수정 (원래 BytesIO를 반환)
                    if ytdlp_stream:
                        stream = [ytdlp_stream]
                    else:
                        stream = None
                except Exception as e:
                    logger.error(f"yt-dlp 이미지 다운로드 실패: {e}")
                    raise CustomError(f"이미지 다운로드 실패: {str(e)}")

                # State 업데이트
                state['extractedData'].update({
                    'imageStream': stream,
                    'captionText': caption
                })

            elif content_type == 'video':
                # yt-dlp
                stream, caption = get_instagram_content_ytdlp(state)
                # State 업데이트
                state['extractedData'].update({
                    'contentStream': stream,
                    'captionText': caption
                })
            else:
                raise CustomError(f"지원하지 않는 타입입니다: {content_type}")

        else:
            raise CustomError(f"지원하지 않는 플랫폼입니다: {sns_platform}")
    except CustomError:
        raise  # CustomError는 그대로 전달
    except Exception as e:
        logger.exception(f"콘텐츠 추출 중 오류 발생: {e}")
        raise CustomError(f"콘텐츠 추출 실패: {str(e)}")


# =============================================
# SNS 플랫폼 별 라우팅 함수
# =============================================
def sns_router(state: ExtractionState):
    """
    URL을 분석하여 YouTube 또는 Instagram 비디오 ID를 추출합니다.

    Args:
        url: YouTube 또는 Instagram URL

    Raises:
        ValueError: 지원하지 않는 플랫폼이거나 유효하지 않은 URL인 경우
    """
    # Load URL
    url = state.get('snsUrl')
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # YouTube 체크
    if 'youtube.com' in domain or 'youtu.be' in domain:
        logger.info("YouTube 플랫폼 감지")
        state.update({'snsPlatform': 'youtube'})
        state.update({'contentType': 'video'})

    # Instagram 체크
    elif 'instagram.com' in domain:
        logger.info("Instagram 플랫폼 감지")
        state.update({'snsPlatform': 'instagram'})

        path = parsed.path.lower()

        # /p/ (이미지 게시물)일 때
        if "/p/" in path:
            state.update({'contentType': 'image'})
        # /reel/, /reels/, /tv/ (영상 게시물)
        elif "/reel/" in path or "/reels/" in path or "/tv/" in path:
            state.update({'contentType': 'video'})

    # 그 외
    else:
        raise CustomError(f"지원하지 않는 플랫폼입니다: {domain}")

    type_router(state)
