from .contracts import ArchitectureIntegrityRecord, IntegrityFinding


class ArchitectureIntegrityScanner:
    """Read-only deterministic scan; callers decide how incidents are persisted."""

    def scan(self, rows: tuple[ArchitectureIntegrityRecord, ...]) -> tuple[IntegrityFinding, ...]:
        findings: list[IntegrityFinding] = []
        for row in rows:
            if row.run_status == "completed" and not row.artifact_ids:
                findings.append(self._finding("COMPLETED_WITHOUT_ARTIFACT", row.run_id))
            if len(row.artifact_ids) > 1:
                findings.append(
                    self._finding("MULTIPLE_AUTHORITATIVE_ARTIFACTS", row.run_id, "critical")
                )
            if row.attempt_statuses.count("succeeded") > 1:
                findings.append(
                    self._finding("MULTIPLE_SUCCESSFUL_ATTEMPTS", row.run_id, "critical")
                )
            checks = {
                "ARTIFACT_CHECKSUM_MISMATCH": row.artifact_checksum_valid,
                "REVIEW_CHECKSUM_MISMATCH": row.review_checksum_valid,
                "APPROVAL_CHECKSUM_MISMATCH": row.approval_checksum_valid,
                "APPROVAL_EVIDENCE_MISMATCH": row.approval_evidence_checksum_valid,
                "AUDIT_CHAIN_INVALID": row.audit_chain_valid,
                "REVISION_LINEAGE_INVALID": row.revision_lineage_valid,
            }
            findings.extend(
                self._finding(code, row.run_id, "critical")
                for code, passed in checks.items()
                if not passed
            )
        return tuple(findings)

    @staticmethod
    def _finding(code: str, aggregate_id: str, severity: str = "high") -> IntegrityFinding:
        return IntegrityFinding(code, severity, aggregate_id, code.replace("_", " ").title())
