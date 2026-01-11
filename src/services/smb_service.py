"""src.services.smb_service.py
SMB 파일 서버 업로드/삭제 서비스
"""
import logging
import uuid
from pathlib import Path

import smbclient
from smbclient import shutil as smb_shutil

from src.core.config import settings

logger = logging.getLogger(__name__)


class SmbService:
    """SMB 파일 서버 연결 및 파일 관리 서비스"""

    def __init__(self):
        self._registered = False

    def _ensure_registered(self):
        """SMB 클라이언트 인증 등록 (최초 1회)"""
        if self._registered:
            return

        if not settings.SMB_HOST or not settings.SMB_USERNAME:
            raise ValueError("SMB 설정이 누락되었습니다. .env 파일을 확인하세요.")

        smbclient.register_session(
            server=settings.SMB_HOST,
            username=settings.SMB_USERNAME,
            password=settings.SMB_PASSWORD,
            port=settings.SMB_PORT,
        )
        self._registered = True
        logger.info(f"SMB 세션 등록 완료: {settings.SMB_HOST}:{settings.SMB_PORT}")

    def _get_remote_path(self, filename: str) -> str:
        """원격 파일 경로 생성"""
        share = settings.SMB_SHARE_NAME
        remote_dir = settings.SMB_REMOTE_DIR
        return f"\\\\{settings.SMB_HOST}\\{share}\\{remote_dir}\\{filename}"

    def generate_filename(self, original_filename: str) -> str:
        """고유 파일명 생성 (UUID + 확장자)"""
        ext = Path(original_filename).suffix.lower()
        return f"{uuid.uuid4().hex}{ext}"

    def upload_file(self, local_path: str, remote_filename: str | None = None) -> str:
        """
        로컬 파일을 SMB 서버에 업로드

        Args:
            local_path: 업로드할 로컬 파일 경로
            remote_filename: 원격 파일명 (None이면 자동 생성)

        Returns:
            업로드된 원격 파일 경로
        """
        self._ensure_registered()

        local_file = Path(local_path)
        if not local_file.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {local_path}")

        if remote_filename is None:
            remote_filename = self.generate_filename(local_file.name)

        remote_path = self._get_remote_path(remote_filename)

        try:
            smb_shutil.copy(str(local_file), remote_path)
            logger.info(f"SMB 업로드 성공: {remote_filename}")
            return f"{settings.SMB_REMOTE_DIR}/{remote_filename}"
        except Exception as e:
            logger.error(f"SMB 업로드 실패: {remote_filename}, 오류: {e}")
            raise

    def upload_bytes(self, data: bytes, remote_filename: str) -> str:
        """
        바이트 데이터를 SMB 서버에 업로드

        Args:
            data: 업로드할 바이트 데이터
            remote_filename: 원격 파일명

        Returns:
            업로드된 원격 파일 경로
        """
        self._ensure_registered()

        remote_path = self._get_remote_path(remote_filename)

        try:
            with smbclient.open_file(remote_path, mode="wb") as f:
                f.write(data)
            logger.info(f"SMB 바이트 업로드 성공: {remote_filename}")
            return f"{settings.SMB_REMOTE_DIR}/{remote_filename}"
        except Exception as e:
            logger.error(f"SMB 바이트 업로드 실패: {remote_filename}, 오류: {e}")
            raise

    def delete_file(self, remote_filename: str) -> bool:
        """
        SMB 서버에서 파일 삭제

        Args:
            remote_filename: 삭제할 원격 파일명

        Returns:
            삭제 성공 여부
        """
        self._ensure_registered()

        remote_path = self._get_remote_path(remote_filename)

        try:
            smbclient.remove(remote_path)
            logger.info(f"SMB 파일 삭제 성공: {remote_filename}")
            return True
        except FileNotFoundError:
            logger.warning(f"SMB 파일이 존재하지 않음: {remote_filename}")
            return False
        except Exception as e:
            logger.error(f"SMB 파일 삭제 실패: {remote_filename}, 오류: {e}")
            return False

    def file_exists(self, remote_filename: str) -> bool:
        """
        SMB 서버에 파일 존재 여부 확인

        Args:
            remote_filename: 확인할 원격 파일명

        Returns:
            파일 존재 여부
        """
        self._ensure_registered()

        remote_path = self._get_remote_path(remote_filename)

        try:
            smbclient.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"SMB 파일 존재 확인 실패: {remote_filename}, 오류: {e}")
            return False

    def list_files(self, pattern: str = "*") -> list[str]:
        """
        SMB 서버 디렉토리 파일 목록 조회

        Args:
            pattern: 파일 패턴 (기본값: *)

        Returns:
            파일명 목록
        """
        self._ensure_registered()

        remote_dir = f"\\\\{settings.SMB_HOST}\\{settings.SMB_SHARE_NAME}\\{settings.SMB_REMOTE_DIR}"

        try:
            entries = smbclient.listdir(remote_dir)
            return [e for e in entries if e not in (".", "..")]
        except Exception as e:
            logger.error(f"SMB 디렉토리 조회 실패: {e}")
            return []


# 싱글톤 인스턴스
smb_service = SmbService()
