from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = ROOT / "docs" / "runbooks" / "production-deployment-verification.md"
GITIGNORE = ROOT / ".gitignore"


def test_production_deployment_verification_runbook_publishes_exact_fail_closed_steps() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    required_commands = (
        "rtk make production-evidence-plan",
        "rtk make infrastructure-choices-verify",
        "rtk make production-readiness-contracts",
        "rtk make production-readiness",
        "rtk make release-gate-evidence-release",
        "rtk make production-release-artifact",
    )
    for command in required_commands:
        assert command in text

    assert "Do not fabricate owners, credentials, pilot results, or deployment artifacts." in text
    assert "Do not hand-edit the artifact to pass." in text
    assert "`blocked`, not `ready`" in text
    assert "intentionally ignored by Git" in text


def test_production_evidence_inputs_are_ignored_to_avoid_committing_real_references() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")

    assert "docs/enterprise/real-world-infrastructure-decisions.json" in text
    assert "docs/enterprise/production-readiness-evidence.json" in text
