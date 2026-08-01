# Event Standard

Every event envelope contains `event_id`, `event_type`, `occurred_at`, `correlation_id`,
`causation_id`, `actor`, `organization_id`, `payload`, `schema_version`, and `signature`. Producers
write an immutable event only after the transaction outcome is known. Consumers are idempotent by
event ID, reject unsupported schema versions, preserve causation, and dead-letter poison messages.
Payload schemas are versioned contracts; secrets and private reasoning are forbidden.

