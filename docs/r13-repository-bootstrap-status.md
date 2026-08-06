# R13 Repository Bootstrap Status

R13 defines the executable repository skeleton for AI-Enterprise.

The top-level directories, named internal homes, marker README files, example manifests, and
minimal JSON schema files are intentional bootstrap anchors. They establish where Manifest,
Registry, schema, compiler, planner, runtime, generator, validator, knowledge, workspace, template,
test, log, and config responsibilities live.

They do not claim to be the full business implementation of later roadmap phases. R14 is responsible
for the first executable Manifest Schema, and later roadmap phases fill the generator, validator,
runtime, template, and production implementation details.

The authoritative runtime/API check is:

```bash
rtk bash -lc 'cd apps/api && uv run pytest -p no:cacheprovider tests/test_r13_repository_bootstrap_runtime.py -q'
```
