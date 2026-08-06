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
    INFORMATION = "information"
    RECOMMENDATION = "recommendation"


class ValidationCategory(StrEnum):
    SCHEMA = "schema"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    TRACEABILITY = "traceability"
    SECURITY = "security"
    QUALITY = "quality"
    GOVERNANCE = "governance"
    AMBIGUITY = "ambiguity"
    DUPLICATION = "duplication"


class ValidationValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ValidationFinding(ValidationValue):
    id: str = Field(pattern=r"^VAL-[0-9]{3}$")
    code: str = Field(pattern=r"^AEPM-VAL-[0-9]{3}$")
    rule_id: str = Field(pattern=r"^AEPM\.[A-Z0-9_.]+$")
    severity: ValidationSeverity
    category: ValidationCategory
    message: str
    path: str
    object_refs: tuple[str, ...] = ()
    blocking: bool = True
    suggested_action: str

    @property
    def object_ids(self) -> tuple[str, ...]:
        return self.object_refs


class AepmValidationReport(ValidationValue):
    schema_version: Literal["aepm-validation-0.1"] = "aepm-validation-0.1"
    valid: bool
    findings: tuple[ValidationFinding, ...]
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> AepmValidationReport:
        expected_valid = not any(finding.blocking for finding in self.findings)
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
                    item.object_refs,
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
                    _path_identifier(document, path),
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
                for field in ("name", "description"):
                    normalized = _normalize(item.get(field))
                    if normalized:
                        concepts.setdefault(normalized, []).append(
                            (f"{collection}/{index}/{field}", str(item.get("id", "")))
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
    object_refs: tuple[str, ...] = (),
    *,
    severity: ValidationSeverity = ValidationSeverity.ERROR,
) -> None:
    category = _category(suffix)
    blocking = severity is ValidationSeverity.ERROR
    findings.append(
        ValidationFinding(
            id=f"VAL-{suffix}",
            code=f"AEPM-VAL-{suffix}",
            rule_id=_rule_id(suffix),
            severity=severity,
            category=category,
            message=message,
            path=path,
            object_refs=object_refs,
            blocking=blocking,
            suggested_action=_suggested_action(suffix, category),
        )
    )


def _category(suffix: str) -> ValidationCategory:
    return {
        "000": ValidationCategory.SCHEMA,
        "001": ValidationCategory.COMPLETENESS,
        "002": ValidationCategory.COMPLETENESS,
        "003": ValidationCategory.GOVERNANCE,
        "004": ValidationCategory.COMPLETENESS,
        "005": ValidationCategory.QUALITY,
        "006": ValidationCategory.GOVERNANCE,
        "007": ValidationCategory.SECURITY,
        "008": ValidationCategory.CONSISTENCY,
        "009": ValidationCategory.AMBIGUITY,
        "010": ValidationCategory.DUPLICATION,
        "011": ValidationCategory.TRACEABILITY,
    }[suffix]


def _rule_id(suffix: str) -> str:
    return {
        "000": "AEPM.SCHEMA.VALID",
        "001": "AEPM.PROJECT_INTENT.REQUIRED",
        "002": "AEPM.OUTCOME.INDICATOR_REQUIRED",
        "003": "AEPM.CAPABILITY.OWNER_REQUIRED",
        "004": "AEPM.PROCESS.TRIGGER_OUTPUT_REQUIRED",
        "005": "AEPM.REQUIREMENT.ACCEPTANCE_CRITERIA_REQUIRED",
        "006": "AEPM.ENTITY.OWNER_REQUIRED",
        "007": "AEPM.INTEGRATION.SECURITY_RULE_REQUIRED",
        "008": "AEPM.CONSISTENCY.CONTRADICTION_CHECK",
        "009": "AEPM.AMBIGUITY.UNRESOLVED_ASSUMPTION",
        "010": "AEPM.DUPLICATION.NORMALIZED_CONCEPT",
        "011": "AEPM.TRACEABILITY.ORPHAN_OBJECT",
    }[suffix]


def _suggested_action(suffix: str, category: ValidationCategory) -> str:
    return {
        "000": "Correct the manifest so it conforms to AEPM v0.1.",
        "001": "Provide a project intent summary before intake.",
        "002": "Define at least one measurable indicator for the outcome.",
        "003": "Assign the capability to a known stakeholder.",
        "004": "Define the process trigger and at least one output.",
        "005": "Add acceptance criteria that can be evaluated later.",
        "006": "Assign the data entity to a known stakeholder.",
        "007": "Add explicit security rules for the integration.",
        "008": "Resolve the conflicting mandatory statements.",
        "009": "Confirm or replace the assumption marker with approved text.",
        "010": "Review the duplicated concept and merge or differentiate it.",
        "011": "Link the object to a valid owner or source relationship.",
    }.get(suffix, f"Review and resolve the {category.value} finding.")


def _objects(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _present(value: Any) -> bool:
    return _text(value) or (isinstance(value, list) and bool(value))


def _identifier(value: dict[str, Any]) -> tuple[str, ...]:
    return (str(value["id"]),) if _text(value.get("id")) else ()


def _path_identifier(document: dict[str, Any], path: str) -> tuple[str, ...]:
    parts = path.removeprefix("$/").split("/")
    if len(parts) < 2:
        return ()
    collection = document.get(parts[0])
    if not isinstance(collection, list):
        return ()
    try:
        item = collection[int(parts[1])]
    except (IndexError, ValueError):
        return ()
    return _identifier(item) if isinstance(item, dict) else ()


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
