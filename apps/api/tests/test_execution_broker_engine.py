import uuid
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from docker.errors import APIError

from ai_enterprise.infrastructure.execution_broker.engine import (
    BrokerEngineError,
    DockerEngineAdapter,
)
from ai_enterprise.infrastructure.execution_broker.policy import BrokerPolicy, BrokerRunRequest

EXECUTION_IMAGE_ID = "sha256:" + "a" * 64
REVIEW_IMAGE_ID = "sha256:" + "b" * 64


def request() -> BrokerRunRequest:
    return BrokerRunRequest.model_validate(
        {
            "schema_version": 1,
            "idempotency_key": uuid.uuid4(),
            "workload_id": uuid.uuid4(),
            "kind": "execution",
            "image_policy_key": "execution-agent",
            "resource_profile": "small",
            "snapshot_ref": uuid.uuid4(),
            "input_sha256": "c" * 64,
            "correlation_id": uuid.uuid4(),
        }
    )


def adapter(
    client: MagicMock,
    *,
    clock: Callable[[], float] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> DockerEngineAdapter:
    return DockerEngineAdapter(
        client,
        BrokerPolicy(
            execution_image_id=EXECUTION_IMAGE_ID,
            review_image_id=REVIEW_IMAGE_ID,
        ),
        **({"clock": clock} if clock is not None else {}),
        **({"sleeper": sleeper} if sleeper is not None else {}),
    )


def configured_client() -> tuple[MagicMock, MagicMock, list[MagicMock]]:
    client = MagicMock()
    image = MagicMock(id=EXECUTION_IMAGE_ID)
    client.images.get.return_value = image
    volumes = [MagicMock(name=f"volume-{index}") for index in range(3)]
    client.volumes.create.side_effect = volumes
    container = MagicMock(
        id="opaque-runtime-id",
        status="exited",
        attrs={"Image": EXECUTION_IMAGE_ID},
    )
    container.wait.return_value = {"StatusCode": 0}
    container.get_archive.side_effect = [([b"output"], {}), ([b"workspace"], {})]
    container.logs.return_value = b"bounded log"
    client.containers.create.return_value = container
    return client, container, volumes


def test_engine_constructs_exact_hardened_container_and_cleans_up(tmp_path: Path) -> None:
    client, container, volumes = configured_client()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "app.py").write_text("print('ok')\n", encoding="utf-8")

    result = adapter(client).run(request(), snapshot_root=snapshot, runtime_input={"ok": True})

    assert result.exit_code == 0
    create = client.containers.create.call_args.kwargs
    assert create["image"] == EXECUTION_IMAGE_ID
    assert create["detach"] is True
    assert create["network_disabled"] is True
    assert create["read_only"] is True
    assert create["user"] == "10001:10001"
    assert create["cap_drop"] == ["ALL"]
    assert create["security_opt"] == ["no-new-privileges:true"]
    assert create["privileged"] is False
    assert {mount["bind"] for mount in create["volumes"].values()} == {
        "/workspace",
        "/runtime-input",
        "/runtime-output",
    }
    assert sorted(mount["mode"] for mount in create["volumes"].values()) == [
        "ro",
        "rw",
        "rw",
    ]
    for forbidden in (
        "command",
        "entrypoint",
        "devices",
        "device_requests",
        "network_mode",
        "pid_mode",
        "ipc_mode",
        "ports",
        "extra_hosts",
        "cap_add",
    ):
        assert forbidden not in create
    container.remove.assert_called_once_with(force=True, v=True)
    assert all(volume.remove.call_count == 1 for volume in volumes)


def test_engine_rejects_post_create_image_mismatch_before_start(tmp_path: Path) -> None:
    client, container, _volumes = configured_client()
    container.attrs = {"Image": REVIEW_IMAGE_ID}
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    with pytest.raises(BrokerEngineError, match="image identity changed"):
        adapter(client).run(request(), snapshot_root=snapshot, runtime_input={})

    container.start.assert_not_called()
    container.remove.assert_called_once_with(force=True, v=True)


def test_engine_timeout_kills_and_removes_container(tmp_path: Path) -> None:
    client, container, _volumes = configured_client()
    container.status = "running"
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    with pytest.raises(BrokerEngineError) as raised:
        adapter(client, clock=MagicMock(side_effect=[0.0, 301.0]), sleeper=lambda _: None).run(
            request(), snapshot_root=snapshot, runtime_input={}
        )

    assert raised.value.code == "engine_timeout"
    container.kill.assert_called_once_with(signal="SIGKILL")
    container.remove.assert_called_once_with(force=True, v=True)


def test_engine_cleanup_failure_overrides_success(tmp_path: Path) -> None:
    client, container, _volumes = configured_client()
    container.remove.side_effect = APIError("remove failed")
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    with pytest.raises(BrokerEngineError) as raised:
        adapter(client).run(request(), snapshot_root=snapshot, runtime_input={})

    assert raised.value.code == "engine_cleanup_failed"
