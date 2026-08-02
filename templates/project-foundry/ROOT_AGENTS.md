# AI-Enterprise Project Execution Rules

## Mission

Implement approved project requirements using the architecture, execution plan, security policy, and
definition of done contained in this repository.

## Source-of-truth Order

1. `governance/authority-policy.yaml`
2. `requirements/requirements.yaml`
3. `architecture/`
4. `planning/execution-plan.yaml`
5. Task-specific instructions
6. Existing implementation

Higher-priority sources override lower-priority sources.

## Mandatory Behavior

- Inspect requirements and architecture before editing code.
- Work only on assigned tasks.
- Preserve requirement traceability.
- Add tests for every behavioral change.
- Run relevant tests before declaring completion.
- Report commands executed and their results.
- Record assumptions explicitly.
- Prefer minimal, reversible changes.
- Never hide failed tests or unresolved risks.

## Approval Boundaries

Human approval is mandatory for production deployment, deletion of persistent data, access to
production credentials, authentication or authorization changes, destructive infrastructure
operations, external communications, financial transactions, and legal commitments.

## Completion Contract

A task is complete only when implementation is present, acceptance criteria are met, tests pass,
documentation is updated, security implications are reviewed, evidence is attached, and independent
review passes.

