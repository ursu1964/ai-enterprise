# BK roadmap audit status

`1/bk.txt` currently contains one concrete implementation-ready specification:

- `R10-IR-01` — AI-Enterprise Verification and Validation Engine

The file also states that the next required specification is `R11-IR-01` —
Evidence and Audit Engine, but it does not contain the canonical `R11-IR-01`
specification body. A derived local R11 specification now exists at
`docs/bk-r11-evidence-audit-engine-spec.md` and is explicitly marked as derived.

Repository support added for this boundary:

- `tools/bk_roadmap_audit.py` parses the BK prompt/spec source.
- The audit checks BK/R10 implementation evidence paths.
- The audit reports `BK_NEXT_CANONICAL_SPEC_BODY_MISSING` when the roadmap file
  references a next spec but no matching canonical `Document ID` body is present.
- The audit checks BK/R11 derived core runtime evidence.
- The audit exits successfully for
  `r11_core_runtime_ready_canonical_spec_missing`, because BK/R10 and the BK/R11
  derived core runtime are implemented while the source-boundary remains visible.

Run:

```bash
rtk bash -lc 'cd /home/user/projects/ai-enterprise && python tools/bk_roadmap_audit.py --json'
```

Current expected status:

```text
r11_core_runtime_ready_canonical_spec_missing
```
