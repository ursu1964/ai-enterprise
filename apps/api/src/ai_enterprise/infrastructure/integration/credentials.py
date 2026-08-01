from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CredentialLease:
    """Ephemeral process environment; values must never be persisted or logged."""

    environment: Mapping[str, str] = field(repr=False)


class CredentialBroker(Protocol):
    def acquire_push_credentials(
        self, repository_id: str
    ) -> AbstractContextManager[CredentialLease]: ...


class NoCredentialsBroker:
    """Local-repository broker for tests and explicitly unauthenticated remotes."""

    class _Lease(AbstractContextManager[CredentialLease]):
        def __enter__(self) -> CredentialLease:
            return CredentialLease({})

        def __exit__(self, *args: object) -> None:
            return None

    def acquire_push_credentials(
        self, repository_id: str
    ) -> AbstractContextManager[CredentialLease]:
        return self._Lease()


class SshConfigCredentialBroker:
    """Expose a deployment-mounted SSH configuration only while pushing."""

    class _Lease(AbstractContextManager[CredentialLease]):
        def __init__(self, config_path: Path) -> None:
            self._config_path = config_path

        def __enter__(self) -> CredentialLease:
            if not self._config_path.is_file():
                raise RuntimeError("Integration SSH configuration is unavailable")
            return CredentialLease(
                {
                    "GIT_SSH_COMMAND": (
                        f"ssh -F {self._config_path} -o BatchMode=yes -o IdentitiesOnly=yes"
                    )
                }
            )

        def __exit__(self, *args: object) -> None:
            return None

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path

    def acquire_push_credentials(
        self, repository_id: str
    ) -> AbstractContextManager[CredentialLease]:
        return self._Lease(self._config_path)
