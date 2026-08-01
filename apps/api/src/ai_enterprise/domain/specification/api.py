from typing import Any

from .kernel import Compatibility, specification_hash
from .service import DataField, ServiceSpecification

_TYPE_MAP: dict[str, dict[str, str]] = {
    "string": {"type": "string"},
    "integer": {"type": "integer"},
    "number": {"type": "number"},
    "boolean": {"type": "boolean"},
    "uuid": {"type": "string", "format": "uuid"},
    "datetime": {"type": "string", "format": "date-time"},
    "object": {"type": "object"},
    "array": {"type": "array"},
}


def _schema(fields: tuple[DataField, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            field.name: {**_TYPE_MAP[field.type], "description": field.description}
            for field in sorted(fields, key=lambda item: item.name)
        },
        "required": sorted(field.name for field in fields if field.required),
    }


def generate_openapi(
    specification: ServiceSpecification, *, version: str, spec_hash: str
) -> dict[str, Any]:
    operations = {
        operation.name: operation for operation in specification.commands + specification.queries
    }
    paths: dict[str, Any] = {}
    schemas: dict[str, Any] = {}
    for endpoint in sorted(specification.endpoints, key=lambda item: (item.path, item.method)):
        operation = operations[endpoint.operation_name]
        input_name, output_name = f"{operation.name}Input", f"{operation.name}Output"
        schemas[input_name] = _schema(operation.input_fields)
        schemas[output_name] = _schema(operation.output_fields)
        paths.setdefault(endpoint.path, {})[endpoint.method.lower()] = {
            "operationId": operation.name,
            "x-required-capability": operation.authorization_capability,
            "x-idempotent": operation.idempotent,
            "requestBody": {
                "required": bool(operation.input_fields),
                "content": {
                    "application/json": {"schema": {"$ref": f"#/components/schemas/{input_name}"}}
                },
            },
            "responses": {
                str(endpoint.success_status): {
                    "description": "Success",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{output_name}"}
                        }
                    },
                }
            },
        }
    return {
        "openapi": "3.1.0",
        "info": {"title": specification.name, "version": version, "x-spec-hash": spec_hash},
        "paths": paths,
        "components": {"schemas": dict(sorted(schemas.items()))},
    }


def classify_api_change(old: dict[str, Any], new: dict[str, Any]) -> Compatibility:
    old_paths, new_paths = old.get("paths", {}), new.get("paths", {})
    for path, methods in old_paths.items():
        if path not in new_paths or not set(methods).issubset(new_paths[path]):
            return Compatibility.BREAKING
        if any(new_paths[path][method] != contract for method, contract in methods.items()):
            return Compatibility.BREAKING
    old_schemas = old.get("components", {}).get("schemas", {})
    new_schemas = new.get("components", {}).get("schemas", {})
    for name, schema in old_schemas.items():
        candidate = new_schemas.get(name)
        if candidate is None:
            return Compatibility.BREAKING
        old_properties = schema.get("properties", {})
        new_properties = candidate.get("properties", {})
        if not set(old_properties).issubset(new_properties):
            return Compatibility.BREAKING
        if any(new_properties[key] != value for key, value in old_properties.items()):
            return Compatibility.BREAKING
        if not set(schema.get("required", [])).issuperset(candidate.get("required", [])):
            return Compatibility.BREAKING
    return (
        Compatibility.COMPATIBLE
        if specification_hash(old) == specification_hash(new)
        else Compatibility.CONDITIONALLY_COMPATIBLE
    )
