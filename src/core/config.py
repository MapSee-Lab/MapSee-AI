"""src.core.config.py
.env 파일에서 API키를 할당합니다.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GOOGLE_API_KEY: str
    AI_SERVER_API_KEY: str
    INSTAGRAM_POST_DOC_ID: str
    INSTAGRAM_APP_ID: str
    YOUTUBE_API_KEY: str
    BACKEND_CALLBACK_URL: str
    BACKEND_API_KEY: str
    ENVIRONMENT: str = "dev"  # dev: 로컬, prod: 서버환경

    # SMB 설정
    SMB_HOST: str = ""
    SMB_PORT: int = 445
    SMB_USERNAME: str = ""
    SMB_PASSWORD: str = ""
    SMB_SHARE_NAME: str = ""  # 공유 폴더명 (예: "web")
    SMB_REMOTE_DIR: str = ""  # 원격 디렉토리 경로 (예: "romrom/images")
    SMB_DOMAIN: str = ""  # 도메인 (선택적)

    model_config = SettingsConfigDict(env_file=".env")
settings = Settings()
