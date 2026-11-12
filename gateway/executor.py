# writes with the agent identity (IMPLEMENTATION.md §6.4.7). Phase 1: rollback_deploy only.
import json
from typing import Any

from gateway.dryrun import FIELD_MANAGER, JSON_PATCH, MERGE, WriteRefused

NAMESPACE = "shop"
__all__ = ["WriteRefused", "classify", "patch_deployment", "patch_scale", "read_deployment", "list_json"]


# 409 or a failed resourceVersion test -> someone else changed it: hand off; RBAC/admission -> escalate
def classify(status: int, body: str) -> WriteRefused:
    if status == 409 or (status == 422 and "test" in body and "resourceVersion" in body):
        return WriteRefused("handed_off", f"object changed under us ({status})")
    if status in (403, 422):
        return WriteRefused("escalated", f"API server refused ({status}): {body[:300]}")
    return WriteRefused("escalated", f"API error {status}: {body[:300]}")


def _call(fn: Any, name: str, body: Any, dry_run: bool, content_type: str) -> dict:
    from kubernetes.client.rest import ApiException

    try:
        resp = fn(name, NAMESPACE, body, dry_run="All" if dry_run else None, field_manager=FIELD_MANAGER,
                  _content_type=content_type, _preload_content=False)
    except ApiException as e:
        raise classify(e.status, str(e.body or e.reason)) from None
    return json.loads(resp.data)


# dry_run=True asks the API server (and admission) without saving anything
def patch_deployment(apps: Any, name: str, body: Any, dry_run: bool, content_type: str = JSON_PATCH) -> dict:
    return _call(apps.patch_namespaced_deployment, name, body, dry_run, content_type)


def patch_scale(apps: Any, name: str, body: dict, dry_run: bool) -> dict:
    return _call(apps.patch_namespaced_deployment_scale, name, body, dry_run, MERGE)


def read_deployment(apps: Any, name: str) -> dict:
    return json.loads(apps.read_namespaced_deployment(name, NAMESPACE, _preload_content=False).data)


def list_json(fn: Any) -> list[dict]:
    return json.loads(fn(NAMESPACE, _preload_content=False).data)["items"]
