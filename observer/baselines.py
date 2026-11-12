# healthy-load medians per service (IMPLEMENTATION.md §6.2.1); the detector's latency check needs them
import sqlite3
from statistics import median


# samples: list of readings {svc: {err_ratio, p95_ms}} -> {svc: (err_ratio, p95_ms)}, missing values skipped
def medians(samples: list[dict]) -> dict[str, tuple[float | None, float | None]]:
    out = {}
    for svc in {s for sample in samples for s in sample}:
        errs = [x[svc]["err_ratio"] for x in samples if x.get(svc, {}).get("err_ratio") is not None]
        p95s = [x[svc]["p95_ms"] for x in samples if x.get(svc, {}).get("p95_ms") is not None]
        out[svc] = (median(errs) if errs else None, median(p95s) if p95s else None)
    return out


def store(conn: sqlite3.Connection, values: dict[str, tuple[float | None, float | None]], now: float) -> None:
    conn.executemany("INSERT OR REPLACE INTO baselines (service, err_ratio, p95_ms, updated_at) VALUES (?, ?, ?, ?)",
                     [(svc, err, p95, now) for svc, (err, p95) in values.items()])
    conn.commit()


# {svc: p95_ms} for the detector
def load(conn: sqlite3.Connection) -> dict[str, float]:
    return {r["service"]: r["p95_ms"] for r in conn.execute("SELECT service, p95_ms FROM baselines")
            if r["p95_ms"] is not None}
