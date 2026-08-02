# AEOS Master Specification

AEOS is the Autonomous Enterprise Operating System. It is the platform layer that governs,
orchestrates, remembers, schedules, secures, and evolves autonomous enterprise instances.

AI Enterprise is the first enterprise instance built on AEOS. Project Foundry is the first factory
inside AI Enterprise that turns client intent into governed projects, work packages, verification,
release candidates, documentation, operations, and reusable blueprints.

## Core Principles

- Enterprises are created from blueprints, not raw free text.
- Every project inherits from Enterprise DNA and produces Project DNA.
- Codex is the engineering execution plane; AEOS owns governance, memory, policy, evidence, and
  lifecycle control.
- Agents may execute bounded work, but they do not approve their own high-risk output.
- No implementation begins without intake, requirements, constraints, ownership, and acceptance
  criteria.
- Every result must produce evidence, documentation, and reusable learning.

## Five Worlds

| World | Mission | Primary Outputs |
| --- | --- | --- |
| Client Experience | Give clients a simple professional interface. | Project requests, uploads, approvals, progress reports. |
| Consulting & Business Intelligence | Understand the business before engineering. | Enterprise DNA, capability analysis, roadmap, Project DNA. |
| Enterprise Intelligence | Think, reason, plan, and govern. | Decisions, blueprints, policies, knowledge, plans. |
| Autonomous Execution | Execute bounded specialist work. | Architecture, code, tests, docs, deployments, reviews. |
| Operations & Evolution | Operate and continuously improve. | Monitoring, support, optimization, lessons, future projects. |

## Dependency Graph

```text
Constitution
  -> Enterprise Genome
  -> Business Ontology
  -> Capability Library
  -> Service Catalog
  -> Enterprise Blueprint
  -> Enterprise Compiler
  -> Enterprise Instance
  -> Enterprise Runtime
  -> Departments
  -> Projects
  -> Workflows
  -> Tasks
  -> Agent Activities
  -> Evidence
  -> Evolution
```

## Canonical Entity Contract

Every AEOS entity follows the same identity language:

```yaml
id:
name:
description:
owner:
status:
version:
created:
modified:
relationships: []
metadata: {}
```

This applies to enterprises, organizations, departments, roles, agents, services, capabilities,
knowledge objects, workflows, rules, projects, tasks, decisions, events, artifacts, resources, and
clients.

## Implementation Order

1. Foundations: constitution, genome, rule engine, ontology, configuration.
2. Enterprise knowledge: knowledge engine, capability library, service catalog, blueprint.
3. Core runtime: kernel, event bus, scheduler, identity, security, resource manager.
4. Intelligence: decision engine, planning engine, context engine, enterprise brain.
5. Organization: department model, agent runtime interface, CrewAI adapter, workflow engine.
6. Client layer: client portal, Enterprise DNA interview, consulting division.
7. Enterprise factory: blueprint compiler, enterprise generator, runtime, deployment.

## Project Foundry Core

The first implementable package is [Project Foundry Core v0.1](project-foundry-core-v0.1.md).
It provides the contracts needed to create governed software-engineering projects safely and
repeatably.

