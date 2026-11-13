import asyncio
import time

import discord
import httpx

from brain.redact import redact
from notifier import embeds
from notifier.state import NotifierState
from pydantic import ValidationError

from schemas import auth
from schemas.models import Card, GatewayDecision


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

    # wake = ping the on-call role in the plain text (embeds never ping); the embed carries the detail
    async def send(self, channel_id: int, embed: discord.Embed, *, wake: bool = False, view=None):
        mentions = discord.AllowedMentions(everyone=False, users=False,
                                          roles=[discord.Object(id=self.role_id)] if wake else False)
        content = f"<@&{self.role_id}> {redact(embed.title or '')}"[:1900] if wake else None
        return await (await self.channel(channel_id)).send(content, embed=embed, allowed_mentions=mentions,
                                                           view=view)

    async def fyi(self, card: Card, receipt_url: str, details: dict | None = None) -> None:
        await self.send(self.fyi_channel, embeds.build("fyi", card, details, receipt_url=receipt_url))

    async def wake(self, card: Card, briefing: str, details: dict | None = None) -> int | None:
        message = await self.send(self.wake_channel, embeds.build("wake", card, details, briefing=briefing),
                                  wake=True, view=AckView(card.incident_id, self.controller))
        return message.id

    async def ticket(self, card: Card, details: dict | None = None) -> None:
        await self.send(self.tickets_channel, embeds.build("ticket", card, details))

    async def request_approval(self, approval_id: str, card: Card, diff: str,
                               forecast: str, expires_at: float, details: dict | None = None) -> None:
        if self.controller.state.get(f"approval:{approval_id}"):
            return
        view = ApprovalView(approval_id, self.controller)
        embed = embeds.build("approval", card, details, diff=diff, forecast=forecast, expires_at=expires_at,
                             approvers=self.controller.approvers, approval_id=approval_id)
        message = await self.send(self.wake_channel, embed, wake=True, view=view)
        self.controller.state.set(f"approval:{approval_id}", {
            "message_id": message.id, "channel_id": message.channel.id, "expires_at": expires_at,
        })

    async def close_approval(self, approval_id: str, row: dict, decision: str):
        message = await (await self.channel(row["channel_id"])).fetch_message(row["message_id"])
        embed = embeds.decided(first_embed(message), decision, row.get("decided_by"))
        await message.edit(content=f"Approval {approval_id}: {decision}", view=None,
                           embed=embed)
