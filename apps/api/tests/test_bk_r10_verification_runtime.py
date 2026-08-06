from __future__ import annotations

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from ai_enterprise.application.bk_r10_verification_runtime import (
    BK_R10_VERSION,
    BKR10ExternalAdapterError,
    bk_r10_create_campaign,
    bk_r10_create_handoff,
    bk_r10_execute_external_verification,
    bk_r10_external_readiness,
    bk_r10_generate_satisfaction_recommendations,
    bk_r10_generate_verdict,
    bk_r10_http_verification_adapter,
    bk_r10_perform_coverage_assessment,
    bk_r10_qualify_environment,
    bk_r10_read_campaign,
    bk_r10_record_result,
    bk_r10_start_campaign,
    bk_r10_submit_waiver,
    bk_r10_write_campaign,
)
from ai_enterprise.main import app


def _actor(role: str = "verifier") -> dict[str, str]:
    return {"actor_type": "human", "actor_id": f"{role}-1", "role": role}


def _headers() -> dict[str, str]:
    return {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }


def _handoff():
    return bk_r10_create_handoff(
        implementation_result_id="impl-result-001",
        implementation_slice_id="slice-001",
        repository_revision="commit-abc",
        requirement_baseline_id="req-baseline-001",
        architecture_baseline_id="arch-baseline-001",
        planning_baseline_id="plan-baseline-001",
        produced_by=_actor("implementation-agent"),
        policy_refs=("policy-verification-default",),
        artifact_refs=("artver-api-001",),
    )


def _campaign():
    obligation = {
        "verification_obligation_id": "obl-req-api-001",
        "requirement_id": "REQ-API-001",
        "acceptance_criterion_id": "AC-API-001",
        "method": "TEST",
        "criticality": "CRITICAL",
        "mandatory": True,
        "required_evidence_types": ("test-report",),
        "responsible_authority": _actor("verification-authority"),
    }
    procedure = {
        "verification_procedure_id": "proc-api-contract",
        "verification_obligation_ids": ("obl-req-api-001",),
        "title": "API contract verification",
        "ordered_steps": ("run contract tests",),
        "expected_results": ("all contract checks pass",),
        "required_tools": ("pytest",),
        "required_environment_profile": "ci-python",
    }
    return bk_r10_create_campaign(
        organization_id="org-001",
        project_id="project-001",
        handoff=_handoff(),
        owner=_actor("verification-owner"),
        obligations=(obligation,),
        procedures=(procedure,),
        criticality="CRITICAL",
    )


def _qualified(campaign=None):
    campaign = campaign or _campaign()
    return bk_r10_qualify_environment(
        campaign,
        {
            "verification_environment_id": "env-ci",
            "environment_type": "CI",
            "environment_profile": "ci-python",
            "runtime_versions": {"python": "3.11"},
            "infrastructure_reference": "ci://local",
            "repository_revision": "commit-abc",
            "configuration_hashes": ("cfg-1",),
            "dependency_lock_hashes": ("lock-1",),
            "network_policy": "isolated",
            "secret_scope": (),
            "evidence_reference": "evidence://env/ci",
        },
        actor=_actor("platform-engineer"),
    )


def test_bk_r10_campaign_binds_exact_handoff_and_baselines() -> None:
    campaign = _campaign()

    assert campaign.status == "DRAFT"
    assert campaign.verification_handoff.handoff_hash
    assert campaign.verification_handoff.repository_revision == "commit-abc"
    assert campaign.verification_handoff.requirement_baseline_id == "req-baseline-001"
    assert campaign.events[-1].event_type == "VerificationCampaignCreated"


def test_bk_r10_entry_requires_verified_environment() -> None:
    blocked = bk_r10_start_campaign(_campaign(), actor=_actor("verification-owner"))

    assert blocked.status == "BLOCKED"
    assert any(item.finding_type == "COVERAGE_GAP" for item in blocked.findings)


def test_bk_r10_records_pass_only_with_evidence_and_generates_positive_verdict() -> None:
    campaign = bk_r10_start_campaign(_qualified(), actor=_actor("verification-owner"))
    campaign = bk_r10_record_result(
        campaign,
        procedure_id="proc-api-contract",
        environment_id="env-ci",
        executor=_actor("independent-verifier"),
        obligation_results=(
            {
                "verification_obligation_id": "obl-req-api-001",
                "status": "PASSED",
                "evidence_references": ("evidence://test-report/api-contract",),
            },
        ),
        raw_evidence_references=("evidence://raw/pytest",),
    )
    campaign = bk_r10_perform_coverage_assessment(campaign, actor=_actor("verification-owner"))
    campaign = bk_r10_generate_verdict(campaign, actor=_actor("verification-owner"))
    campaign = bk_r10_generate_satisfaction_recommendations(
        campaign,
        actor=_actor("verification-owner"),
    )

    assert campaign.status == "COMPLETED"
    assert campaign.verdict is not None
    assert campaign.verdict.final_verdict == "PASS"
    assert campaign.coverage is not None
    assert campaign.coverage.passed_mandatory_obligations == 1
    assert campaign.satisfaction_recommendations[0].recommendation == "SATISFY"


