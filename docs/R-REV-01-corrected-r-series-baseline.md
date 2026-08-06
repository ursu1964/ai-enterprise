# R-REV-01 — Corrected R-Series Baseline

No corrected R-series baseline is required for R2–R22 by the deterministic scan.

Additional correction: IR constitutional specifications are not replacements for existing product-platform R-series modules. They are tracked under `docs/ir/` and reconciled through existing repository boundaries.

Policy:

- R23 must not be started as a continuation label until R2–R22 are audited.
- New implementation must trace to an R requirement, P phase, or ADR.
- Existing functionality must be extended in place, not duplicated under a new source tree.
