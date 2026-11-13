# extras for T's card embeds (notifier/discord_bot.py embed_of): who a message is for, runbook text,
# approver mentions, and the who/when outcome edited onto a decided page. Pure, so tests need no client.
import time
from datetime import datetime, timezone

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
def decided(old: discord.Embed | None, outcome: str, by: str | None, now: float | None = None,
            via: str | None = None) -> discord.Embed | None:
    if old is None:
        return None
    embed = discord.Embed.from_dict(old.to_dict())
    embed.colour = discord.Colour(DECISION_COLOURS.get(outcome, 0x808890))
    who = f" by <@{by}>" if by and by.isdigit() else (f" by {redact(by)[:100]}" if by else "")
    if via == "akira-mcp":
        who += " via Akira MCP"
    when = int(time.time() if now is None else now)
    embed.add_field(name="Outcome", value=f"**{outcome}**{who} <t:{when}:R>", inline=False)
    while len(embed) > MAX_TOTAL and len(embed.fields) > 1:
        embed.remove_field(len(embed.fields) - 2)  # keep the outcome, drop the field before it
    return embed


# what the reader must do, by message kind; first match on the card status wins
def your_move(kind: str, status: str, expires_at: float | None = None) -> str:
    if kind == "approval":
        when = f" before <t:{int(expires_at)}:t> (<t:{int(expires_at)}:R>)" if expires_at else ""
        return (f"Press Approve or Reject below{when}. If nobody decides, the agent changes nothing "
                "and pages on-call.")
    if kind == "wake":
        return "Look at it now. Press Acknowledge to stop the re-pages."
    if kind == "ticket":
        return "Plan a follow-up in working hours. The service works again, but the cause is not fixed."
    if "TRYING ANOTHER FIX" in status:
        return "Nothing yet. You get a page if every fix fails."
    if "HANDED OFF" in status:
        return "Nothing from the agent. The person who made the change owns the incident now."
    return "Nothing. This is for your information."


PARTS = {"gateway": "Gateway (safety checks)", "verifier": "Verifier (checks the fix)",
         "watchdog": "Watchdog (guards the verifier)", "brain": "Brain (diagnosis)",
         "observer": "Observer (detection)", "notifier": "Notifier"}


def _ago(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60} min {s % 60} s" if s >= 60 else f"{s} s"


# "Origin": the change that started it, who sent this message, live or rehearsal
def origin_text(source: dict | None, started: dict | None, page: int = 1) -> str | None:
    lines = []
    if started:
        if started.get("change"):
            lag = ""
            if isinstance(started.get("change_ts"), (int, float)) and isinstance(started.get("onset_at"), (int, float)):
                gap = started["onset_at"] - started["change_ts"]
                lag = f", {_ago(gap)} before the first errors" if gap >= 0 else ", after the first errors"
            lines.append(f"Started by: {started['change']}, made by {started.get('by') or 'unknown'}{lag}.")
        else:
            lines.append("Started by: no recorded change found before the first errors.")
    if source:
        part = PARTS.get(str(source.get("part")), str(source.get("part")))
        lines.append(f"Sent by: {part}, step: {source.get('step')}. Machine: {source.get('host') or 'unknown'}.")
        mode = source.get("mode")
        if mode == "rehearsal":
            lines.append("Mode: **REHEARSAL**. A bench test run (ONCALL_REHEARSAL=1), not a real outage.")
        elif mode == "live":
            lines.append("Mode: LIVE.")
    if page > 1:
        lines.append(f"Re-sent by the Notifier: page #{page}.")
    return "\n".join(redact(line) for line in lines) or None


def _t(ts: object, style: str = "T") -> str | None:
    return f"<t:{int(ts)}:{style}>" if isinstance(ts, (int, float)) and ts > 0 else None


# "Timeline": first errors, opened, this event; discord renders <t:...> in each reader's own time zone
def timeline_text(started: dict | None, event: dict | None, page: int = 1, now: float | None = None) -> str | None:
    started, event = started or {}, event or {}
    lines = []
    if onset := _t(started.get("onset_at")):
        lines.append(f"First errors: {onset} ({_t(started['onset_at'], 'R')})")
    if opened := _t(started.get("opened_at")):
        lines.append(f"Incident opened: {opened}")
    if at := _t(event.get("ts")):
        label = "First sent" if page > 1 else "This message"
        lines.append(f"{label}: {at} ({_t(event['ts'], 'R')})")
    if page > 1:
        lines.append(f"This re-page: {_t(time.time() if now is None else now)}")
    return "\n".join(lines) or None


# footer ids: look the event up in data/audit.jsonl (scripts/verify_audit.py) by its number
def ids_text(footer: str, event: dict | None, approval_id: str | None = None) -> str:
    parts = [footer] if footer else []
    if (event or {}).get("seq"):
        parts.append(f"Event #{event['seq']}")  # type: ignore[index]
    if approval_id:
        parts.append(f"Approval {approval_id}")
    return " · ".join(parts)


def event_time(event: dict | None) -> datetime | None:
    ts = (event or {}).get("ts")
    return datetime.fromtimestamp(ts, timezone.utc) if isinstance(ts, (int, float)) and ts > 0 else None
