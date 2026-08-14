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

1. Accept the direct model-native prompt envelope.
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

For `camera-multiview`, the shared engine uses the same transport and history
contract, while the skill runtime supplies an already-exported API graph. It
does not call `strip_workflow`; it patches only nodes `111` and `667`, hydrates
the thirteen fixed pose inputs idempotently, validates the graph, and sets
`artifact_mode=all` so every saved multiview image is downloaded.

Its public config is exactly:

```json
{
  "full_body_image": "E:/images/person-full-body.png",
  "face_image": "E:/images/person-face.png"
}
```

The returned `artifact` is a list for this skill. Each item contains the
downloaded path, byte count, and SHA-256. A prompt ID or a successful enqueue
without the complete list is not an accepted run.

For `camera-video`, the shared engine uses the same transport and history
contract with three fixed API stages: `t2v-video`, `i2v-video`, and
`multi-i2v-video`. The skill patches only prompt, duration, and the declared
reference-image nodes; it does not call `strip_workflow` or discover a source
workflow. The output type is `gifs` because `VHS_VideoCombine` stores saved MP4
files in ComfyUI history under that field. `artifact_mode=all` downloads and
hashes every saved MP4.

## Public tool shapes

### `list_skills`

Input: `{}`.

Example result:

```json
{
  "skills": [
    {"name": "camera-image", "stages": ["t2i-camera", "i2i-camera"], "output_type": "images"},
    {"name": "camera-multiview", "stages": ["multiview"], "output_type": "images", "artifact_mode": "all"},
    {"name": "camera-video", "stages": ["t2v-video", "i2v-video", "multi-i2v-video"], "output_type": "gifs", "artifact_mode": "all"}
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
  "envelope": {"prompt": {"positive": "...", "negative": "..."}},
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
  "envelope": {"prompt": {"positive": "...", "negative": "..."}},
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
camera-multiview = "camera_multiview.skill_data:get_skill_data"
camera-video = "camera_video.skill_data:get_skill_data"
```

`SkillData` supplies:

- stage names;
- source workflow path and group asset pattern;
- semantic field metadata;
- declarative dependency rules;
- stage-image upload specifications;
- output type;
- `describe_fn`, `prepare_fn`, and `build_config_fn`.

`artifact_mode` is `first` by default. A skill that produces a set rather than
one artifact may set it to `all`; `camera-multiview` and `camera-video` do this
explicitly.

The engine calls these pointers and does not know skill-specific node IDs.

## Installation

```powershell
powershell -ExecutionPolicy Bypass -File scripts\\install.ps1
```

