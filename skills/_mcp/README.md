# comfyui-chenxin-mcp

`comfyui-chenxin-mcp` is the project MCP server. It exposes one stable tool
surface and dispatches to installed skills through `SkillData`.

## Tools

The server registers exactly four tools:

| Tool | Contract |
|---|---|
| `list_skills` | List installed skills and their stages. |
| `describe_config` | Return the selected stage's semantic config schema. |
| `validate_config` | Validate envelope shape and dependency rules without rendering. |
| `run_skill` | Execute one stage and return a verified artifact. |

The server does not grow a new MCP tool for every skill. A skill registers an
entry point that returns `SkillData`; the engine owns the shared execution
protocol.

## Architecture

```text
MCP host
  -> server.py / JSON-RPC stdio
  -> registry.py / SkillData discovery
  -> engine/
       describe.py
       validate.py
       execute.py
       prompt_forge.py
       mcp_client.py
  -> skill runtime through SkillData function pointers
  -> comfyui-mcp@0.49.8
  -> local ComfyUI
```

The engine never imports a skill's runtime modules directly. A skill runtime
never imports `comfyui_chenxin_mcp`. `skill_data.py` is the only bridge between
the two layers.

## camera-image execution contract

For `camera-image`, `run_skill` performs the following exact sequence:

1. Compile the Prompt Forge envelope.
2. Upload declared stage images and replace local paths with ComfyUI filenames.
3. Require an idle local ComfyUI queue.
4. Call the skill's `prepare_fn`.
5. The skill loads its fixed UI asset, applies config and group modes, calls
   `strip_workflow` once, and validates the resulting API graph.
6. Call MCP `validate_workflow` on that exact graph.
7. Require the local runtime from `check_workflow_runtime`.
8. Enqueue with the current contract:

   ```json
   {"workflow": {"<node_id>": {"class_type": "...", "inputs": {}}}}
   ```

9. Reject returned `node_errors` immediately.
10. Poll history until success or timeout.
11. Download the designated artifact and write the submitted graph and run record.

There is no temporary workflow save/load round trip and no post-strip graph
mutation. A failed precondition returns a failed run; the engine does not
select an older graph or silently skip a feature.

## Public tool shapes

### `list_skills`

Input: `{}`.

Example result:

```json
{
  "skills": [
    {"name": "camera-image", "stages": ["t2i-camera", "i2i-camera"], "output_type": "images"}
  ]
}
```

### `describe_config`

```json
{"skill": "camera-image", "stage": "t2i-camera"}
```

The result is the skill-owned schema. Do not duplicate that schema in the MCP
server or hand-maintain a second field table.

### `validate_config`

Input:

```json
{
  "skill": "camera-image",
  "stage": "t2i-camera",
  "envelope": {
    "evidence": {"locked_facts": []},
    "draft": {"positive": "...", "negative": "..."},
    "dialect_id": "anima"
  },
  "config": {"groups": {"g1": [], "g2": []}}
}
```

Success:

```json
{"ok": true, "errors": [], "stage": "t2i-camera", "skill": "camera-image"}
```

Validation does not compile or render a graph. It checks request shape and
declared dependency rules; runtime graph validation happens inside `run_skill`
after group selection and strip.

### `run_skill`

The input is the same envelope/config pair plus `output_dir`:

```json
{
  "skill": "camera-image",
  "stage": "t2i-camera",
  "envelope": {
    "evidence": {"locked_facts": []},
    "draft": {"positive": "1girl, masterpiece", "negative": "lowres"},
    "dialect_id": "anima"
  },
  "config": {
    "sampling": {"steps_first": 30, "cfg": 4.5},
    "seed": 42,
    "image_size": {"width": 1216, "height": 832}
  },
  "output_dir": "outputs"
}
```

Success returns `exit_code=0`, `accepted=true`, a prompt ID, a non-empty
artifact with byte count and SHA-256, and `run_record_path`.

Failure returns `exit_code=1`, `accepted=false`, and a typed error message. Do
not treat queue submission, queue-idle state, or a prompt ID alone as success.

## Skill contract

An installed skill provides an entry point:

```toml
[project.entry-points."comfyui_chenxin_mcp.skills"]
camera-image = "camera_image.skill_data:get_skill_data"
```

`SkillData` supplies:

- stage names;
- source workflow path and group asset pattern;
- semantic field metadata;
- declarative dependency rules;
- stage-image upload specifications;
- output type;
- `describe_fn`, `prepare_fn`, and `build_config_fn`.

The engine calls these pointers and does not know skill-specific node IDs.

## Installation and checks

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$root = (Get-Location).Path
python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests -q
Push-Location (Join-Path $root "skills/camera-image/camera_image")
$env:PYTHONPATH = (Get-Location).Path
python -m pytest runtime/tests -q
Pop-Location
```

The live `camera-image` acceptance matrix is defined in
[`docs/camera-image-flow.md`](../../docs/camera-image-flow.md).
