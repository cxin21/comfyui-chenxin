import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import runtime.execution as execution_module
from runtime.contracts import content_hash
from runtime.execution import (
    ExecutionError,
    approve_execution_draft,
    build_approval_consumption,
    build_execution_draft,
    build_run_record,
)
from runtime.workflow_profile import structure_fingerprint


FIXTURES = Path(__file__).parent / "fixtures"
CONSUMPTION_ROOT = Path(__file__).parent.resolve()
NOW = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
UI_FINGERPRINT = "82a18f487fa7a5e3e5387db598e7e039a7842e6989092731eda5c5d927693a43"
API_GRAPH_HASH = "4a748ab19b5174f0569d3d6aa2480ff2117dbc3a209cb7cb27699ac105a4b1e5"


def ready_build():
    return {
        "schema_version": "1.0",
        "target": "image",
        "generation_mode": "text-to-image",
        "model_id": "anima",
        "dialect": "tags",
        "prompt": "score_9, 1girl, solo, from_front, full_body",
        "negative_prompt": "worst quality, low quality, watermark",
        "validated_tags": ["1girl", "solo", "from_front", "full_body"],
        "rejected_tags": [],
        "recipe_control_tokens": ["score_9"],
        "locked_facts": ["1girl"],
        "ready_to_execute": True,
        "execution": {"requested": True, "performed": False},
    }


def profile():
    return {
        "schema_version": "1.0",
        "profile_id": "camera-anima-v1",
        "runtime_classification": "local",
        "allowed_mutations": ["untrusted.profile.value"],
        "slots": {
            "positive_prompt": {
                "id": 24,
                "type": "ImpactWildcardProcessor",
                "title": "POSITIVE",
            },
            "negative_prompt": {
                "id": 25,
                "type": "ImpactWildcardProcessor",
                "title": "NEGATIVE",
            },
            "camera_angle": {"id": 583},
        },
        "expected_outputs": ["image/png"],
    }


