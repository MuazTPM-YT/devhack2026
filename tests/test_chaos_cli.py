import httpx
import pytest
from fastapi.testclient import TestClient

from chaos import cli
from chaos.main import FAULTS, create_app
from tests.test_chaos import FakeKubectl, FakeRaw


# send the CLI's HTTP calls into the real chaos app, in process
@pytest.fixture
def chaos_app(tmp_path, monkeypatch):
    raw = FakeRaw()
    fake = FakeKubectl()
    with TestClient(create_app(tmp_path, fake, raw, severity=lambda: 0, reset_stable_s=0)) as client:
        def request(method, url, timeout=None, **kw):
            assert url.startswith("http://chaos")
            return client.request(method, url.removeprefix("http://chaos"), **kw)
        monkeypatch.setattr(cli.httpx, "request", request)
        yield fake, raw


def run(*argv):
    return cli.main(["--chaos-url", "http://chaos", *argv])


def test_cli_faults_match_chaos_routes():
    assert set(cli.FAULTS) == set(FAULTS)


def test_inject_records_ground_truth_then_reset_restores(chaos_app, capsys):
    fake, _ = chaos_app
    assert run("inject", "bad-deploy") == 0
    assert "bad_deploy" in capsys.readouterr().out
    assert fake.image("payment") != "ghcr.io/open-telemetry/demo:3.1.0-payment"
    assert run("reset") == 0
    out = capsys.readouterr().out
    assert "restored payment" in out and "healthy yes" in out
    assert run("truth") == 0
    assert "bad_deploy" in capsys.readouterr().out


def test_unknown_fault_is_rejected_before_any_call(chaos_app):
    with pytest.raises(SystemExit) as e:
        run("inject", "rm-rf")
    assert e.value.code == 2


def test_kubectl_passes_flags_and_is_logged(chaos_app, capsys):
    _, raw = chaos_app
    assert run("kubectl", "scale", "deploy/cart", "--replicas=0") == 0
    assert raw.calls == [["scale", "deploy/cart", "--replicas=0"]]
    assert "logged as ground truth" in capsys.readouterr().out


def test_kubectl_leading_option_after_double_dash(chaos_app):
    _, raw = chaos_app
    assert run("kubectl", "--", "-n", "shop", "get", "pods") == 0
    assert raw.calls == [["-n", "shop", "get", "pods"]]


def test_kubectl_shell_metacharacters_stay_plain_words(chaos_app):
    _, raw = chaos_app
    run("kubectl", "get", "pods", "|", "rm", "$(id)")
    assert raw.calls == [["get", "pods", "|", "rm", "$(id)"]]


def test_kubectl_failure_exits_1(chaos_app, capsys):
    _, raw = chaos_app
    raw.result = (False, "Error from server (NotFound)")
    assert run("kubectl", "get", "deploy", "nope") == 1
    assert "NotFound" in capsys.readouterr().err


def test_unreachable_service_says_so(monkeypatch, capsys):
    def down(*a, **kw):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(cli.httpx, "request", down)
    assert run("inject", "bad-deploy") == 1
    assert "cannot reach http://chaos/chaos/bad-deploy" in capsys.readouterr().err


def test_status_lists_unhealthy_first(monkeypatch, capsys):
    health = {"ts": 0, "severity": 5, "services": {
        "ad": {"err_ratio": 0.0, "p95_ms": 2.0, "unhealthy": False, "breaching": False, "bad_pods": 0},
        "payment": {"err_ratio": 0.4, "p95_ms": 30.0, "unhealthy": True, "breaching": True, "bad_pods": 0}}}
    monkeypatch.setattr(cli.httpx, "request",
                        lambda m, url, **kw: httpx.Response(200, json=health, request=httpx.Request(m, url)))
    assert cli.main(["--observer-url", "http://obs", "status"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "severity 5" in lines[0] and "1 of 2" in lines[0]
    assert "payment" in lines[1] and "UNHEALTHY" in lines[1] and "40.0%" in lines[1]


def test_kubectl_leading_option_without_double_dash(chaos_app):
    _, raw = chaos_app
    assert run("kubectl", "-n", "shop", "get", "pods") == 0
    assert raw.calls == [["-n", "shop", "get", "pods"]]


def test_kubectl_without_args_is_an_error(chaos_app, capsys):
    assert run("kubectl") == 1
    assert "give kubectl arguments" in capsys.readouterr().err


# chaos writes need ONCALL_API_TOKEN now; without it the CLI says so plainly and sends nothing
def test_write_without_token_says_so_and_sends_nothing(monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(cli.httpx, "request", lambda *a, **k: sent.append(a))
    monkeypatch.delenv("ONCALL_API_TOKEN")
    assert run("inject", "bad-deploy") == 1
    assert sent == [] and "ONCALL_API_TOKEN" in capsys.readouterr().err
