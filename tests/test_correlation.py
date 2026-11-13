from brain.correlation import correlate, reach, root_of
from schemas.orchestration import SignalEpisode

SHOP = [("frontend", "checkout", 9), ("checkout", "payment", 9), ("checkout", "cart", 9), ("cart", "valkey-cart", 9),
        ("frontend", "cart", 9), ("frontend", "product-catalog", 9), ("checkout", "shipping", 9)]


def ep(service: str, breach: float = 990.0) -> SignalEpisode:
    return SignalEpisode(episode_id=f"episode-{service}", service=service, symptom="errors", first_breach_at=breach,
                         sustained_at=breach + 30, last_observed_at=breach + 30, source_revision=1)


def run(episodes, failing=None, edges=SHOP, journal=(), deepest=None, open_incidents=None):
    failing = set(failing if failing is not None else (e.service for e in episodes))
    return correlate(episodes, open_incidents or {}, list(edges), list(journal), deepest or {}, failing, 600)


def test_reach_follows_calls_downstream():
    assert reach("checkout", SHOP) == {"payment", "cart", "valkey-cart", "shipping"}
    assert reach("valkey-cart", SHOP) == set()


def test_shared_dependency_is_one_group():
    d = run([ep("cart", 985), ep("checkout", 990), ep("valkey-cart", 980)])
    assert len(d.groups) == 1
    g = d.groups[0]
    assert g.reason == "shared_dependency" and g.cause == "dependency:valkey-cart"
    assert g.services == ["cart", "checkout", "valkey-cart"]


def test_victims_group_on_traced_dependency_even_if_it_is_not_yet_unhealthy():
    d = run([ep("cart"), ep("checkout")], failing={"cart", "checkout"}, deepest={"checkout": "cart"})
    assert len(d.groups) == 1 and d.groups[0].cause == "dependency:cart"


def test_unrelated_simultaneous_faults_stay_separate():
    d = run([ep("payment"), ep("product-catalog")])
    assert sorted(g.services[0] for g in d.groups) == ["payment", "product-catalog"]
    assert all(g.reason == "independent" for g in d.groups)
    assert all(note.startswith("timing_only") for note in d.notes.values())
    assert d.links == []


def test_missing_topology_is_unknown_with_link_not_merge():
    d = run([ep("payment"), ep("ad")])
    reasons = {g.services[0]: g.reason for g in d.groups}
    assert reasons == {"payment": "independent", "ad": "unknown_topology"}
    assert [(lk.reason, lk.relation) for lk in d.links] == [("unknown_topology", "related")]


def test_two_failing_branches_are_contradicted_not_guessed():
    root, options = root_of("frontend", {"payment", "product-catalog", "frontend"}, {}, {}, SHOP)
    assert root is None and options == ["payment", "product-catalog"]
    d = run([ep("frontend", 995)], failing={"frontend", "payment", "product-catalog"})
    assert d.groups[0].reason == "contradicted" and "both fit" in d.notes["episode-frontend"]


def test_dependency_breaching_long_after_symptom_is_not_its_cause():
    d = run([ep("checkout", 900), ep("payment", 1000)])
    assert len(d.groups) == 2


def test_later_episode_joins_open_incident_with_same_cause():
    d = run([ep("frontend")], failing={"frontend", "cart", "valkey-cart"},
            open_incidents={"inc-a": {"cause": "dependency:valkey-cart"}})
    assert d.groups == [] and d.joins == [("episode-frontend", "inc-a", "shared_dependency", "dependency:valkey-cart")]


def test_open_incident_with_other_cause_is_not_joined():
    d = run([ep("payment")], open_incidents={"inc-a": {"cause": "dependency:valkey-cart"}})
    assert d.joins == [] and d.groups[0].cause == "dependency:payment"


LIB = [("payment", "currency", 5), ("shipping", "currency", 5)]


def test_one_change_reaching_both_merges_as_shared_change():
    journal = [{"id": 7, "ts": 970.0, "object": "deployment/currency", "by_agent": 0}]
    d = run([ep("payment"), ep("shipping")], edges=LIB, journal=journal)
    assert len(d.groups) == 1
    assert d.groups[0].reason == "shared_change" and d.groups[0].evidence_ids == ["journal:7"]


def test_two_plausible_changes_link_but_do_not_merge():
    journal = [{"id": 7, "ts": 970.0, "object": "deployment/currency", "by_agent": 0},
               {"id": 8, "ts": 975.0, "object": "deployment/currency", "by_agent": 0}]
    d = run([ep("payment"), ep("shipping")], edges=LIB, journal=journal)
    assert len(d.groups) == 2
    assert {lk.relation for lk in d.links} == {"possible_shared_cause"}


def test_agent_change_or_change_outside_window_is_ignored():
    journal = [{"id": 7, "ts": 970.0, "object": "deployment/currency", "by_agent": 1},
               {"id": 8, "ts": 100.0, "object": "deployment/currency", "by_agent": 0}]
    d = run([ep("payment"), ep("shipping")], edges=LIB, journal=journal)
    assert len(d.groups) == 2 and d.links == []


def test_deterministic():
    eps = [ep("cart"), ep("checkout"), ep("valkey-cart"), ep("payment", 900), ep("ad")]
    assert run(eps).as_json() == run(list(reversed(eps))).as_json()
