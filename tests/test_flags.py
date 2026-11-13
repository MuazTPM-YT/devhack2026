import asyncio
import copy
import json

import httpx

from brain.rules import match
from observer import journal
from test_gateway import FakeCore, Resp, World, action
from test_verify_loop import Script, healthy

FLAG_MAP = {"paymentFailure": "payment", "adFailure": "ad"}
POLICY = {"change_window_minutes": 10, "tools": {"raise_limit": {"max_memory": "1Gi"}}}
SERVICES = {"payment": {"kind": "stateless", "actable": True}, "ad": {"kind": "stateless", "actable": True}}


def flagd(payment="off", ad="off"):
    doc = {"flags": {"paymentFailure": {"variants": {"off": 0, "50%": 0.5}, "defaultVariant": payment},
                     "adFailure": {"variants": {"off": False, "on": True}, "defaultVariant": ad}}}
    return {"demo.flagd.json": json.dumps(doc)}


def cm(data, rv="7", manager="chaos-panel"):
    return {"metadata": {"name": "flagd-config", "resourceVersion": rv,
                         "managedFields": [{"manager": manager, "time": "2026-11-13T00:00:00Z"}]}, "data": data}


def flip_entry():
    e = journal.entry("configmap", cm(flagd()), cm(flagd(payment="50%"), "8"), 950.0, "flagd-config")
    return {**e, "id": 77}


def test_journal_names_the_flipped_flag():
    e = flip_entry()
    assert e["kind"] == "flag"
    assert e["diff"] == {"flags[paymentFailure].defaultVariant": {"old": "off", "new": "50%"}}
    assert e["inverse"] == [{"op": "flag", "key": "demo.flagd.json", "flag": "paymentFailure", "defaultVariant": "off"}]
    assert journal.current(cm(flagd(payment="50%")), "flags[paymentFailure].defaultVariant") == "50%"
    assert journal.still_live(e, cm(flagd(payment="50%"))) and not journal.still_live(e, cm(flagd()))


def test_non_flagd_text_falls_back_to_whole_key():
    e = journal.entry("configmap", cm({"x": "a"}), cm({"x": "b"}, "8"), 1.0, "flagd-config")
    assert e["kind"] == "flag" and list(e["diff"]) == ["data[x]"]


def test_rule_links_flag_to_its_service_only():
    inc = {"id": "inc-1", "culprit": "payment", "onset_at": 1000.0}
    pattern, actions = match(inc, [flip_entry()], [], SERVICES, POLICY, flag_map=FLAG_MAP)
    assert pattern == "recent_change"
    assert (actions[0]["tool"], actions[0]["journal_entry"]) == ("revert_config", 77)
    assert match({**inc, "culprit": "ad"}, [flip_entry()], [], SERVICES, POLICY, flag_map=FLAG_MAP)[0] == "unknown"
    assert match(inc, [flip_entry()], [], SERVICES, POLICY)[0] == "unknown"  # no map, no link


class FlagCore(FakeCore):
    def __init__(self, data, extra_on_dry=False):
        self.cm, self.patches, self.extra_on_dry = cm(data), [], extra_on_dry

    def read_namespaced_config_map(self, name, ns, **kw):
        assert name == "flagd-config"
        return Resp(self.cm)

    def patch_namespaced_config_map(self, name, ns, body, dry_run=None, field_manager=None, _content_type=None,
                                    _preload_content=True):
        assert body["metadata"]["resourceVersion"] == self.cm["metadata"]["resourceVersion"]
        self.patches.append({"dry_run": dry_run, "content_type": _content_type, "field_manager": field_manager})
        new = copy.deepcopy(self.cm)
        new["data"].update(body["data"])
        if dry_run and self.extra_on_dry:
            doc = json.loads(new["data"]["demo.flagd.json"])
            doc["flags"]["adFailure"]["defaultVariant"] = "on"
            new["data"]["demo.flagd.json"] = json.dumps(doc)
        if not dry_run:
            new["metadata"]["resourceVersion"] = str(int(self.cm["metadata"]["resourceVersion"]) + 1)
            self.cm = new
        return Resp(new)

    def list_namespaced_config_map(self, ns, **kw):
        return Resp({"items": [self.cm]})


