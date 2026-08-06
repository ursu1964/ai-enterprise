# BK roadmap audit status

`1/bk.txt` contains one concrete implementation-ready specification:

- `R10-IR-01` — AI-Enterprise Verification and Validation Engine

The file also states that the next required specification is `R11-IR-01` —
Evidence and Audit Engine. The canonical IR specification bodies are now stored
outside the prompt transcript as repository-controlled architecture artifacts:

- `docs/ir/R10-IR-01-verification-validation-engine.md`
- `docs/ir/R11-IR-01-evidence-audit-engine.md`

The earlier local R11 document remains at
`docs/bk-r11-evidence-audit-engine-spec.md` and is now superseded by the
canonical IR specification.

Repository support added for this boundary:

- `tools/bk_roadmap_audit.py` parses the BK prompt/spec source.
- The audit checks BK/R10 implementation evidence paths.
- The audit reports `BK_NEXT_CANONICAL_SPEC_BODY_MISSING` when neither the
  roadmap file nor `docs/ir/` contains the referenced canonical IR body.
- The audit checks BK/R11 derived core runtime evidence.
- The audit now passes because BK/R10, BK/R11, and their canonical IR
  specification bodies are present.

Run:

```bash
rtk bash -lc 'cd /home/user/projects/ai-enterprise && python tools/bk_roadmap_audit.py --json'
```

Current expected status:

```text
pass
```
