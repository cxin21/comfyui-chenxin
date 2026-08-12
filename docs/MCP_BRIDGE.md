# MCP Prompt Forge bridge

The MCP bridge has two responsibilities: expose Prompt Forge authoring as a
single parameterized tool, and gate camera execution against a verified build.
It does not convert raw prompt prose into a request and does not infer a task.

## Authoring tool

One tool covers every authoring task — the surface does not grow per model:

- `compile_prompt_artifact(task, request)` — build a verified model-native
  prompt and register its BuildLog.

`task` is one of `anima` | `h3_t2va` | `h3_ref2va`. The request shape is
task-specific (see the tool description or the prompt-forge skill). The tool
returns a slim `{ref_id, prompt, metadata}` dict; the full audit trail lives
server-side in the BuildLog registry, keyed by the 32-character `ref_id`.

Adding a model adds a `_TASKS` entry in
`mcp_server/src/comfyui_chenxin_mcp/engine/prompt_forge.py` and a coerce
function in `server.py` — never a new MCP tool.

## Camera boundary

`validate_config` and `run_skill` receive:

```json
{
  "envelope": {"prompt": {"...": "model-native prompt"}, "prompt_ref": "32-char ref id"},
  "config": {"...": "camera-owned runtime settings"}
}
```

The envelope contains exactly `prompt` (and optionally `prompt_ref`). When a
ref id is given, the server resolves the BuildLog and re-runs the full
verification (status production_ready, task/model match, token verification,
no sacrificed facts, no conflict, correct model-native prompt keys, valid
knowledge hash, unchanged content hash, matching reference count/order/owner/
dimensions, and matching H3 duration) before executing. Without a ref id the
prompt dict is trusted as already-built and validated.

Camera graph patchers re-run the same gate (`compile_prompt_gate`) before
extracting prompt text. There is no second prompt source and no
direct-patcher bypass.

The shared execution engine records the resolved prompt (and optional
`prompt_ref`) in the run record, uploads declared assets, validates the exact
graph and local runtime, enqueues once, waits for terminal history, downloads
outputs, and records output SHA-256. Prompt Forge remains offline and
ignorant of graph nodes and execution settings.
