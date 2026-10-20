from pathlib import Path
from typing import List, Optional
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "IncuBrix Audio Engine"
    VERSION: str = "0.2.0"
    API_V1_PREFIX: str = "/api/v1"
    APP_ENV: str = "development"

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Storage settings
    # Options: "local" (default filesystem), "s3" (AWS S3 or MinIO S3-compatible storage)
    STORAGE_BACKEND: str = "local"
    STORAGE_DIR: Path = Path("storage")
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET_NAME: str = "incubrix-audio"
    S3_ACCESS_KEY_ID: Optional[SecretStr] = None
    S3_SECRET_ACCESS_KEY: Optional[SecretStr] = None
    S3_REGION: str = "us-east-1"
    S3_SECURE: bool = False

    # Audio synthesis and provider settings
    # Options: "mock" (Phase 1 deterministic generator), "soundverse" (Phase 2 real AI provider)
    PROVIDER_TYPE: str = "mock"
    DEFAULT_SAMPLE_RATE: int = 44100
    DEFAULT_TARGET_LUFS: float = -14.0
    DEFAULT_TEMPO_BPM: int = 120
    DEFAULT_KEY: str = "C major"

    # Supported formats and sample rates
    SUPPORTED_FORMATS: List[str] = ["wav"]
    SUPPORTED_SAMPLE_RATES: List[int] = [22050, 44100, 48000]

    # Duration limits (in seconds)
    MIN_DURATION_S: float = 5.0
    MAX_DURATION_S: float = 300.0

    # Soundverse Enterprise API settings
    SOUNDVERSE_API_KEY: Optional[SecretStr] = None
    SOUNDVERSE_BASE_URL: str = "https://apiv2.soundverse.ai"
    SOUNDVERSE_MODEL_VERSION: str = "v7"
    SOUNDVERSE_STEM_VARIANT: str = "six-stem"
    SOUNDVERSE_LICENSE_TIER: int = 1
    SOUNDVERSE_POLL_INTERVAL_S: float = 2.0
    SOUNDVERSE_POLL_TIMEOUT_S: float = 180.0
    SOUNDVERSE_MAX_RETRIES: int = 3
    SOUNDVERSE_RETRY_BACKOFF_S: float = 1.0
    SOUNDVERSE_USE_COMPAT_ROUTE: bool = True


settings = Settings()
