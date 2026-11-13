import json

import pytest
from fastapi.testclient import TestClient

from chaos import ground_truth
from chaos.experiments import Engine, Spec
from chaos.faults import FLAG_CONFIGMAP, FLAG_FILE
from chaos.main import FAULTS, LEGACY, create_app, observer_severity
from tests.test_chaos import JUDGE, FakeKubectl, judge
from tests.test_registry import FLAGS

FLIP = Spec(target="payment", capability="flag:paymentFailure", choice="50%")
ADDR = Spec(target="checkout", capability="env:PAYMENT_ADDR", choice="wrong_port")


class World:
    def __init__(self, tmp_path, observer=True):
        self.now = 1000.0
        self.fake = FakeKubectl()
        self.fake.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE] = json.dumps(FLAGS)
        self.health = {"ts": self.now, "last_ok_ts": self.now, "severity": 0, "prometheus_ok": True, "services": {}}
        self.engine = Engine(tmp_path, self.fake, (lambda: self.health) if observer else None,
                             clock=lambda: self.now)

    # time moves and the observer keeps reading, unless a test freezes it
    def later(self, seconds, fresh=True):
        self.now += seconds
        if fresh and self.health:
            self.health["ts"] = self.health["last_ok_ts"] = self.now
        self.engine.tick()

    def flag(self, name="paymentFailure"):
        return json.loads(self.fake.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE])["flags"][name]["defaultVariant"]

    def set_flag(self, value, name="paymentFailure"):
        doc = json.loads(self.fake.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE])
        doc["flags"][name]["defaultVariant"] = value
        self.fake.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE] = json.dumps(doc)

    def writes(self):
        return [c for c in self.fake.calls if c[0] == "patch" and "--dry-run=server" not in c]

    def status(self, exp):
        return self.engine.get(exp["id"])["status"]


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_preview_names_the_exact_field_and_changes_nothing(world):
    pre = world.engine.preview(FLIP)
    assert pre["ok"] and pre["problems"] == []
    assert pre["changes"] == [{"role": "fault", "kind": "flag", "name": "paymentFailure", "key": None,
                               "place": "configmap/flagd-config flags[paymentFailure].defaultVariant",
                               "before": "off", "after": "50%", "after_s": 0}]
    assert pre["journeys"] == ["checkout"] and pre["target_policy"] == "actable" and pre["ends_after_s"] == 1800
    assert world.flag() == "off" and world.writes() == []


@pytest.mark.parametrize("spec, problem", [
    (Spec(target="shipping", capability="flag:intlShippingSlowdown", choice="5sec"), "not watched"),
    (Spec(target="payment", capability="flag:paymentFailure", choice="75%"), "is not one of"),
    (Spec(target="payment", capability="scale_zero", choice="0"), "does not support"),
    (Spec(target="payment", capability="flag:paymentFailure", choice="50%", delay_s=999), "delay"),
    (Spec(target="payment", capability="flag:paymentFailure", choice="50%", duration_s=5), "duration"),
    (Spec(target="payment", capability="image", choice="payment:v2-bad", decoy=True), "decoy"),
])
def test_crafted_request_is_rejected_before_any_cluster_write(world, spec, problem):
    exp = world.engine.start(spec)
    assert exp["status"] == "rejected" and problem in exp["error"]
    assert world.writes() == [] and ground_truth.read_all(world.engine.truth_path) == []


@pytest.mark.parametrize("health, reason", [
    ({"prometheus_ok": False, "severity": 0, "ts": 1000.0}, "monitoring unavailable"),
    ({"prometheus_ok": True, "severity": 5, "ts": 1000.0, "last_ok_ts": 1000.0}, "not healthy"),
    ({"prometheus_ok": True, "severity": 0, "ts": 1000.0, "last_ok_ts": 900.0}, "100 s old"),
    (None, "unreachable"),
])
def test_unknown_or_unhealthy_baseline_blocks_the_start(world, health, reason):
    world.health = health
    exp = world.engine.start(FLIP)
    assert exp["status"] == "rejected" and reason in exp["error"] and world.flag() == "off"


