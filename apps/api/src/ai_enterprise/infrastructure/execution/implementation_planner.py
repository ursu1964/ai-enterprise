from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from crewai import LLM

from ai_enterprise.config import Settings
from ai_enterprise.domain.execution.exceptions import ImplementationPlanError
from ai_enterprise.domain.execution.policies import (
    DEFAULT_FORBIDDEN_PATHS,
    ExecutionScope,
)

MAXIMUM_EDIT_BYTES = 200_000
MAXIMUM_TOTAL_EDITS = 50


@dataclass(frozen=True, slots=True)
class EditOperation:
    path: str
    mode: str
    content: str


@dataclass(frozen=True, slots=True)
class ImplementationPlan:
    edits: tuple[EditOperation, ...]
    raw_json: str


class ImplementationPlanner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def plan(
        self,
        *,
        contract: dict[str, Any],
        tracked_files: list[str],
    ) -> ImplementationPlan:
        llm = LLM(
            model=self._settings.ollama_model,
            base_url=self._settings.ollama_base_url,
            temperature=0.0,
            timeout=900,
            additional_params={
                "extra_body": {
                    "num_ctx": 16384,
                    "num_predict": 8192,
                },
            },
        )

        prompt = self._build_prompt(
            contract=contract,
            tracked_files=tracked_files,
        )

        try:
            raw = llm.call(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            )
        except Exception as exc:
            raise ImplementationPlanError(
                f"Implementation planner LLM call failed: {exc}"
            ) from exc

        raw_json = str(raw).strip()

        if not raw_json:
            raise ImplementationPlanError(
                "Implementation planner returned an empty result"
            )

        edits = self._parse_and_validate(raw_json, contract)

        return ImplementationPlan(edits=edits, raw_json=raw_json)

    def _parse_and_validate(
        self,
        raw_json: str,
        contract: dict[str, Any],
    ) -> tuple[EditOperation, ...]:
        try:
            payload = json.loads(self._strip_code_fence(raw_json))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ImplementationPlanError(
                f"Implementation planner returned invalid JSON: {exc}"
            ) from exc

        if isinstance(payload, dict) and "edits" in payload:
            raw_edits = payload["edits"]
        elif isinstance(payload, list):
            raw_edits = payload
        else:
            raise ImplementationPlanError(
                "Implementation planner result must be a JSON list of edits "
                "or an object with an 'edits' list"
            )

        if not isinstance(raw_edits, list) or not raw_edits:
            raise ImplementationPlanError(
                "Implementation plan must contain at least one edit"
            )

        if len(raw_edits) > MAXIMUM_TOTAL_EDITS:
            raise ImplementationPlanError(
                f"Implementation plan has too many edits: {len(raw_edits)}"
            )

        scope = self._build_scope(contract)

        allowed_files = set(contract["file_scope"]["allowed_files"])
        allowed_directories = set(
            contract["file_scope"].get("allowed_directories", [])
        )

        edits: list[EditOperation] = []

        for raw_edit in raw_edits:
            path = self._clean_path(raw_edit)
            mode = raw_edit.get("mode", "create")
            content = raw_edit.get("content", "")

            if mode not in {"create", "overwrite", "append"}:
                raise ImplementationPlanError(
                    f"Unsupported edit mode: {mode}"
                )

            if not isinstance(content, str) or not content:
                raise ImplementationPlanError(
                    f"Edit for {path} has empty content"
                )

            if len(content.encode("utf-8")) > MAXIMUM_EDIT_BYTES:
                raise ImplementationPlanError(
                    f"Edit for {path} exceeds content limit"
                )

            if path not in allowed_files and not self._covered_by_directory(
                path,
                allowed_directories,
            ):
                raise ImplementationPlanError(
                    f"Edit target outside approved scope: {path}"
                )

            if not scope.is_allowed(path):
                raise ImplementationPlanError(
                    f"Edit target is forbidden: {path}"
                )

            edits.append(
                EditOperation(path=path, mode=mode, content=content)
            )

        return tuple(edits)

    def _build_scope(self, contract: dict[str, Any]) -> ExecutionScope:
        allowed = list(contract["file_scope"]["allowed_files"])
        allowed.extend(
            contract["file_scope"].get("allowed_directories", [])
        )

        forbidden = list(contract["file_scope"].get("forbidden_files", []))
        forbidden.extend(
            contract["file_scope"].get("forbidden_directories", [])
        )
        forbidden.extend(DEFAULT_FORBIDDEN_PATHS)

        return ExecutionScope(
            allowed_paths=tuple(allowed),
            forbidden_paths=tuple(forbidden),
        )

    @staticmethod
    def _strip_code_fence(raw_json: str) -> str:
        text = raw_json.strip()

        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        return text

    @staticmethod
    def _clean_path(raw_edit: Any) -> str:
        if not isinstance(raw_edit, dict):
            raise ImplementationPlanError(
                "Implementation plan edits must be objects"
            )

        raw_path = raw_edit.get("path")

        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ImplementationPlanError(
                "Implementation plan edit is missing a path"
            )

        path = PurePosixPath(raw_path.strip())

        if path.is_absolute() or ".." in path.parts:
            raise ImplementationPlanError(
                f"Unsafe edit path: {raw_path}"
            )

        return str(path)

    @staticmethod
    def _covered_by_directory(
        path: str,
        allowed_directories: set[str],
    ) -> bool:
        candidate = PurePosixPath(path)

        return any(
            PurePosixPath(directory) in candidate.parents
            for directory in allowed_directories
        )

    def _build_prompt(
        self,
        *,
        contract: dict[str, Any],
        tracked_files: list[str],
    ) -> str:
        file_scope = contract["file_scope"]
        command_policy = contract["command_policy"]

        required_changes = json.dumps(
            contract["required_changes"],
            indent=2,
        )

        return (
            "You are a software engineer implementing one bounded work "
            "package. Produce the exact file contents required to satisfy "
            "the work package using the /workspace repository.\n\n"
            "Work package title: {title}\n"
            "Objective: {objective}\n\n"
            "Required changes:\n{required_changes}\n\n"
            "Allowed file scope:\n{file_scope}\n\n"
            "Approved test commands (must pass):\n{test_commands}\n\n"
            "Existing tracked files in the repository:\n{tracked_files}\n\n"
            "Rules:\n"
            "- Return ONLY JSON of the form "
            '{{"edits": [{{"path": "...", "mode": "create|overwrite|append", '
            '"content": "..."}}]}}.\n'
            "- Every edit path must be inside the allowed file scope.\n"
            "- If the approved test command references a directory such as "
            "'tests', create passing tests inside that directory and ensure "
            "it is within the allowed scope.\n"
            "- Content must be complete, valid and ready to write; do not "
            "use placeholders.\n"
            "- Implement exactly the work package changes, nothing more."
        ).format(
            title=contract["title"],
            objective=contract["objective"],
            required_changes=required_changes,
            file_scope=json.dumps(file_scope, indent=2),
            test_commands=json.dumps(
                command_policy.get("test_commands", []),
                indent=2,
            ),
            tracked_files="\n".join(sorted(tracked_files)),
        )
