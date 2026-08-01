# Compatibility Standard

Every public API, event, schema, SDK, plugin, policy, and stored artifact change is classified as
compatible, conditionally compatible, or breaking. Breaking changes require an ADR, migration guide,
announced deprecation period, dual-read/write or adapter plan where needed, rollback strategy, and
automated compatibility verification. Consumers never infer compatibility from a version string
alone; supported ranges and schema identifiers are explicit.

