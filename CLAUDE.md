# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MapSee-AI is a Python-based SNS content data extraction pipeline that processes Instagram and YouTube content to extract place/location information. It's a FastAPI service that receives URLs, downloads media content, performs speech-to-text (STT), and uses LLM (Gemini) to extract structured place data.

## Development Commands

```bash
# Install dependencies (Python 3.13+)
uv sync

# Run the development server
uv run uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

# Alternative: run directly
uv run python -m src.main
```

### External Dependencies
- **ffmpeg/ffprobe**: Required for audio/video processing
- **yt-dlp**: Used for downloading Instagram/YouTube content

## Architecture

### Request Flow
1. `/api/extract-places` receives `contentId` + `snsUrl`
2. Request returns immediately (async processing)
3. Background task runs the extraction pipeline
4. Results sent to backend via callback URL

### Pipeline Stages (workflow.py)
```
URL → sns_router → get_audio → get_transcription (STT) → get_video_narration → get_llm_response → callback
       ↓
  Platform detection (YouTube/Instagram)
  Content type detection (video/image)
  Download media via yt-dlp
```

### Key Components

**src/apis/**: FastAPI routers
- `place_router.py`: Main API endpoint for place extraction

**src/services/**: Business logic
- `workflow.py`: Main extraction pipeline orchestration
- `content_router.py`: Routes to appropriate downloader based on platform/content type
- `background_tasks.py`: Async task execution and callback handling
- `smb_service.py`: SMB file server integration

**src/services/modules/**: Processing modules
- `llm.py`: Gemini API integration for place extraction
- `stt.py`: Faster-Whisper speech-to-text

**src/services/preprocess/**: Media preprocessing
- `sns.py`: Instagram/YouTube content download (yt-dlp)
- `audio.py`: FFmpeg audio extraction
- `video.py`: Video frame extraction (OCR currently disabled)

**src/models/**: Pydantic schemas
- `ExtractionState`: TypedDict that flows through the pipeline, accumulating data at each stage

**src/core/**: Configuration and utilities
- `config.py`: Settings from .env (API keys, SMB config, etc.)
- `exceptions.py`: CustomError class for pipeline errors

### State Flow Pattern
The pipeline uses `ExtractionState` (TypedDict) as a mutable state object that gets passed through each processing stage. Each stage updates specific fields:
- `contentStream`/`imageStream`: Downloaded media
- `captionText`: Post caption/description
- `audioStream`: Extracted audio
- `transcriptionText`: STT output
- `ocrText`: Video text (currently disabled)
- `result`: Final extracted places

## Configuration

Required environment variables in `.env`:
- `GOOGLE_API_KEY`: Gemini API key
- `AI_SERVER_API_KEY`: API key for this service
- `YOUTUBE_API_KEY`: YouTube Data API key
- `INSTAGRAM_POST_DOC_ID`, `INSTAGRAM_APP_ID`: Instagram API config
- `BACKEND_CALLBACK_URL`, `BACKEND_API_KEY`: Callback endpoint config
- `SMB_*`: SMB file server settings (optional)

## Notes

- OCR functionality is currently disabled (noted with comments throughout)
- The service uses in-memory BytesIO streams for media processing
- Faster-Whisper runs on CPU with int8 quantization by default
- LLM responses are validated against Pydantic schemas using `response_json_schema`
