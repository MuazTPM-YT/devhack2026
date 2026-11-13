import asyncio
import re
import time
from collections.abc import Sequence

import discord
import httpx

from brain.redact import redact
from notifier import embeds
from notifier.state import NotifierState
from pydantic import ValidationError

from schemas import auth
from schemas.models import Card, GatewayDecision

COLOUR = {"page": 0xD83C3E, "ask": 0xE8A317, "ok": 0x2EA043, "info": 0x808890}
# re-page notes the notifier writes itself; gateway briefings are already explained inside the card
NOTES = {"Approval pending": "Still waiting for Approve or Reject on the first message.",
         "Approval expired; no action taken": "Nobody approved in time. The agent changed nothing."}


# card parts -> one embed; extra fields go last; cut to discord's limits (title 256, field 1024, total 6000)
def embed_of(card: Card, extra: Sequence[tuple[str, str]] = (), url: str | None = None) -> discord.Embed:
    embed = discord.Embed(title=redact(card.title)[:256], description=redact(card.summary)[:1000],
                          colour=COLOUR.get(card.level, COLOUR["info"]),
                          url=url if url and url.startswith("http") else None)
    if card.footer:
        embed.set_footer(text=redact(card.footer)[:500])
    for name, value, inline in [*((f.label, f.body, f.inline) for f in card.fields), *((n, v, False) for n, v in extra)]:
        # approvers are discord user ids: show the name (a mention inside an embed never pings)
        value = re.sub(r"approved by (\d{15,21})\b", r"approved by <@\1>", value)
        name, value = redact(name)[:256], redact(value)[:1024] or "-"
        if len(embed.fields) == 20 or len(embed) + len(name) + len(value) > 5900:
            break  # a whole-embed overflow makes discord reject the page
        embed.add_field(name=name, value=value, inline=inline)
    return embed


def rehearsal(details: dict | None) -> bool:
    return ((details or {}).get("source") or {}).get("mode") == "rehearsal"


# the push line above the embed; a rehearsal says so first, so test noise is plain in the channel list
def line(card: Card, details: dict | None) -> str:
    return ("[REHEARSAL] " if rehearsal(details) else "") + card.headline


class ApprovalController:
    def __init__(self, client: httpx.AsyncClient, gateway_url: str,
                 approvers: set[str], state: NotifierState):
        self.client, self.gateway_url, self.approvers, self.state = client, gateway_url, approvers, state
        self.lock = asyncio.Lock()

    async def decide(self, approval_id: str, user_id: str, decision: str) -> str:
        async with self.lock:
            if user_id not in self.approvers:
                return "not authorised"
            row = self.state.get(f"approval:{approval_id}")
            if not row or row["expires_at"] <= time.time():
                return "expired"
            if row.get("decision"):
                return "already decided"
            if decision not in {"approved", "rejected"}:
                return "invalid decision"
            response = await self.client.post(
                f"{self.gateway_url}/approvals/{approval_id}/decide",
                json={"decision": decision, "decided_by": user_id}, timeout=10, headers=auth.headers(),
            )
            if response.status_code != 200:
                return "gateway refused decision"
            try:
                result = GatewayDecision.model_validate(response.json())
            except (ValueError, ValidationError):
                return "gateway refused decision"
            if decision == "approved" and result.decision != "executed":
                return "gateway refused decision"
            row.update(decision=decision, decided_by=user_id, decided_at=time.time())
            self.state.set(f"approval:{approval_id}", row)
            return decision


    # plan §6.6: a wake page re-posts until acknowledged or resolved; an on-call person acks it here
    async def acknowledge(self, incident_id: str, user_id: str) -> str:
        if user_id not in self.approvers:
            return "not authorised"
        if self.state.get(f"ack:{incident_id}"):
            return "already acknowledged"
        self.state.set(f"ack:{incident_id}", {"by": user_id, "at": time.time()})
        return f"acknowledged by {user_id}; paging stopped"


class AckButton(discord.ui.Button):
    def __init__(self, incident_id: str, controller: ApprovalController):
        super().__init__(label="Acknowledge", style=discord.ButtonStyle.primary, custom_id=f"ack:{incident_id}")
        self.incident_id, self.controller = incident_id, controller

    async def callback(self, interaction: discord.Interaction):
        user = str(interaction.user.id)
        result = await self.controller.acknowledge(self.incident_id, user)
        await interaction.response.send_message(result, ephemeral=True)
        if result.startswith("acknowledged") and interaction.message:
            self.disabled = True
            embed = embeds.decided(first_embed(interaction.message), "acknowledged", user)
            await interaction.message.edit(view=self.view, embed=embed)


