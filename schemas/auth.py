# shared secret between our own processes: before it, any local program could approve as a listed approver
import hmac
import os

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

ENV = "ONCALL_API_TOKEN"
HEADER = "X-Oncall-Token"
READS = {"GET", "HEAD", "OPTIONS"}
# the judge plane: who may break the shop. Never the same secret as the agent's own processes
JUDGE_ENV = "CHAOS_JUDGE_TOKEN"
JUDGE_HEADER = "X-Chaos-Token"


def token(env: str = ENV) -> str:
    value = os.environ.get(env, "").strip()
    if len(value) < 16:
        raise RuntimeError(f"missing required env var(s): {env} (at least 16 characters)")
    return value


# start of an agent process (observer, brain, gateway, notifier): needs our token, and must not keep the
# judge's. They load the same .env as the judge tooling, so the secret is dropped here, before any request
def agent_start() -> str:
    os.environ.pop(JUDGE_ENV, None)
    return token()


def headers(env: str = ENV, header: str = HEADER) -> dict[str, str]:
    return {header: token(env)}


# every write (POST, DELETE, ...) needs the token; reads stay open so the browser UI can poll and stream.
# guard_reads: reads need it too (chaos: its GETs return the answers to a blind challenge)
class TokenGuard:
    def __init__(self, app: ASGIApp, env: str = ENV, header: str = HEADER, guard_reads: bool = False):
        self.app, self.env, self.header, self.guard_reads = app, env, header, guard_reads

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and (self.guard_reads or scope["method"] not in READS):
            supplied = dict(scope["headers"]).get(self.header.lower().encode(), b"")
            if not hmac.compare_digest(supplied, token(self.env).encode()):
                await JSONResponse({"detail": f"missing or wrong {self.header}"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)
