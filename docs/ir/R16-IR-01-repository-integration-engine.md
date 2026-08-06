# R16-IR-01 — AI-Enterprise Repository Integration Engine Specification

Document ID: R16-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P26 reconciliation  
Primary Dependencies: R2–R15-IR-01

## Purpose

R16-IR-01 defines the Repository Integration Engine: the governed capability for
connecting AI-Enterprise to source repositories, branches, commits, patches,
pull requests, package registries, repository policies, and external source
control systems.

Repository integration is not raw Git access. It is a controlled boundary where
every read, write, patch, branch operation, review request, publication, and
rollback is authorized, scoped, reproducible, evidence-backed, and attributable.

R16 enables implementation and generated artifacts to move between
AI-Enterprise and physical repositories without allowing agents, workflows, or
services to mutate source control outside policy.

## Architectural role

R16-IR-01 follows R15-IR-01. R15 governs process execution; R16 governs
repository integration steps performed by those processes.

Existing product-platform R16 remains the Knowledge Graph runtime module. This
IR specification defines constitutional repository integration and does not
replace that R16 module.

R16-IR-01 SHALL reconcile with existing integration, Git, governed change,
review, recovery, execution workflow, release-gate, and artifact-publication
components during future implementation.

## Constitutional requirements

- Every repository connection has stable identity, owner, organization, remote
  reference, allowed operations, credential reference, and policy profile.
- Repository credentials are referenced through governed secret mechanisms and
  SHALL NOT be embedded in repository records, commands, evidence, logs, or
  generated artifacts.
- Every write operation binds to exact repository, branch, base commit, base
  tree, change set, actor, workflow execution, policy decision, and evidence.
- Protected branches are deny-by-default and require explicit policy approval.
- Agents cannot push, merge, tag, release, publish packages, or change protected
  repository configuration without R14 authority and R12 policy approval.
- Patch application validates scope, path restrictions, content hash, base
  revision, and approval reference before mutation.
- A branch or target revision advancing unexpectedly SHALL block the write or
  require governed rebase/requalification.
- Pull requests, merge requests, reviews, tags, releases, and package
  publications are first-class repository integration records.
- Failed, denied, skipped, superseded, reverted, and rolled-back repository
  operations remain auditable.
- Repository evidence is captured through R11, workflow state through R15, and
  verification readiness through R10.
- Repository integration SHALL support local deterministic tests without real
  external credentials and production adapters with explicit preflight checks.

## Bounded context

Bounded Context: Repository Connections, Change Transport, Review, Publication,
and Rollback

Owning Authority: Repository Integration Authority

Primary aggregate root:

- `RepositoryConnection`

Supporting aggregates:

- `RepositoryPolicyProfile`
- `RepositoryCredentialBinding`
- `RepositorySnapshot`
- `RepositoryBaseline`
- `RepositoryChangeSet`
- `RepositoryPatch`
- `RepositoryBranchOperation`
- `RepositoryWriteAttempt`
- `RepositoryReviewRequest`
- `RepositoryMergeRequest`
- `RepositoryTag`
- `RepositoryRelease`
- `PackagePublication`
- `RepositoryRollbackPlan`
- `RepositoryRollbackExecution`
- `RepositoryIntegrationEvidence`
- `RepositoryExternalAdapter`

## Canonical domain model

### RepositoryConnection

```yaml
RepositoryConnection:
  repository_connection_id: string
  organization_id: string
  project_id: string | null
  canonical_name: string
  provider: LOCAL_GIT | GITHUB | GITLAB | BITBUCKET | AZURE_REPOS | CUSTOM_GIT | PACKAGE_REGISTRY | CUSTOM
  remote_reference: string
  default_branch: string
  allowed_target_branches: [string]
  protected_branch_patterns: [string]
  credential_binding_id: string | null
  policy_profile_id: string
  lifecycle_status: DRAFT | VALIDATED | ACTIVE | SUSPENDED | DEGRADED | RETIRED
  created_at: datetime
  updated_at: datetime
  content_hash: string
```

### RepositoryPolicyProfile

```yaml
RepositoryPolicyProfile:
  repository_policy_profile_id: string
  allowed_operations: [READ | SNAPSHOT | PATCH | COMMIT | BRANCH | PUSH | PR | MERGE | TAG | RELEASE | PACKAGE_PUBLISH | ROLLBACK]
  forbidden_paths: [string]
  allowed_paths: [string]
  required_reviews: integer
  required_status_checks: [string]
  signing_required: boolean
  protected_branch_write_policy: string
  package_publication_policy: string | null
  evidence_requirements: [string]
  status: DRAFT | APPROVED | ACTIVE | SUPERSEDED | RETIRED
```

### RepositorySnapshot

