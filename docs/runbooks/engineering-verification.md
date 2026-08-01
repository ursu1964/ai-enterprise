# Engineering Verification Runbook

Owner: Platform Engineering. On failure, retain the JSON report and correlation with the commit.

## Routine verification

Run static verification, regenerate artifacts, confirm a second generation is byte-identical, then
run the full gate. Review contract drift, dependency cycles, duplicate identifiers, migration graph,
configuration typing, security authority, and artifact hashes before independent approval.

## Failure and recovery

Do not skip a failed gate. Correct the authoritative specification when intent changed; correct code
when implementation drifted. Regenerate, rerun from the first failed gate, and invalidate downstream
evidence. For compromised evidence or generators, suspend promotion, rotate signing authority,
restore approved versions, and reproduce artifacts in isolation.

## Upgrade and rollback

Version specifications and generators independently. Canary generated deployment artifacts and keep
the prior approved specification, generator, manifest, and evidence bundle. Rollback selects that
complete tuple; mixing versions is prohibited.

