# company runbooks (config/runbooks.yaml): code matches them; the LLM reads them; the gateway enforces hard rules
from typing import Any, get_args

from schemas import config
from schemas.models import Pattern, Tool

MATCH_KEYS = {"pattern", "services", "tools", "change_kinds", "evidence"}
ENTRY_KEYS = {"id", "title", "owner", "severity", "match", "steps", "require_approval", "forbid_tools"}
SEVERITIES = {"SEV-1", "SEV-2", "SEV-3", "SEV-4"}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else [value]


# load + check once at start; a typo in a policy file must fail loud, not silently match nothing
def load(root: str = "config") -> list[dict]:
    books = config.load("runbooks", root).get("runbooks") or []
    seen: set[str] = set()
    for rb in books:
        name = rb.get("id", "?")
        if bad := set(rb) - ENTRY_KEYS:
            raise ValueError(f"runbook {name}: unknown keys {sorted(bad)}")
        if not rb.get("id") or not rb.get("title") or not rb.get("steps"):
            raise ValueError(f"runbook {name}: needs id, title and steps")
        if rb["id"] in seen:
            raise ValueError(f"runbook {name}: duplicate id")
        seen.add(rb["id"])
        if rb.get("severity") is not None and rb["severity"] not in SEVERITIES:
            raise ValueError(f"runbook {name}: severity must be one of {sorted(SEVERITIES)}")
        match = rb.get("match") or {}
        if bad := set(match) - MATCH_KEYS:
            raise ValueError(f"runbook {name}: unknown match keys {sorted(bad)}")
        if bad := set(_as_list(match.get("pattern", []))) - set(get_args(Pattern)):
            raise ValueError(f"runbook {name}: unknown pattern {sorted(bad)}")
        if bad := set(_as_list(match.get("tools", [])) + rb.get("forbid_tools", [])) - set(get_args(Tool)):
            raise ValueError(f"runbook {name}: unknown tools {sorted(bad)}")
        if "evidence" in match and (rb.get("require_approval") or rb.get("forbid_tools")):
            raise ValueError(f"runbook {name}: an evidence match is advice only; the gateway can't see evidence")
    return books


# every runbook whose given match keys all hold, file order. evidence=None (the gateway) never matches
# an evidence-keyed runbook
def match(books: list[dict], pattern: str | None, service: str | None, tool: str | None,
          change_kind: str | None, evidence: str | None = None) -> list[dict]:
    out = []
    for rb in books:
        m = rb.get("match") or {}
        if "pattern" in m and pattern not in _as_list(m["pattern"]):
            continue
        if "services" in m and service not in m["services"]:
            continue
        if "tools" in m and tool not in m["tools"]:
            continue
        if "change_kinds" in m and change_kind not in m["change_kinds"]:
            continue
        if "evidence" in m and (evidence is None or not any(w.lower() in evidence.lower() for w in m["evidence"])):
            continue
        out.append(rb)
    return out


# hard rules over all matches, strictest wins: (runbook ids that require approval, id that forbids `tool`)
def hard_rules(matched: list[dict], tool: str | None) -> tuple[list[str], str | None]:
    ask = [rb["id"] for rb in matched if rb.get("require_approval")]
    forbid = next((rb["id"] for rb in matched if tool in (rb.get("forbid_tools") or [])), None)
    return ask, forbid


# compact form for event payloads, cards and the prompt
def brief(rb: dict) -> dict:
    return {"id": rb["id"], "title": rb["title"], "owner": rb.get("owner"), "severity": rb.get("severity"),
            "steps": list(rb["steps"]),
            "require_approval": bool(rb.get("require_approval")), "forbid_tools": list(rb.get("forbid_tools") or [])}
