# R19-IR-01 — AI-Enterprise Security and Identity Engine Specification

Document ID: R19-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: Future IR/P29 reconciliation  
Primary Dependencies: R2–R18-IR-01

## Purpose

R19-IR-01 defines the Security and Identity Engine: the governed capability for
identifying actors, authenticating principals, authorizing actions, enforcing
tenant and project isolation, managing delegated authority, controlling secrets,
recording security decisions, and preserving security evidence.

Security is not route middleware alone. It is the constitutional control plane
that determines who or what may perform each enterprise action, on which
resource, under which authority, with which obligations, for how long, and with
which evidence.

R19 establishes the identity and security boundary for humans, services,
workloads, workflows, agents, integrations, runtime jobs, emergency operators,
and external systems.

## Architectural role

R19-IR-01 follows R18-IR-01. R18 observes runtime and operational signals; R19
governs identity, authority, secret access, tenant isolation, and security
decisions that those signals and actions depend on.

Existing product-platform R19 remains the Project Memory module. This IR
specification defines the constitutional security and identity engine and does
not replace that R19 module.

R19-IR-01 SHALL reconcile with existing actor dependencies, authority grants,
trusted proxy authentication, broker authentication, credential leases, workflow
guards, tenant isolation, secret scanning, security governance docs, and
production readiness controls during future implementation.

## Constitutional requirements

- Every material action SHALL have an authenticated principal or explicit denied
  authentication record.
- Principals SHALL be classified as human, service, workload, workflow, agent,
  integration, external system, or emergency operator.
- Authorization SHALL evaluate action, resource, tenant, project, actor
  attributes, delegated authority, policy version, obligations, and context.
- Network reachability, token possession, tenant membership, agent assignment,
  or service identity alone SHALL NOT grant authorization.
- Tenant, organization, project, repository, runtime, evidence, and memory
  boundaries SHALL be enforced consistently.
- Privilege is temporary, minimal, scoped, revocable, and auditable.
- Secrets are accessed through governed references or leases and SHALL NOT be
  persisted, logged, emitted in telemetry, committed, or exposed to AI context.
- Emergency access requires explicit break-glass record, expiry, dual control
  where required, and post-use review.
- Denied, failed, expired, revoked, and anomalous security decisions remain
  auditable.
- Security decisions SHALL be observable through R18 and evidence-linked through
  R11.
- AI may assist security review and anomaly detection but SHALL NOT grant
  authority, obtain raw secrets, suppress findings, or approve its own high-risk
  access.

## Bounded context

Bounded Context: Identity, Authentication, Authorization, Tenant Isolation,
Delegated Authority, Secrets, and Security Decisions

Owning Authority: Security and Identity Authority

Primary aggregate root:

- `PrincipalIdentity`

Supporting aggregates:

- `IdentityProvider`
- `PrincipalCredential`
- `AuthenticationSession`
- `TenantMembership`
- `ResourceScope`
- `RoleDefinition`
- `CapabilityGrant`
- `DelegatedAuthority`
- `PolicyDecision`
- `SecurityObligation`
- `SecretReference`
- `SecretLease`
- `EmergencyAccessGrant`
- `AccessReview`
- `SecurityFinding`
- `SecurityIncident`
- `SecurityEvidenceBinding`
- `IdentityFederationBinding`
- `WorkloadIdentityBinding`

## Canonical domain model

### PrincipalIdentity

```yaml
PrincipalIdentity:
  principal_identity_id: string
  organization_id: string
  subject: string
  principal_type: HUMAN | SERVICE | WORKLOAD | WORKFLOW | AGENT | INTEGRATION | EXTERNAL_SYSTEM | EMERGENCY_OPERATOR
  display_name: string
  identity_provider_id: string | null
  external_subject_reference: string | null
  lifecycle_status: PROVISIONED | ACTIVE | SUSPENDED | DISABLED | RETIRED | COMPROMISED
  assurance_level: LOW | MEDIUM | HIGH | PHISHING_RESISTANT | HARDWARE_BACKED
  created_at: datetime
  updated_at: datetime
  content_hash: string
```

### IdentityProvider

