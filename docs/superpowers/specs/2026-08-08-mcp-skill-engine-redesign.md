# MCP + Skill Engine Redesign Specification

**Date:** 2026-08-08
**Status:** draft
**Supersedes:** v1 per-skill approach (commits 40bff0c..753d81c)

## Context

The `comfyui-chenxin-mcp` v1 landed a working MCP server where each skill registers its own tools (`describe_camera_config`, `run_t2i_camera`, etc.). Three problems emerged:

1. **Dead code:** `schema.py` provides `describe_skill(skill, stage)` / `validate_config(skill, stage, config)` but no tool calls them -- each skill bridge bypasses them and calls `runtime.*` directly.
2. **Duplication:** `t2i_camera.py` and `i2i_camera.py` share 80+ lines of identical code (`_wait_for_completion`, `_parse_history`, `_download_artifact`). The only real difference is i2i uploads a reference image.
3. **Doesn't scale:** adding `camera-multiview` and `camera-video` would copy the per-skill bridge pattern (12+ tools, duplicated execution code, duplicated `_spawn_mcp`).

The three skills share the same execution protocol: describe configurable items + groups -> copy source workflow -> patch groups + config -> upload temp -> enqueue -> wait -> download. What differs per skill is only data (workflow file, field map, groups, dependency rules, stage names, output type).

## Decisions

1. **Unified tools (4, constant):** `list_skills`, `describe_config(skill, stage)`, `validate_config(skill, stage, config)`, `run_skill(skill, stage, envelope, config)`. Tool count does not grow with skills.
2. **Shared execution engine** in `comfyui_chenxin_mcp/engine/`: one generic `execute` function handles all skills. The per-skill `t2i_camera.py` / `i2i_camera.py` are deleted.
3. **Skills are pure data:** each skill provides a `SkillData` dataclass (field map, groups, dependency rules, stage images, output type) via entry-points. No per-skill tool registration code, no per-skill execution code.
4. **Declarative dependency rules:** group-config dependencies are data (a list of `Rule` objects), not procedural if/raise. The engine's validator checks them generically.
5. **`schema.py` deleted:** replaced by `engine/describe.py` + `engine/validate.py`, which are the actual dispatch layer the unified tools call.
6. **Per-skill `mcp_bridge.py` deleted:** the server registers the 4 unified tools itself; skills only provide `SkillData` via entry-points.
7. **Entry-point contract changes:** from `register(server: Server) -> None` to `get_skill_data() -> SkillData`.

## Architecture

```
comfyui_chenxin_mcp/                     # MCP server package
  protocol.py                            # JSON-RPC + MCP stdio framing (unchanged)
  registry.py                            # entry-point discovery (contract changes)
  server.py                              # registers 4 unified tools, dispatches by skill name
  engine/
    skill_data.py                        # SkillData dataclass + Rule + ImageSpec
    describe.py                          # describe_config(skill_data, stage) -> schema dict
    validate.py                          # validate_config(skill_data, stage, config) -> {ok, errors}
    execute.py                           # run_skill(mcp, skill_data, stage, config) -> {exit_code, payload}
  tests/                                 # engine unit tests

skills/camera-image/
  workflow/source/文生图相机视角.json      # source workflow (unchanged)
  workflow/t2i-camera/groups.json        # group definitions (unchanged)
  workflow/i2i-camera/groups.json        # group definitions (unchanged)
  skill_data.py                          # SkillData: field_map, groups, rules, stage_images, output_type
  runtime/
    graph_patcher.py                     # describe_config + apply_run_config (kept, engine calls via fn ptr)
    source_workflow.py                   # prepare_temporary_workflow (kept, engine calls via fn ptr)
    validators.py                        # deleted (replaced by engine/validate.py declarative rules)
    prompt_forge_bridge.py               # compile_envelope (kept, engine calls)
    mcp_client.py                        # McpClient (kept, engine uses)
    config_schema.py                     # RunConfig dataclass (kept)
    t2i_camera.py                        # deleted (logic in engine/execute.py)
    i2i_camera.py                        # deleted (logic in engine/execute.py)
    ...other runtime modules...          # kept (lora_resolver, camera_mapper, etc.)

skills/camera-multiview/                 # future: same structure, different data
skills/camera-video/                     # future: same structure, different data + output_type="videos"
```

### Boundary rules (unchanged from v1)

- `comfyui_chenxin_mcp/engine/*` must NOT directly import any skill's `runtime.*`. It calls skill-provided functions via `SkillData` function pointers.
- `runtime/*` must NOT import `comfyui_chenxin_mcp`. It is pure skill logic.
- `skill_data.py` is the only file that imports from both `runtime.*` (to provide function pointers) and `comfyui_chenxin_mcp.engine.skill_data` (for the dataclass).

## Components

### `engine/skill_data.py`

The data contract every skill provides:

