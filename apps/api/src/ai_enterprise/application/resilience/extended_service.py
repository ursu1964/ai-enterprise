from __future__ import annotations

from typing import Any

from ai_enterprise.domain.resilience.policies import ResiliencePolicyError


class InstitutionalGovernanceValidator:
    RECORD_TYPES = frozenset(
        {
            "region_site",
            "region_ownership_lease",
            "residency_policy",
            "execution_zone",
            "model_provider",
            "model_definition",
            "model_evaluation",
            "model_substitution",
            "crypto_profile",
            "crypto_key_version",
            "crypto_rotation",
            "key_revocation",
            "signature_record",
            "authority_succession",
            "emergency_grant",
            "knowledge_assessment",
            "institutional_runbook",
            "runbook_rehearsal",
            "vendor_exit_plan",
            "vendor_exit_rehearsal",
            "technology_substitution",
            "archive_verification",
            "backup_archive_replication",
            "resilience_experiment",
            "artifact_migration",
            "audit_checkpoint",
            "crisis_activation",
            "crisis_exit_review",
        }
    )
    EVIDENCE_STATUSES = frozenset({"tested", "verified", "completed", "passed"})

    def validate(
        self,
        *,
        record_type: str,
        status: str,
        payload: dict[str, Any],
        evidence_hash: str | None,
        actor: str,
    ) -> None:
        if record_type not in self.RECORD_TYPES:
            raise ResiliencePolicyError("Unknown institutional governance record type")
        if status in self.EVIDENCE_STATUSES and not evidence_hash:
            raise ResiliencePolicyError("Provider or rehearsal evidence is required")
        if any(key.lower() in {"private_key", "secret", "token", "credential"} for key in payload):
            raise ResiliencePolicyError("Secret material cannot be persisted")
        if record_type == "region_ownership_lease" and not (
            payload.get("witness_evidence_hash") and int(payload.get("fencing_token", 0)) > 0
        ):
            raise ResiliencePolicyError("Witnessed positive fencing token is required")
        if record_type == "residency_policy" and not (
            payload.get("processing_regions") and payload.get("storage_regions")
        ):
            raise ResiliencePolicyError("Residency regions are required")
        if record_type == "model_definition" and status == "approved" and not evidence_hash:
            raise ResiliencePolicyError("Model approval requires evaluation evidence")
        if record_type == "emergency_grant":
            parties = {actor, payload.get("principal_id"), payload.get("second_approver")}
            if len(parties) != 3:
                raise ResiliencePolicyError("Emergency grant requires independent dual control")
        if record_type in {"institutional_runbook", "authority_succession"} and (
            payload.get("owner") == payload.get("deputy")
            or payload.get("primary_subject") == payload.get("deputy_subject")
        ):
            raise ResiliencePolicyError("Primary owner and backup authority must differ")
        if record_type == "artifact_migration" and (
            payload.get("source_artifact_id") == payload.get("target_artifact_id")
        ):
            raise ResiliencePolicyError("Artifact migration cannot overwrite its source")
        if record_type == "crisis_activation" and (
            actor == payload.get("second_approver") or not payload.get("prohibited_capabilities")
        ):
            raise ResiliencePolicyError("Crisis activation requires dual control and restrictions")
        if record_type == "crisis_exit_review" and not (
            payload.get("integrity_reviewer") and payload.get("authority_reviewer")
        ):
            raise ResiliencePolicyError("Crisis exit requires integrity and authority reviews")