```yaml
IdentityProvider:
  identity_provider_id: string
  organization_id: string
  provider_type: LOCAL_DEV | OIDC | SAML | LDAP | CLOUD_IAM | WORKLOAD_FEDERATION | CUSTOM
  issuer_reference: string
  trust_policy_reference: string
  token_validation_profile: string
  lifecycle_status: DRAFT | VALIDATED | ACTIVE | SUSPENDED | RETIRED
  evidence_references: [EvidenceReference]
```

### AuthenticationSession

```yaml
AuthenticationSession:
  authentication_session_id: string
  principal_identity_id: string
  authentication_method: HEADER_ASSERTION | OIDC_TOKEN | SAML_ASSERTION | API_KEY | HMAC | MTLS | WORKLOAD_IDENTITY | BREAK_GLASS
  issuer_reference: string | null
  started_at: datetime
  expires_at: datetime
  assurance_level: string
  trusted_proxy_reference: string | null
  nonce_reference: string | null
  status: ACTIVE | EXPIRED | REVOKED | REJECTED | SUPERSEDED
  evidence_references: [EvidenceReference]
```

### TenantMembership

```yaml
TenantMembership:
  tenant_membership_id: string
  principal_identity_id: string
  organization_id: string
  tenant_id: string
  project_ids: [string]
  membership_type: OWNER | ADMIN | OPERATOR | CONTRIBUTOR | REVIEWER | VIEWER | SERVICE | AGENT | EXTERNAL
  status: REQUESTED | ACTIVE | SUSPENDED | EXPIRED | REVOKED
  valid_from: datetime
  valid_until: datetime | null
```

### RoleDefinition

```yaml
RoleDefinition:
  role_definition_id: string
  organization_id: string
  canonical_name: string
  description: string
  capabilities: [string]
  assignable_principal_types: [string]
  separation_of_duties_constraints: [string]
  status: DRAFT | APPROVED | ACTIVE | DEPRECATED | RETIRED
  policy_version: string
```

### CapabilityGrant

```yaml
CapabilityGrant:
  capability_grant_id: string
  principal_identity_id: string
  role_definition_id: string | null
  capability: string
  scope_type: ORGANIZATION | TENANT | PROJECT | REPOSITORY | WORKFLOW | AGENT | RUNTIME | EVIDENCE | SECRET | CUSTOM
  scope_id: string
  granted_by: ActorReference
  valid_from: datetime
  valid_until: datetime | null
  status: REQUESTED | ACTIVE | EXPIRED | REVOKED | SUSPENDED
  evidence_references: [EvidenceReference]
```

### DelegatedAuthority

```yaml
DelegatedAuthority:
  delegated_authority_id: string
  delegator_principal_id: string
  delegate_principal_id: string
  allowed_actions: [string]
  resource_scopes: [string]
  constraints: object
  max_duration: string
  valid_from: datetime
  valid_until: datetime
  status: REQUESTED | APPROVED | ACTIVE | EXPIRED | REVOKED | USED
  evidence_references: [EvidenceReference]
```

### PolicyDecision

```yaml
PolicyDecision:
  policy_decision_id: string
  organization_id: string
  project_id: string | null
  principal_identity_id: string | null
  effective_principal_id: string | null
  action: string
  resource_type: string
  resource_id: string
  scope_references: [string]
  policy_references: [string]
  matched_rules: [string]
  obligations: [string]
  outcome: ALLOW | DENY | CONDITIONAL_ALLOW | CHALLENGE | ERROR | NOT_APPLICABLE
  denial_reasons: [string]
  decided_at: datetime
  expires_at: datetime | null
  correlation_id: string
  evidence_reference: string | null
```

### SecretReference

```yaml
SecretReference:
  secret_reference_id: string
  organization_id: string
  project_id: string | null
  canonical_name: string
  secret_provider: ENVIRONMENT | FILE_MOUNT | VAULT | CLOUD_SECRET_MANAGER | KMS | CUSTOM
  provider_reference: string
  allowed_consumers: [string]
  rotation_policy_reference: string
  classification: CONFIDENTIAL | RESTRICTED | HIGHLY_RESTRICTED
  status: DRAFT | ACTIVE | ROTATING | DISABLED | REVOKED | RETIRED
  created_at: datetime
```

### SecretLease