```python
@dataclass(frozen=True)
class ImageSpec:
    config_key: str          # e.g. "reference_image", "controlnet_image"
    required: bool           # whether this image is mandatory for the stage
    requires_group: str | None = None  # group that must be enabled when this image is provided

@dataclass(frozen=True)
class Rule:
    """A declarative group-config dependency."""
    condition: str           # e.g. "config:controlnet_image", "group:controlnet_lllite", "stage:i2i-camera"
    implies: str             # e.g. "group:controlnet_lllite", "config:controlnet_image", "group_auto:load_image"
    direction: str = "bidirectional"  # "bidirectional" | "forward"

@dataclass(frozen=True)
class SkillData:
    name: str                          # "camera-image"
    stages: tuple[str, ...]            # ("t2i-camera", "i2i-camera")
    source_workflow_path: str          # relative to skill package
    groups_dir_pattern: str            # e.g. "workflow/{stage}/groups.json"
    field_map: dict[str, tuple[int, str]]  # NODE_FIELD_MAP
    dependency_rules: tuple[Rule, ...]
    stage_images: dict[str, tuple[ImageSpec, ...]]  # per-stage image upload specs
    output_type: str                   # "images" | "videos"
    describe_fn: Callable[..., dict]   # skill's own describe_config(stage) -> dict
    apply_fn: Callable[..., None]      # skill's own apply_run_config(graph, stage, config, **kwargs)
    prepare_fn: Callable[..., dict]    # skill's own prepare_temporary_workflow(mcp, stage, user_g1, user_g2) -> graph
    dialect_id: str = "anima"          # prompt-forge dialect
```

### `engine/describe.py`

Dispatches to the skill's `describe_fn`. The return shape is the same as v1: `{stage, slots, groups, dependencies}`.

### `engine/validate.py`

Checks declarative `dependency_rules` + envelope shape (`draft.positive` / `draft.negative` non-empty). Replaces both `runtime/validators.py` (deleted) and the procedural if/raise checks in `graph_patcher.apply_run_config`.

### `engine/execute.py`

The extracted + unified version of `t2i_camera.run_t2i` / `i2i_camera.run_i2i`. Flow:

1. `compile_envelope(config.evidence, config.draft, skill_data.dialect_id)` -- prompt-forge gate
2. Upload `stage_images[stage]` images (required first, optional if provided)
3. `mcp.health()` -- check ComfyUI queue is idle
4. `skill_data.prepare_fn(mcp, stage, user_g1, user_g2)` -- copy source + patch groups + upload temp + get API graph
5. `skill_data.apply_fn(graph, stage, config, ...)` -- write tunables to graph nodes
6. `mcp.validate_workflow(graph)` + `mcp.check_runtime(graph)`
7. `mcp.enqueue(graph)` -- submit to ComfyUI
8. `_wait_for_completion(mcp, prompt_id, timeout, poll_interval)` -- poll history
9. `_download_artifact(mcp, entry, output_dir, skill_data.output_type)` -- download result

Steps 8-9 are the duplicated code from t2i/i2i, now in one place. `_download_artifact` uses `skill_data.output_type` to find `"images"` or `"videos"` in the output.

### `server.py`

Registers 4 unified tools. Each tool takes `skill` as first parameter, looks up the `SkillData` from the discovered list, and dispatches to the engine.

### `registry.py` (contract change)

Entry-point group unchanged: `comfyui_chenxin_mcp.skills`.

Callable signature changes:
- v1: `register(server: Server) -> None` (binds tools)
- v2: `get_skill_data() -> SkillData` (returns data)

### `skills/camera-image/skill_data.py`

Provides `get_skill_data() -> SkillData` with camera-image's `NODE_FIELD_MAP`, `GROUPS`, dependency rules, stage images, and function pointers to `graph_patcher.describe_config`, `graph_patcher.apply_run_config`, `source_workflow.prepare_temporary_workflow`.

Entry-point in `pyproject.toml`:
```toml
[project.entry-points."comfyui_chenxin_mcp.skills"]
camera-image = "camera_image.skill_data:get_skill_data"
```

## Data Flow

