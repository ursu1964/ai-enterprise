from ai_enterprise.application.query.read_models import meaning_for, status_read_model
from ai_enterprise.domain.workflow.enums import WorkflowState


def test_every_workflow_state_has_specialized_operator_meaning() -> None:
    for state in WorkflowState:
        meaning = meaning_for(state)

        assert "no specialized explanation" not in meaning["meaning"]
        assert meaning["operator_action"]


def test_runtime_statuses_have_friendly_read_models() -> None:
    assert status_read_model("running")["status_label"] == "Work is running"
    assert status_read_model("draft")["status_label"] == "Draft"
    assert status_read_model("registered")["status_label"] == "Registered"
    assert status_read_model("validation_failed")["status_label"] == "Validation failed"
