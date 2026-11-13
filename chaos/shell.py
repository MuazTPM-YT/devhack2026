import json
import os
import shlex
import shutil
import sys
import threading
import time
from collections.abc import Callable, Iterable
from typing import Any

import httpx
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from chaos import cli
from chaos.term import BAD, MUTE, OK, OXBLOOD, PAPER, ROSE, WARN, gradient, paint, tag

GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:7003").rstrip("/")
OBSERVER = os.environ.get("OBSERVER_URL", cli.DEFAULT_OBSERVER).rstrip("/")
UI = "http://localhost:3000/live"

# "ANSI Shadow" letters for A K I R A
LETTERS = {
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "K": ["██╗  ██╗", "██║ ██╔╝", "█████╔╝ ", "██╔═██╗ ", "██║  ██╗", "╚═╝  ╚═╝"],
    "I": ["██╗", "██║", "██║", "██║", "██║", "╚═╝"],
    "R": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝"],
}
WORD = "AKIRA"

# name, argument hint, what it does; the dropdown shows all three
COMMANDS: list[tuple[str, str, str]] = [
    ("/inject", "<fault>", "break the shop with one fault; it stays until /reset"),
    ("/watch", "", "stream what Akira does, step by step (Ctrl+C to stop)"),
    ("/status", "", "severity and per-service health from the observer"),
    ("/reset", "", "undo every fault and wait until the shop is healthy"),
    ("/faults", "", "list the faults you can inject"),
    ("/truth", "[n]", "what was really broken and when (last n, default 15)"),
    ("/kubectl", "<args>", "run kubectl as admin, e.g. /kubectl -n shop get pods"),
    ("/help", "", "show these commands"),
    ("/clear", "", "clear the screen"),
    ("/quit", "", "leave the shell (Ctrl+D works too)"),
]
NAMES = [c[0] for c in COMMANDS]

STYLE = Style.from_dict({
    "prompt": "#c0564b bold",
    "completion-menu": "bg:#24211d #f3f0e9",
    "completion-menu.completion": "bg:#24211d #f3f0e9",
    "completion-menu.completion.current": "bg:#5b1d18 #f1e4e1 bold",
    "completion-menu.meta.completion": "bg:#24211d #b9b1a2",
    "completion-menu.meta.completion.current": "bg:#5b1d18 #f1e4e1",
    "scrollbar.background": "bg:#3a352f",
    "scrollbar.button": "bg:#b98f86",
    "bottom-toolbar": "noreverse bg:#1c1a17 #b9b1a2",
    "bottom-toolbar.ok": "#5faa6e",
    "bottom-toolbar.bad": "#e0604f",
    "bottom-toolbar.warn": "#d99a1e",
    "bottom-toolbar.dim": "#6b655b",
    "bottom-toolbar.brand": "#c0564b bold",
})


def banner(width: int) -> list[str]:
    rows = ["".join(LETTERS[ch][r] for ch in WORD) for r in range(6)]
    if width < len(rows[0]) + 2:  # narrow terminal: a one-line mark instead of clipped art
        return [paint("AKIRA", fg=OXBLOOD, bold=True)]
    span = len(rows[0]) - 1
    return ["".join(paint(c, fg=gradient(i / span)) if c != " " else c for i, c in enumerate(row)) for row in rows]


def intro() -> str:
    tips = [
        f"Type {paint('/', fg=ROSE, bold=True)} to see every command; ↑ ↓ to pick, Tab or Enter to fill it in.",
        f"{paint('/inject bad-deploy', fg=ROSE, bold=True)} breaks payment. Watch the fix at {paint(UI, fg=ROSE)}.",
        f"{paint('/watch', fg=ROSE, bold=True)} streams every step here; approvals arrive in Discord {paint('#wake', fg=ROSE)}.",
        f"{paint('/reset', fg=ROSE, bold=True)} puts the shop back. One fault at a time.",
    ]
    lines = ["", *banner(shutil.get_terminal_size((100, 30)).columns), "",
             paint("Akira chaos shell", fg=PAPER, bold=True) + paint(" · break the shop, watch the agent fix it", fg=MUTE),
             "", paint("Tips for getting started:", fg=PAPER)]
    lines += [f"{i}. {t}" for i, t in enumerate(tips, 1)]
    return "\n".join(lines) + "\n"


class SlashCompleter(Completer):
    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        if " " not in text:
            for name, hint, what in COMMANDS:
                if name.startswith(text):
                    yield Completion(name, start_position=-len(text), display=f"{name} {hint}".strip(), display_meta=what)
            return
        cmd, _, arg = text.partition(" ")
        if cmd == "/inject" and " " not in arg:
            for fault, what in cli.FAULTS.items():
                if fault.startswith(arg):
                    yield Completion(fault, start_position=-len(arg), display_meta=what)


