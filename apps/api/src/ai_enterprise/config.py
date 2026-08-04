from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Enterprise"
    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    trusted_proxy_hmac_secret: str | None = None
    trusted_proxy_max_clock_skew_seconds: int = 60

    database_url: str = (
        "postgresql+asyncpg://ai_enterprise:ai_enterprise_dev@localhost:5432/ai_enterprise"
    )

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "ollama/gemma3:12b"
    model_provider_default: str = "ollama"
    requirements_crew_adapter: str = "deterministic"
    requirements_llm_provider: str = "ollama"
    requirements_llm_model: str = "ollama/gemma3:12b"
    requirements_llm_base_url: str = "http://localhost:11434"
    requirements_llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    requirements_llm_timeout_seconds: int = Field(default=600, ge=10, le=3600)
    requirements_llm_max_tokens: int = Field(default=8192, ge=512, le=65536)
    architecture_provider: str = "crewai-ollama"
    architecture_model_name: str = "ollama/gemma3:12b"
    architecture_model_base_url: str = "http://localhost:11434"
    architecture_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    architecture_timeout_seconds: int = Field(default=900, ge=1, le=3600)
    architecture_max_tokens: int = Field(default=16384, ge=512, le=65536)
    architecture_max_raw_output_bytes: int = Field(default=2_000_000, ge=1024)
    architecture_max_repair_attempts: int = Field(default=1, ge=0, le=1)
    decomposition_model_name: str = "ollama/gemma3:12b"
    decomposition_model_base_url: str = "http://localhost:11434"
    decomposition_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    decomposition_timeout_seconds: int = Field(default=900, ge=1, le=3600)
    decomposition_max_tokens: int = Field(default=16384, ge=512, le=65536)
    decomposition_snapshots_root: Path = Field(
        default=Path("./runtime-data/decomposition-snapshots")
    )
    requirements_output_repair_enabled: bool = True

    artifact_root: Path = Field(default=Path("./artifacts"))

    worker_poll_interval_seconds: float = 2.0
    worker_readiness_interval_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    worker_lease_seconds: int = Field(default=900, ge=3)
    worker_retry_delay_seconds: int = 30
    worker_heartbeat_seconds: int = Field(default=60, ge=1)
    worker_execution_timeout_seconds: int = 1800
    worker_recovery_interval_seconds: int = Field(default=60, ge=1)
    worker_stale_after_seconds: int = Field(default=180, ge=1)
    worker_retry_base_seconds: int = 30
    worker_retry_maximum_seconds: int = 900
    worker_profile: str = "general"

    repository_allowed_root: Path = Field(default=Path("/home/user/projects"))

    execution_image: str = "ai-enterprise-execution-agent:local"
    execution_snapshots_root: Path = Field(default=Path("./runtime-data/snapshots"))
    execution_artifacts_root: Path = Field(default=Path("./runtime-data/artifacts"))
    execution_temp_root: Path = Field(default=Path("./runtime-data/tmp"))
    execution_maximum_patch_bytes: int = 1_048_576
    execution_default_test_timeout_seconds: int = 300
    execution_implementation_timeout_seconds: int = 600

    review_image: str = "ai-enterprise-review-agent:local"
    review_snapshots_root: Path = Field(default=Path("./runtime-data/review-snapshots"))
    review_artifacts_root: Path = Field(default=Path("./runtime-data/review-artifacts"))
    review_temp_root: Path = Field(default=Path("./runtime-data/review-tmp"))
    review_maximum_patch_bytes: int = 1_048_576
    review_default_check_timeout_seconds: int = 300

    integration_work_root: Path = Field(default=Path("./runtime-data/integration-work"))
    integration_artifacts_root: Path = Field(default=Path("./runtime-data/integration-artifacts"))
    integration_git_identity_name: str = "Enterprise Integration Bot"
    integration_git_identity_email: str = "integration-bot@internal.invalid"
    integration_ssh_config_path: Path = Field(default=Path("/run/secrets/integration_ssh_config"))
    recovery_work_root: Path = Field(default=Path("./runtime-data/recovery-work"))
    recovery_artifacts_root: Path = Field(default=Path("./runtime-data/recovery-artifacts"))
    recovery_ssh_config_path: Path = Field(default=Path("/run/secrets/integration_ssh_config"))

    resilience_provider_profile: str = "unconfigured"
    resilience_local_root: Path = Field(default=Path("./runtime-data/local-resilience"))
    resilience_local_database_path: Path | None = None
    resilience_local_signing_key_path: Path | None = None
    resilience_local_identity_file: Path | None = None
    resilience_local_vendor_source: Path | None = None
    resilience_local_git_remote: str | None = None
    resilience_local_git_mirror_path: Path | None = None
    resilience_local_ollama_models: dict[str, str] = Field(default_factory=dict)
    resilience_local_approved_noop_experiments: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_worker_lease_timing(self) -> "Settings":
        if self.worker_lease_seconds < self.worker_heartbeat_seconds * 3:
            raise ValueError("worker lease must be at least three heartbeat intervals")
        if self.worker_stale_after_seconds < self.worker_heartbeat_seconds * 2:
            raise ValueError("worker stale window must be at least two heartbeat intervals")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
