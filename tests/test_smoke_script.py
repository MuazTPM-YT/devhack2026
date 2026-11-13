import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

T0 = 1000.0


# chaos + observer + gateway in one stub; /events replays one incident and closes
def serve(events: list[str]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, body: str, kind: str = "application/json"):
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            self.reply(json.dumps({"ts": T0, "type": "bad_deploy" if "bad-deploy" in self.path else "reset"}))

        def do_GET(self):
            if self.path == "/health/now":
                return self.reply(json.dumps({"severity": 0}))
            records = [{"ts": T0 + i + 1, "event": {"type": t, "incident_id": "inc-1"}} for i, t in enumerate(events)]
            self.reply("".join(f"data: {json.dumps(r)}\n\n" for r in records), "text/event-stream")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def smoke(events: list[str]) -> subprocess.CompletedProcess:
    server = serve(events)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        env = {**os.environ, "CHAOS_URL": url, "OBSERVER_URL": url, "GATEWAY_URL": url, "TIMEOUT_S": "10"}
        return subprocess.run(["bash", "scripts/smoke.sh"], env=env, text=True, capture_output=True, timeout=30)
    finally:
        server.shutdown()


def test_fix_by_the_agent_passes():
    result = smoke(["incident_opened", "diagnosis_ready", "action_executed", "incident_resolved"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "outcome=incident_resolved" in result.stdout


# live smoke inc-1794562461681: closed as "problem no longer present" with payment:v2-bad still live
def test_resolved_without_an_action_fails():
    result = smoke(["incident_opened", "diagnosis_ready", "incident_resolved"])
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no action" in result.stdout
