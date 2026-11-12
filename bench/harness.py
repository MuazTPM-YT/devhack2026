import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from gateway.client import read_events

SCENARIOS = {
    "bad-deploy": ("recent_change", False),
    "broken-config": ("recent_change", False),
    "memory-leak": ("resource", True),
    "datastore-down": ("protected", True),
}
TERMINAL = {"incident_resolved", "escalated", "handed_off"}


@dataclass
class TrialResult:
    scenario: str
    started_at: float
    outcome: str
    incident_id: str | None = None
    detect_s: float | None = None
    diagnose_s: float | None = None
    recover_s: float | None = None
    diagnosis_correct: bool | None = None
    wake: bool = False
    should_wake: bool = False
    blocked: int = 0
    usage: dict[str, float] | None = None
    source: str = "rehearsal"
    tier: str | None = None
    failed_customer_requests: int | None = None
    harm_clean: bool | None = None
    prediction_held: bool | None = None
    forecast_s: float | None = None
    actual_added_s: float | None = None
    error: str | None = None


class TrialServices(Protocol):
    async def reset(self) -> None: ...
    async def wait_healthy(self) -> None: ...
    async def inject(self, scenario: str) -> dict[str, Any]: ...
    async def observe(self, injection: dict[str, Any], rehearsal: bool) -> list[dict[str, Any]]: ...


class Harness:
    def __init__(self, services: TrialServices, output: Path, rehearsal: bool = False):
        self.services, self.output, self.rehearsal = services, output, rehearsal

    async def run(self, scenarios: list[str], repetitions: int = 10) -> list[TrialResult]:
        results = []
        for scenario in scenarios:
            if scenario not in SCENARIOS:
                raise ValueError(f"Unsupported scenario: {scenario}")
            for _ in range(repetitions):
                result = TrialResult(scenario, time.time(), "failed", should_wake=SCENARIOS[scenario][1])
                try:
                    await self.services.reset()
                    await self.services.wait_healthy()
                    injection = await self.services.inject(scenario)
                    result.started_at = float(injection["ts"])
                    result.should_wake = injection.get("should_wake", result.should_wake)
                    records = await self.services.observe(injection, self.rehearsal)
                    for record in records:
                        event, ts = record["event"], record["ts"]
                        kind, payload = event["type"], event.get("payload", {})
                        result.incident_id = event.get("incident_id") or result.incident_id
                        elapsed = max(0.0, ts - result.started_at)
                        if kind == "incident_opened":
                            result.detect_s = elapsed
                        elif kind == "diagnosis_ready":
                            result.diagnose_s = elapsed
                            if injection.get("target") and payload.get("culprit"):
                                result.diagnosis_correct = (
                                    payload.get("pattern") == SCENARIOS[scenario][0]
                                    and payload["culprit"] == injection["target"]
                                )
                        elif kind == "llm_called":
                            usage = result.usage or {}
                            for key, value in payload.get("usage", {}).items():
                                if isinstance(value, (int, float)):
                                    usage[key] = usage.get(key, 0) + value
                            result.usage = usage
                        elif kind in {"approval_requested", "escalated"}:
                            result.wake = True
                        elif kind == "blocked":
                            result.blocked += 1
                        for field in ("tier", "failed_customer_requests", "harm_clean",
                                      "prediction_held", "forecast_s", "actual_added_s"):
                            if field in payload:
                                setattr(result, field, payload[field])
                        if kind in TERMINAL:
                            result.outcome = kind
                            if kind == "incident_resolved":
                                result.recover_s = elapsed
                    if result.outcome == "failed":
                        result.error = "missing_terminal_event"
                except (httpx.HTTPError, TimeoutError, ValueError, KeyError) as error:
                    result.error = type(error).__name__
                self.output.parent.mkdir(parents=True, exist_ok=True)
                with self.output.open("a") as stream:
                    stream.write(json.dumps(result.__dict__, sort_keys=True) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                results.append(result)
        return results


class HttpTrialServices:
    def __init__(self, client: httpx.AsyncClient, gateway_url: str, observer_url: str, chaos_url: str,
                 stable_s: float = 60, timeout_s: float = 300):
        self.client, self.gateway_url = client, gateway_url.rstrip("/")
        self.observer_url, self.chaos_url = observer_url.rstrip("/"), chaos_url.rstrip("/")
        self.stable_s, self.timeout_s = stable_s, timeout_s

    async def reset(self):
        response = await self.client.post(f"{self.chaos_url}/chaos/reset", timeout=self.timeout_s)
        response.raise_for_status()

    async def wait_healthy(self):
        stable_since: float | None = None
        async with asyncio.timeout(self.timeout_s):
            while True:
                response = await self.client.get(f"{self.observer_url}/health/now")
                response.raise_for_status()
                healthy = response.json()["severity"] == 0
                stable_since = (stable_since or time.monotonic()) if healthy else None
                if stable_since is not None and time.monotonic() - stable_since >= self.stable_s:
                    return
                await asyncio.sleep(1)

    async def inject(self, scenario):
        response = await self.client.post(f"{self.chaos_url}/chaos/{scenario}")
        response.raise_for_status()
        return response.json()

    async def observe(self, injection, rehearsal):
        records = []
        incident_id = None
        async with asyncio.timeout(self.timeout_s):
            async for record in read_events(self.client, self.gateway_url):
                if record["ts"] < injection["ts"]:
                    continue
                event = record["event"]
                if incident_id is None and event["type"] == "incident_opened":
                    incident_id = event["incident_id"]
                if incident_id is None or event.get("incident_id") != incident_id:
                    continue
                records.append(record)
                if rehearsal and event["type"] == "approval_requested":
                    response = await self.client.post(
                        f"{self.gateway_url}/rehearsal/approvals/{event['payload']['approval_id']}/decide",
                        json={"decision": "approved"},
                    )
                    response.raise_for_status()
                if event["type"] in TERMINAL:
                    if rehearsal:
                        diagnosis: dict[str, Any] = next((item["event"]["payload"] for item in records
                                          if item["event"]["type"] == "diagnosis_ready"), {})
                        expected = {"bad_deploy": "recent_change", "broken_config": "recent_change",
                                    "resource_exhaustion": "resource", "failing_dependency": "protected"}.get(injection.get("type"))
                        matched = (bool(injection.get("target")) and expected is not None
                                   and diagnosis.get("culprit") == injection["target"]
                                   and diagnosis.get("pattern") == expected)
                        response = await self.client.post(
                            f"{self.gateway_url}/rehearsal/ledger",
                            json={"incident_id": incident_id, "diagnosis_correct": matched},
                        )
                        response.raise_for_status()
                    return records
        return records


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=list(SCENARIOS), action="append", required=True)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--rehearsal", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("bench/results.jsonl"))
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    if args.rehearsal and os.environ.get("REHEARSAL_ENABLED") != "true":
        parser.error("Set REHEARSAL_ENABLED=true for rehearsal hooks")
    async with httpx.AsyncClient() as client:
        services = HttpTrialServices(client, os.environ["GATEWAY_URL"], os.environ["OBSERVER_URL"],
                                     os.environ["CHAOS_URL"])
        await Harness(services, args.output, args.rehearsal).run(args.scenario, args.runs)


if __name__ == "__main__":
    asyncio.run(main())
