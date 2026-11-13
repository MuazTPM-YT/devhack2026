# Testing Akira end to end: CLI, UI and Discord

This guide covers one loop: break the shop from the chaos shell, watch Akira work in
the UI, approve its fix in Discord, then put the shop back. The timings come from live
runs on 2026-11-13 (`team/anirudh/STATE.md`).

## 1. Start everything (once)

Run each service in its own terminal, from the repo root, **in this order**. The
observer follows the gateway's event stream, so start it *after* the gateway. If you
ever restart the gateway, restart the observer too (see Troubleshooting).

| # | Service | Port | Command |
|---|---|---|---|
| 1 | Gateway (checklist, event bus, approvals) | 7003 | `uv run --locked --env-file .env uvicorn gateway.main:app --host 127.0.0.1 --port 7003` |
| 2 | Observer (detects incidents) | 7001 | `uv run --locked --env-file .env uvicorn observer.main:app --host 127.0.0.1 --port 7001` |
| 3 | Brain (diagnosis, model call) | 7002 | `uv run --locked --env-file .env uvicorn brain.main:app --host 127.0.0.1 --port 7002` |
| 4 | Notifier (Discord) | 7005 | `uv run --locked --env-file .env uvicorn notifier.main:app --host 127.0.0.1 --port 7005` |
| 5 | Chaos panel (breaks the shop, admin) | 7004 | `uv run --locked --env-file .env uvicorn chaos.main:app --host 127.0.0.1 --port 7004` |
| 6 | UI | 3000 | `cd ui && npm run dev` (or `npm run build && npx next start -p 3000`) |

Start the chaos panel only while the shop is healthy: its first start saves the
healthy snapshot that `reset` restores.

Your Discord user id must be listed in `ONCALL_APPROVER_IDS` in `.env`
(comma-separated). Without it, Approve answers "not authorised". The gateway and the
notifier read that list only at startup, so restart both after you change it.

## 2. Open the three windows

1. **Terminal**: the chaos shell, `uv run -m chaos.cli` (no arguments).
2. **Browser**: <http://localhost:3000/live> (Live incident), <http://localhost:3000>
   (Overview).
3. **Discord**: `#wake` channel (approvals and wake-ups). Resolved cards go to the FYI
   channel.

## 3. Shell commands

Type `/` to open the command menu. Move with ↑ ↓; Tab or Enter fills a command in.
After `/inject `, press Tab to see the faults.

| Command | What it does |
|---|---|
| `/inject <fault>` | Breaks the shop with one fault (list below). The fault stays until `/reset`, and is logged as ground truth. |
| `/watch` | Streams every step Akira takes, live, in colour: the same events as the UI timeline. Ctrl+C returns to the prompt. |
| `/status` | Severity (0 = healthy) and per-service health (error ratio, p95, bad pods) from the observer. |
| `/reset` | Undoes every fault and waits until severity stays 0 for 30 s (can take a few minutes). |
| `/faults` | Lists the faults with one line each. |
| `/truth [n]` | What was really broken and when (last n entries, default 15). Akira never sees this. |
| `/kubectl <args>` | Runs kubectl as cluster admin, e.g. `/kubectl -n shop scale deploy/cart --replicas=0`. Writes are logged as ground truth; reads (`get`, `describe`, `logs`, …) are not. No shell: pipes and `$()` are plain words. |
| `/help` | Shows the command list. |
| `/clear` | Clears the screen. |
| `/quit` | Leaves the shell (Ctrl+D works too). The shop keeps whatever state you left it in. |

The bottom bar shows whether the gateway and observer are up, and the current
severity. Check it before you inject.

One-shot form (scripts): `uv run -m chaos.cli <command>`, e.g.
`uv run -m chaos.cli inject bad-deploy`, `... status`, `... reset`, `... truth --last 5`,
`... kubectl -n shop get pods`.

## 4. The test loop

### Before each test

- `/status` shows `severity 0` and every service OK. `kafka` and `valkey-cart` have no
  error or p95 numbers ("No data" on the Overview); that is normal, they serve no
  traced requests.
- The UI sidebar shows **Gateway streaming** and **Observer severity 0**.
- No incident is open (Live incident tag is not "Open").

### Run one fault

1. `/inject bad-deploy`
2. `/watch` (optional) to follow the agent in the terminal.
3. Watch <http://localhost:3000/live>. It switches to the new incident by itself.
4. Wait for the approval in Discord `#wake`, then press **Approve**.
5. Wait for the outcome card.
6. `/reset` before the next fault.

### What happens and how long it takes (bad-deploy, measured)

