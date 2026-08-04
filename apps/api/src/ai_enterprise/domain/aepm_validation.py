from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.specification.kernel import specification_hash


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ValidationValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ValidationFinding(ValidationValue):
    code: str = Field(pattern=r"^AEPM-VAL-[0-9]{3}$")
    severity: ValidationSeverity
    message: str
    path: str
    object_ids: tuple[str, ...] = ()


class AepmValidationReport(ValidationValue):
    schema_version: Literal["aepm-validation-0.1"] = "aepm-validation-0.1"
    valid: bool
    findings: tuple[ValidationFinding, ...]
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> AepmValidationReport:
        expected_valid = not any(
            finding.severity is ValidationSeverity.ERROR for finding in self.findings
        )
        if self.valid is not expected_valid:
            raise ValueError("validation status does not match finding severities")
        expected_hash = _report_hash(self.valid, self.findings)
        if self.report_sha256 != expected_hash:
            raise ValueError("validation report hash does not match canonical findings")
        return self


class AepmValidationEngine:
    def validate(self, document: dict[str, Any]) -> AepmValidationReport:
        findings: list[ValidationFinding] = []
        self._required_content(document, findings)
        self._ownership(document, findings)
        self._contradictions(document, findings)
        self._unresolved_assumptions(document, findings)
        self._duplicates(document, findings)
        self._schema(document, findings)
        ordered = tuple(
            sorted(
                set(findings),
                key=lambda item: (
                    0 if item.severity is ValidationSeverity.ERROR else 1,
                    item.code,
                    item.path,
                    item.object_ids,
                ),
            )
        )
        valid = not any(item.severity is ValidationSeverity.ERROR for item in ordered)
        return AepmValidationReport(
            valid=valid,
            findings=ordered,
            report_sha256=_report_hash(valid, ordered),
        )

    def _required_content(
        self, document: dict[str, Any], findings: list[ValidationFinding]
    ) -> None:
        intent = document.get("project_intent")
        if not isinstance(intent, dict) or not _text(intent.get("summary")):
            _add(findings, "001", "Project intent is missing.", "project_intent")
        checks = (
            ("business_outcomes", "indicators", "002", "Business outcome needs an indicator."),
            ("core_processes", "trigger", "004", "Core process needs a trigger."),
            ("core_processes", "outputs", "004", "Core process needs an output."),
            (
                "quality_requirements",
                "acceptance_criteria",
                "005",
                "Quality requirement needs acceptance criteria.",
            ),
            (
                "integrations",
                "security_rules",
                "007",
                "Integration needs security rules.",
            ),
        )
        for collection, field, code, message in checks:
            for index, item in enumerate(_objects(document.get(collection))):
                if not _present(item.get(field)):
                    _add(
                        findings,
                        code,
                        message,
                        f"{collection}/{index}/{field}",
                        _identifier(item),
                    )

    def _ownership(self, document: dict[str, Any], findings: list[ValidationFinding]) -> None:
        stakeholder_ids = {
            str(item.get("id"))
            for item in _objects(document.get("stakeholders"))
            if _text(item.get("id"))
        }
        for collection, code, label in (
            ("capabilities", "003", "Capability"),
            ("data_entities", "006", "Data entity"),
        ):
            for index, item in enumerate(_objects(document.get(collection))):
                owner = item.get("owner_stakeholder_id")
                if not _text(owner) or owner not in stakeholder_ids:
                    object_ids = _identifier(item)
                    _add(
                        findings,
                        code,
                        f"{label} needs a known stakeholder owner.",
                        f"{collection}/{index}/owner_stakeholder_id",
                        object_ids,
                    )
                    _add(
                        findings,
                        "011",
                        f"{label} is orphaned from its declared owner.",
                        f"{collection}/{index}",
                        object_ids,
                    )

    def _contradictions(
        self, document: dict[str, Any], findings: list[ValidationFinding]
    ) -> None:
        statements: dict[str, list[tuple[bool, str, str]]] = {}
        for collection in ("business_rules", "constraints"):
            for index, item in enumerate(_objects(document.get(collection))):
                polarity = _statement_polarity(item.get("description"))
                if polarity is None:
                    continue
                core, negative = polarity
                statements.setdefault(core, []).append(
                    (negative, f"{collection}/{index}/description", str(item.get("id", "")))
                )
        for values in statements.values():
            if {negative for negative, _path, _identifier_value in values} == {False, True}:
                paths = sorted(path for _negative, path, _identifier_value in values)
                identifiers = tuple(
                    sorted(
                        value
                        for _negative, _path, value in values
                        if value
                    )
                )
                _add(
                    findings,
                    "008",
                    "Statements contain opposing mandatory rules.",
                    "|".join(paths),
                    identifiers,
                )

    def _unresolved_assumptions(
        self, document: dict[str, Any], findings: list[ValidationFinding]
    ) -> None:
        marker = re.compile(r"\b(?:assum(?:e|ed|ption)|tbd|todo|unknown|unresolved)\b", re.I)
        for path, value in _strings(document):
            if marker.search(value):
                _add(
                    findings,
                    "009",
                    "Text contains an unresolved assumption marker.",
                    path,
                )

    def _duplicates(self, document: dict[str, Any], findings: list[ValidationFinding]) -> None:
        concepts: dict[str, list[tuple[str, str]]] = {}
        for collection in (
            "business_outcomes",
            "stakeholders",
            "capabilities",
            "core_processes",
            "business_rules",
            "data_entities",
            "integrations",
            "quality_requirements",
            "constraints",
        ):
            for index, item in enumerate(_objects(document.get(collection))):
                value = item.get("name") or item.get("description")
                normalized = _normalize(value)
                if normalized:
                    concepts.setdefault(normalized, []).append(
                        (f"{collection}/{index}", str(item.get("id", "")))
                    )
        for values in concepts.values():
            if len(values) > 1:
                _add(
                    findings,
                    "010",
                    "Multiple objects describe the same normalized concept.",
                    "|".join(sorted(path for path, _identifier_value in values)),
                    tuple(sorted(value for _path, value in values if value)),
                    severity=ValidationSeverity.WARNING,
                )

    def _schema(self, document: dict[str, Any], findings: list[ValidationFinding]) -> None:
        try:
            AepmManifest.model_validate(document)
        except ValidationError as error:
            existing_paths = {finding.path for finding in findings}
            for detail in error.errors():
                path = "/".join(str(part) for part in detail["loc"])
                if path not in existing_paths:
                    _add(
                        findings,
                        "000",
                        f"Manifest schema violation: {detail['msg']}",
                        path or "$",
                    )


