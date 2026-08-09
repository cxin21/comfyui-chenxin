# Architecture and first principles

## Bounded responsibilities

| Component | Owns | Must not own |
|---|---|---|
| Prompt Forge | Evidence, prompt dialect, prompt quality, envelope gate | ComfyUI, models, nodes, workflow compilation, execution |
| camera-image runtime | Fixed source workflow, semantic config compilation, group selection, graph contracts | MCP transport implementation, prompt authoring |
| comfyui-chenxin-mcp engine | Unified tool dispatch, image upload, queue control, execution, history, artifacts | Skill-specific node logic |
| comfyui-mcp | ComfyUI protocol operations, strip conversion, workflow validation, runtime checks | Product-level config semantics |
| ComfyUI | Node execution and history | Prompt authoring and skill policy |

## Data flow

```text
CreativeEvidence + caller draft
  -> Prompt Forge envelope gate
  -> camera-image semantic config
  -> fixed UI source + group selection
  -> MCP strip_workflow
  -> validated API graph
  -> local ComfyUI enqueue/history
  -> hashed PNG + submitted graph + run record
```

## Workflow authority

The camera runtime has one source workflow:

```text
skills/camera-image/camera_image/runtime/workflow_assets/camera-anima.json
```

It is a complete UI superset. Stage group files describe group membership, but
they do not replace the source workflow. Generated API JSON files are release
inspection artifacts, not runtime alternatives.

## Compiler boundary

The compiler is intentionally one-way:

```text
RunConfig -> UI widgets/modes -> strip -> API graph
```

The UI graph is mutated in memory before strip. The API graph is validated and
then treated as immutable. There is no temporary save/load round trip and no
post-strip repair layer.

## Contract layers

1. `validate_config` checks envelope shape and declared feature dependencies.
2. Group metadata validation checks caller titles, source node membership, and
   stage-required groups.
3. `validate_api_graph` checks resolved API references and image output paths.
4. ComfyUI MCP validates the exact graph against installed node contracts.
5. Runtime checks require the local execution environment.
6. Artifact verification proves that execution produced the requested output.

Each layer has one authority and one failure boundary. A later layer does not
silently repair an earlier invalid result.

## Layer boundaries

- `comfyui_chenxin_mcp.engine.*` imports no skill runtime module.
- `skills/*/runtime/*` imports no MCP engine module.
- `skills/*/skill_data.py` supplies the explicit function-pointer bridge.
- The MCP server exposes four unified tools regardless of skill count.

## Virgin principle

The current contract is designed as the only contract:

- no legacy endpoint;
- no old workflow fallback;
- no API/UI dual runtime authority;
- no silent feature downgrade;
- no compatibility shim for changed node types;
- no graph patch after conversion.

When a contract changes, update the source asset, compiler, schema, tests, and
documentation together, then remove the superseded behavior.

## Verification

Offline checks:

```powershell
$root = (Get-Location).Path
Push-Location (Join-Path $root "skills/camera-image/camera_image")
$env:PYTHONPATH = (Get-Location).Path
python -m pytest runtime/tests -q
Pop-Location
$env:PYTHONPATH = $root
python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests -q
```

Live checks are defined in [`camera-image-flow.md`](camera-image-flow.md) and
require actual PNG output plus submitted-graph assertions.
