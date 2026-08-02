#!/usr/bin/env python3
from __future__ import annotations

import argparse
import secrets
from pathlib import Path


def generate_env(template: Path) -> str:
    text = template.read_text(encoding="utf-8")
    replacements = {
        "change-me-with-a-long-random-secret": secrets.token_urlsafe(48),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a server env file from the template.")
    parser.add_argument("--template", default=".env.server.example")
    parser.add_argument("--output", default=".env.server.generated")
    args = parser.parse_args()
    template = Path(args.template)
    output = Path(args.output)
    if output.exists():
        raise SystemExit(f"{output} already exists; refusing to overwrite secrets")
    output.write_text(generate_env(template), encoding="utf-8")
    output.chmod(0o600)
    print(f"Wrote {output}")
    print("Review provider URLs, database host, object storage, and domain before deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
