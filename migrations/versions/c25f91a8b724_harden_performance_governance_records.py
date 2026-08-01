"""harden mutable performance governance records

Revision ID: c25f91a8b724
Revises: c24e89f7a613
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c25f91a8b724"
down_revision: str | None = "c24e89f7a613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_capability_recommendation_mutation() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'capability recommendations cannot be deleted';
          END IF;
          IF OLD.id IS DISTINCT FROM NEW.id
             OR OLD.organization_id IS DISTINCT FROM NEW.organization_id
             OR OLD.agent_profile_id IS DISTINCT FROM NEW.agent_profile_id
             OR OLD.capability_key IS DISTINCT FROM NEW.capability_key
             OR OLD.recommended_level IS DISTINCT FROM NEW.recommended_level
             OR OLD.recommendation_document IS DISTINCT FROM NEW.recommendation_document
             OR OLD.recommendation_hash IS DISTINCT FROM NEW.recommendation_hash
             OR OLD.evidence_ids IS DISTINCT FROM NEW.evidence_ids
             OR OLD.evidence_set_hash IS DISTINCT FROM NEW.evidence_set_hash
             OR OLD.policy_version IS DISTINCT FROM NEW.policy_version
             OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
            RAISE EXCEPTION 'capability recommendation evidence is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER guard_capability_recommendation_mutation_trigger
        BEFORE UPDATE OR DELETE ON capability_recommendations
        FOR EACH ROW EXECUTE FUNCTION guard_capability_recommendation_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_learning_proposal_mutation() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'learning proposals cannot be deleted';
          END IF;
          IF OLD.id IS DISTINCT FROM NEW.id
             OR OLD.organization_id IS DISTINCT FROM NEW.organization_id
             OR OLD.project_id IS DISTINCT FROM NEW.project_id
             OR OLD.proposal_type IS DISTINCT FROM NEW.proposal_type
             OR OLD.observation IS DISTINCT FROM NEW.observation
             OR OLD.recommendation IS DISTINCT FROM NEW.recommendation
             OR OLD.target_reference IS DISTINCT FROM NEW.target_reference
             OR OLD.proposal_document IS DISTINCT FROM NEW.proposal_document
             OR OLD.proposal_hash IS DISTINCT FROM NEW.proposal_hash
             OR OLD.evidence_ids IS DISTINCT FROM NEW.evidence_ids
             OR OLD.evidence_set_hash IS DISTINCT FROM NEW.evidence_set_hash
             OR OLD.proposed_by IS DISTINCT FROM NEW.proposed_by
             OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
            RAISE EXCEPTION 'learning proposal evidence is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER guard_learning_proposal_mutation_trigger
        BEFORE UPDATE OR DELETE ON performance_learning_proposals
        FOR EACH ROW EXECUTE FUNCTION guard_learning_proposal_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER guard_learning_proposal_mutation_trigger "
        "ON performance_learning_proposals"
    )
    op.execute("DROP FUNCTION guard_learning_proposal_mutation()")
    op.execute(
        "DROP TRIGGER guard_capability_recommendation_mutation_trigger "
        "ON capability_recommendations"
    )
    op.execute("DROP FUNCTION guard_capability_recommendation_mutation()")
