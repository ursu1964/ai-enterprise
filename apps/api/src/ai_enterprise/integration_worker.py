import asyncio

from ai_enterprise.application.integration.factory import (
    build_integration_worker_entry,
)
from ai_enterprise.infrastructure.integration.credentials import (
    SshConfigCredentialBroker,
)
from ai_enterprise.infrastructure.jobs.profiles import WorkerProfile
from ai_enterprise.infrastructure.recovery.rollback_metadata import (
    build_sql_rollback_metadata_hook,
)
from ai_enterprise.worker import run_worker


def main() -> None:
    def build_entry(session, settings, worker_id):
        return build_integration_worker_entry(
            session=session,
            settings=settings,
            worker_id=worker_id,
            credential_broker=SshConfigCredentialBroker(
                settings.integration_ssh_config_path
            ),
            rollback_hook=build_sql_rollback_metadata_hook(session),
        )

    asyncio.run(
        run_worker(
            profile=WorkerProfile.INTEGRATION,
            integration_entry_factory=build_entry,
        )
    )


if __name__ == "__main__":
    main()
