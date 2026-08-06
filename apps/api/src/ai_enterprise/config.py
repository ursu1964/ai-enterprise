from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
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
    r4_interpretation_provider: str = "mock"
    r4_interpretation_model: str = "ollama/gemma3:12b"
    r4_interpretation_base_url: str = "http://localhost:11434"
    r4_interpretation_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    r4_interpretation_timeout_seconds: int = Field(default=120, ge=1, le=900)
    r4_interpretation_max_tokens: int = Field(default=8192, ge=512, le=65536)
    r4_interpretation_provider_retries: int = Field(default=2, ge=0, le=5)
    r4_interpretation_schema_repair_attempts: int = Field(default=1, ge=0, le=1)
    r4_interpretation_redact_secrets: bool = True

    artifact_root: Path = Field(default=Path("./artifacts"))
    r6_publication_git_ssh_config_path: Path | None = None
    r6_publication_aws_profile: str | None = None
    r6_publication_aws_region: str | None = None
    r6_publication_npm_token: SecretStr | None = None
    r6_publication_npmrc_path: Path | None = None
    r7_runtime_kubeconfig_path: Path | None = None
    r7_runtime_opa_url: str | None = None
    r7_runtime_openai_api_key: SecretStr | None = None
    r7_runtime_plugin_root: Path | None = None
    r9_event_bus_backend: str = Field(
        default="local",
        pattern=r"^(local|kafka|sqs|nats)$",
    )
    r9_event_bus_endpoint: str | None = None
    r9_event_bus_topic: str | None = None
    r9_event_bus_region: str | None = None
    r9_event_bus_credentials_ref: str | None = None
    r9_worker_fleet_manifest_path: Path | None = None
    r9_sdk_registry_backend: str = Field(
        default="filesystem",
        pattern=r"^(filesystem|npm)$",
    )
    r9_sdk_registry_ref: str | None = None
    r11_external_integration_mode: str = Field(
        default="local",
        pattern=r"^(local|configured|disabled)$",
    )
    r11_external_endpoint_allowlist: str = ""
    r11_external_credential_refs: str = ""
    r11_partner_trust_refs: str = ""
    r11_gateway_base_url: str | None = None
    r11_secrets_manager_ref: str | None = None
    r16_graph_backend: str = Field(
        default="in_process",
        pattern=r"^(in_process|filesystem|neo4j|rdf|custom)$",
    )
    r16_graph_filesystem_root: Path = Field(default=Path("./runtime-data/r16-knowledge-graphs"))
    r16_graph_backend_endpoint: str | None = None
    r16_graph_backend_database: str | None = None
    r16_graph_backend_credentials_ref: str | None = None
    r16_graph_backend_deployment_evidence_ref: str | None = None
    r16_graph_backend_connectivity_evidence_ref: str | None = None
    r16_graph_backend_restore_evidence_ref: str | None = None
    r16_graph_backend_owner_approval_ref: str | None = None
    r16_graph_backend_partition_strategy: str = Field(
        default="layer",
        pattern=r"^(layer|domain|node_type)$",
    )
    r18_live_provider_calls_enabled: bool = False
    r18_openai_api_key: SecretStr | None = None
    r18_openai_model: str | None = None
    r18_openai_base_url: str = "https://api.openai.com/v1/responses"
    r18_anthropic_api_key: SecretStr | None = None
    r18_anthropic_model: str | None = None
    r18_anthropic_base_url: str = "https://api.anthropic.com/v1/messages"
    r18_google_api_key: SecretStr | None = None
    r18_google_model: str | None = None
    r18_custom_provider_api_key: SecretStr | None = None
    r18_custom_provider_model: str | None = None
    r18_custom_provider_base_url: str | None = None
    r18_provider_timeout_seconds: int = Field(default=120, ge=1, le=900)
    r19_memory_backend: str = Field(
        default="filesystem",
        pattern=r"^(filesystem|postgres|vector|custom)$",
    )
    r19_memory_semantic_index_backend: str = Field(
        default="deterministic",
        pattern=r"^(deterministic|pgvector|opensearch|custom)$",
    )
    r19_memory_endpoint_ref: str | None = None
    r19_memory_database_ref: str | None = None
    r19_memory_index_ref: str | None = None
    r19_memory_credentials_ref: str | None = None
    r19_memory_deployment_evidence_ref: str | None = None
    r19_memory_connectivity_evidence_ref: str | None = None
    r19_memory_encryption_required: bool = False
    r19_memory_kms_key_ref: str | None = None
    r19_memory_rbac_policy_ref: str | None = None
    r19_memory_retention_policy_ref: str | None = None
    bk_r10_ci_runner_provider: str = "mock"
    bk_r10_ci_runner_enabled: bool = False
    bk_r10_ci_runner_endpoint_ref: str | None = None
    bk_r10_ci_runner_credentials_ref: str | None = None
    bk_r10_scanner_provider: str = "mock"
    bk_r10_scanner_enabled: bool = False
    bk_r10_scanner_endpoint_ref: str | None = None
    bk_r10_scanner_credentials_ref: str | None = None
    bk_r10_evidence_store_provider: str = "mock"
    bk_r10_evidence_store_enabled: bool = False
    bk_r10_evidence_store_endpoint_ref: str | None = None
    bk_r10_evidence_store_credentials_ref: str | None = None
    bk_r10_evidence_store_ref: str | None = None
    bk_r10_policy_engine_provider: str = "mock"
    bk_r10_policy_engine_enabled: bool = False
    bk_r10_policy_engine_endpoint_ref: str | None = None
    bk_r10_policy_engine_credentials_ref: str | None = None
    bk_r10_policy_engine_policy_ref: str | None = None
    bk_r10_lab_environment_provider: str = "mock"
    bk_r10_lab_environment_enabled: bool = False
    bk_r10_lab_environment_endpoint_ref: str | None = None
    bk_r10_lab_environment_credentials_ref: str | None = None
    bk_r10_backend_timeout_seconds: int = Field(default=300, ge=1, le=7200)
    bk_r10_mock_backends_enabled: bool = True
    bk_r11_archive_backend: str = Field(
        default="filesystem",
        pattern=r"^(filesystem|s3|gcs|azure_blob|minio|custom)$",
    )
    bk_r11_archive_filesystem_root: Path = Field(default=Path("./artifacts/bk-r11-archives"))
    bk_r11_archive_uri_ref: str | None = None
    bk_r11_archive_credentials_ref: str | None = None
    bk_r11_archive_encryption_required: bool = False
    bk_r11_archive_kms_key_ref: str | None = None
    bk_r11_archive_deployment_evidence_ref: str | None = None
    bk_r11_archive_connectivity_evidence_ref: str | None = None
    bk_r11_signature_provider: str = Field(
        default="disabled",
        pattern=r"^(disabled|mock|kms|custom)$",
    )
    bk_r11_signature_required: bool = False
    bk_r11_signer_key_ref: str | None = None
    bk_r11_custom_signing_command: str | None = None
    bk_r11_mock_backends_enabled: bool = True

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
    execution_container_provider: str = "unconfigured"
    execution_image_id: str | None = None
    execution_broker_snapshots_root: Path = Field(
        default=Path("./runtime-data/execution-broker/snapshots")
    )
    execution_broker_evidence_root: Path = Field(
        default=Path("./runtime-data/execution-broker/terminal-evidence")
    )
    execution_snapshots_root: Path = Field(default=Path("./runtime-data/snapshots"))
    execution_artifacts_root: Path = Field(default=Path("./runtime-data/artifacts"))
    execution_temp_root: Path = Field(default=Path("./runtime-data/tmp"))
    execution_maximum_patch_bytes: int = 1_048_576
    execution_default_test_timeout_seconds: int = 300
    execution_implementation_timeout_seconds: int = 600

    review_image: str = "ai-enterprise-review-agent:local"
    review_image_id: str | None = None
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
