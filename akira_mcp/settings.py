# what the Akira MCP may do, read once at start. A tool group without its secret is a startup error, not a
# runtime surprise; a process without the chaos group never holds the judge's secret.
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from gateway.approvals import REHEARSAL_APPROVER, approvers_from_env
from schemas import auth

TOOLSETS = ("read", "chaos", "approvals")
DEFAULTS = {
    "GATEWAY_URL": "http://127.0.0.1:7003",
    "OBSERVER_URL": "http://127.0.0.1:7001",
    "BRAIN_URL": "http://127.0.0.1:7002",
    "CHAOS_URL": "http://127.0.0.1:7004",
    "NOTIFIER_URL": "http://127.0.0.1:7005",
}


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    gateway_url: str
    observer_url: str
    brain_url: str
    chaos_url: str
    notifier_url: str
    toolsets: frozenset[str]
    operator_id: str | None  # the approver Claude acts for; only with the approvals group
    api_token: bool  # ONCALL_API_TOKEN present: observer /journal reads need it


def url(name: str) -> str:
    value = os.environ.get(name, "").strip() or DEFAULTS[name]
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise SettingsError(f"{name} must be an http(s) URL, got {value!r}")
    return value.rstrip("/")


def toolsets() -> frozenset[str]:
    raw = os.environ.get("AKIRA_MCP_TOOLSETS", "read")
    names = {n.strip().lower() for n in raw.split(",") if n.strip()}
    if bad := sorted(names - set(TOOLSETS)):
        raise SettingsError(f"AKIRA_MCP_TOOLSETS: unknown toolset(s) {bad}; allowed: {', '.join(TOOLSETS)}")
    return frozenset(names | {"read"})


# a Discord user id from the same allowlist the gateway checks; Claude never chooses who it acts for
def operator() -> str:
    value = os.environ.get("AKIRA_OPERATOR_ID", "").strip()
    if not value:
        raise SettingsError("missing required env var(s): AKIRA_OPERATOR_ID (approvals toolset)")
    if not value.isdigit():
        raise SettingsError("AKIRA_OPERATOR_ID must be a Discord user id (digits only)")
    try:
        approvers = approvers_from_env() - {REHEARSAL_APPROVER}
    except RuntimeError as e:
        raise SettingsError(str(e)) from None
    if value not in approvers:
        raise SettingsError("AKIRA_OPERATOR_ID is not in ONCALL_APPROVER_IDS")
    return value


def has_token(env: str) -> bool:
    try:
        auth.token(env)
        return True
    except RuntimeError:
        return False


def load() -> Settings:
    groups = toolsets()
    try:
        if "chaos" in groups:
            auth.token(auth.JUDGE_ENV)
        else:
            os.environ.pop(auth.JUDGE_ENV, None)  # same .env as the judge tooling: drop what we must not hold
        if "approvals" in groups:
            auth.token()
    except RuntimeError as e:
        raise SettingsError(f"{e} (needed by AKIRA_MCP_TOOLSETS={','.join(sorted(groups))})") from None
    return Settings(gateway_url=url("GATEWAY_URL"), observer_url=url("OBSERVER_URL"), brain_url=url("BRAIN_URL"),
                    chaos_url=url("CHAOS_URL"), notifier_url=url("NOTIFIER_URL"), toolsets=groups,
                    operator_id=operator() if "approvals" in groups else None, api_token=has_token(auth.ENV))
