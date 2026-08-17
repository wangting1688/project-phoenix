from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "Project Phoenix - AI短视频操作系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # CORS 允许的来源，逗号分隔，* 表示允许所有（仅开发环境用）
    CORS_ORIGINS: str = "*"

    # 增长系列 API + agent 网关路由开关（封闭内测默认关闭，缩小事故面）
    ENABLE_GROWTH_APIS: bool = False

    DATABASE_URL: str = "sqlite:///./phoenix.db"

    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "phoenix-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    STORAGE_PATH: str = "./storage"

    # 口型同步远程 HTTP 服务地址（方案A：本机 GPU worker 经反向 SSH 隧道暴露到 live:18080）
    # 形如 http://127.0.0.1:18080 则 lipsync_service 通过 HTTP 派发到本机 GPU 跑 Wav2Lip
    LIPSYNC_REMOTE_HTTP: str = ""

    # ===== 演示素材开关 =====
    # 新用户注册时是否自动注入系统演示素材
    DEMO_FOOTAGE_ENABLED: bool = True
    # 演示素材源目录（相对于 STORAGE_PATH）
    DEMO_FOOTAGE_SOURCE_DIR: str = "demo_footage"
    # 每个用户注入的演示素材最大数量
    DEMO_FOOTAGE_MAX_COUNT: int = 6
    # 演示素材是否允许用户编辑标签（scene/emotion/topics）
    DEMO_FOOTAGE_ALLOW_EDIT_TAGS: bool = False

    # AI 配置 (mock / ark)
    AI_PROVIDER: str = "mock"
    ARK_BASE_URL: Optional[str] = None
    ARK_API_KEY: Optional[str] = None
    ARK_MODEL: Optional[str] = None
    ARK_TIMEOUT: int = 120

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
