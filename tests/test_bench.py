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
        return {"ts": 100}
    async def observe(self, injection, rehearsal):
        return [
            {"ts": 102, "event": {"type": "incident_opened", "incident_id": "i"}},
            {"ts": 105, "event": {"type": "diagnosis_ready", "incident_id": "i",
                                   "payload": {"pattern": "recent_change"}}},
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