def test_judge_may_start_on_a_bad_baseline_on_purpose(world):
    world.health["severity"] = 5
    exp = world.engine.start(FLIP.model_copy(update={"skip_baseline": True}))
    assert exp["status"] == "active" and exp["baseline"]["ok"] is False and world.flag() == "50%"


def test_start_applies_records_truth_and_the_old_value(world):
    exp = world.engine.start(FLIP)
    assert exp["status"] == "active" and world.flag() == "50%" and exp["expires_at"] == 1000.0 + 1800
    m = exp["mutations"][0]
    assert (m["before"], m["injected"], m["state"]) == ("off", "50%", "applied")
    truth = ground_truth.read_all(world.engine.truth_path)
    assert [(t["type"], t["target"], t["experiment_id"]) for t in truth] == [
        ("broken_configuration", "payment", exp["id"])]


def test_same_idempotency_key_never_injects_twice(world):
    first = world.engine.start(FLIP, idem_key="k1")
    again = world.engine.start(FLIP, idem_key="k1")
    assert again["id"] == first["id"] and len(world.writes()) == 1
    assert len(ground_truth.read_all(world.engine.truth_path)) == 1


def test_one_lab_experiment_at_a_time(world):
    first = world.engine.start(FLIP)
    second = world.engine.start(ADDR)
    assert second["status"] == "rejected" and first["id"] in second["error"]
    assert world.fake.env("checkout")["PAYMENT_ADDR"] == "payment:8080"


def test_stop_restores_then_waits_for_fresh_health(world):
    exp = world.engine.start(FLIP)
    stopped = world.engine.stop(exp["id"])
    assert stopped["status"] == "verifying" and stopped["ended_by"] == "judge_stop" and world.flag() == "off"
    world.later(5)
    assert world.status(exp) == "verifying"  # one good reading is not recovery
    world.later(30)
    done = world.engine.get(exp["id"])
    assert done["status"] == "finished" and done["healthy"] is True


def test_stale_health_never_counts_as_recovered(world):
    exp = world.engine.start(FLIP)
    world.engine.stop(exp["id"])
    world.health["prometheus_ok"] = False
    world.later(60)
    assert world.status(exp) == "verifying"
    world.later(600)
    done = world.engine.get(exp["id"])
    assert done["status"] == "needs_operator" and "monitoring unavailable" in done["error"]


# the agent (or anyone) reversed the cause: the fault is over and must not come back
def test_repaired_fault_is_noticed_and_not_reapplied(world):
    exp = world.engine.start(FLIP)
    world.set_flag("off")
    world.later(5)
    seen = world.engine.get(exp["id"])
    assert seen["status"] == "verifying" and seen["ended_by"] == "repaired"
    world.later(5)
    world.later(35)
    assert world.status(exp) == "finished" and world.flag() == "off" and len(world.writes()) == 1


def test_fix_undone_by_the_gateway_makes_the_fault_active_again(world):
    exp = world.engine.start(FLIP)
    world.set_flag("off")
    world.later(5)
    world.set_flag("50%")
    world.later(5)
    again = world.engine.get(exp["id"])
    assert again["status"] == "active" and again["ended_by"] is None


def test_expiry_cleans_up_and_is_credited_to_expiry(world):
    exp = world.engine.start(FLIP.model_copy(update={"duration_s": 60}))
    world.later(59)
    assert world.status(exp) == "active" and world.flag() == "50%"
    world.later(2)
    ended = world.engine.get(exp["id"])
    assert ended["status"] == "verifying" and ended["ended_by"] == "expiry" and world.flag() == "off"


