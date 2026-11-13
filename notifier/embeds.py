# Discord embeds built from the 5-line card (plan §6.6/§6.7.1). Pure: no client, so tests can check them.
# Every string passes redact(); Discord limits (title 256, field 1024, total 6000) are enforced here.
import time
from datetime import datetime, timezone
from typing import Any

import discord

from brain.redact import redact
from schemas.models import Card

GREEN, YELLOW, ORANGE, RED, GREY, TEAL, BLURPLE, DARK_RED = (
    0x2ECC71, 0xF1C40F, 0xE67E22, 0xE74C3C, 0x95A5A6, 0x1ABC9C, 0x5865F2, 0x992D22)
# first match on the card status (a major incident is prefixed "MAJOR INCIDENT: "); MITIGATED before FIXED,
# "MITIGATED, NOT FIXED" holds both words
COLORS = [("MAJOR INCIDENT", DARK_RED), ("MITIGATED", YELLOW), ("FIXED", GREEN), ("NEEDS APPROVAL", ORANGE),
          ("WOKE YOU", RED), ("HANDED OFF", GREY), ("RECOVERED", TEAL), ("NO ACTION", BLURPLE)]
DECISION_COLORS = {"approved": GREEN, "rejected": GREY, "expired": GREY, "acknowledged": BLURPLE}
# who each kind of message is for, shown at the top of the embed
AUDIENCE = {
    "fyi": "For: everyone. No action needed.",
    "wake": "For: on-call. A human must look now.",
    "approval": "For: approvers. Approve or reject before it expires.",
    "ticket": "For: the day team. Follow up in working hours.",
}
CARD_FIELDS = ("Did", "Checked", "Undo", "Evidence")
MAX_TOTAL = 6000


def cut(text: Any, limit: int) -> str:
    text = redact(str(text)).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def color_of(status: str) -> int:
    return next((c for word, c in COLORS if word in status.upper()), BLURPLE)


def mentions(user_ids: set[str] | list[str]) -> str:
    return ", ".join(f"<@{u}>" for u in sorted(user_ids) if u.isdigit()) or "none configured"


# card lines "Name: value" -> {Name: value}; line 1 is the headline
def card_parts(card: Card) -> tuple[str, dict[str, str]]:
    lines = [line for line in card.text.splitlines() if line.strip()]
    head = lines[0] if lines else card.status
    parts: dict[str, str] = {}
    for line in lines[1:]:
        name, sep, value = line.partition(": ")
        if sep and name in ("Why", *CARD_FIELDS):
            parts[name] = value
        else:
            parts["Why"] = f"{parts.get('Why', '')}\n{line}".strip()
    return head, parts


def runbook_text(rb: dict) -> str:
    owner = f" (owner: {rb['owner']})" if rb.get("owner") else ""
    rules = []
    if rb.get("require_approval"):
        rules.append("a human approves every action")
    if rb.get("forbid_tools"):
        rules.append(f"never: {', '.join(rb['forbid_tools'])}")
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(rb.get("steps") or [], 1))
    return f"**{rb.get('id')} {rb.get('title')}**{owner}" + (f"\nRule: {'; '.join(rules)}" if rules else "") + \
        (f"\n{steps}" if steps else "")


def build(kind: str, card: Card, details: dict | None = None, *, briefing: str = "", diff: str = "",
          forecast: str = "", expires_at: float | None = None, approvers: set[str] | None = None,
          receipt_url: str = "", approval_id: str | None = None, now: float | None = None) -> discord.Embed:
    details = details or {}
    head, parts = card_parts(card)
    embed = discord.Embed(title=cut(head, 256), description=cut(parts.get("Why", ""), 4000) or None,
                          color=color_of(card.status),
                          timestamp=datetime.fromtimestamp(time.time() if now is None else now, timezone.utc))
    embed.set_author(name=AUDIENCE.get(kind, AUDIENCE["fyi"]))

    def field(name: str, value: Any, inline: bool = False) -> None:
        if value not in (None, ""):
            embed.add_field(name=name, value=cut(value, 1024), inline=inline)

    # most important first: if the embed runs over 6000 chars, fields are dropped from the end
    if kind == "wake":
        field("Briefing", briefing)
        if details.get("page", 1) > 1:
            field("Page", f"#{details['page']}; re-pages until acknowledged or resolved", inline=True)
    if kind == "approval":
        field("Change", f"```{cut(diff, 900)}```" if diff else "")
        field("Forecast", forecast)
        if expires_at is not None:
            field("Expires", f"<t:{int(expires_at)}:R> (<t:{int(expires_at)}:t>)", inline=True)
        field("Who can approve", mentions(approvers or set()), inline=True)
    for name in ("Did", "Checked"):
        field(name, parts.get(name))
    undo = parts.get("Undo")
    field("Undo", f"`{undo}`" if undo and undo.startswith("kubectl ") else undo)
    if rb := details.get("runbook"):
        field("Runbook", runbook_text(rb))
    field("Seen before", details.get("seen_before"))
    field("Receipt", receipt_url)
    refs = card.evidence_ids or []
    field("Evidence", " ".join(f"`{e}`" for e in refs) if refs else parts.get("Evidence"))
    footer = f"Incident {card.incident_id}" + (f" · Approval {approval_id}" if approval_id else "")
    embed.set_footer(text=cut(footer, 2048))
    while len(embed) > MAX_TOTAL and embed.fields:
        embed.remove_field(len(embed.fields) - 1)
    return embed


# copy of a posted embed with the outcome added: who decided and when (plan §6.6 "edit the message")
def decided(old: discord.Embed | None, outcome: str, by: str | None, now: float | None = None) -> discord.Embed | None:
    if old is None:
        return None
    embed = discord.Embed.from_dict(old.to_dict())
    embed.color = DECISION_COLORS.get(outcome, GREY)
    who = f" by <@{by}>" if by and by.isdigit() else (f" by {cut(by, 100)}" if by else "")
    when = int(time.time() if now is None else now)
    embed.add_field(name="Outcome", value=f"**{outcome}**{who} <t:{when}:R>", inline=False)
    while len(embed) > MAX_TOTAL and len(embed.fields) > 1:
        embed.remove_field(len(embed.fields) - 2)  # keep the outcome, drop the field before it
    return embed
