# experience memory: past incidents with the outcome code verified. Learning without training: the
# brain shows them to the LLM, the notifier shows "seen before". Nothing here grants permission.
import sqlite3

TERMINAL = ("resolved", "escalated", "handed_off")


# closest finished incidents first: same culprit and pattern, then same culprit, then same pattern; newest wins ties
# caller holds its DB lock
def similar(conn: sqlite3.Connection, incident_id: str, culprit: str | None, pattern: str | None,
            limit: int = 3) -> list[dict]:
    if not culprit and not pattern:
        return []
    rows = conn.execute(
        "SELECT i.id, i.opened_at, i.resolved_at, i.culprit, i.pattern, i.state, i.llm_why, "
        "r.tool, r.target, r.outcome FROM incidents i "
        "LEFT JOIN receipts r ON r.id = (SELECT MAX(id) FROM receipts WHERE incident_id = i.id) "
        f"WHERE i.id != ? AND i.state IN {TERMINAL} AND (i.culprit = ? OR i.pattern = ?) "
        "ORDER BY (i.culprit IS ? AND i.pattern IS ?) DESC, (i.culprit IS ?) DESC, i.opened_at DESC LIMIT ?",
        (incident_id, culprit, pattern, culprit, pattern, culprit, limit)).fetchall()
    return [{"incident_id": r["id"], "culprit": r["culprit"], "pattern": r["pattern"], "state": r["state"],
             "fix": f"{r['tool']} {r['target']}" if r["tool"] else None, "outcome": r["outcome"],
             "took_s": round(r["resolved_at"] - r["opened_at"]) if r["resolved_at"] and r["opened_at"] else None,
             "model_said": r["llm_why"]} for r in rows]


# one plain line for Discord: "2 similar before, 1 fixed and proven; last (inc-1): rollback_deploy payment -> success in 92 s"
def summary(past: list[dict]) -> str | None:
    if not past:
        return None
    last = past[0]
    how = f"{last['fix']} -> {last['outcome'] or last['state']}" if last["fix"] else f"no action, {last['state']}"
    took = f" in {last['took_s']} s" if last["took_s"] is not None else ""
    worked = sum(1 for p in past if p["outcome"] == "success")
    return f"{len(past)} similar before, {worked} fixed and proven; last ({last['incident_id']}): {how}{took}"
