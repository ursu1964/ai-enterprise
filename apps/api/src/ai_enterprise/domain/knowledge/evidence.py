from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ._hashing import stable_hash
from .errors import InvalidEvidenceLocator

ALLOWED_RELATIONS = frozenset(
    {"supports", "demonstrates", "contradicts", "supersedes", "qualifies", "originates_from"}
)
ALLOWED_LOCATOR_KEYS = frozenset(
    {
        "artifact_field",
        "json_pointer",
        "file_path",
        "line_range",
        "test_case_id",
        "review_finding_id",
        "commit_path",
    }
)


@dataclass(frozen=True)
class EvidenceBinding:
    knowledge_source_id: UUID
    relation: str
    evidence_locator: Mapping[str, Any]
    quotation_hash: str | None = None

    def __post_init__(self) -> None:
        if self.relation not in ALLOWED_RELATIONS:
            raise InvalidEvidenceLocator("unsupported evidence relation")
        validate_locator(self.evidence_locator)
        if self.quotation_hash is not None and len(self.quotation_hash) != 64:
            raise InvalidEvidenceLocator("quotation_hash must be SHA-256")

    @property
    def binding_hash(self) -> str:
        return stable_hash(
            {
                "source": str(self.knowledge_source_id),
                "relation": self.relation,
                "locator": dict(self.evidence_locator),
                "quotation_hash": self.quotation_hash,
            }
        )


def validate_locator(locator: Mapping[str, Any]) -> None:
    if not locator or not set(locator).issubset(ALLOWED_LOCATOR_KEYS):
        raise InvalidEvidenceLocator("locator must use a supported structured locator key")
    if "line_range" in locator:
        line_range = locator["line_range"]
        if (
            not isinstance(line_range, Sequence)
            or isinstance(line_range, (str, bytes))
            or len(line_range) != 2
            or not all(isinstance(value, int) and value > 0 for value in line_range)
            or line_range[0] > line_range[1]
            or "file_path" not in locator
        ):
            raise InvalidEvidenceLocator(
                "line_range requires file_path and positive ordered bounds"
            )
    for path_key in ("file_path", "commit_path"):
        value = locator.get(path_key)
        if value is not None and (
            not isinstance(value, str)
            or value.startswith(("/", "../"))
            or "/../" in value
            or "\\" in value
        ):
            raise InvalidEvidenceLocator(
                "evidence paths must be normalized repository-relative paths"
            )
    pointer = locator.get("json_pointer")
    if pointer is not None and (not isinstance(pointer, str) or not pointer.startswith("/")):
        raise InvalidEvidenceLocator("json_pointer must be an RFC 6901-style absolute pointer")
