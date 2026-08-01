# Service Standard

Every service exposes liveness, readiness, metrics, and version identity. Its public surface groups
capabilities, commands, queries, events, audit, and administration; administration is authenticated
and least privilege. Startup fails closed when required infrastructure or authority stores are
unavailable. Shutdown drains work and preserves durable state. Commands are idempotent where retry
is possible, and all externally visible work has correlation and audit lineage.