def capability_report(**overrides):
    report = {
        "schema_version": "1.0",
        "comfyui": {"url": "http://127.0.0.1:8188", "reachable": True},
        "adapter": {"runtime_classification": "local", "tools": []},
        "queue": {"running": 0, "pending": 0},
        "generated_at": NOW.isoformat().replace("+00:00", "Z"),
        "valid_until": (NOW + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
    }
    report.update(overrides)
    return report


def ui_workflow():
    return json.loads((FIXTURES / "camera-ui-minimal.json").read_text(encoding="utf-8"))


def api_graph():
    return json.loads((FIXTURES / "camera-api-minimal.json").read_text(encoding="utf-8"))


def executable_graph(build=None, graph=None):
    build = build or ready_build()
    graph = copy.deepcopy(api_graph() if graph is None else graph)
    graph["24"]["inputs"]["wildcard_text"] = build["prompt"]
    graph["24"]["inputs"]["populated_text"] = build["prompt"]
    graph["25"]["inputs"]["wildcard_text"] = build["negative_prompt"]
    graph["25"]["inputs"]["populated_text"] = build["negative_prompt"]
    return graph


def exact_patches(build=None):
    build = build or ready_build()
    return [
        {"slot": "positive_prompt", "input": "wildcard_text", "value": build["prompt"]},
        {"slot": "positive_prompt", "input": "populated_text", "value": build["prompt"]},
        {"slot": "negative_prompt", "input": "wildcard_text", "value": build["negative_prompt"]},
        {"slot": "negative_prompt", "input": "populated_text", "value": build["negative_prompt"]},
    ]


def plan_kwargs(**overrides):
    report = overrides.pop("capability_report", capability_report())
    selected_profile = overrides.pop("profile", profile())
    values = {
        "capability_report": report,
        "profile": selected_profile,
        "actual_ui_workflow": ui_workflow(),
        "api_graph": api_graph(),
    }
    values.update(overrides)
    return values


@pytest.fixture(autouse=True)
def trusted_utc_clock(monkeypatch):
    monkeypatch.setattr(execution_module, "_utc_now", lambda: NOW, raising=False)


def build_valid_draft(build=None, patches=None, **kwargs):
    build = build or ready_build()
    return build_execution_draft(
        "character-base",
        build,
        "camera-anima-v1",
        UI_FINGERPRINT,
        exact_patches(build) if patches is None else patches,
        **plan_kwargs(**kwargs),
    )


def approval_event(draft, **overrides):
    event = {
        "decision": "approved",
        "draft_hash": draft["draft_hash"],
        "displayed_at": (NOW - timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        "approved_at": (NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "scope": "enqueue-once",
        "consumption_root": str(CONSUMPTION_ROOT),
        "actor": "user:test",
        "source": "test-fixture",
    }
    event.update(overrides)
    return event


def build_valid_plan(build=None, patches=None, **kwargs):
    draft = build_valid_draft(build, patches, **kwargs)
    event = approval_event(draft)
    return approve_execution_draft(
        draft,
        event,
        consumption_root=event["consumption_root"],
    )


def task_context():
    return {
        "schema_version": "1.0",
        "shared_known": {
            "goal": "render a character base",
            "background": [],
            "acceptance": [],
            "boundaries": [],
        },
        "user_known_agent_unknown": {
            "references": [],
            "aesthetic_preferences": [],
            "real_world_constraints": [],
        },
        "agent_known_user_unknown": {"capabilities": [], "risks": [], "alternatives": []},
        "shared_unknown": {"hypotheses": [], "experiments": []},
    }


def history_response(graph=None, *, prompt_id="prompt-123", status="succeeded"):
    graph = executable_graph() if graph is None else graph
    if status == "succeeded":
        raw_status = {"status_str": "success", "completed": True, "messages": []}
        outputs = {
            "900": {
                "images": [
                    {"filename": "character.png", "subfolder": "run-123", "type": "output"}
                ]
            }
        }
    elif status == "failed":
        raw_status = {"status_str": "error", "completed": False, "messages": []}
        outputs = {}
    else:
        raw_status = {"status_str": "cancelled", "completed": False, "messages": []}
        outputs = {}
    return {
        prompt_id: {
            "prompt": [7, prompt_id, copy.deepcopy(graph), {"client_id": "test"}, ["900"]],
            "outputs": outputs,
            "status": raw_status,
        }
    }


def test_draft_does_not_accept_caller_approval_boolean():
    with pytest.raises(TypeError):
        build_execution_draft(
            "character-base", ready_build(), "camera-anima-v1", "abc", [], False
        )


def test_character_base_plan_requires_exact_prompt_derived_patch_set():
    build = ready_build()
    invalid = []
    invalid.append(exact_patches(build)[:-1])
    invalid.append(exact_patches(build) + [copy.deepcopy(exact_patches(build)[0])])
    wrong_value = exact_patches(build)
    wrong_value[0]["value"] = "attacker supplied prompt"
    invalid.append(wrong_value)
    extra = exact_patches(build)
    extra.append({"slot": "positive_prompt", "input": "seed", "value": 1})
    invalid.append(extra)

    for patch_set in invalid:
        with pytest.raises(ExecutionError, match="exact.*patch"):
            build_valid_plan(build, patch_set)


def test_character_base_contract_is_not_defined_by_profile_allowlist():
    result = build_valid_draft()
    assert [f"{item['slot']}.{item['input']}" for item in result["patches"]] == [
        "positive_prompt.wildcard_text",
        "positive_prompt.populated_text",
        "negative_prompt.wildcard_text",
        "negative_prompt.populated_text",
    ]


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda p: p.update(profile_id="other"), "profile"),
        (lambda p: p.update(runtime_classification="paid"), "local"),
        (lambda p: p.update(expected_outputs=["text/plain"]), "image/png"),
        (lambda p: p["slots"]["positive_prompt"].update(id=26), "slot"),
    ],
)
def test_character_base_rejects_profile_contract_drift(mutate, match):
    selected = profile()
    mutate(selected)
    with pytest.raises(ExecutionError, match=match):
        build_valid_plan(profile=selected)


def test_plan_recomputes_ui_fingerprint_and_api_graph_hash():
    changed_ui = ui_workflow()
    changed_ui["nodes"][0]["type"] = "OtherNode"
    with pytest.raises(ExecutionError, match="slot"):
        build_valid_plan(actual_ui_workflow=changed_ui)

    changed_graph = api_graph()
    del changed_graph["24"]["inputs"]["populated_text"]
    with pytest.raises(ExecutionError, match="populated_text"):
        build_valid_plan(api_graph=changed_graph)


