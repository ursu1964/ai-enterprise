import json
from typing import Any

from pydantic import ValidationError

from ai_enterprise.domain.architecture.schema import ArchitectureArtifactDocument


class ArchitectureOutputParseError(ValueError):
    pass


def parse_architecture_json(raw_output: str, *, maximum_bytes: int) -> ArchitectureArtifactDocument:
    encoded = raw_output.encode("utf-8")
    if not encoded or len(encoded) > maximum_bytes:
        raise ArchitectureOutputParseError("Architecture output is empty or exceeds the byte limit")
    if (
        raw_output != raw_output.strip()
        or not raw_output.startswith("{")
        or not raw_output.endswith("}")
    ):
        raise ArchitectureOutputParseError("Architecture output must be one unwrapped JSON object")
    try:
        payload: Any = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ArchitectureOutputParseError("Architecture output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ArchitectureOutputParseError("Architecture output must be a JSON object")
    try:
        return ArchitectureArtifactDocument.model_validate(payload)
    except ValidationError as exc:
        raise ArchitectureOutputParseError("Architecture output violates schema 1.0") from exc
