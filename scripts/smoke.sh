#!/usr/bin/env bash
# reset, wait healthy, inject bad deploy, wait for terminal event, print detect/diagnose/recover (plan §8.4)
set -euo pipefail

CHAOS_URL=${CHAOS_URL:-http://127.0.0.1:7004}
OBSERVER_URL=${OBSERVER_URL:-http://127.0.0.1:7001}
GATEWAY_URL=${GATEWAY_URL:-http://127.0.0.1:7003}
TIMEOUT_S=${TIMEOUT_S:-300}

echo "reset: $(curl -fsS -X POST "$CHAOS_URL/chaos/reset")"

echo "waiting for severity 0 at $OBSERVER_URL/health/now"
deadline=$(( $(date +%s) + TIMEOUT_S ))
until [ "$(curl -fsS "$OBSERVER_URL/health/now" \
           | python3 -c 'import json,sys; print(json.load(sys.stdin)["severity"])')" = "0" ]; do
  [ "$(date +%s)" -lt "$deadline" ] || { echo "FAIL: not healthy after ${TIMEOUT_S}s" >&2; exit 1; }
  sleep 2
done

injection=$(curl -fsS -X POST "$CHAOS_URL/chaos/bad-deploy")
echo "inject: $injection"
inject_ts=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["ts"])' "$injection")

# follow SSE from the start; keep only the first incident opened after the inject
read -r -d '' FOLLOW <<'EOF' || true
import json, sys
start = float(sys.argv[1])
marks, incident = {}, None
data = []
for line in sys.stdin:
    line = line.rstrip("\n")
    if line.startswith("data:"):
        data.append(line[5:].lstrip())
        continue
    if line or not data:
        continue
    record, data = json.loads("\n".join(data)), []
    event = record["event"]
    if record["ts"] < start:
        continue
    if incident is None and event["type"] == "incident_opened":
        incident = event.get("incident_id")
    if incident is None or event.get("incident_id") != incident:
        continue
    marks.setdefault(event["type"], record["ts"] - start)
    if event["type"] in ("incident_resolved", "escalated", "handed_off"):
        break
def show(kind):
    return f"{marks[kind]:.1f}s" if kind in marks else "-"
outcome = next((k for k in ("incident_resolved", "escalated", "handed_off") if k in marks), "timeout")
print(f"incident={incident} outcome={outcome}")
print(f"detect={show('incident_opened')} diagnose={show('diagnosis_ready')} "
      f"recover={show('incident_resolved')}")
sys.exit(0 if outcome == "incident_resolved" else 1)
EOF

# curl times out the wait; a curl exit from timeout or SIGPIPE is expected, python decides pass/fail
set +o pipefail
curl -sN --max-time "$TIMEOUT_S" -H 'Last-Event-ID: 0' "$GATEWAY_URL/events" \
  | python3 -c "$FOLLOW" "$inject_ts"
