#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from urllib.error import URLError
from urllib.request import urlopen


def verify(base_url: str, model: str, timeout: int = 10) -> dict[str, object]:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return {
            "conformant": False,
            "endpoint": base_url,
            "model": model,
            "findings": [f"model_service: {exc}"],
        }
    models = [item.get("name") for item in payload.get("models", []) if isinstance(item, dict)]
    return {
        "conformant": model in models,
        "endpoint": base_url,
        "model": model,
        "available_models": models,
        "findings": [] if model in models else [f"model_service: model {model} not listed"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Ollama-compatible model endpoint.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = verify(args.base_url, args.model, args.timeout)
    if args.json:
        print(json.dumps(report, sort_keys=True))
    elif report["conformant"]:
        print(f"Model endpoint verified: {args.model}")
    else:
        for finding in report["findings"]:
            print(finding)
    return 0 if report["conformant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
