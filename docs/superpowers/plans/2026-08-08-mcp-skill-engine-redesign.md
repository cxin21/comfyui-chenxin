# MCP + Skill Engine Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace v1's per-skill MCP tool registration with a unified 4-tool interface backed by a shared execution engine, where each skill is pure data (SkillData via entry-points).

**Architecture:** The MCP server owns 4 tools (`list_skills`, `describe_config`, `validate_config`, `run_skill`) that dispatch by skill name to a shared engine. The engine calls skill-provided function pointers (describe_fn, apply_fn, prepare_fn) via SkillData. Skills provide only data + function pointers -- no tool registration code, no execution code.

**Tech Stack:** Python 3.10+, stdlib only, setuptools entry-points, pytest, asyncio stdio JSON-RPC.

## Global Constraints

- **处女原则 (virgin principle):** Write v2 from scratch. Do NOT patch v1 files. Do NOT preserve backward compatibility. Write new code; delete superseded files.
- **No patches, no compat layers:** If v1 code is superseded, delete it and write fresh. No shims, no aliases, no deprecation warnings.
- **Test data:** Use `skills/camera-image/workflow/source/文生图相机视角.json` as real test data for the entire flow. No mock workflow JSON.
- **TDD:** Write failing test first, see RED, write minimal implementation, see GREEN, commit.
- **Boundary rules:** `comfyui_chenxin_mcp/engine/*` must NOT import any skill's `runtime.*`. `runtime/*` must NOT import `comfyui_chenxin_mcp`. `skill_data.py` is the only bridge.
- **Zero third-party deps:** stdlib only for the MCP package.
- **Platform:** Windows 11, Python 3.10+, PowerShell, npx available.
- **Commit convention:** `<type>: <description>` + `Co-Authored-By: Claude <noreply@anthropic.com>`

## Existing code the engine calls (DO NOT MODIFY unless task says so)

- `runtime/graph_patcher.py`: `describe_config(stage) -> dict`, `apply_run_config(graph, stage, config, mcp_list_loras=None) -> None`, `NODE_FIELD_MAP`, `GROUPS`
- `runtime/source_workflow.py`: `prepare_temporary_workflow(mcp, stage, user_g1=None, user_g2=None) -> dict`
- `runtime/prompt_forge_bridge.py`: `compile_envelope(evidence, draft, dialect_id) -> dict`
- `runtime/mcp_client.py`: `McpClient` with `health()`, `upload_image(path)`, `list_loras()`, `validate_workflow(graph)`, `check_runtime(graph)`, `enqueue(graph)`, `get_history(prompt_id)`, `get_image(filename, subfolder, image_type)`, `save_workflow(filename, ui)`, `get_workflow(filename, format)`. `McpClient.from_subprocess(cmd, args, timeout)` is a context manager.
- `runtime/config_schema.py`: `RunConfig` (frozen dataclass: `evidence: dict`, `draft: dict`, `dialect_id="anima"`, `camera: CameraConfig | None`, `camera_extra: dict | None`, `lora: dict | None`, `groups: GroupsConfig | None`, `sampling: SamplingConfig | None`, `seed: int | None`, `image_size: ImageSizeConfig | None`, `reference_image: str | None`, `controlnet_image: str | None`). `CameraConfig(direction, elevation, distance, roll)`, `SamplingConfig(steps_first, cfg, sampler, scheduler, denoise_first, steps_refine, denoise_refine)`, `ImageSizeConfig(width, height)`, `GroupsConfig(g1: list[str] | None, g2: list[str] | None)`. `STAGES.T2I="t2i-camera"`, `STAGES.I2I="i2i-camera"`. `GROUPS.LOAD_IMAGE="加载图片（G1）"`, `GROUPS.CONTROLNET_LLLITE="ControlNet LLLite（G1）"`.

---

### Task 1: SkillData + Rule + ImageSpec dataclasses

**Files:**
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/engine/__init__.py` (empty)
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/engine/skill_data.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_skill_data.py`

**Interfaces:**
- Produces: `SkillData`, `Rule`, `ImageSpec` dataclasses (used by all later tasks)

- [ ] **Step 1: Write the failing test**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/tests/test_skill_data.py
"""SkillData / Rule / ImageSpec dataclass tests."""
from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec


def test_image_spec_defaults():
    spec = ImageSpec(config_key="reference_image", required=True)
    assert spec.config_key == "reference_image"
    assert spec.required is True
    assert spec.requires_group is None


def test_image_spec_with_group():
    spec = ImageSpec(config_key="controlnet_image", required=False, requires_group="ControlNet LLLite（G1）")
    assert spec.requires_group == "ControlNet LLLite（G1）"


def test_rule_bidirectional():
    rule = Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）")
    assert rule.direction == "bidirectional"


def test_rule_forward():
    rule = Rule(condition="stage:i2i-camera", implies="group_auto:加载图片（G1）", direction="forward")
    assert rule.direction == "forward"


def test_skill_data_construction():
    def fake_describe(stage): return {"stage": stage}
    def fake_apply(graph, stage, config, **kw): pass
    def fake_prepare(mcp, stage, g1, g2): return {}

    sd = SkillData(
        name="camera-image",
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={"sampling.steps": (50, "steps")},
        dependency_rules=(
            Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）"),
        ),
        stage_images={
            "t2i-camera": (ImageSpec("controlnet_image", required=False),),
        },
        output_type="images",
        describe_fn=fake_describe,
        apply_fn=fake_apply,
        prepare_fn=fake_prepare,
    )
    assert sd.name == "camera-image"
    assert sd.stages == ("t2i-camera", "i2i-camera")
    assert sd.output_type == "images"
    assert sd.dialect_id == "anima"
    assert callable(sd.describe_fn)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_skill_data.py -v --tb=short 2>&1 | tail -10`
Expected: FAIL with `ModuleNotFoundError: No module named 'comfyui_chenxin_mcp.engine'`

- [ ] **Step 3: Write minimal implementation**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/engine/__init__.py
# (empty file)
```

