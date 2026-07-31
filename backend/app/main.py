from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import api_router
from app.services.scheduler_service import get_growth_scheduler

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI短视频操作系统 - Project Phoenix",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def startup_event():
    """应用启动时初始化"""
    # 启动增长定时调度器
    scheduler = get_growth_scheduler()
    scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    """应用关闭时清理"""
    scheduler = get_growth_scheduler()
    scheduler.stop()


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
