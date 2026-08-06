from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.application.r17_execution_planner_runtime import R17ExecutionPlan
from ai_enterprise.application.r18_generator_orchestration_runtime import R18ExecutionResult
from ai_enterprise.domain.specification.kernel import specification_hash

MEMORY_ENGINE_VERSION = "project-memory-context-engine-1.0"
DETERMINISTIC_MEMORY_TIMESTAMP = "1970-01-01T00:00:00Z"

MEMORY_DOMAINS: tuple[str, ...] = (
    "project",
    "architecture",
    "business",
    "execution",
    "artifacts",
    "validation",
    "operations",
    "knowledge",
    "history",
)

RETENTION_CLASSES: tuple[str, ...] = (
    "permanent",
    "archived",
    "confidential",
    "operational",
    "temporary",
)

MEMORY_BACKENDS: tuple[str, ...] = ("filesystem", "postgres", "vector", "custom")
SEMANTIC_INDEX_BACKENDS: tuple[str, ...] = ("deterministic", "pgvector", "opensearch", "custom")
R19_ACTION_ROLES: dict[str, frozenset[str]] = {
    "read": frozenset(
        {
            "platform-admin",
            "memory-admin",
            "memory-reader",
            "memory-writer",
            "memory-service",
            "compliance-officer",
        }
    ),
    "write": frozenset({"platform-admin", "memory-admin", "memory-writer", "memory-service"}),
    "admin": frozenset({"platform-admin", "memory-admin"}),
    "confidential": frozenset({"platform-admin", "memory-admin", "compliance-officer"}),
    "export": frozenset({"platform-admin", "memory-admin", "compliance-officer"}),
}


class R19RelatedObject(BaseModel):
    model_config = ConfigDict(frozen=True)

    object_type: str
    object_id: str
    relation: str


class R19MemoryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_id: str
    project_id: str
    domain: str
    category: str
    timestamp: str
    author: str
    source: str
    related_objects: tuple[R19RelatedObject, ...]
    summary: str
    version: int
    confidence: float = Field(ge=0.0, le=1.0)
    tags: tuple[str, ...]
    retention_class: str
    visibility: str
    legal_hold: bool
    supersedes: str | None
    content: dict[str, Any]
    record_hash: str
    immutable: bool = True


class R19MemoryRelationship(BaseModel):
    model_config = ConfigDict(frozen=True)

    relationship_id: str
    source_memory_id: str
    target_type: str
    target_id: str
    relationship_type: str
    evidence_hash: str
    relationship_hash: str