# a human set a third value meanwhile: their work is never overwritten with our old snapshot
def test_human_edit_blocks_the_restore(world):
    exp = world.engine.start(FLIP)
    world.set_flag("10%")
    stopped = world.engine.stop(exp["id"])
    assert stopped["status"] == "needs_operator" and "'10%'" in stopped["error"] and world.flag() == "10%"


def test_delayed_start_applies_on_the_watchdog_and_can_be_cancelled(world, tmp_path):
    exp = world.engine.start(FLIP.model_copy(update={"delay_s": 30}))
    assert exp["status"] == "scheduled" and world.flag() == "off"
    world.later(31)
    assert world.status(exp) == "active" and world.flag() == "50%"
    other = World(tmp_path / "b")
    waiting = other.engine.start(FLIP.model_copy(update={"delay_s": 30}))
    assert other.engine.stop(waiting["id"])["status"] == "finished" and other.writes() == []


def test_decoy_lands_after_the_fault_and_leaves_with_the_run(world):
    exp = world.engine.start(FLIP.model_copy(update={"decoy": True}))
    assert "PROMO_BANNER" not in world.fake.env("payment")
    world.later(16)
    assert world.fake.env("payment")["PROMO_BANNER"] == "autumn"
    assert [t["type"] for t in ground_truth.read_all(world.engine.truth_path)] == ["broken_configuration", "decoy"]
    world.set_flag("off")  # the agent picked the real cause
    world.later(5)
    assert world.fake.env("payment")["PROMO_BANNER"] == "autumn"  # no second rollout while the fix is verified
    world.later(5)
    world.later(35)
    assert world.status(exp) == "finished" and "PROMO_BANNER" not in world.fake.env("payment")


def test_failed_first_write_is_rejected_not_half_applied(world):
    world.engine.preview(FLIP)
    world.fake.fail_on = "patch"
    exp = world.engine.start(FLIP.model_copy(update={"skip_baseline": True}))
    assert exp["status"] == "rejected" and "forbidden" in exp["error"]


# chaos died between writing intent and marking it applied: clean up, never trust it
def test_run_interrupted_mid_apply_is_cleaned_up_after_restart(world, tmp_path):
    exp = world.engine.start(FLIP)
    stored = world.engine._load("id = ?", exp["id"])[0]
    stored["status"] = "applying"
    stored["mutations"][0]["state"] = "writing"
    world.engine._save(stored)
    restarted = Engine(tmp_path, world.fake, lambda: world.health, clock=lambda: world.now)
    restarted.tick()
    assert restarted.get(exp["id"])["status"] == "cleanup_required"
    restarted.tick()
    seen = restarted.get(exp["id"])
    assert seen["status"] == "verifying" and seen["ended_by"] == "error" and world.flag() == "off"


def test_cluster_unreachable_keeps_the_run_and_retries(world):
    exp = world.engine.start(FLIP)
    world.fake.fail_on = "get"
    world.later(5)
    seen = world.engine.get(exp["id"])
    assert seen["status"] == "active" and "forbidden" in seen["error"]
    world.fake.fail_on = None
    world.set_flag("off")
    world.later(5)
    assert world.status(exp) == "verifying"


def test_blind_run_hides_the_answer_until_reveal(world):
    exp = world.engine.draw(seed=7)
    seen = world.engine.get(exp["id"])
    assert seen["hidden"] and seen["spec"] is None and seen["mutations"] is None and seen["target"] is None
    assert seen["status"] == "active" and seen["seed"] == 7
    shown = world.engine.reveal(exp["id"])
    assert not shown["hidden"] and shown["spec"]["target"] == exp["spec"]["target"]


def test_same_seed_draws_the_same_experiment(tmp_path):
    picks = [World(tmp_path / str(i)).engine.draw(seed=42)["spec"] for i in range(2)]
    assert picks[0] == picks[1] and picks[0]["blind"]


def test_legacy_presets_cover_every_fault_route():
    assert set(LEGACY) == set(FAULTS)


