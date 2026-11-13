# SQLite repository for orchestration state (tables in schemas/migrations.py). Short immediate
# transactions, compare-and-swap on revisions, fenced task leases. Never await inside tx().
import json
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from schemas.orchestration import (BudgetUse, DelegationRecord, FindingResult, FindingSummary, IncidentLink,
                                   IntentSummary, Membership, OrchestrationPolicy, SignalAck, SignalEpisode,
                                   TaskSummary, WorkspaceSnapshot, fingerprint)

CAS_COLUMNS = {"phase", "cause_key", "deadline_at", "owner", "lease_epoch", "last_error", "tool_calls_used",
               "specialists_started"}
CALL_COUNTED = ("reserved", "ok", "error", "unknown")  # every started call costs, even a failed one


class Conflict(Exception):
    pass


class Workspace:
    # lock: pass the owner's lock when sharing its connection (the gateway's read views)
    def __init__(self, conn: sqlite3.Connection, policy: OrchestrationPolicy, clock: Callable[[], float] = time.time,
                 lock: "threading.Lock | None" = None):
        self.conn, self.policy, self.clock = conn, policy, clock
        self.lock = lock or threading.Lock()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
                self.conn.commit()
            except BaseException:
                self.conn.rollback()
                raise

    def rows(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    def row(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        found = self.rows(sql, args)
        return found[0] if found else None

    # ---- episodes and signal deliveries

    # False when this revision (or a newer one) is already stored: redelivery or out-of-order update
    def upsert_episode(self, ep: SignalEpisode) -> bool:
        with self.tx() as c:
            return self.upsert(c, ep)

    def upsert(self, c: sqlite3.Connection, ep: SignalEpisode) -> bool:
        old = c.execute("SELECT source_revision FROM signal_episodes WHERE episode_id=?", (ep.episode_id,)).fetchone()
        if old and old[0] >= ep.source_revision:
            return False
        c.execute("INSERT INTO signal_episodes (episode_id, cluster, namespace, service, symptom, "
                  "first_breach_at, sustained_at, last_observed_at, recovered_at, source_revision, evidence_json) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(episode_id) DO UPDATE SET symptom=excluded.symptom, "
                  "last_observed_at=excluded.last_observed_at, recovered_at=excluded.recovered_at, "
                  "source_revision=excluded.source_revision, evidence_json=excluded.evidence_json",
                  (ep.episode_id, ep.cluster, ep.namespace, ep.service, ep.symptom, ep.first_breach_at,
                   ep.sustained_at, ep.last_observed_at, ep.recovered_at, ep.source_revision,
                   json.dumps(ep.evidence_ids)))
        return True

    def episode(self, episode_id: str) -> SignalEpisode | None:
        r = self.row("SELECT * FROM signal_episodes WHERE episode_id=?", (episode_id,))
        return _episode(r) if r else None

    def open_episodes(self) -> list[SignalEpisode]:
        return [_episode(r) for r in self.rows("SELECT * FROM signal_episodes WHERE recovered_at IS NULL "
                                               "ORDER BY sustained_at, episode_id")]

    def max_source_revision(self) -> int:
        r = self.row("SELECT COALESCE(MAX(source_revision), 0) FROM signal_episodes")
        return int(r[0]) if r else 0

    def delivery(self, delivery_id: str) -> SignalAck | None:
        r = self.row("SELECT ack_json FROM signal_deliveries WHERE delivery_id=?", (delivery_id,))
        return SignalAck.model_validate_json(r[0]) if r else None

    def record_delivery(self, c: sqlite3.Connection, ack: SignalAck) -> None:
        c.execute("INSERT INTO signal_deliveries (delivery_id, received_at, ack_json) VALUES (?, ?, ?)",
                  (ack.delivery_id, self.clock(), ack.model_dump_json()))

    # ---- incidents, memberships, links

    # incidents row (what the gateway reads) + workspace + memberships + outbox, all or nothing
    def open_incident(self, c: sqlite3.Connection, incident: dict[str, Any], memberships: list[Membership],
                      cause_key: str | None = None) -> None:
        p = self.policy
        c.execute("INSERT INTO incidents (id, opened_at, onset_at, culprit, victims_json, state, severity_at_open) "
                  "VALUES (?, ?, ?, NULL, '[]', 'open', ?)",
                  (incident["id"], incident["opened_at"], incident["onset_at"], incident["severity"]))
        c.execute("INSERT INTO orchestration_workspaces (incident_id, phase, cause_key, created_at, requests_limit, "
                  "tool_calls_limit, specialists_limit) VALUES (?, 'queued', ?, ?, ?, ?, ?)",
                  (incident["id"], cause_key, self.clock(), p.max_model_requests, p.max_tool_calls,
                   p.max_specialists_per_incident))
        for m in memberships:
            self.add_membership(c, m)

    def add_membership(self, c: sqlite3.Connection, m: Membership) -> None:
        c.execute("INSERT INTO incident_memberships (incident_id, episode_id, service, reason, evidence_json, "
                  "added_revision) VALUES (?, ?, ?, ?, ?, ?)",
                  (m.incident_id, m.episode_id, m.service, m.reason, json.dumps(m.evidence_ids), m.added_revision))

    def memberships(self, incident_id: str, open_only: bool = False) -> list[Membership]:
        sql = "SELECT * FROM incident_memberships WHERE incident_id=?" + (" AND closed=0" if open_only else "")
        return [Membership(incident_id=r["incident_id"], episode_id=r["episode_id"], service=r["service"],
                           reason=r["reason"], evidence_ids=json.loads(r["evidence_json"]),
                           added_revision=r["added_revision"]) for r in self.rows(sql + " ORDER BY service",
                                                                                    (incident_id,))]

    # open episode -> owning incident (one owner per open episode, enforced by a unique index)
    def owner_of(self, episode_id: str) -> str | None:
        r = self.row("SELECT incident_id FROM incident_memberships WHERE episode_id=? AND closed=0", (episode_id,))
        return r[0] if r else None

    # an episode that already belonged to a closed incident never opens another one
    def was_owned(self, episode_id: str) -> bool:
        return self.row("SELECT 1 FROM incident_memberships WHERE episode_id=? LIMIT 1", (episode_id,)) is not None

    def close_memberships(self, c: sqlite3.Connection, incident_id: str) -> list[str]:
        ids = [r[0] for r in c.execute("SELECT episode_id FROM incident_memberships WHERE incident_id=? AND closed=0",
                                       (incident_id,))]
        c.execute("UPDATE incident_memberships SET closed=1 WHERE incident_id=?", (incident_id,))
        if ids:  # still sick after close: no new incident until a healthy reading ends the episode
            c.execute(f"UPDATE signal_episodes SET suppressed=1 WHERE episode_id IN ({','.join('?' * len(ids))}) "
                      "AND recovered_at IS NULL", ids)
        return ids

    def link(self, c: sqlite3.Connection, link: IncidentLink) -> None:
        c.execute("INSERT INTO incident_links (incident_a, incident_b, relation, reason, supporting_json, "
                  "contradicting_json, status, revision) VALUES (?,?,?,?,?,?,?,?) "
                  "ON CONFLICT(incident_a, incident_b, relation) DO UPDATE SET reason=excluded.reason, "
                  "supporting_json=excluded.supporting_json, contradicting_json=excluded.contradicting_json, "
                  "status=excluded.status, revision=incident_links.revision+1",
                  (link.incident_a, link.incident_b, link.relation, link.reason, json.dumps(link.supporting_ids),
                   json.dumps(link.contradicting_ids), link.status, link.revision))

    def links(self, incident_id: str) -> list[IncidentLink]:
        return [IncidentLink(incident_a=r["incident_a"], incident_b=r["incident_b"], relation=r["relation"],
                             reason=r["reason"], supporting_ids=json.loads(r["supporting_json"]),
                             contradicting_ids=json.loads(r["contradicting_json"]), status=r["status"],
                             revision=r["revision"])
                for r in self.rows("SELECT * FROM incident_links WHERE incident_a=? OR incident_b=? "
                                   "ORDER BY incident_a, incident_b", (incident_id, incident_id))]

    # ---- workspace row

    def workspace(self, incident_id: str) -> sqlite3.Row | None:
        return self.row("SELECT * FROM orchestration_workspaces WHERE incident_id=?", (incident_id,))

    def unfinished(self) -> list[str]:
        return [r[0] for r in self.rows("SELECT incident_id FROM orchestration_workspaces WHERE phase != 'terminal' "
                                        "ORDER BY created_at")]

    # compare-and-swap on revision; False when someone else moved it first
    def cas(self, c: sqlite3.Connection, incident_id: str, expected_revision: int, **changes: Any) -> bool:
        bad = set(changes) - CAS_COLUMNS
        if bad:
            raise ValueError(f"not a workspace column: {sorted(bad)}")
        sets = "".join(f"{k}=?, " for k in changes)
        cur = c.execute(f"UPDATE orchestration_workspaces SET {sets}revision=revision+1 "
                        "WHERE incident_id=? AND revision=?", (*changes.values(), incident_id, expected_revision))
        return cur.rowcount == 1

    def update(self, incident_id: str, expected_revision: int, **changes: Any) -> bool:
        with self.tx() as c:
            return self.cas(c, incident_id, expected_revision, **changes)

    # scope: membership changed what the investigation assumed; plan: accepted findings changed the plan
    def bump(self, c: sqlite3.Connection, incident_id: str, which: str) -> int:
        column = {"scope": "scope_revision", "plan": "plan_revision"}[which]
        c.execute(f"UPDATE orchestration_workspaces SET {column}={column}+1, revision=revision+1 "
                  "WHERE incident_id=?", (incident_id,))
        return int(c.execute(f"SELECT {column} FROM orchestration_workspaces WHERE incident_id=?",
                             (incident_id,)).fetchone()[0])

    # ---- evidence

    # immutable: same id + same content is a no-op, same id + other content is a bug
    def put_snapshot(self, snapshot_id: str, query_key: str, source: str, fetched_at: float, valid_until: float,
                     payload: Any, source_observed_at: float | None = None) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        digest = fingerprint(payload)
        with self.tx() as c:
            old = c.execute("SELECT payload_hash FROM evidence_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
            if old:
                if old[0] != digest:
                    raise Conflict(f"evidence {snapshot_id} already holds other content")
                return
            c.execute("INSERT INTO evidence_snapshots (snapshot_id, query_key, source, source_observed_at, fetched_at, "
                      "valid_until, payload_json, payload_hash) VALUES (?,?,?,?,?,?,?,?)",
                      (snapshot_id, query_key, source, source_observed_at, fetched_at, valid_until, body, digest))

    def snapshot_payload(self, snapshot_id: str) -> Any:
        r = self.row("SELECT payload_json FROM evidence_snapshots WHERE snapshot_id=?", (snapshot_id,))
        return json.loads(r[0]) if r else None

    # what a run was actually shown; only these ids are citable by that run
    def deliver(self, run_id: str, incident_id: str, items: list[tuple[str, str | None]]) -> None:
        if not items:
            return
        now = self.clock()
        with self.tx() as c:
            c.executemany("INSERT OR IGNORE INTO task_evidence (run_id, incident_id, evidence_id, snapshot_id, "
                          "delivered_at) VALUES (?, ?, ?, ?, ?)",
                          [(run_id, incident_id, eid, sid, now) for eid, sid in items])

    def delivered(self, run_id: str) -> set[str]:
        return {r[0] for r in self.rows("SELECT evidence_id FROM task_evidence WHERE run_id=?", (run_id,))}

    # ---- tasks (fenced: every attempt gets a higher lease token)

    def create_task(self, c: sqlite3.Connection, task_id: str, incident_id: str, question_id: str, type_: str,
                    fp: str, scope_revision: int, plan_revision: int, task_input: dict, allowed_tools: list[str],
                    deadline_at: float, requests: int, tool_calls: int) -> None:
        now = self.clock()
        c.execute("INSERT INTO investigation_tasks (task_id, incident_id, question_id, type, fingerprint, "
                  "scope_revision, plan_revision, input_json, allowed_tools_json, state, deadline_at, "
                  "requests_allocated, tool_calls_allocated, created_at, updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?,'pending',?,?,?,?,?)",
                  (task_id, incident_id, question_id, type_, fp, scope_revision, plan_revision,
                   json.dumps(task_input, sort_keys=True), json.dumps(allowed_tools), deadline_at, requests,
                   tool_calls, now, now))

    def task(self, task_id: str) -> sqlite3.Row | None:
        return self.row("SELECT * FROM investigation_tasks WHERE task_id=?", (task_id,))

    def claim_task(self, task_id: str, worker: str, expected_attempt: int) -> int | None:
        now = self.clock()
        with self.tx() as c:
            r = c.execute("SELECT state, attempt, deadline_at FROM investigation_tasks WHERE task_id=?",
                          (task_id,)).fetchone()
            if r is None or r["state"] != "pending" or r["attempt"] != expected_attempt or now >= r["deadline_at"]:
                return None
            token = expected_attempt + 1
            c.execute("UPDATE investigation_tasks SET state='running', attempt=?, lease_token=?, owner=?, "
                      "lease_expires_at=?, updated_at=? WHERE task_id=?",
                      (token, token, worker, now + self.policy.task_lease_seconds, now, task_id))
            return token

    def heartbeat(self, task_id: str, token: int) -> bool:
        now = self.clock()
        with self.tx() as c:
            cur = c.execute("UPDATE investigation_tasks SET lease_expires_at=?, updated_at=? WHERE task_id=? "
                            "AND lease_token=? AND state='running'",
                            (now + self.policy.task_lease_seconds, now, task_id, token))
            return cur.rowcount == 1

    # "stale" when the lease moved on (expired, cancelled, newer attempt): a late result never lands
    def complete_task(self, task_id: str, token: int, state: str, finding: FindingResult | None = None,
                      error: str | None = None) -> str:
        if state not in ("succeeded", "failed", "timed_out"):
            raise ValueError(f"not a completion state: {state}")
        now = self.clock()
        with self.tx() as c:
            r = c.execute("SELECT * FROM investigation_tasks WHERE task_id=?", (task_id,)).fetchone()
            if r is None or r["state"] != "running" or r["lease_token"] != token:
                return "stale"
            finding_id = None
            if finding is not None:
                finding_id = f"{task_id}:f{token}"
                c.execute("INSERT INTO investigation_findings (finding_id, task_id, incident_id, question_id, "
                          "fingerprint, body_json, created_at) VALUES (?,?,?,?,?,?,?)",
                          (finding_id, task_id, r["incident_id"], r["question_id"], r["fingerprint"],
                           finding.model_dump_json(), now))
            c.execute("UPDATE investigation_tasks SET state=?, finding_id=?, error=?, updated_at=? WHERE task_id=?",
                      (state, finding_id, error, now, task_id))
            return "accepted"

    def expire_leases(self) -> list[str]:
        now = self.clock()
        with self.tx() as c:
            ids = [r[0] for r in c.execute("SELECT task_id FROM investigation_tasks WHERE state='running' "
                                           "AND lease_expires_at < ?", (now,))]
            c.executemany("UPDATE investigation_tasks SET state='lease_expired', updated_at=? WHERE task_id=?",
                          [(now, t) for t in ids])
            return ids

    def cancel_tasks(self, c: sqlite3.Connection, incident_id: str, reason: str) -> list[str]:
        ids = [r[0] for r in c.execute("SELECT task_id FROM investigation_tasks WHERE incident_id=? AND state IN "
                                       "('pending', 'running', 'lease_expired')", (incident_id,))]
        c.executemany("UPDATE investigation_tasks SET state='cancelled', error=?, updated_at=? WHERE task_id=?",
                      [(reason, self.clock(), t) for t in ids])
        return ids

    def finding_for(self, fp: str) -> FindingResult | None:
        r = self.row("SELECT body_json FROM investigation_findings WHERE fingerprint=? ORDER BY created_at DESC "
                     "LIMIT 1", (fp,))
        return FindingResult.model_validate_json(r[0]) if r else None

    # ---- model calls (durable reservations; counted even when the call failed)

    def reserve_call(self, call_id: str, incident_id: str, run_id: str, role: str, task_id: str | None = None,
                     reserved_tokens: int = 0, task_limit: int | None = None) -> str | None:
        now = self.clock()
        limit = self.policy.max_model_requests
        with self.tx() as c:
            used = c.execute(f"SELECT COUNT(*) FROM model_calls WHERE incident_id=? AND state IN "
                             f"({','.join('?' * len(CALL_COUNTED))})", (incident_id, *CALL_COUNTED)).fetchone()[0]
            if used >= limit:
                return "request_budget"
            if role == "specialist":
                # the commander's last calls are kept for its own synthesis
                if used >= limit - self.policy.reserved_commander_requests:
                    return "request_budget"
                if task_limit is not None and c.execute(
                        "SELECT COUNT(*) FROM model_calls WHERE task_id=?", (task_id,)).fetchone()[0] >= task_limit:
                    return "request_budget"
            if self.policy.max_total_tokens is not None:
                spent = self.spent(c, incident_id)
                if spent + reserved_tokens > self.policy.max_total_tokens:
                    return "token_budget"
            c.execute("INSERT INTO model_calls (call_id, incident_id, task_id, run_id, role, state, reserved_at, "
                      "reserved_tokens) VALUES (?, ?, ?, ?, ?, 'reserved', ?, ?)",
                      (call_id, incident_id, task_id, run_id, role, now, reserved_tokens))
            return None

    # tokens charged so far: a finished call costs what it used; an open, failed or lost one keeps its
    # whole reservation, since the provider may have billed it
    def spent(self, c: sqlite3.Connection, incident_id: str) -> int:
        return int(c.execute("SELECT COALESCE(SUM(CASE WHEN state='ok' THEN COALESCE(input_tokens, 0) + "
                             "COALESCE(output_tokens, 0) ELSE reserved_tokens END), 0) FROM model_calls "
                             "WHERE incident_id=?", (incident_id,)).fetchone()[0])

    # exactly once per call: only a reserved row can settle
    def settle_call(self, call_id: str, state: str, input_tokens: int | None = None, output_tokens: int | None = None,
                    error: str | None = None) -> bool:
        if state not in ("ok", "error", "unknown"):
            raise ValueError(f"not a settled call state: {state}")
        with self.tx() as c:
            cur = c.execute("UPDATE model_calls SET state=?, finished_at=?, input_tokens=?, output_tokens=?, error=? "
                            "WHERE call_id=? AND state='reserved'",
                            (state, self.clock(), input_tokens, output_tokens, error, call_id))
            return cur.rowcount == 1

    # a reservation still open at startup: the provider may have charged, so keep it counted
    def orphan_calls_unknown(self) -> int:
        with self.tx() as c:
            return c.execute("UPDATE model_calls SET state='unknown', finished_at=?, error='process restarted' "
                             "WHERE state='reserved'", (self.clock(),)).rowcount

    # ---- outbox

    def enqueue(self, c: sqlite3.Connection, event_id: str, destination: str, event_type: str,
                incident_id: str | None, body: dict, revision: int | None = None) -> None:
        now = self.clock()
        c.execute("INSERT INTO event_outbox (event_id, destination, event_type, incident_id, body_json, "
                  "incident_revision, created_at, next_attempt_at) VALUES (?,?,?,?,?,?,?,?)",
                  (event_id, destination, event_type, incident_id, json.dumps(body, default=str), revision, now, now))

    def due(self, destination: str, limit: int = 50) -> list[sqlite3.Row]:
        return self.rows("SELECT * FROM event_outbox WHERE destination=? AND delivered_at IS NULL AND next_attempt_at "
                         "<= ? ORDER BY created_at, rowid LIMIT ?", (destination, self.clock(), limit))

    def pending_count(self, destination: str) -> int:
        r = self.row("SELECT COUNT(*) FROM event_outbox WHERE destination=? AND delivered_at IS NULL", (destination,))
        return int(r[0]) if r else 0

    # error set = the receiver refused it for good; kept for the record, no longer blocks the queue
    def mark_delivered(self, event_id: str, error: str | None = None) -> None:
        with self.tx() as c:
            c.execute("UPDATE event_outbox SET delivered_at=?, last_error=? WHERE event_id=?",
                      (self.clock(), error, event_id))

    def mark_failed(self, event_id: str, error: str, max_backoff_s: float = 30) -> None:
        with self.tx() as c:
            r = c.execute("SELECT attempts FROM event_outbox WHERE event_id=?", (event_id,)).fetchone()
            attempts = (r[0] if r else 0) + 1
            c.execute("UPDATE event_outbox SET attempts=?, last_error=?, next_attempt_at=? WHERE event_id=?",
                      (attempts, error[:200], self.clock() + min(max_backoff_s, 2 ** (attempts - 1)), event_id))

    # ---- coordinator lease: one scheduler per database

    def acquire_coordinator(self, owner: str, ttl_s: float, name: str = "brain") -> int | None:
        now = self.clock()
        with self.tx() as c:
            r = c.execute("SELECT owner, epoch, expires_at FROM coordinator_leases WHERE name=?", (name,)).fetchone()
            if r and r["owner"] != owner and r["expires_at"] > now:
                return None
            epoch = (r["epoch"] if r else 0) + 1
            c.execute("INSERT INTO coordinator_leases (name, owner, epoch, expires_at) VALUES (?,?,?,?) "
                      "ON CONFLICT(name) DO UPDATE SET owner=excluded.owner, epoch=excluded.epoch, "
                      "expires_at=excluded.expires_at", (name, owner, epoch, now + ttl_s))
            return epoch

    def renew_coordinator(self, owner: str, epoch: int, ttl_s: float, name: str = "brain") -> bool:
        with self.tx() as c:
            cur = c.execute("UPDATE coordinator_leases SET expires_at=? WHERE name=? AND owner=? AND epoch=?",
                            (self.clock() + ttl_s, name, owner, epoch))
            return cur.rowcount == 1

    # ---- experience (migration v3): what a fix actually did, by code, never the model's prose

    # one row per receipt; a contradicting outcome for the same fix on the same service retires older rows
    def record_experience(self, incident_id: str) -> str | None:
        good = ("success", "right_by_accident")
        with self.tx() as c:
            r = c.execute("SELECT r.id, r.tool, r.target, r.outcome, r.diff_json, r.ts, i.pattern FROM receipts r "
                          "JOIN incidents i ON i.id = r.incident_id WHERE r.incident_id=? ORDER BY r.id DESC LIMIT 1",
                          (incident_id,)).fetchone()
            if r is None or r["outcome"] in (None, "pending", "watchdog_failed"):
                return None
            experience_id = f"exp-{incident_id}-{r['id']}"
            if c.execute("SELECT 1 FROM experience_records WHERE experience_id=?", (experience_id,)).fetchone():
                return experience_id
            paths = sorted(json.loads(r["diff_json"] or "{}"))
            c.execute("UPDATE experience_records SET status='superseded' WHERE tool=? AND service=? AND "
                      "pattern IS ? AND status='active' AND (outcome IN ('success', 'right_by_accident')) != ?",
                      (r["tool"], r["target"], r["pattern"], r["outcome"] in good))
            c.execute("INSERT INTO experience_records (experience_id, source_incident_id, receipt_id, pattern, tool, "
                      "service, applicability_json, outcome, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (experience_id, incident_id, r["id"], r["pattern"], r["tool"], r["target"],
                       json.dumps({"service": r["target"], "diff_paths": paths}), r["outcome"], self.clock()))
            return experience_id

    # ---- delegation decisions and the read projection

    def record_delegation(self, c: sqlite3.Connection, incident_id: str, d: DelegationRecord) -> None:
        c.execute("INSERT INTO delegation_decisions (incident_id, status, reason, question_id, explanation, ts) "
                  "VALUES (?,?,?,?,?,?)", (incident_id, d.status, d.reason, d.question_id, d.explanation, d.ts))

    def budget(self, incident_id: str) -> BudgetUse | None:
        w = self.workspace(incident_id)
        if w is None:
            return None
        r = self.row("SELECT COUNT(*), COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0), "
                     "COALESCE(SUM(state='unknown'), 0) FROM model_calls WHERE incident_id=?", (incident_id,))
        assert r is not None
        return BudgetUse(requests_used=r[0], requests_limit=w["requests_limit"], tool_calls_used=w["tool_calls_used"],
                         tool_calls_limit=w["tool_calls_limit"], input_tokens=r[1], output_tokens=r[2],
                         unknown_calls=r[3], specialists_started=w["specialists_started"],
                         specialists_limit=w["specialists_limit"])

    def snapshot(self, incident_id: str, tasks_limit: int = 20) -> WorkspaceSnapshot | None:
        w = self.workspace(incident_id)
        budget = self.budget(incident_id)
        if w is None or budget is None:
            return None
        tasks = [TaskSummary(task_id=r["task_id"], question_id=r["question_id"], type=r["type"], state=r["state"],
                             attempt=r["attempt"], scope=json.loads(r["input_json"]).get("scope", []),
                             deadline_at=r["deadline_at"])
                 for r in self.rows("SELECT * FROM investigation_tasks WHERE incident_id=? ORDER BY created_at "
                                    "LIMIT ?", (incident_id, tasks_limit))]
        findings = []
        for r in self.rows("SELECT * FROM investigation_findings WHERE incident_id=? ORDER BY created_at LIMIT ?",
                           (incident_id, tasks_limit)):
            f = FindingResult.model_validate_json(r["body_json"])
            findings.append(FindingSummary(finding_id=r["finding_id"], task_id=r["task_id"], question_id=f.question_id,
                                           verdict=f.verdict, summary=f.summary, evidence_ids=f.evidence_ids))
        delegation = [DelegationRecord(status=r["status"], reason=r["reason"], question_id=r["question_id"],
                                       explanation=r["explanation"], ts=r["ts"])
                      for r in self.rows("SELECT * FROM delegation_decisions WHERE incident_id=? ORDER BY id",
                                         (incident_id,))]
        return WorkspaceSnapshot(incident_id=incident_id, revision=w["revision"], phase=w["phase"],
                                 scope_revision=w["scope_revision"], plan_revision=w["plan_revision"],
                                 created_at=w["created_at"], deadline_at=w["deadline_at"],
                                 memberships=self.memberships(incident_id), links=self.links(incident_id),
                                 tasks=tasks, findings=findings, delegation=delegation, budget=budget,
                                 intents=self.intents(incident_id, tasks_limit), last_error=w["last_error"])

    # gateway-owned rows (migration v2); none before that migration
    def intents(self, incident_id: str, limit: int = 20) -> list[IntentSummary]:
        try:
            rows = self.rows("SELECT * FROM action_intents WHERE incident_id=? ORDER BY created_at LIMIT ?",
                             (incident_id, limit))
        except sqlite3.OperationalError:
            return []
        out = []
        for r in rows:
            action = json.loads(r["action_json"])
            out.append(IntentSummary(intent_id=r["intent_id"], status="queued" if r["status"] == "new" else r["status"],
                                     plan_revision=r["plan_revision"], tool=action["tool"], target=action["target"],
                                     approval_id=r["approval_id"], receipt_id=r["receipt_id"]))
        return out

    # one line per incident for lists: phase and how many specialist tasks ran
    def summary(self, incident_id: str) -> dict[str, Any] | None:
        w = self.workspace(incident_id)
        if w is None:
            return None
        r = self.row("SELECT COUNT(*) FROM investigation_tasks WHERE incident_id=?", (incident_id,))
        return {"phase": w["phase"], "task_count": int(r[0]) if r else 0}


def _episode(r: sqlite3.Row) -> SignalEpisode:
    return SignalEpisode(episode_id=r["episode_id"], cluster=r["cluster"], namespace=r["namespace"],
                         service=r["service"], symptom=r["symptom"], first_breach_at=r["first_breach_at"],
                         sustained_at=r["sustained_at"], last_observed_at=r["last_observed_at"],
                         recovered_at=r["recovered_at"], source_revision=r["source_revision"],
                         evidence_ids=json.loads(r["evidence_json"]))
