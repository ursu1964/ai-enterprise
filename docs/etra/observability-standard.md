# Observability Standard

Services emit structured logs, distributed trace context, business and infrastructure metrics,
audit events, and liveness/readiness. Dimensions include organization, project, workflow, role,
agent, provider, and policy where applicable, without unbounded labels. Logs exclude secrets and
raw sensitive prompts. Alerts map to an owned runbook and measurable SLO. Correlation and causation
connect API, job, model, tool, database, and audit evidence.

