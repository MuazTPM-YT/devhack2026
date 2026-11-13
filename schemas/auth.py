# shared secret between our own processes: before it, any local program could approve as a listed approver
import hmac
import os

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

ENV = "ONCALL_API_TOKEN"
HEADER = "X-Oncall-Token"
READS = {"GET", "HEAD", "OPTIONS"}


def token() -> str:
    value = os.environ.get(ENV, "").strip()
    if len(value) < 16:
        raise RuntimeError(f"missing required env var(s): {ENV} (at least 16 characters)")
    return value


def headers() -> dict[str, str]:
    return {HEADER: token()}


# every write (POST, DELETE, ...) needs the token; reads stay open so the browser UI can poll and stream
class TokenGuard:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in READS:
            supplied = dict(scope["headers"]).get(HEADER.lower().encode(), b"")
            if not hmac.compare_digest(supplied, token().encode()):
                await JSONResponse({"detail": f"missing or wrong {HEADER}"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)
