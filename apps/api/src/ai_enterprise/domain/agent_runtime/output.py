from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from ai_enterprise.domain.hashing import hash_json

SemanticValidator = Callable[[dict[str, Any]], tuple[dict[str, Any], ...]]


@dataclass(frozen=True)
class RuntimeOutputValidation:
    valid: bool
    normalized_output: dict[str, Any] | None
    findings: tuple[dict[str, Any], ...]
    output_hash: str | None


class StructuredOutputValidator:
    def __init__(
        self, contract: type[BaseModel], semantic_validators: tuple[SemanticValidator, ...] = ()
    ) -> None:
        self.contract = contract
        self.semantic_validators = semantic_validators

    def validate(self, raw_output: str) -> RuntimeOutputValidation:
        try:
            document = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            return RuntimeOutputValidation(
                False, None, ({"code": "OUT-001", "message": "INVALID_JSON"},), None
            )
        if not isinstance(document, dict):
            return RuntimeOutputValidation(
                False, None, ({"code": "OUT-002", "message": "SCHEMA_VIOLATION"},), None
            )
        try:
            normalized = self.contract.model_validate(document).model_dump(mode="json")
        except ValidationError as exc:
            return RuntimeOutputValidation(
                False,
                None,
                (
                    {
                        "code": "OUT-002",
                        "message": "SCHEMA_VIOLATION",
                        "details": exc.errors(include_url=False),
                    },
                ),
                None,
            )
        findings = tuple(
            finding for validator in self.semantic_validators for finding in validator(normalized)
        )
        if findings:
            return RuntimeOutputValidation(False, None, findings, None)
        return RuntimeOutputValidation(True, normalized, (), hash_json(normalized))


@dataclass(frozen=True)
class OutputRepairPolicy:
    maximum_repair_attempts: int = 1
    allow_tool_calls_during_repair: bool = False
    require_same_model: bool = True


@dataclass(frozen=True)
class RepairResult:
    validation: RuntimeOutputValidation
    attempts: int
    escalated: bool


class BoundedOutputRepair:
    def run(
        self,
        *,
        initial_output: str,
        validator: StructuredOutputValidator,
        repair: Callable[[tuple[dict[str, Any], ...]], str],
        policy: OutputRepairPolicy,
    ) -> RepairResult:
        result = validator.validate(initial_output)
        attempts = 0
        while not result.valid and attempts < policy.maximum_repair_attempts:
            attempts += 1
            result = validator.validate(repair(result.findings))
        return RepairResult(result, attempts, not result.valid)
