# extras for T's card embeds (notifier/discord_bot.py embed_of): who a message is for, runbook text,
# approver mentions, and the who/when outcome edited onto a decided page. Pure, so tests need no client.
import time

import discord

from brain.redact import redact

DECISION_COLOURS = {"approved": 0x2EA043, "rejected": 0x808890, "expired": 0x808890, "acknowledged": 0x5865F2}
# who each kind of message is for, shown at the top of the embed
AUDIENCE = {
    "fyi": "For: everyone. No action needed.",
    "wake": "For: on-call. A human must look now.",
    "approval": "For: approvers. Approve or reject before it expires.",
    "ticket": "For: the day team. Follow up in working hours.",
}
MAX_TOTAL = 6000


def mentions(user_ids: set[str] | list[str]) -> str:
    return ", ".join(f"<@{u}>" for u in sorted(user_ids) if u.isdigit()) or "none configured"


def runbook_text(rb: dict) -> str:
    sev = f" [{rb['severity']}]" if rb.get("severity") else ""
    owner = f" (owner: {rb['owner']})" if rb.get("owner") else ""
    rules = []
    if rb.get("require_approval"):
        rules.append("a human approves every action")
    if rb.get("forbid_tools"):
        rules.append(f"never: {', '.join(rb['forbid_tools'])}")
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(rb.get("steps") or [], 1))
    return f"**{rb.get('id')} {rb.get('title')}**{sev}{owner}" + (f"\nRule: {'; '.join(rules)}" if rules else "") + \
        (f"\n{steps}" if steps else "")


# copy of a posted embed with the outcome added: who decided and when (plan §6.6 "edit the message")
def decided(old: discord.Embed | None, outcome: str, by: str | None, now: float | None = None) -> discord.Embed | None:
    if old is None:
        return None
    embed = discord.Embed.from_dict(old.to_dict())
    embed.colour = discord.Colour(DECISION_COLOURS.get(outcome, 0x808890))
    who = f" by <@{by}>" if by and by.isdigit() else (f" by {redact(by)[:100]}" if by else "")
    when = int(time.time() if now is None else now)
    embed.add_field(name="Outcome", value=f"**{outcome}**{who} <t:{when}:R>", inline=False)
    while len(embed) > MAX_TOTAL and len(embed.fields) > 1:
        embed.remove_field(len(embed.fields) - 2)  # keep the outcome, drop the field before it
    return embed
