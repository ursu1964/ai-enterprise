from dataclasses import dataclass

from ai_enterprise.domain.workflow.context import WorkflowContext


@dataclass(frozen=True, slots=True)
class CompletenessResult:
    complete: bool
    missing: tuple[str, ...]


MANDATORY_ARTIFACTS = (
    "manifest",
    "requirements",
    "architecture",
    "work_package",
    "patch",
    "review",
)
MANDATORY_APPROVALS = ("requirements", "architecture", "work_package", "integration")
MANDATORY_EVIDENCE_LINKS = (
    "execution:approval_id",
    "execution:work_package_id",
    "execution:patch_artifact_id",
    "execution:patch_sha256",
    "execution:status",
    "review:execution_id",
    "review:work_package_id",
    "review:patch_artifact_id",
    "review:report_artifact_id",
    "review:expected_patch_sha256",
    "review:actual_patch_sha256",
    "review:status",
    "integration:execution_id",
    "integration:approval_id",
    "integration:project_id",
    "integration:expected_patch_sha256",
    "integration:expected_base_commit_sha",
    "integration:expected_base_tree_sha",
    "integration:actual_base_commit_sha",
    "integration:actual_base_tree_sha",
    "integration:resulting_tree_sha",
    "integration:status",
    "commit:integration_attempt_id",
    "commit:sha",
    "commit:tree_sha",
    "commit:parent_commit_sha",
    "commit:remote_verified",
)


def _missing_hash(name: str, value: str | None) -> str | None:
    if value is None:
        return f"artifact_hash:{name}"
    if len(value) != 64:
        return f"artifact_hash:{name}:invalid"
    return None


def _expect_link(
    missing: list[str], context: WorkflowContext, key: str, expected: object | None
) -> None:
    value = context.evidence_links.get(key)
    if value is None:
        return
    elif expected is not None and value != str(expected):
        missing.append(f"evidence_link:{key}:mismatch")


def _expect_equal(
    missing: list[str],
    context: WorkflowContext,
    left_key: str,
    right_key: str,
) -> None:
    left = context.evidence_links.get(left_key)
    right = context.evidence_links.get(right_key)
    if left is None or right is None:
        return
    if left != right:
        missing.append(f"evidence_link:{left_key}:mismatch:{right_key}")


def _expect_value(
    missing: list[str],
    context: WorkflowContext,
    key: str,
    expected: str,
) -> None:
    value = context.evidence_links.get(key)
    if value is None:
        return
    if value != expected:
        missing.append(f"evidence_link:{key}:mismatch")


def verify_completeness(context: WorkflowContext) -> CompletenessResult:
    missing = [
        f"artifact:{name}" for name in MANDATORY_ARTIFACTS if name not in context.artifact_ids
    ]
    missing.extend(
        item
        for name in MANDATORY_ARTIFACTS
        if (item := _missing_hash(name, context.artifact_hashes.get(name))) is not None
    )
    missing.extend(
        f"approval:{name}" for name in MANDATORY_APPROVALS if name not in context.approval_ids
    )
    missing.extend(
        f"evidence_link:{name}"
        for name in MANDATORY_EVIDENCE_LINKS
        if name not in context.evidence_links
    )
    if context.execution_id is None:
        missing.append("execution")
    if context.review_id is None:
        missing.append("review")
    if context.integration_attempt_id is None:
        missing.append("integration_attempt")
    if context.commit_id is None:
        missing.append("commit")
    _expect_link(missing, context, "review:execution_id", context.execution_id)
    _expect_link(
        missing,
        context,
        "execution:approval_id",
        context.approval_ids.get("work_package"),
    )
    _expect_link(
        missing,
        context,
        "execution:patch_artifact_id",
        context.artifact_ids.get("patch"),
    )
    _expect_link(missing, context, "review:patch_artifact_id", context.artifact_ids.get("patch"))
    _expect_link(missing, context, "review:report_artifact_id", context.artifact_ids.get("review"))
    _expect_link(missing, context, "integration:execution_id", context.execution_id)
    _expect_link(missing, context, "integration:project_id", context.project_id)
    _expect_link(
        missing, context, "integration:approval_id", context.approval_ids.get("integration")
    )
    _expect_link(
        missing,
        context,
        "commit:integration_attempt_id",
        context.integration_attempt_id,
    )
    _expect_equal(
        missing,
        context,
        "execution:work_package_id",
        "review:work_package_id",
    )
    _expect_equal(
        missing,
        context,
        "execution:patch_sha256",
        "review:expected_patch_sha256",
    )
    _expect_equal(
        missing,
        context,
        "review:expected_patch_sha256",
        "review:actual_patch_sha256",
    )
    _expect_equal(
        missing,
        context,
        "review:actual_patch_sha256",
        "integration:expected_patch_sha256",
    )
    _expect_equal(
        missing,
        context,
        "integration:expected_base_commit_sha",
        "integration:actual_base_commit_sha",
    )
    _expect_equal(
        missing,
        context,
        "integration:expected_base_tree_sha",
        "integration:actual_base_tree_sha",
    )
    _expect_equal(missing, context, "integration:resulting_tree_sha", "commit:tree_sha")
    _expect_equal(
        missing, context, "integration:actual_base_commit_sha", "commit:parent_commit_sha"
    )
    if context.evidence_links.get("commit:remote_verified") != "true":
        missing.append("evidence_link:commit:remote_verified:mismatch")
    _expect_link(missing, context, "commit:sha", context.commit_id)
    _expect_value(missing, context, "execution:status", "succeeded")
    _expect_value(missing, context, "review:status", "accepted")
    _expect_value(missing, context, "integration:status", "integrated")
    return CompletenessResult(not missing, tuple(missing))
