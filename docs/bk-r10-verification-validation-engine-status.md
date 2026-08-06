# BK/R10 Verification and Validation Engine status

Source prompt: `1/bk.txt`, section `R10-IR-01`.

Implemented as a reconciled capability instead of replacing the existing `/r10` user-experience module.

API prefix:

- `/api/v1/bk/r10-verification`

Implemented first vertical slice:

- exact R9-style verification handoff and baseline binding;
- governed verification campaign aggregate;
- obligation/procedure/environment/result/finding/waiver/coverage/verdict/recommendation records;
- environment qualification before execution;
- no-evidence-no-pass enforcement;
- no silent skipped-result omission;
- immutable failed result preservation across retries;
- flaky-result detection;
- governed waiver requirements: authority, justification, risk, scope, expiry, compensating controls;
- coverage assessment for mandatory obligations;
- campaign verdicts separating verification and validation status;
- satisfaction recommendations back to requirements instead of direct mutation;
- append-only event stream in the aggregate;
- filesystem persistence for deterministic local execution;
- append-only relational persistence models and Alembic migration for campaigns, obligations,
  procedures, environments, executions, results, findings, waivers, coverage, verdicts,
  satisfaction recommendations, and domain events;
- API-level `persist=true` now records filesystem snapshots plus database/audit projections through
  `BKR10PersistenceService`;
- external backend readiness contracts for CI runners, scanners, evidence stores, policy engines,
  and lab environments;
- fail-closed production validation for disabled, uncredentialed, or mock-only backends;
- deterministic mock external verification execution for CI-safe adapter testing;
- settings-backed backend configuration defaults, with request overrides for readiness checks;
- provider-neutral HTTP verification adapter with validated request/response translation and
  endpoint/credential-reference headers;
- published JSON schema contracts under `schemas/verification/`;
- registry defaults for verification methods, verification policy, and external backend readiness;
- executable example campaign under `examples/verification/`;
- machine-readable conformance report mapping BK/R10 acceptance criteria to repository evidence,
  exposed at `/api/v1/bk/r10-verification/conformance`.

Boundary:

- This is the BK/R10 application-level contract and deterministic runtime.
- Vendor-specific adapters may now be implemented either by using the provider-neutral HTTP adapter
  contract or by supplying a specialized `BKR10ExternalVerificationAdapter`.
- Real CI runners, security scanners, external evidence stores, policy engines, and lab environments
  still require actual endpoint/credential references and deployed services.