```yaml
SecretLease:
  secret_lease_id: string
  secret_reference_id: string
  principal_identity_id: string
  purpose: string
  issued_at: datetime
  expires_at: datetime
  exposure_mode: ENVIRONMENT | FILE_DESCRIPTOR | MEMORY_ONLY | PROVIDER_SESSION | TOKEN_EXCHANGE
  status: ISSUED | ACTIVE | EXPIRED | REVOKED | FAILED
  policy_decision_reference: string
  evidence_reference: string | null
```

### EmergencyAccessGrant

```yaml
EmergencyAccessGrant:
  emergency_access_grant_id: string
  principal_identity_id: string
  reason: string
  affected_scopes: [string]
  requested_by: ActorReference
  approved_by: [ActorReference]
  valid_from: datetime
  valid_until: datetime
  post_use_review_required: boolean
  status: REQUESTED | APPROVED | ACTIVE | EXPIRED | REVOKED | REVIEWED
  evidence_references: [EvidenceReference]
```

## Lifecycle and invariants

Principal lifecycle:

```text
PROVISIONED → ACTIVE → SUSPENDED → ACTIVE
ACTIVE → DISABLED
ACTIVE → COMPROMISED
DISABLED → RETIRED
COMPROMISED → DISABLED
```

Grant lifecycle:

```text
REQUESTED → ACTIVE → EXPIRED
REQUESTED → ACTIVE → REVOKED
ACTIVE → SUSPENDED → ACTIVE
```

Decision lifecycle:

```text
REQUESTED → EVALUATED → RECORDED
EVALUATED → EXPIRED
```

Core invariants:

- Every material command has authenticated actor context or explicit
  authentication failure.
- Every privileged action records a policy decision.
- Every allow decision records effective principal, policy version, resource,
  scope, obligations, and expiry where applicable.
- Denials are recorded and observable without leaking restricted resource data.
- Secret leases are time-bounded and do not expose secret values in records.
- Delegated authority cannot exceed delegator authority.
- Agents cannot grant themselves roles, capabilities, scopes, tools, or secret
  access.
- Human-only approvals cannot be satisfied by agents, services, or workflows.
- Cross-tenant access is denied unless an explicit governed trust relationship
  exists.
- Emergency access expires and requires post-use review.

## Commands

R19-IR-01 SHALL define at least:

- `RegisterIdentityProvider`
- `ValidateIdentityProvider`
- `ProvisionPrincipalIdentity`
- `ActivatePrincipalIdentity`
- `SuspendPrincipalIdentity`
- `DisablePrincipalIdentity`
- `MarkPrincipalCompromised`
- `CreateTenantMembership`
- `RevokeTenantMembership`
- `CreateRoleDefinition`
- `ApproveRoleDefinition`
- `GrantCapability`
- `RevokeCapabilityGrant`
- `AuthenticatePrincipal`
- `RecordAuthenticationFailure`
- `EvaluatePolicyDecision`
- `RecordPolicyDecision`
- `CreateDelegatedAuthority`
- `ApproveDelegatedAuthority`
- `RevokeDelegatedAuthority`
- `RegisterSecretReference`
- `IssueSecretLease`
- `RevokeSecretLease`
- `CreateEmergencyAccessGrant`
- `RevokeEmergencyAccessGrant`
- `CompleteEmergencyAccessReview`
- `CreateAccessReview`
- `RecordSecurityFinding`
- `CreateSecurityIncident`
- `LinkSecurityEvidence`

Every mutating command SHALL include authenticated actor where available,
organization, project where applicable, resource scope, expected aggregate
revision, idempotency key, policy context, reason, and correlation identifier.

## Queries

R19-IR-01 SHALL provide:

- `GetPrincipalIdentity`
- `GetIdentityProvider`
- `GetAuthenticationSession`
- `GetTenantMembership`
- `GetRoleDefinition`
- `GetCapabilityGrant`
- `GetDelegatedAuthority`
- `GetPolicyDecision`
- `GetSecretReference`
- `GetSecretLease`
- `GetEmergencyAccessGrant`
- `GetAccessReview`
- `ListActivePrincipals`
- `ListSuspendedPrincipals`
- `ListPrincipalCapabilities`
- `ListActiveDelegations`
- `ListActiveSecretLeases`
- `ListEmergencyAccessGrants`
- `FindExpiredGrants`
- `FindStaleMemberships`
- `FindCrossTenantAccessAttempts`
- `FindDeniedPrivilegedActions`
- `TracePrincipalAuthority`
- `TraceDecisionToEvidence`

