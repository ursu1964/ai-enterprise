# R-REV-01 — Corrected R-Series Baseline

No corrected R-series baseline is required for R2–R22 by the deterministic scan.

Additional correction: `R10-IR-01` and `R11-IR-01` are constitutional IR
specifications, not replacements for the existing R10 UEIF and R11 UIEF
product-platform modules. They are implemented and audited through the BK/R10
and BK/R11 paths.

Policy:

- R23 must not be started as a continuation label until R2–R22 are audited.
- New implementation must trace to an R requirement, P phase, or ADR.
- Existing functionality must be extended in place, not duplicated under a new source tree.
