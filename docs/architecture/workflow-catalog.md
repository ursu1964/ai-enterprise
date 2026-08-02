# Workflow Catalog

| Workflow | Start | Gates | Proof |
| --- | --- | --- | --- |
| Project Formation | Natural-language idea or manifesto. | Clarification, validation, risk review, manager approval. | Project brief, solution proposal, roadmap, backlog, approval pack. |
| Manifesto Intake | Manifesto upload or idea clarification. | Valid project fields and repository boundary. | Canonical manifest hash. |
| Project Lifecycle | Project registration. | Intake, requirements, architecture, work-package approvals. | Project state and audit trail. |
| Requirements Run | Project awaiting requirements. | Human approval or rejection. | Requirements artifact. |
| Architecture Run | Approved requirements. | Human approval or rejection. | Architecture artifact and lineage. |
| Work Decomposition | Approved architecture. | Validation findings and approval. | Work-package graph. |
| Execution | Approved work package. | Isolation, test results, review. | Execution events, artifacts, tests. |
| Controlled Integration | Approved review and eligibility. | Integration approval. | Integration attempt and recovery evidence. |
| Evolution | Telemetry, failures, reusable success. | Review and promotion. | Blueprint or improvement record. |

Every workflow should expose current state, next action, remaining work, failure path, and recovery
path in human language.