class AckView(discord.ui.View):
    def __init__(self, incident_id: str, controller: ApprovalController):
        super().__init__(timeout=None)
        self.add_item(AckButton(incident_id, controller))


def first_embed(message: discord.Message) -> discord.Embed | None:
    return message.embeds[0] if message.embeds else None


STYLES = {"approved": discord.ButtonStyle.success, "rejected": discord.ButtonStyle.danger}


class ApprovalButton(discord.ui.Button):
    def __init__(self, approval_id: str, decision: str, label: str,
                 controller: ApprovalController):
        super().__init__(label=label, style=STYLES.get(decision, discord.ButtonStyle.secondary),
                         custom_id=f"approval:{approval_id}:{decision}")
        self.approval_id, self.decision, self.controller = approval_id, decision, controller

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = str(interaction.user.id)
        try:
            result = await self.controller.decide(self.approval_id, user, self.decision)
        except httpx.HTTPError:
            result = "gateway unavailable; decision not confirmed"
        await interaction.followup.send(result, ephemeral=True)
        if result in {"approved", "rejected", "expired", "already decided"}:
            if self.view:
                for item in self.view.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
            if interaction.message:
                # "already decided": someone else did; show the stored decider, not the late clicker
                row = self.controller.state.get(f"approval:{self.approval_id}") or {}
                outcome = row.get("decision") or result
                by = row.get("decided_by") if result == "already decided" else (user if result != "expired" else None)
                embed = embeds.decided(first_embed(interaction.message), outcome, by)
                await interaction.message.edit(content=f"Approval {self.approval_id}: {result}", view=self.view,
                                               embed=embed)


class ApprovalView(discord.ui.View):
    def __init__(self, approval_id: str, controller: ApprovalController):
        super().__init__(timeout=None)
        self.add_item(ApprovalButton(approval_id, "approved", "Approve", controller))
        self.add_item(ApprovalButton(approval_id, "rejected", "Reject", controller))


