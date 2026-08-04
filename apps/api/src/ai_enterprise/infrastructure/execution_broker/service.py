from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, Response, status

from ai_enterprise.infrastructure.execution_broker.auth import (
    BrokerAuthenticationError,
    BrokerAuthenticator,
    SqliteNonceStore,
)
from ai_enterprise.infrastructure.execution_broker.policy import (
    MAXIMUM_ARCHIVE_BYTES,
    BrokerPolicyError,
)
from ai_enterprise.infrastructure.execution_broker.store import SnapshotStore


def create_broker_app(
    *,
    snapshot_root: Path,
    hmac_secret: bytes,
    clock: Callable[[], float] = time.time,
    nonce_database_path: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="AI Enterprise Restricted Execution Broker", docs_url=None)
    nonce_store = SqliteNonceStore(
        nonce_database_path or snapshot_root.parent / "broker-nonces.sqlite3"
    )
    authenticator = BrokerAuthenticator(hmac_secret, clock=clock, nonce_store=nonce_store)
    store = SnapshotStore(snapshot_root)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok", "service": "restricted-execution-broker"}

    @app.get("/health/ready")
    async def ready(response: Response) -> dict[str, object]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "blocked",
            "code": "engine_adapter_unconfigured",
            "next": "Configure and verify the restricted engine adapter before dispatch.",
            "snapshot_store": "ready",
            "snapshot_reconciliation": {
                "stale_staging_quarantined": (
                    store.reconciliation.stale_staging_quarantined
                ),
                "orphan_objects_quarantined": (
                    store.reconciliation.orphan_objects_quarantined
                ),
                "referenced_objects_verified": (
                    store.reconciliation.referenced_objects_verified
                ),
                "blocking_references": store.reconciliation.blocking_references,
            },
        }

    @app.post("/v1/snapshots", status_code=status.HTTP_201_CREATED)
    async def register_snapshot(
        request: Request,
        x_broker_worker_id: str = Header(),
        x_broker_timestamp: str = Header(),
        x_broker_nonce: str = Header(),
        x_broker_signature: str = Header(),
    ) -> dict[str, str | int]:
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/gzip":
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={"code": "unsupported_media_type"},
            )
        encoded = bytearray()
        async for chunk in request.stream():
            encoded.extend(chunk)
            if len(encoded) > MAXIMUM_ARCHIVE_BYTES:
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    detail={"code": "archive_too_large"},
                )
        body = bytes(encoded)
        try:
            authenticator.authenticate(
                method=request.method,
                path=request.url.path,
                worker_id=x_broker_worker_id,
                timestamp=x_broker_timestamp,
                nonce=x_broker_nonce,
                signature=x_broker_signature,
                body=body,
            )
            snapshot = store.register(body, owner_worker_id=x_broker_worker_id)
        except BrokerAuthenticationError as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, detail={"code": exc.code}
            ) from exc
        except BrokerPolicyError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "snapshot_policy_rejected", "message": str(exc)},
            ) from exc
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "snapshot_store_unavailable"},
            ) from exc
        return {
            "schema_version": 1,
            "snapshot_ref": str(snapshot.snapshot_ref),
            "archive_sha256": snapshot.archive_sha256,
            "tree_sha256": snapshot.tree_sha256,
            "manifest_sha256": snapshot.manifest_sha256,
            "file_count": snapshot.file_count,
            "expanded_bytes": snapshot.expanded_bytes,
            "owner_worker_id": snapshot.owner_worker_id,
            "created_at": snapshot.created_at.isoformat(),
        }

    return app
