# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소의 코드를 다룰 때 참고하는 가이드입니다.

## 프로젝트 개요

MapSee-AI는 Python 기반의 SNS 콘텐츠 데이터 추출 파이프라인입니다. Instagram과 YouTube 콘텐츠를 처리하여 장소/위치 정보를 추출합니다. FastAPI 서비스로 URL을 받아 미디어 콘텐츠를 다운로드하고, 음성-텍스트 변환(STT)을 수행한 뒤, LLM(Gemini)을 사용하여 구조화된 장소 데이터를 추출합니다.

## 개발 명령어

```bash
# 의존성 설치 (Python 3.13+)
uv sync

# 개발 서버 실행
uv run uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

# 대안: 직접 실행
uv run python -m src.main
```

### 외부 의존성
- **ffmpeg/ffprobe**: 오디오/비디오 처리에 필요
- **yt-dlp**: Instagram/YouTube 콘텐츠 다운로드에 사용

## 네이밍 규칙

### 파일명
- 파일명만 보고 역할을 알 수 있어야 함
- 예: `base.py` ❌ → `playwright_browser.py` ✅
- 예: `router.py` ❌ → `scrape_router.py` ✅

### 변수/함수명
- 길어도 명확한 이름 선호
- 축약어 사용 최소화
- 예: `desc` ❌ → `description` ✅
- 예: `res` ❌ → `response` ✅
- 예: `cnt` ❌ → `count` ✅

## API 응답 규칙

- `success` 필드 사용 금지 - HTTP 상태 코드로 성공/실패 판단
- 200 OK → 성공
- 4xx/5xx → 실패 (에러 메시지는 `detail` 필드에)

## 아키텍처

### 요청 흐름
1. `/api/extract-places`가 `contentId` + `snsUrl`을 받음
2. 요청은 즉시 반환 (비동기 처리)
3. 백그라운드 태스크가 추출 파이프라인 실행
4. 결과는 콜백 URL을 통해 백엔드로 전송

### 파이프라인 단계 (workflow.py)
```
URL → sns_router → get_audio → get_transcription (STT) → get_video_narration → get_llm_response → callback
       ↓
  플랫폼 감지 (YouTube/Instagram)
  콘텐츠 타입 감지 (비디오/이미지)
  yt-dlp로 미디어 다운로드
```

### 주요 컴포넌트

**src/apis/**: FastAPI 라우터
- `place_router.py`: 장소 추출 API 메인 엔드포인트

**src/services/**: 비즈니스 로직
- `workflow.py`: 메인 추출 파이프라인 오케스트레이션
- `content_router.py`: 플랫폼/콘텐츠 타입에 따라 적절한 다운로더로 라우팅
- `background_tasks.py`: 비동기 태스크 실행 및 콜백 처리
- `smb_service.py`: SMB 파일 서버 연동

**src/services/modules/**: 처리 모듈
- `llm.py`: 장소 추출을 위한 Gemini API 연동
- `stt.py`: Faster-Whisper 음성-텍스트 변환

**src/services/preprocess/**: 미디어 전처리
- `sns.py`: Instagram/YouTube 콘텐츠 다운로드 (yt-dlp)
- `audio.py`: FFmpeg 오디오 추출
- `video.py`: 비디오 프레임 추출 (OCR 현재 비활성화)

**src/models/**: Pydantic 스키마
- `ExtractionState`: 파이프라인을 통해 전달되며 각 단계에서 데이터가 축적되는 TypedDict

**src/core/**: 설정 및 유틸리티
- `config.py`: .env에서 설정 로드 (API 키, SMB 설정 등)
- `exceptions.py`: 파이프라인 오류를 위한 CustomError 클래스

### 상태 흐름 패턴
파이프라인은 `ExtractionState` (TypedDict)를 가변 상태 객체로 사용하여 각 처리 단계를 거칩니다. 각 단계에서 특정 필드가 업데이트됩니다:
- `contentStream`/`imageStream`: 다운로드된 미디어
- `captionText`: 게시글 캡션/설명
- `audioStream`: 추출된 오디오
- `transcriptionText`: STT 출력
- `ocrText`: 비디오 텍스트 (현재 비활성화)
- `result`: 최종 추출된 장소들

## 설정

`.env`에 필요한 환경 변수:
- `GOOGLE_API_KEY`: Gemini API 키
- `AI_SERVER_API_KEY`: 이 서비스의 API 키
- `YOUTUBE_API_KEY`: YouTube Data API 키
- `INSTAGRAM_POST_DOC_ID`, `INSTAGRAM_APP_ID`: Instagram API 설정
- `BACKEND_CALLBACK_URL`, `BACKEND_API_KEY`: 콜백 엔드포인트 설정
- `SMB_*`: SMB 파일 서버 설정 (선택사항)

## 참고사항

- OCR 기능은 현재 비활성화 상태 (코드 전반에 주석으로 표시됨)
- 서비스는 미디어 처리에 인메모리 BytesIO 스트림 사용
- Faster-Whisper는 기본적으로 CPU에서 int8 양자화로 실행
- LLM 응답은 `response_json_schema`를 사용하여 Pydantic 스키마로 검증
