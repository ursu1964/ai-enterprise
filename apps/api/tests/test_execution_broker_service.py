import io
import tarfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.infrastructure.execution_broker.auth import BrokerAuthenticator
from ai_enterprise.infrastructure.execution_broker.engine import BrokerEngineResult
from ai_enterprise.infrastructure.execution_broker.evidence import TerminalEvidenceStore
from ai_enterprise.infrastructure.execution_broker.policy import BrokerRunRequest
from ai_enterprise.infrastructure.execution_broker.service import create_broker_app

SECRET = b"b" * 32
WORKER_ID = "worker-general-1"
TIMESTAMP = "1700000000"


def archive(name: str = "src/app.py", content: bytes = b"print('ok')\n") -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        bundle.addfile(info, io.BytesIO(content))
    return output.getvalue()


def headers(body: bytes, *, nonce: str | None = None) -> dict[str, str]:
    selected_nonce = nonce or str(uuid.uuid4())
    return {
        "content-type": "application/gzip",
        "x-broker-worker-id": WORKER_ID,
        "x-broker-timestamp": TIMESTAMP,
        "x-broker-nonce": selected_nonce,
        "x-broker-signature": BrokerAuthenticator.sign(
            secret=SECRET,
            method="POST",
            path="/v1/snapshots",
            worker_id=WORKER_ID,
            timestamp=TIMESTAMP,
            nonce=selected_nonce,
            body=body,
        ),
    }


def client(tmp_path: Path) -> TestClient:
    app = create_broker_app(
        snapshot_root=tmp_path / "snapshots",
        hmac_secret=SECRET,
        clock=lambda: int(TIMESTAMP),
    )
    return TestClient(app)


def test_health_is_live_but_truthfully_not_execution_ready(tmp_path: Path) -> None:
    broker = client(tmp_path)

    assert broker.get("/health/live").status_code == 200
    response = broker.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["code"] == "engine_adapter_unconfigured"
    assert response.json()["snapshot_store"] == "ready"
    assert response.json()["snapshot_reconciliation"]["blocking_references"] == 0
    assert response.json()["terminal_evidence"] == {
        "retained_records": 0,
        "completed_records": 0,
        "pending_handoff": 0,
    }


def test_readiness_reports_pending_terminal_evidence_after_restart(
    tmp_path: Path,
) -> None:
    evidence_store = TerminalEvidenceStore(tmp_path / "terminal-evidence")
    request = BrokerRunRequest.model_validate(
        {
            "schema_version": 1,
            "idempotency_key": uuid.uuid4(),
            "workload_id": uuid.uuid4(),
            "kind": "execution",
            "image_policy_key": "execution-agent",
            "resource_profile": "small",
            "snapshot_ref": uuid.uuid4(),
            "input_sha256": "0" * 64,
            "correlation_id": uuid.uuid4(),
        }
    )
    evidence_store.record(
        request,
        BrokerEngineResult(
            runtime_instance_id="runtime-1",
            image_id="sha256:" + "a" * 64,
            exit_code=1,
            output_archive=b"output",
            workspace_archive=b"workspace",
            runtime_log="log",
            retained_evidence_volumes={
                "workspace": "ai-broker-workload-nonce-workspace",
                "output": "ai-broker-workload-nonce-output",
            },
        ),
    )

    response = client(tmp_path).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["terminal_evidence"] == {
        "retained_records": 1,
        "completed_records": 0,
        "pending_handoff": 1,
    }


def test_authenticated_snapshot_is_immutable_and_privately_stored(
    tmp_path: Path,
) -> None:
    body = archive()
    response = client(tmp_path).post("/v1/snapshots", content=body, headers=headers(body))

    assert response.status_code == 201
    payload = response.json()
    stored = tmp_path / "snapshots" / "objects" / payload["tree_sha256"]
    assert (stored / "tree/src/app.py").read_bytes() == b"print('ok')\n"
    assert (stored / "READY.json").is_file()
    assert not list((tmp_path / "snapshots" / ".staging").iterdir())


def test_tamper_and_replay_are_rejected(tmp_path: Path) -> None:
    broker = client(tmp_path)
    body = archive()
    nonce = str(uuid.uuid4())
    signed = headers(body, nonce=nonce)

    assert broker.post("/v1/snapshots", content=body, headers=signed).status_code == 201
    replay = broker.post("/v1/snapshots", content=body, headers=signed)
    tampered = broker.post("/v1/snapshots", content=body + b"x", headers=headers(body))

    assert replay.status_code == 401
    assert replay.json()["detail"]["code"] == "replayed_request"
    assert tampered.status_code == 401
    assert tampered.json()["detail"]["code"] == "invalid_signature"


def test_nonce_replay_remains_blocked_after_service_restart(tmp_path: Path) -> None:
    body = archive()
    nonce = str(uuid.uuid4())
    signed = headers(body, nonce=nonce)

    assert client(tmp_path).post("/v1/snapshots", content=body, headers=signed).status_code == 201
    replay = client(tmp_path).post("/v1/snapshots", content=body, headers=signed)

    assert replay.status_code == 401
    assert replay.json()["detail"]["code"] == "replayed_request"


def test_archive_policy_rejection_leaves_no_snapshot(tmp_path: Path) -> None:
    body = archive("../escape")
    response = client(tmp_path).post("/v1/snapshots", content=body, headers=headers(body))

    assert response.status_code == 422
    assert not list((tmp_path / "snapshots" / "objects").iterdir())
    assert not list((tmp_path / "snapshots" / ".staging").iterdir())
