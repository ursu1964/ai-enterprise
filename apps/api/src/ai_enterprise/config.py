from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Enterprise"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+asyncpg://"
        "ai_enterprise:ai_enterprise_dev@localhost:5432/ai_enterprise"
    )

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "ollama/gemma4:12b"

    artifact_root: Path = Field(default=Path("./artifacts"))

    worker_poll_interval_seconds: float = 2.0
    worker_lease_seconds: int = 900
    worker_retry_delay_seconds: int = 30
    worker_heartbeat_seconds: int = 60

    repository_allowed_root: Path = Field(
        default=Path("/home/user/projects")
    )

    execution_image: str = "ai-enterprise-execution-agent:local"
    execution_snapshots_root: Path = Field(
        default=Path("./runtime-data/snapshots")
    )
    execution_artifacts_root: Path = Field(
        default=Path("./runtime-data/artifacts")
    )
    execution_temp_root: Path = Field(
        default=Path("./runtime-data/tmp")
    )
    execution_maximum_patch_bytes: int = 1_048_576
    execution_default_test_timeout_seconds: int = 300
    execution_implementation_timeout_seconds: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
