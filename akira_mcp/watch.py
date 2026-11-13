# live tail of the gateway bus, one plain line per event, for a terminal or Claude Code's Monitor tool.
# Survives a gateway restart: it reconnects from the last seq it printed.
import sys
import time
from collections.abc import Callable

import httpx

from chaos import shell

RETRY_S = 5


def start_seq(gateway_url: str) -> int:
    return int(httpx.get(f"{gateway_url}/events/log", params={"after": 0, "limit": 1}, timeout=10).json()["last_seq"])


def run(gateway_url: str, after: int | None = None, incident: str | None = None,
        out: Callable[[str], None] = lambda s: print(s, flush=True), forever: bool = True) -> int:
    down = False
    while True:
        try:
            if after is None:
                after = start_seq(gateway_url)
            out(f"watching {gateway_url}/events after seq {after}" + (f" for {incident}" if incident else ""))
            for record in shell.stream_events(after):
                after = record["seq"]
                if incident and (record.get("event") or {}).get("incident_id") != incident:
                    continue
                out(f"#{record['seq']} " + shell.watch_line(record))
            down = False
        except KeyboardInterrupt:
            return 0
        except (httpx.HTTPError, ValueError, KeyError) as e:
            if not down:  # once per outage, so a Monitor sees it without a flood
                out(f"event stream lost ({type(e).__name__}); retrying every {RETRY_S} s")
                down = True
        if not forever:
            return 1 if down else 0
        try:
            time.sleep(RETRY_S)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(run(shell.GATEWAY))
