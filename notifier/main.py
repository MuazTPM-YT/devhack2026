import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI

from notifier.consumer import NotificationConsumer
from notifier.discord_bot import ApprovalController, DiscordNotifier
from notifier.state import NotifierState
from schemas import auth, logs

logs.setup()


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
    auth.token()  # the gateway refuses decisions without it; fail at start
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
            bot_task = group.create_task(notifier.start(token))
            consumer_task = group.create_task(consumer.run())
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
