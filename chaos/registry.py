# what a judge may break, per target: the reviewed list in config/chaos.yaml joined with live facts.
# Discovery never widens the list; anything unsupported is returned as unavailable with a reason.
import json
import re
from typing import Any

from brain.rules import to_bytes
from chaos.faults import Kubectl, _container, kubectl, read_flags
from schemas import config

WRONG_PORT = "9999"


class Refused(ValueError):
    pass


# payment:8080 -> payment:9999 | payment-gone:8080 (scheme and path kept)
def broken_address(value: str, mode: str) -> str:
    m = re.fullmatch(r"(?P<scheme>[a-z]+://)?(?P<host>[^:/]+)(?::(?P<port>\d+))?(?P<rest>/.*)?", value)
    if not m:
        raise Refused(f"cannot parse address {value!r}")
    host, port = m["host"], m["port"]
    if mode == "wrong_port":
        port = WRONG_PORT
    elif mode == "wrong_host":
        host = f"{host}-gone"
    else:
        raise Refused(f"unknown mode {mode}")
    return f"{m['scheme'] or ''}{host}{':' + port if port else ''}{m['rest'] or ''}"


def _cap(cap_id: str, primitive: str, family: str, label: str, field: dict[str, Any], values: dict[str, Any],
         current: Any, reason: str | None, **more: Any) -> dict[str, Any]:
    return {"id": cap_id, "primitive": primitive, "family": family, "label": label, "field": field,
            "choices": list(values), "values": values, "current": current,
            "available": reason is None, "reason": reason, "tested": False, "unit": None, "what": None,
            "meaning": {}, "decoy": False, **more}


# weakest variant first; a variant that is not a number sorts by name
def _strength(item: tuple[str, Any]) -> tuple[float, str]:
    name, value = item
    return (float(value) if isinstance(value, (int, float)) else 0.0, name)


def _standing(service: dict[str, Any] | None) -> str:
    if service is None:
        return "unwatched"
    if service.get("protected"):
        return "approval_only"
    return "actable" if service.get("actable") else "watch_only"