def test_bk_r10_no_evidence_no_pass_and_no_silent_omission() -> None:
    campaign = bk_r10_start_campaign(_qualified(), actor=_actor("verification-owner"))
    campaign = bk_r10_record_result(
        campaign,
        procedure_id="proc-api-contract",
        environment_id="env-ci",
        executor=_actor("independent-verifier"),
        obligation_results=(
            {
                "verification_obligation_id": "obl-req-api-001",
                "status": "PASSED",
                "evidence_references": (),
            },
        ),
        raw_evidence_references=(),
    )
    campaign = bk_r10_record_result(
        campaign,
        procedure_id="proc-api-contract",
        environment_id="env-ci",
        executor=_actor("independent-verifier"),
        obligation_results=(
            {
                "verification_obligation_id": "obl-req-api-001",
                "status": "SKIPPED",
                "evidence_references": (),
            },
        ),
        raw_evidence_references=("evidence://raw/skipped",),
    )

    codes = {event.event_type for event in campaign.events}
    assert "VerificationResultRecorded" in codes
    assert any(item.finding_type == "EVIDENCE_GAP" for item in campaign.findings)
    assert any("Skipped" in item.description for item in campaign.findings)


def test_bk_r10_failed_result_remains_visible_and_flaky_retry_blocks_verdict() -> None:
    campaign = bk_r10_start_campaign(_qualified(), actor=_actor("verification-owner"))
    failed = bk_r10_record_result(
        campaign,
        procedure_id="proc-api-contract",
        environment_id="env-ci",
        executor=_actor("independent-verifier"),
        obligation_results=(
            {
                "verification_obligation_id": "obl-req-api-001",
                "status": "FAILED",
                "evidence_references": ("evidence://test-report/fail",),
                "notes": "contract mismatch",
            },
        ),
        raw_evidence_references=("evidence://raw/fail",),
    )
    retried = bk_r10_record_result(
        failed,
        procedure_id="proc-api-contract",
        environment_id="env-ci",
        executor=_actor("independent-verifier"),
        obligation_results=(
            {
                "verification_obligation_id": "obl-req-api-001",
                "status": "PASSED",
                "evidence_references": ("evidence://test-report/pass",),
            },
        ),
        raw_evidence_references=("evidence://raw/pass",),
    )
    verdict = bk_r10_generate_verdict(retried, actor=_actor("verification-owner"))

    assert len(retried.results) == 2
    assert retried.results[0].verdict == "FAILED"
    assert any(item.finding_type == "FLAKY_RESULT" for item in retried.findings)
    assert verdict.verdict is not None
    assert verdict.verdict.final_verdict == "FAIL"


def test_bk_r10_governed_waiver_requires_scope_risk_expiry_and_controls() -> None:
    campaign = _qualified()
    waived = bk_r10_submit_waiver(
        campaign,
        obligation_id="obl-req-api-001",
        authority=_actor("verification-authority"),
        justification="external lab unavailable",
        risk_acceptance="accepted for pilot only",
        scope="pilot",
        expires_at="2026-12-31T00:00:00Z",
        compensating_controls=("manual review",),
    )
    coverage = bk_r10_perform_coverage_assessment(waived, actor=_actor("verification-owner"))

    assert waived.waivers[0].status == "APPROVED"
    assert (
        next(
            item
            for item in waived.obligations
            if item.verification_obligation_id == "obl-req-api-001"
        ).status
        == "WAIVED"
    )
    assert coverage.coverage is not None
    assert coverage.coverage.waived_mandatory_obligations == 1


def test_bk_r10_campaign_roundtrip(tmp_path: Path) -> None:
    campaign = _campaign()
    path = tmp_path / "campaign.json"

    campaign_hash = bk_r10_write_campaign(campaign, path)
    loaded = bk_r10_read_campaign(path)

    assert loaded is not None
    assert loaded.content_hash == campaign_hash


def test_bk_r10_api_is_exposed() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/bk/r10-verification/contract" in paths
    assert "/api/v1/bk/r10-verification/handoffs" in paths
    assert "/api/v1/bk/r10-verification/projects/{project_id}/campaigns" in paths


