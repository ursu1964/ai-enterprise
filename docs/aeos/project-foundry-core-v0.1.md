# Project Foundry Core v0.1

Project Foundry is the standardized operating framework through which AI Enterprise creates
applications, platforms, AI assistants, APIs, websites, mobile applications, infrastructure,
automation workflows, data systems, integrations, cybersecurity systems, documentation, and
operational packages.

## Lifecycle

```text
Project idea
  -> Structured project intake
  -> Requirements and constraints
  -> Feasibility and risk analysis
  -> Architecture and implementation plan
  -> Work breakdown structure
  -> Parallel specialized agents
  -> Integration and testing
  -> Security and quality validation
  -> Deployment package
  -> Documentation and operations
  -> Maintenance and improvement
```

## Blueprint Layers

1. Project Intake: normalize the user request into structured inputs and visible assumptions.
2. Project Classification: select required modules such as web, API, AI assistant, data platform,
   voice, integration, security, infrastructure, or migration.
3. Planning and Architecture: produce a Project Definition Package before implementation.
4. Work Decomposition: convert approved architecture into bounded agent tasks.
5. Execution: assign specialist agents with file ownership, contracts, and test requirements.
6. Independent Review: verify correctness, security, regression risk, traceability, and evidence.
7. Integration: combine approved components without violating interface contracts.
8. Release Readiness: confirm deployment, rollback, documentation, monitoring, and approval.

## Agent Hierarchy

| Agent | Responsibility |
| --- | --- |
| Executive Orchestrator | Owns lifecycle, modules, dependencies, gates, and escalation. |
| Project Manager Agent | Maintains backlog, milestones, blockers, reports, and dependency graph. |
| Requirements Analyst Agent | Produces requirements, acceptance criteria, assumptions, and traceability. |
| Solution Architect Agent | Defines boundaries, interfaces, trade-offs, security, and architecture decisions. |
| Domain Expert Agents | Advise on industry, legal, compliance, infrastructure, data, voice, or security needs. |
| Implementation Agents | Execute bounded workstreams with explicit file and interface ownership. |
| Verification Agents | Independently review code, tests, security, architecture, performance, accessibility, and docs. |
| Release Manager Agent | Validates readiness, release notes, deployment manifests, rollback, and human approval. |

## Core Artifacts

- [Project Intake Schema](../../specifications/aeos/project-intake.schema.yaml)
- [Requirements Schema](../../specifications/aeos/requirements.schema.yaml)
- [Execution Plan Schema](../../specifications/aeos/execution-plan.schema.yaml)
- [Agent Task Schema](../../specifications/aeos/agent-task.schema.yaml)
- [Review Report Schema](../../specifications/aeos/review-report.schema.yaml)
- [Approval Matrix](../../specifications/aeos/approval-matrix.yaml)
- [Quality Gates](quality-gates.md)
- [Repository Template](../../templates/project-foundry/ROOT_AGENTS.md)
- [Prompt Contracts](../../templates/project-foundry/prompts/README.md)

## Autonomy Boundary

Project Foundry targets controlled autonomy. It may analyze repositories, draft architecture, create
work packages, generate code, run tests, prepare integration, and produce release artifacts. It must
not deploy to production, delete customer data, expose services publicly, change security policy,
use unrestricted administrator credentials, purchase services, make legal commitments, or approve
its own security exceptions.

