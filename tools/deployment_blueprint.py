#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

DEPLOYMENT_BLUEPRINT_SCHEMA_REF = (
    "schemas/production-readiness/deployment-blueprint-report.schema.json"
)


def _present(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
    }


def build_blueprint(root: Path) -> dict[str, Any]:
    artifacts = {
        "server_env_template": _present(root / ".env.server.example"),
        "server_compose_profile": _present(root / "docker-compose.server.example.yml"),
        "reverse_proxy_tls": _present(root / "docker/reverse-proxy/nginx.conf.example"),
        "prometheus_config": _present(root / "docker/observability/prometheus.yml"),
        "prometheus_alerts": _present(root / "docker/observability/alert_rules.yml"),
        "grafana_dashboard": _present(
            root / "docker/observability/grafana/dashboards/ai-enterprise-overview.json"
        ),
        "backup_timer": _present(root / "deploy/systemd/ai-enterprise-backup.timer"),
        "backup_service": _present(root / "deploy/systemd/ai-enterprise-backup.service"),
        "kubernetes_api": _present(root / "deploy/kubernetes/api-deployment.yaml"),
        "kubernetes_worker": _present(root / "deploy/kubernetes/worker-deployment.yaml"),
    }
    phases = [
        {
            "phase": 1,
            "name": "Stabilize local truth",
            "gate": (
                "Dashboard reads the official manager read model and problem jobs are "
                "resolved or acknowledged."
            ),
            "proof": ["/api/v1/query/dashboard-manager", "/dashboard/server-readiness"],
        },
        {
            "phase": 2,
            "name": "Create server profile",
            "gate": (
                "Server compose and .env.server template remove laptop paths and "
                "placeholder runtime assumptions."
            ),
            "proof": ["make server-readiness-template", "docker-compose.server.example.yml"],
        },
        {
            "phase": 3,
            "name": "Single server deployment",
            "gate": (
                "API, worker, Postgres, volumes, reverse proxy, TLS, and trusted "
                "identity headers are configured."
            ),
            "proof": ["make server-readiness", "tools/sign_proxy_assertion.py"],
        },
        {
            "phase": 4,
            "name": "Production observability",
            "gate": (
                "Prometheus, Grafana, alerts, backups, and model endpoint verification "
                "are operational."
            ),
            "proof": ["make observability-check", "make backup-verify", "make model-verify"],
        },
        {
            "phase": 5,
            "name": "Scalable factory",
            "gate": (
                "Managed database, object storage, durable workspaces, and horizontally "
                "scalable workers are chosen."
            ),
            "proof": ["MANAGED_POSTGRES_URL", "OBJECT_STORAGE_BUCKET", "deploy/kubernetes"],
        },
        {
            "phase": 6,
            "name": "Production multiserver deployment",
            "gate": (
                "Kubernetes or separate worker nodes run API and worker pools with "
                "shared observability and backup controls."
            ),
            "proof": [
                "deploy/kubernetes/api-deployment.yaml",
                "deploy/kubernetes/worker-deployment.yaml",
            ],
        },
    ]
    missing = [name for name, item in artifacts.items() if not item["exists"]]
    report = {
        "name": "AI Enterprise Deployment Blueprint",
        "status": "ready" if not missing else "needs_setup",
        "business_meaning": (
            "The migration path is reusable as an enterprise installation pattern."
            if not missing
            else (
                "The migration pattern is not complete because some deployment "
                "artifacts are missing."
            )
        ),
        "next_action": (
            "Choose real provider values, generate .env.server, and run the server-readiness gate."
            if not missing
            else f"Create missing artifacts: {', '.join(missing)}."
        ),
        "phases": phases,
        "artifacts": artifacts,
        "missing": missing,
        "schema_version": "1.0",
        "schema_ref": DEPLOYMENT_BLUEPRINT_SCHEMA_REF,
    }
    _validate_report(report)
    return report


def _schema() -> dict[str, Any]:
    for candidate in Path(__file__).resolve().parents:
        schema_path = candidate / DEPLOYMENT_BLUEPRINT_SCHEMA_REF
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return schema
    raise RuntimeError(f"{DEPLOYMENT_BLUEPRINT_SCHEMA_REF} schema file is missing")


def _validate_report(report: dict[str, Any]) -> None:
    try:
        jsonschema.validate(report, _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{DEPLOYMENT_BLUEPRINT_SCHEMA_REF}: generated deployment blueprint report "
            f"does not validate: {exc.message}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the reusable AI Enterprise deployment blueprint."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_blueprint(Path(args.root).resolve())
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text if args.json or not args.output else f"Wrote {args.output}")
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
