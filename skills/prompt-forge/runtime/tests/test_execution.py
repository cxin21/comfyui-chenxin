import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import runtime.execution as execution_module
from runtime.contracts import content_hash
from runtime.execution import ExecutionError, build_execution_plan, build_run_record
from runtime.workflow_profile import structure_fingerprint


FIXTURES = Path(__file__).parent / "fixtures"
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


def build_valid_plan(build=None, patches=None, **kwargs):
    build = build or ready_build()
    return build_execution_plan(
        "character-base",
        build,
        "camera-anima-v1",
        UI_FINGERPRINT,
        exact_patches(build) if patches is None else patches,
        True,
        **plan_kwargs(**kwargs),
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
    graph = api_graph() if graph is None else graph
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


def test_plan_requires_current_approval_before_other_runtime_inputs():
    with pytest.raises(ExecutionError, match="approval"):
        build_execution_plan("character-base", ready_build(), "camera-anima-v1", "abc", [], False)


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
    result = build_valid_plan()
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
    result = build_execution_plan(
        "character-base", build, "camera-anima-v1", UI_FINGERPRINT,
        patch_values, True, **kwargs,
    )
    assert (build, patch_values, kwargs) == before
    assert result["prompt_build_id"] == content_hash(build)
    assert result["api_graph_hash"] == API_GRAPH_HASH
    assert result["capability_report_hash"] == content_hash(kwargs["capability_report"])
    assert result["profile_hash"] == content_hash(kwargs["profile"])
    assert result["preflight"] == {
        "workflow": {
            "verified": True,
            "fingerprint": UI_FINGERPRINT,
            "slots": {"positive_prompt": 24, "negative_prompt": 25},
        },
        "api_graph": {"verified": True, "hash": API_GRAPH_HASH},
        "capability": {
            "verified": True,
            "report_hash": content_hash(kwargs["capability_report"]),
        },
        "profile": {"verified": True, "hash": content_hash(kwargs["profile"])},
    }
    unsigned = dict(result)
    del unsigned["plan_hash"]
    assert result["plan_hash"] == content_hash(unsigned)


def test_run_record_requires_valid_task_context_before_lineage_checks():
    plan = build_valid_plan()
    with pytest.raises(ExecutionError, match="TaskContext"):
        build_run_record(
            {}, ready_build(), api_graph(), plan, "prompt-123", "failed", {}, {},
            history=history_response(status="failed"),
        )


@pytest.mark.parametrize("mutation, match", [
    (lambda p: p.update(prompt_build_id="0" * 64), "prompt_build_id"),
    (lambda p: p.update(api_graph_hash="0" * 64), "api_graph_hash"),
    (lambda p: p.pop("profile_hash"), "lineage"),
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
        history=history_response(graph),
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


def test_comfy_history_error_status_characterizes_failed_terminal_record():
    build = ready_build()
    graph = api_graph()
    plan = build_valid_plan(build)
    record = build_run_record(
        task_context(), build, graph, plan, "prompt-123", "failed", {}, {},
        history=history_response(graph, status="failed"),
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
            history=history_response(graph, status="cancelled"),
        )


def test_plan_rejects_non_object_api_graph():
    with pytest.raises(ExecutionError, match="API graph"):
        build_valid_plan(api_graph=None)


def test_plan_rejects_arbitrary_ui_even_with_self_consistent_fingerprint_and_preflight():
    arbitrary_ui = {"nodes": [], "groups": [], "links": []}
    forged_fingerprint = structure_fingerprint(arbitrary_ui)
    with pytest.raises(ExecutionError, match="slot"):
        build_execution_plan(
            "character-base", ready_build(), "camera-anima-v1", forged_fingerprint,
            exact_patches(), True, capability_report=capability_report(), profile=profile(),
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
        build_execution_plan(
            "character-base", ready_build(), "camera-anima-v1",
            structure_fingerprint(attacker_ui), exact_patches(), True,
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
        build_execution_plan(
            "character-base", ready_build(), "camera-anima-v1", UI_FINGERPRINT,
            exact_patches(), True, now=NOW, **kwargs,
        )


def test_run_record_rejects_from_scratch_self_hashed_attacker_profile_plan():
    build = ready_build()
    graph = api_graph()
    attacker_plan = {
        "schema_version": "1.0",
        "stage": "character-base",
        "prompt_build_id": content_hash(build),
        "capability_report_hash": "1" * 64,
        "workflow_profile_id": "attacker-profile",
        "profile_hash": "2" * 64,
        "workflow_fingerprint": "3" * 64,
        "api_graph_hash": content_hash(graph),
        "patches": exact_patches(build),
        "immutable_inputs": [],
        "local_only": True,
        "preflight": {
            "workflow": {
                "verified": True,
                "fingerprint": "3" * 64,
                "slots": {"positive_prompt": 24, "negative_prompt": 25},
            },
            "api_graph": {"verified": True, "hash": content_hash(graph)},
            "capability": {"verified": True, "report_hash": "1" * 64},
            "profile": {"verified": True, "hash": "2" * 64},
        },
        "expected_outputs": ["image/png"],
        "execution_approved": True,
    }
    attacker_plan["plan_hash"] = content_hash(attacker_plan)
    with pytest.raises(ExecutionError, match="profile"):
        build_run_record(
            task_context(), build, graph, attacker_plan, "prompt-123", "failed", {}, {},
            history=history_response(graph, status="failed"),
        )


def test_run_record_rejects_self_hashed_plan_over_empty_api_graph():
    build = ready_build()
    empty_graph = {}
    plan = build_valid_plan(build)
    plan["api_graph_hash"] = content_hash(empty_graph)
    plan["preflight"]["api_graph"]["hash"] = content_hash(empty_graph)
    unsigned = dict(plan)
    unsigned.pop("plan_hash")
    plan["plan_hash"] = content_hash(unsigned)
    with pytest.raises(ExecutionError, match="API graph|missing API node"):
        build_run_record(
            task_context(), build, empty_graph, plan, "prompt-123", "failed", {}, {},
            history=history_response(empty_graph, status="failed"),
        )
