import argparse
import os
import shlex
import sys
import time
from typing import Any

import httpx

# what each fault does to the shop; names match chaos/main.py FAULTS (tests keep the two in sync)
FAULTS: dict[str, str] = {
    "bad-deploy": "payment ships image payment:v2-bad, about 40% of charges fail",
    "broken-config": "checkout points at payment:9999, every order fails",
    "flag-flip": "flag paymentFailure set to 50%",
    "memory-leak": "recommendation cache leak flag on, OOMKilled in about 2 min",
    "datastore-down": "valkey-cart scaled to 0, cart stops",
    "shared-outage": "kafka scaled to 0, checkout errors within 90 s",
}

DEFAULT_CHAOS = "http://127.0.0.1:7004"
DEFAULT_OBSERVER = "http://127.0.0.1:7001"
# reset waits for observer severity 0 held 30 s, up to 300 s, on the server side
RESET_TIMEOUT_S = 420


class CliError(Exception):
    pass


def clock(ts: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts))


def call(method: str, url: str, timeout: float = 30, **kw: Any) -> Any:
    try:
        r = httpx.request(method, url, timeout=timeout, **kw)
    except httpx.TimeoutException:
        raise CliError(f"{url} timed out after {timeout:.0f} s") from None
    except httpx.HTTPError as e:
        raise CliError(f"cannot reach {url} ({type(e).__name__}); is the service running?") from None
    try:
        body = r.json()
    except ValueError:
        body = None
    if r.is_error:
        detail = body.get("detail") if isinstance(body, dict) else r.text[:300]
        raise CliError(f"{r.status_code} from {url}: {detail}")
    return body


def truth_line(e: dict[str, Any]) -> str:
    kind = e.get("type", "?")
    if kind == "reset":
        restored = e.get("restored") or []
        detail = f"restored {', '.join(restored)}" if restored else "nothing to restore"
        if e.get("healthy") is not None:
            detail += f" · healthy {'yes' if e['healthy'] else 'NO (timed out)'}"
    elif kind == "judge_kubectl":
        detail = "kubectl " + shlex.join(e.get("args") or []) + ("" if e.get("ok", True) else " (failed)")
    else:
        detail = " · ".join(str(e[k]) for k in ("target", "key") if e.get(k))
    return f"{clock(e['ts'])}  {kind:<15} {detail}" if "ts" in e else f"{kind} {detail}"


def cmd_list(args: argparse.Namespace) -> int:
    for name, what in FAULTS.items():
        print(f"{name:<15} {what}")
    return 0


def cmd_inject(args: argparse.Namespace) -> int:
    entry = call("POST", f"{args.chaos_url}/chaos/{args.fault}")
    print(f"injected  {truth_line(entry)}")
    print("watch the agent at http://localhost:3000; undo with: uv run python -m chaos.cli reset")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    print("resetting: restore snapshot, then wait for severity 0 (can take a few minutes)…", flush=True)
    entry = call("POST", f"{args.chaos_url}/chaos/reset", timeout=RESET_TIMEOUT_S)
    print(truth_line(entry))
    return 1 if entry.get("healthy") is False else 0


def cmd_kubectl(args: argparse.Namespace) -> int:
    words = args.args[1:] if args.args[:1] == ["--"] else args.args
    if not words:
        raise CliError("give kubectl arguments, e.g. kubectl scale deploy/cart --replicas=0")
    res = call("POST", f"{args.chaos_url}/chaos/kubectl", json={"command": shlex.join(words)})
    out = res.get("output") or "(no output)"
    print(out.rstrip(), file=sys.stdout if res.get("ok") else sys.stderr)
    if res.get("recorded"):
        print("(logged as ground truth)")
    return 0 if res.get("ok") else 1


def cmd_status(args: argparse.Namespace) -> int:
    h = call("GET", f"{args.observer_url}/health/now")
    services: dict[str, dict[str, Any]] = h.get("services") or {}
    bad = sorted(s for s, v in services.items() if v.get("unhealthy"))
    print(f"severity {h.get('severity')} at {clock(h['ts'])} · {len(bad)} of {len(services)} services unhealthy")
    for name in sorted(services, key=lambda s: (s not in bad, s)):
        v = services[name]
        err = "–" if v.get("err_ratio") is None else f"{v['err_ratio'] * 100:.1f}%"
        p95 = "–" if v.get("p95_ms") is None else f"{v['p95_ms']:.0f} ms"
        state = "UNHEALTHY" if v.get("unhealthy") else ("breaching" if v.get("breaching") else "ok")
        print(f"  {name:<18} {state:<10} err {err:>6}  p95 {p95:>8}  bad pods {v.get('bad_pods', 0)}")
    return 0


def cmd_truth(args: argparse.Namespace) -> int:
    entries = call("GET", f"{args.chaos_url}/chaos/ground-truth")
    for e in entries[-args.last:]:
        print(truth_line(e))
    if not entries:
        print("nothing injected yet")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="uv run python -m chaos.cli",
        description="Break the shop and watch the agent fix it. Every change goes through the chaos "
                    "panel (:7004) so it is logged as ground truth.")
    p.add_argument("--chaos-url", default=os.environ.get("CHAOS_URL", DEFAULT_CHAOS),
                   help="chaos panel (env CHAOS_URL, default %(default)s)")
    p.add_argument("--observer-url", default=os.environ.get("OBSERVER_URL", DEFAULT_OBSERVER),
                   help="observer, for status (env OBSERVER_URL, default %(default)s)")
    sub = p.add_subparsers(dest="command", required=True, metavar="command")
    sub.add_parser("list", help="list the faults you can inject").set_defaults(run=cmd_list)
    inject = sub.add_parser("inject", help="inject one fault; it stays until reset")
    inject.add_argument("fault", choices=list(FAULTS), metavar="fault", help=", ".join(FAULTS))
    inject.set_defaults(run=cmd_inject)
    sub.add_parser("reset", help="undo every fault and wait until the shop is healthy").set_defaults(run=cmd_reset)
    # its arguments are split off in main(), so kubectl flags like -n never reach argparse
    sub.add_parser("kubectl", help="run kubectl as admin, e.g. kubectl -n shop scale deploy/cart --replicas=0 "
                                   "(changes are logged)").set_defaults(run=cmd_kubectl)
    sub.add_parser("status", help="current severity and per-service health").set_defaults(run=cmd_status)
    truth = sub.add_parser("truth", help="what was really broken and when")
    truth.add_argument("--last", type=int, default=15, help="entries to show, 0 = all (default %(default)s)")
    truth.set_defaults(run=cmd_truth)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    rest: list[str] = []
    if "kubectl" in argv:
        at = argv.index("kubectl") + 1
        argv, rest = argv[:at], argv[at:]
    args = parser().parse_args(argv)
    args.args = rest
    args.chaos_url = args.chaos_url.rstrip("/")
    args.observer_url = args.observer_url.rstrip("/")
    try:
        return int(args.run(args))
    except CliError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