```yaml
RepositorySnapshot:
  repository_snapshot_id: string
  repository_connection_id: string
  branch: string
  commit_sha: string
  tree_sha: string
  snapshot_path_reference: string | null
  snapshot_mode: LOCAL_WORKTREE | BARE_MIRROR | ARCHIVE | PROVIDER_API
  dependency_lock_hashes: [string]
  configuration_hashes: [string]
  created_by: ActorReference
  created_at: datetime
  evidence_references: [EvidenceReference]
```

### RepositoryChangeSet

```yaml
RepositoryChangeSet:
  repository_change_set_id: string
  repository_connection_id: string
  workflow_execution_id: string | null
  implementation_result_id: string | null
  base_commit_sha: string
  base_tree_sha: string
  target_branch: string
  change_intent: string
  affected_paths: [string]
  patch_ids: [string]
  artifact_references: [string]
  approval_reference: string | null
  status: DRAFT | VALIDATED | APPROVED | APPLIED | PUBLISHED | MERGED | REJECTED | REVERTED | SUPERSEDED
  content_hash: string
```

### RepositoryPatch

```yaml
RepositoryPatch:
  repository_patch_id: string
  repository_change_set_id: string
  patch_reference: string
  patch_sha256: string
  affected_paths: [string]
  forbidden_path_hits: [string]
  base_commit_sha: string
  generated_by: ActorReference | AgentReference | ServiceReference
  approval_reference: string | null
  validation_status: UNVALIDATED | VALID | INVALID | SUPERSEDED
  evidence_references: [EvidenceReference]
```

### RepositoryWriteAttempt

```yaml
RepositoryWriteAttempt:
  repository_write_attempt_id: string
  repository_connection_id: string
  repository_change_set_id: string
  operation_type: PATCH | COMMIT | PUSH | PR | MERGE | TAG | RELEASE | PACKAGE_PUBLISH | ROLLBACK
  actor: ActorReference | AgentReference | ServiceReference
  target_branch: string
  expected_base_commit_sha: string
  observed_base_commit_sha: string | null
  resulting_commit_sha: string | null
  resulting_tree_sha: string | null
  policy_decision_references: [string]
  evidence_references: [EvidenceReference]
  status: QUEUED | RUNNING | SUCCEEDED | FAILED | DENIED | BLOCKED | CANCELLED | SUPERSEDED
  started_at: datetime | null
  completed_at: datetime | null
```

### RepositoryReviewRequest

```yaml
RepositoryReviewRequest:
  repository_review_request_id: string
  repository_change_set_id: string
  provider_reference: string | null
  title: string
  description: string
  source_branch: string
  target_branch: string
  required_reviewers: [ActorReference]
  required_checks: [string]
  status: DRAFT | OPEN | CHECKS_PENDING | CHANGES_REQUESTED | APPROVED | MERGED | CLOSED | REJECTED
  evidence_references: [EvidenceReference]
```

### PackagePublication

```yaml
PackagePublication:
  package_publication_id: string
  repository_connection_id: string
  package_name: string
  package_version: string
  registry_reference: string
  artifact_reference: string
  source_commit_sha: string
  provenance_reference: string
  status: PLANNED | VALIDATED | PUBLISHED | FAILED | REVOKED | SUPERSEDED
  evidence_references: [EvidenceReference]
```

### RepositoryRollbackExecution

```yaml
RepositoryRollbackExecution:
  repository_rollback_execution_id: string
  repository_connection_id: string
  repository_change_set_id: string
  rollback_strategy: REVERT_COMMIT | REVERSE_PATCH | RESET_BRANCH | RESTORE_TAG | PACKAGE_DEPRECATE | CUSTOM
  target_revision: string
  status: PLANNED | RUNNING | COMPLETED | FAILED | PARTIAL | CANCELLED
  residual_risk: string | null
  evidence_references: [EvidenceReference]
```

## Lifecycle and invariants

Repository connection lifecycle:

```text
DRAFT → VALIDATED → ACTIVE → SUSPENDED → ACTIVE
ACTIVE → DEGRADED → ACTIVE
ACTIVE → RETIRED
```

Change set lifecycle:

```text
DRAFT → VALIDATED → APPROVED → APPLIED → PUBLISHED → MERGED
DRAFT → REJECTED
APPROVED → SUPERSEDED
PUBLISHED → REVERTED
```

Core invariants:

- Every mutating repository operation references one active repository
  connection and one approved policy profile.
- Every write attempt records expected and observed base revisions.
- Every patch records hash, base commit, affected paths, and validation result.
- Protected branch operations require explicit policy approval.
- Credentials are never stored as plaintext in domain records.
- Denied and failed operations are durable evidence.
- Branch advancement requires requalification before write.
- Package publication references exact source commit and artifact provenance.
- Rollback operations preserve the original operation history.
- Provider-specific identifiers do not replace canonical AI-Enterprise
  identities.
- Local test adapters and production provider adapters share the same domain
  contract.