def test_bk_r10_api_contract_response() -> None:
    response = TestClient(app).get(
        "/api/v1/bk/r10-verification/contract",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["version"] == BK_R10_VERSION


def test_bk_r10_external_readiness_fails_closed_for_production_mock_backend() -> None:
    report = bk_r10_external_readiness(
        (
            {
                "backend_type": "ci_runner",
                "provider": "mock",
                "enabled": True,
                "mock_mode": True,
            },
        ),
        environment="production",
        required_backends=("ci_runner",),
    )

    assert report.production_ready is False
    assert any(
        item.code == "BK_R10_MOCK_BACKEND_FORBIDDEN_IN_PRODUCTION" for item in report.diagnostics
    )


def test_bk_r10_external_mock_execution_returns_obligation_evidence() -> None:
    result = bk_r10_execute_external_verification(
        {
            "procedure_id": "proc-api-contract",
            "obligation_ids": ("obl-req-api-001",),
            "repository_revision": "commit-abc",
            "environment_id": "env-ci",
            "tool": "pytest",
            "inputs": {"status": "PASSED"},
        },
        {
            "backend_type": "ci_runner",
            "provider": "mock",
            "enabled": True,
            "mock_mode": True,
        },
        environment="development",
    )

    assert result.status == "PASSED"
    assert result.obligation_results[0].status == "PASSED"
    assert result.raw_evidence_references[0].startswith("mock-evidence://raw/")


def test_bk_r10_external_execution_blocks_unready_production_backend() -> None:
    try:
        bk_r10_execute_external_verification(
            {
                "procedure_id": "proc-api-contract",
                "obligation_ids": ("obl-req-api-001",),
                "repository_revision": "commit-abc",
                "environment_id": "env-ci",
                "tool": "pytest",
                "inputs": {"status": "PASSED"},
            },
            {
                "backend_type": "ci_runner",
                "provider": "github-actions",
                "enabled": True,
                "endpoint_reference": "https://github.example/actions",
            },
            environment="production",
        )
    except BKR10ExternalAdapterError as exc:
        assert "BK_R10_CREDENTIAL_REFERENCE_REQUIRED" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("production execution should fail without credential reference")


def test_bk_r10_external_readiness_api_is_exposed() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/bk/r10-verification/external-readiness" in paths
    assert "/api/v1/bk/r10-verification/external-executions/mock" in paths


def test_bk_r10_external_readiness_api_uses_settings_backed_defaults() -> None:
    response = TestClient(app).post(
        "/api/v1/bk/r10-verification/external-readiness",
        headers=_headers(),
        json={"environment": "development", "required_backends": ["ci_runner"]},
    )

    assert response.status_code == 200
    record = response.json()["record"]
    assert record["backends"][0]["backend_type"] == "ci_runner"
    assert record["backends"][0]["provider"] == "mock"
    assert any(item["code"] == "BK_R10_BACKEND_DISABLED" for item in record["diagnostics"])


def test_bk_r10_external_readiness_api_merges_request_overrides() -> None:
    response = TestClient(app).post(
        "/api/v1/bk/r10-verification/external-readiness",
        headers=_headers(),
        json={
            "environment": "development",
            "required_backends": ["ci_runner"],
            "backend_configs": [
                {
                    "backend_type": "ci_runner",
                    "provider": "mock",
                    "enabled": True,
                    "mock_mode": True,
                }
            ],
        },
    )

    assert response.status_code == 200
    record = response.json()["record"]
    assert record["backends"][0]["configured"] is True
    assert record["production_ready"] is True


def test_bk_r10_http_adapter_executes_provider_neutral_verification() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Reference secret://ci-token"
        payload = request.read()
        assert b"proc-api-contract" in payload
        return httpx.Response(
            200,
            json={
                "status": "PASSED",
                "obligation_results": [
                    {
                        "verification_obligation_id": "obl-req-api-001",
                        "status": "PASSED",
                        "evidence_references": ["evidence://ci/api-contract"],
                    }
                ],
                "raw_evidence_references": ["evidence://raw/ci"],
                "normalized_evidence_references": ["evidence://normalized/ci"],
                "metrics": {"external_calls": 1, "duration_ms": 42},
            },
        )

    result = bk_r10_execute_external_verification(
        {
            "procedure_id": "proc-api-contract",
            "obligation_ids": ("obl-req-api-001",),
            "repository_revision": "commit-abc",
            "environment_id": "env-ci",
            "tool": "pytest",
            "inputs": {"suite": "contract"},
        },
        {
            "backend_type": "ci_runner",
            "provider": "custom-http",
            "enabled": True,
            "endpoint_reference": "https://ci.example.test/verify",
            "credential_reference": "secret://ci-token",
        },
        adapter=bk_r10_http_verification_adapter(transport=httpx.MockTransport(handler)),
        environment="production",
    )

    assert result.status == "PASSED"
    assert result.metrics["external_calls"] == 1
    assert result.obligation_results[0].evidence_references == ("evidence://ci/api-contract",)


def test_bk_r10_http_adapter_rejects_invalid_provider_payload() -> None:
    adapter = bk_r10_http_verification_adapter(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"bad": "shape"}))
    )

    try:
        bk_r10_execute_external_verification(
            {
                "procedure_id": "proc-api-contract",
                "obligation_ids": ("obl-req-api-001",),
                "repository_revision": "commit-abc",
                "environment_id": "env-ci",
                "tool": "pytest",
                "inputs": {"suite": "contract"},
            },
            {
                "backend_type": "ci_runner",
                "provider": "custom-http",
                "enabled": True,
                "endpoint_reference": "https://ci.example.test/verify",
                "credential_reference": "secret://ci-token",
            },
            adapter=adapter,
            environment="production",
        )
    except BKR10ExternalAdapterError as exc:
        assert "invalid verification result" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid provider payload should be rejected")
