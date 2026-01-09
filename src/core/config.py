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
    model_config = SettingsConfigDict(env_file=".env")
settings = Settings()