```python
# skills/_mcp/src/comfyui_chenxin_mcp/engine/skill_data.py
"""Data contract every skill provides via entry-points."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ImageSpec:
    """An image to upload before workflow execution."""
    config_key: str
    required: bool
    requires_group: str | None = None


@dataclass(frozen=True)
class Rule:
    """A declarative group-config dependency.

    condition/implies use prefixes: "config:", "group:", "stage:", "group_auto:".
    direction="bidirectional" means A->B AND B->A.
    direction="forward" means A->B only.
    """
    condition: str
    implies: str
    direction: str = "bidirectional"


@dataclass(frozen=True)
class SkillData:
    """Pure data + function pointers describing a skill.

    The engine calls describe_fn/apply_fn/prepare_fn via these pointers.
    Skills provide this via entry-points; the MCP server never imports
    runtime.* directly.
    """
    name: str
    stages: tuple[str, ...]
    source_workflow_path: str
    groups_dir_pattern: str
    field_map: dict[str, tuple[int, str]]
    dependency_rules: tuple[Rule, ...]
    stage_images: dict[str, tuple[ImageSpec, ...]]
    output_type: str
    describe_fn: Callable[..., dict[str, Any]]
    apply_fn: Callable[..., None]
    prepare_fn: Callable[..., dict[str, Any]]
    dialect_id: str = "anima"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_skill_data.py -v --tb=short 2>&1 | tail -10`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/_mcp/src/comfyui_chenxin_mcp/engine/ skills/_mcp/src/comfyui_chenxin_mcp/tests/test_skill_data.py
git commit -m "feat(engine): add SkillData + Rule + ImageSpec dataclasses

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: engine/validate.py - declarative dependency rule validator

**Files:**
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/engine/validate.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_validate.py`

**Interfaces:**
- Consumes: `SkillData`, `Rule` from Task 1
- Produces: `validate_config(skill_data: SkillData, stage: str, config: dict) -> dict` returning `{"ok": bool, "errors": list[str]}`

- [ ] **Step 1: Write the failing tests**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_validate.py
"""Engine validate_config tests - declarative dependency rules."""
from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from comfyui_chenxin_mcp.engine.validate import validate_config


def _skill_data(rules=()):
    return SkillData(
        name="camera-image",
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={},
        dependency_rules=rules,
        stage_images={},
        output_type="images",
        describe_fn=lambda stage: {},
        apply_fn=lambda graph, stage, config, **kw: None,
        prepare_fn=lambda mcp, stage, g1, g2: {},
    )


def test_valid_config_no_errors():
    sd = _skill_data()
    config = {"draft": {"positive": "1girl", "negative": "lowres"}}
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is True
    assert result["errors"] == []


def test_missing_draft_positive():
    sd = _skill_data()
    config = {"draft": {"positive": "", "negative": "lowres"}}
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("positive" in e for e in result["errors"])


def test_missing_draft_negative():
    sd = _skill_data()
    config = {"draft": {"positive": "1girl", "negative": ""}}
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("negative" in e for e in result["errors"])


def test_missing_draft_entirely():
    sd = _skill_data()
    config = {}
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("draft" in e for e in result["errors"])


def test_config_implies_group_violation():
    """controlnet_image provided but group not enabled -> error."""
    sd = _skill_data(rules=(
        Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）"),
    ))
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "controlnet_image": "/path/to/img.png",
        "groups": {"g1": []},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("ControlNet LLLite" in e for e in result["errors"])


def test_config_implies_group_satisfied():
    """controlnet_image provided AND group enabled -> ok."""
    sd = _skill_data(rules=(
        Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）"),
    ))
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "controlnet_image": "/path/to/img.png",
        "groups": {"g1": ["ControlNet LLLite（G1）"]},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is True


def test_group_implies_config_violation():
    """group enabled but controlnet_image not provided -> error."""
    sd = _skill_data(rules=(
        Rule(condition="config:controlnet_image", implies="group:ControlNet LLLite（G1）"),
    ))
    config = {
        "draft": {"positive": "1girl", "negative": "lowres"},
        "groups": {"g1": ["ControlNet LLLite（G1）"]},
    }
    result = validate_config(sd, "t2i-camera", config)
    assert result["ok"] is False
    assert any("controlnet_image" in e for e in result["errors"])


def test_stage_implies_group_auto_forward_only():
    """stage=i2i-camera implies group_auto=load_image (forward, not bidirectional)."""
    sd = _skill_data(rules=(
        Rule(condition="stage:i2i-camera", implies="group_auto:加载图片（G1）", direction="forward"),
    ))
    config = {"draft": {"positive": "1girl", "negative": "lowres"}}
    result = validate_config(sd, "i2i-camera", config)
    # forward rule: stage->group_auto is informational, not a validation error
    assert result["ok"] is True


def test_config_not_dict():
    sd = _skill_data()
    result = validate_config(sd, "t2i-camera", "not a dict")
    assert result["ok"] is False
    assert any("object" in e for e in result["errors"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_validate.py -v --tb=short 2>&1 | tail -15`
Expected: FAIL with `ModuleNotFoundError: No module named 'comfyui_chenxin_mcp.engine.validate'`

- [ ] **Step 3: Write minimal implementation**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/engine/validate.py
"""Declarative dependency rule validator.

Checks group-config dependencies via Rule objects (data, not procedural code).
Also validates envelope shape (draft.positive/negative non-empty).
"""
from __future__ import annotations

from typing import Any

from .skill_data import SkillData, Rule


def validate_config(skill_data: SkillData, stage: str, config: Any) -> dict[str, Any]:
    """Validate a config dict against the skill's dependency rules + envelope shape.

    Returns {"ok": bool, "errors": list[str], "stage": str, "skill": str}.
    """
    if not isinstance(config, dict):
        return {"ok": False, "errors": ["config must be an object"], "stage": stage, "skill": skill_data.name}

    errors: list[str] = []

    # Envelope shape: draft must have non-empty positive/negative.
    draft = config.get("draft")
    if not isinstance(draft, dict):
        errors.append("config.draft must be an object (prompt-forge envelope)")
    else:
        for key in ("positive", "negative"):
            val = draft.get(key)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"config.draft.{key} must be a non-empty string")

    # Declarative dependency rules.
    groups = config.get("groups") or {}
    g1 = list(groups.get("g1", [])) if isinstance(groups, dict) else []
    g2 = list(groups.get("g2", [])) if isinstance(groups, dict) else []
    all_groups = g1 + g2

    for rule in skill_data.dependency_rules:
        errors.extend(_check_rule(rule, stage, config, all_groups))

    if errors:
        return {"ok": False, "errors": errors, "stage": stage, "skill": skill_data.name}
    return {"ok": True, "errors": [], "stage": stage, "skill": skill_data.name}


