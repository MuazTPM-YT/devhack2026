from typing import Protocol

from schemas.models import Card


# details: the event payload's extras (runbook, seen_before, page) shown in the embed
class Notifier(Protocol):
    async def fyi(self, card: Card, receipt_url: str, details: dict | None = None) -> None: ...
    # returns the posted message id (for the Acknowledge button after a restart), or None
    async def wake(self, card: Card, briefing: str, details: dict | None = None) -> int | None: ...
    async def request_approval(self, approval_id: str, card: Card, diff: str,
                               forecast: str, expires_at: float, details: dict | None = None) -> None: ...
