import asyncio
import time
from typing import Any

import discord
import httpx

from gateway.client import read_events
from notifier.discord_bot import DiscordNotifier
from notifier.state import NotifierState
from schemas.models import Card

TERMINAL = {"incident_resolved", "handed_off"}
# payload extras the embeds show; kept with a wake so a re-page shows them too
DETAILS = ("runbook", "seen_before")


class NotificationConsumer:
    def __init__(self, client: httpx.AsyncClient, gateway_url: str, notifier: DiscordNotifier,
                 state: NotifierState, repage_s: float = 120):
        self.client, self.gateway_url, self.notifier, self.state = client, gateway_url, notifier, state
        self.repage_s = repage_s

    async def handle(self, record: dict[str, Any]):
        seq = int(record["seq"])
        if seq <= self.state.get("cursor", 0):
            return
        event = record["event"]
        incident_id, kind = event.get("incident_id"), event["type"]
        payload = event.get("payload", {})
        details = {k: payload[k] for k in DETAILS if payload.get(k)}
        pending = self.state.get("wakes", {})
        if kind in TERMINAL:
            pending.pop(incident_id, None)
        if kind in {"approval_requested", "incident_resolved", "escalated", "handed_off"}:
            card = Card.model_validate(payload["card"])
            if kind == "approval_requested":
                await self.notifier.request_approval(payload["approval_id"], card,
                                                     payload["diff"], payload["forecast"], payload["expires_at"],
                                                     details=details)
                pending[incident_id] = {"card": card.model_dump(), "briefing": "Approval pending",
                                        "last_page": time.time(), "approval_id": payload["approval_id"],
                                        "details": details, "pages": 1}
            elif kind == "incident_resolved":
                if card.status == "MITIGATED, NOT FIXED":
                    await self.notifier.ticket(card, details=details)
                else:
                    await self.notifier.fyi(card, self.link(payload.get("receipt_url", "")), details=details)
            elif kind == "escalated":
                message_id = await self.notifier.wake(card, payload.get("briefing", ""), details=details)
                pending[incident_id] = {"card": card.model_dump(), "briefing": payload.get("briefing", ""),
                                        "last_page": time.time(), "message_id": message_id,
                                        "details": details, "pages": 1}
            else:
                await self.notifier.fyi(card, self.link(payload.get("receipt_url", "")), details=details)
        if kind == "approval_decided":
            approval_id = payload["approval_id"]
            row = self.state.get(f"approval:{approval_id}")
            if row:
                row["decision"] = payload["decision"]
                self.state.set(f"approval:{approval_id}", row)
            # human said yes: stop paging; reject/expiry is followed by gateway escalation
            wake = pending.get(incident_id)
            if payload["decision"] == "approved" and wake and wake.get("approval_id") == approval_id:
                pending.pop(incident_id)
        if payload.get("acknowledged"):
            pending.pop(incident_id, None)
        self.state.set("wakes", pending)
        self.state.set("cursor", seq)

    # gateway sends "/receipts/2"; discord needs a full link to make it clickable
    def link(self, url: str) -> str:
        return f"{self.gateway_url.rstrip('/')}{url}" if url.startswith("/") else url

    async def repage_once(self):
        sent: dict[str, tuple[float, Any, int]] = {}
        for incident_id, row in self.state.get("wakes", {}).items():
            if self.state.get(f"ack:{incident_id}") or time.time() - row["last_page"] < self.repage_s:
                continue
            page = row.get("pages", 1) + 1
            try:
                message_id = await self.notifier.wake(Card.model_validate(row["card"]), row["briefing"],
                                                      details={**row.get("details", {}), "page": page})
            except (discord.HTTPException, httpx.HTTPError):
                continue
            sent[incident_id] = (time.time(), message_id, page)
        # re-read: an incident can close while we wait on Discord; writing the old list back revived it
        pending = self.state.get("wakes", {})
        for incident_id in [i for i in pending if self.state.get(f"ack:{i}")]:
            pending.pop(incident_id)  # a human acknowledged it: stop paging
        for incident_id, (ts, message_id, page) in sent.items():
            if incident_id in pending:
                row = pending[incident_id]
                row["last_page"], row["message_id"], row["pages"] = ts, message_id or row.get("message_id"), page
        self.state.set("wakes", pending)

    async def repage(self):
        while True:
            await asyncio.sleep(min(10, self.repage_s))
            await self.repage_once()

    async def expire_once(self):
        for approval_id, row in self.state.approvals().items():
            decision = row.get("decision")
            if not decision and row["expires_at"] <= time.time():
                decision = "expired"
                row["decision"] = decision
                self.state.set(f"approval:{approval_id}", row)
                self.mark_wake_expired(approval_id)
            if decision and not row.get("view_closed"):
                try:
                    await self.notifier.close_approval(approval_id, row, decision)
                except discord.HTTPException:
                    continue
                row["view_closed"] = True
                self.state.set(f"approval:{approval_id}", row)

    # gateway sends nothing on silent expiry; keep paging but stop saying "pending"
    def mark_wake_expired(self, approval_id: str):
        pending = self.state.get("wakes", {})
        for row in pending.values():
            if row.get("approval_id") == approval_id:
                row["briefing"] = "Approval expired; no action taken"
        self.state.set("wakes", pending)

    async def expire_approvals(self):
        while True:
            await self.expire_once()
            await asyncio.sleep(5)

    async def run(self):
        await self.notifier.wait_until_ready()
        async with asyncio.TaskGroup() as group:
            group.create_task(self.repage())
            group.create_task(self.expire_approvals())
            while True:
                try:
                    async for record in read_events(self.client, self.gateway_url, self.state.get("cursor", 0)):
                        await self.handle(record)
                    await asyncio.sleep(1)
                except (httpx.HTTPError, ValueError, KeyError, discord.HTTPException):
                    await asyncio.sleep(2)
