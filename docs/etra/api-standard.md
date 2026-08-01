# API Standard

Public APIs use `/api/v1` (or an explicitly documented successor), UUID identities, UTC timestamps,
bounded request fields, and Pydantic contracts. Commands accept idempotency and correlation data;
updates use expected versions or immutable revision creation. Errors have a stable code, message,
correlation identifier, and safe details. Lists have deterministic order and bounded pagination.
Commands and queries remain logically separated. Authentication is required by default, internal
execution endpoints are not public, and compatibility is assessed before release.

