# Release Verification Artifact

- Status: `passed`
- Environment: `non-production`
- Artifact hash: `d9245a5ee77afbf01e49adf1b2cc938e9a297fe1c42d1b89a8595886a8dbbb2b`
- Git commit: `290b1fa80f1067c7b7d82757ec0a46db61749351`
- Git dirty: `false`

## Gate summary

- Total gates: `17`
- Passed gates: `17`
- Failed gates: `0`
- Required captured evidence: `17`
- Missing captured evidence: `0`

## Production readiness

- Not a production artifact.

## Failed gates

- None

## Policy

- `archive_path`: `artifacts/release-verification.json`
- `created_after_successful_release_gate`: `True`
- `fails_when_gate_evidence_commit_mismatch`: `True`
- `fails_when_gate_evidence_tree_mismatch`: `True`
- `fails_when_gate_log_integrity_fails`: `True`
- `fails_when_git_is_dirty_or_unknown`: `True`
- `fails_when_migration_verification_fails`: `True`
- `fails_when_production_readiness_contracts_invalid`: `True`
- `fails_when_production_readiness_is_blocked`: `True`
- `fails_when_required_gate_evidence_missing`: `True`
- `records_production_evidence_plan`: `False`
- `records_production_readiness_contracts`: `False`