## Commands

R16-IR-01 SHALL define at least:

- `RegisterRepositoryConnection`
- `ValidateRepositoryConnection`
- `ActivateRepositoryConnection`
- `SuspendRepositoryConnection`
- `RetireRepositoryConnection`
- `CreateRepositoryPolicyProfile`
- `BindRepositoryCredential`
- `PreflightRepositoryAdapter`
- `CreateRepositorySnapshot`
- `CreateRepositoryBaseline`
- `CreateRepositoryChangeSet`
- `RegisterRepositoryPatch`
- `ValidateRepositoryPatch`
- `ApproveRepositoryChangeSet`
- `ApplyRepositoryPatch`
- `CreateRepositoryCommit`
- `PushRepositoryCommit`
- `OpenRepositoryReviewRequest`
- `RecordRepositoryReviewDecision`
- `MergeRepositoryReviewRequest`
- `CreateRepositoryTag`
- `CreateRepositoryRelease`
- `PublishPackage`
- `PlanRepositoryRollback`
- `ExecuteRepositoryRollback`
- `RecordRepositoryOperationEvidence`

Every mutating command SHALL include authenticated actor, organization, project
where applicable, repository connection, expected aggregate revision,
idempotency key, policy context, reason, and correlation identifier.

## Queries

R16-IR-01 SHALL provide:

- `GetRepositoryConnection`
- `GetRepositoryPolicyProfile`
- `GetRepositorySnapshot`
- `GetRepositoryBaseline`
- `GetRepositoryChangeSet`
- `GetRepositoryPatch`
- `GetRepositoryWriteAttempt`
- `GetRepositoryReviewRequest`
- `GetPackagePublication`
- `ListRepositoryConnections`
- `ListRepositoryChangeSets`
- `ListOpenRepositoryReviewRequests`
- `ListFailedRepositoryOperations`
- `TraceRepositoryChangeSet`
- `TraceRepositoryOperationToEvidence`
- `FindRepositoryOperationsMissingEvidence`
- `FindUnreviewedProtectedBranchWrites`
- `FindRepositoryCredentialConfigurationGaps`
- `CompareRepositoryBaselines`

Queries SHALL be policy-filtered and SHALL redact credentials, tokens, secrets,
private remote details, and restricted file content.

## Events

R16-IR-01 SHALL publish immutable domain events including:

- `RepositoryConnectionRegistered`
- `RepositoryConnectionValidated`
- `RepositoryConnectionActivated`
- `RepositoryConnectionSuspended`
- `RepositoryCredentialBound`
- `RepositoryAdapterPreflightPassed`
- `RepositoryAdapterPreflightFailed`
- `RepositorySnapshotCreated`
- `RepositoryBaselineCreated`
- `RepositoryChangeSetCreated`
- `RepositoryPatchRegistered`
- `RepositoryPatchValidated`
- `RepositoryPatchRejected`
- `RepositoryChangeSetApproved`
- `RepositoryPatchApplied`
- `RepositoryCommitCreated`
- `RepositoryPushSucceeded`
- `RepositoryPushFailed`
- `RepositoryReviewRequestOpened`
- `RepositoryReviewDecisionRecorded`
- `RepositoryReviewRequestMerged`
- `RepositoryTagCreated`
- `RepositoryReleaseCreated`
- `PackagePublished`
- `PackagePublicationFailed`
- `RepositoryRollbackPlanned`
- `RepositoryRollbackCompleted`
- `RepositoryRollbackFailed`
- `ProtectedBranchWriteDenied`
- `RepositoryBranchAdvancedDetected`

Events SHALL include organization, project, repository, branch, base revision,
result revision where applicable, actor, policy, evidence, correlation,
causation, timestamp, and provider references.

## Security and governance

R16-IR-01 SHALL enforce:

- strong identity for human, service, workflow, and agent repository actors;
- deny-by-default write access;
- least-privilege credentials and short-lived credential leases where possible;
- protected branch policy enforcement;
- path allowlist and denylist enforcement;
- commit/tag signing policy where required;
- separation of duties for reviews and merges;
- secret scanning and sensitive-data redaction before publication;
- tenant and project isolation;
- provider webhook authenticity validation;
- package-registry token scoping;
- supply-chain provenance capture;
- idempotency for mutating repository commands;
- safe rollback and recovery controls;
- auditability of denied, failed, and privileged actions.

AI may propose changes, create patches, summarize diffs, classify review
comments, recommend rollback plans, and identify risky files.

AI SHALL NOT bypass review, approve its own protected-branch writes, obtain raw
credentials, force-push protected branches, hide failed writes, or publish
packages without governed authority.

## Cross-module contracts

R16-IR-01 integrates with:

