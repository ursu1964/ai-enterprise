from __future__ import annotations

import re
from pathlib import Path

from ai_enterprise.domain.review.enums import FindingSeverity
from ai_enterprise.domain.review.policies import ReviewFinding

SECRET_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "aws-access-key-id",
        "AWS access key ID",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "aws-secret-access-key",
        "AWS secret access key",
        re.compile(
            r"\b(?:aws_secret_access_key\s*=\s*|"
            r'["\']aws\.secret\.access\.key["\']\s*:\s*["\'])'
            r"[A-Za-z0-9/+=]{40}\b"
        ),
    ),
    (
        "private-key",
        "Private key block",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "github-token",
        "GitHub token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ),
    (
        "google-api-key",
        "Google API key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ),
    (
        "slack-token",
        "Slack token",
        re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    ),
    (
        "stripe-live-secret",
        "Stripe live secret key",
        re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b"),
    ),
    (
        "generic-bearer-token",
        "Generic bearer token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b"),
    ),
)


class SecretScanner:
    def scan(self, repository: Path) -> tuple[ReviewFinding, ...]:
        findings: list[ReviewFinding] = []

        changed_files = self._changed_files(repository)

        for relative_path in changed_files:
            file_path = repository / relative_path

            if file_path.is_symlink() or not file_path.is_file():
                continue

            try:
                content = file_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            for rule_id, title, pattern in SECRET_PATTERNS:
                for match in pattern.finditer(content):
                    line_start = content.count(
                        "\n",
                        0,
                        match.start(),
                    ) + 1
                    line_end = content.count(
                        "\n",
                        0,
                        match.end(),
                    ) + 1

                    matched_prefix = content[
                        max(0, match.start() - 24) : match.start()
                    ]
                    matched_suffix = content[
                        match.end() : match.end() + 24
                    ]

                    findings.append(
                        ReviewFinding(
                            rule_id=rule_id,
                            category="security",
                            severity=FindingSeverity.CRITICAL,
                            title=title,
                            description=(
                                f"Detected secret-like content matching "
                                f"rule {rule_id} in {relative_path}"
                            ),
                            blocking=True,
                            file_path=relative_path,
                            line_start=line_start,
                            line_end=line_end,
                            evidence={
                                "rule_id": rule_id,
                                "context": (
                                    matched_prefix
                                    + "<REDACTED>"
                                    + matched_suffix
                                ),
                            },
                        )
                    )

        return tuple(findings)

    @staticmethod
    def _changed_files(repository: Path) -> list[str]:
        import subprocess

        result = subprocess.run(
            ["git", "-C", str(repository), "diff", "--cached", "--name-only"],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

        return [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        ]