def _check_rule(rule: Rule, stage: str, config: dict, all_groups: list[str]) -> list[str]:
    """Check a single Rule. Returns list of error strings (empty if ok)."""
    cond_type, _, cond_val = rule.condition.partition(":")
    impl_type, _, impl_val = rule.implies.partition(":")

    errors: list[str] = []

    cond_met = _is_condition_met(cond_type, cond_val, stage, config, all_groups)
    if cond_met:
        errors.extend(_check_implies(impl_type, impl_val, config, all_groups))

    if rule.direction == "bidirectional":
        impl_met = _is_condition_met(impl_type, impl_val, stage, config, all_groups)
        if impl_met:
            errors.extend(_check_implies(cond_type, cond_val, config, all_groups))

    return errors


def _is_condition_met(cond_type: str, cond_val: str, stage: str, config: dict, all_groups: list[str]) -> bool:
    if cond_type == "config":
        return config.get(cond_val) is not None
    if cond_type == "group":
        return cond_val in all_groups
    if cond_type == "stage":
        return stage == cond_val
    return False


def _check_implies(impl_type: str, impl_val: str, config: dict, all_groups: list[str]) -> list[str]:
    if impl_type == "config":
        if config.get(impl_val) is None:
            return [f"config.{impl_val} is required (dependency rule)"]
    elif impl_type == "group":
        if impl_val not in all_groups:
            return [f"group '{impl_val}' must be enabled (dependency rule)"]
    # group_auto: informational, not a validation error.
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_validate.py -v --tb=short 2>&1 | tail -15`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/_mcp/src/comfyui_chenxin_mcp/engine/validate.py skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_validate.py
git commit -m "feat(engine): add declarative dependency rule validator

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: engine/describe.py - schema dispatch

**Files:**
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/engine/describe.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_describe.py`

**Interfaces:**
- Consumes: `SkillData` from Task 1
- Produces: `describe_config(skill_data: SkillData, stage: str) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_describe.py
"""Engine describe_config tests - dispatches to skill's describe_fn."""
from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from comfyui_chenxin_mcp.engine.describe import describe_config


def _skill_data(describe_fn=None):
    def fake_describe(stage):
        return {"stage": stage, "slots": {"sampling": {"fields": {"steps": {"default": 40}}}}}
    return SkillData(
        name="camera-image",
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={},
        dependency_rules=(),
        stage_images={},
        output_type="images",
        describe_fn=describe_fn or fake_describe,
        apply_fn=lambda graph, stage, config, **kw: None,
        prepare_fn=lambda mcp, stage, g1, g2: {},
    )


def test_describe_dispatches_to_skill_fn():
    sd = _skill_data()
    result = describe_config(sd, "t2i-camera")
    assert result["stage"] == "t2i-camera"
    assert "sampling" in result["slots"]


def test_describe_unknown_stage_raises():
    sd = _skill_data()
    try:
        describe_config(sd, "nonexistent-stage")
        assert False, "should have raised ValueError"
    except ValueError as e:
        assert "nonexistent-stage" in str(e)


def test_describe_returns_skill_fn_result_unchanged():
    """Engine does not modify the describe_fn output."""
    def custom_describe(stage):
        return {"stage": stage, "custom": True, "slots": {}}
    sd = _skill_data(describe_fn=custom_describe)
    result = describe_config(sd, "t2i-camera")
    assert result["custom"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_describe.py -v --tb=short 2>&1 | tail -10`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/engine/describe.py
"""Schema dispatch - calls the skill's own describe_fn."""
from __future__ import annotations

from .skill_data import SkillData


def describe_config(skill_data: SkillData, stage: str) -> dict:
    """Dispatch to the skill's describe_fn. Validates stage first.

    Returns whatever the skill's describe_fn returns (typically
    {stage, slots, groups, ...}).
    """
    if stage not in skill_data.stages:
        raise ValueError(
            f"unknown stage {stage!r} for skill {skill_data.name!r}; "
            f"available: {skill_data.stages}"
        )
    return skill_data.describe_fn(stage)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_describe.py -v --tb=short 2>&1 | tail -10`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/_mcp/src/comfyui_chenxin_mcp/engine/describe.py skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_describe.py
git commit -m "feat(engine): add describe_config dispatch

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: RunConfig.from_envelope + engine/execute.py

**Files:**
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/engine/execute.py`
- Create: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_execute.py`
- Modify: `skills/camera-image/runtime/config_schema.py` - add `from_envelope` classmethod to `RunConfig`

**Interfaces:**
- Consumes: `SkillData` from Task 1; `RunConfig` from `runtime/config_schema.py`; `McpClient` from `runtime/mcp_client.py`; `compile_envelope` from `runtime/prompt_forge_bridge.py`
- Produces: `run_skill(mcp, skill_data, stage, config, output_dir, timeout) -> tuple[dict, int]`

- [ ] **Step 1: Add RunConfig.from_envelope classmethod**

In `skills/camera-image/runtime/config_schema.py`, add this classmethod to the `RunConfig` dataclass (after the field definitions, before the class ends):

```python
    @classmethod
    def from_envelope(cls, envelope: dict, **tunables) -> "RunConfig":
        """Build RunConfig from an envelope dict + tunable kwargs.

        envelope must contain: evidence (dict), draft (dict).
        Optional envelope key: dialect_id (str, default "anima").
        tunables: camera (dict), camera_extra (dict), lora (dict),
                  groups (dict), sampling (dict), seed (int),
                  image_size (dict), reference_image (str), controlnet_image (str).
        """
        camera = tunables.get("camera")
        if isinstance(camera, dict):
            camera = CameraConfig(**camera)
        sampling = tunables.get("sampling")
        if isinstance(sampling, dict):
            sampling = SamplingConfig(**sampling)
        image_size = tunables.get("image_size")
        if isinstance(image_size, dict):
            image_size = ImageSizeConfig(**image_size)
        groups = tunables.get("groups")
        if isinstance(groups, dict):
            groups = GroupsConfig(**groups)
        return cls(
            evidence=envelope.get("evidence", {}),
            draft=envelope.get("draft", {}),
            dialect_id=envelope.get("dialect_id", "anima"),
            camera=camera,
            camera_extra=tunables.get("camera_extra"),
            lora=tunables.get("lora"),
            groups=groups,
            sampling=sampling,
            seed=tunables.get("seed"),
            image_size=image_size,
            reference_image=tunables.get("reference_image"),
            controlnet_image=tunables.get("controlnet_image"),
        )
