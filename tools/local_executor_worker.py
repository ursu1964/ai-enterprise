#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
API_SRC = REPO_ROOT / "apps/api/src"
for import_path in (str(TOOLS_ROOT), str(API_SRC)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from configure_local_executor import local_executor_configuration  # noqa: E402

from ai_enterprise.config import Settings, get_settings  # noqa: E402
from ai_enterprise.domain.enums import JobType  # noqa: E402
from ai_enterprise.infrastructure.jobs.profiles import (  # noqa: E402
    WorkerProfile,
    allowed_job_types,
)
from ai_enterprise.infrastructure.jobs.readiness import assess_worker_readiness  # noqa: E402

EXECUTOR_JOB_TYPES = frozenset(
    {JobType.EXECUTE_WORK_PACKAGE, JobType.REVIEW_CANDIDATE_PATCH}
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
    env["PYTHONPATH"] = (
        str(API_SRC) if not python_path else f"{API_SRC}{os.pathsep}{python_path}"
    )
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
        EXECUTOR_JOB_TYPES
        if scope == "executor"
        else allowed_job_types(WorkerProfile.GENERAL)
    )
    result = await assess_worker_readiness(settings, candidates)
    return {
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
    if args.json or not args.run:
        print(json.dumps(report, sort_keys=True))
    if not report["ok"]:
        return 2
    if args.run:
        run_worker(env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
