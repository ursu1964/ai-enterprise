import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import jsonschema


def _repo_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "tools").is_dir():
            return candidate
    raise AssertionError("Could not locate repository root with tools directory")


def _load(name: str):
    root = _repo_root()
    if name == "release_artifact":
        _load("migration_verify")
        _load("production_readiness_contracts")
        _load("infrastructure_choices")
        _load("production_readiness")
        _load("production_evidence_plan")
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release_artifact = _load("release_artifact")
SCHEMA_DIR = _repo_root() / "schemas" / "release-artifacts"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_release_artifact_records_release_gates_and_migration_summary(tmp_path: Path) -> None:
    root = _release_root(tmp_path)

    document = release_artifact.build_artifact(root)

    assert document["schema_version"] == "1.0"
    assert document["status"] == "passed"
    assert document["release_environment"] == "non-production"
    assert document["production_readiness_contracts"] is None
    assert document["production_readiness"] is None
    assert document["production_evidence_plan"] is None
    assert document["migration_verification"]["conformant"] is True
    assert document["migration_verification"]["rollback_feasible_count"] == 2
    assert document["gate_summary"]["total"] == len(document["gates"])
    assert document["gate_summary"]["failed"] == 0
    assert document["gate_summary"]["captured_evidence_required"] == []
    assert document["gate_evidence_file"]["loaded"] is False
    assert "make check-release" in document["gate_summary"]["execution_model"]
    assert {gate["name"] for gate in document["gates"]} >= {
        "compose-check",
        "migration-check",
        "lint",
        "typecheck",
        "test",
        "docker-smoke",
        "dashboard-verify",
        "dashboard-browser-verify",
        "engineering-full",
        "etra-check",
    }
    assert all(gate["required"] is True for gate in document["gates"])
    assert all(
        gate["evidence"]["source"] == "make check-release dependency" for gate in document["gates"]
    )
    assert document["artifact_policy"]["fails_when_migration_verification_fails"] is True
    assert document["artifact_policy"]["fails_when_required_gate_evidence_missing"] is True
    assert document["artifact_policy"]["fails_when_gate_evidence_commit_mismatch"] is True
    assert len(document["artifact_hash"]) == 64
    jsonschema.validate(document, _schema("release-verification.schema.json"))

    markdown = release_artifact.render_markdown(document)
    assert "# Release Verification Artifact" in markdown
    assert "Environment: `non-production`" in markdown
    assert "Not a production artifact" in markdown


