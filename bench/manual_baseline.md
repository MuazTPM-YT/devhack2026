# Manual baseline

Run each fault three times. Operator uses kubectl and telemetry UIs only.
Do not tell the operator which fault was injected.

Record one JSON object per trial in a separate local file. Include scenario,
injection timestamp, diagnosis time, recovery time, outcome, and operator label.
Recovery must hold through the agreed verification window. Leave recovery time
empty when escalation is the expected outcome. Do not invent measurements.

No manual trials have run yet.