Queries SHALL be policy-filtered and SHALL redact secrets, tokens, credential
material, private identity-provider configuration, restricted denial details, and
protected security findings.

## Events

R19-IR-01 SHALL publish immutable domain events including:

- `IdentityProviderRegistered`
- `IdentityProviderValidated`
- `PrincipalIdentityProvisioned`
- `PrincipalIdentityActivated`
- `PrincipalIdentitySuspended`
- `PrincipalIdentityDisabled`
- `PrincipalMarkedCompromised`
- `TenantMembershipCreated`
- `TenantMembershipRevoked`
- `RoleDefinitionCreated`
- `RoleDefinitionApproved`
- `CapabilityGranted`
- `CapabilityGrantRevoked`
- `PrincipalAuthenticated`
- `AuthenticationFailed`
- `PolicyDecisionEvaluated`
- `AccessAllowed`
- `AccessDenied`
- `DelegatedAuthorityCreated`
- `DelegatedAuthorityApproved`
- `DelegatedAuthorityRevoked`
- `SecretReferenceRegistered`
- `SecretLeaseIssued`
- `SecretLeaseRevoked`
- `EmergencyAccessRequested`
- `EmergencyAccessApproved`
- `EmergencyAccessRevoked`
- `EmergencyAccessReviewed`
- `AccessReviewCreated`
- `SecurityFindingRecorded`
- `SecurityIncidentCreated`
- `SecurityEvidenceLinked`

Events SHALL include organization, project where applicable, principal, effective
principal, action, resource, scope, policy, outcome, evidence, correlation,
causation, timestamp, and classification references.

## Security and governance

R19-IR-01 SHALL enforce:

- strong identity for humans, services, workloads, workflows, agents, and
  integrations;
- fail-closed authentication in non-development environments;
- trusted proxy assertion validation where header-based identity is used;
- HMAC, nonce, timestamp, and replay protection for broker/workload requests;
- RBAC, ABAC, capability, and scope checks;
- separation of duties for critical approvals;
- tenant, project, repository, runtime, memory, evidence, and secret isolation;
- short-lived credential and secret leases;
- secret scanning and redaction;
- emergency access expiry and review;
- audit/evidence capture for privileged decisions;
- least privilege and default deny;
- explicit policy versioning and decision recording;
- protection against confused deputy and agent self-escalation.

AI may detect anomalous access patterns, propose least-privilege changes,
summarize access reviews, classify security findings, and suggest incident
triage.

AI SHALL NOT grant authority, approve emergency access, read raw secrets,
disable controls, suppress findings, or expose restricted security data through
summaries.

## Cross-module contracts

R19-IR-01 integrates with:

- R2 for project and tenant context.
- R5 for requirement approval authority.
- R6 for architecture approval authority.
- R7 for planning and work authorization.
- R8 for artifact-generation access boundaries.
- R9 for implementation execution authority.
- R10 for independent verification authority.
- R11 for security evidence and audit records.
- R12 for policy definitions, exceptions, and obligations.
- R13 for AI orchestration authority.
- R14 for agent identities, sessions, skills, tools, and supervision.
- R15 for workflow principal and delegated authority.
- R16 for repository credentials and protected branch authorization.
- R17 for deployment secrets and production authorization.
- R18 for security telemetry, alerts, and incidents.
- R20 for knowledge access controls.
- R21 for platform administration.
- R22 for constitutional authority and evolution controls.

R19 SHALL NOT replace R12 policy authoring, R11 audit evidence, R15 workflow
approval gates, or R17 deployment readiness gates.

## Repository implementation mapping

Existing repository capabilities relevant to R19-IR-01 include:

