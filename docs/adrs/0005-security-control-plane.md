# ADR-0005: Security Control Plane

- Status: accepted
- Date: 2026-08-01
- Owners: enterprise-architecture
- Supersedes: none
- Exception expiry: none

## Context

AI Enterprise coordinates humans, services, workflows, agents, crews, workloads, integrations, and
tenant resources. Authentication alone cannot decide which actor may perform a sensitive operation.

## Decision

Treat identity, authorization, tenant isolation, delegated authority, and compliance evidence as a
security control plane. Sensitive actions require explicit policy evaluation and structured
decision evidence.

## Alternatives considered

Route-local permission checks were rejected because they scatter policy and make audit evidence
inconsistent.

Trusting network location or token possession was rejected because reachability is not authority.

## Consequences

Actor context, tenant context, policy versions, authority helpers, audit evidence, and denial
reasons become platform contracts.

## Constitutional principles affected

This decision strengthens least privilege, tenant isolation, accountability, and compliance.

## Migration and compatibility implications

Existing actor dependencies can evolve into richer identity and policy records without breaking
public workflow APIs.

## Security and privacy implications

Privilege must be temporary and minimal. Tenant-scoped actions must fail closed when tenant context
is missing or inconsistent.

## Observability and operational implications

Security decisions should be queryable as evidence and visible in audit and operator surfaces when
they affect workflow progress.

## Verification and rollback

Tests must cover missing actor context, denied roles, tenant mismatch, expired authority, and audit
record creation. Rollback would require an explicit ADR because it weakens the security model.

## References

- [Security Governance](../reference-architecture/16-security-governance/README.md)
- [Security Standard](../etra/security-standard.md)