```
LLM host
  -> tools/list
     <- 4 tools: list_skills, describe_config, validate_config, run_skill

  -> list_skills()
     <- [{name: "camera-image", stages: ["t2i-camera", "i2i-camera"]}, ...]

  -> describe_config(skill="camera-image", stage="t2i-camera")
     -> engine.describe_config(skill_data, "t2i-camera")
     -> skill_data.describe_fn("t2i-camera")
     <- {stage, slots, groups, dependencies}

  -> validate_config(skill="camera-image", stage="t2i-camera", config={...})
     -> engine.validate_config(skill_data, "t2i-camera", config)
     -> checks dependency_rules + envelope shape
     <- {ok: true, errors: []}

  -> run_skill(skill="camera-image", stage="t2i-camera", envelope={...}, config={...})
     -> _build_run_config(envelope, config)
     -> _spawn_mcp()
     -> engine.run_skill(mcp, skill_data, stage, run_config)
        1. compile_envelope(evidence, draft, dialect_id)
        2. upload stage_images (reference, controlnet)
        3. mcp.health()
        4. skill_data.prepare_fn(mcp, stage, g1, g2)
        5. skill_data.apply_fn(graph, stage, config)
        6. mcp.validate_workflow + check_runtime
        7. mcp.enqueue(graph)
        8. _wait_for_completion(mcp, prompt_id, timeout)
        9. _download_artifact(mcp, entry, output_dir, output_type)
     <- {exit_code: 0, payload: {accepted, prompt_id, artifact, ...}}
```

## Error Handling

- **Unknown skill:** JSON-RPC error if skill not in discovered list.
- **Unknown stage:** same, if stage not in `skill_data.stages`.
- **Validation failure:** `validate_config` returns `{ok: false, errors: [...]}` with specific rule violations.
- **Execution failure:** `run_skill` returns `{exit_code: 1, payload: {accepted: false, error: "..."}}`.
- **Prompt-forge rejection:** `compile_envelope` raises, caught by `run_skill`, returns exit_code=1.
- **ComfyUI queue not idle:** raises RuntimeError, caught, returns exit_code=1.
- **Download failure:** raises RuntimeError, caught, returns exit_code=1.

## Testing

- **Test data:** use the real source workflow at `skills/camera-image/workflow/source/` as actual test data for the entire flow (describe -> validate -> prepare -> apply). No mock workflow JSON.
- **Engine unit tests** (`comfyui_chenxin_mcp/tests/`):
  - `test_describe.py`: describe_config dispatches to skill_data.describe_fn, returns schema with real workflow
  - `test_validate.py`: each Rule type checked; envelope shape validated
  - `test_execute.py`: mock McpClient, verify call sequence; verify stage_images upload order; verify output_type routing
- **Skill data tests** (`skills/camera-image/tests/`):
  - `test_skill_data.py`: verify SkillData fields; verify describe_fn / apply_fn / prepare_fn callable against real workflow
- **Smoke test** (`comfyui_chenxin_mcp/tests/test_server_smoke.py`):
  - Spawn real server, `list_skills` returns camera-image, `describe_config` returns schema, `run_skill` dispatches correctly

## Scope

### In scope
- Redesign server to use 4 unified tools
- Extract shared execution engine from `t2i_camera.py` / `i2i_camera.py`
- Define `SkillData` dataclass + declarative `Rule` system
- Migrate `camera-image` to the new `skill_data.py` + entry-point contract
- Delete `schema.py`, per-skill `mcp_bridge.py`, `t2i_camera.py`, `i2i_camera.py`, `validators.py`
- Update smoke test + all affected unit tests

### Out of scope
- Implementing `camera-multiview` or `camera-video` (separate task)
- HTTP transport, auth, multi-tenant
- McpClient connection pooling (still per-call spawn)
- `runtime/graph_patcher.py` internal refactoring (NODE_FIELD_MAP stays as-is)
- `runtime/lora_resolver.py`, `runtime/camera_mapper.py` (skill-specific, untouched)

## Migration concern

The v1 code (commits 40bff0c..753d81c) just landed. This redesign supersedes v1.

**Implementation principle: 处女原则 (virgin principle).** Write v2 as if it's the first time -- how would you design it from scratch. Do NOT patch v1 files incrementally. Do NOT preserve backward compatibility. Do NOT add compat layers or migration shims. Write new files from scratch; delete v1 files that are superseded. If a v1 file's logic moves to the engine, write the engine fresh and delete the v1 file -- do not "refactor in place."

The plan sequences work so tests pass at each step, but each step writes clean new code, not patches on old code.

## Self-Review Checklist

1. Does the design solve all three problems (dead code, duplication, scalability)? Yes -- schema.py deleted, t2i/i2i merged, skills are pure data.
2. Are boundary rules preserved? Yes -- engine calls via function pointers, runtime doesn't import MCP.
3. Is the SkillData contract complete? Yes -- covers workflow path, field map, groups, rules, images, output type, function pointers, dialect.
4. Are dependency rules fully declarative? Yes -- Rule dataclass with condition/implies/direction, no procedural code.
5. Does the design support camera-video (different output type)? Yes -- output_type field.
6. Does the design support future skills without server changes? Yes -- entry-point discovery + SkillData.
7. Is the migration path sequenced? Yes -- extract engine first, then contract change, then delete old files.
8. Are tests specified? Yes -- engine unit tests + skill data tests + smoke test.
9. Is error handling complete? Yes -- unknown skill/stage, validation, execution, prompt-forge, queue, download.
10. Is the scope bounded? Yes -- multiview/video implementation is out of scope.
