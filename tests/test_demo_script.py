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
