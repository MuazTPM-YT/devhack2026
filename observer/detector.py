# breach -> sustain -> unhealthy -> incident (IMPLEMENTATION.md §6.2.2). Pure logic: readings in, health out.


class Detector:
    def __init__(self, err_threshold: float, latency_multiplier: float, sustain_s: float, group_within_s: float):
        self.err_threshold = err_threshold
        self.latency_multiplier = latency_multiplier
        self.sustain_s = sustain_s
        self.group_within_s = group_within_s
        self.first_breach: dict[str, float] = {}
        self.incident: dict | None = None

    # one poll: readings {svc: {err_ratio, p95_ms}}, baselines {svc: p95_ms}, bad_pods {svc: count} from kube watch
    def tick(self, now: float, readings: dict, baselines: dict, bad_pods: dict) -> tuple[dict, tuple | None]:
        services = {}
        for svc in sorted(set(readings) | set(bad_pods)):
            r = readings.get(svc, {})
            err, p95, base = r.get("err_ratio"), r.get("p95_ms"), baselines.get(svc)
            breaching = (err is not None and err > self.err_threshold) or (
                p95 is not None and base is not None and p95 > self.latency_multiplier * base)
            if breaching:
                self.first_breach.setdefault(svc, now)
            else:
                self.first_breach.pop(svc, None)
            first = self.first_breach.get(svc)
            pods = bad_pods.get(svc, 0)
            sustained = first is not None and now - first >= self.sustain_s
            services[svc] = {"err_ratio": err, "p95_ms": p95, "baseline_p95_ms": base, "breaching": breaching,
                             "first_breach_ts": first, "bad_pods": pods, "unhealthy": sustained or pods > 0}

        unhealthy = sorted(s for s, v in services.items() if v["unhealthy"])
        # ponytail: "open alerts" read as unhealthy services; swap in real alert count if one appears
        severity = (3 * sum(v["breaching"] for v in services.values())
                    + 2 * sum(v["bad_pods"] for v in services.values()) + len(unhealthy))
        health = {"ts": now, "severity": severity, "services": services}

        if unhealthy and self.incident is None:
            starts = [services[s]["first_breach_ts"] for s in unhealthy]
            self.incident = {"id": f"inc-{int(now * 1000)}", "opened_at": now,
                             "onset_at": min(now if t is None else t for t in starts), "unhealthy": unhealthy,
                             "culprit": None, "victims": [], "major": False, "severity": float(severity)}
            return health, ("incident_opened", dict(self.incident))
        if self.incident is not None:
            new = [s for s in unhealthy if s not in self.incident["unhealthy"]]
            if new and now - self.incident["opened_at"] <= self.group_within_s:
                self.incident["unhealthy"] = sorted(self.incident["unhealthy"] + new)
                return health, ("alerts_grouped", dict(self.incident))
        return health, None

    # brain/gateway closed it (resolved, escalated, handed off); next unhealthy service opens a new one
    def close_incident(self) -> None:
        self.incident = None
