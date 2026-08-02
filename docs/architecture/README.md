# AI Enterprise Architecture

This directory is the readable architecture layer for P1. It summarizes the platform from multiple
viewpoints and links to the canonical reference architecture for expansion.

## Chapter Map

- [Views](views.md): business, logical, runtime, deployment, operational, and evolution views.
- [Domain Model](domain-model.md): canonical enterprise objects, lifecycles, and relationships.
- [Context Map](context-map.md): bounded contexts and upstream/downstream dependencies.
- [Agent Catalog](agent-catalog.md): agent families and responsibilities.
- [Crew Catalog](crew-catalog.md): crew types and collaboration model.
- [Workflow Catalog](workflow-catalog.md): governed lifecycle workflows.
- [Module Catalog](module-catalog.md): enterprise modules and reusable growth paths.
- [MVP Vertical Slice](mvp-vertical-slice.md): P2 executable repository/control-plane proof.
- [Application Kernel](application-kernel.md): P4 command, aggregate, workflow, event, and outbox discipline.
- [Security Governance](security-governance.md): P5 identity, authorization, tenant isolation, and evidence model.
- [Project Formation Orchestration](project-formation-orchestration.md): P6 specialized agents that turn an idea into an approved project plan.
- [AEOS Master Specification](../aeos/README.md): Autonomous Enterprise Operating System and
  Project Foundry foundation.
- [Reference Architecture](../reference-architecture/README.md): full catalog, chapter contract,
  standards map, and ADR links.

## Discipline

Architecture docs explain why the system exists, how the parts fit together, how it runs, how it is
verified, and how it can evolve without breaking current contracts.
