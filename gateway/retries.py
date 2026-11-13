# retry after a clean undo (§6.4.11): may the agent try another fix, ask the brain, page when it goes quiet. Methods of Gateway (gateway/checklist.py binds them)
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import httpx

from gateway import policy
from schemas import auth
from schemas.models import ActionRequest

if TYPE_CHECKING:
    from gateway.checklist import Gateway

log = logging.getLogger("gateway")


# why a fix was undone -> may the agent try another one? Blind monitoring proves nothing, so no retry on it
RETRY_REASONS = ("severity rose after the action", "did not recover", "harm check failed")


RETRY_DEADLINE_S = 300.0  # brain agent run is capped at 150 s; past this the brain is lost, page a human


# gateway -> brain "try another fix" call; (accepted, why not)
def brain_retry(http: httpx.AsyncClient, brain_url: str) -> Callable[[dict], Awaitable[tuple[bool, str]]]:
    async def ask(body: dict) -> tuple[bool, str]:
        r = await http.post(f"{brain_url}/incidents/{body['incident']['id']}/retry", json=body, timeout=5,
                            headers=auth.headers())
        if r.status_code == 202:
            return True, ""
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = None
        return False, f"brain refused the retry: {detail or r.status_code}"
    return ask


# why the agent may not try another fix now; None = it may

def retry_blocker(self: "Gateway", incident_id: str) -> str | None:
    with self.lock:
        used = policy.usage(self.conn, incident_id, self.clock())
        waiting = self.conn.execute("SELECT COUNT(*) FROM approvals WHERE incident_id=? AND state='pending'",
                                    (incident_id,)).fetchone()[0]
    b = self.policy["budgets"]
    if used["incident"] >= self.max_tries:
        return f"all {self.max_tries} fixes tried"
    hour = 0 if self.rehearsal else used["hour"]
    if used["incident"] >= b["max_actions_per_incident"] or hour >= b["max_actions_per_hour"]:
        return "action budget used up"
    if waiting:  # a follow-up (raise_limit) still waits for a person: they are already involved
        return "another approval for this incident is waiting for a person"
    return None


# grant the retry, then ask the brain for the next fix; None = the brain took it, else why not

async def start_retry(self: "Gateway", action: ActionRequest, row: dict, attempt: int) -> str | None:
    assert self.request_retry is not None
    failed = self.tries.get(action.incident_id, [])
    self.retry_grants[action.incident_id] = (self.clock(), attempt)
    body = {"incident": self.card_incident(row, action.target).model_dump(mode="json"), "attempt": attempt,
            "max_attempts": self.max_tries, "failed": failed}
    try:
        ok, why = await self.request_retry(body)
    except (httpx.HTTPError, ValueError) as e:
        ok, why = False, f"brain unreachable ({type(e).__name__})"
    if ok:
        log.info("incident %s: fix %s failed, brain asked for fix %s of %s", action.incident_id, attempt - 1,
                 attempt, self.max_tries)
        return None
    self.retry_grants.pop(action.incident_id, None)
    log.warning("incident %s: no retry: %s", action.incident_id, why)
    return why


# a granted retry the brain never answered (crash, restart): page instead of waiting for the max age

async def retry_timeouts(self: "Gateway") -> int:
    now, done = self.clock(), 0
    # a gateway restart forgot its grants: watch those incidents from now; their next fix is no retry (asks)
    with self.lock:
        orphans = [r[0] for r in self.conn.execute("SELECT id FROM incidents WHERE state='replanning'")]
    for incident_id in orphans:
        self.retry_grants.setdefault(incident_id, (now, None))
    for incident_id, (granted_at, _) in list(self.retry_grants.items()):
        row = self.incident(incident_id)
        if row is None or row.get("state") != "replanning":
            self.retry_grants.pop(incident_id, None)  # the brain escalated itself, or a fix is running
            continue
        if now - granted_at < RETRY_DEADLINE_S:
            continue
        self.retry_grants.pop(incident_id, None)
        await self.stop({"incident_id": incident_id, "target": row.get("culprit"), "pattern": row.get("pattern")},
                        row, [], "retry", "escalated",
                        f"the brain sent no new fix within {RETRY_DEADLINE_S:.0f} s of the retry; look by hand",
                        sent_by=("gateway", "retry deadline"))
        done += 1
    return done
