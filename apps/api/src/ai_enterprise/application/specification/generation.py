from dataclasses import dataclass
from typing import Any

from ai_enterprise.domain.specification.api import generate_openapi
from ai_enterprise.domain.specification.database import EntitySpecification, generate_create_table
from ai_enterprise.domain.specification.event import EventSpecification, generate_event_schema
from ai_enterprise.domain.specification.kernel import (
    SpecificationArtifact,
    SpecificationIdentity,
    specification_hash,
)
from ai_enterprise.domain.specification.service import ServiceSpecification


@dataclass(frozen=True)
class GeneratedArtifact:
    artifact_type: str
    content: dict[str, Any] | str
    source_spec_hash: str
    provenance: dict[str, str]
    artifact_hash: str

    @classmethod
    def build(
        cls,
        artifact_type: str,
        content: dict[str, Any] | str,
        source_spec_hash: str,
        provenance: dict[str, str],
    ) -> "GeneratedArtifact":
        values = {
            "artifact_type": artifact_type,
            "content": content,
            "source_spec_hash": source_spec_hash,
            "provenance": provenance,
        }
        return cls(
            artifact_type,
            content,
            source_spec_hash,
            provenance,
            specification_hash(values),
        )

    def verify(self) -> bool:
        return self.artifact_hash == specification_hash(
            {
                "artifact_type": self.artifact_type,
                "content": self.content,
                "source_spec_hash": self.source_spec_hash,
                "provenance": self.provenance,
            }
        )


class SpecificationGenerator:
    def api(
        self, identity: SpecificationIdentity, service: ServiceSpecification
    ) -> GeneratedArtifact:
        source = SpecificationArtifact.build(identity=identity, kind="service", document=service)
        return GeneratedArtifact.build(
            "openapi",
            generate_openapi(service, version=identity.version, spec_hash=source.spec_hash),
            source.spec_hash,
            identity.provenance.model_dump(),
        )

    def database(
        self, identity: SpecificationIdentity, entity: EntitySpecification
    ) -> GeneratedArtifact:
        source = SpecificationArtifact.build(identity=identity, kind="database", document=entity)
        return GeneratedArtifact.build(
            "sql", generate_create_table(entity), source.spec_hash, identity.provenance.model_dump()
        )

    def event(
        self, identity: SpecificationIdentity, event: EventSpecification
    ) -> GeneratedArtifact:
        source = SpecificationArtifact.build(identity=identity, kind="event", document=event)
        return GeneratedArtifact.build(
            "json-schema",
            generate_event_schema(event, spec_hash=source.spec_hash),
            source.spec_hash,
            identity.provenance.model_dump(),
        )