def test_release_artifact_fails_closed_for_dirty_git_tree(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    (root / ".gitignore").write_text("artifacts/\n# dirty change\n", encoding="utf-8")

    document = release_artifact.build_artifact(root)

    assert document["status"] == "failed"
    assert document["git"]["dirty"] is True
    assert document["artifact_policy"]["fails_when_git_is_dirty_or_unknown"] is True


def test_release_artifact_rejects_evidence_tree_mismatch(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    evidence_file = root / "artifacts" / "gate-evidence.json"
    evidence_file.parent.mkdir()
    evidence = _evidence_document(root, {"lint": {"status": "passed"}})
    evidence_git = evidence["git"]
    assert isinstance(evidence_git, dict)
    evidence_git["tree"] = "0" * 40
    evidence_file.write_text(json_document(evidence), encoding="utf-8")

    document = release_artifact.build_artifact(
        root, evidence_file=evidence_file, require_evidence_for=("lint",)
    )

    assert document["status"] == "failed"
    assert document["gate_evidence_file"]["tree_matches_current"] is False


def test_production_release_fails_closed_without_readiness_evidence(tmp_path: Path) -> None:
    root = _release_root(tmp_path)

    document = release_artifact.build_artifact(root, production=True)

    assert document["status"] == "failed"
    assert document["release_environment"] == "production"
    assert document["production_readiness_contracts"]["conformant"] is False
    assert document["production_readiness"]["production_allowed"] is False
    assert document["production_evidence_plan"]["production_allowed"] is False
    assert document["production_evidence_plan"]["status"] == "blocked"
    assert document["artifact_policy"]["fails_when_production_readiness_contracts_invalid"] is True
    assert document["artifact_policy"]["fails_when_production_readiness_is_blocked"] is True
    assert document["artifact_policy"]["records_production_readiness_contracts"] is True
    assert document["artifact_policy"]["records_production_evidence_plan"] is True


def test_production_release_records_valid_contracts_even_when_semantics_block(
    tmp_path: Path,
) -> None:
    root = _release_root(tmp_path)
    _write_production_contract_files(root)

    document = release_artifact.build_artifact(root, production=True)

    assert document["status"] == "failed"
    assert document["production_readiness_contracts"]["conformant"] is True
    assert document["production_readiness"]["production_allowed"] is False
    assert any(
        item.endswith("status must be passed")
        for item in document["production_readiness"]["findings"]
    )

    markdown = release_artifact.render_markdown(document)
    assert "Environment: `production`" in markdown
    assert "Structural contracts: `valid`" in markdown
    assert "Semantic readiness: `blocked`" in markdown


def test_release_artifact_fails_when_migration_verification_fails(tmp_path: Path) -> None:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    _migration(versions / "one.py", "one", None)
    _migration(versions / "two.py", "two", "missing")

    document = release_artifact.build_artifact(tmp_path)

    assert document["status"] == "failed"
    assert document["gate_summary"]["failed"] == len(document["gates"])
    assert document["migration_verification"]["conformant"] is False
    assert any(
        "dangling down_revision" in finding
        for finding in document["migration_verification"]["findings"]
    )


def test_release_artifact_merges_supplied_gate_evidence(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    evidence_file = root / "artifacts" / "gate-evidence.json"
    evidence_file.parent.mkdir()
    evidence_file.write_text(
        json_document(
            _evidence_document(
                root,
                {
                    "docker-smoke": {"status": "passed", "duration_seconds": 12.5},
                    "engineering-full": {"status": "failed", "duration_seconds": 1.2},
                },
                status="failed",
            )
        ),
        encoding="utf-8",
    )

    document = release_artifact.build_artifact(root, evidence_file=evidence_file)
    gates = {gate["name"]: gate for gate in document["gates"]}

    assert document["status"] == "failed"
    assert document["gate_summary"]["failed"] == 1
    assert gates["docker-smoke"]["status"] == "passed"
    assert gates["docker-smoke"]["evidence"]["duration_seconds"] == 12.5
    assert gates["engineering-full"]["status"] == "failed"


def test_release_artifact_fails_when_required_captured_evidence_is_missing(
    tmp_path: Path,
) -> None:
    root = _release_root(tmp_path)
    evidence_file = root / "artifacts" / "gate-evidence.json"
    evidence_file.parent.mkdir()
    evidence_file.write_text(
        json_document(_evidence_document(root, {"lint": {"status": "passed", "return_code": 0}})),
        encoding="utf-8",
    )

    document = release_artifact.build_artifact(
        root,
        evidence_file=evidence_file,
        require_evidence_for=("lint", "typecheck", "test"),
    )
    gates = {gate["name"]: gate for gate in document["gates"]}

    assert document["status"] == "failed"
    assert document["gate_summary"]["captured_evidence_required"] == [
        "lint",
        "test",
        "typecheck",
    ]
    assert document["gate_summary"]["captured_evidence_missing"] == [
        "typecheck",
        "test",
    ]
    assert document["gate_evidence_file"]["missing_required_gates"] == [
        "typecheck",
        "test",
    ]
    assert gates["lint"]["status"] == "passed"
    assert gates["typecheck"]["status"] == "failed"
    assert gates["typecheck"]["evidence"]["missing_required_evidence"] is True


def test_release_artifact_passes_when_all_release_gate_evidence_is_present(
    tmp_path: Path,
) -> None:
    root = _release_root(tmp_path)
    evidence_file = root / "artifacts" / "gate-evidence.json"
    evidence_file.parent.mkdir()
    required = (
        "compose-check",
        "migration-check",
        "lint",
        "typecheck",
        "test",
        "secret-scan",
        "docker-smoke",
        "architecture-baseline-manifest",
        "dashboard-verify",
        "engineering-static",
        "evolution-check",
        "federation-check",
        "intelligence-check",
        "engineering-full",
        "etra-check",
    )
    evidence_file.write_text(
        json_document(
            _evidence_document(
                root,
                {name: {"status": "passed", "return_code": 0} for name in required},
            )
        ),
        encoding="utf-8",
    )

    document = release_artifact.build_artifact(
        root,
        evidence_file=evidence_file,
        require_evidence_for=required,
    )
    gates = {gate["name"]: gate for gate in document["gates"]}

    assert document["status"] == "passed"
    assert document["gate_summary"]["captured_evidence_missing"] == []
    assert document["gate_summary"]["captured_evidence_required"] == sorted(required)
    assert all(gates[name]["evidence_required"] is True for name in required)
    assert all(gates[name]["evidence"]["missing_required_evidence"] is False for name in required)


def test_release_artifact_writes_json_file(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    output = Path("artifacts/release-verification.json")
    markdown_output = Path("artifacts/release-verification.md")

    document = release_artifact.write_artifact(root, output, markdown_output=markdown_output)

    written = root / output
    markdown = root / markdown_output
    assert written.exists()
    assert markdown.exists()
    assert document["artifact_policy"]["archive_path"] == str(output)
    assert "release-verification" in written.name
    assert "# Release Verification Artifact" in markdown.read_text(encoding="utf-8")

    verification = release_artifact.verify_markdown_summary(written, markdown)
    assert verification["valid"] is True
    assert verification["stored_artifact_hash"] == document["artifact_hash"]
    jsonschema.validate(verification, _schema("release-verification-check.schema.json"))


def test_release_artifact_build_fails_closed_when_schema_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _release_root(tmp_path)
    original_schema = release_artifact._schema

    def stricter_schema(name: str) -> dict:
        schema = original_schema(name)
        if name == "release-verification.schema.json":
            schema = {**schema, "required": [*schema["required"], "impossible_field"]}
        return schema

    monkeypatch.setattr(release_artifact, "_schema", stricter_schema)

    try:
        release_artifact.build_artifact(root)
    except RuntimeError as exc:
        assert "release-verification.schema.json" in str(exc)
        assert "generated document does not validate" in str(exc)
    else:
        raise AssertionError("invalid release artifact schema output was accepted")


def test_release_artifact_markdown_verification_fails_closed_when_schema_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _release_root(tmp_path)
    output = Path("artifacts/release-verification.json")
    markdown_output = Path("artifacts/release-verification.md")
    release_artifact.write_artifact(root, output, markdown_output=markdown_output)
    original_schema = release_artifact._schema

    def stricter_schema(name: str) -> dict:
        schema = original_schema(name)
        if name == "release-verification-check.schema.json":
            schema = {**schema, "required": [*schema["required"], "impossible_field"]}
        return schema

    monkeypatch.setattr(release_artifact, "_schema", stricter_schema)

    try:
        release_artifact.verify_markdown_summary(root / output, root / markdown_output)
    except RuntimeError as exc:
        assert "release-verification-check.schema.json" in str(exc)
        assert "generated document does not validate" in str(exc)
    else:
        raise AssertionError("invalid release verification check output was accepted")


def test_release_artifact_markdown_verification_detects_stale_summary(
    tmp_path: Path,
) -> None:
    root = _release_root(tmp_path)
    output = Path("artifacts/release-verification.json")
    markdown_output = Path("artifacts/release-verification.md")
    release_artifact.write_artifact(root, output, markdown_output=markdown_output)
    markdown = root / markdown_output
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace("Artifact hash:", "Old hash:"),
        encoding="utf-8",
    )

    verification = release_artifact.verify_markdown_summary(root / output, markdown)

    assert verification["valid"] is False
    assert "markdown: artifact hash reference is missing or stale" in verification["findings"]


def test_release_artifact_markdown_verification_detects_tampered_json(
    tmp_path: Path,
) -> None:
    root = _release_root(tmp_path)
    output = Path("artifacts/release-verification.json")
    markdown_output = Path("artifacts/release-verification.md")
    release_artifact.write_artifact(root, output, markdown_output=markdown_output)
    written = root / output
    payload = release_artifact.json.loads(written.read_text(encoding="utf-8"))
    payload["status"] = "failed" if payload["status"] == "passed" else "passed"
    written.write_text(json_document(payload), encoding="utf-8")

    verification = release_artifact.verify_markdown_summary(written, root / markdown_output)

    assert verification["valid"] is False
    assert "artifact_hash: stored hash does not match JSON content" in verification["findings"]


def test_release_artifact_cli_verification_report_can_be_written(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    output = root / "artifacts" / "release-verification.json"
    markdown_output = root / "artifacts" / "release-verification.md"
    report_output = root / "artifacts" / "release-verification-check.json"
    release_artifact.write_artifact(root, output, markdown_output=markdown_output)
    report = release_artifact.verify_markdown_summary(output, markdown_output)
    report_output.write_text(json_document(report), encoding="utf-8")

    loaded = release_artifact.json.loads(report_output.read_text(encoding="utf-8"))
    assert loaded["valid"] is True
    assert loaded["stored_artifact_hash"] == report["stored_artifact_hash"]


def test_release_artifact_records_actual_archive_path(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    output = Path("artifacts/production-release-verification.json")

    document = release_artifact.write_artifact(root, output, production=True)

    assert document["status"] == "failed"
    assert document["release_environment"] == "production"
    assert document["artifact_policy"]["archive_path"] == str(output)
    assert (root / output).exists()


def json_document(value: object) -> str:
    import json

    return json.dumps(value, indent=2, sort_keys=True)


def _release_root(tmp_path: Path) -> Path:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    _migration(versions / "one.py", "one", None)
    _migration(versions / "two.py", "two", "one")
    (tmp_path / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    _init_git(tmp_path)
    return tmp_path


def _write_production_contract_files(root: Path) -> None:
    enterprise = root / "docs" / "enterprise"
    enterprise.mkdir(parents=True)
    (enterprise / "real-world-infrastructure-decisions.json").write_text(
        json_document(
            {
                "domain_tls": {
                    "domain": "prod.example.test",
                    "tls_provider": "managed-load-balancer",
                    "certificate_owner": "platform-team",
                    "renewal_proof": "ticket://tls-renewal",
                },
                "identity_proxy": {
                    "provider": "custom",
                    "signature_owner": "identity-team",
                    "hmac_secret_source": "secret-ref://proxy/hmac",
                    "signed_headers": [
                        "X-Actor-ID",
                        "X-Actor-Type",
                        "X-Actor-Role",
                        "X-Proxy-Timestamp",
                        "X-Proxy-Signature",
                    ],
                },
                "model_service": {
                    "provider": "managed-provider",
                    "base_url": "https://model.example.test",
                    "model": "prod-model",
                    "capacity_owner": "ai-platform",
                    "verification_command": "rtk make model-verify",
                },
                "github_access": {
                    "mode": "github-app",
                    "organization": "real-org",
                    "repository_policy": "per-project",
                    "secret_source": "secret-ref://github/app",
                },
                "database": {
                    "mode": "managed-postgres",
                    "connection_secret": "secret-ref://db/url",
                    "backup_policy": "daily-with-restore-drill",
                    "restore_drill_frequency": "monthly",
                },
                "object_storage": {
                    "provider": "s3",
                    "bucket": "prod-artifacts",
                    "region": "eu-central-1",
                    "encryption": "kms",
                    "retention_policy": "90-days",
                },
                "kubernetes": {
                    "enabled": True,
                    "registry": "registry.example.test/ai-enterprise",
                    "namespace": "ai-enterprise",
                    "ingress_class": "nginx",
                    "storage_class": "fast-ssd",
                    "worker_replicas": 3,
                },
                "backup_restore": {
                    "schedule_owner": "platform-team",
                    "backup_timer": "ai-enterprise-backup.timer",
                    "last_restore_drill": "2026-08-01",
                    "restore_drill_evidence": "ticket://restore-drill",
                },
                "notification": {
                    "alert_channel": "pagerduty",
                    "oncall_owner": "platform-oncall",
                    "escalation_policy": "ticket://escalation-policy",
                },
            }
        ),
        encoding="utf-8",
    )
    proof = {}
    required = release_artifact.production_readiness.REQUIRED_PROOF
    for name, fields in required.items():
        item = {
            "status": "pending",
            "checked_at": "2026-08-01T00:00:00Z",
            "valid_until": "2026-09-01T00:00:00Z",
            "evidence": f"ticket://{name}",
        }
        for field in fields:
            item[field] = (
                True
                if field.endswith(("verified", "passed", "reviewed", "absent"))
                else f"ref://{field}"
            )
        proof[name] = item
    (enterprise / "production-readiness-evidence.json").write_text(
        json_document(
            {"environment": "production", "reviewed_by": "release-owner", "proof": proof}
        ),
        encoding="utf-8",
    )


def _init_git(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Release Test",
            "-c",
            "user.email=release@example.test",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
        check=True,
    )


def _evidence_document(
    root: Path, gates: dict[str, object], *, status: str = "passed"
) -> dict[str, object]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    return {
        "status": status,
        "provenance_valid": True,
        "git": {"commit": commit, "tree": tree, "branch": "main", "dirty": False},
        "gates": gates,
    }


def _migration(path: Path, revision: str, down_revision: str | None) -> None:
    path.write_text(
        f'revision = "{revision}"\n'
        f"down_revision = {down_revision!r}\n"
        "def upgrade():\n"
        "    op.create_table('example')\n"
        "def downgrade():\n"
        "    op.drop_table('example')\n",
        encoding="utf-8",
    )
