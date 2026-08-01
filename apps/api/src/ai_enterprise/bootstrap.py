import argparse
import asyncio
import secrets
import stat
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from ai_enterprise.config import get_settings
from ai_enterprise.infrastructure.agent_runtime.seed import seed_initial_skills
from ai_enterprise.infrastructure.database.foundation_models import (
    ActorIdentityModel,
    AuthorityGrantModel,
)
from ai_enterprise.infrastructure.database.session import SessionFactory
from ai_enterprise.infrastructure.organization.seed import seed_organization
from ai_enterprise.infrastructure.resilience.extended_models import (
    ModelDefinitionModel,
    ModelProviderModel,
    RegionModel,
)
from ai_enterprise.infrastructure.security.local_activation import (
    require_bounded_bare_remote,
    require_provider_environment,
)

NAMESPACE = uuid.UUID("be652ec0-3bda-4de3-b7fc-4a575bac6fee")
DEV_GRANTS = {
    "change.create": "change_proposer",
    "change.submit": "change_proposer",
    "change.assess": "change_assessor",
    "change.validate": "change_validator",
    "change.decide": "change_approver",
    "integration.approve": "integration_approver",
    "integration.operate": "integration_operator",
    "recovery.approve": "rollback_approver",
    "resilience.admin": "resilience_admin",
    "model.governance": "model_governance_authority",
}


def _write_secrets(path: Path) -> None:
    if path.exists():
        return
    path.write_text(
        "TRUSTED_PROXY_HMAC_SECRET=" + secrets.token_hex(32) + "\n"
        "LOCAL_SIGNING_SECRET=" + secrets.token_hex(32) + "\n",
        encoding="utf-8",
    )
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def prepare_runtime(root: Path) -> str:
    for name in ("remotes", "integration-work", "recovery-work", "snapshots", "tmp"):
        (root / name).mkdir(parents=True, exist_ok=True)
    _write_secrets(root / "dev-secrets.env")
    remote = (root / "remotes" / "ai-enterprise.git").resolve()
    if not remote.exists():
        subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(remote)], check=True)
    remote_url = remote.as_uri()
    require_bounded_bare_remote(remote_url=remote_url, allowed_root=root.resolve())
    return remote_url


async def seed_database() -> None:
    now = datetime.now(UTC)
    actor_id = uuid.uuid5(NAMESPACE, "actor:local-admin")
    provider_id = uuid.uuid5(NAMESPACE, "provider:local-ollama")
    region_id = uuid.uuid5(NAMESPACE, "region:local-dev")
    model_id = uuid.uuid5(NAMESPACE, "model:local-default")
    settings = get_settings()
    require_provider_environment(app_env=settings.app_env, provider_kind="local")
    async with SessionFactory() as session, session.begin():
        organization_id = await seed_organization(session)
        await seed_initial_skills(session, organization_id)
        if await session.get(ActorIdentityModel, actor_id) is None:
            session.add(
                ActorIdentityModel(
                    id=actor_id, subject="local-admin", actor_type="human", enabled=True
                )
            )
        for capability, role in DEV_GRANTS.items():
            existing = await session.scalar(
                select(AuthorityGrantModel).where(
                    AuthorityGrantModel.actor_id == actor_id,
                    AuthorityGrantModel.capability == capability,
                    AuthorityGrantModel.scope == "development",
                )
            )
            if existing is None:
                session.add(
                    AuthorityGrantModel(
                        id=uuid.uuid5(NAMESPACE, f"grant:{capability}"),
                        actor_id=actor_id,
                        role=role,
                        capability=capability,
                        scope="development",
                        granted_by="local-bootstrap",
                        valid_from=now,
                    )
                )
            else:
                existing.role = role
        if await session.get(RegionModel, region_id) is None:
            session.add(
                RegionModel(id=region_id, code="local-dev", jurisdiction="LOCAL", status="active")
            )
        if await session.get(ModelProviderModel, provider_id) is None:
            session.add(
                ModelProviderModel(
                    id=provider_id,
                    name="local-ollama",
                    regions=["local-dev"],
                    retention_mode="local-only",
                    status="active",
                )
            )
        if await session.get(ModelDefinitionModel, model_id) is None:
            session.add(
                ModelDefinitionModel(
                    id=model_id,
                    provider_id=provider_id,
                    name=settings.ollama_model,
                    version="development",
                    hosting_region="local-dev",
                    approved_use_cases=["requirements", "architecture", "planning", "review"],
                    prohibited_data_classes=["regulated-production"],
                    status="active",
                    evaluation_evidence_hash=None,
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotent local AI Enterprise bootstrap")
    parser.add_argument("--runtime-root", type=Path, default=Path("runtime-data"))
    parser.add_argument("--skip-seed", action="store_true")
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    remote_url = prepare_runtime(runtime_root)
    print(f"LOCAL_GIT_REMOTE_URL={remote_url}")
    print(f"DEV_SECRETS_FILE={runtime_root / 'dev-secrets.env'}")
    if not args.skip_seed:
        asyncio.run(seed_database())


if __name__ == "__main__":
    main()
