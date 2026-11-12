# trust gate + ledger (IMPLEMENTATION.md §6.4.6). Key (pattern, action, target); rehearsal and real kept apart.
import sqlite3


# 95% lower bound on success rate. With 0 failures beta.ppf(1-c, s, 1) is exactly (1-c)**(1/s)
def lower_bound(successes: int, failures: int, confidence: float = 0.95) -> float:
    # ponytail: exact for 0 failures only; any failure closes the gate (reset_on_failure), so that's enough
    if successes == 0 or failures > 0:
        return 0.0
    return (1 - confidence) ** (1 / successes)


# auto_eligible: true | false | "stateless_only" (config/policy.yaml tools)
def eligible(tool_policy: dict, target_kind: str) -> bool:
    ae = tool_policy.get("auto_eligible")
    return ae is True or (ae == "stateless_only" and target_kind == "stateless")


def counts(conn: sqlite3.Connection, pattern: str, action: str, target: str) -> dict:
    rows = conn.execute("SELECT source, successes, failures FROM ledger WHERE pattern=? AND action=? AND target=?",
                        (pattern, action, target)).fetchall()
    out = {"rehearsal": (0, 0), "real": (0, 0)}
    for r in rows:
        out[r["source"]] = (r["successes"], r["failures"])
    return out


# gate numbers for the receipt; open only if eligible, no failure, bound >= bar
def check(conn: sqlite3.Connection, trust_policy: dict, tool_policy: dict, pattern: str, action: str,
          target: str, target_kind: str) -> dict:
    if not trust_policy["reset_on_failure"]:
        raise ValueError("trust.reset_on_failure=false needs the general beta bound; not built")
    c = counts(conn, pattern, action, target)
    s = c["rehearsal"][0] + c["real"][0]
    f = c["rehearsal"][1] + c["real"][1]
    bound = lower_bound(s, f, trust_policy["confidence"])
    ok = eligible(tool_policy, target_kind) and pattern != "unknown" and bound >= trust_policy["bar"]
    return {"successes": s, "failures": f, "rehearsal": c["rehearsal"], "real": c["real"],
            "lower_bound": round(bound, 4), "bar": trust_policy["bar"], "open": ok}


def record(conn: sqlite3.Connection, pattern: str, action: str, target: str, source: str, success: bool,
           now: float) -> None:
    conn.execute("INSERT OR IGNORE INTO ledger (pattern, action, target, source) VALUES (?, ?, ?, ?)",
                 (pattern, action, target, source))
    if success:
        conn.execute("UPDATE ledger SET successes = successes + 1 WHERE pattern=? AND action=? AND target=? AND source=?",
                     (pattern, action, target, source))
    else:
        conn.execute("UPDATE ledger SET failures = failures + 1, last_failure_at = ? "
                     "WHERE pattern=? AND action=? AND target=? AND source=?", (now, pattern, action, target, source))
    conn.commit()
