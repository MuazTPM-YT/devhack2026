import os
import shutil
import signal
import subprocess
from pathlib import Path

# cloudflared's own error when trycloudflare refuses a quick tunnel; the URL in it is not a tunnel
REFUSED = (
    '2026-11-13T15:00:00Z ERR Error requesting quick Tunnel error="failed to request quick Tunnel: '
    'Post \\"https://api.trycloudflare.com/tunnel\\": 429 Too Many Requests"'
)
GOOD_URL = "https://alpha-bravo-charlie.trycloudflare.com"


# fake cloudflared logs a refusal for the first `refusals` starts, then GOOD_URL; it stays up so the
# log is read before it dies (no race). curl says 405, sleep is instant
def fake_bin(tmp: Path, refusals: int) -> Path:
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    real_sleep = shutil.which("sleep")
    (tmp / "starts").write_text("0")
    scripts = {
        "cloudflared": f"""#!/usr/bin/env bash
n=$(( $(cat {tmp}/starts) + 1 )); echo $n > {tmp}/starts
if [ $n -le {refusals} ]; then echo '{REFUSED}'; else echo '|  {GOOD_URL}  |'; fi
exec {real_sleep} 30
""",
        "curl": "#!/usr/bin/env bash\nprintf 405\n",
        "sleep": "#!/usr/bin/env bash\n:\n",
    }
    for name, body in scripts.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o755)
    return bin_dir


def run_tunnel(tmp: Path, refusals: int) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{fake_bin(tmp, refusals)}:{os.environ['PATH']}"}
    script = f'source scripts/demo.sh; RUN={tmp}; tunnel tun-x http://127.0.0.1:1'
    try:
        return subprocess.run(["bash", "-c", script], env=env, text=True, capture_output=True, timeout=30)
    finally:
        pid_file = tmp / "tun-x.pid"
        if pid_file.exists():
            try:
                os.killpg(int(pid_file.read_text()), signal.SIGTERM)
            except ProcessLookupError:
                pass


# live 2026-11-13: 3 of 4 tunnels refused, bundle shipped https://api.trycloudflare.com as their URL
def test_refused_tunnel_fails_and_writes_no_url(tmp_path):
    result = run_tunnel(tmp_path, refusals=99)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL  tun-x" in result.stderr
    assert "429 Too Many Requests" in result.stderr
    assert not (tmp_path / "tun-x.url").exists()
    assert (tmp_path / "starts").read_text().strip() == "3"


def test_refused_tunnel_is_retried(tmp_path):
    result = run_tunnel(tmp_path, refusals=2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "tun-x.url").read_text().strip() == GOOD_URL
    assert "RETRY tun-x" in result.stderr


def judge(tmp: Path, body: str, env: dict | None = None) -> subprocess.CompletedProcess:
    script = f'source scripts/demo.sh; RUN={tmp}; {body}'
    return subprocess.run(["bash", "-c", script], env={**os.environ, **(env or {})}, text=True,
                          capture_output=True, timeout=30)


# live 2026-11-13: a second `shop` run skipped the chaos already serving :7004 but minted a new judge
# token for the bundle, so every chaos call from the backend got 401. The token chaos runs with is reused
def test_rerun_hands_out_the_token_chaos_already_has(tmp_path):
    env = {"CHAOS_JUDGE_TOKEN": ""}
    first = judge(tmp_path, "serving() { return 1; }; judge_token", env)
    assert first.returncode == 0 and len(first.stdout) == 48, first.stderr
    assert oct((tmp_path / "chaos-judge.token").stat().st_mode & 0o777) == "0o600"
    again = judge(tmp_path, "serving() { return 0; }; judge_token", {"CHAOS_JUDGE_TOKEN": "other-token-0123456789"})
    assert again.stdout == first.stdout  # chaos is up with the first token: the bundle must carry that one


def test_judge_token_from_env_or_new_when_chaos_is_down(tmp_path):
    (tmp_path / "chaos-judge.token").write_text("stale-token-from-last-session")
    out = judge(tmp_path, "serving() { return 1; }; judge_token", {"CHAOS_JUDGE_TOKEN": "env-token-0123456789"})
    assert out.stdout == "env-token-0123456789"


def test_chaos_up_with_unknown_token_fails_loud(tmp_path):
    out = judge(tmp_path, "serving() { return 0; }; judge_token", {"CHAOS_JUDGE_TOKEN": ""})
    assert out.returncode != 0 and "shop_machine.sh down" in out.stderr
