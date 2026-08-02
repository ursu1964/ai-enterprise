# Real World Infrastructure Choices

This document explains how AI Enterprise handles the choices that cannot be invented by the application.

The operator creates `docs/enterprise/real-world-infrastructure-decisions.json` from `docs/enterprise/real-world-infrastructure-decisions.template.json`. That file records the real domain, TLS provider, identity proxy, model endpoint, GitHub integration, database, object storage, Kubernetes rollout, backup restore evidence, and alert channel.

Verification commands:

```bash
make infrastructure-choices-template
make infrastructure-choices-verify
curl -fsS http://localhost:8000/dashboard/infrastructure-choices
```

The template command proves the decision schema is valid. The verify command must pass only after placeholders are replaced with real provider values.

Business rule: no production deployment is complete until this decision file is real, reviewed, and backed by proof paths for TLS renewal, identity signing, model verification, GitHub access, backup restore drills, and alert escalation.
