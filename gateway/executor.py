# writes with the agent identity (IMPLEMENTATION.md §6.4.7): Deployments, their scale, ConfigMap flagd-config.
import json
from typing import Any

from gateway.dryrun import FIELD_MANAGER, JSON_PATCH, MERGE, WriteRefused

NAMESPACE = "shop"
__all__ = ["WriteRefused", "classify", "patch_deployment", "patch_scale", "patch_configmap", "read_deployment",
           "read_configmap", "list_json"]


# what the API server says when a JSON Patch fails to apply; ours only fail on the generation `test`.
# Admission denials ("denied request: ...") and field errors ("... is invalid: ...") read differently
PATCH_NOT_APPLIED = "the server rejected our request due to an error in our request"


# 409 or a failed precondition test -> someone else changed it: hand off; RBAC/admission -> escalate
def classify(status: int, body: str) -> WriteRefused:
    if status == 409 or (status == 422 and PATCH_NOT_APPLIED in body):
        return WriteRefused("handed_off", f"object changed under us ({status})")
    if status in (403, 422):
        return WriteRefused("escalated", f"API server refused ({status}): {body[:300]}")
    return WriteRefused("escalated", f"API error {status}: {body[:300]}")


def _call(fn: Any, name: str, body: Any, dry_run: bool, content_type: str) -> dict:
    import urllib3
    from kubernetes.client.rest import ApiException

    try:
        resp = fn(name, NAMESPACE, body, dry_run="All" if dry_run else None, field_manager=FIELD_MANAGER,
                  _content_type=content_type, _preload_content=False)
    except ApiException as e:
        raise classify(e.status, str(e.body or e.reason)) from None
    except (urllib3.exceptions.HTTPError, OSError) as e:
        if dry_run:
            raise WriteRefused("escalated", f"Kubernetes API unreachable ({type(e).__name__})") from None
        # no answer to a real write: it may have landed. No receipt, no auto-undo: a human checks (Muaz chose)
        raise WriteRefused("escalated", f"write outcome unknown ({type(e).__name__}): the change may or may not "
                                        f"be live; check the cluster by hand") from None
    return json.loads(resp.data)


# dry_run=True asks the API server (and admission) without saving anything
def patch_deployment(apps: Any, name: str, body: Any, dry_run: bool, content_type: str = JSON_PATCH) -> dict:
    return _call(apps.patch_namespaced_deployment, name, body, dry_run, content_type)


def patch_scale(apps: Any, name: str, body: dict, dry_run: bool) -> dict:
    return _call(apps.patch_namespaced_deployment_scale, name, body, dry_run, MERGE)


# RBAC lets the agent patch only flagd-config; any other ConfigMap comes back 403 -> escalated
def patch_configmap(core: Any, name: str, body: dict, dry_run: bool) -> dict:
    return _call(core.patch_namespaced_config_map, name, body, dry_run, MERGE)


# reads fail as WriteRefused too, so every checklist caller ends the incident instead of crashing (HTTP 500)
def _read(fn: Any, *args: Any) -> Any:
    import urllib3
    from kubernetes.client.rest import ApiException

    try:
        return json.loads(fn(*args, NAMESPACE, _preload_content=False).data)
    except ApiException as e:
        raise classify(e.status, str(e.body or e.reason)) from None
    except (urllib3.exceptions.HTTPError, OSError) as e:
        raise WriteRefused("escalated", f"Kubernetes API unreachable ({type(e).__name__})") from None


def read_configmap(core: Any, name: str) -> dict:
    return _read(core.read_namespaced_config_map, name)


def read_deployment(apps: Any, name: str) -> dict:
    return _read(apps.read_namespaced_deployment, name)


def list_json(fn: Any) -> list[dict]:
    return _read(fn)["items"]
