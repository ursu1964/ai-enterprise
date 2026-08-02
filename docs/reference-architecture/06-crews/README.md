# Crew Architecture

## Purpose

Crew architecture defines how multiple agents cooperate on one governed objective without losing
authority, traceability, or quality control.

## Responsibilities

It owns crew definition, templates, collaboration model, formation, runtime, evaluation, lifecycle,
and the dashboard language used to show crew activity.

## Workflow

Crews are formed from project needs, role authority, agent capability, and current workflow phase.
They produce artifacts, decisions, events, reviews, and improvement proposals.

## Interfaces

Crew composition consumes organization governance. Crew runtime uses workflow state, project context,
tool registry, model readiness, job queues, and audit persistence.

## Observability

Operators should see which crew is active, what phase it serves, what it produced, what remains, and
which risks require attention.

## Evolution

Successful crews become templates. Repeated failures should create calibration signals, new
specialist roles, better prompts, or tighter workflow gates.

## References

- [Crew Catalog](../../architecture/crew-catalog.md)
- [Agent Runtime Operations](../../runbooks/agent-runtime-operations.md)
