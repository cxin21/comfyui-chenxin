import copy
from datetime import datetime, timedelta, timezone

import pytest

from runtime.contracts import content_hash
from runtime.execution import ExecutionError, build_execution_plan, build_run_record


NOW = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)


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
        "allowed_mutations": [
            "positive_prompt.wildcard_text",
            "positive_prompt.populated_text",
            "negative_prompt.wildcard_text",
            "negative_prompt.populated_text",
        ],
        "expected_outputs": ["image/png"],
    }


def capability_report(*, valid_until=None, classification="local", running=0, pending=0):
    return {
        "schema_version": "1.0",
        "comfyui": {"url": "http://127.0.0.1:8188", "reachable": True},
        "adapter": {"runtime_classification": classification, "tools": []},
        "queue": {"running": running, "pending": pending},
        "generated_at": NOW.isoformat().replace("+00:00", "Z"),
        "valid_until": (valid_until or NOW + timedelta(minutes=10))
        .isoformat()
        .replace("+00:00", "Z"),
    }


def patches():
    return [
        {"slot": "positive_prompt", "input": "wildcard_text", "value": "positive"},
        {"slot": "negative_prompt", "input": "wildcard_text", "value": "negative"},
    ]


def plan_kwargs(**overrides):
    values = {
        "capability_report": capability_report(),
        "profile": profile(),
        "now": NOW,
        "preflight": {"nodes": "pass", "models": "pass", "resources": "pass", "policy": "pass"},
    }
    values.update(overrides)
    return values


def test_plan_requires_current_approval_before_other_runtime_inputs():
    with pytest.raises(ExecutionError, match="approval"):
        build_execution_plan(
            "character-base", ready_build(), "camera-anima-v1", "abc", [], False
        )


def test_plan_rejects_not_ready_unrequested_or_already_performed_build():
    for field, value, match in (
        ("ready_to_execute", False, "ready"),
        ("requested", False, "requested"),
        ("performed", True, "performed"),
    ):
        build = ready_build()
        if field in build:
            build[field] = value
        else:
            build["execution"][field] = value
        with pytest.raises(ExecutionError, match=match):
            build_execution_plan(
                "character-base", build, "camera-anima-v1", "abc", patches(), True,
                **plan_kwargs(),
            )


def test_plan_rejects_prompt_build_that_fails_anima_quality_gate():
    build = ready_build()
    build["rejected_tags"] = ["invented_tag"]
    with pytest.raises(ExecutionError, match="quality"):
        build_execution_plan(
            "character-base", build, "camera-anima-v1", "abc", patches(), True,
            **plan_kwargs(),
        )


def test_plan_rejects_stale_nonlocal_busy_or_failed_preflight():
    cases = [
        (plan_kwargs(capability_report=capability_report(valid_until=NOW)), "fresh"),
        (plan_kwargs(capability_report=capability_report(classification="paid")), "local"),
        (plan_kwargs(capability_report=capability_report(running=1)), "one.*job"),
        (plan_kwargs(preflight={"nodes": "fail", "models": "pass", "resources": "pass", "policy": "pass"}), "preflight"),
    ]
    for kwargs, match in cases:
        with pytest.raises(ExecutionError, match=match):
            build_execution_plan(
                "character-base", ready_build(), "camera-anima-v1", "abc", patches(), True,
                **kwargs,
            )


def test_plan_rejects_profile_fingerprint_and_patch_boundary_errors():
    invalid_cases = [
        (("wrong-profile", "abc", patches()), plan_kwargs(), "profile"),
        (("camera-anima-v1", "", patches()), plan_kwargs(), "fingerprint"),
        (("camera-anima-v1", "abc", [{"slot": "positive_prompt", "input": "seed", "value": 1}]), plan_kwargs(), "allowlist"),
    ]
    for args, kwargs, match in invalid_cases:
        with pytest.raises(ExecutionError, match=match):
            build_execution_plan("character-base", ready_build(), *args, True, **kwargs)


def test_plan_is_immutable_and_records_hashes_without_enqueuing():
    build = ready_build()
    patch_values = patches()
    kwargs = plan_kwargs()
    before = copy.deepcopy((build, patch_values))
    result = build_execution_plan(
        "character-base", build, "camera-anima-v1", "abc", patch_values, True,
        **kwargs,
    )
    assert (build, patch_values) == before
    assert result["prompt_build_id"] == content_hash(build)
    assert result["capability_report_hash"] == content_hash(kwargs["capability_report"])
    assert result["workflow_profile_hash"] == content_hash(kwargs["profile"])
    assert result["workflow_fingerprint"] == "abc"
    assert result["execution_approved"] is True
    assert result["local_only"] is True
    assert "prompt_id" not in result
    assert "performed" not in result


def test_run_record_has_stable_lineage_hash_and_does_not_forge_performed():
    task = {"schema_version": "1.0", "goal": "character"}
    build = ready_build()
    graph = {"24": {"inputs": {"text": "hello"}}}
    plan = {"schema_version": "1.0", "stage": "character-base", "execution_approved": True}
    input_hashes = {"workflow": content_hash({"workflow": 1})}
    output_hashes = {"image": content_hash(b"png".hex())}

    record = build_run_record(
        task, build, graph, plan, "prompt-123", "succeeded", input_hashes, output_hashes
    )
    reordered = build_run_record(
        {"goal": "character", "schema_version": "1.0"}, build, graph, plan,
        "prompt-123", "succeeded", dict(reversed(list(input_hashes.items()))), output_hashes,
    )

    assert record["task_context_hash"] == content_hash(task)
    assert record["prompt_build_hash"] == content_hash(build)
    assert record["api_graph_hash"] == content_hash(graph)
    assert record["execution_plan_hash"] == content_hash(plan)
    assert record["record_hash"] == reordered["record_hash"]
    assert record["execution_performed"] is True
    assert build["execution"]["performed"] is False


def test_run_record_rejects_success_without_runtime_evidence_and_bad_hashes():
    values = ({}, ready_build(), {}, {"execution_approved": True})
    with pytest.raises(ExecutionError, match="prompt_id"):
        build_run_record(*values, "", "succeeded", {}, {"image": content_hash("x")})
    with pytest.raises(ExecutionError, match="output"):
        build_run_record(*values, "prompt-1", "succeeded", {}, {})
    with pytest.raises(ExecutionError, match="SHA-256"):
        build_run_record(*values, "prompt-1", "failed", {"input": "fake"}, {})


def test_run_record_rejects_forged_prompt_build_performed_flag():
    build = ready_build()
    build["execution"]["performed"] = True
    with pytest.raises(ExecutionError, match="performed"):
        build_run_record(
            {}, build, {}, {"execution_approved": True}, "prompt-1", "failed", {}, {}
        )
