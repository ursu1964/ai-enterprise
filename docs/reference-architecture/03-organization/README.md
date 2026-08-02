# Organization Architecture

## Purpose

Organization architecture defines who can act, which authority they have, how agents are assigned,
and how crews are formed for governed work.

## Responsibilities

It owns organizations, units, roles, role versions, agents, assignments, workflow guards, authority
evaluation, and crew composition.

## Data Model

Core records include organization, unit, role, role version, agent profile, assignment, authority
decision, and crew composition. These records must support audit and reproducible workflow behavior.

## Interfaces

Organization APIs expose role and agent management. Workflow and agent runtime components consume
authority decisions before allowing tools, model calls, or workflow transitions.

## Security

Authority must be explicit. Agents do not gain permission by being useful; they gain permission
through governed assignment and role evaluation.

## Evolution

The organization model should grow toward richer departments, project-specific crews, competency
history, promotion rules, and client-specific operating boundaries.

## References

- [Agent Catalog](../../architecture/agent-catalog.md)
- [Crew Catalog](../../architecture/crew-catalog.md)
