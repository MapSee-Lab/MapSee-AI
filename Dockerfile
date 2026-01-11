# ===================================================================
# Python FastAPI Dockerfile
# ===================================================================
#
# 설명:
# - FastAPI 애플리케이션을 위한 멀티 스테이지 Dockerfile
# - faster-whisper를 위한 ffmpeg 설치 포함
# - Playwright 브라우저 (Chromium) 설치 포함
# - uv를 사용한 빠른 의존성 설치
#
# 빌드 구조:
# - Python 3.13 기반
# - ffmpeg 및 시스템 의존성 설치
# - Playwright Chromium 브라우저 설치
# - uv를 통한 패키지 관리
#
# ===================================================================

FROM python:3.13-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
# - ffmpeg: faster-whisper의 오디오 처리를 위해 필요
# - curl: 헬스체크 및 다운로드용
# - Playwright Chromium 실행에 필요한 시스템 라이브러리
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    # Playwright Chromium 의존성
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# uv 설치 (빠른 Python 패키지 매니저)
RUN pip install --no-cache-dir uv

# 프로젝트 파일 복사
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY .env ./

# 의존성 설치
# uv를 사용하여 빠르게 설치
RUN uv pip install --system --no-cache .

# Playwright 브라우저 설치 (Chromium만 설치하여 이미지 크기 최소화)
RUN playwright install chromium

# 타임존 설정 (Asia/Seoul)
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 포트 노출 (FastAPI 기본 포트)
EXPOSE 8000

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENVIRONMENT=prod

# 애플리케이션 실행
# uvicorn을 사용하여 FastAPI 서버 실행
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ===================================================================
# 사용 방법
# ===================================================================
#
# 1. .env 파일 생성:
#    echo "GOOGLE_API_KEY=your_api_key" > .env
#
# 2. Docker 이미지 빌드:
#    docker build -t mapsee-ai:latest .
#
# 3. Docker 컨테이너 실행:
#    docker run -d -p 8000:8000 mapsee-ai:latest
#
# 4. 헬스체크:
#    curl http://localhost:8000/docs
#
# ===================================================================
