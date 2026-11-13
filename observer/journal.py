# change journal (IMPLEMENTATION.md §6.2.4). Objects are API JSON (camelCase), e.g. from
# ApiClient().sanitize_for_serialization(obj); the client's .to_dict() gives snake_case and will not match.
import json
import sqlite3
from typing import Any, cast

AGENT_MANAGER = "oncall-agent"
RESTART_KEY = "kubectl.kubernetes.io/restartedAt"
KIND_ORDER = ["image", "env", "resources", "replicas", "restart", "other"]


def _template(obj: dict) -> dict:
    return obj.get("spec", {}).get("template", {})


def _containers(obj: dict) -> dict:
    return {c["name"]: c for c in _template(obj).get("spec", {}).get("containers", [])}


# old values for changed keys; None deletes keys the change added (null = delete in merge patches)
def _undo_map(old: dict, new: dict) -> dict:
    out = {}
    for k in old.keys() | new.keys():
        o, n = old.get(k), new.get(k)
        if k in old and k in new and o == n:
            continue
        out[k] = _undo_map(o, n) if isinstance(o, dict) and isinstance(n, dict) else o
    return out


# env is a list keyed by name: put back old entries, $patch-delete the added ones
def _undo_env(old: list, new: list) -> list:
    o, n = {e["name"]: e for e in old}, {e["name"]: e for e in new}
    return [o[k] for k in o if o[k] != n.get(k)] + [{"name": k, "$patch": "delete"} for k in n if k not in o]


def _deployment_changes(old: dict, new: dict) -> tuple[str, dict, list] | None:
    diff: dict[str, Any] = {}
    kinds: set[str] = set()
    patches: list[dict[str, Any]] = []
    oc, nc = _containers(old), _containers(new)
    if oc.keys() != nc.keys():
        diff["containers"] = {"old": sorted(oc), "new": sorted(nc)}
        kinds.add("other")
    for name in sorted(oc.keys() & nc.keys()):
        o, n, undo = oc[name], nc[name], {}
        if o.get("image") != n.get("image"):
            diff[f"containers[{name}].image"] = {"old": o.get("image"), "new": n.get("image")}
            undo["image"] = o.get("image")
            kinds.add("image")
        oe, ne = o.get("env") or [], n.get("env") or []
        if oe != ne:
            diff[f"containers[{name}].env"] = {"old": oe, "new": ne}
            undo["env"] = _undo_env(oe, ne)
            kinds.add("env")
        orr, nr = o.get("resources") or {}, n.get("resources") or {}
        if orr != nr:
            diff[f"containers[{name}].resources"] = {"old": orr, "new": nr}
            undo["resources"] = _undo_map(orr, nr)
            kinds.add("resources")
        if undo:
            patches.append({"name": name, **undo})

    oa = _template(old).get("metadata", {}).get("annotations") or {}
    na = _template(new).get("metadata", {}).get("annotations") or {}
    ann_undo = _undo_map(oa, na)
    for k in sorted(ann_undo):
        diff[f"annotations[{k}]"] = {"old": oa.get(k), "new": na.get(k)}
    if ann_undo:
        kinds.add("restart" if set(ann_undo) == {RESTART_KEY} else "other")

    inverse = []
    if "containers" in diff:
        # container added/removed: a patch can't undo that cleanly, roll back the whole template
        rev = (old.get("metadata", {}).get("annotations") or {}).get("deployment.kubernetes.io/revision")
        inverse.append({"op": "rollback", "revision": rev})
    else:
        template: dict[str, Any] = {}
        if patches:
            template["spec"] = {"containers": patches}
        if ann_undo:
            template["metadata"] = {"annotations": ann_undo}
        if template:
            inverse.append({"op": "patch", "body": {"spec": {"template": template}}})

    if old.get("spec", {}).get("replicas") != new.get("spec", {}).get("replicas"):
        diff["replicas"] = {"old": old["spec"].get("replicas"), "new": new["spec"].get("replicas")}
        inverse.append({"op": "scale", "replicas": old["spec"].get("replicas")})
        kinds.add("replicas")

    if not diff:
        return None
    return next(k for k in KIND_ORDER if k in kinds), diff, inverse


def _flags(text: str | None) -> dict | None:
    try:
        doc = json.loads(text or "")
    except ValueError:
        return None
    return doc.get("flags") if isinstance(doc, dict) and isinstance(doc.get("flags"), dict) else None


