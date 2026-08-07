#!/usr/bin/env python3
from __future__ import annotations

# ruff: noqa: I001

import argparse
import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
API_SRC = REPO_ROOT / "apps/api/src"
for import_path in (str(TOOLS_ROOT), str(API_SRC)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

_config_module = importlib.import_module("ai_enterprise.config")
_enums_module = importlib.import_module("ai_enterprise.domain.enums")
_profiles_module = importlib.import_module("ai_enterprise.infrastructure.jobs.profiles")
_readiness_module = importlib.import_module("ai_enterprise.infrastructure.jobs.readiness")
_local_executor_module = importlib.import_module("configure_local_executor")

Settings = _config_module.Settings
get_settings = _config_module.get_settings
JobType = _enums_module.JobType
WorkerProfile = _profiles_module.WorkerProfile
allowed_job_types = _profiles_module.allowed_job_types
assess_worker_readiness = _readiness_module.assess_worker_readiness
local_executor_configuration = _local_executor_module.local_executor_configuration

EXECUTOR_JOB_TYPES = frozenset({JobType.EXECUTE_WORK_PACKAGE, JobType.REVIEW_CANDIDATE_PATCH})
LOCAL_EXECUTOR_WORKER_SCHEMA_REF = (
    "schemas/production-readiness/local-executor-worker-report.schema.json"
)


def activation_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    config = local_executor_configuration()
    env.update(
        {
            "EXECUTION_CONTAINER_PROVIDER": "restricted-local-docker",
            "EXECUTION_IMAGE": config.execution_image,
            "EXECUTION_IMAGE_ID": config.execution_image_id,
            "REVIEW_IMAGE": config.review_image,
            "REVIEW_IMAGE_ID": config.review_image_id,
            "WORKER_PROFILE": WorkerProfile.GENERAL.value,
        }
    )
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(API_SRC) if not python_path else f"{API_SRC}{os.pathsep}{python_path}"
    return env


async def readiness_report(
    env: dict[str, str],
    *,
    scope: Literal["executor", "general"],
) -> dict[str, Any]:
    settings = Settings(
        _env_file=None,
        execution_container_provider=env["EXECUTION_CONTAINER_PROVIDER"],
        execution_image=env["EXECUTION_IMAGE"],
        execution_image_id=env["EXECUTION_IMAGE_ID"],
        review_image=env["REVIEW_IMAGE"],
        review_image_id=env["REVIEW_IMAGE_ID"],
    )
    candidates = (
        EXECUTOR_JOB_TYPES if scope == "executor" else allowed_job_types(WorkerProfile.GENERAL)
    )
    result = await assess_worker_readiness(settings, candidates)
    report = {
        "schema_version": "1.0",
        "schema_ref": LOCAL_EXECUTOR_WORKER_SCHEMA_REF,
        "ok": not result.blockers,
        "scope": scope,
        "permitted_job_types": sorted(job_type.value for job_type in result.permitted_job_types),
        "blockers": [
            {
                "code": blocker.code,
                "capability": blocker.capability,
                "job_types": sorted(job_type.value for job_type in blocker.job_types),
                "detail": blocker.detail,
                "next_action": blocker.next_action,
            }
            for blocker in result.blockers
        ],
    }
    _validate_report(report)
    return report


def _schema() -> dict[str, Any]:
    for candidate in Path(__file__).resolve().parents:
        schema_path = candidate / LOCAL_EXECUTOR_WORKER_SCHEMA_REF
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return schema
    raise RuntimeError(f"{LOCAL_EXECUTOR_WORKER_SCHEMA_REF} schema file is missing")


def _validate_report(report: dict[str, Any]) -> None:
    try:
        jsonschema.validate(report, _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{LOCAL_EXECUTOR_WORKER_SCHEMA_REF}: generated local executor worker report "
            f"does not validate: {exc.message}"
        ) from exc


def worker_command() -> list[str]:
    return [sys.executable, "-m", "ai_enterprise.worker"]


def run_worker(env: dict[str, str]) -> None:
    get_settings.cache_clear()
    os.execvpe(worker_command()[0], worker_command(), env)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight or run the approved local executor worker as a host process. "
            "This avoids mounting the host Docker socket into the compose worker."
        )
    )
    parser.add_argument(
        "--scope",
        choices=["executor", "general"],
        default="executor",
        help="Readiness scope to check before reporting or running.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Exec the host general worker after successful general readiness preflight.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    env = activation_env()
    scope: Literal["executor", "general"] = "general" if args.run else args.scope
    report = asyncio.run(readiness_report(env, scope=scope))
    report["worker_command"] = worker_command()
    report["activation_env"] = {
        key: env[key]
        for key in (
            "EXECUTION_CONTAINER_PROVIDER",
            "EXECUTION_IMAGE",
            "EXECUTION_IMAGE_ID",
            "REVIEW_IMAGE",
            "REVIEW_IMAGE_ID",
            "WORKER_PROFILE",
        )
    }
    _validate_report(report)
    if args.json or not args.run:
        print(json.dumps(report, sort_keys=True))
    if not report["ok"]:
        return 2
    if args.run:
        run_worker(env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
