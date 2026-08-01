import asyncio

from ai_enterprise.application.recovery.factory import build_recovery_worker_entry
from ai_enterprise.infrastructure.integration.credentials import (
    SshConfigCredentialBroker,
)
from ai_enterprise.infrastructure.jobs.profiles import WorkerProfile
from ai_enterprise.worker import run_worker


def main() -> None:
    def build_entry(session, settings, worker_id):
        return build_recovery_worker_entry(
            session=session,
            settings=settings,
            worker_id=worker_id,
            credential_broker=SshConfigCredentialBroker(
                settings.recovery_ssh_config_path
            ),
        )

    asyncio.run(
        run_worker(
            profile=WorkerProfile.RECOVERY,
            recovery_entry_factory=build_entry,
        )
    )


if __name__ == "__main__":
    main()