# flagd file: name the flags whose defaultVariant moved, so a revert touches only those (§6.2.5)
def _flag_changes(od: dict, nd: dict, undo: dict) -> tuple[dict, list] | None:
    diff, inverse = {}, []
    for key in sorted(undo):
        of, nf = _flags(od.get(key)), _flags(nd.get(key))
        if of is None or nf is None or of.keys() != nf.keys():
            return None  # flag added/removed or not flagd JSON: fall back to the whole key
        for name in sorted(of):
            a, b = of[name].get("defaultVariant"), nf[name].get("defaultVariant")
            if a != b:
                diff[f"flags[{name}].defaultVariant"] = {"old": a, "new": b}
                inverse.append({"op": "flag", "key": key, "flag": name, "defaultVariant": a})
    return (diff, inverse) if diff else None


def _configmap_changes(old: dict, new: dict, is_flags: bool) -> tuple[str, dict, list] | None:
    od, nd = old.get("data") or {}, new.get("data") or {}
    undo = _undo_map(od, nd)
    if not undo:
        return None
    if is_flags and (flagged := _flag_changes(od, nd, undo)):
        return "flag", *flagged
    diff = {f"data[{k}]": {"old": od.get(k), "new": nd.get(k)} for k in sorted(undo)}
    return ("flag" if is_flags else "configmap"), diff, [{"op": "patch", "body": {"data": undo}}]


# newest writer wins; status writes come from controllers, not people, so skip them
def author(obj: dict) -> str | None:
    fields: list[dict[str, Any]] = [m for m in obj.get("metadata", {}).get("managedFields") or [] if m.get("subresource") != "status"]
    return max(fields, key=lambda m: m.get("time") or "", default={}).get("manager")


# one MODIFIED event -> journal row, or None when nothing we track changed
def entry(resource: str, old: dict, new: dict, now: float, flag_configmap: str) -> dict | None:
    name = new["metadata"]["name"]
    if resource == "deployment":
        changes = _deployment_changes(old, new)
    else:
        changes = _configmap_changes(old, new, name == flag_configmap)
    if changes is None:
        return None
    kind, diff, inverse = changes
    manager = author(new)
    return {"ts": now, "kind": kind, "object": f"{resource}/{name}", "field_manager": manager,
            "resource_version": new["metadata"].get("resourceVersion"), "diff": diff, "inverse": inverse,
            "by_agent": manager == AGENT_MANAGER}


# read a diff path ("containers[payment].image", "replicas", "data[k]") off a live object
def current(obj: dict, path: str):
    if path == "replicas":
        return obj.get("spec", {}).get("replicas")
    if path == "containers":
        return sorted(_containers(obj))
    if path.startswith("data["):
        return (obj.get("data") or {}).get(path[5:-1])
    if path.startswith("flags["):
        name = path[len("flags["):].split("]", 1)[0]
        for text in (obj.get("data") or {}).values():
            if (flags := _flags(text)) and name in flags:
                return flags[name].get("defaultVariant")
        return None
    if path.startswith("annotations["):
        return (_template(obj).get("metadata", {}).get("annotations") or {}).get(path[12:-1])
    name, field = path[len("containers["):].split("].", 1)
    c = _containers(obj).get(name, {})
    return c.get(field) or ({} if field == "resources" else [] if field == "env" else None)


# env is compared var by var: only the vars this entry changed, so an unrelated later var changes nothing
def _env_live(old: list, new: list, now: list) -> bool:
    o, n, live = ({e["name"]: e for e in env or []} for env in (old, new, now))
    return all(live.get(k) == n.get(k) for k in o.keys() | n.keys() if o.get(k) != n.get(k))


# is the change this entry recorded still what the cluster runs? (freshness step 3)
def still_live(e: dict, obj: dict) -> bool:
    return all(_env_live(d["old"], d["new"], current(obj, p)) if p.endswith("].env") else current(obj, p) == d["new"]
               for p, d in e["diff"].items())


def insert(conn: sqlite3.Connection, e: dict) -> int:
    cur = conn.execute(
        "INSERT INTO journal (ts, kind, object, field_manager, resource_version, diff_json, inverse_json, by_agent)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (e["ts"], e["kind"], e["object"], e["field_manager"], e["resource_version"],
         json.dumps(e["diff"], sort_keys=True), json.dumps(e["inverse"], sort_keys=True), int(e["by_agent"])))
    conn.commit()
    return cast(int, cur.lastrowid)


# backs GET /journal?since=&object=
def read(conn: sqlite3.Connection, since: float = 0, obj: str | None = None) -> list[dict]:
    sql = "SELECT * FROM journal WHERE ts >= ?"
    args: list[Any] = [since]
    if obj:
        sql += " AND object = ?"
        args.append(obj)
    rows = conn.execute(sql + " ORDER BY ts, id", args).fetchall()
    return [{**dict(r), "diff": json.loads(r["diff_json"]), "inverse": json.loads(r["inverse_json"]),
             "by_agent": bool(r["by_agent"])} for r in rows]