def test_plan_records_complete_lineage_and_self_hash_without_mutating_inputs():
    build = ready_build()
    patch_values = exact_patches(build)
    kwargs = plan_kwargs()
    before = copy.deepcopy((build, patch_values, kwargs))
    result = build_execution_draft(
        "character-base", build, "camera-anima-v1", UI_FINGERPRINT,
        patch_values, **kwargs,
    )
    assert (build, patch_values, kwargs) == before
    assert result["prompt_build_id"] == content_hash(build)
    assert result["source_api_graph_hash"] == API_GRAPH_HASH
    assert result["executable_api_graph_hash"] == content_hash(executable_graph(build))
    assert result["capability_report_hash"] == content_hash(kwargs["capability_report"])
    assert result["profile_hash"] == content_hash(kwargs["profile"])
    assert result["preflight"] == {
        "workflow": {
            "verified": True,
            "fingerprint": UI_FINGERPRINT,
            "slots": {"positive_prompt": 24, "negative_prompt": 25},
        },
        "api_graph": {
            "verified": True,
            "source_hash": API_GRAPH_HASH,
            "executable_hash": content_hash(executable_graph(build)),
        },
        "capability": {
            "verified": True,
            "report_hash": content_hash(kwargs["capability_report"]),
        },
        "profile": {"verified": True, "hash": content_hash(kwargs["profile"])},
    }
    assert result["plan_state"] == "draft"
    assert result["execution_approved"] is False
    unsigned = dict(result)
    del unsigned["draft_hash"]
    assert result["draft_hash"] == content_hash(unsigned)


def test_approval_binds_exact_displayed_draft_and_hashes_event_and_plan():
    draft = build_valid_draft()
    event = approval_event(draft)

    plan = approve_execution_draft(
        draft,
        event,
        consumption_root=event["consumption_root"],
    )

    assert plan["plan_state"] == "approved"
    assert plan["execution_approved"] is True
    assert plan["draft_hash"] == draft["draft_hash"]
    assert plan["approval_event"] == event
    assert plan["approval_id"] == content_hash(event)
    unsigned = dict(plan)
    del unsigned["plan_hash"]
    assert plan["plan_hash"] == content_hash(unsigned)


def test_approval_requires_exact_existing_canonical_consumption_root(tmp_path):
    draft = build_valid_draft()
    root = tmp_path / "runs"
    root.mkdir()
    event = approval_event(draft, consumption_root=str(root.resolve()))

    plan = approve_execution_draft(draft, event, consumption_root=root.resolve())

    assert plan["approval_event"]["consumption_root"] == str(root.resolve())

    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ExecutionError, match="consumption root"):
        approve_execution_draft(draft, event, consumption_root=other.resolve())
    with pytest.raises(ExecutionError, match="consumption root"):
        approve_execution_draft(
            draft,
            approval_event(draft, consumption_root="relative/runs"),
            consumption_root=root.resolve(),
        )
    missing = tmp_path / "missing"
    with pytest.raises(ExecutionError, match="existing"):
        approve_execution_draft(
            draft,
            approval_event(draft, consumption_root=str(missing)),
            consumption_root=missing,
        )


