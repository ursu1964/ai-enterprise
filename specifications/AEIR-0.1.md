# AEIR v0.1

AEIR v0.1 is the first canonical internal representation compiled deterministically from an
approved-shape AEPM v0.1 manifest. The executable contract is
`ai_enterprise.domain.aeir.AeirProjectModel`.

The representation supports Project, Intent, Outcome, Stakeholder, Capability, Process,
Requirement, Rule, Entity, Integration, Constraint, Risk, Decision, Artifact, and Relationship
objects. Risk and Artifact objects are supported by the contract but are not invented during AEPM
conversion because AEPM v0.1 does not provide those facts.

Every object retains the required identity, type, name, description, status, source, confidence,
version, and relationship references. Direct client-manifest facts enter as `unverified` with
confidence `1.0`, meaning the extraction is exact—not that the claim is approved. Preferred
technology targets become `proposed` decisions and never silently become approved architecture.

The compiler is deterministic: identical canonical AEPM content produces identical objects,
relationships, source hashes, and model hashes. The model rejects duplicate identifiers, missing
relationship endpoints, inconsistent relationship back-references, and a mismatched model hash.
