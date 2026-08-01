from typing import Literal

from pydantic import Field, model_validator

from .kernel import StrictSpecification


class DataField(StrictSpecification):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    type: Literal["string", "integer", "number", "boolean", "uuid", "datetime", "object", "array"]
    required: bool = True
    nullable: bool = False
    description: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def reject_required_nullable(self) -> "DataField":
        if self.required and self.nullable:
            raise ValueError("a required field cannot be nullable")
        return self


class Operation(StrictSpecification):
    name: str = Field(pattern=r"^[A-Z][A-Za-z0-9]+$")
    input_fields: tuple[DataField, ...] = ()
    output_fields: tuple[DataField, ...] = ()
    authorization_capability: str = Field(min_length=3)
    timeout_seconds: int = Field(gt=0, le=3600)
    retry_limit: int = Field(ge=0, le=10)
    idempotent: bool

    @model_validator(mode="after")
    def deterministic_fields(self) -> "Operation":
        for fields in (self.input_fields, self.output_fields):
            names = [field.name for field in fields]
            if names != sorted(set(names)):
                raise ValueError("operation fields must be sorted and unique")
        return self


class Endpoint(StrictSpecification):
    operation_name: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str = Field(pattern=r"^/[a-z0-9_{}\-/]*$")
    success_status: int = Field(ge=200, lt=300)


class ServiceSpecification(StrictSpecification):
    name: str = Field(pattern=r"^[A-Z][A-Za-z0-9]+Service$")
    purpose: str = Field(min_length=10, max_length=1000)
    dependencies: tuple[str, ...] = ()
    commands: tuple[Operation, ...] = ()
    queries: tuple[Operation, ...] = ()
    endpoints: tuple[Endpoint, ...] = ()
    produced_events: tuple[str, ...] = ()
    consumed_events: tuple[str, ...] = ()
    workers: tuple[str, ...] = ()
    external_integrations: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    p95_latency_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def unique_and_bound(self) -> "ServiceSpecification":
        operations = self.commands + self.queries
        names = [operation.name for operation in operations]
        if len(names) != len(set(names)):
            raise ValueError("operation names must be unique")
        endpoint_names = [endpoint.operation_name for endpoint in self.endpoints]
        endpoint_keys = [(endpoint.path, endpoint.method) for endpoint in self.endpoints]
        if len(endpoint_names) != len(set(endpoint_names)) or not set(endpoint_names).issubset(
            names
        ):
            raise ValueError("endpoints must uniquely reference declared operations")
        if len(endpoint_keys) != len(set(endpoint_keys)):
            raise ValueError("an HTTP method/path can bind only one operation")
        if tuple(sorted(set(self.dependencies))) != self.dependencies:
            raise ValueError("dependencies must be unique and sorted")
        collections = (
            self.produced_events,
            self.consumed_events,
            self.workers,
            self.external_integrations,
            self.policies,
            self.permissions,
        )
        if any(values != tuple(sorted(set(values))) for values in collections):
            raise ValueError("service references must be unique and sorted")
        return self
