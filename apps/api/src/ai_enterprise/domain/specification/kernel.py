import hashlib
import json
import math
import re
import unicodedata
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class SpecificationError(ValueError):
    pass


class Compatibility(StrEnum):
    COMPATIBLE = "compatible"
    CONDITIONALLY_COMPATIBLE = "conditionally_compatible"
    BREAKING = "breaking"


def canonical_json(value: BaseModel | dict[str, Any]) -> str:
    document = (
        value.model_dump(mode="json", exclude_none=False) if isinstance(value, BaseModel) else value
    )
    return json.dumps(
        _normalize_json(document),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _normalize_json(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SpecificationError("non-finite numbers are forbidden in specifications")
        return 0.0 if value == 0 else value
    if isinstance(value, list | tuple):
        return [_normalize_json(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise SpecificationError("specification object keys must be strings")
        normalized_keys = [unicodedata.normalize("NFC", key) for key in value]
        if len(normalized_keys) != len(set(normalized_keys)):
            raise SpecificationError("object keys collide after Unicode normalization")
        return {
            normalized_key: _normalize_json(item)
            for normalized_key, item in zip(normalized_keys, value.values(), strict=True)
        }
    raise SpecificationError(f"unsupported canonical value type: {type(value).__name__}")


def specification_hash(value: BaseModel | dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class StrictSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Provenance(StrictSpecification):
    requirements_hash: str
    architecture_hash: str
    package_hash: str

    @model_validator(mode="after")
    def validate_hashes(self) -> "Provenance":
        if not all(_SHA256.fullmatch(value) for value in self.model_dump().values()):
            raise ValueError("all provenance values must be lowercase SHA-256 hashes")
        return self


class SpecificationIdentity(StrictSpecification):
    schema_version: str = "1.0.0"
    specification_key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
    version: str
    provenance: Provenance

    @model_validator(mode="after")
    def validate_versions(self) -> "SpecificationIdentity":
        if not _VERSION.fullmatch(self.schema_version) or not _VERSION.fullmatch(self.version):
            raise ValueError("schema and artifact versions must be strict semantic versions")
        return self


class SpecificationArtifact(StrictSpecification):
    identity: SpecificationIdentity
    kind: str
    document: dict[str, Any]
    spec_hash: str

    @classmethod
    def build(
        cls, *, identity: SpecificationIdentity, kind: str, document: BaseModel | dict[str, Any]
    ) -> "SpecificationArtifact":
        normalized = (
            document.model_dump(mode="json") if isinstance(document, BaseModel) else document
        )
        bound = {"identity": identity.model_dump(mode="json"), "kind": kind, "document": normalized}
        return cls(
            identity=identity, kind=kind, document=normalized, spec_hash=specification_hash(bound)
        )

    def verify(self) -> bool:
        bound = {
            "identity": self.identity.model_dump(mode="json"),
            "kind": self.kind,
            "document": self.document,
        }
        return self.spec_hash == specification_hash(bound)


def semantic_version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise SpecificationError("invalid semantic version")
    return tuple(map(int, match.groups()))  # type: ignore[return-value]


def require_version_for_change(old: str, new: str, compatibility: Compatibility) -> None:
    old_major, old_minor, old_patch = semantic_version(old)
    new_major, new_minor, new_patch = semantic_version(new)
    if (new_major, new_minor, new_patch) <= (old_major, old_minor, old_patch):
        raise SpecificationError("specification version must increase")
    if compatibility is Compatibility.BREAKING and new_major <= old_major:
        raise SpecificationError("breaking changes require a major version")
    if compatibility is Compatibility.COMPATIBLE and new_major != old_major:
        raise SpecificationError("compatible changes cannot increment the major version")
