# R21 Execution Orchestrator service

This service directory is the R21 bootstrap home for the governed execution
orchestrator. The current implementation lives in the API application runtime
module and exposes deterministic contracts for compile, plan, execution,
approval, checkpoint, recovery, evidence, provenance, and delivery packaging.

Production deployment of this service as a separate process requires external
runtime infrastructure: durable event streaming, distributed leases, worker
fleet deployment, credential stores, and artifact repository backends.
