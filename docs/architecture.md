# Architecture and first principles

## Bounded responsibilities

| Component | Owns | Must not own |
|---|---|---|
| Prompt Forge | Evidence, prompt dialect, prompt quality, envelope gate | ComfyUI, models, nodes, workflow compilation, execution |
| camera-image runtime | Fixed source workflow, semantic config compilation, group selection, graph contracts | MCP transport implementation, prompt authoring |
| camera-multiview runtime | Fixed API workflow, two-image binding, pose asset integrity, all-output collection | MCP transport implementation, prompt authoring, group selection |
| camera-video runtime | Three fixed MiniMax H3 API workflows, strict prompt/duration/image binding, MP4 artifact contract | MCP transport implementation, prompt authoring, workflow discovery, compatibility branches |
| comfyui-chenxin-mcp engine | Unified tool dispatch, image upload, queue control, execution, history, artifacts | Skill-specific node logic |
| comfyui-mcp | ComfyUI protocol operations, strip conversion, workflow validation, runtime checks | Product-level config semantics |
| ComfyUI | Node execution and history | Prompt authoring and skill policy |

## Data flow

```text
CreativeEvidence + caller draft
  -> Prompt Forge envelope gate
  -> camera-image, camera-multiview, or camera-video semantic config
  -> fixed UI source + group selection (camera-image)
  -> fixed API source (camera-multiview/camera-video)
  -> validated API graph
  -> local ComfyUI enqueue/history
  -> hashed PNG/MP4 + submitted graph + run record
```

## Workflow authority

The camera runtime has one source workflow:

```text
skills/camera-image/camera_image/runtime/workflow_assets/camera-anima.json
```

It is a complete UI superset. Stage group files describe group membership, but
they do not replace the source workflow. Generated API JSON files are not
runtime alternatives for `camera-image`.

`camera-multiview` has a separate, directly executable API authority:

```text
skills/camera-multiview/camera_multiview/runtime/workflow_assets/Flux2-Klein人物一键多视图工作流.json
```

Its API file, `manifest.json`, and `pose/` directory are one immutable release
asset. Runtime must not discover, convert, repair, or replace them.

`camera-video` has three directly executable API authorities:

```text
skills/camera-video/camera_video/runtime/workflow_assets/minimax-h3-t2v.json
skills/camera-video/camera_video/runtime/workflow_assets/minimax-h3-i2v-single.json
skills/camera-video/camera_video/runtime/workflow_assets/minimax-h3-i2v-multi.json
```

The adjacent `manifest.json` locks each hash and declares the only writable
node IDs. Runtime does not convert, strip, discover, repair, or switch among
these graphs.

## Compiler boundaries

`camera-image` compiles one-way:

```text
RunConfig -> UI widgets/modes -> strip -> API graph
```

The UI graph is mutated in memory before strip. `camera-multiview` has no UI
compiler:

```text
RunConfig(two image paths) -> fixed API graph -> validate -> enqueue
```

`camera-video` also has no UI compiler:

```text
RunConfig(prompt, duration, optional image paths) -> fixed API graph -> validate -> enqueue
```

Both API graph families are validated and then treated as immutable. There is
no temporary save/load round trip or post-conversion repair layer.

## Contract layers

1. `validate_config` checks envelope shape and declared feature dependencies.
2. Group metadata validation checks caller titles, source node membership, and
   stage-required groups.
3. `validate_api_graph` checks resolved API references and image output paths.
4. ComfyUI MCP validates the exact graph against installed node contracts.
5. Runtime checks require the local execution environment.
6. Artifact verification proves that execution produced the requested output.

For `camera-video`, the skill-owned stage schema is the only public
configuration authority. The manifest is the only fixed-asset authority, and
the shared engine is the only transport/execution authority.

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