```

- [ ] **Step 2: Write the failing tests for engine/execute.py**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_execute.py
"""Engine run_skill tests - mock McpClient, verify call sequence."""
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from comfyui_chenxin_mcp.engine.execute import run_skill
from runtime.config_schema import RunConfig


def _skill_data():
    return SkillData(
        name="camera-image",
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={},
        dependency_rules=(),
        stage_images={
            "t2i-camera": (ImageSpec("controlnet_image", required=False),),
            "i2i-camera": (
                ImageSpec("reference_image", required=True),
                ImageSpec("controlnet_image", required=False),
            ),
        },
        output_type="images",
        describe_fn=lambda stage: {},
        apply_fn=lambda graph, stage, config, **kw: None,
        prepare_fn=lambda mcp, stage, g1, g2: {"nodes": [], "links": []},
    )


def _config(stage="t2i-camera", **overrides):
    envelope = {
        "evidence": {},
        "draft": {"positive": "1girl", "negative": "lowres"},
        "dialect_id": "anima",
    }
    envelope.update(overrides)
    return RunConfig.from_envelope(envelope)


def _mock_mcp():
    mcp = MagicMock()
    mcp.__enter__ = lambda s: mcp
    mcp.__exit__ = lambda *a: False
    mcp.health.return_value = {"queue": {"running": [], "pending": []}}
    mcp.validate_workflow.return_value = {"error_count": 0}
    mcp.check_runtime.return_value = {"runtime": "local"}
    mcp.enqueue.return_value = {"prompt_id": "test-prompt-123"}
    mcp.get_history.return_value = {
        "test-prompt-123": {
            "status": {"status_str": "success"},
            "outputs": {"35": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        }
    }
    mcp.get_image.return_value = b"\x89PNG fake image data"
    return mcp


def test_run_skill_t2i_success(tmp_path):
    sd = _skill_data()
    config = _config()
    mcp = _mock_mcp()
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="t2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 0
    assert payload["accepted"] is True
    assert payload["prompt_id"] == "test-prompt-123"
    assert "artifact" in payload
    assert (tmp_path / "out.png").exists()


def test_run_skill_i2i_requires_reference(tmp_path):
    sd = _skill_data()
    config = _config(stage="i2i-camera")  # no reference_image
    mcp = _mock_mcp()
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="i2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 1
    assert "reference_image" in payload.get("error", "")


def test_run_skill_i2i_uploads_reference(tmp_path):
    sd = _skill_data()
    config = _config(stage="i2i-camera", reference_image="/fake/path.png")
    mcp = _mock_mcp()
    mcp.upload_image.return_value = {"name": "ref.png", "subfolder": ""}
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="i2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 0
    mcp.upload_image.assert_any_call("/fake/path.png")


def test_run_skill_health_check_fails(tmp_path):
    sd = _skill_data()
    config = _config()
    mcp = _mock_mcp()
    mcp.health.return_value = {"queue": {"running": ["job1"], "pending": []}}
    payload, code = run_skill(mcp=mcp, skill_data=sd, stage="t2i-camera", config=config,
                              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert code == 1
    assert "queue" in payload["error"].lower()


def test_run_skill_calls_prepare_and_apply(tmp_path):
    sd = _skill_data()
    config = _config()
    mcp = _mock_mcp()
    prepare_called = []
    apply_called = []

    def track_prepare(m, stage, g1, g2):
        prepare_called.append((stage, g1, g2))
        return {"nodes": [], "links": []}

    def track_apply(graph, stage, cfg, **kw):
        apply_called.append(stage)

    sd = SkillData(
        name=sd.name, stages=sd.stages, source_workflow_path=sd.source_workflow_path,
        groups_dir_pattern=sd.groups_dir_pattern, field_map=sd.field_map,
        dependency_rules=sd.dependency_rules, stage_images=sd.stage_images,
        output_type=sd.output_type, describe_fn=sd.describe_fn,
        apply_fn=track_apply, prepare_fn=track_prepare,
    )
    run_skill(mcp=mcp, skill_data=sd, stage="t2i-camera", config=config,
              output_dir=tmp_path, timeout=5.0, poll_interval=0.1)
    assert len(prepare_called) == 1
    assert prepare_called[0][0] == "t2i-camera"
    assert len(apply_called) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /d/Projects/comfyui-chenxin && PYTHONPATH=skills/camera-image python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_execute.py -v --tb=short 2>&1 | tail -15`
Expected: FAIL with `ModuleNotFoundError: No module named 'comfyui_chenxin_mcp.engine.execute'`