def _add(
    findings: list[ValidationFinding],
    suffix: str,
    message: str,
    path: str,
    object_ids: tuple[str, ...] = (),
    *,
    severity: ValidationSeverity = ValidationSeverity.ERROR,
) -> None:
    findings.append(
        ValidationFinding(
            code=f"AEPM-VAL-{suffix}",
            severity=severity,
            message=message,
            path=path,
            object_ids=object_ids,
        )
    )


def _objects(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _present(value: Any) -> bool:
    return _text(value) or (isinstance(value, list) and bool(value))


def _identifier(value: dict[str, Any]) -> tuple[str, ...]:
    return (str(value["id"]),) if _text(value.get("id")) else ()


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFC", value).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", normalized).split())


def _statement_polarity(value: Any) -> tuple[str, bool] | None:
    normalized = _normalize(value)
    for prefix, negative in (
        ("must not ", True),
        ("shall not ", True),
        ("prohibited ", True),
        ("must ", False),
        ("shall ", False),
        ("required ", False),
    ):
        if normalized.startswith(prefix):
            return normalized.removeprefix(prefix), negative
    return None


def _strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        return [
            pair
            for index, item in enumerate(value)
            for pair in _strings(item, f"{path}/{index}")
        ]
    if isinstance(value, dict):
        return [
            pair
            for key in sorted(value)
            for pair in _strings(value[key], f"{path}/{key}")
        ]
    return []


def _report_hash(valid: bool, findings: tuple[ValidationFinding, ...]) -> str:
    return specification_hash(
        {
            "schema_version": "aepm-validation-0.1",
            "valid": valid,
            "findings": [item.model_dump(mode="json") for item in findings],
        }
    )