# gateway and observer state for the status bar, polled off the prompt thread every 3 s
class Health:
    def __init__(self) -> None:
        self.gateway: bool | None = None
        self.severity: float | None = None
        self.observer: bool | None = None
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while True:
            try:
                self.gateway = httpx.get(f"{GATEWAY}/health", timeout=1.5).is_success
            except httpx.HTTPError:
                self.gateway = False
            try:
                r = httpx.get(f"{OBSERVER}/health/now", timeout=1.5)
                self.observer, self.severity = r.is_success, r.json().get("severity") if r.is_success else None
            except (httpx.HTTPError, ValueError):
                self.observer, self.severity = False, None
            time.sleep(3)

    def toolbar(self) -> FormattedText:
        def dot(state: bool | None) -> tuple[str, str]:
            return ("class:bottom-toolbar.dim", "○") if state is None else \
                (("class:bottom-toolbar.ok", "●") if state else ("class:bottom-toolbar.bad", "●"))
        sev = self.severity
        sev_style = "class:bottom-toolbar.dim" if sev is None else ("class:bottom-toolbar.warn" if sev else "class:bottom-toolbar.ok")
        return FormattedText([
            ("class:bottom-toolbar.brand", " akira "), ("", f" {os.path.basename(os.getcwd())}   "),
            dot(self.gateway), ("", " gateway   "), dot(self.observer), ("", " observer   "),
            (sev_style, f"severity {'–' if sev is None else sev}"),
            ("class:bottom-toolbar.dim", "   / for commands · Ctrl+D to quit "),
        ])


# --- /watch ---------------------------------------------------------------------------------------

def _s(v: Any) -> str:
    return str(v) if v not in (None, "") else "?"


# one coloured line per bus event; mirrors ui/lib/flow.ts describe()
def describe(kind: str, p: dict[str, Any]) -> tuple[str, str]:
    if kind == "incident_opened":
        return "warn", f"incident opened · {', '.join(p.get('unhealthy') or [])} · severity {_s(p.get('severity'))}"
    if kind == "alerts_grouped":
        return "warn", f"alert folded in · {', '.join(p.get('unhealthy') or [])}"
    if kind == "culprit_found":
        how = "from error traces" if p.get("from_traces") else "deepest unhealthy service"
        return "info", f"culprit {_s(p.get('culprit'))} ({how}); victims {', '.join(p.get('victims') or []) or 'none'}"
    if kind == "major_incident":
        top = (p.get("ranked") or [{}])[0]
        return "warn", f"major incident · shared cause {_s(top.get('target'))}"
    if kind == "bundle_built":
        return "info", "evidence bundle · " + " · ".join(f"{p.get(k, 0)} {k}" for k in ("changes", "metrics", "traces", "events", "logs"))
    if kind == "rule_matched":
        tools = p.get("tools") or []
        return ("info" if tools else "warn"), f"rule {_s(p.get('pattern'))} → {', '.join(tools) or 'no safe action'}"
    if kind == "injection_quarantined":
        return "warn", "log line quarantined (looked like an instruction)"
    if kind == "llm_called":
        if p.get("error"):
            return "bad", f"model call failed · {p['error']}"
        if p.get("cached"):
            return "info", "used cached diagnosis"
        tokens = (p.get("usage") or {}).get("total_tokens")
        return "info", f"model answered · {_s(p.get('model'))}" + (f" · {tokens} tokens" if tokens else "")
    if kind == "diagnosis_ready":
        return "info", f"diagnosis {_s(p.get('pattern'))} on {_s(p.get('culprit'))}"
    if kind == "checklist_step":
        name = _s(p.get("name")).replace("_", " ")
        reason = f" · {p['reason']}" if p.get("reason") else ""
        if p.get("passed"):
            return "ok", f"gate passed: {name}{reason}"
        return ("warn" if p.get("name") in ("trust_gate", "approval") else "bad"), f"gate stopped: {name}{reason}"
    if kind == "approval_requested":
        return "warn", f"asked a human in Discord #wake · {_s(p.get('diff'))}"
    if kind == "approval_decided":
        d = _s(p.get("decision"))
        return ("ok" if d == "approved" else "bad"), f"approval {d}"
    if kind == "action_executed":
        return "ok", f"executed {_s(p.get('tool'))} on {_s(p.get('target'))} · receipt #{_s(p.get('receipt_id'))}"
    if kind == "verify_tick":
        return ("ok" if p.get("recovered") else "info"), f"health check · severity {_s(p.get('severity'))}" + (" · recovered" if p.get("recovered") else "")
    if kind == "early_abort":
        return "bad", f"early abort · severity {_s(p.get('before'))} → {_s(p.get('severity'))}"
    if kind == "action_undone":
        return "bad", f"undid receipt #{_s(p.get('receipt_id'))} · {_s(p.get('reason'))}"
    if kind == "harm_check":
        return ("ok" if p.get("clean") else "bad"), "harm check " + ("clean" if p.get("clean") else "found side effects")
    if kind == "blocked":
        return "bad", f"blocked by the API server · {_s(p.get('reason'))}"
    if kind in ("incident_resolved", "escalated", "handed_off"):
        card = (p.get("card") or {}).get("text", "")
        first = card.splitlines()[0] if card else ""
        tone = {"incident_resolved": "ok", "handed_off": "warn"}.get(kind, "bad")
        return tone, f"{kind.replace('_', ' ')} · {first or _s(p.get('briefing'))}"
    return "info", kind.replace("_", " ")


