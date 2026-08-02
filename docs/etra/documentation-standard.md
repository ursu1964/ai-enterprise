# Documentation Standard

ADRs, API references, workflow/state diagrams, domain catalogs, deployment guides, and runbooks are
versioned beside code. Generated references identify their source and regeneration command. A change
updates affected documentation in the same review. Examples are executable or tested when practical.
Runbooks name owners and verification dates. Documentation cannot be the sole enforcement mechanism
for a safety invariant.

Implementation slices must close with documentation after verification. The required order is:
plan, execute, verify, then document. Dashboard changes must document the visible route, backing data
source, operator meaning, and verification evidence.
