import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol
from uuid import UUID

from ai_enterprise.domain.agent_runtime.tool import ToolDefinition, ToolInvocationRequest
from ai_enterprise.domain.organization.authority import AuthorityDecision, AuthorityRequest


@dataclass(frozen=True)
class RuntimeToolManifest:
    id: UUID
    agent_profile_id: UUID
    agent_profile_version_id: UUID
    assignment_id: UUID
    allowed_tools: frozenset[str]
    tool_permissions: frozenset[str]
    status: str


class ToolRegistryPort(Protocol):
    def get_active(self, tool_key: str) -> ToolDefinition | None: ...


class RuntimeSessionPort(Protocol):
    def get_active(self, session_id: UUID) -> RuntimeToolManifest | None: ...


class RuntimeAuthorityPort(Protocol):
    def evaluate(self, request: AuthorityRequest) -> AuthorityDecision: ...


class ArgumentPolicyValidator:
    """Validates schema and narrow, tool-specific scope constraints."""

    def validate(self, *, tool: ToolDefinition, request: ToolInvocationRequest) -> tuple[bool, str]:
        try:
            self._validate_schema(request.arguments, tool.input_schema, path="$")
        except ValueError as exc:
            return False, str(exc)
        policy = tool.argument_policy
        size = len(json.dumps(request.arguments, sort_keys=True, separators=(",", ":")))
        if size > int(policy.get("maximum_input_bytes", 65_536)):
            return False, "TOOL-ARGUMENT-SIZE-EXCEEDED"
        forbidden = set(policy.get("forbidden_argument_keys", ()))
        if forbidden & self._all_keys(request.arguments):
            return False, "TOOL-ARGUMENT-FORBIDDEN-KEY"
        scope_argument = policy.get("scope_id_argument")
        if not isinstance(scope_argument, str):
            return False, "TOOL-SCOPE-POLICY-MISSING"
        if str(request.arguments.get(scope_argument)) != str(request.scope_id):
            return False, "TOOL-ARGUMENT-SCOPE-MISMATCH"
        for argument in policy.get("path_arguments", ()):
            value = request.arguments.get(argument)
            if not isinstance(value, str) or not self._safe_relative_path(value):
                return False, "TOOL-ARGUMENT-PATH-OUT-OF-SCOPE"
            prefixes = tuple(
                str(item).rstrip("/") for item in policy.get("allowed_path_prefixes", ())
            )
            if prefixes and not any(
                value == prefix or value.startswith(f"{prefix}/") for prefix in prefixes
            ):
                return False, "TOOL-ARGUMENT-PATH-OUT-OF-SCOPE"
        command_argument = policy.get("command_id_argument")
        if command_argument is not None:
            allowed = frozenset(policy.get("allowed_command_ids", ()))
            if request.arguments.get(command_argument) not in allowed:
                return False, "TOOL-ARGUMENT-COMMAND-NOT-APPROVED"
        return True, "TOOL-ARGUMENTS-VALID"

    @staticmethod
    def _safe_relative_path(value: str) -> bool:
        path = PurePosixPath(value)
        return (
            bool(value) and not path.is_absolute() and ".." not in path.parts and "\\" not in value
        )

    @classmethod
    def _all_keys(cls, value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(cls._all_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(cls._all_keys(item) for item in value))
        return set()

    @classmethod
    def _validate_schema(cls, value: Any, schema: dict[str, Any], *, path: str) -> None:
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError("TOOL-ARGUMENT-SCHEMA-ENUM")
        expected = schema.get("type")
        expected_types: dict[str, type[Any] | tuple[type[Any], ...]] = {
            "object": dict,
            "array": list,
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "null": type(None),
        }
        if not isinstance(expected, str):
            raise ValueError("TOOL-ARGUMENT-SCHEMA-UNSUPPORTED")
        python_type = expected_types.get(expected)
        if python_type is None:
            raise ValueError("TOOL-ARGUMENT-SCHEMA-UNSUPPORTED")
        if not isinstance(value, python_type) or (
            expected in {"integer", "number"} and isinstance(value, bool)
        ):
            raise ValueError(f"TOOL-ARGUMENT-SCHEMA-TYPE:{path}")
        if expected == "object":
            properties = schema.get("properties")
            required = schema.get("required", ())
            if not isinstance(properties, dict) or not isinstance(required, list):
                raise ValueError("TOOL-ARGUMENT-SCHEMA-INVALID")
            missing = set(required) - set(value)
            if missing:
                raise ValueError("TOOL-ARGUMENT-SCHEMA-REQUIRED")
            if schema.get("additionalProperties") is not False:
                raise ValueError("TOOL-ARGUMENT-SCHEMA-NOT-STRICT")
            if set(value) - set(properties):
                raise ValueError("TOOL-ARGUMENT-SCHEMA-ADDITIONAL")
            for key, item in value.items():
                cls._validate_schema(item, properties[key], path=f"{path}.{key}")
        elif expected == "array":
            items = schema.get("items")
            if not isinstance(items, dict):
                raise ValueError("TOOL-ARGUMENT-SCHEMA-INVALID")
            for index, item in enumerate(value):
                cls._validate_schema(item, items, path=f"{path}[{index}]")


class ToolAuthorizationService:
    def __init__(
        self,
        *,
        tool_registry: ToolRegistryPort,
        sessions: RuntimeSessionPort,
        authority_service: RuntimeAuthorityPort,
        argument_validator: ArgumentPolicyValidator | None = None,
    ) -> None:
        self.tool_registry = tool_registry
        self.sessions = sessions
        self.authority_service = authority_service
        self.argument_validator = argument_validator or ArgumentPolicyValidator()

    def evaluate(self, request: ToolInvocationRequest) -> AuthorityDecision:
        tool = self.tool_registry.get_active(request.tool_key)
        if tool is None or not tool.is_active:
            return self._denied("TOOL-NOT-ACTIVE")
        runtime_session = self.sessions.get_active(request.runtime_session_id)
        if runtime_session is None or runtime_session.status != "active":
            return self._denied("TOOL-RUNTIME-SESSION-INACTIVE")
        if runtime_session.agent_profile_version_id != request.agent_profile_version_id:
            return self._denied("TOOL-RUNTIME-IDENTITY-MISMATCH")
        if runtime_session.assignment_id != request.assignment_id:
            return self._denied("TOOL-RUNTIME-ASSIGNMENT-MISMATCH")
        if request.tool_key not in runtime_session.allowed_tools:
            return self._denied("TOOL-NOT-IN-RUNTIME-MANIFEST")
        authority = self.authority_service.evaluate(
            AuthorityRequest(
                actor_id=runtime_session.agent_profile_id,
                capability=tool.required_capability,
                scope_type=request.scope_type,
                scope_id=request.scope_id,
                action_context={"tool_key": request.tool_key, "arguments": request.arguments},
            )
        )
        if not authority.allowed:
            return authority
        if tool.required_permission not in runtime_session.tool_permissions:
            return self._denied("TOOL-PERMISSION-MISSING", authority.policy_versions)
        arguments_valid, code = self.argument_validator.validate(tool=tool, request=request)
        if not arguments_valid:
            return self._denied(code, authority.policy_versions)
        return AuthorityDecision(True, "TOOL-AUTHORIZED", (), authority.policy_versions)

    @staticmethod
    def _denied(code: str, policy_versions: tuple[str, ...] = ()) -> AuthorityDecision:
        return AuthorityDecision(False, code, ({"code": code},), policy_versions)
