"""src.main
FastAPI 애플리케이션 진입점
"""
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from src.core.logging import setup_logging
from src.apis.place_router import router as place_router
from src.apis.demo_router import router as demo_router
from src.apis.robust_router import router as robust_router

# 로깅 초기화
setup_logging(log_level="INFO")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 수명주기 관리

    앱 시작 시: 필요한 초기화 수행
    앱 종료 시: 리소스 정리 (필요 시)
    """
    # ========== 시작 단계 ==========
    logger.info("=== 애플리케이션 시작: 초기화 중 ===")

    logger.info("=== 애플리케이션 준비 완료 ===")

    yield  # 애플리케이션 실행

    # ========== 종료 단계 ==========
    logger.info("=== 애플리케이션 종료 중 ===")


# FastAPI 앱 생성 (lifespan 컨텍스트 적용)
app = FastAPI(
    title="MapSee AI Processor",
    description="MapSee의 SNS 콘텐츠 데이터 추출 파이프라인입니다.",
    version="0.0.2",
    lifespan=lifespan
)


# 라우터 등록
app.include_router(place_router)
app.include_router(demo_router)
app.include_router(robust_router)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """요청 처리 시간 측정 미들웨어"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # 응답 헤더에 처리 시간 추가
    response.headers["X-Process-Time"] = f"{process_time:.4f}"

    # 로깅
    logger.info(
        f"요청 처리 완료: {request.method} {request.url.path} - {process_time:.4f}초"
    )

    return response


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
