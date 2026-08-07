#!/usr/bin/env python3
"""Generate UPDL Semantic Platform 0.4 projections.

The source is a canonical registry JSON document. Generators consume that model
only; they do not parse source YAML or introduce independent domain semantics.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_enterprise.domain.specification.kernel import specification_hash

GENERATOR_VERSION = "0.4.0"
DEFAULT_REGISTRY = Path("registry/updl-semantic-platform-0.4/reference-approval.json")
DEFAULT_OUTPUT = Path("generated/semantic-platform-0.4")


@dataclass(frozen=True)
class GeneratedArtifact:
    path: str
    media_type: str
    content: str
    source_elements: tuple[str, ...]
    semantic_hash: str
    generator_id: str
    generator_version: str = GENERATOR_VERSION


def build_generation(
    root: Path,
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    previous_registry_path: Path | None = None,
) -> dict[str, Any]:
    registry = _load_registry(root, registry_path)
    previous_registry = (
        _load_registry(root, previous_registry_path) if previous_registry_path is not None else None
    )
    artifacts: list[GeneratedArtifact] = []
    artifacts.extend(_postgresql_artifacts(registry))
    artifacts.extend(_migration_artifacts(registry, previous_registry))
    artifacts.extend(_openapi_artifacts(registry))
    artifacts.extend(_ui_artifacts(registry))
    artifacts.extend(_test_artifacts(registry))
    artifacts.extend(_documentation_artifacts(registry))
    artifacts.extend(_diagram_artifacts(registry))
    artifacts.extend(_ai_context_artifacts(registry))

    manifest_without_hash = {
        "schema_version": "1.0",
        "registry": {
            "id": registry["registry"]["id"],
            "version": registry["registry"]["version"],
            "semantic_hash": _semantic_hash(registry),
        },
        "previous_registry": (
            {
                "id": previous_registry["registry"]["id"],
                "version": previous_registry["registry"]["version"],
                "semantic_hash": _semantic_hash(previous_registry),
            }
            if previous_registry is not None
            else None
        ),
        "compiler": {"version": GENERATOR_VERSION},
        "generators": _generator_records(artifacts),
        "artifacts": [
            {
                "path": item.path,
                "media_type": item.media_type,
                "semantic_hash": item.semantic_hash,
                "generator": item.generator_id,
                "generator_version": item.generator_version,
                "source_elements": list(item.source_elements),
            }
            for item in artifacts
        ],
        "coverage": _coverage(registry),
        "diagnostics": [],
    }
    return {
        **manifest_without_hash,
        "generation_hash": _stable_hash(manifest_without_hash),
        "_artifacts": artifacts,
    }


def write_generation(
    root: Path,
    output_root: Path,
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    previous_registry_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    target = output_root if output_root.is_absolute() else root / output_root
    if target == root or target.parent == target:
        raise RuntimeError("Refusing to replace a broad generation target")
    build = build_generation(
        root,
        registry_path=registry_path,
        previous_registry_path=previous_registry_path,
    )
    artifacts: list[GeneratedArtifact] = build.pop("_artifacts")
    staging_root = target.parent / ".generated-tmp" / build["generation_hash"]
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True)
    for artifact in artifacts:
        output = staging_root / artifact.path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(artifact.content, encoding="utf-8")
    manifest_output = staging_root / "generation-manifest.json"
    manifest_output.write_text(
        json.dumps(build, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging_root.replace(target)
    try:
        staging_root.parent.rmdir()
    except OSError:
        pass
    return build


def _load_registry(root: Path, registry_path: Path) -> dict[str, Any]:
    path = registry_path if registry_path.is_absolute() else root / registry_path
    registry = json.loads(path.read_text(encoding="utf-8"))
    _validate_registry(registry)
    return registry


def _validate_registry(registry: dict[str, Any]) -> None:
    required = (
        "registry",
        "types",
        "objects",
        "relationships",
        "constraints",
        "commands",
        "events",
        "behaviors",
        "transitions",
        "permissions",
    )
    missing = [key for key in required if key not in registry]
    if missing:
        raise RuntimeError(f"Canonical registry is missing sections: {', '.join(missing)}")
    objects = registry["objects"]
    types = registry["types"]
    for object_id, definition in objects.items():
        for property_name, property_definition in definition["properties"].items():
            property_type = property_definition["type"]
            if property_type.startswith("Reference<"):
                referenced = property_type.removeprefix("Reference<").removesuffix(">")
                if referenced not in objects:
                    raise RuntimeError(
                        f"{object_id}.{property_name}: unknown reference {referenced}"
                    )
            elif (
                property_type not in {"String", "Text", "Boolean", "Timestamp"}
                and property_type not in types
            ):
                raise RuntimeError(f"{object_id}.{property_name}: unknown type {property_type}")
    for behavior_id, behavior in registry["behaviors"].items():
        subject = behavior["subject"]
        state_property = behavior["state_property"]
        if subject not in objects:
            raise RuntimeError(f"{behavior_id}: unknown subject {subject}")
        if state_property not in objects[subject]["properties"]:
            raise RuntimeError(f"{behavior_id}: unknown state property {state_property}")
        for transition_id in behavior["transitions"]:
            if transition_id not in registry["transitions"]:
                raise RuntimeError(f"{behavior_id}: unknown transition {transition_id}")
    for transition_id, transition in registry["transitions"].items():
        behavior = registry["behaviors"][transition["behavior"]]
        states = set(behavior["states"])
        unknown_states = (set(transition["from"]) | {transition["to"]}) - states
        if unknown_states:
            raise RuntimeError(f"{transition_id}: unknown states {sorted(unknown_states)}")
        if transition["command"] not in registry["commands"]:
            raise RuntimeError(f"{transition_id}: unknown command {transition['command']}")
        for event_id in transition.get("emits", []):
            if event_id not in registry["events"]:
                raise RuntimeError(f"{transition_id}: unknown event {event_id}")
        for permission_id in transition.get("permissions", []):
            if permission_id not in registry["permissions"]:
                raise RuntimeError(f"{transition_id}: unknown permission {permission_id}")


def _migration_artifacts(
    registry: dict[str, Any],
    previous_registry: dict[str, Any] | None,
) -> tuple[GeneratedArtifact, ...]:
    plan = _migration_plan(registry, previous_registry)
    sql = _migration_sql(registry, plan)
    source_elements = tuple(
        sorted(
            {
                *registry["objects"],
                *(previous_registry or {"objects": {}})["objects"],
                *(
                    migration["id"]
                    for migration in registry.get("migrations", {}).values()
                    if isinstance(migration, dict) and isinstance(migration.get("id"), str)
                ),
            }
        )
    )
    return (
        _artifact(
            "semantic.migrations",
            "database/migration-plan.json",
            "application/json",
            _json(plan),
            source_elements,
        ),
        _artifact(
            "semantic.migrations",
            "database/migration.sql",
            "text/sql",
            sql,
            source_elements,
        ),
    )


def _migration_plan(
    registry: dict[str, Any],
    previous_registry: dict[str, Any] | None,
) -> dict[str, Any]:
    if previous_registry is None:
        return {
            "schema_version": "1.0",
            "mode": "baseline",
            "status": "no_previous_registry",
            "blocked": False,
            "changes": [],
            "required_actions": [],
        }

    changes: list[dict[str, Any]] = []
    current_objects = registry["objects"]
    previous_objects = previous_registry["objects"]
    for object_id in sorted(current_objects.keys() - previous_objects.keys()):
        changes.append(
            {
                "semanticElementId": object_id,
                "kind": "object_added",
                "classification": "additive",
                "blocked": False,
                "action": "create_table",
            }
        )
    for object_id in sorted(previous_objects.keys() - current_objects.keys()):
        changes.append(
            {
                "semanticElementId": object_id,
                "kind": "object_removed",
                "classification": "destructive",
                "blocked": True,
                "action": "manual_review",
                "reason": "Removing an object can destroy persisted data.",
            }
        )
    for object_id in sorted(current_objects.keys() & previous_objects.keys()):
        changes.extend(
            _property_migration_changes(
                registry,
                previous_registry,
                object_id,
            )
        )

    blocked_changes = [change for change in changes if change["blocked"]]
    return {
        "schema_version": "1.0",
        "mode": "semantic_diff",
        "status": "blocked" if blocked_changes else "ready",
        "blocked": bool(blocked_changes),
        "changes": changes,
        "required_actions": [
            {
                "semanticElementId": change["semanticElementId"],
                "action": change["action"],
                "reason": change.get("reason", "Manual migration review is required."),
            }
            for change in blocked_changes
        ],
    }


def _property_migration_changes(
    registry: dict[str, Any],
    previous_registry: dict[str, Any],
    object_id: str,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    current_properties = registry["objects"][object_id]["properties"]
    previous_properties = previous_registry["objects"][object_id]["properties"]
    for property_name in sorted(current_properties.keys() - previous_properties.keys()):
        property_definition = current_properties[property_name]
        migration = _declared_property_migration(registry, object_id, property_name)
        required = bool(property_definition.get("required"))
        blocked = required and migration is None
        changes.append(
            {
                "semanticElementId": f"{object_id}.property.{property_name}",
                "kind": "property_added",
                "objectId": object_id,
                "property": property_name,
                "type": property_definition["type"],
                "required": required,
                "classification": (
                    "manual_review"
                    if blocked
                    else "breaking_with_backfill"
                    if required
                    else "additive"
                ),
                "blocked": blocked,
                "action": "declare_backfill" if blocked else "add_column",
                "reason": (
                    "Required property added without default or backfill strategy."
                    if blocked
                    else "Declared backfill makes required property migration explicit."
                    if required
                    else "Optional property can be added without rewriting existing rows."
                ),
                "migration": migration["id"] if migration is not None else None,
            }
        )
    for property_name in sorted(previous_properties.keys() - current_properties.keys()):
        changes.append(
            {
                "semanticElementId": f"{object_id}.property.{property_name}",
                "kind": "property_removed",
                "objectId": object_id,
                "property": property_name,
                "classification": "destructive",
                "blocked": True,
                "action": "manual_review",
                "reason": "Removing a property can destroy persisted data.",
            }
        )
    for property_name in sorted(current_properties.keys() & previous_properties.keys()):
        current_type = current_properties[property_name]["type"]
        previous_type = previous_properties[property_name]["type"]
        if current_type != previous_type:
            changes.append(
                {
                    "semanticElementId": f"{object_id}.property.{property_name}",
                    "kind": "property_type_changed",
                    "objectId": object_id,
                    "property": property_name,
                    "from": previous_type,
                    "to": current_type,
                    "classification": "breaking",
                    "blocked": True,
                    "action": "manual_review",
                    "reason": "Type changes require explicit compatibility and data migration.",
                }
            )
    return changes


def _declared_property_migration(
    registry: dict[str, Any],
    object_id: str,
    property_name: str,
) -> dict[str, Any] | None:
    for migration in registry.get("migrations", {}).values():
        for operation in migration.get("operations", []):
            property_operation = operation.get("property")
            if not isinstance(property_operation, dict):
                continue
            if (
                property_operation.get("object") == object_id
                and property_operation.get("name") == property_name
                and "backfill" in operation
            ):
                return migration
    return None


def _migration_sql(registry: dict[str, Any], plan: dict[str, Any]) -> str:
    lines = ["-- Generated by semantic.migrations 0.4.0", ""]
    if plan["mode"] == "baseline":
        lines.append("-- Baseline generation: no previous registry was supplied.")
        return "\n".join(lines)
    if plan["blocked"]:
        lines.append("-- Migration blocked: unsafe semantic changes require manual action.")
        for action in plan["required_actions"]:
            lines.append(f"-- {action['semanticElementId']}: {action['reason']}")
        return "\n".join(lines)
    if not plan["changes"]:
        lines.append("-- No semantic persistence changes detected.")
        return "\n".join(lines)

    for change in plan["changes"]:
        if change["kind"] == "object_added":
            lines.extend(_create_table_sql(registry, change["semanticElementId"]))
            lines.append("")
        elif change["kind"] == "property_added":
            lines.extend(_add_property_sql(registry, change))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _create_table_sql(registry: dict[str, Any], object_id: str) -> list[str]:
    definition = registry["objects"][object_id]
    table = _sql_name(object_id)
    lines = [
        f"-- semantic-id: {object_id}",
        f"CREATE TABLE {table} (",
        "    id UUID PRIMARY KEY,",
    ]
    constraints: list[str] = []
    columns: list[str] = []
    for property_name, property_definition in sorted(definition["properties"].items()):
        column, column_type, extra, constraint = _sql_column(
            registry,
            object_id,
            property_name,
            property_definition,
        )
        columns.append(f"    {column} {column_type}{extra}")
        if constraint:
            constraints.append(constraint)
    columns.append("    version BIGINT NOT NULL DEFAULT 1")
    lines.extend(_comma_lines(columns + constraints))
    lines.append(");")
    return lines


def _add_property_sql(registry: dict[str, Any], change: dict[str, Any]) -> list[str]:
    object_id = change["objectId"]
    property_name = change["property"]
    property_definition = registry["objects"][object_id]["properties"][property_name]
    column, column_type, extra, constraint = _sql_column(
        registry,
        object_id,
        property_name,
        property_definition,
    )
    table = _sql_name(object_id)
    lines = [f"-- semantic-id: {change['semanticElementId']}"]
    if change["classification"] == "breaking_with_backfill":
        migration = _declared_property_migration(registry, object_id, property_name)
        if migration is None:
            raise RuntimeError(f"{change['semanticElementId']}: missing declared migration")
        backfill = _property_backfill(migration, object_id, property_name)
        lines.append(f"ALTER TABLE {table} ADD COLUMN {column} {column_type};")
        lines.append(
            f"UPDATE {table} SET {column} = {_sql_literal(backfill['value'])} "
            f"WHERE {column} IS NULL;"
        )
        lines.append(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL;")
        if " UNIQUE" in extra:
            lines.append(
                f"ALTER TABLE {table} ADD CONSTRAINT uq_{table}_{column} UNIQUE ({column});"
            )
    else:
        lines.append(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}{extra};")
    if constraint:
        lines.append(f"ALTER TABLE {table} ADD {constraint.strip()};")
    return lines


def _property_backfill(
    migration: dict[str, Any],
    object_id: str,
    property_name: str,
) -> dict[str, Any]:
    for operation in migration["operations"]:
        property_operation = operation.get("property")
        if (
            isinstance(property_operation, dict)
            and property_operation.get("object") == object_id
            and property_operation.get("name") == property_name
        ):
            backfill = operation.get("backfill")
            if isinstance(backfill, dict) and backfill.get("strategy") == "literal":
                return backfill
    raise RuntimeError(f"{object_id}.property.{property_name}: missing literal backfill")


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise RuntimeError(f"Unsupported SQL literal: {value!r}")


def _postgresql_artifacts(registry: dict[str, Any]) -> tuple[GeneratedArtifact, ...]:
    sql = ["-- Generated by semantic.postgresql 0.4.0", ""]
    mapping: dict[str, Any] = {}
    for object_id, definition in sorted(registry["objects"].items()):
        table = _sql_name(object_id)
        mapping[object_id] = {"table": table, "properties": {}}
        lines = _create_table_sql(registry, object_id)
        for property_name, property_definition in sorted(definition["properties"].items()):
            column, *_ = _sql_column(
                registry,
                object_id,
                property_name,
                property_definition,
            )
            mapping[object_id]["properties"][property_name] = {"column": column}
        sql.extend(lines)
        sql.append("")
    enforcement = {
        constraint_id: {
            "status": "runtime_required",
            "reason": (
                "Semantic constraint is conditional or cross-property and remains "
                "runtime-enforced."
            ),
        }
        for constraint_id in sorted(registry["constraints"])
    }
    return (
        _artifact(
            "semantic.postgresql",
            "database/schema.sql",
            "text/sql",
            "\n".join(sql),
            (*registry["objects"], *registry["types"]),
        ),
        _artifact(
            "semantic.postgresql",
            "database/mapping.json",
            "application/json",
            _json(mapping),
            tuple(registry["objects"]),
        ),
        _artifact(
            "semantic.postgresql",
            "database/enforcement.json",
            "application/json",
            _json(enforcement),
            tuple(registry["constraints"]),
        ),
    )


def _openapi_artifacts(registry: dict[str, Any]) -> tuple[GeneratedArtifact, ...]:
    schemas: dict[str, Any] = {"SemanticDiagnostic": _diagnostic_schema()}
    for type_id, definition in sorted(registry["types"].items()):
        schemas[_schema_name(type_id)] = {
            "type": "string",
            "enum": definition["values"],
            "x-semantic-id": type_id,
        }
    for object_id, definition in sorted(registry["objects"].items()):
        required = [
            name for name, prop in sorted(definition["properties"].items()) if prop.get("required")
        ]
        schemas[_schema_name(object_id)] = {
            "type": "object",
            "x-semantic-id": object_id,
            "required": ["id", *required, "version"],
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                **{
                    name: _openapi_property(registry, prop["type"])
                    for name, prop in sorted(definition["properties"].items())
                },
                "version": {"type": "integer"},
            },
        }
    paths: dict[str, Any] = {}
    for transition_id, transition in sorted(registry["transitions"].items()):
        command = registry["commands"][transition["command"]]
        path = f"/requests/{{id}}/{_command_action(command['name'])}"
        paths[path] = {
            "post": {
                "operationId": command["name"],
                "x-semantic-command": transition["command"],
                "x-semantic-transition": transition_id,
                "responses": {
                    "200": {"description": f"{command['name']} accepted"},
                    "400": {
                        "description": "Semantic command rejected",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SemanticDiagnostic"}
                            }
                        },
                    },
                },
            }
        }
    openapi = {
        "openapi": "3.1.0",
        "info": {
            "title": "Reference Approval Semantic API",
            "version": registry["registry"]["version"],
        },
        "paths": paths,
        "components": {"schemas": schemas},
    }
    return (
        _artifact(
            "semantic.openapi",
            "openapi/openapi.json",
            "application/json",
            _json(openapi),
            (*registry["objects"], *registry["commands"], *registry["transitions"]),
        ),
    )


def _ui_artifacts(registry: dict[str, Any]) -> tuple[GeneratedArtifact, ...]:
    request = registry["objects"]["approval.object.request"]
    lifecycle = registry["behaviors"]["approval.behavior.request_lifecycle"]
    model = {
        "registry": registry["registry"],
        "forms": [
            {
                "id": "generated.form.approval.object.request",
                "subject": "approval.object.request",
                "fields": [
                    {
                        "property": name,
                        "control": (
                            "state"
                            if name == lifecycle["state_property"]
                            else _control(prop["type"])
                        ),
                        "required": bool(prop.get("required")),
                        "readOnly": name == lifecycle["state_property"],
                    }
                    for name, prop in sorted(request["properties"].items())
                ],
            }
        ],
        "actions": [
            {
                "command": transition["command"],
                "transition": transition_id,
                "label": registry["commands"][transition["command"]]["name"].removesuffix(
                    "Request"
                ),
                "availableFrom": transition["from"],
                "runtimeAuthoritative": True,
            }
            for transition_id, transition in sorted(registry["transitions"].items())
        ],
        "validation": [
            {
                "constraintId": constraint_id,
                "clientEnforced": False,
                "runtimeEnforced": True,
                "message": constraint["message"],
            }
            for constraint_id, constraint in sorted(registry["constraints"].items())
        ],
    }
    return (
        _artifact(
            "semantic.ui",
            "ui/model.json",
            "application/json",
            _json(model),
            (
                "approval.object.request",
                "approval.behavior.request_lifecycle",
                *registry["constraints"],
            ),
        ),
    )


def _test_artifacts(registry: dict[str, Any]) -> tuple[GeneratedArtifact, ...]:
    lines = [
        "# Generated semantic behavior contract tests",
        "",
        "These are deterministic test scaffolds. Application fixtures supply concrete objects.",
        "",
    ]
    for constraint_id in sorted(registry["constraints"]):
        lines.extend(
            [
                f"## Constraint `{constraint_id}`",
                "",
                "- Assert the constraint exists in the canonical registry.",
                "- Assert its result type is Boolean.",
                "- Assert passing and failing fixture cases preserve diagnostic identity.",
                "",
            ]
        )
    for transition_id, transition in sorted(registry["transitions"].items()):
        lines.extend(
            [
                f"## Transition `{transition_id}`",
                "",
                f"- Valid source states: `{', '.join(transition['from'])}`.",
                f"- Target state: `{transition['to']}`.",
                f"- Command: `{transition['command']}`.",
                f"- Events: `{', '.join(transition.get('emits', [])) or 'none'}`.",
                "- Assert invalid source states produce no mutation and no events.",
                "",
            ]
        )
    return (
        _artifact(
            "semantic.tests",
            "tests/semantic-contracts.generated.md",
            "text/markdown",
            "\n".join(lines),
            (*registry["constraints"], *registry["transitions"]),
        ),
    )


def _documentation_artifacts(registry: dict[str, Any]) -> tuple[GeneratedArtifact, ...]:
    index = [
        "# Reference Approval Registry",
        "",
        (
            f"Generated from registry `{registry['registry']['id']}` "
            f"version `{registry['registry']['version']}`."
        ),
        "",
        "## Objects",
        "",
        *[f"- `{object_id}`" for object_id in sorted(registry["objects"])],
        "",
        "## Behaviors",
        "",
        *[f"- `{behavior_id}`" for behavior_id in sorted(registry["behaviors"])],
        "",
    ]
    request = registry["objects"]["approval.object.request"]
    request_doc = [
        "# Request",
        "",
        "Semantic ID: `approval.object.request`",
        "",
        request["description"],
        "",
        "## Properties",
        "",
        *[
            f"- `{name}`: `{definition['type']}`"
            for name, definition in sorted(request["properties"].items())
        ],
        "",
        "## Constraints",
        "",
        *[
            f"- `{constraint_id}`"
            for constraint_id, constraint in sorted(registry["constraints"].items())
            if constraint["scope"] == "approval.object.request"
        ],
        "",
    ]
    return (
        _artifact(
            "semantic.documentation",
            "docs/index.md",
            "text/markdown",
            "\n".join(index),
            tuple(registry["objects"]),
        ),
        _artifact(
            "semantic.documentation",
            "docs/objects/approval.object.request.md",
            "text/markdown",
            "\n".join(request_doc),
            ("approval.object.request", *registry["constraints"]),
        ),
    )


def _diagram_artifacts(registry: dict[str, Any]) -> tuple[GeneratedArtifact, ...]:
    behavior_id = "approval.behavior.request_lifecycle"
    behavior = registry["behaviors"][behavior_id]
    lines = ["stateDiagram-v2", f"    [*] --> {behavior['initial_state']}"]
    for transition in registry["transitions"].values():
        for source in transition["from"]:
            command_name = registry["commands"][transition["command"]]["name"]
            lines.append(f"    {source} --> {transition['to']}: {command_name}")
    return (
        _artifact(
            "semantic.diagrams",
            "diagrams/request-lifecycle.mmd",
            "text/vnd.mermaid",
            "\n".join(lines) + "\n",
            (behavior_id, *registry["transitions"]),
        ),
    )


def _ai_context_artifacts(registry: dict[str, Any]) -> tuple[GeneratedArtifact, ...]:
    context = {
        "registry": registry["registry"],
        "objects": {
            object_id: {
                "meaning": definition["description"],
                "properties": sorted(definition["properties"]),
                "constraints": sorted(
                    constraint_id
                    for constraint_id, constraint in registry["constraints"].items()
                    if constraint["scope"] == object_id
                ),
                "behavior": next(
                    (
                        behavior_id
                        for behavior_id, behavior in registry["behaviors"].items()
                        if behavior["subject"] == object_id
                    ),
                    None,
                ),
                "ai_action_model": {
                    "may_suggest": True,
                    "may_execute_with_authorization": False,
                    "must_not_invent_semantics": True,
                    "runtime_is_authoritative": True,
                },
            }
            for object_id, definition in sorted(registry["objects"].items())
        },
    }
    return (
        _artifact(
            "semantic.ai-context",
            "ai/context.json",
            "application/json",
            _json(context),
            (*registry["objects"], *registry["constraints"], *registry["behaviors"]),
        ),
    )


def _coverage(registry: dict[str, Any]) -> list[dict[str, str]]:
    coverage: list[dict[str, str]] = []
    for object_id in sorted(registry["objects"]):
        coverage.append(
            {
                "semanticElementId": object_id,
                "target": "postgresql",
                "status": "fully_enforced",
                "notes": "Object identity and required scalar/reference properties are projected.",
            }
        )
        coverage.append(
            {
                "semanticElementId": object_id,
                "target": "openapi",
                "status": "fully_enforced",
                "notes": "Object schema is projected with semantic traceability extensions.",
            }
        )
        coverage.append(
            {
                "semanticElementId": object_id,
                "target": "migration",
                "status": "partially_enforced",
                "notes": "Semantic diff classifies object/property changes before SQL changes.",
            }
        )
    for constraint_id in sorted(registry["constraints"]):
        for target in ("postgresql", "openapi", "ui"):
            coverage.append(
                {
                    "semanticElementId": constraint_id,
                    "target": target,
                    "status": "runtime_required",
                    "notes": "Conditional semantic rule remains authoritative at runtime.",
                }
            )
    for transition_id in sorted(registry["transitions"]):
        coverage.append(
            {
                "semanticElementId": transition_id,
                "target": "ui",
                "status": "documented_only",
                "notes": "UI action metadata is generated; runtime authorizes and executes.",
            }
        )
        coverage.append(
            {
                "semanticElementId": transition_id,
                "target": "openapi",
                "status": "partially_enforced",
                "notes": "Command operation is exposed; lifecycle validity is runtime-enforced.",
            }
        )
    return coverage


def _artifact(
    generator_id: str,
    path: str,
    media_type: str,
    content: str,
    source_elements: tuple[str, ...],
) -> GeneratedArtifact:
    content = content if content.endswith("\n") else content + "\n"
    return GeneratedArtifact(
        path=path,
        media_type=media_type,
        content=content,
        source_elements=tuple(sorted(source_elements)),
        semantic_hash=_stable_hash(
            {
                "generator": generator_id,
                "path": path,
                "source_elements": sorted(source_elements),
                "content": content,
            }
        ),
        generator_id=generator_id,
    )


def _sql_column(
    registry: dict[str, Any],
    object_id: str,
    property_name: str,
    property_definition: dict[str, Any],
) -> tuple[str, str, str, str | None]:
    property_type = property_definition["type"]
    required = " NOT NULL" if property_definition.get("required") else ""
    unique = " UNIQUE" if property_definition.get("unique") else ""
    if property_type.startswith("Reference<"):
        referenced = property_type.removeprefix("Reference<").removesuffix(">")
        column = f"{property_name}_id"
        constraint = (
            f"    CONSTRAINT fk_{_sql_name(object_id)}_{property_name} "
            f"FOREIGN KEY ({column}) REFERENCES {_sql_name(referenced)}(id)"
        )
        return column, "UUID", required, constraint
    if property_type in registry["types"]:
        values = ", ".join(f"'{value}'" for value in registry["types"][property_type]["values"])
        constraint = (
            f"    CONSTRAINT chk_{_sql_name(object_id)}_{property_name} "
            f"CHECK ({property_name} IN ({values}))"
        )
        return property_name, "TEXT", required + unique, constraint
    return property_name, _sql_type(property_type), required + unique, None


def _sql_type(property_type: str) -> str:
    return {
        "String": "TEXT",
        "Text": "TEXT",
        "Boolean": "BOOLEAN",
        "Timestamp": "TIMESTAMPTZ",
    }[property_type]


def _openapi_property(registry: dict[str, Any], property_type: str) -> dict[str, Any]:
    if property_type.startswith("Reference<"):
        return {"type": "string", "format": "uuid", "x-semantic-reference": property_type[10:-1]}
    if property_type in registry["types"]:
        return {"$ref": f"#/components/schemas/{_schema_name(property_type)}"}
    return {
        "String": {"type": "string"},
        "Text": {"type": "string"},
        "Boolean": {"type": "boolean"},
        "Timestamp": {"type": "string", "format": "date-time"},
    }[property_type]


def _diagnostic_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["code", "severity", "message"],
        "properties": {
            "code": {"type": "string"},
            "severity": {"type": "string"},
            "message": {"type": "string"},
            "semanticElementId": {"type": "string"},
        },
    }


def _control(property_type: str) -> str:
    if property_type == "Text":
        return "textarea"
    if property_type == "Boolean":
        return "checkbox"
    if property_type == "Timestamp":
        return "datetime"
    return "text"


def _command_action(name: str) -> str:
    return name.removesuffix("Request").lower()


def _schema_name(semantic_id: str) -> str:
    return "".join(part.capitalize() for part in semantic_id.rsplit(".", 1)[-1].split("_"))


def _sql_name(semantic_id: str) -> str:
    return semantic_id.replace("approval.object.", "approval_").replace(".", "_")


def _comma_lines(lines: list[str]) -> list[str]:
    return [f"{line}," if index < len(lines) - 1 else line for index, line in enumerate(lines)]


def _generator_records(artifacts: list[GeneratedArtifact]) -> list[dict[str, str]]:
    return [
        {"id": generator_id, "version": GENERATOR_VERSION}
        for generator_id in sorted({artifact.generator_id for artifact in artifacts})
    ]


def _semantic_hash(registry: dict[str, Any]) -> str:
    return f"sha256:{_stable_hash(registry)}"


def _stable_hash(payload: Any) -> str:
    return specification_hash(payload)


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--previous-registry", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = write_generation(
        args.root,
        args.output_root,
        registry_path=args.registry,
        previous_registry_path=args.previous_registry,
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
