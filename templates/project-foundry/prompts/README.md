# Project Foundry Prompt Contracts

Project Foundry uses a controlled prompt chain instead of one broad prompt.

## Prompt 1 - Intake Normalization

Role: Project Intake Analyst.

Output: valid `project-intake.yaml` only.

Rules:

- Do not invent mandatory business facts.
- Record uncertainties as assumptions.
- Separate requirements from proposed solutions.
- Identify missing acceptance criteria.
- Identify permissions and production risks.

## Prompt 2 - Requirements Decomposition

Role: Requirements Engineering Agent.

Outputs: `requirements.md`, `requirements.yaml`, `traceability.csv`, `assumptions.md`.

## Prompt 3 - Architecture Generation

Role: Lead Solution Architect.

Outputs: `architecture.md`, Mermaid diagrams, ADR directory, API contracts, and data model.

## Prompt 4 - Work Decomposition

Role: Technical Program Planner.

Output: `execution-plan.yaml`.

## Prompt 5 - Agent Task Execution

Role: Assigned Specialist Agent.

Output: code changes, tests, task completion report, and evidence log.

## Prompt 6 - Independent Review

Role: Independent Verification Agent.

Decision: `PASS`, `PASS_WITH_CONDITIONS`, or `FAIL`.

## Prompt 7 - Integration

Role: Integration Agent.

Output: integration evidence and incompatibility report when needed.

## Prompt 8 - Release Readiness

Role: Release Readiness Agent.

Output: `release-readiness-report.md`.

