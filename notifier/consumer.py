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
        pending = self.state.get("wakes", {})
        if kind in TERMINAL:
            pending.pop(incident_id, None)
        if kind in {"approval_requested", "incident_resolved", "escalated", "handed_off"}:
            card = Card.model_validate(payload["card"])
            if kind == "approval_requested":
                await self.notifier.request_approval(payload["approval_id"], card,
                                                     payload["diff"], payload["forecast"], payload["expires_at"])
                pending[incident_id] = {"card": card.model_dump(), "briefing": "Approval pending",
                                        "last_page": time.time(), "approval_id": payload["approval_id"]}
            elif kind == "incident_resolved":
                if card.status == "MITIGATED, NOT FIXED":
                    await self.notifier.ticket(card)
                else:
                    await self.notifier.fyi(card, payload.get("receipt_url", ""))
            elif kind == "escalated":
                message_id = await self.notifier.wake(card, payload.get("briefing", ""))
                pending[incident_id] = {"card": card.model_dump(), "briefing": payload.get("briefing", ""),
                                        "last_page": time.time(), "message_id": message_id}
            else:
                await self.notifier.fyi(card, payload.get("receipt_url", ""))
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

    async def repage_once(self):
        pending = self.state.get("wakes", {})
        for incident_id in [i for i in pending if self.state.get(f"ack:{i}")]:
            pending.pop(incident_id)  # a human acknowledged it: stop paging
        for row in pending.values():
            if time.time() - row["last_page"] >= self.repage_s:
                try:
                    message_id = await self.notifier.wake(Card.model_validate(row["card"]), row["briefing"])
                except (discord.HTTPException, httpx.HTTPError):
                    continue
                row["last_page"], row["message_id"] = time.time(), message_id or row.get("message_id")
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
