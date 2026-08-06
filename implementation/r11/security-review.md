# P21 — R11 security review

- Security and secret scanning are enforced by `rtk make check-release`.
- Production-only credentials, approvals, and external endpoints must not be fabricated.
- Any R requirement conflicting with existing ADRs must be resolved through a new ADR.
- Acceptance requires the release gate secret scan to pass.
