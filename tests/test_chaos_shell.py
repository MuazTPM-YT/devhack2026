from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from chaos import cli, shell


def completions(text):
    return [c.text for c in shell.SlashCompleter().get_completions(Document(text), CompleteEvent())]


def test_slash_lists_every_command_and_filters_by_prefix():
    assert completions("/") == shell.NAMES
    assert completions("/in") == ["/inject"]
    assert completions("/zz") == []
    assert completions("inject") == []


def test_inject_completes_fault_names():
    assert completions("/inject ") == list(cli.FAULTS)
    assert completions("/inject sh") == ["shared-outage"]
    assert completions("/inject bad-deploy ") == []


def run(line):
    calls, out = [], []
    keep = shell.dispatch(line, run_cli=lambda argv: calls.append(argv) or 0, out=out.append)
    return keep, calls, "\n".join(out)


def test_dispatch_maps_commands_to_the_cli():
    assert run("/inject bad-deploy")[1] == [["inject", "bad-deploy"]]
    assert run("/status")[1] == [["status"]]
    assert run("/reset")[1] == [["reset"]]
    assert run("/faults")[1] == [["list"]]
    assert run("/truth 5")[1] == [["truth", "--last", "5"]]
    assert run("/kubectl -n shop get pods")[1] == [["kubectl", "-n", "shop", "get", "pods"]]


def test_dispatch_guides_on_bad_input_and_quits():
    assert run("/quit")[0] is False and run("/exit")[0] is False
    keep, calls, out = run("inject bad-deploy")
    assert keep and not calls and "commands start with /" in out
    assert "did you mean /inject" in run("/inj")[2]
    assert "/inject <fault>" in run("/inject")[2]
    assert run("   ")[1] == []
    assert "No closing quotation" in run('/kubectl get "x')[2]


def test_argparse_errors_do_not_kill_the_shell():
    def boom(argv):
        raise SystemExit(2)
    assert shell.dispatch("/inject nope", run_cli=boom, out=lambda s: None) is True


def test_event_lines_read_like_the_ui_timeline():
    assert shell.describe("checklist_step", {"name": "dry_run", "passed": True, "reason": "1 spec paths change"}) == \
        ("ok", "gate passed: dry run · 1 spec paths change")
    assert shell.describe("checklist_step", {"name": "trust_gate", "passed": False})[0] == "warn"
    assert shell.describe("checklist_step", {"name": "policy", "passed": False})[0] == "bad"
    assert shell.describe("llm_called", {"error": "deadline_exceeded"}) == ("bad", "model call failed · deadline_exceeded")
    tone, text = shell.describe("incident_resolved", {"card": {"text": "FIXED in 2m 42s: payment\nWhy: x"}})
    assert tone == "ok" and text.endswith("FIXED in 2m 42s: payment")
    assert shell.describe("something_new", {}) == ("info", "something new")
    line = shell.watch_line({"ts": 0, "event": {"type": "verify_tick", "payload": {"severity": 0, "recovered": True}}})
    assert "health check · severity 0 · recovered" in line


def test_banner_is_rectangular_and_plain_without_a_tty():
    rows = shell.banner(200)
    assert len(rows) == 6 and len({len(r) for r in rows}) == 1
    assert "\x1b[" not in "".join(rows)  # pytest output is not a tty, so no colour codes
    assert shell.banner(20) == ["AKIRA"]


def test_no_command_without_a_terminal_explains_instead_of_hanging(capsys):
    assert cli.main([]) == 2
    assert "needs a terminal" in capsys.readouterr().err
