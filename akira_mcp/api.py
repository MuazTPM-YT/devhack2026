# one HTTP client for every Akira service; failures become one readable line for Claude
from typing import Any

import httpx

from schemas import auth


class AkiraError(Exception):
    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status, self.body = status, body


def detail_of(body: Any, text: str) -> str:
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, list):  # FastAPI 422: [{"loc": [...], "msg": ...}]
        return "; ".join(f"{'.'.join(map(str, d.get('loc', [])))}: {d.get('msg')}" for d in detail if isinstance(d, dict))
    return str(detail) if detail is not None else text[:300]


class Api:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def call(self, method: str, url: str, timeout: float = 15, **kw: Any) -> Any:
        try:
            r = await self.client.request(method, url, timeout=timeout, **kw)
        except httpx.TimeoutException:
            raise AkiraError(f"{method} {url} timed out after {timeout:.0f} s") from None
        except httpx.HTTPError as e:
            raise AkiraError(f"cannot reach {url} ({type(e).__name__}); is that service running?") from None
        try:
            body = r.json()
        except ValueError:
            body = None
        if r.is_error:
            raise AkiraError(f"{r.status_code} from {method} {url}: {detail_of(body, r.text)}", r.status_code, body)
        return body

    async def get(self, url: str, **kw: Any) -> Any:
        return await self.call("GET", url, **kw)

    async def post(self, url: str, **kw: Any) -> Any:
        return await self.call("POST", url, **kw)


def oncall() -> dict[str, str]:
    return auth.headers()


def judge() -> dict[str, str]:
    return auth.headers(auth.JUDGE_ENV, auth.JUDGE_HEADER)
