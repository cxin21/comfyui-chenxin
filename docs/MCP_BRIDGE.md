# MCP execution boundary

The project uses two MCP layers with different responsibilities:

```text
Codex / host
  -> comfyui-chenxin-mcp
       -> skill engine
            -> comfyui-mcp@0.49.8
                 -> local ComfyUI
```

## Project MCP server

`mcp_server` is the project server. It exposes exactly:

- `list_skills`
- `describe_config`
- `validate_config`
- `run_skill`

It discovers skills through Python entry points and calls their `SkillData`
function pointers. It does not know camera node IDs or implement feature
patches.

## ComfyUI MCP client

The engine's `McpClient` owns the subprocess contract with
`comfyui-mcp@0.49.8`. The camera workflow uses these operations:

| Operation | Purpose |
|---|---|
| `upload_image` | Upload local stage images and return ComfyUI filenames |
| `strip_workflow` | Convert the selected UI graph to API format (`camera-image` only) |
| `validate_workflow` | Validate the final API graph |
| `check_workflow_runtime` | Confirm the graph uses the local runtime |
| `enqueue_workflow` | Submit `{"workflow": graph}` |
| history/image operations | Wait for completion and download the artifact |

The exact MCP tool contract is owned by the installed `comfyui-mcp` package and
is checked during environment setup. Do not call an older `get_workflow` save/load
path for camera-image compilation, and do not call `strip_workflow` for an
already-exported API skill.

For `camera-multiview` and `camera-video`, the input graph is already API
format; the runtime intentionally does not call `strip_workflow`. The project
contract uses `comfyui-mcp@0.49.8` with the full workflow tool set. Older
validators may misread ComfyUI V3 autogrow keys such as `values.a`; that is a
tool-version failure boundary, not permission to mutate the fixed graph at
runtime.

Video artifacts are returned by ComfyUI under the history `gifs` field because
the fixed output node is `VHS_VideoCombine`. The media itself is MP4. The
engine downloads every saved item, including MCP responses that identify a
local video path rather than returning an inline image block, and records its
size and SHA-256.

## Boundary rules

- Prompt Forge does not call MCP.
- The camera runtime does not import the MCP engine.
- The engine does not import camera runtime modules directly.
- The UI-to-API converter is not reimplemented in project code.
- Conversion occurs once; no post-conversion graph repair is permitted.
- Missing capabilities fail closed before enqueue.

## Debugging order

When a run fails, inspect in this order:

1. `validate_config` result;
2. image upload result and returned filename;
3. `submitted-graph.json`;
4. project graph validation result;
5. ComfyUI `validate_workflow` result;
6. ComfyUI node error and history entry;
7. downloaded artifact and hash.

Do not infer success from a prompt ID or an idle queue. The final evidence is
the validated submitted graph plus the verified artifact.
