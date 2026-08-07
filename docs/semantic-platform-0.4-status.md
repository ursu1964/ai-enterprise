# Semantic Platform 0.4 Status

Status: implemented as a deterministic multi-target generation slice.

Version 0.4 proves that a canonical semantic registry can project synchronized
artifacts without making any generator an independent source of domain meaning.

Implemented:

- Canonical reference registry:
  `registry/updl-semantic-platform-0.4/reference-approval.json`
- Deterministic generator:
  `tools/semantic_platform_generate.py`
- Generation targets:
  - PostgreSQL schema
  - PostgreSQL mapping metadata
  - database enforcement report
  - semantic database migration plan
  - OpenAPI
  - UI metadata
  - test scaffolding
  - documentation
  - Mermaid lifecycle diagram
  - AI semantic context
  - generation manifest
- Coverage reporting so each generator declares whether it fully enforces,
  partially enforces, documents, or delegates semantics to runtime enforcement.
- Semantic migration planning that compares a previous registry with the current
  registry and blocks unsafe required-property additions until a backfill
  strategy is declared.
- Atomic output replacement through a staging directory.

Operational rule:

- Generated output belongs under `generated/` and is intentionally excluded from
  source control.
- The committed source of truth is the canonical registry plus generator code
  and tests.

Verification:

```bash
rtk make semantic-platform-generate
PYTHONPATH=apps/api/src python tools/semantic_platform_generate.py \
  --previous-registry registry/updl-semantic-platform-0.4/reference-approval.json \
  --output-root generated/semantic-platform-0.4
cd apps/api && .venv/bin/pytest -q tests/test_semantic_platform_generation.py
```
