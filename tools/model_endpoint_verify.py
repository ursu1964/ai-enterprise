#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import jsonschema

MODEL_ENDPOINT_REPORT_SCHEMA_REF = (
    "schemas/production-readiness/model-endpoint-verification-report.schema.json"
)


def verify(base_url: str, model: str, timeout: int = 10) -> dict[str, object]:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        report = {
            "conformant": False,
            "endpoint": base_url,
            "model": model,
            "findings": [f"model_service: {exc}"],
            "schema_version": "1.0",
            "schema_ref": MODEL_ENDPOINT_REPORT_SCHEMA_REF,
        }
        _validate_report(report)
        return report
    models = [
        item["name"]
        for item in payload.get("models", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    report = {
        "conformant": model in models,
        "endpoint": base_url,
        "model": model,
        "available_models": models,
        "findings": [] if model in models else [f"model_service: model {model} not listed"],
        "schema_version": "1.0",
        "schema_ref": MODEL_ENDPOINT_REPORT_SCHEMA_REF,
    }
    _validate_report(report)
    return report


def _schema() -> dict[str, Any]:
    for candidate in Path(__file__).resolve().parents:
        schema_path = candidate / MODEL_ENDPOINT_REPORT_SCHEMA_REF
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return schema
    raise RuntimeError(f"{MODEL_ENDPOINT_REPORT_SCHEMA_REF} schema file is missing")


def _validate_report(report: dict[str, object]) -> None:
    try:
        jsonschema.validate(report, _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{MODEL_ENDPOINT_REPORT_SCHEMA_REF}: generated model endpoint report "
            f"does not validate: {exc.message}"
        ) from exc


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
