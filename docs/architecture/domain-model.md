# Domain Model

## Canonical Object Families

| Family | Objects | Primary Owner |
| --- | --- | --- |
| Project lifecycle | Manifesto, project, artifact, approval, audit event | `infrastructure/database/models.py` |
| Workflow runtime | Workflow instance, transition, step, job, retry, lease | `infrastructure/database/workflow_models.py` |
| Crew execution | Crew run, model/tool invocation, output validation | `infrastructure/database/models.py`, `infrastructure/agent_runtime/models.py` |
| Model and prompt governance | Model deployment, routing policy, prompt registry, prompt version | `infrastructure/agent_runtime/models.py` |
| Project formation | Project brief, solution proposal, delivery plan, quality review, approval pack | `ProjectFormationService`, artifact records |
| Work planning | Decomposition run, decomposition artifact, planned decomposition work package | `infrastructure/decomposition/models.py` |
| Execution delivery | Execution run, execution event, test result, candidate patch, review finding | `infrastructure/database/models.py` |
| Organization and identity | Organization, unit, role, role version, agent profile, assignment, authority | `infrastructure/organization/models.py` |
| Enterprise kernel | Enterprise resource, schedule, module, organizational thread, maturity snapshot | `domain/enterprise_kernel`, enterprise-kernel routes |
| Knowledge and evolution | Knowledge item, candidate, improvement, decision, blueprint evidence | `domain/knowledge`, evolution services |
| Resilience and recovery | Incident, assessment, approval, attempt, DR plan, backup, restore verification | recovery and resilience models |
| Security governance | Actor context, policy version, authority decision, tenant boundary, evidence | dependencies, authority helpers, future security models |
| Performance governance | Metric, recommendation, certification, learning proposal | performance routes and models |
| Query/read model | Operating picture, project operating picture, graph projection, freshness signal | query platform routes |

## Core Objects

| Object | Meaning | Lifecycle Signal |
| --- | --- | --- |
| Manifesto | Client or enterprise intent that starts project creation. | Stored as canonical JSON with hash evidence. |
| Project | Governed delivery container with repository, lifecycle status, project type, and manifest hash. | Intake, requirements, architecture, planning, execution, review, integration. |
| Artifact | Requirements, architecture, work-package, execution, review, or evidence output. | Created with type, version, content hash, and lineage. |
| Formation pack | Typed planning bundle that turns a rough idea into reviewable project intent. | Draft needs clarification, ready for approval. |
| Workflow | Durable ordered process that coordinates lifecycle steps. | State transitions, current step, operator recommendation. |
| Job | Durable worker task for asynchronous execution. | Queued, leased, retry wait, succeeded, failed, dead letter. |
| Planned decomposition work package | Candidate implementation unit produced by decomposition planning. | Candidate, validated, approved for execution-package creation. |
| Execution work package | Approved bounded implementation contract used by execution/review/integration. | Draft, awaiting approval, approved, executing, succeeded, failed. |
| Execution | Isolated work attempt with events, tests, artifacts, and review handoff. | Requested, running, completed, failed. |
| Agent | Specialized operating actor with skills, tools, authority, and evaluation. | Registered, assigned, active, evaluated, promoted. |
| Crew | Coordinated group of agents for a governed workflow phase. | Formed, executing, reviewed, released. |
| Blueprint | Reusable pattern extracted from successful enterprise work. | Candidate, validated, promoted, versioned. |
| Prompt registry | Governed prompt identity with owner, department, crew, and active version. | Draft, active, rolled back to approved version. |
| Operating picture | Read-only projection for dashboard and API clients. | Generated on demand with freshness and recommendations. |

## Implementation References

| Concept | API/Service/Test Surface |
| --- | --- |
| Project lifecycle | `/api/v1/projects`, `ProjectWorkflowService`, `test_p0_project_lifecycle_contract.py` |
| Dashboard intelligence | `/api/v1/projects/{project_id}/intelligence`, `test_dashboard_api.py` |
| Workflow runtime | workflow service, workflow models, workflow kernel tests |
| Agent runtime | `/api/v1/agent-runtime`, agent runtime tests |
| Prompt governance | `/api/v1/prompts`, prompt registry tests |
| Project formation | `/api/v1/project-formation/packs`, project formation tests |
| Query platform | `/api/v1/query/operating-picture`, query platform tests |
| Organization authority | organization routes, authority helpers, organization workflow guard tests |
| Architecture governance | architecture routes/services and architecture acceptance tests |
| Recovery/resilience | recovery/resilience routes, recovery processor tests |
| Conformance | `tools/etra_conformance.py`, `test_etra_conformance.py` |

## Traceability

The core trace is manifesto -> project -> intake -> requirements -> decision -> architecture ->
planning -> work package -> execution -> review -> integration -> evidence -> reusable blueprint.

## Invariants

Every important lifecycle step must leave an auditable record. Reusable knowledge must keep source,
decision, and evidence links so future projects inherit proof, not undocumented assumptions.

Work-package naming must stay explicit: decomposition work packages represent planned structure,
while execution work packages represent approved implementation contracts.
