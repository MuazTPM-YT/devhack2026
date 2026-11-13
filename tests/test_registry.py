import json

import pytest

from chaos import registry
from chaos.faults import FLAG_CONFIGMAP, FLAG_FILE
from chaos.registry import Refused, broken_address, resolve
from tests.test_chaos import FakeKubectl

FLAGS = {"flags": {
    "paymentFailure": {"defaultVariant": "off", "description": "Fail payment service charge requests n%",
                       "variants": {"100%": 1, "off": 0, "10%": 0.1, "50%": 0.5}},
    "recommendationCacheFailure": {"defaultVariant": "off", "variants": {"off": False, "on": True}},
    "intlShippingSlowdown": {"defaultVariant": "off", "variants": {"off": 0, "5sec": 5}},
    "emitRawPii": {"defaultVariant": "off", "variants": {"off": False, "on": True}},
}}


def cluster():
    fake = FakeKubectl()
    fake.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE] = json.dumps(FLAGS)
    return fake


def cap(reg, target, cap_id):
    return next(c for c in reg["targets"][target]["capabilities"] if c["id"] == cap_id)


def test_flag_variants_come_from_the_cluster_weakest_first():
    c = cap(registry.build(cluster()), "payment", "flag:paymentFailure")
    assert c["available"] and c["choices"] == ["10%", "50%", "100%"] and c["current"] == "off"
    assert c["what"].startswith("Fail payment") and c["field"] == {"kind": "flag", "name": "paymentFailure",
                                                                   "key": None}


def test_unsupported_pairs_are_listed_as_unavailable_with_a_reason():
    reg = registry.build(cluster())
    assert cap(reg, "shipping", "flag:intlShippingSlowdown")["reason"] == "service not watched by the observer"
    assert cap(reg, "cart", "flag:cartFailure")["reason"] == "flag not in the deployed flagd file"
    assert cap(reg, "checkout", "image")["reason"] == "no reviewed bad image for this service"
    assert cap(reg, "checkout", "env:CART_ADDR")["reason"] == "env var not set on this Deployment"
    assert not any(c["available"] for c in reg["targets"]["shipping"]["capabilities"])


# discovery never widens the reviewed list: a new flag in the cluster waits for review
def test_flag_not_in_the_reviewed_list_is_pending_never_offered():
    reg = registry.build(cluster())
    assert reg["pending_review"] == ["emitRawPii"]
    assert not [c for t in reg["targets"].values() for c in t["capabilities"] if "emitRawPii" in c["id"]]


def test_env_fault_values_are_computed_by_the_server():
    c = cap(registry.build(cluster()), "checkout", "env:PAYMENT_ADDR")
    assert c["values"] == {"wrong_port": "payment:9999", "wrong_host": "payment-gone:8080"}
    assert broken_address("http://email:8080", "wrong_port") == "http://email:9999"
    assert broken_address("http://shipping:8080/x", "wrong_host") == "http://shipping-gone:8080/x"


def test_target_policy_and_decoy_follow_services_yaml():
    reg = registry.build(cluster())
    assert reg["targets"]["payment"]["policy"] == "actable"
    assert reg["targets"]["kafka"]["policy"] == "approval_only"
    assert reg["targets"]["accounting"]["policy"] == "watch_only"
    assert cap(reg, "payment", "flag:paymentFailure")["decoy"] is True
    # a decoy is a rollout: never on a data store, never with a bad image
    assert cap(reg, "kafka", "scale_zero")["decoy"] is False
    assert cap(reg, "payment", "image")["decoy"] is False


def test_scale_zero_only_where_reviewed_and_not_twice():
    fake = cluster()
    assert cap(registry.build(fake), "valkey-cart", "scale_zero")["available"]
    fake.deployments["valkey-cart"]["spec"]["replicas"] = 0
    assert cap(registry.build(fake), "valkey-cart", "scale_zero")["reason"] == "already at 0 replicas"
    assert not [c for c in registry.build(fake)["targets"]["payment"]["capabilities"] if c["id"] == "scale_zero"]


@pytest.mark.parametrize("target, capability, choice, reason", [
    ("nope", "image", "x", "unknown target"),
    ("payment", "env:PAYMENT_ADDR", "wrong_port", "does not support"),
    ("shipping", "flag:intlShippingSlowdown", "5sec", "not watched"),
    ("payment", "flag:paymentFailure", "75%", "is not one of"),
    ("payment", "flag:paymentFailure", "off", "is not one of"),
])
def test_resolve_refuses_what_the_registry_does_not_offer(target, capability, choice, reason):
    with pytest.raises(Refused, match=reason):
        resolve(registry.build(cluster()), target, capability, choice)


def test_resolve_returns_the_injected_value():
    c, value = resolve(registry.build(cluster()), "payment", "flag:paymentFailure", "50%")
    assert c["primitive"] == "flag_variant" and value == "50%" and c["meaning"]["50%"] == 0.5


def test_memory_limit_choices_respect_live_request_and_limit():
    fake = cluster()
    c = fake.deployments["recommendation"]["spec"]["template"]["spec"]["containers"][0]
    c["resources"] = {"requests": {"memory": "32Mi"}, "limits": {"memory": "200Mi"}}
    offered = cap(registry.build(fake), "recommendation", "memory_limit")
    assert offered["available"] and offered["choices"] == ["32Mi", "64Mi", "128Mi"]
    assert offered["field"] == {"kind": "memory", "name": "recommendation", "key": None}
    c["resources"]["requests"]["memory"] = "200Mi"
    blocked = cap(registry.build(fake), "recommendation", "memory_limit")
    assert not blocked["available"] and "request" in blocked["reason"]


def test_replica_reduction_keeps_one_replica_and_never_widens_reviewed_targets():
    fake = cluster()
    fake.deployments["ad"]["spec"]["replicas"] = 3
    offered = cap(registry.build(fake), "ad", "replica_reduction")
    assert offered["available"] and offered["values"] == {"1": 1, "2": 2}
    fake.deployments["ad"]["spec"]["replicas"] = 1
    assert not cap(registry.build(fake), "ad", "replica_reduction")["available"]
    assert not any(c["id"] == "replica_reduction" for c in registry.build(fake)["targets"]["kafka"]["capabilities"])
