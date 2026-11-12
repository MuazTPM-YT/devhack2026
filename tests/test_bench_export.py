import csv
import json
import xml.etree.ElementTree as ET

import pytest

from bench.export import export_report
from bench.report import compare, load_rows, main, summarize


def test_report_counts_failures_and_measured_denominators():
    result = summarize([
        {"scenario": "bad-deploy", "outcome": "failed", "source": "rehearsal"},
        {"scenario": "bad-deploy", "outcome": "incident_resolved", "source": "rehearsal",
         "recover_s": 12, "failed_customer_requests": 0, "diagnosis_correct": False,
         "usage": {"prompt_tokens": 20}, "forecast_s": 5, "actual_added_s": 2},
    ])["bad-deploy"]
    assert result["runs"] == 2
    assert result["failures"] == 1
    assert result["recover_s"] == {"median": 12, "worst": 12, "samples": 1}
    assert result["failed_customer_requests"] == {"median": 0, "worst": 0, "samples": 1}
    assert result["diagnosis_samples"] == 1
    assert result["diagnosis_accuracy"] == 0
    assert result["wake_samples"] == 0
    assert result["false_wakes"] is None
    assert result["forecast_samples"] == 1
    assert result["forecast_mean_absolute_error_s"] == 3
    assert result["usage_samples"] == 1
    assert result["token_totals"] == {"prompt_tokens": 20}
    assert result["sources"] == {"rehearsal": 2}


def test_exports_preserve_missing_zero_and_manual_only_scenarios(tmp_path):
    result = compare([
        {"scenario": "bad-deploy", "recover_s": 10, "detect_s": 0},
        {"scenario": "bad-deploy", "outcome": "failed"},
        {"scenario": "protected", "outcome": "escalated"},
    ], [
        {"scenario": "bad-deploy", "recover_s": 30},
        {"scenario": "manual-only", "recover_s": 20},
    ])
    export_report(result, tmp_path, comparison=True)
    assert json.loads((tmp_path / "summary.json").read_text()) == result
    with (tmp_path / "timings.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    zero = next(row for row in rows if row["dataset"] == "agent" and row["scenario"] == "bad-deploy"
                and row["metric"] == "detect_s")
    missing = next(row for row in rows if row["scenario"] == "protected" and row["metric"] == "recover_s")
    assert zero["median"] == "0"
    assert zero["samples"] == "1"
    assert missing["median"] == ""
    assert missing["samples"] == "0"
    assert any(row["scenario"] == "manual-only" for row in rows)
    text = (tmp_path / "report.md").read_text()
    assert "not measured" in text
    assert "bad-deploy: 3x" in text
    assert "subscription usage is not a cash charge" in text
    ET.parse(tmp_path / "timings.svg")


def test_svg_escapes_labels_and_empty_report_is_explicit(tmp_path):
    result = summarize([{"scenario": '<script>&"', "recover_s": None}])
    export_report(result, tmp_path)
    tree = ET.parse(tmp_path / "timings.svg")
    assert all(element.tag.rsplit("}", 1)[-1] != "script" for element in tree.iter())
    assert '<script>&" / recover_s' in "".join(tree.getroot().itertext())
    assert "not measured" in "".join(tree.getroot().itertext())
    export_report({}, tmp_path)
    assert "No trials recorded." in (tmp_path / "report.md").read_text()
    assert "No trials recorded." in (tmp_path / "timings.svg").read_text()


@pytest.mark.parametrize("patch", [
    {"recover_s": -1}, {"detect_s": True}, {"diagnose_s": float("nan")},
    {"recover_s": float("inf")}, {"failed_customer_requests": 2.5},
    {"diagnosis_correct": "false"}, {"usage": {"prompt_tokens": -1}},
    {"usage": []}, {"source": []}, {"scenario": ""},
])
def test_invalid_measurements_report_line_without_echoing_row(tmp_path, patch):
    path = tmp_path / "input.jsonl"
    path.write_text('\n' + json.dumps({"scenario": "bad-deploy", **patch}) + '\n')
    with pytest.raises(ValueError, match="at line 2"):
        load_rows(path)


def test_cli_exports_and_retains_json_stdout(tmp_path, monkeypatch, capsys):
    path, output = tmp_path / "input.jsonl", tmp_path / "reports"
    path.write_text(json.dumps({"scenario": "bad-deploy", "recover_s": 10}) + '\n')
    monkeypatch.setattr("sys.argv", ["bench.report", str(path), "--output-dir", str(output)])
    main()
    assert json.loads(capsys.readouterr().out) == json.loads((output / "summary.json").read_text())
    assert {p.name for p in output.iterdir()} == {"report.md", "timings.svg", "timings.csv", "summary.json"}


def test_bad_manual_file_does_not_write_partial_report(tmp_path, monkeypatch):
    agent, manual, output = tmp_path / "agent.jsonl", tmp_path / "manual.jsonl", tmp_path / "report"
    agent.write_text('{"scenario":"bad-deploy"}\n')
    manual.write_text('{"scenario":"bad-deploy","recover_s":-1}\n')
    monkeypatch.setattr("sys.argv", ["bench.report", str(agent), "--manual", str(manual), "--output-dir", str(output)])
    with pytest.raises(ValueError):
        main()
    assert not output.exists()


def test_csv_scenario_cannot_become_a_spreadsheet_formula(tmp_path):
    export_report(summarize([{"scenario": "=1+2", "recover_s": 0}]), tmp_path)
    with (tmp_path / "timings.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert all(row["scenario"] == "'=1+2" for row in rows)
