# Deployment Standard

A deployment unit contains an immutable signed artifact, externalized configuration, ordered
migrations, liveness/readiness checks, monitoring, release metadata, rollback instructions, and
compatibility evidence. Releases are reproducible, progressive, observable, and reversible.
Database rollback feasibility is assessed independently from application rollback. Production
activation requires real regional, identity, key, backup, model-gateway, Git, and credential adapters.

