from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit


class LocalActivationSecurityError(ValueError):
    """A local activation request crossed a configured trust boundary."""


_LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})
_SENSITIVE_KEYS = frozenset(
    {"authorization", "credential", "password", "private_key", "secret", "token"}
)


def require_provider_environment(*, app_env: str, provider_kind: str) -> None:
    """Prevent a local provider from ever becoming eligible outside local environments."""

    if (
        provider_kind.strip().lower() == "local"
        and app_env.strip().lower() not in _LOCAL_ENVIRONMENTS
    ):
        raise LocalActivationSecurityError("Local providers are forbidden in this environment")


def require_configured_endpoint(*, requested: str, configured: str) -> str:
    """Return the canonical endpoint only when it exactly matches configuration."""

    requested_value = _canonical_endpoint(requested)
    configured_value = _canonical_endpoint(configured)
    if not configured_value or requested_value != configured_value:
        raise LocalActivationSecurityError("Model endpoint is not the configured endpoint")
    return configured_value


def require_bounded_bare_remote(*, remote_url: str, allowed_root: Path) -> Path:
    """Accept only an existing bare file remote physically contained by the configured root."""

    parsed = urlsplit(remote_url)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise LocalActivationSecurityError("Local Git remote must use a local file URL")
    if parsed.query or parsed.fragment:
        raise LocalActivationSecurityError("Local Git remote URL cannot contain query or fragment")
    candidate = Path(unquote(parsed.path))
    return _require_confined_existing_path(candidate, allowed_root, require_bare=True)


def require_confined_backup_path(*, candidate: Path, allowed_root: Path) -> Path:
    """Constrain backup files and reject symlink traversal, including non-final components."""

    root = allowed_root.resolve(strict=True)
    _reject_symlink_components(candidate, root)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise LocalActivationSecurityError("Backup path escapes its configured root") from exc
    return resolved


def require_safe_log_metadata(metadata: dict[str, object]) -> dict[str, object]:
    """Reject secret-bearing logging metadata instead of attempting lossy redaction."""

    offenders = {key for key in metadata if key.strip().lower() in _SENSITIVE_KEYS}
    if offenders:
        raise LocalActivationSecurityError("Secret-bearing metadata cannot be logged")
    return dict(metadata)


@dataclass(frozen=True, slots=True)
class RestoreIsolationEvidence:
    isolated_workspace: bool
    production_credentials_absent: bool
    external_dispatch_blocked: bool
    source_backup_hash: str
    verification_artifact_hash: str


def require_restore_isolation(evidence: RestoreIsolationEvidence) -> None:
    if not all(
        (
            evidence.isolated_workspace,
            evidence.production_credentials_absent,
            evidence.external_dispatch_blocked,
            len(evidence.source_backup_hash) == 64,
            len(evidence.verification_artifact_hash) == 64,
        )
    ):
        raise LocalActivationSecurityError("Restore isolation evidence is incomplete")


@dataclass(frozen=True, slots=True)
class HmacSigner:
    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not self.key_id or len(self.secret) < 32:
            raise LocalActivationSecurityError(
                "Signer key identity and 256-bit secret are required"
            )

    def sign(self, digest: bytes) -> str:
        return hmac.new(self.secret, digest, hashlib.sha256).hexdigest()

    def verify(self, digest: bytes, signature: str) -> bool:
        return hmac.compare_digest(self.sign(digest), signature)


def sign_identity_assertion(
    *, secret: bytes, actor_id: str, actor_type: str, actor_role: str, timestamp: int
) -> str:
    message = f"{actor_id}\n{actor_type}\n{actor_role}\n{timestamp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_identity_assertion(
    *,
    secret: bytes,
    actor_id: str,
    actor_type: str,
    actor_role: str,
    timestamp: int,
    signature: str,
) -> bool:
    expected = sign_identity_assertion(
        secret=secret,
        actor_id=actor_id,
        actor_type=actor_type,
        actor_role=actor_role,
        timestamp=timestamp,
    )
    return hmac.compare_digest(expected, signature)


def _canonical_endpoint(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise LocalActivationSecurityError("Model endpoint must be an HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LocalActivationSecurityError("Model endpoint cannot embed credentials or parameters")
    path = parsed.path.rstrip("/")
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme.lower()}://{host}{port}{path}"


def _require_confined_existing_path(
    candidate: Path, allowed_root: Path, *, require_bare: bool
) -> Path:
    root = allowed_root.resolve(strict=True)
    _reject_symlink_components(candidate, root)
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise LocalActivationSecurityError("Local Git remote escapes its configured root") from exc
    if require_bare and not all((resolved / name).exists() for name in ("HEAD", "objects", "refs")):
        raise LocalActivationSecurityError("Local Git remote is not a bare repository")
    return resolved


def _reject_symlink_components(candidate: Path, root: Path) -> None:
    absolute = candidate if candidate.is_absolute() else root / candidate
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise LocalActivationSecurityError("Symlink traversal is forbidden")