- [ ] **Step 4: Write minimal implementation**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/engine/execute.py
"""Shared execution engine - one run_skill for all skills.

Replaces t2i_camera.run_t2i + i2i_camera.run_i2i (80+ lines of duplicated code).
Flow: prompt-forge gate -> upload images -> health -> prepare -> apply -> validate -> enqueue -> wait -> download.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from .skill_data import SkillData


def run_skill(
    *,
    mcp,
    skill_data: SkillData,
    stage: str,
    config,
    output_dir: Path,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
) -> tuple[dict[str, Any], int]:
    """Execute a skill stage. Returns (payload, exit_code).

    Generic flow:
    1. prompt-forge gate (compile_envelope)
    2. upload stage_images (reference, controlnet)
    3. health check (ComfyUI queue idle)
    4. prepare temp workflow (copy source + patch groups + upload)
    5. apply run config (write tunables to graph)
    6. validate + check runtime
    7. enqueue + wait + download
    """
    started = time.monotonic()
    run_dir = output_dir / "runs" / f"{stage.replace('/', '-')}_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: prompt-forge gate.
        from runtime.prompt_forge_bridge import compile_envelope
        package = compile_envelope(config.evidence, config.draft, skill_data.dialect_id)

        # Step 2: upload stage_images.
        patch_config = config
        for spec in skill_data.stage_images.get(stage, ()):
            val = getattr(config, spec.config_key, None)
            if spec.required and not val:
                raise ValueError(f"{spec.config_key} is required for {stage}")
            if val:
                upload_result = mcp.upload_image(val)
                uploaded = None
                if isinstance(upload_result, dict):
                    uploaded = upload_result.get("name")
                    subfolder = upload_result.get("subfolder", "")
                    if subfolder and uploaded:
                        uploaded = f"{subfolder}/{uploaded}"
                if not uploaded:
                    raise RuntimeError(f"{spec.config_key} upload failed: {upload_result}")
                patch_config = replace(patch_config, **{spec.config_key: uploaded})

        # Step 3: health check.
        health = mcp.health()
        if isinstance(health, dict) and isinstance(health.get("queue"), dict):
            q = health["queue"]
            if len(q.get("running", [])) or len(q.get("pending", [])):
                raise RuntimeError(f"ComfyUI queue not idle (running={len(q.get('running', []))}, pending={len(q.get('pending', []))})")

        # Step 4: prepare temp workflow.
        graph = skill_data.prepare_fn(
            mcp,
            stage=stage,
            user_g1=list(patch_config.groups.g1) if patch_config.groups else None,
            user_g2=list(patch_config.groups.g2) if patch_config.groups else None,
        )

        # Step 5: apply run config.
        skill_data.apply_fn(
            graph,
            stage=stage,
            config=patch_config,
            mcp_list_loras=mcp.list_loras if patch_config.lora else None,
        )

        # Step 6: validate + check runtime.
        validation = mcp.validate_workflow(graph)
        if isinstance(validation, dict) and validation.get("error_count", 0) > 0:
            raise RuntimeError(f"workflow validation failed: {validation}")

        runtime_check = mcp.check_runtime(graph)
        if isinstance(runtime_check, dict) and runtime_check.get("runtime") != "local":
            raise RuntimeError(f"workflow uses non-local runtime: {runtime_check}")

        # Step 7: enqueue + wait + download.
        result = mcp.enqueue(graph)
        prompt_id = None
        if isinstance(result, dict):
            prompt_id = result.get("prompt_id") or result.get("promptId")
        if not prompt_id:
            raise RuntimeError(f"enqueue did not return prompt_id: {result}")

        entry = _wait_for_completion(mcp, prompt_id, timeout, poll_interval)
        artifact = _download_artifact(mcp, entry, output_dir, skill_data.output_type)

    except Exception as exc:
        from runtime.attempt_state import record_attempt
        record_attempt({"stage": stage, "status": "failed", "error": str(exc)})
        return {"accepted": False, "stage": stage, "error": str(exc)}, 1

    duration_ms = int((time.monotonic() - started) * 1000)
    run_record = {
        "schema_version": "2.0",
        "stage": stage,
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "config": asdict(config),
        "prompt_package_quality": package.get("quality", {}),
    }
    (run_dir / "submitted-graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "run-record.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    from runtime.attempt_state import record_attempt
    record_attempt({"stage": stage, "status": "success", "prompt_id": prompt_id,
                     "artifact": artifact.get("path")})

    payload: dict[str, Any] = {
        "accepted": True,
        "stage": stage,
        "prompt_id": prompt_id,
        "artifact": artifact,
        "duration_ms": duration_ms,
        "run_record_path": str(run_dir / "run-record.json"),
        "prompt_forge_warnings": package.get("warnings", []),
    }
    return payload, 0


def _wait_for_completion(mcp, prompt_id: str, timeout: float, poll: float) -> dict:
    """Poll get_history until success or failure."""
    deadline = time.monotonic() + timeout
    while True:
        history = mcp.get_history(prompt_id)
        entry, status_str, error_detail = _parse_history(history, prompt_id)
        if status_str == "success":
            return entry if entry else {"prompt_id": prompt_id, "outputs": {}}
        if status_str == "error":
            raise RuntimeError(f"execution failed: {error_detail}")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"timed out after {timeout:.0f}s")
        time.sleep(poll)


def _parse_history(history, prompt_id: str) -> tuple[dict | None, str | None, str]:
    if isinstance(history, dict):
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {}) if isinstance(entry, dict) else {}
            status_str = status.get("status_str") if isinstance(status, dict) else None
            error_detail = ""
            if status_str == "error":
                msgs = status.get("messages", []) if isinstance(status, dict) else []
                for m in msgs:
                    if isinstance(m, list) and len(m) == 2 and m[0] == "execution_error":
                        info = m[1] if isinstance(m[1], dict) else {}
                        error_detail = f"node {info.get('node_id')}: {info.get('exception_message')}"
            return entry, status_str, error_detail
        return None, None, ""
    return None, None, ""


def _download_artifact(mcp, entry: dict, output_dir: Path, output_type: str) -> dict:
    """Download the first output artifact (image or video)."""
    outputs = entry.get("outputs", {})
    artifact_info = None
    for node_id, out in outputs.items():
        if isinstance(out, dict) and isinstance(out.get(output_type), list) and out[output_type]:
            artifact_info = out[output_type][0]
            break
    if not artifact_info:
        raise RuntimeError(f"no output {output_type} in history entry")

    filename = artifact_info["filename"]
    subfolder = artifact_info.get("subfolder", "")
    image_type = artifact_info.get("type", "output")
    raw = mcp.get_image(filename, subfolder, image_type)

    output_dir.mkdir(parents=True, exist_ok=True)
    data: bytes | None = None
    if isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    elif isinstance(raw, dict) and "data" in raw:
        import base64
        data = base64.b64decode(raw["data"])
    elif isinstance(raw, list):
        import base64
        for block in raw:
            if isinstance(block, dict) and block.get("type") in ("image", "video"):
                b64 = block.get("data")
                if isinstance(b64, str):
                    data = base64.b64decode(b64)
                    break

    if data is None:
        raise RuntimeError(f"artifact download returned no data for {filename}")

    out_path = output_dir / filename
    out_path.write_bytes(data)
    return {
        "filename": filename,
        "subfolder": subfolder,
        "path": str(out_path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /d/Projects/comfyui-chenxin && PYTHONPATH=skills/camera-image python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_execute.py -v --tb=short 2>&1 | tail -15`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/_mcp/src/comfyui_chenxin_mcp/engine/execute.py skills/_mcp/src/comfyui_chenxin_mcp/tests/test_engine_execute.py skills/camera-image/runtime/config_schema.py
git commit -m "feat(engine): add shared execution engine + RunConfig.from_envelope

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: registry.py + server.py rewrite (4 unified tools)

**Files:**
- Rewrite: `skills/_mcp/src/comfyui_chenxin_mcp/registry.py`
- Rewrite: `skills/_mcp/src/comfyui_chenxin_mcp/server.py`
- Rewrite: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_registry.py`

**Interfaces:**
- Consumes: `SkillData` from Task 1; `describe_config` from Task 3; `validate_config` from Task 2; `run_skill` from Task 4
- Produces: `discover_skills() -> list[SkillData]`; server with 4 unified tools

- [ ] **Step 1: Write the failing tests for registry**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/tests/test_registry.py
"""Registry tests - entry-point discovery returns SkillData."""
from unittest.mock import patch
from comfyui_chenxin_mcp.registry import discover_skills
from comfyui_chenxin_mcp.engine.skill_data import SkillData


class FakeEntryPoint:
    def __init__(self, name, fn):
        self.name = name
        self._fn = fn
    def load(self):
        return self._fn


def _fake_skill_data(name="camera-image"):
    return SkillData(
        name=name,
        stages=("t2i-camera", "i2i-camera"),
        source_workflow_path="workflow/source/test.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map={},
        dependency_rules=(),
        stage_images={},
        output_type="images",
        describe_fn=lambda stage: {},
        apply_fn=lambda graph, stage, config, **kw: None,
        prepare_fn=lambda mcp, stage, g1, g2: {},
    )


def test_discover_returns_skill_data_list():
    def get_skill_data():
        return _fake_skill_data()
    with patch("comfyui_chenxin_mcp.registry.importlib.metadata.entry_points") as m:
        m.return_value.select = lambda group: [FakeEntryPoint("camera-image", get_skill_data)]
        skills = discover_skills()
    assert len(skills) == 1
    assert isinstance(skills[0], SkillData)
    assert skills[0].name == "camera-image"


def test_discover_empty_when_no_skills():
    with patch("comfyui_chenxin_mcp.registry.importlib.metadata.entry_points") as m:
        m.return_value.select = lambda group: []
        skills = discover_skills()
    assert skills == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_registry.py -v --tb=short 2>&1 | tail -10`
Expected: FAIL (registry still returns old `SkillRegistration` objects)

- [ ] **Step 3: Rewrite registry.py**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/registry.py
"""Skill discovery via Python entry-points.

