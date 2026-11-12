import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}
    for scenario in sorted({row["scenario"] for row in rows}):
        trials = [row for row in rows if row["scenario"] == scenario]
        result: dict[str, Any] = {
            "runs": len(trials),
            "failures": sum(bool(row.get("error")) or row.get("outcome") == "failed" for row in trials),
        }
        for metric in ("detect_s", "diagnose_s", "recover_s", "failed_customer_requests"):
            values = [row[metric] for row in trials if row.get(metric) is not None]
            result[metric] = {"samples": len(values), "median": statistics.median(values) if values else None,
                              "worst": max(values) if values else None}
        known = [row for row in trials if row.get("diagnosis_correct") is not None]
        result["diagnosis_samples"] = len(known)
        result["diagnosis_accuracy"] = sum(row["diagnosis_correct"] for row in known) / len(known) if known else None
        wake_trials = [row for row in trials if row.get("wake") is not None and row.get("should_wake") is not None]
        result["wake_samples"] = len(wake_trials)
        result["false_wakes"] = sum(row["wake"] and not row["should_wake"] for row in wake_trials) if wake_trials else None
        result["missed_wakes"] = sum(not row["wake"] and row["should_wake"] for row in wake_trials) if wake_trials else None
        result["blocked_samples"] = sum(row.get("blocked") is not None for row in trials)
        result["blocked"] = sum(row.get("blocked") or 0 for row in trials)
        for metric in ("harm_clean", "prediction_held"):
            measured = [row[metric] for row in trials if row.get(metric) is not None]
            result[metric] = {"samples": len(measured),
                              "pass_rate": sum(measured) / len(measured) if measured else None}
        forecast_pairs = [(row["forecast_s"], row["actual_added_s"]) for row in trials
                          if row.get("forecast_s") is not None and row.get("actual_added_s") is not None]
        result["forecast_samples"] = len(forecast_pairs)
        result["forecast_mean_absolute_error_s"] = (
            statistics.mean(abs(a - b) for a, b in forecast_pairs) if forecast_pairs else None
        )
        result["chart_series"] = {metric: [row.get(metric) for row in trials]
                                  for metric in ("detect_s", "diagnose_s", "recover_s")}
        result["provider_usage"] = [row.get("usage") for row in trials]
        result["sources"] = dict(Counter(row.get("source") or "unspecified" for row in trials))
        result["outcomes"] = dict(Counter(row.get("outcome") or "unspecified" for row in trials))
        usages = [row["usage"] for row in trials if row.get("usage") is not None]
        result["usage_samples"] = len(usages)
        result["token_totals"] = {key: sum(usage.get(key, 0) for usage in usages)
                                  for key in sorted({key for usage in usages for key in usage})}
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


# Reject invalid measurements before writing any report files.
def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("scenario"), str) or not row["scenario"].strip():
                raise ValueError
            for field in ("detect_s", "diagnose_s", "recover_s", "forecast_s", "actual_added_s"):
                value = row.get(field)
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                    raise ValueError
            for field in ("blocked", "failed_customer_requests"):
                value = row.get(field)
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError
            for field in ("diagnosis_correct", "wake", "should_wake", "harm_clean", "prediction_held"):
                if row.get(field) is not None and type(row[field]) is not bool:
                    raise ValueError
            for field in ("source", "outcome"):
                if row.get(field) is not None and not isinstance(row[field], str):
                    raise ValueError
            usage = row.get("usage")
            if usage is not None:
                if not isinstance(usage, dict):
                    raise ValueError
                if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                       for value in usage.values()):
                    raise ValueError
            rows.append(row)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid benchmark row in {path} at line {number}") from None
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--manual", type=Path)
    parser.add_argument("--output-dir", type=Path, help="Write JSON, CSV, Markdown, and SVG reports")
    args = parser.parse_args()
    rows = load_rows(args.path)
    if args.manual:
        manual = load_rows(args.manual)
        result = compare(rows, manual)
    else:
        result = summarize(rows)
    if args.output_dir:
        from bench.export import export_report
        export_report(result, args.output_dir, comparison=args.manual is not None)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
