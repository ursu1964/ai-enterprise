# Repository Architecture Standard

Required top-level areas are `apps/`, `migrations/`, `tests` within an application, `docs/`, and
`tools/`. Optional areas are `services/`, `domains/`, `kernel/`, `sdk/`, `generators/`,
`integrations/`, and `infrastructure/`; create them when that concern exists, never as empty
decoration. Deployable code belongs in `apps`, domain code remains below a named package, database
evolution belongs only in `migrations`, and generated/runtime data is excluded from source control.

Dependencies point inward: API and infrastructure may depend on application/domain; domain must
not import API, infrastructure, SQLAlchemy, FastAPI, CrewAI, or vendor model SDKs. Public contracts
are versioned. Owners approve exceptions through an ADR.

