# verifier decisions (IMPLEMENTATION.md §6.4.9). Pure: the gateway loop feeds it /health/now every 5 s.


# per-service share of the detector's severity formula
def service_score(s: dict) -> int:
    return 3 * s["breaching"] + 2 * s["bad_pods"] + s["unhealthy"]


class Verification:
    def __init__(self, t0: float, health_at_action: dict, culprit: str, victims: list[str],
                 prediction: dict | None, window_s: float, early_abort: bool, stable_s: float = 15,
                 grace_s: float = 0, prediction_delay_s: float = 0, scope: set[str] | None = None):
        self.t0 = t0
        # orchestration: severity counted over this action's own services only, frozen at execute time, so
        # another incident's outage cannot abort a fix that works. None = whole fleet (legacy)
        self.scope = scope
        self.sev_before = self.severity(health_at_action)
        # only services the observer measures; a trace-only victim (frontend-proxy) would block recovery forever
        self.watched = [s for s in [culprit, *victims] if s == culprit or s in health_at_action["services"]]
        self.prediction = prediction
        self.window_s = window_s
        self.early_abort = early_abort
        self.stable_s = stable_s
        self.grace_s = grace_s
        # known propagation delay the model can't see (flagd reloads a ConfigMap ~60 s after the patch): live,
        # a flag revert predicted "within 60 s" recovered at ~110 s and lost its trust credit
        self.prediction_delay_s = prediction_delay_s
        self.healthy_since: float | None = None
        # None = nothing to check (no prediction); a fix without one can only be "right by accident"
        self.prediction_held: bool | None = False if prediction else None
        self.recovered = False
        # the last reading was stale (observer serving old numbers, prometheus_ok false): it proved nothing
        self.blind = False
        self.last_health = health_at_action
        self.collateral: dict[str, float] = {}
        self.last_ts = t0
        self.healthy_at_start = {s for s, v in health_at_action["services"].items()
                                 if not v["unhealthy"] and s not in self.watched}

    def severity(self, health: dict) -> float:
        if self.scope is None:
            return health["severity"]
        return sum(service_score({"breaching": v.get("breaching", False), "bad_pods": v.get("bad_pods", 0),
                                  "unhealthy": v.get("unhealthy", False)})
                   for s, v in health["services"].items() if s in self.scope)

    # one tick -> None (keep going) | "early_abort" | "handed_off" | "recovered" | "window_end"
    def step(self, now: float, health: dict, non_agent_change: bool) -> str | None:
        services = health["services"]
        self.last_health = health
        for s in self.healthy_at_start:
            if services.get(s, {}).get("unhealthy"):
                self.collateral[s] = self.collateral.get(s, 0) + (now - self.last_ts)
        self.last_ts = now

        # stale numbers are no evidence: they cannot prove the prediction, a recovery, or harm
        self.blind = health.get("prometheus_ok") is False
        p = self.prediction
        if p and not self.blind and now - self.t0 <= p["within_s"] + self.prediction_delay_s:
            value = services.get(p["target"], {}).get(p["metric"])
            if value is not None and value < p["below"]:
                self.prediction_held = True

        if non_agent_change:
            return "handed_off"
        # victims lag the culprit, so severity can rise just after a right fix: no early abort in the grace
        if (self.early_abort and not self.blind and now - self.t0 >= self.grace_s
                and self.severity(health) > self.sev_before):
            return "early_abort"
        healthy = not self.blind and all(services.get(s, {}).get("unhealthy") is False for s in self.watched)
        self.recovered = healthy
        if healthy:
            self.healthy_since = now if self.healthy_since is None else self.healthy_since
            if (p is None or self.prediction_held) and now - self.healthy_since >= self.stable_s:
                return "recovered"
        else:
            self.healthy_since = None
        if now - self.t0 >= self.window_s:
            return "window_end"
        return None

    # success | right_by_accident (resolved, no trust credit) | undo
    def outcome(self, harm_clean: bool) -> str:
        if not self.recovered or not harm_clean:
            return "undo"
        return "success" if self.prediction_held else "right_by_accident"


# ledger effect: success +1, undone/early abort -1, right by accident and hands-off leave it alone
def ledger_effect(outcome: str) -> bool | None:
    return {"success": True, "undo": False, "early_abort": False}.get(outcome)


# harm check 1+2: only the declared object changed (others -> hands-off), no service outside blast got worse
def harm_check(hashes_before: dict, hashes_after: dict, declared: str, non_agent_objects: set[str],
               health_before: dict, health_after: dict, blast: set[str], tolerance: int = 0,
               excused: frozenset[str] = frozenset()) -> dict:
    changed = {k for k in hashes_before.keys() | hashes_after.keys() if hashes_before.get(k) != hashes_after.get(k)}
    unexpected = sorted(changed - {declared} - non_agent_objects)
    all_worse = sorted(s for s, v in health_after["services"].items()
                       if s not in blast and s in health_before["services"]
                       and service_score(v) > service_score(health_before["services"][s]) + tolerance)
    # excused: services of another incident that broke on its own before this action (orchestration only)
    worse = [s for s in all_worse if s not in excused]
    out = {"clean": not unexpected and declared in changed and not worse,
           "declared_changed": declared in changed, "unexpected_changes": unexpected, "worse_services": worse}
    if excused:
        out["unrelated_worse"] = [s for s in all_worse if s in excused]
    return out
