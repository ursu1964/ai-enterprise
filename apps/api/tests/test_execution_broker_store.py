import io
import json
import sqlite3
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ai_enterprise.infrastructure.execution_broker.store import SnapshotStore


def archive(
    entries: list[tuple[str, bytes, int]], *, mtime: int = 0, gzip: bool = True
) -> bytes:
    output = io.BytesIO()
    mode = "w:gz" if gzip else "w"
    with tarfile.open(fileobj=output, mode=mode) as bundle:
        for name, content, permissions in entries:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = permissions
            info.mtime = mtime
            bundle.addfile(info, io.BytesIO(content))
    return output.getvalue()


def test_equivalent_archives_deduplicate_by_canonical_tree(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    first = store.register(
        archive(
            [("src/a.py", b"a\n", 0o644), ("src/b.py", b"b\n", 0o644)],
            mtime=1,
        ),
        owner_worker_id="worker-a",
    )
    second = store.register(
        archive(
            [("src/b.py", b"b\n", 0o600), ("src/a.py", b"a\n", 0o600)],
            mtime=999,
        ),
        owner_worker_id="worker-a",
    )

    assert first.snapshot_ref != second.snapshot_ref
    assert first.archive_sha256 != second.archive_sha256
    assert first.tree_sha256 == second.tree_sha256
    assert len(list((tmp_path / "snapshots" / "objects").iterdir())) == 1


def test_reference_is_owner_bound_and_survives_restart(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"
    stored = SnapshotStore(root).register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )

    restarted = SnapshotStore(root)
    assert restarted.resolve(stored.snapshot_ref, owner_worker_id="worker-a").is_dir()
    with pytest.raises(KeyError, match="unavailable"):
        restarted.resolve(stored.snapshot_ref, owner_worker_id="worker-b")


def test_executable_intent_changes_tree_identity_and_stored_mode(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    regular = store.register(
        archive([("run.sh", b"exit 0\n", 0o644)]), owner_worker_id="worker-a"
    )
    executable = store.register(
        archive([("run.sh", b"exit 0\n", 0o755)]), owner_worker_id="worker-a"
    )

    assert regular.tree_sha256 != executable.tree_sha256
    regular_file = store.resolve(regular.snapshot_ref, owner_worker_id="worker-a") / "run.sh"
    executable_file = (
        store.resolve(executable.snapshot_ref, owner_worker_id="worker-a") / "run.sh"
    )
    assert regular_file.stat().st_mode & 0o777 == 0o400
    assert executable_file.stat().st_mode & 0o777 == 0o500


def test_resolve_rejects_content_corruption(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    stored = store.register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )
    target = store.resolve(stored.snapshot_ref, owner_worker_id="worker-a") / "main.py"
    target.chmod(0o600)
    target.write_bytes(b"corrupt\n")

    with pytest.raises(ValueError, match="corrupt"):
        store.resolve(stored.snapshot_ref, owner_worker_id="worker-a")


def test_resolve_rejects_ready_metadata_tamper(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    stored = store.register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )
    object_root = tmp_path / "snapshots" / "objects" / stored.tree_sha256
    ready_path = object_root / "READY.json"
    object_root.chmod(0o700)
    ready_path.chmod(0o600)
    ready = json.loads(ready_path.read_text(encoding="utf-8"))
    ready["file_count"] = 999
    ready_path.write_text(json.dumps(ready), encoding="utf-8")

    with pytest.raises(ValueError, match="corrupt"):
        store.resolve(stored.snapshot_ref, owner_worker_id="worker-a")


def test_resolve_rejects_database_reference_rebind(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"
    store = SnapshotStore(root)
    first = store.register(
        archive([("first.py", b"one\n", 0o644)]), owner_worker_id="worker-a"
    )
    second = store.register(
        archive([("second.py", b"two\n", 0o644)]), owner_worker_id="worker-a"
    )
    with sqlite3.connect(root / "registrations.sqlite3") as connection:
        connection.execute(
            "UPDATE snapshot_registrations SET tree_sha256 = ? WHERE snapshot_ref = ?",
            (second.tree_sha256, str(first.snapshot_ref)),
        )

    with pytest.raises(ValueError, match="identity mismatch"):
        store.resolve(first.snapshot_ref, owner_worker_id="worker-a")


def test_concurrent_equivalent_publications_share_one_object(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    encoded = archive([("main.py", b"pass\n", 0o644)])
    with ThreadPoolExecutor(max_workers=4) as executor:
        stored = list(
            executor.map(
                lambda _: store.register(encoded, owner_worker_id="worker-a"), range(4)
            )
        )

    assert len({item.snapshot_ref for item in stored}) == 4
    assert len({item.tree_sha256 for item in stored}) == 1
    assert len(list((tmp_path / "snapshots" / "objects").iterdir())) == 1
    assert all(
        store.resolve(item.snapshot_ref, owner_worker_id="worker-a").is_dir()
        for item in stored
    )
