import csv
import json
from html import escape
from pathlib import Path
from typing import Any

TIMINGS = ("detect_s", "diagnose_s", "recover_s")


def display(value: Any) -> str:
    return "not measured" if value is None else f"{value:.3g}"


def timing_svg(groups: dict[str, dict[str, Any]]) -> str:
    entries = [(label, scenario, metric, row[metric])
               for label, scenarios in groups.items() for scenario, row in scenarios.items()
               for metric in TIMINGS]
    maximum = max((entry[3]["worst"] or 0 for entry in entries), default=0)
    scale = 480 / maximum if maximum else 0
    height = 100 + 36 * len(entries)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1240 {height}" '
             'role="img" aria-labelledby="title description">',
             '<title id="title">Benchmark timings</title>',
             '<desc id="description">Filled bars show median seconds. Outlines show worst seconds. '
             'Missing measurements have no bar. Sample counts exclude missing values.</desc>',
             '<rect width="1240" height="100%" fill="white"/>',
             '<g font-family="sans-serif" font-size="13" fill="#172b4d">',
             '<text x="20" y="24">Timing from injection (seconds): filled median, outlined worst</text>',
             f'<text x="20" y="47">Common scale: 0 to {maximum:.3g} seconds. Missing values are not zero.</text>']
    if not entries:
        parts.append('<text x="20" y="80">No trials recorded.</text>')
    for index, (label, scenario, metric, stats) in enumerate(entries):
        y = 80 + 36 * index
        full_name = f"{label} / {scenario} / {metric}"
        name = escape(full_name if len(full_name) <= 49 else full_name[:46] + "...")
        parts.append(f'<text x="20" y="{y}"><title>{escape(full_name)}</title>{name}</text>')
        if stats["samples"]:
            color = "#146c94" if label == "agent" else "#8a4b08"
            parts.extend([
                f'<rect x="380" y="{y - 13}" width="{stats["worst"] * scale:.3f}" '
                f'height="18" fill="none" stroke="{color}"/>',
                f'<rect x="380" y="{y - 10}" width="{stats["median"] * scale:.3f}" '
                f'height="12" fill="{color}"/>',
            ])
        value = (f'median {display(stats["median"])}; worst {display(stats["worst"])}; n={stats["samples"]}'
                 if stats["samples"] else "not measured; n=0")
        parts.append(f'<text x="880" y="{y}">{value}</text>')
    return "\n".join([*parts, '</g></svg>'])


def markdown(groups: dict[str, dict[str, Any]], speedups: dict[str, Any]) -> str:
    lines = ["# Benchmark report", "",
             "Only recorded inputs are summarized. Missing values are not zero.",
             "Timing medians exclude missing measurements; inspect sample counts and outcomes.",
             "Sources (including rehearsal) are listed below. These results do not grant authorization.",
             "", "![Median and worst timings](timings.svg)", ""]
    table = ["| Dataset | Scenario | Attempts | Failures | Metric | Samples | Median | Worst |",
             "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |"]
    for label, scenarios in groups.items():
        for scenario, row in scenarios.items():
            name = scenario.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")
            for metric in (*TIMINGS, "failed_customer_requests"):
                stats = row[metric]
                table.append(f'| {label} | {name} | {row["runs"]} | {row["failures"]} | '
                             f'{metric} | {stats["samples"]} | {display(stats["median"])} | {display(stats["worst"])} |')
            lines.extend(["", f"## {label}: {name}", "",
                          f'Sources: {json.dumps(row["sources"], sort_keys=True)}.',
                          f'Outcomes: {json.dumps(row["outcomes"], sort_keys=True)}.',
                          f'Diagnosis accuracy: {display(row["diagnosis_accuracy"])} '
                          f'(n={row["diagnosis_samples"]}).',
                          f'False wakes: {display(row["false_wakes"])}; missed wakes: '
                          f'{display(row["missed_wakes"])} (n={row["wake_samples"]}).',
                          f'Blocked actions: {row["blocked"]} (n={row["blocked_samples"]}).',
                          f'Harm pass rate: {display(row["harm_clean"]["pass_rate"])} '
                          f'(n={row["harm_clean"]["samples"]}).',
                          f'Prediction pass rate: {display(row["prediction_held"]["pass_rate"])} '
                          f'(n={row["prediction_held"]["samples"]}).',
                          f'Forecast mean absolute error: {display(row["forecast_mean_absolute_error_s"])} seconds '
                          f'(n={row["forecast_samples"]}).',
                          f'Token totals: {json.dumps(row["token_totals"], sort_keys=True)} '
                          f'(n={row["usage_samples"]}); subscription usage is not a cash charge.', ""])
    if speedups:
        lines.extend(["## Recovery comparison", "",
                      "Manual median / agent median; each side uses its recorded recovery samples.", ""])
        for scenario, value in speedups.items():
            lines.append(f"- {escape(scenario)}: {display(value)}" + ("x" if value is not None else ""))
    if not any(groups.values()):
        lines.append("No trials recorded.")
    insertion = lines.index("![Median and worst timings](timings.svg)") + 2
    lines[insertion:insertion] = [*table, ""]
    return "\n".join(lines) + "\n"


def export_report(result: dict[str, Any], directory: Path, *, comparison: bool = False) -> None:
    groups = {"agent": result["agent"], "manual": result["manual"]} if comparison else {"agent": result}
    report = markdown(groups, result["recovery_speedup"] if comparison else {})
    chart = timing_svg(groups)
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(encoded)
    (directory / "report.md").write_text(report)
    (directory / "timings.svg").write_text(chart)
    with (directory / "timings.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["dataset", "scenario", "attempts", "failures", "metric", "samples", "median", "worst"])
        for label, scenarios in groups.items():
            for scenario, row in scenarios.items():
                for metric in (*TIMINGS, "failed_customer_requests"):
                    stats = row[metric]
                    cell = "'" + scenario if scenario.lstrip().startswith(("=", "+", "-", "@")) else scenario
                    writer.writerow([label, cell, row["runs"], row["failures"], metric,
                                     stats["samples"], stats["median"], stats["worst"]])
