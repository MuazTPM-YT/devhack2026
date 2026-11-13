import itertools

from observer.episodes import EpisodeTracker, symptom_of


def health(ts, **services):
    return {"ts": ts, "severity": 0, "services": services}


def sick(err=0.4, pods=0, breach=990.0):
    return {"err_ratio": err, "p95_ms": 100.0, "breaching": err > 0.05, "bad_pods": pods,
            "first_breach_ts": breach, "unhealthy": True}


def well():
    return {"err_ratio": 0.0, "p95_ms": 50.0, "breaching": False, "bad_pods": 0, "first_breach_ts": None,
            "unhealthy": False}


def tracker():
    ids = (f"episode-{n:04d}" for n in itertools.count(1))
    return EpisodeTracker(0.05, new_id=lambda: next(ids))


def test_open_once_then_recover():
    t = tracker()
    [opened] = t.update(health(1000, cart=sick()))
    assert (opened.service, opened.symptom, opened.first_breach_at, opened.source_revision) == ("cart", "errors", 990, 1)
    assert t.update(health(1005, cart=sick())) == []  # same spell, no new signal
    [ended] = t.update(health(1010, cart=well()))
    assert ended.episode_id == opened.episode_id and ended.recovered_at == 1010 and ended.source_revision == 2
    [again] = t.update(health(1020, cart=sick()))
    assert again.episode_id != opened.episode_id  # a new spell is a new episode


def test_missing_reading_keeps_episode_open():
    t = tracker()
    t.update(health(1000, cart=sick()))
    assert t.update(health(1005)) == []
    assert t.update(health(1010, cart={"unhealthy": None})) == []
    assert "cart" in t.open


def test_symptom_change_is_a_change():
    t = tracker()
    t.update(health(1000, cart=sick()))
    [changed] = t.update(health(1005, cart=sick(pods=2)))
    assert changed.symptom == "mixed" and changed.last_observed_at == 1005


def test_symptoms():
    assert symptom_of({"err_ratio": 0.0, "bad_pods": 1, "breaching": False}, 0.05) == "pods"
    assert symptom_of({"err_ratio": 0.01, "bad_pods": 0, "breaching": True}, 0.05) == "latency"


def test_restore_continues_revisions():
    t = tracker()
    [opened] = t.update(health(1000, cart=sick()))
    fresh = tracker()
    fresh.restore([opened])
    assert fresh.update(health(1005, cart=sick())) == []
    [ended] = fresh.update(health(1010, cart=well()))
    assert ended.episode_id == opened.episode_id and ended.source_revision == 2
