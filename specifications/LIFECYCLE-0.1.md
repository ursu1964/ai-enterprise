# Lifecycle v0.1

R3 keeps lifecycle, truth, and approval state independent.

Lifecycle status:

- `draft`
- `active`
- `deprecated`
- `archived`

Truth status:

- `asserted`
- `inferred`
- `assumed`
- `verified`
- `disputed`

Approval status:

- `not_required`
- `pending`
- `approved`
- `rejected`

Project workflow states:

`created -> imported -> validation_pending -> clarification_required -> client_review -> approved -> ready_for_compilation -> archived`

Approved snapshots require no unresolved blocking findings, source traceability, and required human
approval.
