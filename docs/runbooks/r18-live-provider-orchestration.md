# R18 Live Provider Orchestration Runbook

R18 defaults to deterministic local `rule-engine` generators. Live model-provider calls are
fail-closed and must be enabled explicitly.

## Required configuration

Set the provider-specific values in the API environment:

```bash
R18_LIVE_PROVIDER_CALLS_ENABLED=true

# OpenAI
R18_OPENAI_API_KEY=...
R18_OPENAI_MODEL=gpt-5.1
R18_OPENAI_BASE_URL=https://api.openai.com/v1/responses

# Optional timeout override
R18_PROVIDER_TIMEOUT_SECONDS=120
```

Equivalent Anthropic, Google, and custom HTTP settings are documented in `.env.server.example`.

## Preflight readiness

Call the readiness endpoint with the generator registry you intend to use:

```bash
curl -sS -X POST "$API_URL/api/v1/r18/provider-readiness" \
  -H "Content-Type: application/json" \
  -H "X-Actor-ID: platform-operator" \
  -H "X-Actor-Type: human" \
  -H "X-Actor-Role: platform-admin" \
  -d '{"generator_registry": null, "orchestration_options": {}}'
```

For an external provider-backed generator, the provider must report:

- `configured: true`
- `supports_live_execution: true`
- no fatal diagnostics

## Execute with a live provider

Submit an R17 plan and R16 graph to:

```text
POST /api/v1/r18/execute-plan
```

The request must assign at least one generator to an external `model_provider`, for example
`openai`. R18 will then call the configured provider adapter for those assigned tasks.

## Optional live smoke test

The normal test suite never uses real credentials. To run the optional OpenAI smoke test:

```bash
cd apps/api
R18_RUN_LIVE_PROVIDER_TESTS=true \
R18_OPENAI_API_KEY=... \
R18_OPENAI_MODEL=gpt-5.1 \
uv run pytest -p no:cacheprovider tests/test_r18_live_provider_smoke.py -q
```

If credentials are absent, the smoke test is skipped.

## Failure behavior

R18 blocks or fails closed when:

- live provider calls are disabled,
- a required API key/model/endpoint is missing,
- provider HTTP calls fail,
- provider output omits required artifacts,
- provider output emits duplicate or unrequested artifacts,
- generated artifact content is empty.

No provider can bypass the R17 task owner assignment or R18 artifact contract.
