from __future__ import annotations

from typing import Protocol
from uuid import UUID


class RegionWitness(Protocol):
    async def acquire_fencing_token(self, resource_id: UUID, region: str) -> tuple[int, str]: ...


class ModelGateway(Protocol):
    async def generate(self, model_id: UUID, request: dict[str, object]) -> dict[str, object]: ...


class SigningProvider(Protocol):
    async def sign(self, provider_reference: str, content_hash: str) -> tuple[bytes, str]: ...


class IdentityContinuityProvider(Protocol):
    async def strongly_authenticate(self, principal_id: str) -> bool: ...


class VendorExportProvider(Protocol):
    async def export(self, plan_id: UUID) -> tuple[str, str]: ...


class ChaosExecutionProvider(Protocol):
    async def execute(self, experiment_id: UUID) -> tuple[str, str]: ...


class ArchiveVerificationProvider(Protocol):
    async def verify(self, archive_location: str, checkpoint_hash: str) -> tuple[bool, str]: ...


class UnconfiguredExternalProvider:
    """Explicit fail-closed placeholder; never reports external success."""

    def __getattr__(self, name: str) -> object:
        raise RuntimeError(f"External resilience provider is not configured: {name}")
