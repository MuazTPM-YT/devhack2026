import json

import httpx
import pytest

from bench.harness import Harness, HttpTrialServices


def stream(records):
    return httpx.Response(200, text="".join(f"data: {json.dumps(row)}\n\n" for row in records))


async def test_reconnect_resumes_cursor_and_ignores_duplicate_events():
    opened = {"seq": 1, "ts": 100, "event": {"type": "incident_opened", "incident_id": "i"}}
    diagnosis = {"seq": 2, "ts": 102, "event": {"type": "diagnosis_ready", "incident_id": "i",
                                              "payload": {"pattern": "recent_change", "culprit": "payment"}}}
    resolved = {"seq": 3, "ts": 110, "event": {"type": "incident_resolved", "incident_id": "i"}}
    cursors = []
    def handle(request):
        cursors.append(request.headers["Last-Event-ID"])
        if len(cursors) == 1:
            return stream([opened, diagnosis])
        return stream([diagnosis, resolved])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        services = HttpTrialServices(client, "http://gateway", "http://observer", "http://chaos")
        records = await services.observe({"ts": 100}, False)
    assert cursors == ["0", "2"]
    assert [record["seq"] for record in records] == [1, 2, 3]


async def test_replayed_approval_does_not_repeat_post(monkeypatch):
    monkeypatch.setenv("ONCALL_REHEARSAL", "1")
    opened = {"seq": 1, "ts": 100, "event": {"type": "incident_opened", "incident_id": "i"}}
    approval = {"seq": 2, "ts": 101, "event": {"type": "approval_requested", "incident_id": "i",
                                             "payload": {"approval_id": "a"}}}
    resolved = {"seq": 3, "ts": 110, "event": {"type": "incident_resolved", "incident_id": "i",
                                             "payload": {"receipt_id": 17}}}
    gets, posts = [], []
    def handle(request):
        if request.method == "GET":
            gets.append(request)
            return stream([opened, approval] if len(gets) == 1 else [approval, resolved])
        posts.append(request.url.path)
        return httpx.Response(200, json={"decision": "executed"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        services = HttpTrialServices(client, "http://gateway", "http://observer", "http://chaos")
        await services.observe({"ts": 100}, True)
    assert posts == ["/approvals/a/decide", "/ledger/rehearsal"]


async def test_resume_counts_recorded_attempts_and_does_not_repeat_fault(tmp_path):
    class Services:
        resets = 0
        async def reset(self):
            self.resets += 1
        async def wait_healthy(self):
            pass
        async def inject(self, scenario):
            return {"ts": 100, "target": "payment"}
        async def observe(self, injection, rehearsal):
            return [{"ts": 110, "event": {"type": "incident_resolved", "incident_id": "i"}}]
    output = tmp_path / "results.jsonl"
    services = Services()
    await Harness(services, output).run(["bad-deploy"], 1)
    resumed = await Harness(services, output).run(["bad-deploy"], 2, resume=True)
    assert services.resets == 2
    assert len(resumed) == 1
    assert len(output.read_text().splitlines()) == 2
    await Harness(services, output).run(["bad-deploy"], 2, resume=True)
    assert services.resets == 2


async def test_resume_corrupt_file_fails_before_reset(tmp_path):
    class Services:
        async def reset(self):
            pytest.fail("Corrupt resume file must not trigger a fault reset")
    output = tmp_path / "results.jsonl"
    output.write_text("{truncated\n")
    with pytest.raises(ValueError, match="resume"):
        await Harness(Services(), output).run(["bad-deploy"], 2, resume=True)


async def test_timeout_keeps_detection_and_diagnosis_measurements(tmp_path):
    from bench.harness import ObservationError
    records = [
        {"seq": 1, "ts": 102, "event": {"type": "incident_opened", "incident_id": "i"}},
        {"seq": 2, "ts": 105, "event": {"type": "diagnosis_ready", "incident_id": "i",
                                        "payload": {"pattern": "recent_change", "culprit": "payment"}}},
    ]
    def handle(request):
        return stream(records)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        http = HttpTrialServices(client, "http://gateway", "http://observer", "http://chaos",
                                 timeout_s=0.01, reconnect_s=1)
        with pytest.raises(ObservationError) as error:
            await http.observe({"ts": 100}, False)
        assert len(error.value.records) == 2
        class Services:
            async def reset(self):
                pass
            async def wait_healthy(self):
                pass
            async def inject(self, scenario):
                return {"ts": 100, "target": "payment"}
            async def observe(self, injection, rehearsal):
                return await http.observe(injection, rehearsal)
        results = await Harness(Services(), tmp_path / "results.jsonl").run(["bad-deploy"], 1)
    result = results[0]
    assert result.error == "observation_timeout"
    assert result.detect_s == 2
    assert result.diagnose_s == 5
    assert result.diagnosis_correct is True
    assert result.recover_s is None
    assert result.outcome == "failed"


async def test_uncertain_approval_post_is_not_retried(monkeypatch):
    from bench.harness import ObservationError
    monkeypatch.setenv("ONCALL_REHEARSAL", "1")
    records = [
        {"seq": 1, "ts": 100, "event": {"type": "incident_opened", "incident_id": "i"}},
        {"seq": 2, "ts": 101, "event": {"type": "approval_requested", "incident_id": "i",
                                        "payload": {"approval_id": "a"}}},
    ]
    posts = []
    def handle(request):
        if request.method == "GET":
            return stream(records)
        posts.append(request.url.path)
        raise httpx.ReadTimeout("fake network timeout")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        services = HttpTrialServices(client, "http://gateway", "http://observer", "http://chaos")
        with pytest.raises(ObservationError, match="approval_request_failed") as error:
            await services.observe({"ts": 100}, True)
    assert posts == ["/approvals/a/decide"]
    assert len(error.value.records) == 2


async def test_failed_attempts_count_toward_resume_target(tmp_path):
    class Services:
        calls = 0
        async def reset(self):
            self.calls += 1
            raise TimeoutError
    services = Services()
    output = tmp_path / "results.jsonl"
    await Harness(services, output).run(["bad-deploy"], 2)
    assert services.calls == 2
    assert await Harness(services, output).run(["bad-deploy"], 2, resume=True) == []
    assert services.calls == 2


async def test_health_wait_requires_current_metrics_and_retries_startup(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    responses = [
        httpx.Response(503),
        httpx.Response(200, json={"severity": 0, "prometheus_ok": False}),
        httpx.Response(200, json={"severity": 0}),
        httpx.Response(200, json={"severity": False, "prometheus_ok": True}),
        httpx.Response(200, json={"severity": 0, "prometheus_ok": True}),
    ]
    calls = []
    def handle(request):
        calls.append(request.url.path)
        return responses.pop(0)
    sleep = AsyncMock()
    monkeypatch.setattr("bench.harness.asyncio.sleep", sleep)
    monkeypatch.setattr("bench.harness.time", SimpleNamespace(monotonic=lambda: 100))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        services = HttpTrialServices(client, "http://gateway", "http://observer", "http://chaos", stable_s=0)
        await services.wait_healthy()
    assert len(calls) == 5
    assert sleep.await_count == 4


async def test_stale_metrics_restart_the_entire_stability_window(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    samples = iter([True, False, True, True, True])
    ticks = iter([0, 1, 2, 3, 4])
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"severity": 0, "prometheus_ok": next(samples)})
    monkeypatch.setattr("bench.harness.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("bench.harness.time", SimpleNamespace(monotonic=lambda: next(ticks)))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        services = HttpTrialServices(client, "http://gateway", "http://observer", "http://chaos", stable_s=2)
        await services.wait_healthy()
    assert len(calls) == 5
