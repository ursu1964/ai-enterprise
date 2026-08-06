# R18 Generator Orchestration Framework Status

R18 is implemented as the deterministic orchestration layer that executes R17 plans through
registered generator contracts and produces traceable artifact records.

Implemented:

- Built-in generator registry with first-class generator definitions.
- Generator contract metadata:
  - generator ID and name,
  - supported task types,
  - capabilities,
  - input and output schemas,
  - versioning,
  - execution policies,
  - dependencies,
  - performance profile,
  - model/prompt version metadata.
- Deterministic orchestration from R17 Execution Plan plus R16 Knowledge Graph.
- Exact generator-owner enforcement: a task must execute with the generator assigned by R17.
- Shared semantic context per task; generators receive scoped knowledge-node context.
- Central artifact repository snapshot with immutable artifact hashes.
- Artifact records with manifest origin, registry reference, generator version, model version,
  prompt version, execution plan version, and knowledge graph version.
- Lifecycle events for registered, available, assigned, executing, validated, completed, archived,
  failed, and retry-eligible states.
- Validation between generator outputs and downstream propagation.
- Conflict detection for duplicate artifact paths.
- Human review gate enforcement from R17 approval gates.
- Deterministic retry handling for transient task failures.
- Execution metrics: execution time, tokens, memory, artifacts, validation errors, retries.
- External provider readiness contract:
  - local rule-engine generators are always available,
  - external providers require credential/model references,
  - custom/local providers also require endpoint references,
  - orchestration fails closed when assigned external providers are not configured.
- Provider adapter layer:
  - shared `generate(task, graph_context, generator_config)` contract,
  - local rule-engine adapter,
  - mock OpenAI-compatible adapter for CI and deterministic tests,
  - HTTP adapter paths for OpenAI, Anthropic, Google, and custom HTTP providers,
  - provider response translation into R18 artifact records.
- Strict provider artifact contract validation:
  - every requested task output must be produced,
  - duplicate outputs are rejected,
  - unrequested outputs are rejected,
  - empty generated content is rejected.
- Environment-backed provider configuration through R18 settings and `.env.server.example`.
- Optional live OpenAI smoke test, skipped unless credentials are explicitly provided.
- Live-provider runbook at `docs/runbooks/r18-live-provider-orchestration.md`.
- Optional physical artifact materialization under a controlled artifact root.
- Append-only R18 execution history.
- API endpoints under `/api/v1/r18`.

Boundary:

- R18 coordinates generator execution and records provider-generated artifact outputs. Live external
  calls are fail-closed unless `R18_LIVE_PROVIDER_CALLS_ENABLED=true` and provider credentials/model
  settings are configured.
- The normal test suite uses mock adapters and does not require real OpenAI, Anthropic, Google, or
  custom-provider credentials.
