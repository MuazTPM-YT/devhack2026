# Manual baseline

Run each fault three times. Operator uses kubectl and telemetry UIs only.
Do not tell the operator which fault was injected.

Record one JSON object per trial in `data/manual-results.jsonl`. Use keys
`scenario`, `started_at`, `diagnose_s`, `recover_s`, `outcome`, and `operator`.
Durations use seconds from injection.
Recovery must hold through the agreed verification window. Leave recovery time
empty when escalation is the expected outcome. Do not invent measurements.

No manual trials have run yet.
