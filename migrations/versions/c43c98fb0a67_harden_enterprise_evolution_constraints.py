"""harden enterprise evolution type and state constraints

Revision ID: c43c98fb0a67
Revises: c42b87eaf956
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c43c98fb0a67"
down_revision: str | None = "c42b87eaf956"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_enterprise_improvement_category",
        "enterprise_improvements",
        "category IN ('architecture','generator','workflow','policy','agent','infrastructure',"
        "'security','performance','developer_experience','operations','governance')",
    )
    op.create_check_constraint(
        "ck_enterprise_improvement_no_self_dependency",
        "enterprise_improvements",
        "NOT (improvement_key = ANY(dependencies))",
    )
    op.create_check_constraint(
        "ck_enterprise_evolution_artifact_type",
        "enterprise_evolution_artifacts",
        "artifact_type IN ('learning_hypothesis','pattern','anti_pattern','recommendation',"
        "'simulation','experiment','generator_evolution','policy_evolution',"
        "'ai_workforce_evolution','capability_evolution','maturity_assessment','benchmark',"
        "'roadmap','refactoring_plan','self_reflection')",
    )
    op.create_check_constraint(
        "ck_enterprise_evolution_decision",
        "enterprise_evolution_decisions",
        "decision IN ('approve','reject') AND target_type IN ('improvement','artifact')",
    )
    op.create_check_constraint(
        "ck_enterprise_improvement_transition_state",
        "enterprise_improvement_transitions",
        "to_state IN ('proposed','analyzed','simulated','reviewed','approved','implemented',"
        "'measured','accepted','archived') AND (from_state IS NULL OR from_state IN "
        "('proposed','analyzed','simulated','reviewed','approved','implemented','measured',"
        "'accepted','archived'))",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_enterprise_improvement_transition_state",
        "enterprise_improvement_transitions",
        type_="check",
    )
    op.drop_constraint(
        "ck_enterprise_evolution_decision", "enterprise_evolution_decisions", type_="check"
    )
    op.drop_constraint(
        "ck_enterprise_evolution_artifact_type",
        "enterprise_evolution_artifacts",
        type_="check",
    )
    op.drop_constraint(
        "ck_enterprise_improvement_no_self_dependency",
        "enterprise_improvements",
        type_="check",
    )
    op.drop_constraint(
        "ck_enterprise_improvement_category", "enterprise_improvements", type_="check"
    )
