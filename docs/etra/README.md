# Enterprise Technical Reference Architecture

ETRA version 1.0 is the implementation contract for this repository. Its standards are normative;
exceptions require an approved ADR with an owner, expiry date, and migration plan.

Run `python tools/etra_conformance.py --root .` locally and in CI. Add `--json` for a
machine-readable report. A non-zero exit code means the repository is not conformant.

Standards cover repositories, services, APIs, events, storage, domains, workflows, agents,
prompts, policy, observability, security, testing, documentation, deployment, configuration,
compatibility, extensions, and operations. Significant decisions use the ADR process and every
substantial change uses the engineering review checklist.

