#!/usr/bin/env python3
"""Start AI Enterprise and launch project workflows from manifest files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_API = "http://localhost:8000"
ENV_FILE = Path(".env")
ENV_EXAMPLE_FILE = Path(".env.example")
RUNTIME_DATA_DIR = Path("runtime-data")
DEFAULT_REPOSITORY_ALLOWED_ROOT = Path("/home/user/projects")


@dataclass(frozen=True, slots=True)
class ProjectSpec:
    name: str
    description: str
    repository_path: str
    repository_url: str | None
    default_branch: str
    start_workflow: bool
    actor_id: str


def run(command: list[str], *, dry_run: bool = False) -> None:
    print("+ " + " ".join(command), flush=True)
    if dry_run:
        return
    subprocess.run(command, check=True)


def prepare_environment(*, dry_run: bool = False) -> None:
    if ENV_FILE.exists():
        print(f"Using existing {ENV_FILE}")
    elif ENV_EXAMPLE_FILE.exists():
        run(["cp", str(ENV_EXAMPLE_FILE), str(ENV_FILE)], dry_run=dry_run)
    else:
        raise FileNotFoundError(f"Missing {ENV_EXAMPLE_FILE}; cannot create {ENV_FILE}")


def prepare_runtime_data(*, dry_run: bool = False) -> None:
    if dry_run:
        print(f"would ensure writable {RUNTIME_DATA_DIR}")
        return
    RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in [RUNTIME_DATA_DIR, *RUNTIME_DATA_DIR.rglob("*")]:
        path.chmod(path.stat().st_mode | 0o077)


def repository_allowed_root() -> Path:
    if not ENV_FILE.exists():
        return DEFAULT_REPOSITORY_ALLOWED_ROOT.resolve()
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "REPOSITORY_ALLOWED_ROOT":
            return Path(value.strip().strip("\"'")).expanduser().resolve()
    return DEFAULT_REPOSITORY_ALLOWED_ROOT.resolve()


def require_boolean(value: Any, field: str, path: Path, index: int) -> bool:
    if isinstance(value, bool):
        return value
    raise TypeError(f"{path} project #{index} {field} must be a JSON boolean")


def load_manifest(path: Path) -> list[ProjectSpec]:
    document = json.loads(path.read_text(encoding="utf-8"))
    raw_projects = document.get("projects")
    if not isinstance(raw_projects, list) or not raw_projects:
        raise ValueError(f"{path} must contain a non-empty 'projects' array")
    defaults = document.get("defaults", {})
    if not isinstance(defaults, dict):
        raise TypeError(f"{path} defaults must be an object")
    projects: list[ProjectSpec] = []
    for index, raw in enumerate(raw_projects, start=1):
        if not isinstance(raw, dict):
            raise TypeError(f"{path} project #{index} must be an object")
        merged = defaults | raw
        try:
            start_workflow = require_boolean(
                merged.get("start_workflow", True), "start_workflow", path, index
            )
            spec = ProjectSpec(
                name=str(merged["name"]),
                description=str(merged["description"]),
                repository_path=str(merged["repository_path"]),
                repository_url=(
                    None
                    if merged.get("repository_url") in {None, ""}
                    else str(merged["repository_url"])
                ),
                default_branch=str(merged.get("default_branch", "main")),
                start_workflow=start_workflow,
                actor_id=str(merged.get("actor_id", "enterprise-autostart")),
            )
        except KeyError as exc:
            raise ValueError(f"{path} project #{index} is missing {exc.args[0]!r}") from exc
        validate_project(spec, path, index)
        projects.append(spec)
    return projects


def validate_project(spec: ProjectSpec, path: Path, index: int) -> None:
    if len(spec.name) < 3:
        raise ValueError(f"{path} project #{index} name must be at least 3 characters")
    if len(spec.description) < 20:
        raise ValueError(f"{path} project #{index} description must be at least 20 characters")
    if not spec.repository_path.strip():
        raise ValueError(f"{path} project #{index} repository_path is required")
    if not spec.default_branch.strip():
        raise ValueError(f"{path} project #{index} default_branch is required")
    repository_path = Path(spec.repository_path).expanduser().resolve()
    allowed_root = repository_allowed_root()
    try:
        repository_path.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"{path} project #{index} repository_path must be under {allowed_root}"
        ) from exc


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: int = 30,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
    if not data:
        return {}
    return json.loads(data.decode("utf-8"))


def wait_ready(api_base: str, *, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            payload = request_json("GET", f"{api_base}/health/ready", timeout=5)
        except Exception as exc:  # noqa: BLE001 - surface last readiness problem
            last_error = exc
        else:
            if payload.get("status") == "ok":
                return
        time.sleep(2)
    raise TimeoutError(f"API did not become ready within {timeout_seconds}s: {last_error}")


def ensure_repository(path: str, branch: str, *, dry_run: bool = False) -> None:
    repository_path = Path(path).expanduser().resolve()
    if dry_run:
        print(f"would ensure repository {repository_path}")
        return
    repository_path.mkdir(parents=True, exist_ok=True)
    if not (repository_path / ".git").exists():
        run(["git", "-C", str(repository_path), "init", f"--initial-branch={branch}"])
    if not repository_has_head(repository_path):
        marker = repository_path / ".ai-enterprise-initialized"
        if not marker.exists():
            marker.write_text(
                "Repository initialized by AI Enterprise for governed workflow execution.\n",
                encoding="utf-8",
            )
        run(["git", "-C", str(repository_path), "add", ".ai-enterprise-initialized"])
        run(
            [
                "git",
                "-C",
                str(repository_path),
                "-c",
                "user.name=AI Enterprise",
                "-c",
                "user.email=ai-enterprise@local.invalid",
                "commit",
                "-m",
                "Initialize AI Enterprise repository",
            ]
        )


def repository_has_head(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def launch_project(api_base: str, spec: ProjectSpec, *, dry_run: bool = False) -> dict[str, Any]:
    ensure_repository(spec.repository_path, spec.default_branch, dry_run=dry_run)
    payload = {
        "name": spec.name,
        "description": spec.description,
        "repository_path": str(Path(spec.repository_path).expanduser().resolve()),
        "repository_url": spec.repository_url,
        "default_branch": spec.default_branch,
    }
    if dry_run:
        print(f"would create project {spec.name!r}: {json.dumps(payload, sort_keys=True)}")
        return {"name": spec.name, "project_id": None, "workflow_id": None}
    project = request_json("POST", f"{api_base}/api/v1/projects", payload)
    workflow = None
    if spec.start_workflow:
        workflow = request_json(
            "POST",
            f"{api_base}/api/v1/projects/{project['id']}/workflow",
            {"actor_id": spec.actor_id},
        )
    return {
        "name": spec.name,
        "project_id": project["id"],
        "workflow_id": None if workflow is None else workflow["id"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start AI Enterprise, bootstrap local state, create projects from manifest files, "
            "and start their workflows in parallel."
        )
    )
    parser.add_argument(
        "--manifest",
        action="append",
        type=Path,
        required=True,
        help="JSON manifest file. Repeat to launch multiple manifestos.",
    )
    parser.add_argument("--api-base", default=DEFAULT_API)
    parser.add_argument("--parallelism", type=int, default=4)
    parser.add_argument("--ready-timeout", type=int, default=180)
    parser.add_argument(
        "--no-env",
        action="store_true",
        help="Do not create .env from .env.example.",
    )
    parser.add_argument("--no-compose", action="store_true", help="Do not run docker compose up.")
    parser.add_argument("--no-bootstrap", action="store_true", help="Do not run local bootstrap.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.parallelism < 1:
        raise SystemExit("--parallelism must be positive")
    if not args.no_env:
        prepare_environment(dry_run=args.dry_run)
    projects = [project for path in args.manifest for project in load_manifest(path)]
    prepare_runtime_data(dry_run=args.dry_run)
    if not args.no_compose:
        run(["docker", "compose", "up", "--build", "-d"], dry_run=args.dry_run)
    if not args.no_bootstrap:
        run(
            ["docker", "compose", "--profile", "dev-bootstrap", "run", "--rm", "bootstrap"],
            dry_run=args.dry_run,
        )
    if not args.dry_run:
        wait_ready(args.api_base, timeout_seconds=args.ready_timeout)
    print(f"Launching {len(projects)} project workflow(s) with parallelism={args.parallelism}")
    results: list[dict[str, Any]] = []
    failures = 0
    with ThreadPoolExecutor(max_workers=args.parallelism) as pool:
        futures = {
            pool.submit(launch_project, args.api_base, project, dry_run=args.dry_run): project
            for project in projects
        }
        for future in as_completed(futures):
            project = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - keep launching independent projects
                failures += 1
                print(f"FAILED {project.name}: {exc}", file=sys.stderr)
            else:
                results.append(result)
                print(
                    "STARTED "
                    f"{result['name']} project_id={result['project_id']} "
                    f"workflow_id={result['workflow_id']}"
                )
    print(json.dumps({"failed": failures, "started": results}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
