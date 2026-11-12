import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}
    for scenario in sorted({row["scenario"] for row in rows}):
        trials = [row for row in rows if row["scenario"] == scenario]
        result: dict[str, Any] = {"runs": len(trials), "failures": sum(bool(row.get("error")) for row in trials)}
        for metric in ("detect_s", "diagnose_s", "recover_s"):
            values = [row[metric] for row in trials if row.get(metric) is not None]
            result[metric] = {"samples": len(values), "median": statistics.median(values) if values else None,
                              "worst": max(values) if values else None}
        known = [row for row in trials if row.get("diagnosis_correct") is not None]
        result["diagnosis_accuracy"] = sum(row["diagnosis_correct"] for row in known) / len(known) if known else None
        result["false_wakes"] = sum(row["wake"] and not row["should_wake"] for row in trials)
        result["missed_wakes"] = sum(not row["wake"] and row["should_wake"] for row in trials)
        result["blocked"] = sum(row.get("blocked", 0) for row in trials)
        summary[scenario] = result
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.path.read_text().splitlines() if line.strip()]
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
