import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from runtime.contracts import content_hash
from runtime.execution import ExecutionError, build_execution_plan, build_run_record


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
            "positive_prompt": {"id": 24},
            "negative_prompt": {"id": 25},
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


def preflight(report=None, selected_profile=None):
    report = report or capability_report()
    selected_profile = selected_profile or profile()
    return {
        "nodes": {"status": "pass", "workflow_fingerprint": UI_FINGERPRINT},
        "models": {"status": "pass", "api_graph_hash": API_GRAPH_HASH},
        "resources": {"status": "pass", "capability_report_hash": content_hash(report)},
        "policy": {"status": "pass", "profile_hash": content_hash(selected_profile)},
    }


def plan_kwargs(**overrides):
    report = overrides.pop("capability_report", capability_report())
    selected_profile = overrides.pop("profile", profile())
    values = {
        "capability_report": report,
        "profile": selected_profile,
        "now": NOW,
        "preflight": preflight(report, selected_profile),
        "actual_ui_workflow": ui_workflow(),
        "api_graph": api_graph(),
    }
    values.update(overrides)
    return values


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


def terminal_evidence(plan, outputs, *, prompt_id="prompt-123", status="succeeded"):
    return {
        "source": "comfyui_history",
        "prompt_id": prompt_id,
        "status": status,
        "plan_hash": plan["plan_hash"],
        "api_graph_hash": plan["api_graph_hash"],
        "output_hashes": copy.deepcopy(outputs),
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
    with pytest.raises(ExecutionError, match="fingerprint"):
        build_valid_plan(actual_ui_workflow=changed_ui)

    changed_graph = api_graph()
    changed_graph["24"]["inputs"]["seed"] = 999
    with pytest.raises(ExecutionError, match="api_graph_hash"):
        build_valid_plan(api_graph=changed_graph)


@pytest.mark.parametrize("branch,evidence_key", [
    ("nodes", "workflow_fingerprint"),
    ("models", "api_graph_hash"),
    ("resources", "capability_report_hash"),
    ("policy", "profile_hash"),
])
def test_plan_rejects_self_reported_or_mismatched_preflight_evidence(branch, evidence_key):
    evidence = preflight()
    evidence[branch][evidence_key] = "0" * 64
    with pytest.raises(ExecutionError, match="preflight"):
        build_valid_plan(preflight=evidence)


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
    unsigned = dict(result)
    del unsigned["plan_hash"]
    assert result["plan_hash"] == content_hash(unsigned)


def test_run_record_requires_valid_task_context_before_lineage_checks():
    plan = build_valid_plan()
    with pytest.raises(ExecutionError, match="TaskContext"):
        build_run_record(
            {}, ready_build(), api_graph(), plan, "prompt-123", "failed", {}, {},
            terminal_evidence=terminal_evidence(plan, {}, status="failed"),
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
            terminal_evidence={"source": "comfyui_history"},
        )


@pytest.mark.parametrize("field,value", [
    ("source", "caller_claim"),
    ("prompt_id", "other-prompt"),
    ("status", "failed"),
    ("plan_hash", "0" * 64),
    ("api_graph_hash", "0" * 64),
    ("output_hashes", {}),
])
def test_run_record_rejects_terminal_evidence_mismatch(field, value):
    plan = build_valid_plan()
    outputs = {"image": content_hash("png")}
    evidence = terminal_evidence(plan, outputs)
    evidence[field] = value
    with pytest.raises(ExecutionError, match="terminal evidence"):
        build_run_record(
            task_context(), ready_build(), api_graph(), plan, "prompt-123", "succeeded",
            {}, outputs, terminal_evidence=evidence,
        )


def test_run_record_derives_performed_from_matching_history_and_hashes_record():
    build = ready_build()
    graph = api_graph()
    plan = build_valid_plan(build)
    outputs = {"image": content_hash("png")}
    evidence = terminal_evidence(plan, outputs)
    record = build_run_record(
        task_context(), build, graph, plan, "prompt-123", "succeeded", {}, outputs,
        terminal_evidence=evidence,
    )
    assert record["execution_performed"] is True
    assert record["terminal_evidence"] == evidence
    assert build["execution"]["performed"] is False
    unsigned = dict(record)
    del unsigned["record_hash"]
    assert record["record_hash"] == content_hash(unsigned)


def test_plan_rejects_non_object_api_graph():
    evidence = preflight()
    evidence["models"]["api_graph_hash"] = content_hash(None)
    with pytest.raises(ExecutionError, match="API graph"):
        build_valid_plan(api_graph=None, preflight=evidence)
