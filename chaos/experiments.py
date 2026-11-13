# lab experiments: preflight, durable lifecycle, compare-before-restore cleanup (review §7.5 to §7.7).
# scheduled -> applying -> active -> verifying -> finished; rejected | cleanup_required | needs_operator.
# The record lives in data/chaos.db, never in data/oncall.db: the brain has no path to it.
import json
import random
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from chaos import ground_truth, registry
from chaos.faults import Kubectl, KubectlError, read_field, write_field
from chaos.registry import Refused
from schemas import config

OPEN = ("scheduled", "applying", "active", "cleanup_required", "verifying")
DONE = ("finished", "needs_operator", "rejected")
MAX_CLEANUP_TRIES = 5

Health = Callable[[], dict[str, Any] | None]


Origin = Literal["judge", "akira-mcp"]


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str = Field(min_length=1, max_length=63)
    capability: str = Field(min_length=1, max_length=80)
    choice: str = Field(min_length=1, max_length=40)
    delay_s: int = Field(default=0, ge=0)
    duration_s: int | None = Field(default=None, gt=0)
    decoy: bool = False
    blind: bool = False
    skip_baseline: bool = False
    # who asked: a judge (CLI, UI) or Claude through the Akira MCP; bench can tell the runs apart
    origin: Origin = "judge"


# where a field lives, in words a judge can check with kubectl
def place(kind: str, name: str, key: str | None) -> str:
    if kind == "flag":
        return f"configmap/flagd-config flags[{name}].defaultVariant"
    return f"deployment/{name} " + {"image": "image", "replicas": "replicas"}.get(kind, f"env {key}")