Each skill package declares an entry-point in its pyproject.toml:
    [project.entry-points."comfyui_chenxin_mcp.skills"]
    camera-image = "camera_image.skill_data:get_skill_data"

The callable must return a SkillData instance.
"""
from __future__ import annotations

import importlib.metadata

from .engine.skill_data import SkillData

ENTRY_POINT_GROUP = "comfyui_chenxin_mcp.skills"


def discover_skills() -> list[SkillData]:
    """Discover installed skills via entry-points.

    Returns a list of SkillData. Empty if no skill is installed.
    """
    out: list[SkillData] = []
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        selected = eps.select(group=ENTRY_POINT_GROUP)
    else:
        selected = eps.get(ENTRY_POINT_GROUP, [])
    for ep in selected:
        get_data_fn = ep.load()
        out.append(get_data_fn())
    return out
```

- [ ] **Step 4: Rewrite server.py**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/server.py
"""comfyui-chenxin-mcp stdio server entrypoint.

Boots: protocol server + entry-point discovery + 4 unified tools.
No hardcoded skill names. Skills declare themselves via Python entry-points.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

from .protocol import Server
from .registry import discover_skills
from .engine.describe import describe_config
from .engine.validate import validate_config
from .engine.execute import run_skill
from .engine.skill_data import SkillData


def _spawn_mcp():
    """Spawn comfyui-mcp subprocess for ComfyUI communication."""
    from runtime.mcp_client import McpClient
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    return McpClient.from_subprocess(
        npx, ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url],
        timeout=600.0,
    )


def _find_skill(skills: list[SkillData], name: str) -> SkillData:
    for sd in skills:
        if sd.name == name:
            return sd
    raise ValueError(f"unknown skill: {name!r}; installed: {[s.name for s in skills]}")