- R2 for project and Manifest repository intent.
- R5 for requirement traceability in change sets.
- R6 for architecture-impact and conformance references.
- R7 for planned work-package links.
- R8 for generated artifacts entering repositories.
- R9 for implementation result and verification handoff links.
- R10 for pre-merge and post-publication verification gates.
- R11 for repository evidence, diffs, audit records, and provenance.
- R12 for branch, credential, publication, and exception policies.
- R13 for AI-driven repository operation orchestration.
- R14 for agent authority and tool boundaries.
- R15 for repository steps inside workflows.
- R17 for deployment and release source revision binding.
- R18 for repository-operation telemetry.
- R19 for identity, delegation, secrets, and access enforcement.
- R20 for organizational repository knowledge.
- R21 for platform repository administration.
- R22 for constitutional baseline changes.

R16 SHALL NOT independently approve requirements, verification verdicts,
deployment authorization, or constitutional evolution.

## Repository implementation mapping

Existing repository capabilities relevant to R16-IR-01 include:

- `apps/api/src/ai_enterprise/infrastructure/integration/`
- `apps/api/src/ai_enterprise/application/integration/`
- `apps/api/src/ai_enterprise/application/recovery/`
- `apps/api/src/ai_enterprise/infrastructure/recovery/`
- `apps/api/src/ai_enterprise/application/change_management/`
- `apps/api/src/ai_enterprise/application/review/`
- `apps/api/src/ai_enterprise/application/execution_workflow.py`
- `apps/api/src/ai_enterprise/infrastructure/repositories/git_repository.py`
- `apps/api/tests/test_integration_git_runtime.py`
- `apps/api/tests/test_governed_change_kernel.py`
- `apps/api/tests/test_rollback_metadata_hook.py`
- `tools/release_gate_evidence.py`
- `tools/release_artifact.py`
- `schemas/production-readiness/`

Future implementation SHALL inventory these components before adding new
runtime code. The existing R16 Knowledge Graph runtime remains a
product-platform module and shall be reconciled as repository intelligence
context where appropriate instead of replacing it.

No new root-level Python source tree SHALL be created. Application code remains
under `apps/api/src`.

## Verification strategy

Unit tests SHALL cover:

- repository connection validation;
- credential binding without secret disclosure;
- policy profile evaluation;
- branch and path restrictions;
- patch hash and base revision validation;
- protected branch denial;
- review and merge state transitions;
- package publication readiness;
- rollback planning;
- evidence-gap handling.

Contract tests SHALL cover:

- R11 evidence capture;
- R12 policy decisions;
- R14 agent authority boundary;
- R15 workflow step integration;
- R17 deployment source revision binding;
- command, query, event, and error schemas.

Integration tests SHALL cover:

- local Git snapshot, patch, commit, push, review simulation, and rollback;
- branch advancement detection;
- denied protected branch write;
- package publication with filesystem/local registry adapter;
- external adapter preflight without credentials;
- optional provider tests gated by real credentials.

Security tests SHALL cover:

- credential leakage attempts;
- unauthorized push/merge/tag/package publication;
- path traversal in patches;
- secret introduction in repository diffs;
- forged webhook or provider event;
- agent self-approval;
- cross-project repository access;
- replayed write commands.

Resilience tests SHALL cover:

- remote unavailable;
- credential lease failure;
- partial push failure;
- review-provider outage;
- package-registry outage;
- rollback failure;
- duplicate provider events;
- projection rebuild from repository events.

## Acceptance criteria

R16-IR-01 is implementation-ready when:

- Repository connections, policies, credentials, snapshots, baselines, change
  sets, patches, write attempts, review requests, package publications, and
  rollbacks have explicit schemas.
- Mutating operations bind to repository, branch, base revision, actor, policy,
  workflow, and evidence.
- Protected branch, path, credential, review, signing, and package publication
  controls are explicit.
- Branch advancement blocks stale writes unless requalified.
- Denied, failed, superseded, reverted, and rolled-back operations are auditable.
- Provider-specific identifiers remain subordinate to canonical identities.
- Production provider adapters require real configuration and preflight checks.
- Local deterministic integration remains testable without real credentials.
- Commands, queries, events, security rules, repository mapping, and verification
  strategy are defined.
- The document explicitly preserves the existing R16 Knowledge Graph module and
  does not create a second implementation architecture.

## Readiness verdict

| Gate | Status |
|---|---|
| Semantic completeness | PASS |
| Contract completeness | PASS |
| Governance completeness | PASS |
| Operational completeness | PASS |
| Repository compatibility | CONDITIONAL — requires IR/P26 reconciliation |
| Verification completeness | PASS |
| Cross-R consistency | PASS |

Overall status: IMPLEMENTATION READY.

R16-IR-01 is ready for Architecture Baseline v1.0 inclusion. Future
implementation should reconcile existing integration, Git, recovery, review,
change-management, workflow, and release-gate components into this IR contract
without duplicating repository authority.
