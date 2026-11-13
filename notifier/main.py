import asyncio
import logging
import os
import signal
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import discord
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from notifier.consumer import NotificationConsumer
from notifier.discord_bot import ApprovalController, DiscordNotifier
from notifier.state import NotifierState
from schemas import auth, logs

logs.setup()
log = logging.getLogger(__name__)


class Ack(BaseModel):
    by: str = Field(min_length=1, max_length=40)
    via: Literal["discord", "akira-mcp"] = "akira-mcp"

log = logging.getLogger("notifier")
BOT_TRIES = 5


# live 2026-11-13: discord answered the first handshake with 503, discord.py crashed in its own reconnect
# (AttributeError), and paging died while /health still answered: an approval expired unseen.
# Reconnect a few times; a wrong token never gets better, so it fails at once
async def run_bot(client, token: str, tries: int = BOT_TRIES, wait_s: float = 5.0, sleep=asyncio.sleep) -> None:
    for attempt in range(1, tries + 1):
        try:
            await client.start(token)
            return  # closed on purpose: shutdown
        except discord.LoginFailure:
            raise
        except Exception as e:
            log.error("discord bot stopped (%r); reconnect %s of %s in %.0f s", e, attempt, tries, wait_s * attempt)
            await client.close()
            client.clear()  # discord.py: makes a closed client startable again
            await sleep(wait_s * attempt)
    raise RuntimeError(f"discord unreachable after {tries} tries; no page can go out")


# a dead bot or consumer must stop the process, not leave it up and silent
def die_on_failure(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        log.critical("notifier %s failed: %r; stopping so nobody mistakes it for alive", task.get_name(),
                     task.exception())
        os.kill(os.getpid(), signal.SIGTERM)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing {name}")
    return value


def load_approvers() -> set[str]:
    approvers = {value.strip() for value in required("ONCALL_APPROVER_IDS").split(",") if value.strip()}
    if not approvers:
        raise ValueError("Missing ONCALL_APPROVER_IDS")
    if "rehearsal-harness" in approvers:
        raise ValueError("rehearsal-harness is forbidden in ONCALL_APPROVER_IDS")
    return approvers


@asynccontextmanager
async def lifespan(app: FastAPI):
    token = required("DISCORD_BOT_TOKEN")
    auth.agent_start()  # the gateway refuses decisions without it; fail at start
    channels = [int(required(name)) for name in (
        "DISCORD_FYI_CHANNEL_ID", "DISCORD_WAKE_CHANNEL_ID", "DISCORD_TICKETS_CHANNEL_ID",
        "DISCORD_ONCALL_ROLE_ID")]
    approvers = load_approvers()
    gateway_url = required("GATEWAY_URL").rstrip("/")
    state = NotifierState(Path("data/notifier.db"))
    async with httpx.AsyncClient() as client:
        controller = ApprovalController(client, gateway_url, approvers, state)
        notifier = DiscordNotifier(controller, *channels)
        consumer = NotificationConsumer(client, gateway_url, notifier, state,
                                         float(os.environ.get("REPAGE_SECONDS", "120")))
        async with asyncio.TaskGroup() as group:
            bot_task = group.create_task(run_bot(notifier, token), name="discord bot")
            consumer_task = group.create_task(consumer.run(), name="event consumer")
            for task in (bot_task, consumer_task):
                task.add_done_callback(die_on_failure)
            app.state.notifier = notifier
            try:
                yield
            finally:
                consumer_task.cancel()
                await notifier.close()
                bot_task.cancel()


app = FastAPI(lifespan=lifespan)
app.add_middleware(auth.TokenGuard)  # ack writes need our token; /health and /pages stay open like gateway reads


@app.get("/health")
async def health():
    notifier = getattr(app.state, "notifier", None)
    return {"ready": bool(notifier and notifier.is_ready())}


def running() -> DiscordNotifier:
    notifier = getattr(app.state, "notifier", None)
    if notifier is None:
        raise HTTPException(503, "notifier not started")
    return notifier


# what Discord is waiting on: wake pages still re-paging, approval messages not yet decided
@app.get("/pages")
async def pages():
    state = running().controller.state
    now = time.time()
    wakes = [{"incident_id": i, "briefing": w.get("briefing"), "pages": w.get("pages", 1),
              "last_page": w.get("last_page"), "approval_id": w.get("approval_id"),
              "headline": (w.get("card") or {}).get("headline") or (w.get("card") or {}).get("status"),
              "acknowledged": state.get(f"ack:{i}")} for i, w in (state.get("wakes") or {}).items()]
    asks = [{"approval_id": a, "expires_at": r.get("expires_at")} for a, r in state.approvals().items()
            if not r.get("decision") and (r.get("expires_at") or 0) > now]
    return {"pages": wakes, "approvals": asks}


# acknowledge without opening Discord: same allowlist as the button, then the message loses its button
@app.post("/pages/{incident_id}/ack")
async def ack(incident_id: str, body: Ack):
    notifier = running()
    row = (notifier.controller.state.get("wakes") or {}).get(incident_id)
    if row is None:
        raise HTTPException(404, "no open page for this incident")
    result = await notifier.controller.acknowledge(incident_id, body.by)
    if result == "not authorised":
        raise HTTPException(403, result)
    if result == "already acknowledged":
        raise HTTPException(409, result)
    updated = False
    if row.get("message_id"):
        try:
            await notifier.close_page(row["message_id"], body.by, via=body.via)
            updated = True
        except (discord.HTTPException, ValueError) as e:
            log.warning("ack %s: wake message not updated: %s", incident_id, type(e).__name__)
    return {"result": result, "message_updated": updated}
