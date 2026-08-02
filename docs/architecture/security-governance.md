# Identity and Security Governance

## Purpose

The security platform answers who or what may perform each action, on which resource, for which
tenant, under which conditions, with which evidence, and for how long.

## Identity Taxonomy

The platform distinguishes workforce users, client users, service identities, workload identities,
agent identities, crew identities, workflow identities, external integration identities, and
emergency identities.

## Authorization Rule

Network access, authentication, token possession, tenant membership, and workflow assignment are not
enough. Sensitive actions require explicit policy evaluation with actor, effective actor, tenant,
resource, action, environment, delegation chain, and authority lifetime.

## Tenant Isolation Rule

Tenant isolation must be layered: request context, policy evaluation, repository boundaries,
tenant-qualified storage, tenant-aware observability, and database isolation. Missing tenant context
must fail closed for tenant-scoped actions.

## Evidence Rule

Security decisions produce structured evidence: decision identifier, actor, tenant, action,
resource, policy version, matched rule, outcome, obligations, denial reasons, and timestamp.

## Current Implementation Direction

The repo already uses actor dependencies, organization governance, authority helpers, policy
versions, audit records, and dashboard source checks. P5 extends that into a complete security
control plane with stronger tenant and identity modeling.

## References

- [Security Architecture](../reference-architecture/10-security/README.md)
- [Security Standard](../etra/security-standard.md)
- [Reference: Security Governance](../reference-architecture/16-security-governance/README.md)
