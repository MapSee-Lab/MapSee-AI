import yt_dlp
import requests
import os
from pathlib import Path
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

def extract_caption(url: str):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    logger.info(f"캡션 추출 시작: {url}")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        # 본문 텍스트 추출
        description = info.get('description', '')

        return description

# 사용 예시
# url = "https://www.instagram.com/p/DO-u-YwD6Rt/?img_index=8"
# result = extract_instagram_caption(url)
# print(f"본문: {result}")


def download_instagram_complete(url, output_path='./downloads'):
    """yt-dlp로 메타데이터 추출 후 사진/동영상 모두 다운로드"""

    os.makedirs(output_path, exist_ok=True)

    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
    }

    results = {
        'metadata': {},
        'downloaded_files': []
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)

            # 메타데이터 저장
            results['metadata'] = {
                'description': info.get('description', ''),
                'uploader': info.get('uploader', ''),
                'uploader_id': info.get('uploader_id', ''),
                'like_count': info.get('like_count', 0),
                'comment_count': info.get('comment_count', 0),
            }

            # 캐러셀(여러 미디어)인 경우
            if 'entries' in info:
                for idx, entry in enumerate(info.get('entries', []), 1):
                    if not entry:
                        continue

                    # 비디오인 경우 yt-dlp로 다운로드
                    if entry.get('url') and not entry.get('url', '').endswith(('.jpg', '.png', '.jpeg')):
                        ydl_opts_download = {
                            'outtmpl': f'{output_path}/%(uploader)s_%(id)s_{idx}.%(ext)s',
                            'format': 'best',
                        }
                        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl_down:
                            ydl_down.download([entry.get('url')])
                            results['downloaded_files'].append(f"video_{idx}")

                    # 사진인 경우 직접 다운로드
                    thumbnail_url = entry.get('thumbnail') or entry.get('url')
                    if thumbnail_url:
                        filename = f"{results['metadata']['uploader_id']}_{info.get('id', 'unknown')}_{idx}.jpg"
                        filepath = Path(output_path) / filename

                        if download_image(thumbnail_url, filepath):
                            results['downloaded_files'].append(filename)
                            logger.info(f"[{idx}] 사진 다운로드 성공: {filename}")

            # 단일 미디어인 경우
            else:
                # 비디오 다운로드
                if info.get('url'):
                    ydl_opts_download = {
                        'outtmpl': f'{output_path}/%(uploader)s_%(id)s.%(ext)s',
                        'format': 'best',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts_download) as ydl_down:
                        ydl_down.download([url])
                        results['downloaded_files'].append("video")

                # 썸네일/사진 다운로드
                thumbnail_url = info.get('thumbnail')
                if thumbnail_url:
                    filename = f"{results['metadata']['uploader_id']}_{info.get('id', 'unknown')}.jpg"
                    filepath = Path(output_path) / filename

                    if download_image(thumbnail_url, filepath):
                        results['downloaded_files'].append(filename)
                        logger.info(f"단일 사진 다운로드 성공: {filename}")

        except Exception as e:
            logger.info(f"인스타그램 미디어 처리 중 에러 발생: {e}")

    return results

def download_image(url, filepath):
    """URL에서 이미지를 다운로드"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        logger.info(f"이미지 다운로드 실패 ({url}): {e}")
        return False

# 사용 예시
# url = "https://www.instagram.com/p/DO-u-YwD6Rt/?img_index=8"
# results = download_instagram_complete(url)
# print(f"\n본문: {results['metadata'].get('description', 'N/A')}")
# print(f"다운로드된 파일: {len(results['downloaded_files'])}개")
