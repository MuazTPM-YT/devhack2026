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
        wake_trials = [row for row in trials if row.get("wake") is not None and row.get("should_wake") is not None]
        result["false_wakes"] = sum(row["wake"] and not row["should_wake"] for row in wake_trials) if wake_trials else None
        result["missed_wakes"] = sum(not row["wake"] and row["should_wake"] for row in wake_trials) if wake_trials else None
        result["blocked"] = sum(row.get("blocked", 0) for row in trials)
        for metric in ("harm_clean", "prediction_held"):
            measured = [row[metric] for row in trials if row.get(metric) is not None]
            result[metric] = {"samples": len(measured),
                              "pass_rate": sum(measured) / len(measured) if measured else None}
        forecast_pairs = [(row["forecast_s"], row["actual_added_s"]) for row in trials
                          if row.get("forecast_s") is not None and row.get("actual_added_s") is not None]
        result["forecast_mean_absolute_error_s"] = (
            statistics.mean(abs(a - b) for a, b in forecast_pairs) if forecast_pairs else None
        )
        result["chart_series"] = {metric: [row.get(metric) for row in trials]
                                  for metric in ("detect_s", "diagnose_s", "recover_s")}
        result["provider_usage"] = [row.get("usage") for row in trials]
        result["billing"] = "subscription; token counts are not cash charges"
        summary[scenario] = result
    return summary


def compare(agent_rows: list[dict[str, Any]], manual_rows: list[dict[str, Any]]) -> dict[str, Any]:
    agent, manual = summarize(agent_rows), summarize(manual_rows)
    speedup = {}
    for scenario in sorted(set(agent) & set(manual)):
        automated = agent[scenario]["recover_s"]["median"]
        baseline = manual[scenario]["recover_s"]["median"]
        speedup[scenario] = baseline / automated if automated and baseline is not None else None
    return {"agent": agent, "manual": manual, "recovery_speedup": speedup}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--manual", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.path.read_text().splitlines() if line.strip()]
    if args.manual:
        manual = [json.loads(line) for line in args.manual.read_text().splitlines() if line.strip()]
        result = compare(rows, manual)
    else:
        result = summarize(rows)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