# -> {version, limits, decoy, targets: {name: {policy, capabilities: [...]}}, pending_review: [flags]}
def build(run: Kubectl = kubectl, policy: dict[str, Any] | None = None,
          services_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or config.load("chaos")
    services_cfg = services_cfg or config.load("services")
    services: dict[str, Any] = services_cfg["services"]
    repair_limits = config.load("policy")["tools"]
    flag_map: dict[str, str] = services_cfg.get("flags", {})
    live_flags: dict[str, Any] = json.loads(read_flags(run)).get("flags", {})
    deployments = {d["metadata"]["name"]: d for d in json.loads(run("get", "deployments", "-o", "json"))["items"]}

    names = list(services) + sorted({flag_map[f] for f in policy.get("flags", {}) if f in flag_map} - set(services))
    targets: dict[str, dict[str, Any]] = {
        n: {"kind": services.get(n, {}).get("kind"), "critical": bool(services.get(n, {}).get("critical")),
            "policy": _standing(services.get(n)), "journeys": policy.get("journeys", {}).get(n, []),
            "capabilities": []} for n in names}
    pairs = set(policy.get("decoy", {}).get("pairs_with", []))

    def add(target: str, cap: dict[str, Any]) -> None:
        # the decoy is an env change, so a rollout: only where a rolling update is safe (actable, stateless)
        cap["decoy"] = bool(cap["available"] and cap["primitive"] in pairs
                            and targets[target]["policy"] == "actable" and target in deployments)
        targets[target]["capabilities"].append(cap)

    for flag, meta in policy.get("flags", {}).items():
        target = flag_map.get(flag)
        if target is None:
            continue
        live = live_flags.get(flag)
        current = live.get("defaultVariant") if live else None
        variants = {k: v for k, v in (live or {}).get("variants", {}).items() if k != current}
        reason = None
        if target not in services:
            reason = "service not watched by the observer"
        elif live is None:
            reason = "flag not in the deployed flagd file"
        elif not variants:
            reason = "flag has no other variant"
        # the injected value is the variant name; meaning keeps what flagd serves for it (0.5, true, 5000)
        ordered = dict(sorted(variants.items(), key=_strength))
        add(target, _cap(f"flag:{flag}", "flag_variant", meta["family"], f"flag {flag}",
                         {"kind": "flag", "name": flag, "key": None},
                         {name: name for name in ordered}, current, reason, meaning=ordered,
                         tested=bool(meta.get("tested")), unit=meta.get("unit"),
                         what=(live or {}).get("description")))

    for target in targets:
        deployment = deployments.get(target)
        fixture = policy.get("images", {}).get(target)
        if fixture:
            current = _container(deployment)["image"] if deployment else None
            reason = "deployment not found" if deployment is None else (
                "bad image already running" if current == fixture["image"] else None)
            add(target, _cap("image", "bad_image", fixture["family"], f"bad build {fixture['image']}",
                             {"kind": "image", "name": target, "key": None}, {fixture["image"]: fixture["image"]},
                             current, reason, tested=bool(fixture.get("tested"))))
        elif targets[target]["policy"] == "actable":
            add(target, _cap("image", "bad_image", "bad_deployment", "bad build", {"kind": "image", "name": target,
                             "key": None}, {}, None, "no reviewed bad image for this service"))
        env = {e["name"]: e.get("value") for e in _container(deployment).get("env", [])} if deployment else {}
        for key in policy.get("env_addr", {}).get(target, []):
            current = env.get(key)
            values: dict[str, Any] = {}
            reason = None
            if deployment is None:
                reason = "deployment not found"
            elif current is None:
                reason = "env var not set on this Deployment"
            else:
                try:
                    values = {mode: broken_address(current, mode) for mode in ("wrong_port", "wrong_host")}
                except Refused as e:
                    reason = str(e)
            add(target, _cap(f"env:{key}", "broken_env", "broken_configuration", f"env {key}",
                             {"kind": "env", "name": target, "key": key}, values, current, reason))
        if target in policy.get("scale_zero", []):
            current = deployment["spec"].get("replicas", 1) if deployment else None
            reason = "deployment not found" if deployment is None else ("already at 0 replicas" if current == 0
                                                                        else None)
            add(target, _cap("scale_zero", "scale_zero", "dependency_failure", "scale to 0 replicas",
                             {"kind": "replicas", "name": target, "key": None}, {"0": 0}, current, reason,
                             tested=target in ("valkey-cart", "kafka")))
        if target in policy.get("replica_reduction", []):
            current = deployment["spec"].get("replicas", 1) if deployment else None
            max_replicas = repair_limits["scale"]["max"]
            values = {str(n): n for n in range(1, current)} if current is not None and 1 < current <= max_replicas else {}
            reason = "deployment not found" if deployment is None else (
                f"need 2 to {max_replicas} replicas before reducing capacity" if not values else None)
            add(target, _cap("replica_reduction", "replica_reduction", "resource_exhaustion", "reduce replicas",
                             {"kind": "replicas", "name": target, "key": None}, values, current, reason,
                             unit="replicas", what="Less capacity; an incident needs sustained errors or latency."))
        if target in policy.get("memory_limits", {}):
            resources = (_container(deployment).get("resources") or {}) if deployment else {}
            current = (resources.get("limits") or {}).get("memory")
            request = (resources.get("requests") or {}).get("memory") or "0"
            values = {}
            reason = None
            try:
                if to_bytes(str(current)) <= to_bytes(repair_limits["raise_limit"]["max_memory"]):
                    values = {n: n for n in policy["memory_limits"][target]
                              if 0 < to_bytes(str(n)) < to_bytes(str(current)) and to_bytes(str(n)) >= to_bytes(request)}
                if not values:
                    reason = "no reviewed limit below the current limit and at least the memory request"
            except (ValueError, OverflowError):
                reason = "deployment has no readable memory limit or request"
            add(target, _cap("memory_limit", "memory_limit", "resource_exhaustion", "lower memory limit",
                             {"kind": "memory", "name": target, "key": None}, values, current, reason,
                             unit="bytes", what="A low cap can cause OOMKilled; restore the previous cap to recover."))

    return {"version": policy["version"], "limits": policy["limits"], "decoy": policy.get("decoy", {}),
            "targets": targets,
            "pending_review": sorted(set(live_flags) - set(policy.get("flags", {})))}


# the one capability a spec names, with the value it injects; raises Refused with the reason
def resolve(registry: dict[str, Any], target: str, capability: str, choice: str) -> tuple[dict[str, Any], Any]:
    entry = registry["targets"].get(target)
    if entry is None:
        raise Refused(f"unknown target {target}")
    cap = next((c for c in entry["capabilities"] if c["id"] == capability), None)
    if cap is None:
        raise Refused(f"{target} does not support {capability}")
    if not cap["available"]:
        raise Refused(f"{capability} on {target}: {cap['reason']}")
    if choice not in cap["values"]:
        raise Refused(f"{choice!r} is not one of {cap['choices']}")
    return cap, cap["values"][choice]
