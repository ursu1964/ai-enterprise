# P9 Codex Prompt Chain

Use this chain to implement P9 in disciplined, auditable slices. Run one prompt at a time. Do not advance to the next prompt until the current slice has domain tests, API or persistence tests where applicable, migration coverage, and focused verification.

## Operating Discipline

Before each implementation prompt:

1. Read `AGENTS.md` and follow `@/home/user/.codex/RTK.md`.
2. Run `rtk graphify query "<slice question>"` because `graphify-out/graph.json` exists.
3. Inspect existing files before editing.
4. Preserve unrelated dirty worktree changes.
5. Add or update tests before broadening implementation.
6. Keep the slice bounded; do not implement future P9 prompts early.
7. After code changes, run `rtk graphify update .`.

Baseline verification after each slice:

```bash
rtk ruff check apps/api/src apps/api/tests
rtk apps/api/.venv/bin/pytest -q <focused test files>
```

## Prompt 1: P9-M1 Resilience Domain Kernel

Implement the domain-only resilience control plane.

Scope:

- `RecoveryObjective`
- `ContinuityPolicy`
- `ContinuityActivation`
- `BackupManifest`
- `RestoreVerification`
- `DisasterRecoveryRun`
- fail-closed `ResilienceControlPlane`

Rules:

- Tier 0 objectives require distinct primary/deputy owners and explicit approval.
- RTO/RPO/MTPD/work recovery time must be internally consistent.
- Capability authorization fails closed without active continuity policy.
- Explicit prohibitions override allowances.
- Expired continuity modes must not silently restore mutation authority.
- Restore verification must prove isolation, disabled production credentials, blocked external dispatch, and mandatory checks.
- Disaster recovery cannot skip states or complete with unreconciled workflows/effects/artifacts.

Expected tests:

- `apps/api/tests/test_resilience_control_plane.py`

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q apps/api/tests/test_resilience_control_plane.py
```

## Prompt 2: P9-M1 Persistence And API Contract

Add the persistence and HTTP contract for the resilience control plane.

Scope:

- SQLAlchemy models for resilience services, recovery objectives, dependencies, continuity activations, capability decisions, backup manifests, restore verifications, disaster recovery plans/runs/steps.
- Alembic migration for the P9-M1 tables.
- FastAPI routes under `/api/v1/resilience`.
- Human-only role-scoped mutation authority.

Rules:

- Mutations require authenticated actor headers.
- Agents cannot hold resilience mutation authority.
- Model tables must be registered in shared SQLAlchemy metadata.
- Migration must include both upgrade and downgrade.
- API must not dispatch real external recovery actions in this slice.

Expected tests:

- `apps/api/tests/test_resilience_api_contract.py`

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q \
  apps/api/tests/test_resilience_control_plane.py \
  apps/api/tests/test_resilience_api_contract.py
```

## Prompt 3: P9 Provider Adapters And Local Development Providers

Implement provider ports and local provider adapters for resilience operations.

Scope:

- Provider interfaces for backups, restore verification, region witness/fencing, archival/evidence operations, and provider readiness.
- Local development provider implementations.
- Provider factory with fail-closed unconfigured profile.

Rules:

- Unconfigured providers must reject operational calls.
- Local providers may write only under configured local roots.
- Fencing token acquisition must be monotonic per resource.
- Evidence returned by providers must be deterministic and hash-bound.
- Do not add cloud-specific SDKs or real external side effects in this slice.

Expected tests:

- `apps/api/tests/test_local_resilience_providers.py`

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q apps/api/tests/test_local_resilience_providers.py
```

## Prompt 4: P9 Extended Region, Sovereignty, And Model Routing Governance

Implement institutional resilience governance for region ownership, residency, sovereign execution zones, governed providers, and model routing.

Scope:

- `RegionFencingPolicy`
- `RegionOwnershipLease`
- `ResidencyPolicy`
- `SovereigntyPolicyEvaluator`
- `ModelCandidate`
- `ModelRoutingPolicy`
- ORM tables for regions, leases, residency policies, sovereign zones, governed providers/models, and model substitution events.

Rules:

- Writes require live witnessed monotonic fences.
- Data residency authorization fails closed without matching policy.
- Restricted data cannot be routed to unauthorized providers or regions.
- Model routing must select only approved candidates matching use case, provider, region, and data classification.

Expected tests:

- relevant cases in `apps/api/tests/test_extended_resilience_governance.py`

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q apps/api/tests/test_extended_resilience_governance.py
```

