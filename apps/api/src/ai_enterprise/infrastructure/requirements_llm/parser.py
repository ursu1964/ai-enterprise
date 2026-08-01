import json
import re
from dataclasses import dataclass
from hashlib import sha256

from pydantic import ValidationError

from ai_enterprise.domain.requirements_revision.models import RequirementsArtifactDocument


@dataclass(frozen=True, slots=True)
class ArtifactParseFailure:
    raw_output_hash: str
    errors: tuple[dict[str, object], ...]


class RequirementsArtifactParser:
    MAX_OUTPUT_BYTES = 1_000_000
    MAX_ERRORS = 100

    def parse(self, raw_output: str) -> RequirementsArtifactDocument:
        if len(raw_output.encode()) > self.MAX_OUTPUT_BYTES:
            raise ValueError("Requirements model output exceeds the configured bound")
        value = raw_output.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, re.DOTALL | re.IGNORECASE)
        if fenced:
            value = fenced.group(1).strip()
        payload = json.loads(value)
        return RequirementsArtifactDocument.model_validate(payload)

    def failure(self, raw_output: str, error: Exception) -> ArtifactParseFailure:
        errors: tuple[dict[str, object], ...]
        if isinstance(error, ValidationError):
            errors = tuple(
                {
                    "type": item.get("type"),
                    "location": [str(value) for value in item.get("loc", ())],
                    "message": item.get("msg"),
                }
                for item in error.errors(include_url=False, include_input=False)[: self.MAX_ERRORS]
            )
        elif isinstance(error, json.JSONDecodeError):
            errors = (
                {
                    "type": "json_decode_error",
                    "location": [error.lineno, error.colno],
                    "message": error.msg,
                },
            )
        else:
            errors = ({"type": "parse_error", "location": [], "message": str(error)[:1000]},)
        return ArtifactParseFailure(sha256(raw_output.encode()).hexdigest(), errors)
