# Model and Prompt Governance

## Purpose

Model and Prompt Governance keeps AI behavior reproducible. Crews should request governed
capabilities and approved prompt versions, not depend on whichever model or prompt text happens to
be embedded in source code.

## Current Slice

The first P10 implementation adds a database-backed prompt registry. `prompt_registries` records
prompt identity, owner, department, applicable crew, status, and the active approved version.
`prompt_versions` records layered prompt content, output schema, policy document, version number,
approval status, and a stable prompt hash.

## Interfaces

- `POST /api/v1/prompts`
- `GET /api/v1/prompts`
- `POST /api/v1/prompts/{prompt_id}/versions`
- `POST /api/v1/prompt-versions/{version_id}/approve`
- `POST /api/v1/prompts/{prompt_id}/rollback/{version_id}`
- `GET /api/v1/prompts/{prompt_id}/compiled`

## Operating Rule

Only platform administrators may create, version, approve, or roll back prompts. Runtime consumers
should use compiled prompts so every model invocation can record the prompt hash and version that
influenced the output.

## Future Work

Later P10 slices should add prompt evaluations, shadow runs, experiment promotion, cost and latency
comparison, provider failover evidence, prompt deprecation windows, dashboard visibility, and
automatic detection of prompt text still embedded directly in Python source.

## References

- [Agent Architecture](../reference-architecture/05-agents/README.md)
- [Runtime Architecture](../reference-architecture/09-runtime/README.md)
- [Prompt Standard](../etra/prompt-standard.md)
