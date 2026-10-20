from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "IncuBrix Audio Engine"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    APP_ENV: str = "development"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Local storage for artifacts (audio stems, mix, manifest)
    STORAGE_DIR: Path = Path("storage")

    # Audio synthesis and provider settings
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


settings = Settings()
