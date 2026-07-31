import json
from typing import Any


class InvalidModelJsonError(ValueError):
    pass


def parse_model_json(raw_output: str) -> dict[str, Any]:
    value = raw_output.strip()

    if value.startswith("```"):
        lines = value.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        value = "\n".join(lines).strip()

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InvalidModelJsonError(
            f"Model returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidModelJsonError(
            "Model output must be a JSON object"
        )

    return parsed