- `apps/api/src/ai_enterprise/api/dependencies.py`
- `apps/api/src/ai_enterprise/infrastructure/security/local_activation.py`
- `apps/api/src/ai_enterprise/infrastructure/execution_broker/auth.py`
- `apps/api/src/ai_enterprise/infrastructure/integration/credentials.py`
- `apps/api/src/ai_enterprise/application/organization/workflow_guard.py`
- `apps/api/src/ai_enterprise/infrastructure/review/secret_scanner.py`
- `apps/api/src/ai_enterprise/infrastructure/database/foundation_models.py`
- `apps/api/src/ai_enterprise/domain/organization/authority.py`
- `apps/api/src/ai_enterprise/domain/knowledge/retrieval.py`
- `apps/api/src/ai_enterprise/api/routes/r19_project_memory.py`
- `apps/api/src/ai_enterprise/application/r19_project_memory_runtime.py`
- `apps/api/tests/test_organizational_workflow_guard.py`
- `apps/api/tests/test_worker_queue_isolation.py`
- `apps/api/tests/test_knowledge_retrieval_context.py`
- `apps/api/tests/test_integration_git_runtime.py`
- `tools/secret_scan.py`
- `docs/reference-architecture/16-security-governance/`
- `docs/architecture/security-governance.md`

Future implementation SHALL inventory these components before adding new
runtime code. The existing R19 project memory module remains a product-platform
module and shall be reconciled as a security-controlled memory consumer where
appropriate instead of replacing it.

No new root-level Python source tree SHALL be created. Application code remains
under `apps/api/src`.

## Verification strategy

Unit tests SHALL cover:

- principal lifecycle;
- trusted proxy authentication;
- broker HMAC authentication and nonce replay prevention;
- role and capability grants;
- policy decision outcomes;
- tenant and project scope enforcement;
- delegated authority constraints;
- secret reference and lease redaction;
- emergency access expiry;
- human-only approval constraints.

Contract tests SHALL cover:

- R11 evidence capture;
- R12 policy decision references;
- R14 agent authority boundaries;
- R15 workflow principal propagation;
- R16 credential use;
- R17 deployment secret bindings;
- R18 security telemetry;
- command, query, event, and error schemas.

Integration tests SHALL cover:

- authenticated API request to authorized command;
- denied missing actor context;
- local development identity fallback;
- production fail-closed trusted proxy configuration;
- workflow guard denial for human-only actions;
- repository credential lease without persistence;
- secret scanning in change review;
- cross-project access denial.

Security tests SHALL cover:

- forged trusted proxy headers;
- replayed broker request;
- weak HMAC secret rejection;
- cross-tenant privilege escalation;
- agent self-authorization;
- raw secret leakage;
- expired grant usage;
- emergency access abuse;
- policy decision tampering.

Resilience tests SHALL cover:

- identity provider outage;
- authority store outage;
- policy-service outage;
- secret provider outage;
- nonce-store restart;
- access-review projection rebuild;
- audit/evidence capture outage.

## Acceptance criteria

R19-IR-01 is implementation-ready when:

- Principals, identity providers, authentication sessions, memberships, roles,
  grants, delegated authorities, policy decisions, secrets, emergency access,
  reviews, findings, and incidents have explicit schemas.
- Authentication and authorization are separate, deterministic decisions.
- Policy decisions record principal, effective principal, action, resource,
  scope, policy version, obligations, outcome, denial reasons, and evidence.
- Tenant and project isolation are explicit.
- Secrets are reference/lease based and never stored as plaintext records.
- Emergency access is expiring, auditable, and reviewable.
- Human-only and separation-of-duties controls are explicit.
- Agent self-escalation is prohibited.
- Commands, queries, events, security rules, repository mapping, and verification
  strategy are defined.
- The document explicitly preserves the existing R19 project memory module and
  does not create a second implementation architecture.

## Readiness verdict

| Gate | Status |
|---|---|
| Semantic completeness | PASS |
| Contract completeness | PASS |
| Governance completeness | PASS |
| Operational completeness | PASS |
| Repository compatibility | CONDITIONAL — requires IR/P29 reconciliation |
| Verification completeness | PASS |
| Cross-R consistency | PASS |

Overall status: IMPLEMENTATION READY.

R19-IR-01 is ready for Architecture Baseline v1.0 inclusion. Future
implementation should reconcile existing actor dependencies, authority grants,
trusted proxy authentication, broker authentication, credential leases, workflow
guards, tenant isolation, secret scanning, security docs, and project-memory
access controls into this IR contract without duplicating security authority.
