# Specification-First Engineering Enforcement

P9 M6–M11 and M14–M15 are enforced by approved JSON specifications under
`specifications/engineering`. Infrastructure targets are generated from the infrastructure model;
typed configuration describes required, secret, environment, and validation properties; security
roles and permissions have one deny-by-default source; and public contracts bind implementation
files to stable tokens.

Run `python tools/engineering_verify.py --static` for CI-safe repository, specification, contract,
dependency, identifier, migration, generated-artifact, and deterministic-reproduction checks. Run
`python tools/engineering_verify.py --full` for Ruff, mypy, compilation, and pytest after static
verification. Evidence is canonical JSON with SHA-256. A failed predecessor gate prevents later
gates and promotion evidence cannot be self-declared or bypassed.

Generated target descriptions are written to `infrastructure/generated`. They are derived artifacts;
edit the approved specification or versioned generator and regenerate, never hand-edit them.