| Time after `/inject` | What you see | Where |
|---|---|---|
| 0 s | `injected … bad_deploy payment` | shell |
| ~20 s | payment errors start (new pods roll out) | `/status`, Overview |
| **~45–55 s** | **Incident opens.** Stage *Detect* done, flow map lights Observer → Brain | UI, `/watch` |
| +0–35 s | Culprit found (from error traces), evidence bundle, rule matched (`recent change` → `rollback_deploy`) | UI timeline |
| up to +90 s | Model call (OpenCode Go, 90 s deadline) | flow map: Brain → Model |
| **~1.5–2.5 min** | **Approval card in Discord `#wake`** ("NEEDS APPROVAL: payment"), with diff, forecast and Approve / Reject | Discord, UI Approval section |
| you decide | **5 min** to answer before it expires; the agent re-pages every 2 min | Discord |
| right after Approve | The gates run again, then `rollback_deploy` executes (receipt #N) | UI timeline, flow map: Gateway → Kubernetes |
| next 1–2 min | Health checks every 5 s; severity falls to 0; harm check | UI Severity chart, `/watch` |
| **~4–6 min total** | **Outcome card**: "FIXED in …: payment; payment errors 43.0% -> 0.0%" | Discord FYI channel, UI Outcome |

If no approval card has arrived **3 minutes** after the incident opened, see
Troubleshooting.

### Faults and what Akira should do

Every gate is closed today (trust bound 0% < 90% bar), so every fix asks a human first.

| Fault | Breaks | Expected fix | Detection | Notes |
|---|---|---|---|---|
| `bad-deploy` | payment ships `payment:v2-bad`, ~40% of charges fail | `rollback_deploy payment` | ~50 s | the reference run |
| `flag-flip` | flag `paymentFailure` = 50% | `revert_config` on the flag | ~1 min | verify waits an extra 90 s (flagd reloads the ConfigMap after ~60 s) |
| `broken-config` | checkout points at `payment:9999`, every order fails | `revert_config` on checkout's env | ~1 min | |
| `memory-leak` | recommendation cache leak, OOMKilled after ~2 min | `revert_config` on the leak flag | **~2.5–3 min** (needs the OOM) | slowest to show up |
| `datastore-down` | valkey-cart scaled to 0, cart fails | `scale` back up, or escalation | ~1 min | valkey-cart is protected: only a scale back is allowed, never other changes |
| `shared-outage` | kafka scaled to 0, checkout errors within 90 s | major incident; `scale` back, or escalation | ~2 min | several services fail at once; kafka is protected |
| `/kubectl …` | anything you choose | depends | depends | e.g. `-n shop set env deploy/shipping QUOTE_ADDR=quote:1` |

### Discord cards

| Card | Channel | When | What to do |
|---|---|---|---|
| **NEEDS APPROVAL: <service>** | `#wake` | the fix needs a human (now: always) | Approve or Reject within 5 min |
| **FIXED in …** | FYI | the fix worked, prediction and harm check done | nothing; open the receipt link |
| **WOKE YOU BECAUSE: …** | `#wake`, re-paged every 2 min | no safe fix, approval expired or rejected, undo failed | Acknowledge, then look by hand |
| **HANDED OFF** | FYI | someone else changed the cluster mid-fix | nothing; Akira stepped back on purpose |
| **MITIGATED, NOT FIXED** | tickets | a restart helped but the cause stays | follow up later |

## 5. Rules for clean tests

- **One fault at a time, and `/reset` between faults.** The observer handles one
  incident at a time.
- **Don't inject while Akira is fixing something.** Any cluster change it did not make
  (chaos panel or kubectl) during a fix makes it **hand off**. That is the safety
  check working, not a bug.
- Wait for the outcome card before you reset. A reset mid-fix also counts as a change
  by someone else.
- `/reset` waits until the shop has been healthy for 30 s. Let it finish.

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Fault is in `/truth` but no incident opens after ~2 min (3+ min for memory-leak), and `/status` shows an unhealthy service | The observer still holds an old incident: it missed that incident's outcome, which happens after a gateway restart. It clears itself 20 min after that incident opened (`incident_max_age_seconds`) | Restart the observer (step 2 of §1). The fault is still active, so the incident opens within a minute |
| UI Live page shows an old incident | Same as above (no new incident on the bus) | Restart the observer |
| No Discord message at all | Notifier (7005) not running | Start it (§1 #4). It resumes from its saved cursor, so it does not re-post old cards |
| Approve says "not authorised" | Your Discord id is not in `ONCALL_APPROVER_IDS` | Add it to `.env`, restart gateway, then observer, then notifier |
| Incident ended "handed off" | You injected or reset during the fix | Expected. `/reset`, then run one fault at a time |
| Incident ended "escalated: approval expired" | Nobody answered within 5 min | Run it again and approve sooner |
| UI shows "Gateway unreachable" or "connecting" | Gateway down | Start it, then restart the observer |
| UI error "Hydration failed" on `/live` | Stale Next dev server after big UI changes | Restart `npm run dev` |
| Shell bar shows the observer red | Observer down | Start it (§1 #2) |
