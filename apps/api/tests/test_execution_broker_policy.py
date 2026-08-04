import io
import tarfile
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.infrastructure.execution_broker.policy import (
    BrokerPolicy,
    BrokerPolicyError,
    BrokerRunRequest,
    extract_snapshot_archive,
)

EXECUTION_IMAGE_ID = "sha256:" + "a" * 64
REVIEW_IMAGE_ID = "sha256:" + "b" * 64


def request_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "idempotency_key": str(uuid.uuid4()),
        "workload_id": str(uuid.uuid4()),
        "kind": "execution",
        "image_policy_key": "execution-agent",
        "resource_profile": "standard",
        "snapshot_ref": str(uuid.uuid4()),
        "input_sha256": "c" * 64,
        "correlation_id": str(uuid.uuid4()),
    }
    payload.update(updates)
    return payload


def archive(entries: list[tuple[str, bytes, str]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        for name, content, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(content)
                bundle.addfile(info, io.BytesIO(content))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                bundle.addfile(info)
            else:
                raise AssertionError(kind)
    return output.getvalue()


def test_request_rejects_docker_options_and_wrong_image_policy() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BrokerRunRequest.model_validate(request_payload(privileged=True))
    with pytest.raises(ValidationError, match="image policy does not match"):
        BrokerRunRequest.model_validate(
            request_payload(image_policy_key="review-agent")
        )


def test_policy_resolves_only_immutable_images_and_bounded_profiles() -> None:
    policy = BrokerPolicy(
        execution_image_id=EXECUTION_IMAGE_ID, review_image_id=REVIEW_IMAGE_ID
    )
    resolved = policy.resolve(BrokerRunRequest.model_validate(request_payload()))

    assert resolved.image_id == EXECUTION_IMAGE_ID
    assert resolved.runtime_uid == 10001
    assert resolved.resources.memory_bytes == 1 << 30
    with pytest.raises(BrokerPolicyError, match="immutable sha256"):
        BrokerPolicy(
            execution_image_id="execution-agent:latest",
            review_image_id=REVIEW_IMAGE_ID,
        )


def test_archive_extracts_regular_files_under_assigned_root(tmp_path: Path) -> None:
    encoded = archive([("src/app.py", b"print('ok')\n", "file")])

    digest = extract_snapshot_archive(encoded, tmp_path / "snapshot")

    assert len(digest) == 64
    assert (tmp_path / "snapshot/src/app.py").read_bytes() == b"print('ok')\n"


@pytest.mark.parametrize(
    ("name", "kind", "message"),
    [
        ("../escape", "file", "unsafe path"),
        ("/absolute", "file", "unsafe path"),
        ("source-link", "symlink", "forbidden entry type"),
    ],
)
def test_archive_rejects_escape_and_link_entries(
    tmp_path: Path, name: str, kind: str, message: str
) -> None:
    encoded = archive([(name, b"data", kind)])

    with pytest.raises(BrokerPolicyError, match=message):
        extract_snapshot_archive(encoded, tmp_path / "snapshot")


def test_archive_rejects_compressed_and_expanded_size_excess(tmp_path: Path) -> None:
    encoded = archive([("large.bin", b"x" * 1024, "file")])

    with pytest.raises(BrokerPolicyError, match="size limit"):
        extract_snapshot_archive(encoded, tmp_path / "compressed", maximum_bytes=8)
    with pytest.raises(BrokerPolicyError, match="expanded snapshot"):
        extract_snapshot_archive(encoded, tmp_path / "expanded", maximum_bytes=512)


@pytest.mark.parametrize("name", ["src\\app.py", "cafe\u0301.py", "bad\nname.py"])
def test_archive_rejects_nonportable_paths(tmp_path: Path, name: str) -> None:
    with pytest.raises(BrokerPolicyError, match="not portable"):
        extract_snapshot_archive(
            archive([(name, b"data", "file")]), tmp_path / "snapshot"
        )


def test_archive_rejects_casefold_path_collisions(tmp_path: Path) -> None:
    with pytest.raises(BrokerPolicyError, match="path collision"):
        extract_snapshot_archive(
            archive([("Readme", b"a", "file"), ("README", b"b", "file")]),
            tmp_path / "snapshot",
        )