def main() -> None:
    server = Server(name="comfyui-chenxin-mcp", version="0.2.0")
    skills = discover_skills()

    @server.tool(
        name="list_skills",
        description="List installed camera skills and their stages.",
        input_schema={"type": "object", "additionalProperties": False},
    )
    async def list_tools() -> dict:
        return {
            "skills": [
                {"name": sd.name, "stages": list(sd.stages), "output_type": sd.output_type}
                for sd in skills
            ]
        }

    @server.tool(
        name="describe_config",
        description="Return the full schema (defaults, groups, enums, dependencies) for a skill stage.",
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
            },
            "required": ["skill", "stage"],
            "additionalProperties": False,
        },
    )
    async def describe(skill: str, stage: str) -> dict:
        sd = _find_skill(skills, skill)
        return describe_config(sd, stage)

    @server.tool(
        name="validate_config",
        description="Validate a config dict before running a skill.",
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
                "config": {"type": "object"},
            },
            "required": ["skill", "stage", "config"],
            "additionalProperties": False,
        },
    )
    async def validate(skill: str, stage: str, config: dict) -> dict:
        sd = _find_skill(skills, skill)
        return validate_config(sd, stage, config)

    @server.tool(
        name="run_skill",
        description="Run a skill stage (e.g. t2i-camera generation).",
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "stage": {"type": "string"},
                "envelope": {"type": "object"},
                "config": {"type": "object"},
                "output_dir": {"type": "string", "default": "outputs"},
            },
            "required": ["skill", "stage", "envelope", "config"],
            "additionalProperties": False,
        },
    )
    async def run(skill: str, stage: str, envelope: dict, config: dict,
                  output_dir: str = "outputs") -> dict:
        sd = _find_skill(skills, skill)
        from runtime.config_schema import RunConfig
        run_config = RunConfig.from_envelope(envelope, **config)
        with _spawn_mcp() as mcp:
            payload, code = run_skill(
                mcp=mcp, skill_data=sd, stage=stage, config=run_config,
                output_dir=Path(output_dir),
            )
        return {"exit_code": code, "payload": payload}

    asyncio.run(server.serve_stdio())


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_registry.py -v --tb=short 2>&1 | tail -10`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/_mcp/src/comfyui_chenxin_mcp/registry.py skills/_mcp/src/comfyui_chenxin_mcp/server.py skills/_mcp/src/comfyui_chenxin_mcp/tests/test_registry.py
git commit -m "feat(server): rewrite registry + server with 4 unified tools

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: camera-image skill_data.py + entry-point

**Files:**
- Create: `skills/camera-image/camera_image/skill_data.py`
- Modify: `skills/camera-image/pyproject.toml` - change entry-point
- Create: `skills/camera-image/tests/test_skill_data.py`

**Interfaces:**
- Consumes: `SkillData` from Task 1; `describe_config`, `apply_run_config`, `NODE_FIELD_MAP`, `GROUPS` from `runtime/graph_patcher.py`; `prepare_temporary_workflow` from `runtime/source_workflow.py`
- Produces: `get_skill_data() -> SkillData`

- [ ] **Step 1: Write the failing test (uses real workflow source)**

```python
# skills/camera-image/tests/test_skill_data.py
"""camera-image skill_data tests - verify against real workflow source."""
from camera_image.skill_data import get_skill_data
from comfyui_chenxin_mcp.engine.skill_data import SkillData


def test_get_skill_data_returns_correct_fields():
    sd = get_skill_data()
    assert isinstance(sd, SkillData)
    assert sd.name == "camera-image"
    assert sd.stages == ("t2i-camera", "i2i-camera")
    assert sd.output_type == "images"
    assert sd.dialect_id == "anima"


def test_field_map_is_populated():
    sd = get_skill_data()
    assert len(sd.field_map) > 0
    assert any("sampling" in k for k in sd.field_map)


def test_dependency_rules_cover_controlnet():
    sd = get_skill_data()
    rule_strs = [r.condition + "->" + r.implies for r in sd.dependency_rules]
    assert any("controlnet_image" in r and "controlnet_lllite" in r.lower() for r in rule_strs)


def test_stage_images_cover_both_stages():
    sd = get_skill_data()
    assert "t2i-camera" in sd.stage_images
    assert "i2i-camera" in sd.stage_images
    i2i_specs = {s.config_key: s for s in sd.stage_images["i2i-camera"]}
    assert "reference_image" in i2i_specs
    assert i2i_specs["reference_image"].required is True


def test_describe_fn_works_with_real_workflow():
    """describe_fn must return a real schema from the source workflow."""
    sd = get_skill_data()
    result = sd.describe_fn("t2i-camera")
    assert result["stage"] == "t2i-camera"
    assert "slots" in result
    assert "sampling" in result["slots"]
    assert "groups" in result["slots"]


def test_prepare_fn_is_callable():
    sd = get_skill_data()
    assert callable(sd.prepare_fn)


def test_apply_fn_is_callable():
    sd = get_skill_data()
    assert callable(sd.apply_fn)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/Projects/comfyui-chenxin/skills/camera-image && PYTHONPATH=. python -m pytest tests/test_skill_data.py -v --tb=short 2>&1 | tail -10`
Expected: FAIL with `ModuleNotFoundError: No module named 'camera_image.skill_data'`

- [ ] **Step 3: Write skill_data.py**

```python
# skills/camera-image/camera_image/skill_data.py
"""camera-image skill data for the comfyui-chenxin-mcp engine.

Provides SkillData: field map, groups, dependency rules, stage images,
and function pointers to runtime.graph_patcher + runtime.source_workflow.
"""
from __future__ import annotations

from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
from runtime.config_schema import GROUPS, STAGES
from runtime.graph_patcher import NODE_FIELD_MAP, apply_run_config, describe_config
from runtime.source_workflow import prepare_temporary_workflow


def get_skill_data() -> SkillData:
    return SkillData(
        name="camera-image",
        stages=(STAGES.T2I, STAGES.I2I),
        source_workflow_path="workflow/source/文生图相机视角.json",
        groups_dir_pattern="workflow/{stage}/groups.json",
        field_map=NODE_FIELD_MAP,
        dependency_rules=(
            Rule(
                condition="config:controlnet_image",
                implies=f"group:{GROUPS.CONTROLNET_LLLITE}",
            ),
            Rule(
                condition=f"stage:{STAGES.I2I}",
                implies=f"group_auto:{GROUPS.LOAD_IMAGE}",
                direction="forward",
            ),
        ),
        stage_images={
            STAGES.T2I: (
                ImageSpec("controlnet_image", required=False, requires_group=GROUPS.CONTROLNET_LLLITE),
            ),
            STAGES.I2I: (
                ImageSpec("reference_image", required=True),
                ImageSpec("controlnet_image", required=False, requires_group=GROUPS.CONTROLNET_LLLITE),
            ),
        },
        output_type="images",
        describe_fn=describe_config,
        apply_fn=apply_run_config,
        prepare_fn=prepare_temporary_workflow,
        dialect_id="anima",
    )
