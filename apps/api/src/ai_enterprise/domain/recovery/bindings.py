from typing import Any

from ai_enterprise.domain.hashing import hash_json, hash_text
from ai_enterprise.domain.recovery.entities import ChangedPath, CommitPlan


def hash_commands(commands: tuple[dict[str, Any], ...]) -> str:
    return hash_json({"commands": list(commands)})


def hash_changed_paths(paths: tuple[ChangedPath, ...]) -> str:
    return hash_json({"changed_paths": [path.as_dict() for path in paths]})


def rollback_binding_hash(
    *,
    integration_attempt_id: str,
    integration_commit_sha: str,
    parent_commit_sha: str,
    integration_tree_sha: str,
    parent_tree_sha: str,
    changed_paths_sha256: str,
    inverse_diff_sha256: str,
    original_patch_sha256: str,
    approved_test_commands_sha256: str,
    recovery_policy_version: str,
) -> str:
    return hash_json(
        {
            "approved_test_commands_sha256": approved_test_commands_sha256,
            "changed_paths_sha256": changed_paths_sha256,
            "integration_attempt_id": integration_attempt_id,
            "integration_commit_sha": integration_commit_sha,
            "integration_tree_sha": integration_tree_sha,
            "inverse_diff_sha256": inverse_diff_sha256,
            "original_patch_sha256": original_patch_sha256,
            "parent_commit_sha": parent_commit_sha,
            "parent_tree_sha": parent_tree_sha,
            "recovery_policy_version": recovery_policy_version,
        }
    )


def assessment_binding_hash(
    *,
    incident_id: str,
    rollback_record_id: str,
    strategy: str,
    expected_remote_head_sha: str,
    required_test_commands_sha256: str,
    assessment_policy_version: str,
) -> str:
    return hash_json(
        {
            "assessment_policy_version": assessment_policy_version,
            "expected_remote_head_sha": expected_remote_head_sha,
            "incident_id": incident_id,
            "required_test_commands_sha256": required_test_commands_sha256,
            "rollback_record_id": rollback_record_id,
            "strategy": strategy,
        }
    )


def approval_binding_hash(
    *,
    recovery_assessment_id: str,
    rollback_record_id: str,
    repository_id: str,
    target_branch: str,
    strategy: str,
    expected_remote_head_sha: str,
    integration_commit_sha: str,
    required_test_commands_sha256: str,
    assessment_policy_version: str,
    recovery_policy_version: str,
) -> str:
    return hash_json(
        {
            "assessment_policy_version": assessment_policy_version,
            "expected_remote_head_sha": expected_remote_head_sha,
            "integration_commit_sha": integration_commit_sha,
            "recovery_assessment_id": recovery_assessment_id,
            "recovery_policy_version": recovery_policy_version,
            "repository_id": repository_id,
            "required_test_commands_sha256": required_test_commands_sha256,
            "rollback_record_id": rollback_record_id,
            "strategy": strategy,
            "target_branch": target_branch,
        }
    )


def commit_plan_binding(plan: CommitPlan) -> str:
    return hash_json(
        {
            "author_email": plan.author_email,
            "author_name": plan.author_name,
            "author_timestamp": plan.author_timestamp.isoformat(),
            "committer_email": plan.committer_email,
            "committer_name": plan.committer_name,
            "committer_timestamp": plan.committer_timestamp.isoformat(),
            "message_sha256": hash_text(plan.message),
            "parent_sha": plan.parent_sha,
            "policy_version": plan.policy_version,
            "tree_sha": plan.tree_sha,
        }
    )