class DiscordNotifier(discord.Client):
    def __init__(self, controller: ApprovalController, fyi_channel: int, wake_channel: int,
                 tickets_channel: int, role_id: int):
        super().__init__(intents=discord.Intents.default())
        self.controller = controller
        self.fyi_channel, self.wake_channel = fyi_channel, wake_channel
        self.tickets_channel, self.role_id = tickets_channel, role_id

    async def setup_hook(self):
        for approval_id, row in self.controller.state.approvals().items():
            if not row.get("decision") and row["expires_at"] > time.time():
                self.add_view(ApprovalView(approval_id, self.controller), message_id=row["message_id"])
        for incident_id, row in (self.controller.state.get("wakes") or {}).items():
            if row.get("message_id") and not self.controller.state.get(f"ack:{incident_id}"):
                self.add_view(AckView(incident_id, self.controller), message_id=row["message_id"])

    async def channel(self, channel_id: int):
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            raise ValueError("Discord channel cannot receive messages")
        return channel

    # wake pings the on-call role in the plain text (an embed never pings); the embed carries the detail
    async def send_text(self, channel_id: int, text: str, *, wake: bool = False, view=None,
                        embed: discord.Embed | None = None):
        channel = await self.channel(channel_id)
        mentions = discord.AllowedMentions(everyone=False, users=False,
                                          roles=[discord.Object(id=self.role_id)] if wake else False)
        prefix = f"<@&{self.role_id}> " if wake else ""
        if embed is not None:
            return await channel.send(prefix + redact(text)[:1900], allowed_mentions=mentions, view=view,
                                      embed=embed)
        return await channel.send(prefix + redact(text)[:1900], allowed_mentions=mentions, view=view)

    # T's card embed + who it is for, what to do, runbook, seen before, origin, timeline, approvers, page count
    # (details = payload extras + the bus record's seq and time)
    def dressed(self, kind: str, card: Card, extra: Sequence[tuple[str, str]] = (), details: dict | None = None,
                url: str | None = None, approval_id: str | None = None,
                expires_at: float | None = None) -> discord.Embed:
        details = details or {}
        page = details.get("page", 1)
        src, started, event = details.get("source"), details.get("started"), details.get("event")
        more: list[tuple[str, str]] = []
        if kind == "approval":
            more.append(("Who can approve", embeds.mentions(self.controller.approvers)))
        if kind == "wake" and page > 1:
            more.append(("Page", f"#{page}; re-pages until acknowledged or resolved"))
        # before runbook and seen-before: when the embed is too big, those go first
        if origin := embeds.origin_text(src, started, page):
            more.append(("Origin", origin))
        if when := embeds.timeline_text(started, event, page):
            more.append(("Timeline", when))
        if rb := details.get("runbook"):
            more.append(("Runbook", embeds.runbook_text(rb)))
        if details.get("seen_before"):
            more.append(("Seen before", details["seen_before"]))
        embed = embed_of(card, [*extra, *more], url=url)
        embed.set_author(name=embeds.AUDIENCE[kind])
        embed.description = f"{embed.description or ''}\n\n**Your move:** " \
                            f"{embeds.your_move(kind, card.status, expires_at)}"
        if rehearsal(details):
            embed.title = f"[REHEARSAL] {embed.title or ''}"[:256]
        embed.set_footer(text=redact(embeds.ids_text(card.footer, event, approval_id))[:500])
        embed.timestamp = embeds.event_time(event)
        while len(embed) > embeds.MAX_TOTAL and len(embed.fields) > 1:
            embed.remove_field(len(embed.fields) - 1)  # discord rejects the whole page over 6000
        return embed

    # cards from before embeds (old events, re-pages) have no fields: send their text as before
    async def fyi(self, card: Card, receipt_url: str, details: dict | None = None) -> None:
        if not card.fields:
            await self.send_text(self.fyi_channel, f"{card.text}\n{receipt_url}")
            return
        await self.send_text(self.fyi_channel, line(card, details),
                             embed=self.dressed("fyi", card, details=details, url=receipt_url))

    async def wake(self, card: Card, briefing: str, details: dict | None = None) -> int | None:
        view = AckView(card.incident_id, self.controller)
        if not card.fields:
            message = await self.send_text(self.wake_channel, f"{card.text}\n{briefing}", wake=True, view=view)
        else:
            note = [("Update", NOTES[briefing])] if briefing in NOTES else []
            message = await self.send_text(self.wake_channel, line(card, details), wake=True, view=view,
                                           embed=self.dressed("wake", card, note, details))
        return message.id

    async def ticket(self, card: Card, details: dict | None = None) -> None:
        if not card.fields:
            await self.send_text(self.tickets_channel, card.text)
            return
        await self.send_text(self.tickets_channel, line(card, details),
                             embed=self.dressed("ticket", card, details=details))

    async def request_approval(self, approval_id: str, card: Card, diff: str,
                               forecast: str, expires_at: float, details: dict | None = None) -> None:
        if self.controller.state.get(f"approval:{approval_id}"):
            return
        view = ApprovalView(approval_id, self.controller)
        if not card.fields:
            message = await self.send_text(self.wake_channel,
                                           f"{card.text}\nDiff: {diff[:500]}\nForecast: {forecast}\n"
                                           f"Expires: <t:{int(expires_at)}:R>", wake=True, view=view)
        else:
            extra = [("Side effects", forecast), ("Exact change", f"```{diff.replace('`', '')[:900]}```"),
                     ("Expires", f"<t:{int(expires_at)}:R> (<t:{int(expires_at)}:t>)")]
            message = await self.send_text(self.wake_channel, line(card, details), wake=True, view=view,
                                           embed=self.dressed("approval", card, extra, details,
                                                              approval_id=approval_id, expires_at=expires_at))
        self.controller.state.set(f"approval:{approval_id}", {
            "message_id": message.id, "channel_id": message.channel.id, "expires_at": expires_at,
        })

    async def close_approval(self, approval_id: str, row: dict, decision: str):
        message = await (await self.channel(row["channel_id"])).fetch_message(row["message_id"])
        embed = embeds.decided(first_embed(message), decision, row.get("decided_by"))
        await message.edit(content=f"Approval {approval_id}: {decision}", view=None, embed=embed)
