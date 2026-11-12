# writes with the agent identity (IMPLEMENTATION.md §6.4.7). Phase 1: rollback_deploy only.
import json
from typing import Any

from gateway.dryrun import FIELD_MANAGER, JSON_PATCH

NAMESPACE = "shop"


class WriteRefused(Exception):
    def __init__(self, outcome: str, reason: str):
        super().__init__(reason)
        self.outcome, self.reason = outcome, reason


# 409 or a failed resourceVersion test -> someone else changed it: hand off; RBAC/admission -> escalate
def classify(status: int, body: str) -> WriteRefused:
    if status == 409 or (status == 422 and "test" in body and "resourceVersion" in body):
        return WriteRefused("handed_off", f"object changed under us ({status})")
    if status in (403, 422):
        return WriteRefused("escalated", f"API server refused ({status}): {body[:300]}")
    return WriteRefused("escalated", f"API error {status}: {body[:300]}")


# dry_run=True asks the API server (and admission) without saving anything
def patch_deployment(apps: Any, name: str, patch: list[dict], dry_run: bool) -> dict:
    from kubernetes.client.rest import ApiException

    try:
        resp = apps.patch_namespaced_deployment(name, NAMESPACE, patch, dry_run="All" if dry_run else None,
                                                field_manager=FIELD_MANAGER, _content_type=JSON_PATCH,
                                                _preload_content=False)
    except ApiException as e:
        raise classify(e.status, str(e.body or e.reason)) from None
    return json.loads(resp.data)


def read_deployment(apps: Any, name: str) -> dict:
    return json.loads(apps.read_namespaced_deployment(name, NAMESPACE, _preload_content=False).data)


def list_json(fn: Any) -> list[dict]:
    return json.loads(fn(NAMESPACE, _preload_content=False).data)["items"]
