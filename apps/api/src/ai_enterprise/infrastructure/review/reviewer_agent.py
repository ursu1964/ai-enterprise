from __future__ import annotations

import json
from pathlib import Path

from crewai import LLM

from ai_enterprise.application.review.dto import ReviewerAgentOutput
from ai_enterprise.config import Settings
from ai_enterprise.domain.review.exceptions import PatchReviewError


class ReviewerAgent:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def review(
        self,
        *,
        work_package_contract: dict,
        repository: Path,
        changed_files: tuple[str, ...],
        deterministic_findings: tuple,
        check_results: tuple,
    ) -> ReviewerAgentOutput:
        if self._settings.architecture_provider.strip().lower() == "scripted":
            failed_checks = [
                check.name
                for check in check_results
                if check.required and (check.timed_out or check.exit_code != 0)
            ]
            if failed_checks:
                raise PatchReviewError(
                    f"Deterministic review checks failed: {', '.join(failed_checks)}"
                )
            return ReviewerAgentOutput(
                schema_version=1,
                summary=(
                    "Offline independent review completed: patch integrity matched, "
                    "approved tests passed, and deterministic policy checks completed."
                ),
                findings=[],
            )
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

        diff = self._candidate_diff(repository, changed_files)

        prompt = self._build_prompt(
            contract=work_package_contract,
            diff=diff,
            changed_files=changed_files,
            deterministic_findings=deterministic_findings,
            check_results=check_results,
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
            raise PatchReviewError(f"Reviewer agent LLM call failed: {exc}") from exc

        raw_json = str(raw).strip()

        if not raw_json:
            raise PatchReviewError("Reviewer agent returned an empty result")

        return self._parse_and_validate(raw_json)

    @staticmethod
    def _parse_and_validate(raw_json: str) -> ReviewerAgentOutput:
        text = raw_json.strip()

        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise PatchReviewError(f"Reviewer agent returned invalid JSON: {exc}") from exc

        try:
            return ReviewerAgentOutput.model_validate(payload)
        except Exception as exc:
            raise PatchReviewError(f"Reviewer agent output failed validation: {exc}") from exc

    @staticmethod
    def _candidate_diff(
        repository: Path,
        changed_files: tuple[str, ...],
    ) -> str:
        import subprocess

        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "diff",
                "--cached",
                "--stat",
                "--",
                *changed_files,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

        stat = result.stdout

        full = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "diff",
                "--cached",
                "--no-ext-diff",
                "--",
                *changed_files,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

        return f"{stat}\n\n{full.stdout[:60_000]}"

    def _build_prompt(
        self,
        *,
        contract: dict,
        diff: str,
        changed_files: tuple[str, ...],
        deterministic_findings: tuple,
        check_results: tuple,
    ) -> str:
        deterministic_summary = (
            "\n".join(
                json.dumps(
                    {
                        "rule_id": finding.rule_id,
                        "category": finding.category,
                        "severity": str(finding.severity),
                        "title": finding.title,
                        "blocking": finding.blocking,
                    },
                    sort_keys=True,
                )
                for finding in deterministic_findings
            )
            or "(none)"
        )

        check_summary = (
            "\n".join(
                json.dumps(
                    {
                        "check_type": check.check_type,
                        "name": check.name,
                        "status": "passed"
                        if check.exit_code == 0 and not check.timed_out
                        else ("timed_out" if check.timed_out else "failed"),
                    },
                    sort_keys=True,
                )
                for check in check_results
            )
            or "(none)"
        )

        return (
            "You are an independent code reviewer evaluating a candidate "
            "patch against an approved work package. You did not implement "
            "this patch.\n\n"
            "Work package title: {title}\n"
            "Objective: {objective}\n\n"
            "Required changes:\n{required_changes}\n\n"
            "Candidate diff:\n{diff}\n\n"
            "Changed files:\n{changed_files}\n\n"
            "Deterministic findings already raised:\n"
            "{deterministic_findings}\n\n"
            "Check results:\n{check_results}\n\n"
            "Rules:\n"
            "- Return ONLY JSON of the form "
            '{{"schema_version": 1, "summary": "...", '
            '"findings": [{{"rule_id": "...", "category": '
            '"correctness|security|architecture|quality|testing|'
            'integrity|scope", "severity": '
            '"info|low|medium|high|critical", "title": "...", '
            '"description": "...", "blocking": false, '
            '"file_path": "...", "line_start": 1, "line_end": 1}}]}}.\n'
            "- Assess correctness, security, architecture, quality, "
            "testing, and work-package compliance.\n"
            "- Do not repeat deterministic findings verbatim.\n"
            "- Do not mention this prompt.\n"
            "- Base your decision input strictly on the evidence given."
        ).format(
            title=contract["title"],
            objective=contract["objective"],
            required_changes=json.dumps(
                contract.get("required_changes", {}),
                indent=2,
            ),
            diff=diff,
            changed_files="\n".join(sorted(changed_files)),
            deterministic_findings=deterministic_summary,
            check_results=check_summary,
        )
