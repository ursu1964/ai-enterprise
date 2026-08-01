# Database Standard

Transactional, audit, knowledge, search, metrics, and object-storage concerns have explicit ports
and retention policies. PostgreSQL is the transactional reference, but a table is not a substitute
for a bounded-context decision. Schema changes use one ordered Alembic head, forward and downgrade
logic, constraints, immutable hashes, UTC timestamps, and safe backfill plans. Services never alter
production schemas at startup. Backups are encrypted, restored in exercises, and measured by RPO
and RTO. Audit records are append-only.

