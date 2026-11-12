import asyncio
import time

import discord
import httpx

from brain.redact import redact
from notifier.state import NotifierState
from schemas.models import Card


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
            row.update(decision=decision, decided_by=user_id, decided_at=time.time())
            self.state.set(f"approval:{approval_id}", row)
            return decision


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

    async def send_text(self, channel_id: int, text: str, *, wake: bool = False, view=None):
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            raise ValueError("Discord channel cannot receive messages")
        mentions = discord.AllowedMentions(everyone=False, users=False,
                                          roles=[discord.Object(id=self.role_id)] if wake else False)
        prefix = f"<@&{self.role_id}> " if wake else ""
        return await channel.send(prefix + redact(text)[:1900], allowed_mentions=mentions, view=view)

    async def fyi(self, card: Card, receipt_url: str) -> None:
        await self.send_text(self.fyi_channel, f"{card.text}\n{receipt_url}")

    async def wake(self, card: Card, briefing: str) -> None:
        await self.send_text(self.wake_channel, f"{card.text}\n{briefing}", wake=True)

    async def ticket(self, card: Card) -> None:
        await self.send_text(self.tickets_channel, card.text)

    async def request_approval(self, approval_id: str, card: Card, diff: str,
                               forecast: str, expires_at: float) -> None:
        view = ApprovalView(approval_id, self.controller)
        message = await self.send_text(self.wake_channel,
                                       f"{card.text}\nDiff: {diff[:500]}\nForecast: {forecast}\n"
                                       f"Expires: <t:{int(expires_at)}:R>", wake=True, view=view)
        self.controller.state.set(f"approval:{approval_id}", {
            "message_id": message.id, "channel_id": message.channel.id, "expires_at": expires_at,
        })
