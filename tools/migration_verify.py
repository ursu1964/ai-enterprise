#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

import jsonschema

MIGRATION_GRAPH_SCHEMA_REF = "schemas/release-artifacts/migration-graph-report.schema.json"
SERVER_READINESS_SCHEMA_REF = "schemas/production-readiness/server-readiness-report.schema.json"


class MigrationFinding(Exception):
    pass


def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple):
        return tuple(_literal(item) for item in node.elts)
    if isinstance(node, ast.List):
        return [_literal(item) for item in node.elts]
    return None


def _assigned_literal(module: ast.Module, name: str) -> Any:
    for statement in module.body:
        target: ast.expr | None = None
        value: ast.AST | None = None
        if isinstance(statement, ast.Assign):
            target = statement.targets[0] if statement.targets else None
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value = statement.value
        if isinstance(target, ast.Name) and target.id == name and value is not None:
            return _literal(value)
    return None


def _function(module: ast.Module, name: str) -> ast.FunctionDef | None:
    return next(
        (
            statement
            for statement in module.body
            if isinstance(statement, ast.FunctionDef) and statement.name == name
        ),
        None,
    )


def _is_empty_rollback(function: ast.FunctionDef | None) -> bool:
    if function is None:
        return True
    body = [
        statement
        for statement in function.body
        if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
    ]
    if not body:
        return True
    if all(isinstance(statement, ast.Pass) for statement in body):
        return True
    for statement in body:
        if isinstance(statement, ast.Raise):
            return True
    return False


def _normalize_down_revision(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if item is not None)
    return (str(value),)


