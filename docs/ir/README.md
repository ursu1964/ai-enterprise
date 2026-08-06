# AI-Enterprise IR Constitutional Specification Catalog

The IR specifications are constitutional platform modules that may overlap in
number with the product-platform R-series. They are intentionally tracked in
`docs/ir/` so they do not replace the existing numbered R modules.

| Document ID | Title | Status | Path |
|---|---|---|---|
| R10-IR-01 | Verification and Validation Engine | IMPLEMENTATION READY | `docs/ir/R10-IR-01-verification-validation-engine.md` |
| R11-IR-01 | Evidence and Audit Engine | IMPLEMENTATION READY | `docs/ir/R11-IR-01-evidence-audit-engine.md` |
| R12-IR-01 | Policy and Governance Engine | IMPLEMENTATION READY | `docs/ir/R12-IR-01-policy-governance-engine.md` |
| R13-IR-01 | AI Orchestration Engine | IMPLEMENTATION READY | `docs/ir/R13-IR-01-ai-orchestration-engine.md` |
| R14-IR-01 | Agent Framework | IMPLEMENTATION READY | `docs/ir/R14-IR-01-agent-framework.md` |
| R15-IR-01 | Workflow and Process Engine | IMPLEMENTATION READY | `docs/ir/R15-IR-01-workflow-process-engine.md` |

## Collision rule

`R10-IR-01`, `R11-IR-01`, and later IR documents are not replacements for
existing `1/r10.txt`, `1/r11.txt`, `1/r13.txt`, `1/r14.txt`, `1/r15.txt`, or
other product-platform R documents.

Implementation must reconcile IR modules into existing repository boundaries and
must not create a second AI-Enterprise source tree.
