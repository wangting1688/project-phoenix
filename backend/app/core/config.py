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

    # AI 配置 (mock / ark)
    AI_PROVIDER: str = "mock"
    ARK_BASE_URL: Optional[str] = None
    ARK_API_KEY: Optional[str] = None
    ARK_MODEL: Optional[str] = None
    ARK_TIMEOUT: int = 30

    # 火山方舟豆包语音 TTS (Voice Cloning) — 独立新账号
    # 鉴权: 训练/合成都用 X-Api-Key header (新控制台)
    #       https://console.volcengine.com/speech/new/setting/apikeys
    # 训练: POST {BASE_URL}/api/v3/tts/voice_clone
    # 合成: POST {BASE_URL}/api/v3/tts
    VOLC_TTS_BASE_URL: str = "https://openspeech.bytedance.com"
    VOLC_TTS_API_KEY: Optional[str] = None
    VOLC_TTS_APP_ID: Optional[str] = None
    VOLC_TTS_CLUSTER: Optional[str] = None
    VOLC_TTS_ACCESS_TOKEN: Optional[str] = None  # 兼容旧版 Bearer (可选)
    VOLC_TTS_IAM_AK: Optional[str] = None       # 兼容 HMAC (可选)
    VOLC_TTS_IAM_SK: Optional[str] = None       # 兼容 HMAC (可选)
    VOLC_TTS_TIMEOUT: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
