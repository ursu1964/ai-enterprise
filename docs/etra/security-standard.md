# Security Standard

Mutual service identity, least privilege, encrypted secrets, signed artifacts, immutable audit,
dependency scanning, and runtime isolation are mandatory. Production credentials come from an
approved secret provider and never source control. Inputs are schema and scope validated; paths and
commands use allowlists. Workloads fail closed if KMS/HSM, identity, backup, model gateway, or
authority dependencies are absent. Threat analysis covers trust boundaries, supply chain, tenant
isolation, prompt injection, exfiltration, and recovery.