class R19MemoryIndex(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_project: dict[str, tuple[str, ...]]
    by_domain: dict[str, tuple[str, ...]]
    by_tag: dict[str, tuple[str, ...]]
    by_source: dict[str, tuple[str, ...]]
    by_related_object: dict[str, tuple[str, ...]]
    latest_by_chain: dict[str, str]
    index_hash: str


class R19MemoryStore(BaseModel):
    model_config = ConfigDict(frozen=True)

    engine_version: str
    records: tuple[R19MemoryRecord, ...]
    relationships: tuple[R19MemoryRelationship, ...]
    index: R19MemoryIndex
    store_hash: str


class R19MemoryQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str | None = None
    text: str | None = None
    domains: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    related_object: R19RelatedObject | None = None
    include_confidential: bool = False
    limit: int = Field(default=20, ge=1, le=200)


class R19MemoryQueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: tuple[R19MemoryRecord, ...]
    relationships: tuple[R19MemoryRelationship, ...]
    query_hash: str


class R19ContextRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_task: dict[str, Any]
    knowledge_graph: dict[str, Any] | None = None
    project_id: str | None = None
    domains: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    max_records: int = Field(default=12, ge=1, le=100)
    include_confidential: bool = False


class R19ContextBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    project_id: str | None
    selected_memory_ids: tuple[str, ...]
    memory_summaries: tuple[dict[str, Any], ...]
    knowledge_references: tuple[dict[str, str], ...]
    execution_policies: tuple[dict[str, Any], ...]
    token_estimate: int
    context_hash: str


class R19MemoryExport(BaseModel):
    model_config = ConfigDict(frozen=True)

    engine_version: str
    exported_at: str
    store_hash: str
    records: tuple[R19MemoryRecord, ...]
    relationships: tuple[R19MemoryRelationship, ...]
    export_hash: str


class R19MemoryValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    diagnostics: tuple[dict[str, str], ...]
    report_hash: str


class R19MemoryBackendConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_backend: str = "filesystem"
    semantic_index_backend: str = "deterministic"
    endpoint_reference: str | None = None
    database_reference: str | None = None
    index_reference: str | None = None
    credentials_reference: str | None = None
    deployment_evidence_ref: str | None = None
    connectivity_evidence_ref: str | None = None
    encryption_required: bool = False
    kms_key_ref: str | None = None
    rbac_policy_ref: str | None = None
    retention_policy_ref: str | None = None


class R19MemoryReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    ready: bool
    backend_config: R19MemoryBackendConfig
    checks: dict[str, dict[str, Any]]
    diagnostics: tuple[dict[str, str], ...]
    readiness_hash: str


class R19AuthorizationDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    action: str
    actor_type: str
    actor_role: str
    confidential_access: bool
    code: str
    reasons: tuple[dict[str, str], ...]
    decision_hash: str


class R19SemanticIndexEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_id: str
    embedding_ref: str
    text_hash: str
    backend: str
    index_hash: str


class R19SemanticIndexReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: str
    entries: tuple[R19SemanticIndexEntry, ...]
    diagnostics: tuple[dict[str, str], ...]
    report_hash: str


def r19_empty_store() -> R19MemoryStore:
    return _store((), ())


def r19_store_memory(
    store: dict[str, Any] | R19MemoryStore | None,
    *,
    project_id: str,
    domain: str,
    category: str,
    author: str,
    source: str,
    summary: str,
    related_objects: list[dict[str, Any]] | tuple[R19RelatedObject, ...] = (),
    content: dict[str, Any] | None = None,
    tags: list[str] | tuple[str, ...] = (),
    confidence: float = 1.0,
    retention_class: str = "permanent",
    visibility: str = "internal",
    legal_hold: bool = False,
    timestamp: str = DETERMINISTIC_MEMORY_TIMESTAMP,
) -> R19MemoryStore:
    current = _coerce_store(store)
    record = _memory_record(
        project_id=project_id,
        domain=domain,
        category=category,
        author=author,
        source=source,
        summary=summary,
        related_objects=tuple(
            item if isinstance(item, R19RelatedObject) else R19RelatedObject.model_validate(item)
            for item in related_objects
        ),
        content=content or {},
        tags=tuple(str(item) for item in tags),
        confidence=confidence,
        retention_class=retention_class,
        visibility=visibility,
        legal_hold=legal_hold,
        timestamp=timestamp,
        supersedes=None,
        version=1,
    )
    return _store((*current.records, record), current.relationships)


def r19_update_memory(
    store: dict[str, Any] | R19MemoryStore,
    *,
    memory_id: str,
    author: str,
    summary: str,
    content: dict[str, Any],
    tags: list[str] | tuple[str, ...] | None = None,
    timestamp: str = DETERMINISTIC_MEMORY_TIMESTAMP,
) -> R19MemoryStore:
    current = _coerce_store(store)
    previous = _record_by_id(current, memory_id)
    next_version = (
        max((item.version for item in _history_records(current, memory_id)), default=0) + 1
    )
    record = _memory_record(
        project_id=previous.project_id,
        domain=previous.domain,
        category=previous.category,
        author=author,
        source=previous.source,
        summary=summary,
        related_objects=previous.related_objects,
        content=content,
        tags=tuple(tags) if tags is not None else previous.tags,
        confidence=previous.confidence,
        retention_class=previous.retention_class,
        visibility=previous.visibility,
        legal_hold=previous.legal_hold,
        timestamp=timestamp,
        supersedes=memory_id,
        version=next_version,
    )
    relationship = _relationship(
        record.memory_id,
        "memory",
        previous.memory_id,
        "supersedes",
        {"new_record_hash": record.record_hash, "old_record_hash": previous.record_hash},
    )
    return _store((*current.records, record), (*current.relationships, relationship))


def r19_relate_memory(
    store: dict[str, Any] | R19MemoryStore,
    *,
    source_memory_id: str,
    target_type: str,
    target_id: str,
    relationship_type: str,
    evidence: dict[str, Any] | None = None,
) -> R19MemoryStore:
    current = _coerce_store(store)
    _record_by_id(current, source_memory_id)
    relationship = _relationship(
        source_memory_id,
        target_type,
        target_id,
        relationship_type,
        evidence or {},
    )
    return _store(current.records, (*current.relationships, relationship))


def r19_query_memory(
    store: dict[str, Any] | R19MemoryStore,
    query: dict[str, Any] | R19MemoryQuery,
) -> R19MemoryQueryResult:
    current = _coerce_store(store)
    model = query if isinstance(query, R19MemoryQuery) else R19MemoryQuery.model_validate(query)
    terms = tuple(_tokens(model.text or ""))
    scored: list[tuple[int, R19MemoryRecord]] = []
    for record in current.records:
        if not _visible(record, model.include_confidential):
            continue
        if model.project_id and record.project_id != model.project_id:
            continue
        if model.domains and record.domain not in model.domains:
            continue
        if model.categories and record.category not in model.categories:
            continue
        if model.tags and not set(model.tags).issubset(set(record.tags)):
            continue
        if model.sources and record.source not in model.sources:
            continue
        if model.related_object and not any(
            related.object_type == model.related_object.object_type
            and related.object_id == model.related_object.object_id
            for related in record.related_objects
        ):
            continue
        score = _score(record, terms)
        if terms and score == 0:
            continue
        scored.append((score, record))
    records = tuple(
        record
        for _, record in sorted(
            scored,
            key=lambda item: (-item[0], item[1].timestamp, item[1].memory_id),
        )[: model.limit]
    )
    memory_ids = {item.memory_id for item in records}
    relationships = tuple(
        item
        for item in current.relationships
        if item.source_memory_id in memory_ids or item.target_id in memory_ids
    )
    payload = {
        "query": model.model_dump(mode="json"),
        "record_ids": [item.memory_id for item in records],
        "relationship_ids": [item.relationship_id for item in relationships],
    }
    return R19MemoryQueryResult(
        records=records,
        relationships=relationships,
        query_hash=specification_hash(payload),
    )


def r19_context(
    store: dict[str, Any] | R19MemoryStore,
    request: dict[str, Any] | R19ContextRequest,
) -> R19ContextBundle:
    current = _coerce_store(store)
    model = (
        request
        if isinstance(request, R19ContextRequest)
        else R19ContextRequest.model_validate(request)
    )
    task = model.execution_task
    task_id = str(task.get("task_id", "unknown-task"))
    node_id = str(task.get("knowledge_node_id", ""))
    query = R19MemoryQuery(
        project_id=model.project_id,
        text=" ".join(
            str(value)
            for value in (
                task.get("task_type"),
                task.get("stage_id"),
                task.get("generator"),
                node_id,
            )
            if value
        ),
        domains=model.domains,
        tags=model.tags,
        related_object=(
            R19RelatedObject(object_type="knowledge_node", object_id=node_id, relation="context")
            if node_id
            else None
        ),
        include_confidential=model.include_confidential,
        limit=model.max_records,
    )
    selected = r19_query_memory(current, query).records
    knowledge_references = _knowledge_references(model.knowledge_graph, node_id)
    summaries = tuple(
        {
            "memory_id": record.memory_id,
            "domain": record.domain,
            "category": record.category,
            "summary": record.summary,
            "confidence": record.confidence,
            "tags": list(record.tags),
        }
        for record in selected
    )
    policies = tuple(
        {"memory_id": record.memory_id, "retention_class": record.retention_class}
        for record in selected
        if record.domain in {"architecture", "business", "operations"}
    )
    payload = {
        "task_id": task_id,
        "project_id": model.project_id,
        "selected_memory_ids": [item.memory_id for item in selected],
        "memory_summaries": summaries,
        "knowledge_references": knowledge_references,
        "execution_policies": policies,
    }
    return R19ContextBundle(
        task_id=task_id,
        project_id=model.project_id,
        selected_memory_ids=tuple(item.memory_id for item in selected),
        memory_summaries=summaries,
        knowledge_references=knowledge_references,
        execution_policies=policies,
        token_estimate=len(json.dumps(payload, sort_keys=True)),
        context_hash=specification_hash(payload),
    )


def r19_history(
    store: dict[str, Any] | R19MemoryStore,
    memory_id: str,
) -> tuple[R19MemoryRecord, ...]:
    return _history_records(_coerce_store(store), memory_id)


def r19_export_memory(store: dict[str, Any] | R19MemoryStore) -> R19MemoryExport:
    current = _coerce_store(store)
    payload = {
        "engine_version": current.engine_version,
        "exported_at": DETERMINISTIC_MEMORY_TIMESTAMP,
        "store_hash": current.store_hash,
        "records": [item.model_dump(mode="json") for item in current.records],
        "relationships": [item.model_dump(mode="json") for item in current.relationships],
    }
    return R19MemoryExport(
        **payload,
        export_hash=specification_hash(payload),
    )


def r19_validate_store(store: dict[str, Any] | R19MemoryStore) -> R19MemoryValidationReport:
    current = _coerce_store(store)
    diagnostics: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for record in current.records:
        if record.memory_id in seen_ids:
            diagnostics.append(_diag("fatal", "R19-DUPLICATE-MEMORY-ID", record.memory_id))
        seen_ids.add(record.memory_id)
        if record.domain not in MEMORY_DOMAINS:
            diagnostics.append(_diag("fatal", "R19-UNKNOWN-DOMAIN", record.memory_id))
        if record.retention_class not in RETENTION_CLASSES:
            diagnostics.append(_diag("fatal", "R19-UNKNOWN-RETENTION", record.memory_id))
        expected = _record_hash(record)
        if record.record_hash != expected:
            diagnostics.append(_diag("fatal", "R19-RECORD-HASH-MISMATCH", record.memory_id))
    for relationship in current.relationships:
        if relationship.source_memory_id not in seen_ids:
            diagnostics.append(
                _diag("fatal", "R19-RELATIONSHIP-SOURCE-MISSING", relationship.relationship_id)
            )
    payload = {
        "valid": not diagnostics,
        "diagnostics": diagnostics,
    }
    return R19MemoryValidationReport(
        valid=not diagnostics,
        diagnostics=tuple(diagnostics),
        report_hash=specification_hash(payload),
    )


def r19_memory_readiness(
    config: dict[str, Any] | R19MemoryBackendConfig | None = None,
) -> R19MemoryReadiness:
    model = (
        config
        if isinstance(config, R19MemoryBackendConfig)
        else R19MemoryBackendConfig.model_validate(config or {})
    )
    checks: dict[str, dict[str, Any]] = {}
    diagnostics: list[dict[str, str]] = []

    checks["memory_backend"] = {
        "ok": model.memory_backend in MEMORY_BACKENDS,
        "value": model.memory_backend,
    }
    if not checks["memory_backend"]["ok"]:
        diagnostics.append(_diag("fatal", "R19-BACKEND-UNKNOWN", model.memory_backend))

    checks["semantic_index_backend"] = {
        "ok": model.semantic_index_backend in SEMANTIC_INDEX_BACKENDS,
        "value": model.semantic_index_backend,
    }
    if not checks["semantic_index_backend"]["ok"]:
        diagnostics.append(
            _diag("fatal", "R19-SEMANTIC-INDEX-BACKEND-UNKNOWN", model.semantic_index_backend)
        )

    external_backend = model.memory_backend in {"postgres", "vector", "custom"}
    checks["backend_endpoint"] = {
        "ok": not external_backend or bool(model.endpoint_reference),
        "required": external_backend,
        "value": model.endpoint_reference,
    }
    if not checks["backend_endpoint"]["ok"]:
        diagnostics.append(_diag("fatal", "R19-BACKEND-ENDPOINT-MISSING", model.memory_backend))

    checks["backend_credentials"] = {
        "ok": not external_backend or bool(model.credentials_reference),
        "required": external_backend,
        "value": model.credentials_reference,
    }
    if not checks["backend_credentials"]["ok"]:
        diagnostics.append(_diag("fatal", "R19-BACKEND-CREDENTIALS-MISSING", model.memory_backend))

    production_backend = model.memory_backend != "filesystem"
    checks["deployment_evidence"] = {
        "ok": not production_backend or bool(model.deployment_evidence_ref),
        "required": production_backend,
        "value": model.deployment_evidence_ref,
    }
    if not checks["deployment_evidence"]["ok"]:
        diagnostics.append(_diag("fatal", "R19-DEPLOYMENT-EVIDENCE-MISSING", model.memory_backend))

    checks["connectivity_evidence"] = {
        "ok": not production_backend or bool(model.connectivity_evidence_ref),
        "required": production_backend,
        "value": model.connectivity_evidence_ref,
    }
    if not checks["connectivity_evidence"]["ok"]:
        diagnostics.append(
            _diag("fatal", "R19-CONNECTIVITY-EVIDENCE-MISSING", model.memory_backend)
        )

    checks["kms"] = {
        "ok": not model.encryption_required or bool(model.kms_key_ref),
        "required": model.encryption_required,
        "value": model.kms_key_ref,
    }
    if not checks["kms"]["ok"]:
        diagnostics.append(_diag("fatal", "R19-KMS-KEY-MISSING", "kms_key_ref"))

    checks["rbac_policy"] = {
        "ok": bool(model.rbac_policy_ref),
        "required": True,
        "value": model.rbac_policy_ref,
    }
    if not checks["rbac_policy"]["ok"]:
        diagnostics.append(_diag("warning", "R19-RBAC-POLICY-REF-MISSING", "rbac_policy_ref"))

    semantic_external = model.semantic_index_backend in {"pgvector", "opensearch", "custom"}
    checks["semantic_index_reference"] = {
        "ok": not semantic_external or bool(model.index_reference),
        "required": semantic_external,
        "value": model.index_reference,
    }
    if not checks["semantic_index_reference"]["ok"]:
        diagnostics.append(
            _diag("fatal", "R19-SEMANTIC-INDEX-REFERENCE-MISSING", model.semantic_index_backend)
        )

    fatal = any(item["severity"] == "fatal" for item in diagnostics)
    payload = {
        "ready": not fatal,
        "backend_config": model.model_dump(mode="json"),
        "checks": checks,
        "diagnostics": diagnostics,
    }
    return R19MemoryReadiness(
        ready=not fatal,
        backend_config=model,
        checks=checks,
        diagnostics=tuple(diagnostics),
        readiness_hash=specification_hash(payload),
    )


def r19_authorize_memory_action(
    *,
    action: str,
    actor_type: str,
    actor_role: str,
    include_confidential: bool = False,
) -> R19AuthorizationDecision:
    normalized_action = action if action in R19_ACTION_ROLES else "read"
    reasons: list[dict[str, str]] = []
    allowed_roles = R19_ACTION_ROLES[normalized_action]
    role_allowed = actor_role in allowed_roles
    type_allowed = actor_type in {"human", "service"}
    confidential_allowed = (
        not include_confidential or actor_role in R19_ACTION_ROLES["confidential"]
    )
    if not type_allowed:
        reasons.append({"code": "R19-ACTOR-TYPE-DENIED", "detail": actor_type})
    if not role_allowed:
        reasons.append({"code": "R19-ROLE-DENIED", "detail": actor_role})
    if not confidential_allowed:
        reasons.append({"code": "R19-CONFIDENTIAL-ACCESS-DENIED", "detail": actor_role})
    allowed = type_allowed and role_allowed and confidential_allowed
    payload = {
        "allowed": allowed,
        "action": normalized_action,
        "actor_type": actor_type,
        "actor_role": actor_role,
        "confidential_access": include_confidential,
        "code": "R19-AUTHORIZED" if allowed else "R19-AUTHORIZATION-DENIED",
        "reasons": reasons,
    }
    return R19AuthorizationDecision(
        **payload,
        decision_hash=specification_hash(payload),
    )


def r19_semantic_index_report(
    store: dict[str, Any] | R19MemoryStore,
    config: dict[str, Any] | R19MemoryBackendConfig | None = None,
) -> R19SemanticIndexReport:
    current = _coerce_store(store)
    backend_config = (
        config
        if isinstance(config, R19MemoryBackendConfig)
        else R19MemoryBackendConfig.model_validate(config or {})
    )
    readiness = r19_memory_readiness(backend_config)
    diagnostics: list[dict[str, str]] = [
        item for item in readiness.diagnostics if item["code"].startswith("R19-SEMANTIC")
    ]
    entries = tuple(
        R19SemanticIndexEntry(
            memory_id=record.memory_id,
            embedding_ref=(
                f"{backend_config.semantic_index_backend}:"
                f"{backend_config.index_reference or 'local'}:{record.memory_id}"
            ),
            text_hash=specification_hash(
                {
                    "summary": record.summary,
                    "tags": record.tags,
                    "content": record.content,
                }
            ),
            backend=backend_config.semantic_index_backend,
            index_hash=specification_hash(
                {
                    "memory_id": record.memory_id,
                    "backend": backend_config.semantic_index_backend,
                    "index_reference": backend_config.index_reference,
                }
            ),
        )
        for record in current.records
    )
    payload = {
        "backend": backend_config.semantic_index_backend,
        "entries": [item.model_dump(mode="json") for item in entries],
        "diagnostics": diagnostics,
    }
    return R19SemanticIndexReport(
        backend=backend_config.semantic_index_backend,
        entries=entries,
        diagnostics=tuple(diagnostics),
        report_hash=specification_hash(payload),
    )


def r19_production_validate_store(
    store: dict[str, Any] | R19MemoryStore,
    config: dict[str, Any] | R19MemoryBackendConfig | None = None,
) -> R19MemoryValidationReport:
    base = r19_validate_store(store)
    readiness = r19_memory_readiness(config)
    semantic = r19_semantic_index_report(store, config)
    diagnostics = (
        *base.diagnostics,
        *readiness.diagnostics,
        *semantic.diagnostics,
    )
    payload = {
        "valid": not any(item["severity"] == "fatal" for item in diagnostics),
        "diagnostics": diagnostics,
    }
    return R19MemoryValidationReport(
        valid=not any(item["severity"] == "fatal" for item in diagnostics),
        diagnostics=tuple(diagnostics),
        report_hash=specification_hash(payload),
    )


def r19_ingest_r17_execution_plan(
    store: dict[str, Any] | R19MemoryStore | None,
    plan: dict[str, Any] | R17ExecutionPlan,
    *,
    project_id: str,
    author: str,
) -> R19MemoryStore:
    model = plan if isinstance(plan, R17ExecutionPlan) else R17ExecutionPlan.model_validate(plan)
    current = _coerce_store(store)
    records = [
        _memory_record(
            project_id=project_id,
            domain="execution",
            category="execution-plan",
            author=author,
            source="r17.execution-planner",
            summary=f"Execution plan {model.plan_id} created with {len(model.tasks)} tasks.",
            related_objects=(
                R19RelatedObject(
                    object_type="execution_plan", object_id=model.plan_id, relation="records"
                ),
            ),
            content=model.model_dump(mode="json"),
            tags=("r17", "execution-plan", model.graph_version),
            confidence=1.0,
            retention_class="permanent",
            visibility="internal",
            legal_hold=False,
            timestamp=model.created_at,
            supersedes=None,
            version=1,
        )
    ]
    for decision in model.decision_log:
        records.append(
            _memory_record(
                project_id=project_id,
                domain="architecture",
                category="ai-decision",
                author=author,
                source="r17.decision-log",
                summary=decision.rationale,
                related_objects=(
                    R19RelatedObject(
                        object_type="execution_plan",
                        object_id=model.plan_id,
                        relation="explains",
                    ),
                ),
                content=decision.model_dump(mode="json"),
                tags=("r17", "decision", decision.category),
                confidence=1.0,
                retention_class="permanent",
                visibility="internal",
                legal_hold=False,
                timestamp=model.created_at,
                supersedes=None,
                version=1,
            )
        )
    return _store((*current.records, *records), current.relationships)


def r19_ingest_r18_execution_result(
    store: dict[str, Any] | R19MemoryStore | None,
    result: dict[str, Any] | R18ExecutionResult,
    *,
    project_id: str,
    author: str,
) -> R19MemoryStore:
    model = (
        result
        if isinstance(result, R18ExecutionResult)
        else R18ExecutionResult.model_validate(result)
    )
    current = _coerce_store(store)
    records: list[R19MemoryRecord] = [
        _memory_record(
            project_id=project_id,
            domain="execution",
            category="execution-result",
            author=author,
            source="r18.generator-orchestrator",
            summary=f"Execution {model.execution_id} finished with status {model.status}.",
            related_objects=(
                R19RelatedObject(
                    object_type="execution", object_id=model.execution_id, relation="records"
                ),
                R19RelatedObject(
                    object_type="execution_plan", object_id=model.plan_id, relation="implements"
                ),
            ),
            content=model.model_dump(mode="json"),
            tags=("r18", "execution", model.status),
            confidence=1.0,
            retention_class="permanent",
            visibility="internal",
            legal_hold=False,
            timestamp=DETERMINISTIC_MEMORY_TIMESTAMP,
            supersedes=None,
            version=1,
        )
    ]
    for task_record in model.task_records:
        records.append(
            _memory_record(
                project_id=project_id,
                domain="execution",
                category="task-execution",
                author=author,
                source="r18.task-record",
                summary=f"Task {task_record.task_id} executed by {task_record.generator_id}.",
                related_objects=(
                    R19RelatedObject(
                        object_type="execution_task",
                        object_id=task_record.task_id,
                        relation="records",
                    ),
                    R19RelatedObject(
                        object_type="generator",
                        object_id=task_record.generator_id,
                        relation="produced-by",
                    ),
                ),
                content=task_record.model_dump(mode="json"),
                tags=("r18", "task", task_record.status),
                confidence=1.0,
                retention_class="operational",
                visibility="internal",
                legal_hold=False,
                timestamp=DETERMINISTIC_MEMORY_TIMESTAMP,
                supersedes=None,
                version=1,
            )
        )
        for artifact in task_record.artifacts:
            records.append(
                _memory_record(
                    project_id=project_id,
                    domain="artifacts",
                    category="generated-artifact",
                    author=author,
                    source="r18.artifact-repository",
                    summary=(
                        f"Artifact {artifact.artifact_id} was produced by "
                        f"{artifact.generator_id} for {artifact.knowledge_node_id}."
                    ),
                    related_objects=(
                        R19RelatedObject(
                            object_type="artifact",
                            object_id=artifact.artifact_id,
                            relation="records",
                        ),
                        R19RelatedObject(
                            object_type="knowledge_node",
                            object_id=artifact.knowledge_node_id,
                            relation="traceable-to",
                        ),
                        R19RelatedObject(
                            object_type="execution_task",
                            object_id=artifact.execution_task_id,
                            relation="produced-by",
                        ),
                    ),
                    content=artifact.model_dump(mode="json"),
                    tags=("r18", "artifact", artifact.artifact_type),
                    confidence=1.0,
                    retention_class="permanent",
                    visibility="internal",
                    legal_hold=False,
                    timestamp=DETERMINISTIC_MEMORY_TIMESTAMP,
                    supersedes=None,
                    version=1,
                )
            )
    return _store((*current.records, *records), current.relationships)


def r19_write_store(store: dict[str, Any] | R19MemoryStore, path: Path) -> str:
    current = _coerce_store(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = current.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return current.store_hash


def r19_read_store(path: Path) -> R19MemoryStore:
    if not path.exists():
        return r19_empty_store()
    return R19MemoryStore.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _memory_record(
    *,
    project_id: str,
    domain: str,
    category: str,
    author: str,
    source: str,
    summary: str,
    related_objects: tuple[R19RelatedObject, ...],
    content: dict[str, Any],
    tags: tuple[str, ...],
    confidence: float,
    retention_class: str,
    visibility: str,
    legal_hold: bool,
    timestamp: str,
    supersedes: str | None,
    version: int,
) -> R19MemoryRecord:
    payload = {
        "project_id": project_id,
        "domain": domain,
        "category": category,
        "timestamp": timestamp,
        "author": author,
        "source": source,
        "related_objects": [item.model_dump(mode="json") for item in related_objects],
        "summary": summary,
        "version": version,
        "confidence": confidence,
        "tags": tuple(sorted(set(tags))),
        "retention_class": retention_class,
        "visibility": visibility,
        "legal_hold": legal_hold,
        "supersedes": supersedes,
        "content": content,
    }
    record_hash = specification_hash(payload)
    return R19MemoryRecord(
        memory_id=f"memory-{record_hash[:16]}",
        record_hash=record_hash,
        immutable=True,
        **payload,
    )


def _relationship(
    source_memory_id: str,
    target_type: str,
    target_id: str,
    relationship_type: str,
    evidence: dict[str, Any],
) -> R19MemoryRelationship:
    evidence_hash = specification_hash(evidence)
    payload = {
        "source_memory_id": source_memory_id,
        "target_type": target_type,
        "target_id": target_id,
        "relationship_type": relationship_type,
        "evidence_hash": evidence_hash,
    }
    relationship_hash = specification_hash(payload)
    return R19MemoryRelationship(
        relationship_id=f"memory-rel-{relationship_hash[:16]}",
        relationship_hash=relationship_hash,
        **payload,
    )


def _store(
    records: tuple[R19MemoryRecord, ...],
    relationships: tuple[R19MemoryRelationship, ...],
) -> R19MemoryStore:
    unique_records = tuple({item.memory_id: item for item in records}.values())
    unique_relationships = tuple({item.relationship_id: item for item in relationships}.values())
    sorted_records = tuple(sorted(unique_records, key=lambda item: item.memory_id))
    sorted_relationships = tuple(
        sorted(unique_relationships, key=lambda item: item.relationship_id)
    )
    index = _index(sorted_records)
    payload = {
        "engine_version": MEMORY_ENGINE_VERSION,
        "records": [item.model_dump(mode="json") for item in sorted_records],
        "relationships": [item.model_dump(mode="json") for item in sorted_relationships],
        "index": index.model_dump(mode="json"),
    }
    return R19MemoryStore(
        engine_version=MEMORY_ENGINE_VERSION,
        records=sorted_records,
        relationships=sorted_relationships,
        index=index,
        store_hash=specification_hash(payload),
    )


def _index(records: tuple[R19MemoryRecord, ...]) -> R19MemoryIndex:
    by_project: dict[str, list[str]] = {}
    by_domain: dict[str, list[str]] = {}
    by_tag: dict[str, list[str]] = {}
    by_source: dict[str, list[str]] = {}
    by_related_object: dict[str, list[str]] = {}
    latest_by_chain: dict[str, str] = {}
    for record in records:
        by_project.setdefault(record.project_id, []).append(record.memory_id)
        by_domain.setdefault(record.domain, []).append(record.memory_id)
        by_source.setdefault(record.source, []).append(record.memory_id)
        for tag in record.tags:
            by_tag.setdefault(tag, []).append(record.memory_id)
        for related in record.related_objects:
            key = f"{related.object_type}:{related.object_id}"
            by_related_object.setdefault(key, []).append(record.memory_id)
        chain_root = _chain_root(records, record)
        latest = latest_by_chain.get(chain_root)
        if latest is None or _record_by_id_from_records(records, latest).version < record.version:
            latest_by_chain[chain_root] = record.memory_id
    payload = {
        "by_project": _freeze_index(by_project),
        "by_domain": _freeze_index(by_domain),
        "by_tag": _freeze_index(by_tag),
        "by_source": _freeze_index(by_source),
        "by_related_object": _freeze_index(by_related_object),
        "latest_by_chain": dict(sorted(latest_by_chain.items())),
    }
    return R19MemoryIndex(
        **payload,
        index_hash=specification_hash(payload),
    )


def _coerce_store(store: dict[str, Any] | R19MemoryStore | None) -> R19MemoryStore:
    if store is None:
        return r19_empty_store()
    if isinstance(store, R19MemoryStore):
        return store
    return R19MemoryStore.model_validate(store)


def _record_by_id(store: R19MemoryStore, memory_id: str) -> R19MemoryRecord:
    for record in store.records:
        if record.memory_id == memory_id:
            return record
    raise ValueError(f"Memory record {memory_id} does not exist")


def _record_by_id_from_records(
    records: tuple[R19MemoryRecord, ...],
    memory_id: str,
) -> R19MemoryRecord:
    for record in records:
        if record.memory_id == memory_id:
            return record
    raise ValueError(f"Memory record {memory_id} does not exist")


def _history_records(
    store: R19MemoryStore,
    memory_id: str,
) -> tuple[R19MemoryRecord, ...]:
    target = _record_by_id(store, memory_id)
    chain_root = _chain_root(store.records, target)
    return tuple(
        sorted(
            (
                record
                for record in store.records
                if _chain_root(store.records, record) == chain_root
            ),
            key=lambda item: item.version,
        )
    )


def _chain_root(records: tuple[R19MemoryRecord, ...], record: R19MemoryRecord) -> str:
    current = record
    seen: set[str] = set()
    while current.supersedes and current.supersedes not in seen:
        seen.add(current.memory_id)
        current = _record_by_id_from_records(records, current.supersedes)
    return current.memory_id


def _freeze_index(value: dict[str, list[str]]) -> dict[str, tuple[str, ...]]:
    return {key: tuple(sorted(set(items))) for key, items in sorted(value.items())}


def _record_hash(record: R19MemoryRecord) -> str:
    payload = record.model_dump(mode="json")
    payload.pop("memory_id")
    payload.pop("record_hash")
    payload.pop("immutable")
    return specification_hash(payload)


def _score(record: R19MemoryRecord, terms: tuple[str, ...]) -> int:
    if not terms:
        return 1
    haystack = " ".join(
        [
            record.summary,
            record.category,
            record.domain,
            record.source,
            " ".join(record.tags),
            json.dumps(record.content, sort_keys=True),
        ]
    ).lower()
    return sum(1 for term in terms if term in haystack)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in "".join(char.lower() if char.isalnum() else " " for char in value).split()
        if token
    )


def _visible(record: R19MemoryRecord, include_confidential: bool) -> bool:
    return include_confidential or (
        record.retention_class != "confidential" and record.visibility != "confidential"
    )


def _knowledge_references(
    graph: dict[str, Any] | None,
    node_id: str,
) -> tuple[dict[str, str], ...]:
    if not graph or not node_id:
        return ()
    refs: list[dict[str, str]] = []
    for node in graph.get("nodes", []):
        if isinstance(node, dict) and str(node.get("id")) == node_id:
            refs.append(
                {
                    "object_type": "knowledge_node",
                    "object_id": str(node.get("id")),
                    "graph_hash": str(graph.get("graph_hash", "")),
                }
            )
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        if str(edge.get("source")) == node_id or str(edge.get("target")) == node_id:
            refs.append(
                {
                    "object_type": "knowledge_edge",
                    "object_id": str(edge.get("id")),
                    "relationship_type": str(edge.get("relationship_type")),
                }
            )
    return tuple(refs)


def _diag(severity: str, code: str, path: str) -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "message": f"{code} at {path}",
        "path": path,
    }
