"""Opt-in Experiment C preflight.

The live test accepts only a preflight file produced by the real comfyui-mcp
load/strip/validate/runtime tools.  REST discovery is not treated as proof of
an executable graph, and this module never converts a UI workflow itself.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from runtime.contracts import canonical_json, content_hash
from runtime.execution import build_multiview_draft


LIVE = os.environ.get("PROMPT_FORGE_LIVE") == "1"
LIVE_MARK = pytest.mark.skipif(not LIVE, reason="set PROMPT_FORGE_LIVE=1 explicitly")
FINGERPRINT = "fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf"
STAGE1_HASH = "3ae0de91bae7272846ee8b1230cce0c2a0b0ed91448851734b1e8166ac04d909"
STAGE1_RECORD_HASH = "614cae18927b3d0808d59eadc95d5abcb953c7e174f4d320faff3d0345026438"
_PREFLIGHT_KEYS = frozenset(
    ("ui_workflow", "api_graph", "capability_report", "validation", "runtime")
)


def _validated_mcp_preflight(value: object) -> dict:
    assert isinstance(value, dict) and set(value) == _PREFLIGHT_KEYS
    assert value["validation"] == {"valid": True, "errors": []}, (
        "MCP workflow validation must be explicitly valid with zero errors"
    )
    runtime = value["runtime"]
    assert isinstance(runtime, dict) and runtime.get("runtime") == "local"
    assert runtime.get("usesApiNodes") is False
    graph = value["api_graph"]
    assert isinstance(graph, dict)
    assert graph.get("111", {}).get("class_type") == "LoadImage"
    assert graph.get("667", {}).get("class_type") == "LoadImage"
    return value


def _prepare_experiment_c_preflight(
    value: object, *, upload_image, enqueue_workflow
) -> tuple[dict, object]:
    """Validate all read-only gates before upload; pending preflight never enqueues."""
    safe = _validated_mcp_preflight(value)
    receipt = upload_image()
    # `enqueue_workflow` is deliberately retained as an injected forbidden
    # capability so tests prove the pending-preflight path never calls it.
    del enqueue_workflow
    return safe, receipt


def _write_pending(run_dir: Path, draft: dict, mcp_preflight: dict) -> Path:
    root = run_dir.resolve(strict=True)
    bundle = {
        "schema_version": "1.0",
        "bundle_type": "character-multiview-c-pending",
        "draft": draft,
        "draft_hash": draft["draft_hash"],
        "consumption_root": str(root),
        "mcp_preflight_hash": content_hash(mcp_preflight),
    }
    bundle["bundle_hash"] = content_hash(bundle)
    path = root / f'pending-c-{draft["draft_hash"]}.json'
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(bundle) + "\n")
    return path


def test_invalid_mcp_conversion_evidence_fails_closed_before_pending_bundle():
    invalid = {
        "ui_workflow": {},
        "api_graph": {"111": {"class_type": "LoadImage"}, "667": {"class_type": "LoadImage"}},
        "capability_report": {},
        "validation": {"valid": False, "errors": ["missing inputs"]},
        "runtime": {"runtime": "local", "usesApiNodes": False},
    }
    with pytest.raises(AssertionError, match="explicitly valid"):
        _validated_mcp_preflight(invalid)


def test_invalid_mcp_conversion_never_calls_upload_or_enqueue():
    invalid = {
        "ui_workflow": {},
        "api_graph": {"111": {"class_type": "LoadImage"}, "667": {"class_type": "LoadImage"}},
        "capability_report": {},
        "validation": {"valid": False, "errors": ["missing inputs"]},
        "runtime": {"runtime": "local", "usesApiNodes": False},
    }
    calls = []
    with pytest.raises(AssertionError, match="explicitly valid"):
        _prepare_experiment_c_preflight(
            invalid,
            upload_image=lambda: calls.append("upload"),
            enqueue_workflow=lambda: calls.append("enqueue"),
        )
    assert calls == []


def test_pending_bundle_retains_exact_unapproved_draft(tmp_path):
    draft = {"draft_hash": "d" * 64, "plan_state": "draft", "execution_approved": False}
    evidence = {
        "ui_workflow": {}, "api_graph": {}, "capability_report": {},
        "validation": {"valid": True, "errors": []},
        "runtime": {"runtime": "local", "usesApiNodes": False},
    }
    path = _write_pending(tmp_path, draft, evidence)
    retained = json.loads(path.read_text(encoding="utf-8"))
    assert retained["draft"] == draft
    assert retained["draft_hash"] == draft["draft_hash"]
    assert retained["bundle_hash"] == content_hash({k: v for k, v in retained.items() if k != "bundle_hash"})


@LIVE_MARK
def test_live_multiview_experiment_c_pending_preflight():
    preflight_path = os.environ.get("PROMPT_FORGE_MCP_PREFLIGHT_FILE")
    assert preflight_path, (
        "set PROMPT_FORGE_MCP_PREFLIGHT_FILE to evidence emitted by the real "
        "comfyui-mcp load/strip/validate/runtime tools"
    )
    preflight = _validated_mcp_preflight(
        json.loads(Path(preflight_path).resolve(strict=True).read_text(encoding="utf-8"))
    )
    record_path = Path(os.environ["PROMPT_FORGE_STAGE1_RECORD"]).resolve(strict=True)
    image_path = Path(os.environ["PROMPT_FORGE_STAGE1_IMAGE"]).resolve(strict=True)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["record_hash"] == STAGE1_RECORD_HASH
    artifact = {
        "schema_version": "1.0",
        "artifact_type": "CharacterBaseImage",
        "accepted": True,
        "content_hash": STAGE1_HASH,
        "lineage_id": STAGE1_RECORD_HASH,
        "source_record_hash": STAGE1_RECORD_HASH,
        "artifact_path": str(image_path),
        "artifact_root": str(image_path.parent),
        "visual_acceptance": {"front_facing": True, "identity_visible": True},
    }
    draft = build_multiview_draft(
        stage1_record=record,
        base_artifact=artifact,
        workflow_profile_id="flux2-klein-multiview-v1",
        workflow_fingerprint=FINGERPRINT,
        capability_report=preflight["capability_report"],
        profile=json.loads(
            (Path(__file__).parents[1] / "profiles/flux2-klein-multiview.json").read_text(encoding="utf-8")
        ),
        actual_ui_workflow=preflight["ui_workflow"],
        api_graph=preflight["api_graph"],
    )
    run_dir = Path(os.environ["PROMPT_FORGE_RUN_DIR"]).resolve(strict=True)
    pending = _write_pending(run_dir, draft, preflight)
    pytest.fail(
        "Experiment C draft is pending external approval; no upload or enqueue was performed: "
        f"draft_hash={draft['draft_hash']} bundle={pending}"
    )