class Engine:
    def __init__(self, data_dir: Path, run: Kubectl, health: Health | None = None,
                 lock: Any = None, policy: dict[str, Any] | None = None,
                 clock: Callable[[], float] = time.time):
        self.db_path, self.truth_path = data_dir / "chaos.db", data_dir / "ground_truth.jsonl"
        self.run, self.health, self.clock = run, health, clock
        self.lock = lock or threading.RLock()
        self.policy = policy
        self.conn: sqlite3.Connection | None = None

    # ---- storage ---------------------------------------------------------------------------
    def open(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, idem_key TEXT UNIQUE, "
                          "status TEXT NOT NULL, created_at REAL NOT NULL, data TEXT NOT NULL)")
        self.conn.commit()

    def _db(self) -> sqlite3.Connection:
        if self.conn is None:
            self.open()
        assert self.conn is not None
        return self.conn

    def _save(self, exp: dict[str, Any], idem_key: str | None = None) -> None:
        db = self._db()
        db.execute("INSERT INTO experiments (id, idem_key, status, created_at, data) VALUES (?, ?, ?, ?, ?) "
                   "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                   (exp["id"], idem_key, exp["status"], exp["created_at"], json.dumps(exp)))
        db.commit()

    def _load(self, where: str, *args: Any) -> list[dict[str, Any]]:
        rows = self._db().execute(f"SELECT data FROM experiments WHERE {where}", args).fetchall()
        return [json.loads(r[0]) for r in rows]

    def _limits(self) -> dict[str, Any]:
        return (self.policy or config.load("chaos"))["limits"]

    # ---- views -----------------------------------------------------------------------------
    # a blind run shows timings and status only, until it ends or the judge reveals it
    def view(self, exp: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in exp.items() if k != "truth_entry"}
        if exp["spec"]["blind"] and not exp["revealed"] and exp["status"] not in DONE:
            out.update(spec=None, mutations=None, family=None, target=None, hidden=True)
        else:
            out.update(target=exp["spec"]["target"], hidden=False)
        return out

    def get(self, exp_id: str) -> dict[str, Any] | None:
        with self.lock:
            found = self._load("id = ?", exp_id)
            return self.view(found[0]) if found else None

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.lock:
            return [self.view(e) for e in self._load("1 ORDER BY created_at DESC LIMIT ?", limit)]

    def open_runs(self) -> list[dict[str, Any]]:
        marks = ",".join("?" * len(OPEN))
        return self._load(f"status IN ({marks}) ORDER BY created_at", *OPEN)

    # ---- preflight -------------------------------------------------------------------------
    # fresh monitoring that says the shop is healthy; None when no observer is configured
    def baseline(self) -> dict[str, Any]:
        if self.health is None:
            return {"ok": None, "reason": "observer not configured; baseline unknown"}
        h = self.health()
        if h is None:
            return {"ok": False, "reason": "observer unreachable; baseline unknown"}
        if h.get("prometheus_ok") is not True:
            return {"ok": False, "reason": "monitoring unavailable; baseline unknown"}
        age = self.clock() - float(h.get("last_ok_ts") or h["ts"])
        out = {"severity": h["severity"], "age_s": round(age, 1)}
        if age > self._limits()["baseline_max_age_s"]:
            return {**out, "ok": False, "reason": f"last good reading is {age:.0f} s old; baseline unknown"}
        if h["severity"] != 0:
            return {**out, "ok": False, "reason": f"shop is not healthy (severity {h['severity']})"}
        return {**out, "ok": True, "reason": None}

    # every check, no mutation: what would change, and each reason it may not start
    def preview(self, spec: Spec, legacy: bool = False) -> dict[str, Any]:
        with self.lock:
            reg = registry.build(self.run, self.policy)
            limits, decoy = reg["limits"], reg["decoy"]
            problems: list[str] = []
            changes: list[dict[str, Any]] = []
            cap = None
            try:
                cap, value = registry.resolve(reg, spec.target, spec.capability, spec.choice)
            except Refused as e:
                # a legacy re-inject of the same fault stays the no-op it always was
                again = legacy and next((c for c in reg["targets"].get(spec.target, {}).get("capabilities", [])
                                         if c["id"] == spec.capability and spec.choice in c["values"]), None)
                if again:
                    cap, value = again, again["values"][spec.choice]
                else:
                    problems.append(str(e))
            if spec.delay_s > limits["max_delay_s"]:
                problems.append(f"delay {spec.delay_s} s is over the {limits['max_delay_s']} s limit")
            if spec.duration_s is not None and not limits["min_duration_s"] <= spec.duration_s <= limits["max_duration_s"]:
                problems.append(f"duration must be {limits['min_duration_s']} to {limits['max_duration_s']} s")
            if cap:
                f = cap["field"]
                changes.append({"role": "fault", **f, "place": place(**f), "before": cap["current"], "after": value,
                                "after_s": 0})
                if spec.decoy and not cap["decoy"]:
                    problems.append("a decoy change is not offered with this fault")
                elif spec.decoy:
                    d = {"kind": "env", "name": spec.target, "key": decoy["env"]}
                    changes.append({"role": "decoy", **d, "place": place(**d),
                                    "before": read_field(run=self.run, **d), "after": decoy["value"],
                                    "after_s": decoy["gap_s"]})
            if not legacy:
                busy = [e for e in self.open_runs() if not e["legacy"]]
                if len(busy) >= limits["max_active"]:
                    problems.append(f"experiment {busy[0]['id']} is still {busy[0]['status']}")
            base = self.baseline()
            if not legacy and not spec.skip_baseline and base["ok"] is not True:
                problems.append(base["reason"])
            if cap and not problems and not legacy:
                try:  # the API server's own answer, nothing stored
                    for c in changes:
                        write_field(c["kind"], c["name"], c["key"], c["after"], self.run, dry=True)
                except KubectlError as e:
                    problems.append(f"API server refused the change: {e}")
            target = reg["targets"].get(spec.target, {})
            return {"ok": not problems, "problems": problems, "changes": changes,
                    "family": cap["family"] if cap else None, "tested": bool(cap and cap["tested"]),
                    "journeys": target.get("journeys", []), "target_policy": target.get("policy"),
                    "semantics": "impulse", "ends_after_s": spec.duration_s or limits["max_lifetime_s"],
                    "baseline": base, "registry_version": reg["version"]}

    # ---- lifecycle -------------------------------------------------------------------------
    # truth: the ground-truth line of a legacy scenario ({"type", ["key"]}); lab runs record their family
    def start(self, spec: Spec, idem_key: str | None = None, truth: dict[str, Any] | None = None,
              seed: int | None = None) -> dict[str, Any]:
        with self.lock:
            if idem_key:  # a browser retry after a timeout must not inject twice
                seen = self._db().execute("SELECT data FROM experiments WHERE idem_key = ?", (idem_key,)).fetchone()
                if seen:
                    return json.loads(seen[0])
            legacy = truth is not None
            pre = self.preview(spec, legacy)
            now = self.clock()
            exp: dict[str, Any] = {
                "id": f"exp-{uuid.uuid4().hex[:10]}", "status": "scheduled", "spec": spec.model_dump(),
                "origin": spec.origin,
                "legacy": legacy, "truth": truth, "seed": seed, "family": pre["family"],
                "registry_version": pre["registry_version"], "baseline": pre["baseline"],
                "created_at": now, "start_at": now + spec.delay_s, "applied_at": None, "expires_at": None,
                "ended_at": None, "ended_by": None, "error": None, "revealed": False, "healthy": None,
                "calm_since": None, "cleanup_tries": 0, "truth_entry": None,
                "mutations": [{"role": c["role"], "kind": c["kind"], "name": c["name"], "key": c["key"],
                               "place": c["place"], "before": None, "injected": c["after"], "state": "planned",
                               "after_s": c["after_s"], "applied_at": None} for c in pre["changes"]]}
            if not pre["ok"]:
                exp.update(status="rejected", error="; ".join(pre["problems"]), ended_at=now)
                self._save(exp, idem_key)
                return exp
            self._save(exp, idem_key)
            if spec.delay_s == 0:
                self._apply(exp)
            return exp

    # a valid experiment picked by seed, for the blind challenge
    def draw(self, seed: int | None = None, blind: bool = True, decoy: bool = False,
             tested_only: bool = True, origin: Origin = "judge") -> dict[str, Any]:
        with self.lock:
            seed = seed if seed is not None else random.SystemRandom().randrange(2**31)
            reg = registry.build(self.run, self.policy)
            options = sorted((t, c["id"], choice) for t, entry in reg["targets"].items()
                             for c in entry["capabilities"] for choice in c["choices"]
                             if c["available"] and (c["tested"] or not tested_only) and (c["decoy"] or not decoy))
            if not options:
                raise Refused("nothing available to draw from")
            target, capability, choice = random.Random(seed).choice(options)
            return self.start(Spec(target=target, capability=capability, choice=choice, decoy=decoy, blind=blind,
                                   origin=origin), seed=seed)

    def _write(self, exp: dict[str, Any], m: dict[str, Any]) -> None:
        m["before"] = read_field(m["kind"], m["name"], m["key"], self.run)
        m["state"] = "writing"
        self._save(exp)  # intent and the old value are on disk before the cluster changes
        write_field(m["kind"], m["name"], m["key"], m["injected"], self.run)
        m.update(state="applied", applied_at=self.clock())
        self._save(exp)

    def _apply(self, exp: dict[str, Any]) -> None:
        exp["status"] = "applying"
        self._save(exp)
        spec, truth = exp["spec"], exp["truth"]
        faults = [m for m in exp["mutations"] if m["role"] == "fault"]
        try:
            for m in faults:
                self._write(exp, m)
        except KubectlError as e:
            # kubectl said no, so that write did not land; earlier ones did and must be cleaned up
            for m in faults:
                if m["state"] == "writing":
                    m["state"] = "planned"
            partial = any(m["state"] == "applied" for m in faults)
            exp.update(status="cleanup_required" if partial else "rejected", error=str(e), ended_at=self.clock(),
                       ended_by="error")
            self._save(exp)
            if exp["legacy"]:
                raise
            return
        now = self.clock()
        if truth:
            extra = {k: v for k, v in truth.items() if k != "type"}
            entry = ground_truth.record(self.truth_path, truth["type"], spec["target"], **extra,
                                        experiment_id=exp["id"])
        else:
            entry = ground_truth.record(self.truth_path, exp["family"], spec["target"], capability=spec["capability"],
                                        choice=spec["choice"], experiment_id=exp["id"],
                                        origin=spec.get("origin", "judge"))
        life = None if exp["legacy"] else (spec["duration_s"] or self._limits()["max_lifetime_s"])
        exp.update(status="active", applied_at=now, expires_at=None if life is None else now + life,
                   truth_entry=entry)
        self._save(exp)

    # restore only what still holds the injected value; someone else's change is never overwritten
    def _restore(self, exp: dict[str, Any], roles: tuple[str, ...]) -> list[str]:
        conflicts = []
        for m in exp["mutations"]:
            if m["role"] not in roles or m["state"] not in ("applied", "writing"):
                continue
            now = read_field(m["kind"], m["name"], m["key"], self.run)
            if now == m["injected"]:
                write_field(m["kind"], m["name"], m["key"], m["before"], self.run)
                m["state"] = "restored"
            elif now == m["before"]:
                m["state"] = "repaired"
            else:
                m["state"] = "conflict"
                conflicts.append(f"{m['place']} is now {now!r}, neither the old nor the injected value")
            self._save(exp)
        return conflicts

    def _cleanup(self, exp: dict[str, Any], by: str) -> None:
        exp.update(status="cleanup_required", ended_by=by, cleanup_tries=exp["cleanup_tries"] + 1)
        self._save(exp)
        conflicts = self._restore(exp, ("fault", "decoy"))
        if conflicts:
            exp.update(status="needs_operator", error="; ".join(conflicts), ended_at=self.clock())
        else:
            exp.update(status="verifying", ended_at=self.clock(), calm_since=None)
        self._save(exp)

    def _finish(self, exp: dict[str, Any], healthy: bool | None) -> None:
        conflicts = self._restore(exp, ("decoy",))  # the decoy stays up while the agent's fix is verified
        if conflicts:
            exp.update(status="needs_operator", error="; ".join(conflicts))
        else:
            exp.update(status="finished", healthy=healthy)
        self._save(exp)

    def _verify(self, exp: dict[str, Any], now: float) -> None:
        faults = [m for m in exp["mutations"] if m["role"] == "fault"]
        if exp["ended_by"] in ("repaired", "changed") and any(
                read_field(m["kind"], m["name"], m["key"], self.run) == m["injected"] for m in faults):
            # the fix was undone (the gateway's own undo): the fault is live again
            for m in faults:
                m["state"] = "applied"
            exp.update(status="active", ended_at=None, ended_by=None, calm_since=None)
            return self._save(exp)
        if self.health is None:
            return self._finish(exp, None)
        base = self.baseline()
        limits = self._limits()
        if base["ok"]:
            exp["calm_since"] = exp["calm_since"] or now
            if now - exp["calm_since"] >= limits["stable_s"]:
                return self._finish(exp, True)
        else:
            exp["calm_since"] = None
            if now - exp["ended_at"] > limits["verify_timeout_s"]:
                exp.update(status="needs_operator", healthy=False,
                           error=f"{limits['verify_timeout_s']} s after the fault ended: {base['reason']}")
        self._save(exp)

    def _step(self, exp: dict[str, Any], now: float) -> None:
        if exp["status"] == "scheduled":
            if exp["start_at"] <= now:
                self._apply(exp)
        elif exp["status"] == "applying":
            # start() holds the lock while it applies, so this run died mid-apply (crash, kubectl timeout):
            # a write may have landed, clean it up instead of trusting it
            exp.update(status="cleanup_required", ended_by="error", error="interrupted while applying")
            self._save(exp)
        elif exp["status"] == "active":
            for m in exp["mutations"]:
                if m["role"] == "decoy" and m["state"] == "planned" and now >= exp["applied_at"] + m["after_s"]:
                    self._write(exp, m)
                    ground_truth.record(self.truth_path, "decoy", exp["spec"]["target"], key=m["key"],
                                        experiment_id=exp["id"])
            if exp["expires_at"] is not None and now >= exp["expires_at"]:
                return self._cleanup(exp, "expiry")
            faults = [m for m in exp["mutations"] if m["role"] == "fault"]
            live = [read_field(m["kind"], m["name"], m["key"], self.run) for m in faults]
            if all(value != m["injected"] for m, value in zip(faults, live)):
                # someone reversed the cause: the fault is over and is never applied again
                for m, value in zip(faults, live):
                    m["state"] = "repaired" if value == m["before"] else "changed"
                clean = all(m["state"] == "repaired" for m in faults)
                exp.update(status="verifying", ended_at=now, ended_by="repaired" if clean else "changed",
                           calm_since=None)
                self._save(exp)
        elif exp["status"] == "cleanup_required":
            if exp["cleanup_tries"] >= MAX_CLEANUP_TRIES:
                exp.update(status="needs_operator", error=f"cleanup failed {MAX_CLEANUP_TRIES} times: {exp['error']}")
                return self._save(exp)
            self._cleanup(exp, exp["ended_by"] or "error")
        elif exp["status"] == "verifying":
            self._verify(exp, now)

    # the watchdog: runs with or without a browser, every few seconds
    def tick(self) -> None:
        with self.lock:
            for exp in self.open_runs():
                try:
                    self._step(exp, self.clock())
                except KubectlError as e:  # cluster unreachable: keep the state, try again next tick
                    exp["error"] = str(e)
                    self._save(exp)

    def stop(self, exp_id: str) -> dict[str, Any] | None:
        with self.lock:
            found = self._load("id = ?", exp_id)
            if not found:
                return None
            exp = found[0]
            if exp["status"] == "scheduled":
                exp.update(status="finished", ended_by="judge_stop", ended_at=self.clock())
                self._save(exp)
            elif exp["status"] == "active":
                try:
                    self._cleanup(exp, "judge_stop")
                except KubectlError as e:  # stays cleanup_required; the watchdog retries
                    exp["error"] = str(e)
                    self._save(exp)
            return self.view(exp)

    def reveal(self, exp_id: str) -> dict[str, Any] | None:
        with self.lock:
            found = self._load("id = ?", exp_id)
            if not found:
                return None
            found[0]["revealed"] = True
            self._save(found[0])
            return self.view(found[0])

    # POST /chaos/reset restored the snapshot itself: every open run ends here, credited to the reset
    def close_all(self, by: str = "reset") -> None:
        with self.lock:
            for exp in self.open_runs():
                exp.update(status="finished", ended_by=by, ended_at=self.clock())
                self._save(exp)
