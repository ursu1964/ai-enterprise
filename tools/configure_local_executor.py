#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXECUTION_IMAGE = "ai-enterprise-execution-agent:local"
REVIEW_IMAGE = "ai-enterprise-review-agent:local"


class LocalExecutorConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LocalExecutorConfiguration:
    execution_image: str
    execution_image_id: str
    review_image: str
    review_image_id: str

    def dotenv(self) -> str:
        return "\n".join(
            (
                "EXECUTION_CONTAINER_PROVIDER=restricted-local-docker",
                f"EXECUTION_IMAGE={self.execution_image}",
                f"EXECUTION_IMAGE_ID={self.execution_image_id}",
                f"REVIEW_IMAGE={self.review_image}",
                f"REVIEW_IMAGE_ID={self.review_image_id}",
                "",
            )
        )

    def json(self) -> dict[str, str]:
        return {
            "execution_container_provider": "restricted-local-docker",
            "execution_image": self.execution_image,
            "execution_image_id": self.execution_image_id,
            "review_image": self.review_image,
            "review_image_id": self.review_image_id,
        }


def docker_image_id(image: str) -> str:
    try:
        completed = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{json .}}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise LocalExecutorConfigurationError("docker CLI is not installed") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise LocalExecutorConfigurationError(
            f"required local image {image!r} is not available: {detail}"
        ) from exc
    try:
        payload: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LocalExecutorConfigurationError(
            f"docker returned invalid inspect JSON for {image!r}"
        ) from exc
    image_id = payload.get("Id")
    if not isinstance(image_id, str) or not _is_sha256_image_id(image_id):
        raise LocalExecutorConfigurationError(
            f"docker image {image!r} did not resolve to an immutable sha256 image ID"
        )
    return image_id


def local_executor_configuration(
    *,
    execution_image: str = EXECUTION_IMAGE,
    review_image: str = REVIEW_IMAGE,
) -> LocalExecutorConfiguration:
    return LocalExecutorConfiguration(
        execution_image=execution_image,
        execution_image_id=docker_image_id(execution_image),
        review_image=review_image,
        review_image_id=docker_image_id(review_image),
    )


def write_env_file(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise LocalExecutorConfigurationError(
            f"{path} already exists; pass --force to replace it"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
    temp_path.replace(path)


def _is_sha256_image_id(value: str) -> bool:
    if not value.startswith("sha256:") or len(value) != 71:
        return False
    try:
        int(value.removeprefix("sha256:"), 16)
    except ValueError:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the exact local env block required as input to the approved "
            "restricted Docker executor preflight."
        )
    )
    parser.add_argument("--execution-image", default=EXECUTION_IMAGE)
    parser.add_argument("--review-image", default=REVIEW_IMAGE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        config = local_executor_configuration(
            execution_image=args.execution_image,
            review_image=args.review_image,
        )
        if args.json:
            print(json.dumps(config.json(), sort_keys=True))
            return 0
        content = config.dotenv()
        if args.output is not None:
            write_env_file(args.output, content, force=args.force)
            print(f"Wrote approved local executor env to {args.output}")
            return 0
        print(content, end="")
        return 0
    except LocalExecutorConfigurationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
