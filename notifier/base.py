from typing import Protocol

from schemas.models import Card


class Notifier(Protocol):
    async def fyi(self, card: Card, receipt_url: str) -> None: ...
    async def wake(self, card: Card, briefing: str) -> None: ...
    async def request_approval(self, approval_id: str, card: Card, diff: str,
                               forecast: str, expires_at: float) -> None: ...
