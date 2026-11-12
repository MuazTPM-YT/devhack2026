import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from gateway.trust import counts, lower_bound


def summarize_ledger(path: Path, confidence: float = 0.95, bar: float = 0.90) -> dict[str, Any]:
    if not 0 < confidence < 1 or not 0 < bar < 1:
        raise ValueError("Confidence and bar must be between 0 and 1")
    if not path.is_file():
        raise ValueError("Ledger database not found")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = []
        keys = db.execute("SELECT DISTINCT pattern, action, target FROM ledger ORDER BY pattern, action, target")
        for key in keys.fetchall():
            separate = counts(db, key["pattern"], key["action"], key["target"])
            successes = separate["rehearsal"][0] + separate["real"][0]
            failures = separate["rehearsal"][1] + separate["real"][1]
            if successes < 0 or failures < 0:
                raise ValueError("Invalid ledger counts")
            bound = lower_bound(successes, failures, confidence)
            rows.append({
                **dict(key), "rehearsal": separate["rehearsal"], "real": separate["real"],
                "successes": successes, "failures": failures, "lower_bound": round(bound, 4),
                "statistical_threshold_met": bound >= bar,
            })
    finally:
        db.close()
    return {"confidence": confidence, "bar": bar, "reset_on_failure": True,
            "authorization_evaluated": False, "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--bar", type=float, default=0.90)
    args = parser.parse_args()
    try:
        result = summarize_ledger(args.database, args.confidence, args.bar)
    except (ValueError, sqlite3.Error) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