def verify(migrations_dir: Path) -> dict[str, Any]:
    findings: list[str] = []
    rows: list[dict[str, Any]] = []
    for path in sorted(migrations_dir.glob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = _assigned_literal(module, "revision")
        down_revisions = _normalize_down_revision(_assigned_literal(module, "down_revision"))
        upgrade = _function(module, "upgrade")
        downgrade = _function(module, "downgrade")
        if not isinstance(revision, str) or not revision:
            findings.append(f"{path.name}: missing revision")
            continue
        if upgrade is None:
            findings.append(f"{revision}: missing upgrade()")
        if _is_empty_rollback(downgrade):
            findings.append(f"{revision}: downgrade() is missing or not feasible")
        rows.append(
            {
                "path": str(path),
                "revision": revision,
                "down_revisions": down_revisions,
            }
        )

    revisions = {row["revision"] for row in rows}
    duplicates = sorted(
        revision for revision in revisions if sum(row["revision"] == revision for row in rows) > 1
    )
    for revision in duplicates:
        findings.append(f"duplicate revision: {revision}")

    for row in rows:
        for parent in row["down_revisions"]:
            if parent not in revisions:
                findings.append(f"{row['revision']}: dangling down_revision {parent}")

    children: dict[str, list[str]] = {revision: [] for revision in revisions}
    for row in rows:
        for parent in row["down_revisions"]:
            if parent in children:
                children[parent].append(row["revision"])
    bases = sorted(row["revision"] for row in rows if not row["down_revisions"])
    heads = sorted(revision for revision, values in children.items() if not values)
    if len(bases) != 1:
        findings.append(f"expected exactly one base revision, found {len(bases)}")
    if len(heads) != 1:
        findings.append(f"expected exactly one head revision, found {len(heads)}")

    visited: set[str] = set()
    visiting: set[str] = set()
    parent_map = {
        row["revision"]: tuple(parent for parent in row["down_revisions"] if parent in revisions)
        for row in rows
    }

    def visit(revision: str) -> None:
        if revision in visiting:
            findings.append(f"cycle detected at revision {revision}")
            return
        if revision in visited:
            return
        visiting.add(revision)
        for parent in parent_map[revision]:
            visit(parent)
        visiting.remove(revision)
        visited.add(revision)

    for revision in sorted(revisions):
        visit(revision)

    report = {
        "schema_version": "1.0",
        "schema_ref": MIGRATION_GRAPH_SCHEMA_REF,
        "conformant": not findings,
        "migration_count": len(rows),
        "base_revisions": bases,
        "head_revisions": heads,
        "rollback_feasible_count": sum(
            1
            for row in rows
            if f"{row['revision']}: downgrade() is missing or not feasible" not in findings
        ),
        "findings": sorted(set(findings)),
    }
    _validate_report(report, MIGRATION_GRAPH_SCHEMA_REF)
    return report


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _server_check(
    checks: list[dict[str, Any]], key: str, ok: bool, message: str, action: str
) -> None:
    checks.append(
        {
            "key": key,
            "status": "pass" if ok else "fail",
            "message": message,
            "action": action,
        }
    )


def verify_server_readiness(
    *,
    root: Path,
    env_file: Path,
    compose_file: Path,
    allow_placeholders: bool = False,
) -> dict[str, Any]:
    env = _read_env(env_file)
    checks: list[dict[str, Any]] = []
    required_env = {
        "APP_ENV",
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "TRUSTED_PROXY_HMAC_SECRET",
        "OLLAMA_BASE_URL",
        "REPOSITORY_ALLOWED_ROOT",
        "AI_ENTERPRISE_WORKSPACE_ROOT",
        "AI_ENTERPRISE_ARTIFACT_ROOT",
        "AI_ENTERPRISE_RUNTIME_ROOT",
    }
    missing = sorted(key for key in required_env if not env.get(key))
    placeholders = sorted(
        key
        for key, value in env.items()
        if "change-me" in value.lower() or "absolute/path" in value.lower()
    )
    storage_roots = [
        env.get("AI_ENTERPRISE_WORKSPACE_ROOT", ""),
        env.get("AI_ENTERPRISE_ARTIFACT_ROOT", ""),
        env.get("AI_ENTERPRISE_RUNTIME_ROOT", ""),
    ]
    server_compose = compose_file.read_text(encoding="utf-8") if compose_file.exists() else ""
    local_compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    observability_compose = root / "docker-compose.observability.yml"
    prometheus_config = root / "docker/observability/prometheus.yml"
    prometheus_alerts = root / "docker/observability/alert_rules.yml"
    grafana_dashboard = root / "docker/observability/grafana/dashboards/ai-enterprise-overview.json"
    reverse_proxy_config = root / "docker/reverse-proxy/nginx.conf.example"
    backup_verify = root / "tools/backup_verify.py"
    secret_generator = root / "tools/generate_server_secrets.py"
    proxy_signer = root / "tools/sign_proxy_assertion.py"
    model_verifier = root / "tools/model_endpoint_verify.py"
    deployment_blueprint = root / "tools/deployment_blueprint.py"
    deployment_blueprint_doc = root / "docs/enterprise/deployment-blueprint-module.md"
    infrastructure_choices = root / "tools/infrastructure_choices.py"
    infrastructure_choices_template = (
        root / "docs/enterprise/real-world-infrastructure-decisions.template.json"
    )
    backup_timer = root / "deploy/systemd/ai-enterprise-backup.timer"
    backup_service = root / "deploy/systemd/ai-enterprise-backup.service"
    k8s_api = root / "deploy/kubernetes/api-deployment.yaml"
    k8s_worker = root / "deploy/kubernetes/worker-deployment.yaml"
    alembic_ini = root / "apps/api/alembic.ini"
    migrations_dir = root / "migrations/versions"

    _server_check(
        checks,
        "server_env_file",
        env_file.exists(),
        f"Server environment file found at {env_file}.",
        "Create .env.server from .env.server.example before deployment.",
    )
    _server_check(
        checks,
        "server_compose_file",
        compose_file.exists(),
        f"Server compose file found at {compose_file}.",
        "Use docker-compose.server.example.yml as the server deployment starting point.",
    )
    _server_check(
        checks,
        "required_environment",
        not missing,
        "Required server environment variables are present.",
        "All required server variables are present."
        if not missing
        else f"Set missing variables: {', '.join(missing)}.",
    )
    _server_check(
        checks,
        "production_environment",
        env.get("APP_ENV") == "production",
        "APP_ENV is set to production.",
        "Set APP_ENV=production for server deployment.",
    )
    _server_check(
        checks,
        "secret_placeholders",
        allow_placeholders or not placeholders,
        "No placeholder secrets remain.",
        "Template placeholders are allowed for this verification."
        if allow_placeholders and placeholders
        else "No placeholder values were found."
        if not placeholders
        else f"Replace placeholder values for: {', '.join(placeholders)}.",
    )
    _server_check(
        checks,
        "trusted_proxy",
        len(env.get("TRUSTED_PROXY_HMAC_SECRET", "")) >= 32
        and (allow_placeholders or "change-me" not in env.get("TRUSTED_PROXY_HMAC_SECRET", "")),
        "Trusted proxy HMAC secret is configured.",
        "Generate a long random TRUSTED_PROXY_HMAC_SECRET and configure the reverse proxy.",
    )
    _server_check(
        checks,
        "server_storage_roots",
        all(value.startswith("/") for value in storage_roots)
        and not any(value.startswith("/home/user") for value in storage_roots),
        "Server storage roots are absolute and not laptop user paths.",
        "Use durable server paths such as /srv/ai-enterprise/workspaces.",
    )
    _server_check(
        checks,
        "model_service",
        bool(env.get("OLLAMA_BASE_URL"))
        and "host.docker.internal" not in env.get("OLLAMA_BASE_URL", ""),
        "Model service URL is server-oriented.",
        "Use an internal Ollama/GPU service URL or managed model bridge.",
    )
    _server_check(
        checks,
        "server_compose_no_laptop_paths",
        "/home/user/projects" not in server_compose
        and "host.docker.internal" not in server_compose,
        "Server compose file does not depend on laptop paths or host gateway model access.",
        "Keep laptop-only assumptions in docker-compose.yml, not the server profile.",
    )
    _server_check(
        checks,
        "local_compose_preserved",
        "127.0.0.1:8000:8000" in local_compose and "/home/user/projects" in local_compose,
        "Local compose remains laptop-safe and unchanged for development.",
        "Do not expose the local compose directly on a public server.",
    )
    _server_check(
        checks,
        "backup_verifier",
        backup_verify.exists(),
        "Backup verification command is available.",
        "Add tools/backup_verify.py before scheduling server backups.",
    )
    _server_check(
        checks,
        "migration_gate",
        alembic_ini.exists() and migrations_dir.exists(),
        "Database migration gate is available.",
        "Keep Alembic migration verification in the server deployment path.",
    )
    _server_check(
        checks,
        "observability_stack",
        observability_compose.exists()
        and prometheus_config.exists()
        and grafana_dashboard.exists(),
        "Prometheus and Grafana templates are available.",
        "Add observability compose, Prometheus scrape config, and Grafana dashboard provisioning.",
    )
    _server_check(
        checks,
        "observability_alerts",
        prometheus_alerts.exists(),
        "Prometheus alert rules are available.",
        "Add API, worker heartbeat, job failure, and model-service alert rules before production.",
    )
    _server_check(
        checks,
        "reverse_proxy_template",
        reverse_proxy_config.exists(),
        "Reverse proxy TLS template is available.",
        "Add an HTTPS reverse proxy template with trusted identity header guidance.",
    )
    _server_check(
        checks,
        "secret_generation",
        secret_generator.exists(),
        "Server secret generation helper is available.",
        "Add tools/generate_server_secrets.py so operators do not hand-write secrets.",
    )
    _server_check(
        checks,
        "proxy_signature_helper",
        proxy_signer.exists(),
        "Trusted proxy signature helper is available.",
        "Add tools/sign_proxy_assertion.py to test X-Proxy-Signature generation.",
    )
    _server_check(
        checks,
        "model_endpoint_verifier",
        model_verifier.exists(),
        "Model endpoint verification helper is available.",
        "Add tools/model_endpoint_verify.py before changing production model endpoints.",
    )
    _server_check(
        checks,
        "github_access_hooks",
        all(
            key in env
            for key in (
                "LOCAL_GIT_REMOTE_URL",
                "GITHUB_INTEGRATION_MODE",
                "GITHUB_APP_ID",
                "GITHUB_APP_INSTALLATION_ID",
                "GITHUB_PRIVATE_KEY_PATH",
                "GITHUB_TOKEN_FILE",
            )
        ),
        "GitHub and Git remote integration hooks are documented.",
        "Add GitHub App, token-file, or SSH remote variables before production project creation.",
    )
    _server_check(
        checks,
        "backup_schedule",
        backup_timer.exists() and backup_service.exists(),
        "Backup verification schedule templates are available.",
        "Add systemd timer/service templates for scheduled backup verification.",
    )
    _server_check(
        checks,
        "managed_infrastructure_hooks",
        all(
            key in env
            for key in (
                "MANAGED_POSTGRES_URL",
                "OBJECT_STORAGE_PROVIDER",
                "OBJECT_STORAGE_BUCKET",
                "OBJECT_STORAGE_REGION",
            )
        ),
        "Managed Postgres and object storage hooks are documented.",
        "Add managed database and object-storage variables to .env.server.example.",
    )
    _server_check(
        checks,
        "kubernetes_rollout_templates",
        k8s_api.exists() and k8s_worker.exists(),
        "Kubernetes API and worker rollout templates are available.",
        "Add Kubernetes deployment templates before multi-server rollout.",
    )
    _server_check(
        checks,
        "deployment_blueprint",
        deployment_blueprint.exists() and deployment_blueprint_doc.exists(),
        "Reusable deployment blueprint module is available.",
        (
            "Add the deployment blueprint generator and documentation so server migrations "
            "become reusable."
        ),
    )
    _server_check(
        checks,
        "infrastructure_choices_gate",
        infrastructure_choices.exists() and infrastructure_choices_template.exists(),
        "Real infrastructure choices gate is available.",
        "Add the infrastructure choices template and verifier before production deployment.",
    )
    failures = [item for item in checks if item["status"] == "fail"]
    report = {
        "schema_version": "1.0",
        "schema_ref": SERVER_READINESS_SCHEMA_REF,
        "conformant": not failures,
        "mode": "server_readiness",
        "env_file": str(env_file),
        "compose_file": str(compose_file),
        "allow_placeholders": allow_placeholders,
        "checks": checks,
        "findings": [f"{item['key']}: {item['action']}" for item in failures],
    }
    _validate_report(report, SERVER_READINESS_SCHEMA_REF)
    return report


def _schema(schema_ref: str) -> dict[str, Any]:
    for candidate in Path(__file__).resolve().parents:
        schema_path = candidate / schema_ref
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return schema
    raise RuntimeError(f"{schema_ref} schema file is missing")


def _validate_report(report: dict[str, Any], schema_ref: str) -> None:
    try:
        jsonschema.validate(report, _schema(schema_ref))
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{schema_ref}: generated migration verification report does not validate: "
            f"{exc.message}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Alembic migration graph integrity.")
    parser.add_argument("--migrations-dir", default="migrations/versions")
    parser.add_argument("--server-readiness", action="store_true")
    parser.add_argument("--root", default=".")
    parser.add_argument("--env-file", default=".env.server")
    parser.add_argument("--compose-file", default="docker-compose.server.example.yml")
    parser.add_argument("--allow-placeholders", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.server_readiness:
        root = Path(args.root).resolve()
        env_file = Path(args.env_file)
        if not env_file.is_absolute():
            env_file = root / env_file
        compose_file = Path(args.compose_file)
        if not compose_file.is_absolute():
            compose_file = root / compose_file
        report = verify_server_readiness(
            root=root,
            env_file=env_file,
            compose_file=compose_file,
            allow_placeholders=args.allow_placeholders,
        )
    else:
        report = verify(Path(args.migrations_dir))
    if args.json:
        print(json.dumps(report, sort_keys=True))
    elif report["conformant"]:
        if report.get("mode") == "server_readiness":
            print("Server readiness verified")
        else:
            print(f"Migration graph verified: {report['migration_count']} migration(s)")
    else:
        for finding in report["findings"]:
            print(finding)
    return 0 if report["conformant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
