import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager
from pathlib import Path

import discord
import httpx
from fastapi import FastAPI

from notifier.consumer import NotificationConsumer
from notifier.discord_bot import ApprovalController, DiscordNotifier
from notifier.state import NotifierState
from schemas import auth, logs

logs.setup()

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


@app.get("/health")
async def health():
    notifier = getattr(app.state, "notifier", None)
    return {"ready": bool(notifier and notifier.is_ready())}
