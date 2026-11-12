# watch Deployments, ConfigMaps, Pods in shop with the reader identity (IMPLEMENTATION.md §6.2.3).
# Objects stay API JSON (camelCase) end to end, as observer/journal.py expects.
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import datetime

from observer import journal

log = logging.getLogger("observer.watch")


def _ts(value: str | None) -> float | None:
    return datetime.fromisoformat(value).timestamp() if value else None


# ReplicaSet "payment-7d9f" -> Deployment "payment"; pods without a ReplicaSet owner are not ours
def service_of(pod: dict) -> str | None:
    for owner in pod["metadata"].get("ownerReferences") or []:
        if owner.get("kind") == "ReplicaSet":
            return owner["name"].rsplit("-", 1)[0]
    return None


# CrashLoopBackOff now, OOMKilled in the last 2 min, or NotReady for 30 s (§6.2.2 step 4)
def pod_bad(pod: dict, now: float) -> bool:
    if pod["metadata"].get("deletionTimestamp"):
        return False
    status = pod.get("status") or {}
    for c in status.get("containerStatuses") or []:
        if ((c.get("state") or {}).get("waiting") or {}).get("reason") == "CrashLoopBackOff":
            return True
        term = (c.get("lastState") or {}).get("terminated") or {}
        finished = _ts(term.get("finishedAt"))
        if term.get("reason") == "OOMKilled" and finished is not None and now - finished <= 120:
            return True
    for cond in status.get("conditions") or []:
        if cond.get("type") == "Ready" and cond.get("status") != "True":
            since = _ts(cond.get("lastTransitionTime"))
            if since is not None and now - since >= 30:
                return True
    return False


def bad_pods(pods: list[dict], now: float) -> dict[str, int]:
    out: dict[str, int] = {}
    for pod in pods:
        svc = service_of(pod)
        if svc and pod_bad(pod, now):
            out[svc] = out.get(svc, 0) + 1
    return out


class Tracker:
    def __init__(self, conn: sqlite3.Connection, flag_configmap: str, clock: Callable[[], float] = time.time):
        self.conn, self.flag_configmap, self.clock = conn, flag_configmap, clock
        self.objects: dict[tuple[str, str], dict] = {}
        self.pods: dict[str, dict] = {}
        self.lock = threading.Lock()

    # one watch/list item; a known object with a new resourceVersion is a change, even after a relist
    def handle(self, resource: str, etype: str, obj: dict) -> dict | None:
        name = obj["metadata"]["name"]
        with self.lock:
            if resource == "pod":
                if etype == "DELETED":
                    self.pods.pop(name, None)
                else:
                    self.pods[name] = obj
                return None
            key = (resource, name)
            if etype == "DELETED":
                self.objects.pop(key, None)
                return None
            old = self.objects.get(key)
            self.objects[key] = obj
            if old is None or old["metadata"].get("resourceVersion") == obj["metadata"].get("resourceVersion"):
                return None
            entry = journal.entry(resource, old, obj, self.clock(), self.flag_configmap)
            if entry:
                entry["id"] = journal.insert(self.conn, entry)
            return entry

    def bad_pods(self, now: float) -> dict[str, int]:
        with self.lock:
            pods = list(self.pods.values())
        return bad_pods(pods, now)


# list, then watch from that resourceVersion; any error -> pause and relist (Tracker spots missed changes)
def run_watch(list_fn: Callable, resource: str, tracker: Tracker, namespace: str, stop: threading.Event,
              sleep: Callable[[float], None] = time.sleep) -> None:
    from kubernetes import watch

    while not stop.is_set():
        try:
            data = json.loads(list_fn(namespace, _preload_content=False).data)
            for item in data["items"]:
                tracker.handle(resource, "ADDED", item)
            w = watch.Watch()
            for event in w.stream(list_fn, namespace, resource_version=data["metadata"]["resourceVersion"],
                                  timeout_seconds=300):
                tracker.handle(resource, event["type"], event["raw_object"])
                if stop.is_set():
                    w.stop()
        except Exception as e:  # network blip, 410 after retry, API restart: relist is always safe
            log.warning("watch %s failed: %s; relisting", resource, type(e).__name__)
            sleep(2)
