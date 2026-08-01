# Configuration Standard

Environment, security, infrastructure, feature flags, policy references, and model selection are
separate typed categories. Defaults are safe for local development and fail closed for production.
Secrets are references, never values in logs, prompts, artifacts, or Git. Configuration is validated
at startup, changes are audited, and effective non-secret configuration is inspectable. Feature flags
have owners, expiry, rollback behavior, and tests for both states.

