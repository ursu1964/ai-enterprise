from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from ai_enterprise.application.agent_runtime.tool_authorization_service import (
    ArgumentPolicyValidator,
    ToolAuthorizationService,
)
from ai_enterprise.domain.agent_runtime.enums import ToolInvocationStatus
from ai_enterprise.domain.agent_runtime.errors import RegistryIntegrityError, ToolPolicyError
from ai_enterprise.domain.agent_runtime.tool import (
    ToolDefinition,
    ToolInvocationRequest,
    ToolInvocationResult,
)
from ai_enterprise.domain.hashing import hash_json


@dataclass(frozen=True)
class ToolInvocationRecord:
    id: UUID
    runtime_session_id: UUID
    tool_key: str
    tool_version: str
    input_document: dict[str, Any]
    input_hash: str
    authorization_decision: dict[str, Any]
    status: ToolInvocationStatus
    output_document: dict[str, Any] | None = None
    output_hash: str | None = None
    error_document: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class InvocationStore(Protocol):
    def create(self, record: ToolInvocationRecord) -> None: ...

    def replace(self, record: ToolInvocationRecord) -> None: ...


class InMemoryInvocationStore:
    def __init__(self) -> None:
        self.records: dict[UUID, ToolInvocationRecord] = {}

    def create(self, record: ToolInvocationRecord) -> None:
        if record.id in self.records:
            raise ToolPolicyError("TOOL-INVOCATION-DUPLICATE")
        self.records[record.id] = record

    def replace(self, record: ToolInvocationRecord) -> None:
        if record.id not in self.records:
            raise ToolPolicyError("TOOL-INVOCATION-NOT-FOUND")
        self.records[record.id] = record


class InMemoryToolRegistry:
    def __init__(self, definitions: tuple[ToolDefinition, ...] = ()) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ToolDefinition) -> None:
        if not definition.is_active:
            raise RegistryIntegrityError("TOOL-DEFINITION-NOT-ACTIVE")
        existing = self._definitions.get(definition.key)
        if existing is not None and existing.definition_hash != definition.definition_hash:
            raise RegistryIntegrityError("TOOL-DEFINITION-IMMUTABLE")
        self._definitions[definition.key] = definition

    def get_active(self, tool_key: str) -> ToolDefinition | None:
        definition = self._definitions.get(tool_key)
        return definition if definition is not None and definition.is_active else None


_GATEWAY_TOKEN = object()


@dataclass(frozen=True)
class GatewayInvocationContext:
    invocation_id: UUID
    runtime_session_id: UUID
    _token: object

    def assert_gateway(self) -> None:
        if self._token is not _GATEWAY_TOKEN:
            raise ToolPolicyError("TOOL-DIRECT-INFRASTRUCTURE-INVOCATION")


ToolHandler = Callable[[dict[str, Any], GatewayInvocationContext], dict[str, Any]]


class ToolGateway:
    """The sole entry point for policy-bound tool execution and evidence capture."""

    def __init__(
        self,
        *,
        registry: InMemoryToolRegistry,
        authorization: ToolAuthorizationService,
        invocation_store: InvocationStore,
        handlers: dict[tuple[str, str], ToolHandler],
    ) -> None:
        self.registry = registry
        self.authorization = authorization
        self.invocation_store = invocation_store
        self.handlers = handlers.copy()
        self.output_validator = ArgumentPolicyValidator()

    def invoke(self, request: ToolInvocationRequest) -> ToolInvocationResult:
        invocation_id = uuid4()
        tool = self.registry.get_active(request.tool_key)
        version = tool.version if tool is not None else "unknown"
        decision = self.authorization.evaluate(request)
        now = datetime.now(UTC)
        record = ToolInvocationRecord(
            id=invocation_id,
            runtime_session_id=request.runtime_session_id,
            tool_key=request.tool_key,
            tool_version=version,
            input_document=request.arguments,
            input_hash=hash_json(request.arguments),
            authorization_decision={
                "allowed": decision.allowed,
                "code": decision.code,
                "reasons": list(decision.reasons),
                "policy_versions": list(decision.policy_versions),
            },
            status=ToolInvocationStatus.REQUESTED,
            created_at=now,
        )
        self.invocation_store.create(record)
        if not decision.allowed or tool is None:
            record = replace(
                record,
                status=ToolInvocationStatus.DENIED,
                error_document={"code": decision.code},
                completed_at=datetime.now(UTC),
            )
            self.invocation_store.replace(record)
            return self._result(record)
        handler = self.handlers.get((tool.key, tool.version))
        if handler is None:
            record = replace(
                record,
                status=ToolInvocationStatus.FAILED,
                error_document={"code": "TOOL-HANDLER-NOT-REGISTERED"},
                completed_at=datetime.now(UTC),
            )
            self.invocation_store.replace(record)
            return self._result(record)
        record = replace(record, status=ToolInvocationStatus.AUTHORIZED)
        self.invocation_store.replace(record)
        record = replace(
            record, status=ToolInvocationStatus.EXECUTING, started_at=datetime.now(UTC)
        )
        self.invocation_store.replace(record)
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="governed-tool")
        future = executor.submit(
            handler,
            request.arguments.copy(),
            GatewayInvocationContext(invocation_id, request.runtime_session_id, _GATEWAY_TOKEN),
        )
        try:
            output = future.result(timeout=tool.timeout_seconds)
            self.output_validator._validate_schema(output, tool.output_schema, path="$")
            record = replace(
                record,
                status=ToolInvocationStatus.SUCCEEDED,
                output_document=output,
                output_hash=hash_json(output),
                completed_at=datetime.now(UTC),
            )
        except TimeoutError:
            future.cancel()
            record = replace(
                record,
                status=ToolInvocationStatus.TIMED_OUT,
                error_document={"code": "TOOL-EXECUTION-TIMED-OUT"},
                completed_at=datetime.now(UTC),
            )
        except Exception as exc:
            record = replace(
                record,
                status=ToolInvocationStatus.FAILED,
                error_document={"code": "TOOL-EXECUTION-FAILED", "type": type(exc).__name__},
                completed_at=datetime.now(UTC),
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        self.invocation_store.replace(record)
        return self._result(record)

    @staticmethod
    def _result(record: ToolInvocationRecord) -> ToolInvocationResult:
        return ToolInvocationResult(
            invocation_id=record.id,
            status=record.status,
            output=record.output_document,
            output_hash=record.output_hash,
            error=record.error_document,
        )
