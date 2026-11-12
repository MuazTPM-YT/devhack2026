import argparse
import asyncio
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from gateway.client import read_events
from schemas.models import GatewayDecision

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


class ObservationError(ValueError):
    def __init__(self, reason: str, records: list[dict[str, Any]]):
        super().__init__(reason)
        self.records = list(records)


class TrialServices(Protocol):
    async def reset(self) -> None: ...
    async def wait_healthy(self) -> None: ...
    async def inject(self, scenario: str) -> dict[str, Any]: ...
    async def observe(self, injection: dict[str, Any], rehearsal: bool) -> list[dict[str, Any]]: ...


class Harness:
    def __init__(self, services: TrialServices, output: Path, rehearsal: bool = False):
        self.services, self.output, self.rehearsal = services, output, rehearsal

    def completed_attempts(self) -> dict[str, int]:
        completed: dict[str, int] = {}
        if not self.output.exists():
            return completed
        for number, line in enumerate(self.output.read_text().splitlines(), 1):
            try:
                row = TrialResult(**json.loads(line))
                if row.scenario not in SCENARIOS or row.outcome not in TERMINAL | {"failed"}:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError(f"Invalid resume result at line {number}") from None
            completed[row.scenario] = completed.get(row.scenario, 0) + 1
        return completed

    async def run(self, scenarios: list[str], repetitions: int = 10, *, resume: bool = False) -> list[TrialResult]:
        if self.rehearsal and os.environ.get("ONCALL_REHEARSAL") != "1":
            raise ValueError("Set ONCALL_REHEARSAL=1 for rehearsal hooks")
        if repetitions < 1:
            raise ValueError("repetitions must be positive")
        for scenario in scenarios:
            if scenario not in SCENARIOS:
                raise ValueError(f"Unsupported scenario: {scenario}")
        completed = self.completed_attempts() if resume else {}
        results = []
        for scenario in scenarios:
            remaining = max(0, repetitions - completed.get(scenario, 0)) if resume else repetitions
            for _ in range(remaining):
                result = TrialResult(scenario, time.time(), "failed", should_wake=SCENARIOS[scenario][1])
                records: list[dict[str, Any]] = []
                injection: dict[str, Any] = {}
                try:
                    await self.services.reset()
                    await self.services.wait_healthy()
                    injection = await self.services.inject(scenario)
                    result.started_at = float(injection["ts"])
                    result.should_wake = injection.get("should_wake", result.should_wake)
                    records = await self.services.observe(injection, self.rehearsal)
                except ObservationError as error:
                    records = error.records
                    result.error = str(error)
                except (httpx.HTTPError, TimeoutError, ValueError, KeyError) as error:
                    result.error = type(error).__name__
                measure(result, injection, records)
                if result.outcome == "failed" and result.error is None:
                    result.error = "missing_terminal_event"
                self.output.parent.mkdir(parents=True, exist_ok=True)
                with self.output.open("a") as stream:
                    stream.write(json.dumps(result.__dict__, sort_keys=True) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                completed[scenario] = completed.get(scenario, 0) + 1
                results.append(result)
        return results


def measure(result: TrialResult, injection: dict[str, Any], records: list[dict[str, Any]]) -> None:
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
                    payload.get("pattern") == SCENARIOS[result.scenario][0]
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


class HttpTrialServices:
    def __init__(self, client: httpx.AsyncClient, gateway_url: str, observer_url: str, chaos_url: str,
                 stable_s: float = 60, timeout_s: float = 300, reconnect_s: float = 1):
        self.client, self.gateway_url = client, gateway_url.rstrip("/")
        self.observer_url, self.chaos_url = observer_url.rstrip("/"), chaos_url.rstrip("/")
        if stable_s < 0 or timeout_s <= 0 or reconnect_s < 0:
            raise ValueError("Invalid benchmark timing configuration")
        self.stable_s, self.timeout_s, self.reconnect_s = stable_s, timeout_s, reconnect_s

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

    async def _approve(self, approval_id: str, records: list[dict[str, Any]]) -> None:
        try:
            response = await self.client.post(
                f"{self.gateway_url}/approvals/{approval_id}/decide",
                json={"decision": "approved", "decided_by": "rehearsal-harness"},
            )
            response.raise_for_status()
            decision = GatewayDecision.model_validate(response.json())
        except (httpx.HTTPError, ValueError):
            raise ObservationError("approval_request_failed", records) from None
        if decision.decision != "executed":
            raise ObservationError("Rehearsal approval did not execute", records)

    async def _credit(self, receipt_id: int, records: list[dict[str, Any]], injection: dict[str, Any]) -> None:
        diagnosis: dict[str, Any] = next((item["event"]["payload"] for item in reversed(records)
                                         if item["event"]["type"] == "diagnosis_ready"), {})
        expected = {"bad_deploy": "recent_change", "broken_config": "recent_change",
                    "resource_exhaustion": "resource", "failing_dependency": "protected"}.get(injection.get("type", ""))
        matched = (bool(injection.get("target")) and expected is not None
                   and diagnosis.get("culprit") == injection["target"]
                   and diagnosis.get("pattern") == expected)
        try:
            response = await self.client.post(
                f"{self.gateway_url}/ledger/rehearsal",
                json={"receipt_id": receipt_id, "diagnosis_matched": matched},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise ObservationError("ledger_submission_failed", records) from None

    async def observe(self, injection, rehearsal):
        if rehearsal and os.environ.get("ONCALL_REHEARSAL") != "1":
            raise ValueError("Set ONCALL_REHEARSAL=1 for rehearsal hooks")
        records: list[dict[str, Any]] = []
        incident_id = None
        receipt_id: int | None = None
        cursor = 0
        approvals: set[str] = set()
        try:
            async with asyncio.timeout(self.timeout_s):
                while True:
                    try:
                        async for record in read_events(self.client, self.gateway_url, after=cursor):
                            sequence, ts, event = record["seq"], record["ts"], record["event"]
                            if type(sequence) is not int or sequence < 1:
                                raise ValueError("Invalid event sequence")
                            if not isinstance(ts, (int, float)) or not math.isfinite(ts) or not isinstance(event, dict):
                                raise ValueError("Invalid event")
                            if sequence <= cursor:
                                continue
                            cursor = sequence
                            if ts < injection["ts"]:
                                continue
                            if incident_id is None and event["type"] == "incident_opened":
                                incident_id = event["incident_id"]
                            if incident_id is None or event.get("incident_id") != incident_id:
                                continue
                            payload = event.get("payload", {})
                            if not isinstance(payload, dict):
                                raise ValueError("Invalid event payload")
                            records.append(record)
                            candidate = payload.get("receipt_id")
                            if type(candidate) is int and candidate > 0:
                                receipt_id = candidate
                            if rehearsal and event["type"] == "approval_requested":
                                approval_id = event["payload"]["approval_id"]
                                if approval_id not in approvals:
                                    approvals.add(approval_id)
                                    await self._approve(approval_id, records)
                            if event["type"] in TERMINAL:
                                if rehearsal and receipt_id is not None:
                                    await self._credit(receipt_id, records, injection)
                                return records
                    except ObservationError:
                        raise
                    except httpx.HTTPStatusError as error:
                        code = error.response.status_code
                        if code not in {408, 429} and code < 500:
                            raise ObservationError(f"event_stream_http_{code}", records) from None
                    except httpx.TransportError:
                        pass
                    except (ValueError, TypeError, KeyError):
                        raise ObservationError("invalid_event_stream", records) from None
                    await asyncio.sleep(self.reconnect_s)
        except TimeoutError:
            raise ObservationError("observation_timeout", records) from None


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=list(SCENARIOS), action="append", required=True)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--rehearsal", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Count recorded attempts toward --runs")
    parser.add_argument("--output", type=Path, default=Path("bench/results.jsonl"))
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    if args.rehearsal and os.environ.get("ONCALL_REHEARSAL") != "1":
        parser.error("Set ONCALL_REHEARSAL=1 for rehearsal hooks")
    async with httpx.AsyncClient() as client:
        services = HttpTrialServices(client, os.environ["GATEWAY_URL"], os.environ["OBSERVER_URL"],
                                     os.environ["CHAOS_URL"])
        await Harness(services, args.output, args.rehearsal).run(args.scenario, args.runs, resume=args.resume)


if __name__ == "__main__":
    asyncio.run(main())