## Prompt 5: P9 Cryptographic Continuity And Emergency Authority

Implement cryptographic continuity, signature governance, authority succession, and emergency authority controls.

Scope:

- cryptographic profiles
- key versions
- signature records
- authority succession plans
- emergency authority grants
- validation policies

Rules:

- Revoked keys cannot sign new records.
- Historical verification is allowed only for signatures created before revocation.
- Emergency authority requires independent dual control.
- Emergency grants must be time bounded.
- Secret material must never be accepted in governance payloads.

Expected tests:

- crypto and emergency authority cases in `apps/api/tests/test_extended_resilience_governance.py`

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q apps/api/tests/test_extended_resilience_governance.py
```

## Prompt 6: P9 Institutional Runbooks, Rehearsals, Vendor Exit, Experiments, And Archive Verification

Implement the governance records for institutional operating continuity.

Scope:

- institutional runbooks
- rehearsals
- vendor exit plans
- technology substitution records
- resilience experiments
- artifact migration records
- archive verification runs
- generic institutional governance records

Rules:

- Successful or tested statuses require evidence hashes.
- Chaos and resilience experiments require evidence before completion.
- Artifact migrations require non-empty proof.
- Vendor exit rehearsals cannot claim tested status without evidence.
- Generic governance records must reject secret-like payload fields.

Expected tests:

- provider evidence and generic governance cases in `apps/api/tests/test_extended_resilience_governance.py`

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q apps/api/tests/test_extended_resilience_governance.py
```

## Prompt 7: P9 Crisis Mode Governance

Implement crisis activation governance and closeout rules.

Scope:

- `CrisisActivation`
- `CrisisGovernancePolicy`
- crisis mode activation persistence
- crisis governance API record path

Rules:

- Crisis activation must require accountable commander and second authority.
- Crisis mode must not close without independent integrity and authority review.
- Crisis capabilities must remain explicit and auditable.
- No normal governance bypass may be implied by crisis mode.

Expected tests:

- crisis cases in `apps/api/tests/test_extended_resilience_governance.py`

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q apps/api/tests/test_extended_resilience_governance.py
```

## Prompt 8: P9 Governed Recovery Integration

Integrate resilience with governed recovery workflows.

Scope:

- recovery incidents
- recovery assessments
- recovery approvals
- recovery attempts
- recovery processor behavior
- recovery API routes

Rules:

- Recovery must be assessment-driven.
- Recovery attempts must be evidence-producing.
- Approval must be explicit and authority-scoped.
- Processor must not invent missing external state.
- Recovery completion must leave auditable outcome records.

Expected tests:

- `apps/api/tests/test_recovery_domain.py`
- `apps/api/tests/test_recovery_control_plane.py`
- `apps/api/tests/test_recovery_processor.py`

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q \
  apps/api/tests/test_recovery_domain.py \
  apps/api/tests/test_recovery_control_plane.py \
  apps/api/tests/test_recovery_processor.py
```

## Prompt 9: P9 End-To-End Resilience Verification

Run the full P9 focused verification and fix only P9-related regressions.

Scope:

- all P9 resilience, extended governance, provider, and recovery tests
- migration import/metadata checks
- route registration checks

Do not:

- repair unrelated roadmap slices
- collapse multiple Alembic heads unless explicitly requested
- refactor unrelated APIs

Expected verification:

```bash
rtk apps/api/.venv/bin/pytest -q \
  apps/api/tests/test_resilience_control_plane.py \
  apps/api/tests/test_resilience_api_contract.py \
  apps/api/tests/test_extended_resilience_governance.py \
  apps/api/tests/test_local_resilience_providers.py \
  apps/api/tests/test_recovery_domain.py \
  apps/api/tests/test_recovery_control_plane.py \
  apps/api/tests/test_recovery_processor.py
```

Success criterion:

- all focused P9 tests pass
- graphify is updated
- final response states implemented slices, verification commands, and residual risks