```

- [ ] **Step 4: Update pyproject.toml entry-point**

In `skills/camera-image/pyproject.toml`, change the entry-point from:
```toml
camera-image = "camera_image.mcp_bridge:register"
```
to:
```toml
camera-image = "camera_image.skill_data:get_skill_data"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /d/Projects/comfyui-chenxin/skills/camera-image && PYTHONPATH=. python -m pytest tests/test_skill_data.py -v --tb=short 2>&1 | tail -10`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add skills/camera-image/camera_image/skill_data.py skills/camera-image/pyproject.toml skills/camera-image/tests/test_skill_data.py
git commit -m "feat(camera-image): add skill_data + update entry-point contract

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Delete v1 files + rewrite smoke test + verify full suite

**Files:**
- Delete: `skills/_mcp/src/comfyui_chenxin_mcp/schema.py`
- Delete: `skills/_mcp/src/comfyui_chenxin_mcp/workflow_dir.py`
- Delete: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_schema.py`
- Delete: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_workflow_dir.py`
- Delete: `skills/camera-image/camera_image/mcp_bridge.py`
- Delete: `skills/camera-image/runtime/t2i_camera.py`
- Delete: `skills/camera-image/runtime/i2i_camera.py`
- Delete: `skills/camera-image/runtime/validators.py`
- Delete: `skills/camera-image/tests/test_mcp_bridge.py`
- Rewrite: `skills/_mcp/src/comfyui_chenxin_mcp/tests/test_server_smoke.py`

**Interfaces:**
- Consumes: all previous tasks
- Produces: clean v2 with no dead code, full test suite passing

- [ ] **Step 1: Delete v1 files**

```bash
cd /d/Projects/comfyui-chenxin
git rm skills/_mcp/src/comfyui_chenxin_mcp/schema.py
git rm skills/_mcp/src/comfyui_chenxin_mcp/workflow_dir.py
git rm skills/_mcp/src/comfyui_chenxin_mcp/tests/test_schema.py
git rm skills/_mcp/src/comfyui_chenxin_mcp/tests/test_workflow_dir.py
git rm skills/camera-image/camera_image/mcp_bridge.py
git rm skills/camera-image/runtime/t2i_camera.py
git rm skills/camera-image/runtime/i2i_camera.py
git rm skills/camera-image/runtime/validators.py
git rm skills/camera-image/tests/test_mcp_bridge.py
```

- [ ] **Step 2: Rewrite smoke test for 4 unified tools**

```python
# skills/_mcp/src/comfyui_chenxin_mcp/tests/test_server_smoke.py
"""Server smoke test - spawn real server, verify 4 unified tools."""
import json
import subprocess
import sys
import pytest


@pytest.fixture
def server_proc():
    proc = subprocess.Popen(
        [sys.executable, "-m", "comfyui_chenxin_mcp.server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _send(proc, msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read()
        pytest.fail(f"server stdout closed. stderr: {stderr[:500]}")
    return json.loads(line)


def _initialize(proc):
    _send(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    })
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
    }) + "\n")
    proc.stdin.flush()


def test_server_handshake_lists_unified_tools(server_proc):
    _initialize(server_proc)
    lst = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })
    names = [t["name"] for t in lst["result"]["tools"]]
    assert "list_skills" in names
    assert "describe_config" in names
    assert "validate_config" in names
    assert "run_skill" in names
    assert "describe_camera_config" not in names
    assert "run_t2i_camera" not in names


def test_list_skills_returns_camera_image(server_proc):
    _initialize(server_proc)
    out = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "list_skills", "arguments": {}},
    })
    text = json.loads(out["result"]["content"][0]["text"])
    assert any(s["name"] == "camera-image" for s in text["skills"])


def test_describe_config_returns_schema(server_proc):
    _initialize(server_proc)
    out = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "describe_config",
                   "arguments": {"skill": "camera-image", "stage": "t2i-camera"}},
    })
    text = json.loads(out["result"]["content"][0]["text"])
    assert text["stage"] == "t2i-camera"
    assert "sampling" in text["slots"]


def test_validate_config_returns_ok(server_proc):
    _initialize(server_proc)
    out = _send(server_proc, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "validate_config",
                   "arguments": {"skill": "camera-image", "stage": "t2i-camera",
                                 "config": {"draft": {"positive": "1girl", "negative": "lowres"}}}},
    })
    text = json.loads(out["result"]["content"][0]["text"])
    assert text["ok"] is True
```

- [ ] **Step 3: Install both packages fresh**

```bash
cd /d/Projects/comfyui-chenxin
pip install -e ./skills/_mcp --quiet
pip install -e ./skills/camera-image --quiet
```

- [ ] **Step 4: Run the full test suite**

```bash
cd /d/Projects/comfyui-chenxin
python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/ --tb=short -q 2>&1 | tail -15
cd /d/Projects/comfyui-chenxin/skills/camera-image && PYTHONPATH=. python -m pytest tests/ --tb=short -q 2>&1 | tail -15
```
Expected: all tests pass. No import errors from deleted files.

- [ ] **Step 5: Run smoke test specifically**

```bash
cd /d/Projects/comfyui-chenxin && python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_server_smoke.py --tb=long -q 2>&1 | tail -15
```
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
cd /d/Projects/comfyui-chenxin
git add -A
git commit -m "refactor(v2): delete v1 files, rewrite smoke test for unified tools

Deletes: schema.py, workflow_dir.py, mcp_bridge.py, t2i_camera.py,
i2i_camera.py, validators.py + their tests.
Rewrites smoke test for 4 unified tools (list_skills/describe/validate/run).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**
- Decision 1 (unified 4 tools): Task 5 (server.py) + Task 7 (smoke test) ✅
- Decision 2 (shared execution engine): Task 4 (engine/execute.py) ✅
- Decision 3 (skills are pure data): Task 1 (SkillData) + Task 6 (camera-image skill_data) ✅
- Decision 4 (declarative dependency rules): Task 2 (engine/validate.py + Rule) ✅
- Decision 5 (schema.py deleted): Task 7 ✅
- Decision 6 (mcp_bridge.py deleted): Task 7 ✅
- Decision 7 (entry-point contract change): Task 5 (registry) + Task 6 (pyproject.toml) ✅
- Boundary rules: engine imports only SkillData (function pointers), never runtime.* directly ✅
- Test data: Task 6 uses real workflow source ✅

**2. Placeholder scan:** No TBD/TODO. All code blocks are complete. ✅

**3. Type consistency:**
- `SkillData` fields consistent across Task 1 (definition), Task 2 (validate), Task 3 (describe), Task 4 (execute), Task 5 (server), Task 6 (camera-image) ✅
- `Rule.condition`/`implies` prefix format consistent across Task 1, Task 2, Task 6 ✅
- `RunConfig.from_envelope` consistent across Task 4 (definition) and Task 5 (server calls it) ✅
- `run_skill` parameters consistent across Task 4 (definition) and Task 5 (server calls it) ✅
