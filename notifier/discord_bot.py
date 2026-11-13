import asyncio
import re
import time
from collections.abc import Sequence

import discord
import httpx

from brain.redact import redact
from notifier.state import NotifierState
from pydantic import ValidationError

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
                json={"decision": decision, "decided_by": user_id}, timeout=10,
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
        super().__init__(label="Acknowledge", custom_id=f"ack:{incident_id}")
        self.incident_id, self.controller = incident_id, controller

    async def callback(self, interaction: discord.Interaction):
        result = await self.controller.acknowledge(self.incident_id, str(interaction.user.id))
        await interaction.response.send_message(result, ephemeral=True)
        if result.startswith("acknowledged") and interaction.message:
            self.disabled = True
            await interaction.message.edit(view=self.view)


class AckView(discord.ui.View):
    def __init__(self, incident_id: str, controller: ApprovalController):
        super().__init__(timeout=None)
        self.add_item(AckButton(incident_id, controller))


class ApprovalButton(discord.ui.Button):
    def __init__(self, approval_id: str, decision: str, label: str,
                 controller: ApprovalController):
        super().__init__(label=label, custom_id=f"approval:{approval_id}:{decision}")
        self.approval_id, self.decision, self.controller = approval_id, decision, controller

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.controller.decide(self.approval_id, str(interaction.user.id),
                                                  self.decision)
        except httpx.HTTPError:
            result = "gateway unavailable; decision not confirmed"
        await interaction.followup.send(result, ephemeral=True)
        if result in {"approved", "rejected", "expired", "already decided"}:
            if self.view:
                for item in self.view.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
            if interaction.message:
                await interaction.message.edit(content=f"Approval {self.approval_id}: {result}",
                                               view=self.view)


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

    async def send_text(self, channel_id: int, text: str, *, wake: bool = False, view=None,
                        embed: discord.Embed | None = None):
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            raise ValueError("Discord channel cannot receive messages")
        mentions = discord.AllowedMentions(everyone=False, users=False,
                                          roles=[discord.Object(id=self.role_id)] if wake else False)
        prefix = f"<@&{self.role_id}> " if wake else ""
        if embed is not None:
            return await channel.send(prefix + redact(text)[:1900], allowed_mentions=mentions, view=view,
                                      embed=embed)
        return await channel.send(prefix + redact(text)[:1900], allowed_mentions=mentions, view=view)

    # cards from before embeds (old events, re-pages) have no fields: send their text as before
    async def fyi(self, card: Card, receipt_url: str) -> None:
        if not card.fields:
            await self.send_text(self.fyi_channel, f"{card.text}\n{receipt_url}")
            return
        await self.send_text(self.fyi_channel, card.headline, embed=embed_of(card, url=receipt_url))

    async def wake(self, card: Card, briefing: str) -> int | None:
        view = AckView(card.incident_id, self.controller)
        if not card.fields:
            message = await self.send_text(self.wake_channel, f"{card.text}\n{briefing}", wake=True, view=view)
        else:
            note = [("Update", NOTES[briefing])] if briefing in NOTES else []
            message = await self.send_text(self.wake_channel, card.headline, wake=True, view=view,
                                           embed=embed_of(card, note))
        return message.id

    async def ticket(self, card: Card) -> None:
        if not card.fields:
            await self.send_text(self.tickets_channel, card.text)
            return
        await self.send_text(self.tickets_channel, card.headline, embed=embed_of(card))

    async def request_approval(self, approval_id: str, card: Card, diff: str,
                               forecast: str, expires_at: float) -> None:
        if self.controller.state.get(f"approval:{approval_id}"):
            return
        view = ApprovalView(approval_id, self.controller)
        if not card.fields:
            message = await self.send_text(self.wake_channel,
                                           f"{card.text}\nDiff: {diff[:500]}\nForecast: {forecast}\n"
                                           f"Expires: <t:{int(expires_at)}:R>", wake=True, view=view)
        else:
            extra = [("Side effects", forecast), ("Exact change", f"```{diff.replace('`', '')[:900]}```"),
                     ("Expires", f"<t:{int(expires_at)}:R>")]
            message = await self.send_text(self.wake_channel, card.headline, wake=True, view=view,
                                           embed=embed_of(card, extra))
        self.controller.state.set(f"approval:{approval_id}", {
            "message_id": message.id, "channel_id": message.channel.id, "expires_at": expires_at,
        })

    async def close_approval(self, approval_id: str, row: dict, decision: str):
        channel = self.get_channel(row["channel_id"]) or await self.fetch_channel(row["channel_id"])
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            raise ValueError("Discord channel cannot receive messages")
        message = await channel.fetch_message(row["message_id"])
        await message.edit(content=f"Approval {approval_id}: {decision}", view=None)
