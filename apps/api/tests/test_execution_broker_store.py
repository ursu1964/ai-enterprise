import io
import json
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import ai_enterprise.infrastructure.execution_broker.store as store_module
from ai_enterprise.infrastructure.execution_broker.store import (
    SnapshotStore,
    SnapshotStoreCorruptionError,
)


class SimulatedCrash(BaseException):
    pass


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
    assert restarted.resolve(stored.snapshot_ref, owner_worker_id="worker-a").root.is_dir()
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
    regular_file = store.resolve(regular.snapshot_ref, owner_worker_id="worker-a").root / "run.sh"
    executable_file = (
        store.resolve(executable.snapshot_ref, owner_worker_id="worker-a").root / "run.sh"
    )
    assert regular_file.stat().st_mode & 0o777 == 0o400
    assert executable_file.stat().st_mode & 0o777 == 0o500


def test_resolve_rejects_content_corruption(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots")
    stored = store.register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )
    target = store.resolve(stored.snapshot_ref, owner_worker_id="worker-a").root / "main.py"
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
        store.resolve(item.snapshot_ref, owner_worker_id="worker-a").root.is_dir()
        for item in stored
    )


def test_startup_quarantines_interrupted_staging_without_following_links(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshots"
    SnapshotStore(root)
    partial = root / ".staging" / "interrupted.partial"
    partial.mkdir()
    (partial / "evidence.txt").write_text("preserve", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / ".staging" / "foreign-link"
    link.symlink_to(outside, target_is_directory=True)

    restarted = SnapshotStore(root)

    assert restarted.reconciliation.stale_staging_quarantined == 2
    assert not list((root / ".staging").iterdir())
    assert outside.is_dir()
    reasons = [
        json.loads(path.read_text(encoding="utf-8"))["reason"]
        for path in (root / ".quarantine").glob("*.json")
    ]
    assert reasons == ["interrupted-staging", "interrupted-staging"]


def test_startup_quarantines_object_without_registration(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"
    store = SnapshotStore(root)
    stored = store.register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )
    with sqlite3.connect(root / "registrations.sqlite3") as connection:
        connection.execute(
            "DELETE FROM snapshot_registrations WHERE snapshot_ref = ?",
            (str(stored.snapshot_ref),),
        )

    restarted = SnapshotStore(root)

    assert restarted.reconciliation.orphan_objects_quarantined == 1
    assert not list((root / "objects").iterdir())
    evidence = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (root / ".quarantine").glob("*.json")
    ]
    assert [item["reason"] for item in evidence] == ["unreferenced-object-valid"]


def test_startup_fails_closed_for_missing_registered_object(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"
    store = SnapshotStore(root)
    stored = store.register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )
    object_root = root / "objects" / stored.tree_sha256
    object_root.chmod(0o700)
    for path in object_root.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    shutil.rmtree(object_root)

    with pytest.raises(SnapshotStoreCorruptionError, match="missing or corrupt"):
        SnapshotStore(root)
    report = json.loads((root / "reconciliation.json").read_text(encoding="utf-8"))
    assert report["blocking_references"] == 1


def test_startup_quarantines_corrupt_registered_object_and_blocks(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"
    store = SnapshotStore(root)
    stored = store.register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )
    object_root = root / "objects" / stored.tree_sha256
    target = object_root / "tree" / "main.py"
    target.chmod(0o600)
    target.write_bytes(b"corrupt\n")

    with pytest.raises(SnapshotStoreCorruptionError, match="missing or corrupt"):
        SnapshotStore(root)

    assert not object_root.exists()
    evidence = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (root / ".quarantine").glob("*.json")
    ]
    assert [item["reason"] for item in evidence] == ["referenced-object-corrupt"]


def test_startup_does_not_silently_recreate_a_lost_registration_database(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshots"
    store = SnapshotStore(root)
    store.register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )
    (root / "registrations.sqlite3").unlink()

    with pytest.raises(SnapshotStoreCorruptionError, match="database is missing"):
        SnapshotStore(root)


