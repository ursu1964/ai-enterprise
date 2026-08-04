from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class BrokerAuthenticationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class NonceStore(Protocol):
    def reserve(self, nonce: uuid.UUID, *, seen_at: float, retain_until: float) -> bool: ...


class MemoryNonceStore:
    def __init__(self) -> None:
        self._seen_nonces: dict[uuid.UUID, float] = {}

    def reserve(self, nonce: uuid.UUID, *, seen_at: float, retain_until: float) -> bool:
        self._seen_nonces = {
            value: expiry for value, expiry in self._seen_nonces.items() if expiry >= seen_at
        }
        if nonce in self._seen_nonces:
            return False
        self._seen_nonces[nonce] = retain_until
        return True


class SqliteNonceStore:
    def __init__(self, path: Path) -> None:
        if path.is_symlink():
            raise ValueError("broker nonce database cannot be a symbolic link")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._path = path
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS broker_nonces "
                "(nonce TEXT PRIMARY KEY, seen_at REAL NOT NULL, retain_until REAL NOT NULL)"
            )
        path.chmod(0o600)

    def reserve(self, nonce: uuid.UUID, *, seen_at: float, retain_until: float) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM broker_nonces WHERE retain_until < ?", (seen_at,)
            )
            try:
                connection.execute(
                    "INSERT INTO broker_nonces (nonce, seen_at, retain_until) VALUES (?, ?, ?)",
                    (str(nonce), seen_at, retain_until),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def _connect(self) -> sqlite3.Connection:
        descriptor = os.open(
            self._path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            return sqlite3.connect(f"/proc/self/fd/{descriptor}")
        finally:
            os.close(descriptor)


class BrokerAuthenticator:
    def __init__(
        self,
        secret: bytes,
        *,
        maximum_clock_skew_seconds: int = 60,
        clock: Callable[[], float] = time.time,
        nonce_store: NonceStore | None = None,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("broker HMAC secret must contain at least 32 bytes")
        self._secret = secret
        self._maximum_clock_skew_seconds = maximum_clock_skew_seconds
        self._clock = clock
        self._nonce_store = nonce_store or MemoryNonceStore()

    def authenticate(
        self,
        *,
        method: str,
        path: str,
        worker_id: str,
        timestamp: str,
        nonce: str,
        signature: str,
        body: bytes,
    ) -> None:
        try:
            parsed_timestamp = int(timestamp)
            parsed_nonce = uuid.UUID(nonce)
        except (ValueError, TypeError) as exc:
            raise BrokerAuthenticationError(
                "invalid_auth_headers", "timestamp and nonce must be valid"
            ) from exc
        now = self._clock()
        if abs(now - parsed_timestamp) > self._maximum_clock_skew_seconds:
            raise BrokerAuthenticationError("stale_request", "request timestamp is outside policy")
        if not worker_id or len(worker_id) > 200 or any(char.isspace() for char in worker_id):
            raise BrokerAuthenticationError("invalid_worker_id", "worker identity is invalid")
        expected = self.sign(
            secret=self._secret,
            method=method,
            path=path,
            worker_id=worker_id,
            timestamp=timestamp,
            nonce=str(parsed_nonce),
            body=body,
        )
        if not hmac.compare_digest(expected, signature.lower()):
            raise BrokerAuthenticationError("invalid_signature", "request signature is invalid")
        if not self._nonce_store.reserve(
            parsed_nonce,
            seen_at=now,
            retain_until=now + max(900, self._maximum_clock_skew_seconds * 2),
        ):
            raise BrokerAuthenticationError("replayed_request", "request nonce was already used")

    @staticmethod
    def sign(
        *,
        secret: bytes,
        method: str,
        path: str,
        worker_id: str,
        timestamp: str,
        nonce: str,
        body: bytes,
    ) -> str:
        body_digest = hashlib.sha256(body).hexdigest()
        canonical = "\n".join(
            (method.upper(), path, worker_id, timestamp, nonce, body_digest)
        ).encode()
        return hmac.new(secret, canonical, hashlib.sha256).hexdigest()