def test_approval_rejects_symlink_consumption_root_alias(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    alias = tmp_path / "runs-alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    draft = build_valid_draft()
    event = approval_event(draft, consumption_root=str(alias))

    with pytest.raises(ExecutionError, match="canonical|alias|consumption root"):
        approve_execution_draft(draft, event, consumption_root=alias)


@pytest.mark.parametrize(
    "event_changes, match",
    [
        ({"draft_hash": "0" * 64}, "draft_hash"),
        ({"decision": "rejected"}, "decision"),
        ({"scope": "enqueue-many"}, "scope"),
        ({"actor": ""}, "actor"),
        ({"source": ""}, "source"),
        ({"unexpected": True}, "schema"),
        ({"displayed_at": "2026-08-03T00:00:00+08:00"}, "UTC"),
        ({"approved_at": "2026-08-02T23:57:00Z"}, "order"),
        ({"expires_at": "2026-08-03T00:00:00Z"}, "expired"),
        ({"expires_at": "2026-08-03T00:09:00Z"}, "600"),
    ],
)
def test_approval_rejects_wrong_or_stale_event(event_changes, match):
    draft = build_valid_draft()
    with pytest.raises(ExecutionError, match=match):
        event = approval_event(draft, **event_changes)
        approve_execution_draft(
            draft,
            event,
            consumption_root=event.get("consumption_root", CONSUMPTION_ROOT),
        )


def test_approval_rejects_modified_or_stale_hashed_draft():
    draft = build_valid_draft()
    draft["patches"][0]["value"] = "modified after display"
    event = approval_event(draft)
    with pytest.raises(ExecutionError, match="draft_hash"):
        approve_execution_draft(
            draft,
            event,
            consumption_root=event["consumption_root"],
        )


def test_approval_rejects_event_with_missing_required_field():
    draft = build_valid_draft()
    event = approval_event(draft)
    event.pop("actor")
    with pytest.raises(ExecutionError, match="schema"):
        approve_execution_draft(
            draft,
            event,
            consumption_root=event["consumption_root"],
        )


def test_approval_consumption_is_bound_to_plan_and_stable_enqueue_request():
    plan = build_valid_plan()

    consumption = build_approval_consumption(plan, "request-b-123")

    assert consumption["approval_id"] == plan["approval_id"]
    assert consumption["plan_hash"] == plan["plan_hash"]
    assert consumption["draft_hash"] == plan["draft_hash"]
    assert consumption["consumption_root"] == plan["approval_event"]["consumption_root"]
    assert consumption["enqueue_request_id"] == "request-b-123"
    assert consumption["consumed_at"] == "2026-08-03T00:00:00Z"
    unsigned = dict(consumption)
    unsigned.pop("consumption_id")
    assert consumption["consumption_id"] == content_hash(unsigned)


def test_approval_consumption_rejects_expired_or_tampered_plan(monkeypatch):
    plan = build_valid_plan()
    monkeypatch.setattr(
        execution_module,
        "_utc_now",
        lambda: NOW + timedelta(minutes=6),
    )
    with pytest.raises(ExecutionError, match="expired"):
        build_approval_consumption(plan, "request-b-123")

    monkeypatch.setattr(execution_module, "_utc_now", lambda: NOW)
    tampered = copy.deepcopy(plan)
    tampered["approval_id"] = "0" * 64
    with pytest.raises(ExecutionError, match="approval_id"):
        build_approval_consumption(tampered, "request-b-123")

    with pytest.raises(ExecutionError, match="request"):
        build_approval_consumption(plan, " ")


def test_run_record_requires_valid_task_context_before_lineage_checks():
    plan = build_valid_plan()
    with pytest.raises(ExecutionError, match="TaskContext"):
        build_run_record(
            {}, ready_build(), api_graph(), plan, "prompt-123", "failed", {}, {},
            history=history_response(status="failed"),
        )


@pytest.mark.parametrize("mutation, match", [
    (lambda p: p.update(prompt_build_id="0" * 64), "draft_hash"),
    (lambda p: p.update(source_api_graph_hash="0" * 64), "draft_hash"),
    (lambda p: p.update(executable_api_graph_hash="0" * 64), "draft_hash"),
    (lambda p: p.pop("profile_hash"), "lineage"),
    (lambda p: p.update(approval_id="0" * 64), "approval_id"),
    (lambda p: p.update(plan_hash="0" * 64), "plan_hash"),
])
def test_run_record_rejects_incomplete_or_forged_plan(mutation, match):
    plan = build_valid_plan()
    mutation(plan)
    with pytest.raises(ExecutionError, match=match):
        build_run_record(
            task_context(), ready_build(), api_graph(), plan, "prompt-123", "failed", {}, {},
            history=history_response(status="failed"),
        )


def test_run_record_rejects_history_prompt_graph_mismatch():
    plan = build_valid_plan()
    outputs = {"character.png": content_hash("png")}
    other_graph = api_graph()
    other_graph["24"]["inputs"]["seed"] = 999
    with pytest.raises(ExecutionError, match="history.*graph"):
        build_run_record(
            task_context(), ready_build(), api_graph(), plan, "prompt-123", "succeeded",
            {}, outputs, history=history_response(other_graph),
        )


def test_run_record_rejects_output_hash_name_not_present_in_history():
    plan = build_valid_plan()
    with pytest.raises(ExecutionError, match="filename"):
        build_run_record(
            task_context(), ready_build(), api_graph(), plan, "prompt-123", "succeeded",
            {}, {"other.png": content_hash("png")}, history=history_response(),
        )


def test_run_record_derives_performed_from_matching_history_and_hashes_record():
    build = ready_build()
    graph = api_graph()
    plan = build_valid_plan(build)
    outputs = {"character.png": content_hash("png")}
    record = build_run_record(
        task_context(), build, graph, plan, "prompt-123", "succeeded", {}, outputs,
        history=history_response(),
    )
    assert record["history_verified"] is True
    assert record["artifact_hashes_verified"] is False
    assert record["history_outputs"] == [
        {
            "node_id": "900",
            "filename": "character.png",
            "subfolder": "run-123",
            "type": "output",
        }
    ]
    assert "execution_performed" not in record
    assert build["execution"]["performed"] is False
    unsigned = dict(record)
    del unsigned["record_hash"]
    assert record["record_hash"] == content_hash(unsigned)


def test_run_record_requires_explicit_retained_artifact_when_history_has_previews():
    build = ready_build()
    graph = api_graph()
    plan = build_valid_plan(build)
    history = history_response()
    history["prompt-123"]["outputs"]["901"] = {
        "images": [
            {"filename": "preview.png", "subfolder": "", "type": "temp"},
        ]
    }
    output_hashes = {
        "character.png": "a" * 64,
        "preview.png": "b" * 64,
    }
    with pytest.raises(ExecutionError, match="explicit artifact_descriptor"):
        build_run_record(
            task_context(), build, graph, plan, "prompt-123", "succeeded", {},
            output_hashes, history=history,
        )

    descriptor = {
        "node_id": "900",
        "filename": "character.png",
        "subfolder": "run-123",
        "type": "output",
    }
    record = build_run_record(
        task_context(), build, graph, plan, "prompt-123", "succeeded", {},
        output_hashes, history=history, artifact_descriptor=descriptor,
    )
    assert record["artifact_descriptor"] == descriptor


def test_comfy_history_error_status_characterizes_failed_terminal_record():
    build = ready_build()
    graph = api_graph()
    plan = build_valid_plan(build)
    record = build_run_record(
        task_context(), build, graph, plan, "prompt-123", "failed", {}, {},
        history=history_response(status="failed"),
    )
    assert record["history_status"] == {"status_str": "error", "completed": False}
    assert record["history_verified"] is True


def test_cancelled_is_rejected_without_a_distinct_comfy_history_status():
    build = ready_build()
    graph = api_graph()
    plan = build_valid_plan(build)
    with pytest.raises(ExecutionError, match="cancel"):
        build_run_record(
            task_context(), build, graph, plan, "prompt-123", "cancelled", {}, {},
            history=history_response(status="cancelled"),
        )


def test_plan_rejects_non_object_api_graph():
    with pytest.raises(ExecutionError, match="API graph"):
        build_valid_plan(api_graph=None)


def test_plan_rejects_arbitrary_ui_even_with_self_consistent_fingerprint_and_preflight():
    arbitrary_ui = {"nodes": [], "groups": [], "links": []}
    forged_fingerprint = structure_fingerprint(arbitrary_ui)
    with pytest.raises(ExecutionError, match="slot"):
        build_execution_draft(
            "character-base", ready_build(), "camera-anima-v1", forged_fingerprint,
            exact_patches(), capability_report=capability_report(), profile=profile(),
            actual_ui_workflow=arbitrary_ui,
            api_graph=api_graph(),
        )


def test_plan_rejects_profile_and_ui_that_self_certify_attacker_slot_type():
    selected_profile = profile()
    selected_profile["slots"]["positive_prompt"] = {
        "id": 24,
        "type": "AttackerNode",
        "title": "EVIL",
    }
    attacker_ui = ui_workflow()
    attacker_ui["nodes"][0]["type"] = "AttackerNode"
    attacker_ui["nodes"][0]["title"] = "EVIL"
    with pytest.raises(ExecutionError, match="slot.*positive_prompt"):
        build_execution_draft(
            "character-base", ready_build(), "camera-anima-v1",
            structure_fingerprint(attacker_ui), exact_patches(),
            capability_report=capability_report(), profile=selected_profile,
            actual_ui_workflow=attacker_ui, api_graph=api_graph(),
        )


def test_run_record_rejects_caller_constructed_terminal_claim():
    build = ready_build()
    plan = build_valid_plan(build)
    outputs = {"character.png": content_hash("png")}
    with pytest.raises(TypeError):
        build_run_record(
            task_context(), build, api_graph(), plan, "prompt-123", "succeeded", {}, outputs,
            terminal_evidence={"source": "comfyui_history"},
        )


def test_plan_public_api_does_not_accept_caller_controlled_clock():
    kwargs = plan_kwargs()
    with pytest.raises(TypeError):
        build_execution_draft(
            "character-base", ready_build(), "camera-anima-v1", UI_FINGERPRINT,
            exact_patches(), now=NOW, **kwargs,
        )


def test_run_record_rejects_from_scratch_self_hashed_attacker_profile_plan():
    build = ready_build()
    graph = api_graph()
    attacker_plan = {
        "schema_version": "1.0",
        "stage": "character-base",
        "plan_state": "approved",
        "prompt_build_id": content_hash(build),
        "capability_report_hash": "1" * 64,
        "workflow_profile_id": "attacker-profile",
        "profile_hash": "2" * 64,
        "workflow_fingerprint": "3" * 64,
        "source_api_graph_hash": content_hash(graph),
        "executable_api_graph_hash": content_hash(executable_graph(build, graph)),
        "patches": exact_patches(build),
        "immutable_inputs": [],
        "local_only": True,
        "preflight": {
            "workflow": {
                "verified": True,
                "fingerprint": "3" * 64,
                "slots": {"positive_prompt": 24, "negative_prompt": 25},
            },
            "api_graph": {
                "verified": True,
                "source_hash": content_hash(graph),
                "executable_hash": content_hash(executable_graph(build, graph)),
            },
            "capability": {"verified": True, "report_hash": "1" * 64},
            "profile": {"verified": True, "hash": "2" * 64},
        },
        "expected_outputs": ["image/png"],
        "execution_approved": True,
        "draft_hash": "4" * 64,
        "approval_event": {
            "decision": "approved",
            "draft_hash": "4" * 64,
            "displayed_at": "2026-08-02T23:58:00Z",
            "approved_at": "2026-08-02T23:59:00Z",
            "expires_at": "2026-08-03T00:05:00Z",
            "scope": "enqueue-once",
            "consumption_root": str(CONSUMPTION_ROOT),
            "actor": "attacker",
            "source": "attacker",
        },
    }
    attacker_plan["approval_id"] = content_hash(attacker_plan["approval_event"])
    attacker_plan["plan_hash"] = content_hash(attacker_plan)
    with pytest.raises(ExecutionError, match="profile"):
        build_run_record(
            task_context(), build, graph, attacker_plan, "prompt-123", "failed", {}, {},
            history=history_response(status="failed"),
        )


def test_run_record_rejects_self_hashed_plan_over_empty_api_graph():
    build = ready_build()
    empty_graph = {}
    plan = build_valid_plan(build)
    plan["source_api_graph_hash"] = content_hash(empty_graph)
    plan["executable_api_graph_hash"] = content_hash(empty_graph)
    plan["preflight"]["api_graph"]["source_hash"] = content_hash(empty_graph)
    plan["preflight"]["api_graph"]["executable_hash"] = content_hash(empty_graph)
    draft = {
        key: copy.deepcopy(value)
        for key, value in plan.items()
        if key not in {"approval_event", "approval_id", "plan_hash"}
    }
    draft["plan_state"] = "draft"
    draft["execution_approved"] = False
    draft.pop("draft_hash")
    plan["draft_hash"] = content_hash(draft)
    plan["approval_event"]["draft_hash"] = plan["draft_hash"]
    plan["approval_id"] = content_hash(plan["approval_event"])
    unsigned = dict(plan)
    unsigned.pop("plan_hash")
    plan["plan_hash"] = content_hash(unsigned)
    with pytest.raises(ExecutionError, match="API graph|missing API node"):
        build_run_record(
            task_context(), build, empty_graph, plan, "prompt-123", "failed", {}, {},
            history=history_response(empty_graph, status="failed"),
        )


def test_run_record_rejects_unpatched_source_graph_in_history():
    build = ready_build()
    source_graph = api_graph()
    plan = build_valid_plan(build)
    outputs = {"character.png": content_hash("png")}
    with pytest.raises(ExecutionError, match="executable|history.*graph"):
        build_run_record(
            task_context(), build, source_graph, plan, "prompt-123", "succeeded", {}, outputs,
            history=history_response(source_graph),
        )