def flag_world(tmp_path, **kw):
    w = World(tmp_path)
    w.core = FlagCore(flagd(payment="50%"), **kw)
    w.gw.core, w.gw.flag_map = w.core, FLAG_MAP
    w.obs.journal = [flip_entry()]
    return w


def flag_action():
    return action(tool="revert_config", journal_entry=77, evidence_ids=["journal:77"])


def payment_flag(w):
    return json.loads(w.core.cm["data"]["demo.flagd.json"])["flags"]["paymentFailure"]["defaultVariant"]


async def test_flag_revert_sets_only_that_flag_back(tmp_path):
    w = flag_world(tmp_path)
    w.gw.verify_every = 3600
    d = await w.gw.submit(flag_action())
    assert d.decision == "awaiting_approval"
    assert "flag paymentFailure -> off" in next(e for e in w.events if e["type"] == "approval_requested")["payload"]["diff"]
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "executed" and payment_flag(w) == "off"
    # dry run before asking, dry run again after approval, then the real write
    assert [(p["dry_run"], p["content_type"]) for p in w.core.patches] == \
        [("All", "application/merge-patch+json")] * 2 + [(None, "application/merge-patch+json")]
    assert w.core.patches[-1]["field_manager"] == "oncall-agent" and w.apps.patches == []
    inverse = json.loads(w.conn.execute("SELECT inverse_json FROM receipts").fetchone()[0])
    assert inverse["op"] == "restore_configmap"
    w.gw.undo("payment", inverse, pause=True)
    assert payment_flag(w) == "50%"
    for t in w.gw.tasks:
        t.cancel()


async def test_dry_run_moving_other_flags_escalates(tmp_path):
    w = flag_world(tmp_path, extra_on_dry=True)
    d = await w.gw.submit(flag_action())
    assert (d.decision, d.failed_step) == ("escalated", "dry_run") and "adFailure" in d.reason


async def test_flag_already_back_changes_nothing(tmp_path):
    w = flag_world(tmp_path)
    w.core.cm = cm(flagd())
    d = await w.gw.submit(flag_action())
    assert (d.decision, d.failed_step) == ("refused", "dry_run") and "already back" in d.reason
    assert w.core.patches == []


async def test_flag_revert_verifies_with_longer_window_and_configmap_harm_check(tmp_path):
    w = flag_world(tmp_path)
    script = Script(w, [healthy()])
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
    d = await w.gw.submit(flag_action())
    w.gw.verify_every = 0
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    script.active = True
    outcome = await asyncio.wait_for(next(iter(w.gw.tasks)), 5)
    assert outcome == "success"
    harm = next(e for e in w.events if e["type"] == "harm_check")["payload"]
    assert harm["clean"] and harm["declared_changed"] and harm["unexpected_changes"] == []


async def test_brain_flag_flip_proposes_flag_revert(tmp_path):
    from test_brain import INC, World as BrainWorld, diagnosis_json, make

    class FlagFlipWorld(BrainWorld):
        def __call__(self, request):
            if request.url.path == "/journal":
                return httpx.Response(200, json=[flip_entry()])
            return super().__call__(request)

    world = FlagFlipWorld()
    brain = make(world, [diagnosis_json(causes=[])], tmp_path)
    brain.flag_map = FLAG_MAP
    record = await brain.handle(INC)
    assert record["incident"]["culprit"] == "payment" and record["pattern"] == "recent_change"
    assert [(a.tool, a.journal_entry) for a in brain.submitted] == [("revert_config", 77)]


# flagd needs ~60 s, then the 1 m error window: a good flag revert can look sick for > 120 s
async def test_slow_flag_reload_is_not_undone_inside_the_extra_window(tmp_path):
    from test_verify_loop import sick
    w = flag_world(tmp_path)
    script = Script(w, [sick()] * 26 + [healthy()])  # 130 s sick, then fine
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
    d = await w.gw.submit(flag_action())
    w.gw.verify_every = 0
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    script.active = True
    outcome = await asyncio.wait_for(next(iter(w.gw.tasks)), 5)
    assert outcome in ("success", "right_by_accident") and payment_flag(w) == "off"
