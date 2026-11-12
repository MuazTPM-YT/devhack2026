import json

from bench.harness import Harness
from bench.report import summarize


class FakeServices:
    calls = 0
    async def reset(self):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError
    async def wait_healthy(self):
        pass
    async def inject(self, scenario):
        return {"ts": 100, "target": "payment"}
    async def observe(self, injection, rehearsal):
        return [
            {"ts": 102, "event": {"type": "incident_opened", "incident_id": "i"}},
            {"ts": 105, "event": {"type": "diagnosis_ready", "incident_id": "i",
                                   "payload": {"pattern": "recent_change", "culprit": "payment"}}},
            {"ts": 110, "event": {"type": "incident_resolved", "incident_id": "i"}},
        ]


async def test_failed_trial_persisted_and_next_trial_runs(tmp_path):
    path = tmp_path / "results.jsonl"
    results = await Harness(FakeServices(), path).run(["bad-deploy"], 2)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert results[0].error == "TimeoutError"
    assert results[1].recover_s == 10
    assert len(rows) == 2
    summary = summarize(rows)["bad-deploy"]
    assert summary["failures"] == 1
    assert summary["recover_s"] == {"samples": 1, "median": 10, "worst": 10}
    assert summary["diagnosis_accuracy"] == 1


async def test_matching_pattern_wrong_culprit_is_not_correct(tmp_path):
    class WrongCulprit(FakeServices):
        calls = 1
        async def inject(self, scenario):
            return {"ts": 100, "target": "payment"}
        async def observe(self, injection, rehearsal):
            records = await super().observe(injection, rehearsal)
            records[1]["event"]["payload"]["culprit"] = "frontend"
            return records
    results = await Harness(WrongCulprit(), tmp_path / "results.jsonl").run(["bad-deploy"], 1)
    assert results[0].diagnosis_correct is False


async def test_rehearsal_hooks_only_when_enabled():
    import httpx
    from bench.harness import HttpTrialServices
    calls = []
    records = [
        {"seq": 1, "ts": 100, "event": {"type": "incident_opened", "incident_id": "i"}},
        {"seq": 2, "ts": 101, "event": {"type": "diagnosis_ready", "incident_id": "i",
                                        "payload": {"pattern": "recent_change", "culprit": "payment"}}},
        {"seq": 3, "ts": 102, "event": {"type": "approval_requested", "incident_id": "i",
                                        "payload": {"approval_id": "a"}}},
        {"seq": 4, "ts": 110, "event": {"type": "incident_resolved", "incident_id": "i"}},
    ]
    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, text="".join(f"data: {json.dumps(row)}\n\n" for row in records))
        return httpx.Response(200, json={"ok": True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        services = HttpTrialServices(client, "http://gateway", "http://observer", "http://chaos")
        injection = {"ts": 100, "type": "bad_deploy", "target": "payment"}
        await services.observe(injection, False)
        assert all(request.method == "GET" for request in calls)
        calls.clear()
        await services.observe(injection, True)
        posts = [request for request in calls if request.method == "POST"]
        assert len(posts) == 2
        assert json.loads(posts[-1].content) == {"incident_id": "i", "diagnosis_correct": True}
        assert "ground_truth" not in posts[-1].content.decode()