TONE_FG = {"ok": OK, "warn": WARN, "bad": BAD, "info": PAPER}
MARK = {"ok": "●", "warn": "▲", "bad": "◆", "info": "·"}


def watch_line(record: dict[str, Any]) -> str:
    ev = record.get("event") or {}
    tone, text = describe(_s(ev.get("type")), ev.get("payload") or {})
    stamp = time.strftime("%H:%M:%S", time.localtime(record.get("ts") or time.time()))
    fg = (130, 205, 140) if tone == "ok" else (240, 120, 105) if tone == "bad" else TONE_FG[tone]
    return f"{paint(stamp, fg=MUTE)}  {paint(MARK[tone], fg=fg, bold=True)} {paint(text, fg=fg if tone != 'info' else PAPER)}"


def stream_events(after: int) -> Iterable[dict[str, Any]]:
    with httpx.stream("GET", f"{GATEWAY}/events", headers={"Last-Event-ID": str(after)},
                      timeout=httpx.Timeout(5, read=45)) as r:
        r.raise_for_status()
        data: list[str] = []
        for line in r.iter_lines():
            if line.startswith("data:"):
                data.append(line[5:].lstrip())
            elif not line and data:
                yield json.loads("\n".join(data))
                data.clear()


# tail the gateway event bus from "now"; the audit record count is the newest seq
def watch(out: Callable[[str], None] = print) -> None:
    try:
        after = int(httpx.get(f"{GATEWAY}/audit/verify", timeout=10).json().get("records", 0))
    except (httpx.HTTPError, ValueError):
        after = 0
    out(paint(f"watching {GATEWAY}/events · Ctrl+C to stop", fg=MUTE))
    current = None
    try:
        for rec in stream_events(after):
            inc = (rec.get("event") or {}).get("incident_id")
            if inc and inc != current:
                current = inc
                out("\n" + paint(f"── incident {inc} ", fg=ROSE, bold=True) + paint("─" * 24, fg=MUTE))
            out(watch_line(rec))
    except KeyboardInterrupt:
        out(paint("stopped watching", fg=MUTE))
    except httpx.HTTPError as e:
        out(tag("error", "bad") + f" event stream: {type(e).__name__}; is the gateway on {GATEWAY}?")


# --- dispatch -------------------------------------------------------------------------------------

def help_text() -> str:
    width = max(len(f"{n} {h}".strip()) for n, h, _ in COMMANDS)
    return "\n".join(f"  {paint(f'{n} {h}'.strip().ljust(width), fg=ROSE, bold=True)}   {w}" for n, h, w in COMMANDS)


# run one line; False means quit
def dispatch(line: str, run_cli: Callable[[list[str]], int] = cli.main, out: Callable[[str], None] = print) -> bool:
    text = line.strip()
    if not text:
        return True
    if not text.startswith("/"):
        out(tag("hint", "warn") + " commands start with /. Type / to see them.")
        return True
    try:
        words = shlex.split(text)
    except ValueError as e:
        out(tag("error", "bad") + f" {e}")
        return True
    cmd, args = words[0], words[1:]
    try:
        if cmd in ("/quit", "/exit"):
            return False
        if cmd == "/help":
            out(help_text())
        elif cmd == "/clear":
            out("\x1b[2J\x1b[H" + intro())
        elif cmd == "/watch":
            watch(out)
        elif cmd == "/faults":
            run_cli(["list"])
        elif cmd == "/inject":
            if not args:
                out(tag("hint", "warn") + " /inject <fault>; Tab after /inject shows them")
            else:
                run_cli(["inject", args[0]])
        elif cmd in ("/status", "/reset"):
            run_cli([cmd[1:]])
        elif cmd == "/truth":
            run_cli(["truth", "--last", args[0]] if args else ["truth"])
        elif cmd == "/kubectl":
            run_cli(["kubectl", *args])
        else:
            near = [n for n in NAMES if n.startswith(cmd[:3])]
            out(tag("error", "bad") + f" unknown command {cmd}" + (f"; did you mean {near[0]}?" if near else "; /help lists them"))
    except SystemExit:
        pass  # argparse already printed why
    except KeyboardInterrupt:
        out(paint("stopped waiting; the chaos panel keeps going on its own", fg=MUTE))
    return True


def run() -> int:
    if not sys.stdin.isatty():
        print("the interactive shell needs a terminal; use e.g. `uv run -m chaos.cli inject bad-deploy`", file=sys.stderr)
        return 2
    print(intro())
    health = Health()
    session: PromptSession[str] = PromptSession(
        history=InMemoryHistory(), completer=SlashCompleter(), complete_while_typing=True, style=STYLE,
        bottom_toolbar=health.toolbar, refresh_interval=3, reserve_space_for_menu=8)
    while True:
        try:
            print(paint("─" * min(shutil.get_terminal_size((100, 30)).columns, 100), fg=(70, 64, 58)))
            line = session.prompt([("class:prompt", "› ")])
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        if not dispatch(line):
            break
    print(paint("bye. the shop keeps whatever state you left it in; /reset next time if needed.", fg=MUTE))
    return 0