def test_restart_reconciles_crash_after_object_publication(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"

    def checkpoint(name: str) -> None:
        if name == "object_renamed":
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        SnapshotStore(root, checkpoint=checkpoint).register(
            archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
        )

    restarted = SnapshotStore(root)
    assert restarted.reconciliation.orphan_objects_quarantined == 1
    assert not list((root / "objects").iterdir())
    assert not list((root / ".staging").iterdir())


def test_restart_preserves_registration_after_commit_checkpoint_crash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshots"

    def checkpoint(name: str) -> None:
        if name == "after_registration_commit":
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        SnapshotStore(root, checkpoint=checkpoint).register(
            archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
        )
    with sqlite3.connect(root / "registrations.sqlite3") as connection:
        snapshot_ref = connection.execute(
            "SELECT snapshot_ref FROM snapshot_registrations"
        ).fetchone()[0]

    restarted = SnapshotStore(root)
    assert restarted.resolve(
        uuid.UUID(snapshot_ref), owner_worker_id="worker-a"
    ).root.is_dir()


def test_sigkill_after_publish_leaves_no_active_orphan(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"
    archive_path = tmp_path / "snapshot.tar.gz"
    archive_path.write_bytes(archive([("main.py", b"pass\n", 0o644)]))
    script = """
import os
import sys
from pathlib import Path
from ai_enterprise.infrastructure.execution_broker.store import SnapshotStore

def checkpoint(name):
    if name == "object_renamed":
        os.kill(os.getpid(), 9)

SnapshotStore(Path(sys.argv[1]), checkpoint=checkpoint).register(
    Path(sys.argv[2]).read_bytes(), owner_worker_id="worker-a"
)
"""

    result = subprocess.run(
        [sys.executable, "-c", script, str(root), str(archive_path)], check=False
    )

    assert result.returncode == -9
    restarted = SnapshotStore(root)
    assert not list((root / "objects").iterdir())
    assert not list((root / ".staging").iterdir())
    assert (
        restarted.reconciliation.orphan_objects_quarantined
        + restarted.reconciliation.stale_staging_quarantined
        == 1
    )


def test_restart_finalizes_quarantine_intent_after_evidence_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "snapshots"
    SnapshotStore(root)
    partial = root / ".staging" / "interrupted.partial"
    partial.mkdir()
    original = store_module._write_atomic_json

    def crash_during_finalize(path: Path, value: dict[str, object]) -> None:
        if path.parent.name == ".quarantine" and value.get("state") == "quarantined":
            raise SimulatedCrash
        original(path, value)

    monkeypatch.setattr(store_module, "_write_atomic_json", crash_during_finalize)
    with pytest.raises(SimulatedCrash):
        SnapshotStore(root)
    monkeypatch.setattr(store_module, "_write_atomic_json", original)

    restarted = SnapshotStore(root)
    assert not list((root / ".staging").iterdir())
    evidence = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (root / ".quarantine").glob("*.json")
    ]
    assert [item["state"] for item in evidence] == ["quarantined"]
    assert restarted.reconciliation.blocking_references == 0


@pytest.mark.parametrize(
    ("column", "value"),
    [("archive_sha256", "invalid"), ("file_count", 99), ("expanded_bytes", 99)],
)
def test_startup_rejects_tampered_registration_evidence(
    tmp_path: Path, column: str, value: str | int
) -> None:
    root = tmp_path / "snapshots"
    store = SnapshotStore(root)
    stored = store.register(
        archive([("main.py", b"pass\n", 0o644)]), owner_worker_id="worker-a"
    )
    with sqlite3.connect(root / "registrations.sqlite3") as connection:
        connection.execute(
            f"UPDATE snapshot_registrations SET {column} = ? WHERE snapshot_ref = ?",
            (value, str(stored.snapshot_ref)),
        )

    with pytest.raises(SnapshotStoreCorruptionError):
        SnapshotStore(root)
