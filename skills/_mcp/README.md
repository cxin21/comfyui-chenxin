# comfyui-chenxin-mcp

A stdio MCP 2024-11-05 server that exposes [comfyui-chenxin](https://github.com/) plugin skills (camera-image, camera-multiview, camera-video, ...) to MCP-compatible hosts: Claude Desktop, Claude Code, Codex, OpenCode, etc.

The server is a thin transport. The real work is in `engine/` (shared execution core) and the skill packages that advertise themselves through Python entry-points.

## What it does

The server registers exactly **4 tools** and dispatches every call to the engine, which in turn calls into whichever skill the caller named:

| Tool | Purpose |
|------|---------|
| `list_skills` | Enumerate installed skills and their stages. |
| `describe_config` | Return the full schema (defaults, groups, enums, dependencies) for a stage. |
| `validate_config` | Validate a config + envelope before running. |
| `run_skill` | Execute a stage end-to-end. |

Tool count does not grow with the number of skills. Adding a new skill is a `pip install` plus an entry-point declaration in the skill's own `pyproject.toml` — no edits to this package.

## Architecture

```
comfyui_chenxin_mcp/
  protocol.py          JSON-RPC 2.0 + MCP 2024-11-05 stdio framing
  registry.py          Entry-point discovery (comfyui_chenxin_mcp.skills group)
  server.py            Registers 4 unified tools, dispatches by skill name
  engine/
    skill_data.py      SkillData + ImageSpec + Rule dataclasses (data contract)
    describe.py        describe_config(skill_data, stage) -> schema dict
    validate.py        validate_config(skill_data, stage, config) -> {ok, errors}
    execute.py         run_skill(mcp, skill_data, stage, config) -> {exit_code, payload}
    prompt_forge.py    compile_envelope gate (calls prompt-forge subprocess)
    mcp_client.py      Wraps the comfyui-mcp stdio subprocess as a Python client
    state.py           Local attempt-state ledger
  tools/               MCP tool definitions (one module per tool)
  tests/               Engine unit + integration tests
```

Skills live in their own packages (e.g. `skills/camera-image/`) and provide a single entry-point that returns a `SkillData` describing what they can do plus function pointers the engine calls.

### Boundary rules

| Layer | Must not import |
|-------|-----------------|
| `comfyui_chenxin_mcp/engine/*` | any `camera_image.runtime.*` (or any other skill's `runtime.*`). The engine talks to skills only via `SkillData` function pointers. |
| any `camera_image/runtime/*` | `comfyui_chenxin_mcp`. Runtime is pure skill logic. |
| `camera_image/skill_data.py` | nothing else — it is the single bridge. It may import both `comfyui_chenxin_mcp.engine.skill_data` (for the dataclass) and `camera_image.runtime.*` (for the function pointers). |

A `runtime.*` module that imports `comfyui_chenxin_mcp` will create a cycle that the engine's import-order independence depends on. Don't.

## Installation

```bash
# 1. Install the MCP server
pip install -e skills/_mcp

# 2. Install the skill packages you want
pip install -e skills/camera-image
pip install -e skills/camera-multiview   # when available
pip install -e skills/camera-video       # when available
```

The MCP server has no Python dependencies of its own (it spawns `npx comfyui-mcp` as a subprocess for ComfyUI communication). Skills depend on the server package only for the `SkillData` dataclass.

## Running the server

### Automatic (recommended)

Add to your MCP host's config (e.g. Claude Desktop's `claude_desktop_config.json` or the project's `.codex-plugin/plugin.json`):

```json
{
  "mcpServers": {
    "comfyui-chenxin": {
      "command": "comfyui-chenxin-mcp-server"
    }
  }
}
```

The host launches the server as a child process and talks JSON-RPC 2.0 over stdio.

### Manual

```bash
comfyui-chenxin-mcp-server
# or
python -m comfyui_chenxin_mcp.server
```

The server prints nothing on success; it sits waiting for JSON-RPC on stdin.

## The 4 unified tools

### `list_skills()`

Enumerate installed skills.

**Input:** `{}`

**Output:**

```json
{
  "skills": [
    { "name": "camera-image", "stages": ["t2i-camera", "i2i-camera"], "output_type": "images" }
  ]
}
```

### `describe_config(skill, stage)`

Return the full schema for a stage.

**Input:**

```json
{ "skill": "camera-image", "stage": "t2i-camera" }
```

**Output:** Whatever the skill's `describe_fn` returns. For `camera-image` this includes `stage`, `workflow`, `source_workflow`, and a `slots` object enumerating every tunable (sampling, camera, camera_extra, image_size, lora, groups, seed, controlnet_image, reference_image, red_image, green_image, blue_image, red_prompt, green_prompt, blue_prompt, signature_image, ...). See `skills/camera-image/SKILL.md` for the slot list.

### `validate_config(skill, stage, config)`

Run declarative dependency-rule checks plus envelope shape checks.

**Input:**

```json
{
  "skill": "camera-image",
  "stage": "t2i-camera",
  "config": {
    "evidence": { "locked_facts": [...] },
    "draft":    { "positive": "...", "negative": "..." },
    "groups":   { "g1": [...], "g2": [...] }
  }
}
```

**Output:**

```json
{ "ok": true, "errors": [], "stage": "t2i-camera", "skill": "camera-image" }
```

Errors are structured strings. Example for a rule violation:

```json
{
  "ok": false,
  "errors": ["config 'reference_image' required by group '加载图片（G1）' (dependency rule)"],
  "stage": "t2i-camera",
  "skill": "camera-image"
}
```

### `run_skill(skill, stage, envelope, config, output_dir?)`

Execute a stage end-to-end.

**Input:**

```json
{
  "skill": "camera-image",
  "stage": "t2i-camera",
  "envelope": {
    "evidence":  { "locked_facts": [...] },
    "draft":     { "positive": "...", "negative": "..." },
    "dialect_id": "anima"
  },
  "config": {
    "camera":       { "direction": "front", "elevation": "eye-level", "distance": "medium" },
    "sampling":     { "steps_first": 30, "cfg": 4.5 },
    "seed":         42,
    "image_size":   { "width": 1216, "height": 832 },
    "lora":         { "selections": ["add_detail"] },
    "groups":       { "g1": ["面部 ADetailer（G1）"], "g2": [] },
    "controlnet_image": null,
    "reference_image": null,
    "red_image":      null,
    "green_image":    null,
    "blue_image":     null,
    "red_prompt":     null,
    "green_prompt":   null,
    "blue_prompt":    null,
    "signature_image": null
  },
  "output_dir": "outputs"
}
```

`output_dir` defaults to `"outputs"`. The engine creates `outputs/runs/<stage>_<timestamp>/` and writes `submitted-graph.json` and `run-record.json` there.

**Output (success):**

```json
{
  "exit_code": 0,
  "payload": {
    "accepted": true,
    "stage": "t2i-camera",
    "prompt_id": "abc-123-...",
    "artifact": {
      "filename": "t2i-camera_00001_.png",
      "subfolder": "",
      "path": "outputs/t2i-camera_00001_.png",
      "bytes": 712345,
      "sha256": "..."
    },
    "duration_ms": 12345,
    "run_record_path": "outputs/runs/t2i-camera_1700000000/run-record.json",
    "prompt_forge_warnings": []
  }
}
```

**Output (failure):**

```json
{
  "exit_code": 1,
  "payload": {
    "accepted": false,
    "stage": "t2i-camera",
    "error": "prompt-forge rejected envelope: ..."
  }
}
```

## Adding a new skill

The contract is intentionally minimal — a skill is pure data plus 3 function pointers.

1. **Create a Python package** with this layout:

   ```
   my-skill/
     pyproject.toml
     my_skill/
       __init__.py
       skill_data.py        # provides get_skill_data() -> SkillData
       runtime/             # skill-specific logic
         ...
   ```

2. **Declare the entry-point** in `pyproject.toml`:

   ```toml
   [project.entry-points."comfyui_chenxin_mcp.skills"]
   my-skill = "my_skill.skill_data:get_skill_data"
   ```

3. **Implement `get_skill_data()`**:

   ```python
   from comfyui_chenxin_mcp.engine.skill_data import SkillData, Rule, ImageSpec
   from my_skill.runtime.graph_patcher import describe_config, apply_run_config
   from my_skill.runtime.source_workflow import prepare_temporary_workflow
   from my_skill.runtime.config_schema import RunConfig, STAGES

   def get_skill_data() -> SkillData:
       return SkillData(
           name="my-skill",
           stages=(STAGES.MAIN,),
           source_workflow_path="workflow/source/...",
           groups_dir_pattern="workflow/{stage}/groups.json",
           field_map={},  # optional metadata
           dependency_rules=(),  # tuple of Rule(condition, implies, direction)
           stage_images={STAGES.MAIN: ()},  # tuple of ImageSpec(config_key, required, requires_group)
           output_type="images",  # or "videos"
           describe_fn=describe_config,
           prepare_fn=prepare_temporary_workflow,
           build_config_fn=RunConfig.from_envelope,
           dialect_id="anima",  # or your own
       )
   ```

4. **Implement the 3 function pointers** in your `runtime/`:

   - `describe_config(stage) -> dict` — return whatever schema you want; the engine passes it through unchanged.
   - `prepare_temporary_workflow(mcp, *, stage, config, groups, mcp_list_loras=None) -> dict` — given an MCP client, stage, `RunConfig | None`, and `GroupsConfig | None`, return an API-format workflow dict (the engine does the temp file + ComfyUI upload).
   - `build_config_fn(envelope, **tunables) -> RunConfig` — turn the JSON envelope + tunables into your skill's `RunConfig` dataclass. Engine calls this with `(envelope, camera=..., sampling=..., ...)`.

5. **Install** with `pip install -e my-skill/`. The server picks it up at the next startup.

### Declarative dependency rules

Rules are data, not procedural if-checks. Each `Rule` has:

- `condition` — one of `config:<key>`, `group:<title>`, `stage:<id>`, `group_auto:<title>`
- `implies` — same vocabulary
- `direction` — `bidirectional` (default) or `forward`

The engine's `validate_config` walks every rule and emits a structured error for any unmet implication. Add rules to your `SkillData.dependency_rules` and the engine handles the rest.

Example (from `camera-image`):

```python
Rule(
    condition="config:controlnet_image",
    implies="group:ControlNet LLLite（G1）",
)
```

Means: if `config.controlnet_image` is set, `groups.g1` must contain `ControlNet LLLite（G1）`, AND if `ControlNet LLLite（G1）` is in `groups.g1`, `config.controlnet_image` must be set.

A `forward` rule only fires in one direction:

```python
Rule(
    condition="group:区域提示词（G1）",
    implies="config:red_prompt",
    direction="forward",
)
```

Means: enabling the group requires `red_prompt`, but providing `red_prompt` does not force the group on.

### Stage images

`SkillData.stage_images[stage]` is a tuple of `ImageSpec(config_key, required, requires_group=None)`. The engine uploads them **in order** before the workflow runs, replacing the local path with the ComfyUI-assigned filename on the config object the patcher sees.

```python
ImageSpec("reference_image", required=True),
ImageSpec("controlnet_image", required=False, requires_group="ControlNet LLLite（G1）"),
```

Upload semantics:

- A spec with `requires_group=<title>` is only uploaded when that group is enabled (or auto-enabled).
- A spec marked `required=True` is always uploaded (e.g. i2i's `reference_image`).
- A spec with no `requires_group` is always uploaded (rare).

### Output type

`SkillData.output_type` is `"images"` or `"videos"`. The download step in `engine.execute._download_artifact` reads this and pulls the first output of that type from the history entry. Use `"videos"` for `camera-video` when it lands.

## Tests

```bash
# engine unit + integration tests
pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/

# smoke test (spawns the real stdio server)
pytest skills/_mcp/src/comfyui_chenxin_mcp/tests/test_server_smoke.py
```

Coverage:

- `test_protocol.py` — JSON-RPC 2.0 / MCP 2024-11-05 framing.
- `test_registry.py` — entry-point discovery picks up `camera-image` from the installed package.
- `test_skill_data.py` — `SkillData` field validity for `camera-image`.
- `test_engine_describe.py` — `describe_config` returns expected slot names against the real source workflow.
- `test_engine_validate.py` — declarative `Rule` checks fire in both directions; envelope shape validated.
- `test_engine_execute.py` — `run_skill` flow with mocked `McpClient`; upload order; `output_type` routing; `groups=None` regression.
- `test_mcp_client.py` — comfyui-mcp subprocess wrapper.
- `test_server_smoke.py` — spawns the real `comfyui-chenxin-mcp-server`, exercises all 4 tools end-to-end.

## Reference

- The 2026-08-08 redesign spec: `docs/superpowers/specs/2026-08-08-mcp-skill-engine-redesign.md`.
- The skill that uses this server: `skills/camera-image/SKILL.md`.
- The original v1 spec (superseded): `docs/superpowers/specs/2026-08-08-comfyui-chenxin-mcp.md` — historical only.