# Agent Architecture

## Purpose

Agent architecture defines how specialized AI workers operate with authority, context, skills,
tools, memory, evaluation, and promotion.

## Responsibilities

This chapter owns agent philosophy, lifecycle, definition, capabilities, skills, tools, context,
memory, communication, collaboration, evaluation, templates, runtime, and SDK expectations.

## Data Model

Important records include skill definitions, tool definitions, model deployments, runtime sessions,
context manifests, prompt registries, prompt versions, invocations, validation results, and agent
assignments.

## Interfaces

Agents work through governed APIs and adapter layers. Tools and models are invoked through runtime
records so actions can be audited, validated, replayed, or rejected.

Prompt governance is exposed through `/api/v1/prompts`, prompt-version approval, rollback, and
compiled prompt retrieval. Prompt text is treated as a governed asset with owner, department,
applicable crew, output schema, policy document, approval state, and prompt hash.

## Security

Agents must be bounded by role, context, tool permission, repository boundary, and output
validation. Powerful tools require explicit authority and evidence.

## Evolution

Agent specialization should improve through successful evidence, failed-task learning, reusable
prompts, skill catalog growth, and promotion rules.

## References

- [Agent Catalog](../../architecture/agent-catalog.md)
- [Model and Prompt Governance](../../architecture/model-prompt-governance.md)
- [Agent Standard](../../etra/agent-standard.md)
