# R14 Manifest Schema Status

R14 defines the executable, strict-canonical AI-Enterprise Manifest contract.

The R14 Manifest is the validated input boundary for the bootstrap repository. It requires every
canonical section from `r14.txt` and rejects technical implementation design such as database,
framework, microservice, API, or React-component instructions.

Minimal client intake is intentionally not accepted directly by R14. A later intake-normalization
layer may transform minimal business intake into the strict canonical Manifest shape, but R14 itself
remains the machine-readable validation target that enters Registry expansion and compilation.

Authoritative checks:

```bash
rtk bash -lc 'cd apps/api && uv run pytest -p no:cacheprovider tests/test_r14_manifest_schema_runtime.py -q'
```