def test_legacy_fault_never_expires_and_reset_ends_it(tmp_path):
    fake = FakeKubectl()
    with judge(create_app(tmp_path, fake, tick_s=None)) as client:
        entry = client.post("/chaos/bad-deploy").json()
        run = client.get(f"/chaos/experiments/{entry['experiment_id']}").json()
        assert run["status"] == "active" and run["legacy"] and run["expires_at"] is None
        client.post("/chaos/reset")
        ended = client.get(f"/chaos/experiments/{entry['experiment_id']}").json()
        assert ended["status"] == "finished" and ended["ended_by"] == "reset"


def test_every_chaos_route_needs_the_judge_token(tmp_path):
    with TestClient(create_app(tmp_path, FakeKubectl(), tick_s=None)) as client:
        for method, path in [("GET", "/chaos/ground-truth"), ("GET", "/chaos/registry"),
                             ("GET", "/chaos/experiments"), ("POST", "/chaos/bad-deploy"),
                             ("POST", "/chaos/experiments"), ("POST", "/chaos/kubectl"), ("POST", "/chaos/reset")]:
            assert client.request(method, path).status_code == 401, path
        assert client.get("/chaos/registry", headers={"X-Chaos-Token": "wrong-token-000000000"}).status_code == 401
        assert client.get("/chaos/registry", headers=JUDGE).status_code == 200


def test_missing_judge_token_fails_at_start(tmp_path, monkeypatch):
    monkeypatch.delenv("CHAOS_JUDGE_TOKEN")
    with pytest.raises(RuntimeError, match="CHAOS_JUDGE_TOKEN"):
        with TestClient(create_app(tmp_path, FakeKubectl(), tick_s=None)):
            pass


def test_http_compose_preview_start_stop(tmp_path):
    fake = FakeKubectl()
    health = {"ts": 0.0, "severity": 0, "prometheus_ok": True}

    def now():
        import time
        health["ts"] = health["last_ok_ts"] = time.time()
        return health

    with judge(create_app(tmp_path, fake, health=now, tick_s=None)) as client:
        reg = client.get("/chaos/registry").json()
        assert reg["baseline"]["ok"] is True and reg["open"] == []
        spec = {"target": "checkout", "capability": "env:PAYMENT_ADDR", "choice": "wrong_host"}
        pre = client.post("/chaos/experiments/preview", json=spec).json()
        assert pre["ok"] and pre["changes"][0]["after"] == "payment-gone:8080"
        started = client.post("/chaos/experiments", json=spec, headers={"Idempotency-Key": "abc"})
        assert started.status_code == 200 and started.json()["status"] == "active"
        assert client.post("/chaos/experiments", json=spec, headers={"Idempotency-Key": "abc"}).json()["id"] \
            == started.json()["id"]
        assert fake.env("checkout")["PAYMENT_ADDR"] == "payment-gone:8080"
        busy = client.post("/chaos/experiments", json=spec)
        assert busy.status_code == 409 and busy.json()["status"] == "rejected"
        assert client.post("/chaos/experiments", json={**spec, "extra": 1}).status_code == 422
        stopped = client.post(f"/chaos/experiments/{started.json()['id']}/stop").json()
        assert stopped["status"] == "verifying" and fake.env("checkout")["PAYMENT_ADDR"] == "payment:8080"
        assert client.post("/chaos/experiments/exp-nope/stop").status_code == 404
        assert [e["status"] for e in client.get("/chaos/experiments").json()] == ["rejected", "verifying"]


# a stale zero is not healthy: reset must not report recovery on old numbers
def test_reset_health_wait_ignores_stale_readings(monkeypatch):
    import httpx

    def reply(body):
        return lambda url, timeout: httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", reply({"severity": 0, "prometheus_ok": False}))
    assert observer_severity("http://observer") is None
    monkeypatch.setattr(httpx, "get", reply({"severity": 0, "prometheus_ok": True}))
    assert observer_severity("http://observer") == 0
