from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "Project Phoenix - AI短视频操作系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite:///./phoenix.db"

    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "phoenix-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    STORAGE_PATH: str = "./storage"

    class Config:
        env_file = ".env"


settings = Settings()
