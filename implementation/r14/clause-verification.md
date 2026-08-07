# P24 — R14 exact clause verification

Status: COMPLETE  
Scope: `1/r14.txt` — Executable AI-Enterprise Manifest Schema  
Verification date: 2026-08-07

## Source reconciliation

| Source | Role | Decision |
|---|---|---|
| `1/r14.txt` | Authoritative product-platform R14 contract | Verified as Executable Manifest Schema. |
| `docs/ir/R14-IR-01-agent-framework.md` | Later implementation-ready IR contract | Preserved as Agent Framework architecture. It explicitly does not replace product-platform R14. |

R14 is closed against the strict canonical Manifest Schema contract. Minimal intake remains intentionally deferred to a future normalization layer, consistent with `docs/r14-manifest-schema-status.md` and the runtime contract.

## Clause-to-symbol verification

| R14 clause | Requirement | Repository evidence | Status |
|---|---|---|---|
| 1. Purpose | Manifest is the only project-specific input and describes business intent, not technical design. | `schemas/Manifest.schema.json`; `r14_manifest_schema_contract`; `_implementation_independence`; tests rejecting technical design | IMPLEMENTED |
| 2. Manifest Definition | Manifest answers what system to build, not how to build it. | Schema description; forbidden implementation field list; validation findings `R14-INTENT-ONLY` | IMPLEMENTED |
| 3. Core Principle | Every Manifest field is business-intent, implementation-independent, and automatically validatable. | Draft 2020-12 JSON Schema; semantic validation functions; schema executable test | IMPLEMENTED |
| 4. Manifest Lifecycle | Client → Manifest → Validation → Registry Expansion → Knowledge Graph → Execution Plan → Generated Software; Manifest immutable during generation; changes create new version. | `R14ManifestSchemaContract.lifecycle`; `r14_validate_manifest_evolution`; version immutability tests | IMPLEMENTED |
| 5. Manifest Structure | Canonical sections: metadata, organization, vision, domain, objectives, users, business entities, capabilities, workflows, business rules, policies, integrations, reporting, security, quality, constraints, deployment preferences, version. | `REQUIRED_SECTIONS`; `schemas/Manifest.schema.json.required`; schema test | IMPLEMENTED |
| 6. Metadata | Manifest identity fields exist. | `schemas/Manifest.schema.json.properties.metadata`; `manifest/crm.r14.json` | IMPLEMENTED |
| 7. Organization | Owning organization fields exist and influence policy without changing business logic. | `schemas/Manifest.schema.json.properties.organization`; strict business schema | IMPLEMENTED |
| 8. Vision | Human-readable purpose is required and preserved as business intent. | `schemas/Manifest.schema.json.properties.vision`; valid manifest fixture | IMPLEMENTED |
| 9. Domain | Business domain activates registry modules. | `schemas/Manifest.schema.json.properties.domain`; registry-reference validation | IMPLEMENTED |
| 10. Objectives | Measurable outcomes are represented. | `schemas/Manifest.schema.json.properties.objectives`; duplicate and dependency validation covers objective IDs | IMPLEMENTED |
| 11. Users | Users are business roles, not auth accounts. | `businessActor` schema; registry mapping `users` → `registry/Roles`; fixture validation | IMPLEMENTED |
| 12. Business Entities | Entities define business concepts only. | `businessEntity` schema; registry mapping `businessEntities` → `registry/Entities`; implementation-independence checks | IMPLEMENTED |
| 13. Capabilities | Capabilities describe organization actions and become generated services later. | `capability` schema; registry mapping `capabilities` → `registry/Actions`; workflow reference validation | IMPLEMENTED |
| 14. Workflows | Workflows describe business sequences and reference valid capabilities/entities. | `workflow` and `workflowStep` schema; `_workflow_references`; unknown capability/entity tests | IMPLEMENTED |
| 15. Business Rules | Business rules constrain behavior and become validation logic later. | `businessRules` schema via `namedStatement`; duplicate/dependency validation | IMPLEMENTED |
| 16. Policies | Policies define organizational governance and compatibility constraints. | `policy` schema; registry mapping `policies` → `registry/Policies`; `_policy_compatibility`; policy conflict test | IMPLEMENTED |
| 17. Integrations | Manifest specifies what to integrate, not how. | `integration` schema; registry mapping `integrations` → `registry/Integrations`; forbidden technical field checks | IMPLEMENTED |
| 18. Reporting | Business reporting needs are represented as analytics intent. | `report` schema; canonical section requirement | IMPLEMENTED |
| 19. Security | Business-level security requirements are represented without implementation mechanisms. | `securityRequirement` schema; policy compatibility checks; implementation-independence validation | IMPLEMENTED |
| 20. Quality Requirements | Non-functional requirements are represented for later generators. | `qualityRequirement` schema requiring acceptance criteria | IMPLEMENTED |
| 21. Constraints | Mandatory constraints are represented and validated for consistency. | `constraint` schema; `_constraint_consistency`; conflict test | IMPLEMENTED |
| 22. Deployment Preferences | Preferences guide generation but remain overridable by constraints. | `deploymentPreferences` schema; implementation-independence exemption only for preference path | IMPLEMENTED |
| 23. Manifest Versioning | Manifest, schema, registry, generator, and compiler versions are required. | `version` schema; `SCHEMA_VERSION`; evolution validation tests | IMPLEMENTED |
| 24. Validation Rules | Required sections, schema version, registry references, duplicate IDs, circular dependencies, constraints, policies, workflow references; failures stop generation. | `r14_validate_manifest`; `_strict_canonical_boundary`; `_registry_references`; `_duplicates`; `_cycles`; `_workflow_references`; tests | IMPLEMENTED |
| 25. Manifest Expansion | Manifest expands to business, semantic, dependency, execution, and implementation graphs; derived artifacts are not client-edited. | `R14ManifestSchemaContract.expansion_outputs` | IMPLEMENTED |
| 26. Minimal Manifest Example | Spec contains minimal intake example. Current baseline keeps strict canonical R14 and defers minimal intake normalization. | `minimal_intake_supported=False`; `normalization_layer=deferred_to_intake_normalization_layer`; `test_r14_minimal_manifest_is_rejected_until_normalization_layer_exists`; `docs/r14-manifest-schema-status.md` | ACCEPTED BOUNDARY |
| 27. Manifest Evolution | Revisions receive new version identifiers and maintain traceability. | `r14_validate_manifest_evolution`; version immutability tests | IMPLEMENTED |
| 28. Manifest Contract | Business intent once, no embedded technical implementation, canonical structure, pre-generation validation, traceability, deterministic logical output. | Runtime contract hash; JSON schema; semantic validators; tests | IMPLEMENTED |
| 29. Outcome | Universal machine-readable Manifest contract and stable input boundary for R13/R15. | `schemas/Manifest.schema.json`; API routes; status document; implementation package | IMPLEMENTED |

## Verification commands

Focused:

```bash
rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r14_manifest_schema_runtime.py tests/test_traceability.py'
```

Full:

```bash
rtk make check
```

Release:

```bash
rtk make check-release
```

## Result

No R14 strict-canonical Manifest Schema implementation gap remains. Minimal intake is not part of the accepted R14 core implementation; it remains a separate normalization-layer concern.
