# R-INDEX — AI-Enterprise Architecture Baseline Index

R-INDEX is the navigation layer between the R-series architecture documents and the committed repository implementation.

| R | P phase | Title | Alignment status | Evidence package |
|---|---|---|---|---|
| R2 | P12 | R2 — Foundational Domain and Manifest Concepts | complete | `implementation/r02` |
| R3 | P13 | R3 should convert R1 and R2 into the first executable implementation specification. It should define exactly what the engineering team builds before introducing the frontend, document generators, or AI interpretation. | complete | `implementation/r03` |
| R4 | P14 | R4 — AI Interpretation and Manifest Extraction Specification | complete | `implementation/r04` |
| R5 | P15 | R5 — Universal Manifest Transformation Engine (UMTE) | complete | `implementation/r05` |
| R6 | P16 | R6 — Universal Artifact Generation Framework (UAGF) | complete | `implementation/r06` |
| R7 | P17 | R7 — Universal Execution & Runtime Model (UERM) | complete | `implementation/r07` |
| R8 | P18 | R8 — Universal Governance, Evolution & Intelligence Framework (UGEIF) | complete | `implementation/r08` |
| R9 | P19 | R9 — Universal AI-Enterprise Kernel (UAK) | complete | `implementation/r09` |
| R10 | P20 | R10 — Universal Experience & Interaction Framework (UEIF) | complete | `implementation/r10` |
| R11 | P21 | R11 | complete | `implementation/r11` |
| R12 | P22 | R12 — AI-Enterprise Implementation & Bootstrap Specification | complete | `implementation/r12` |
| R13 | P23 | R13 — AI-Enterprise Repository Bootstrap Specification | complete | `implementation/r13` |
| R14 | P24 | R14 — Executable AI-Enterprise Manifest Schema | complete | `implementation/r14` |
| R15 | P25 | R15 — AI-Enterprise Manifest Compiler Specification | complete | `implementation/r15` |
| R16 | P26 | R16 — AI-Enterprise Knowledge Graph Specification | complete | `implementation/r16` |
| R17 | P27 | R17 — AI-Enterprise Execution Planning Engine Specification | complete | `implementation/r17` |
| R18 | P28 | R18 — AI-Enterprise Generator Orchestration Framework | complete | `implementation/r18` |
| R19 | P29 | R19 — AI-Enterprise Project Memory & Context Engine | complete | `implementation/r19` |
| R20 | P30 | R20 — AI-Enterprise Runtime Kernel Specification | complete | `implementation/r20` |
| R21 | P31 | R21 defines the **AI-Enterprise Execution Orchestrator**. | complete | `implementation/r21` |
| R22 | P32 | R22 defines the **AI-Enterprise Artifact Intelligence and Evidence Graph**. | complete | `implementation/r22` |

## Baseline rule

R2–R22 define what must exist. P12 onward records how each requirement is implemented in the existing repository.

Application code remains under `apps/api/src`; implementation packages contain audit, planning, and acceptance evidence only.

## IR constitutional specifications

The BK/IR constitutional modules are tracked separately from the numbered
product-platform R-series where names collide:

- `R10-IR-01` — Verification and Validation Engine:
  `docs/ir/R10-IR-01-verification-validation-engine.md`
- `R11-IR-01` — Evidence and Audit Engine:
  `docs/ir/R11-IR-01-evidence-audit-engine.md`

These IR modules reconcile to the existing BK/R10 and BK/R11 implementation
paths and do not replace the existing R10 UEIF or R11 UIEF modules.
