# comfyui-chenxin-mcp specification

Status: current implementation contract

## Purpose

Provide one MCP-native execution surface for installed skills. Keep transport,
queue, history, and artifact concerns in the shared engine; keep workflow
semantics in the skill package.

## Fixed interface

The stdio MCP server uses JSON-RPC 2.0 with MCP framing and exposes exactly:

- `list_skills`
- `describe_config`
- `validate_config`
- `run_skill`

The interface is skill-agnostic. Adding a skill adds a `SkillData` entry point;
it does not add a new tool family.

## Skill entry point

```toml
[project.entry-points."comfyui_chenxin_mcp.skills"]
camera-image = "camera_image.skill_data:get_skill_data"
```

`SkillData` contains stages, workflow metadata, dependency rules, stage-image
specifications, output type, and the skill-owned describe/prepare/config
functions.

## Runtime data flow

```text
MCP host
  -> list / describe / validate
  -> run_skill(envelope, config)
  -> build RunConfig
  -> Prompt Forge gate
  -> ordered image upload
  -> queue guard
  -> skill.prepare_fn
  -> final API graph validation
  -> local runtime check
  -> enqueue_workflow({"workflow": graph})
  -> history wait
  -> artifact download/hash
  -> run record
```

For camera-image, `prepare_fn` loads the fixed UI source, applies config and
group modes, calls `strip_workflow` once, and returns the validated API graph.

## Error contract

- Invalid envelope/config: `validate_config` returns `{ok:false, errors:[...]}`.
- Prompt gate failure: `run_skill` returns `exit_code=1`.
- Missing MCP capability or invalid graph: `run_skill` returns a typed failure.
- ComfyUI node error: fail immediately; do not wait for a successful history.
- Missing or invalid artifact: the run is unsuccessful.

No fallback workflow, compatibility interface, temporary save/load path, or
post-strip graph repair is part of the contract.

## Boundaries

- The engine does not import skill runtime modules.
- Skill runtime modules do not import the engine.
- `skill_data.py` is the explicit bridge.
- The upstream `comfyui-mcp` package owns ComfyUI protocol operations and strip
  conversion.
- Prompt Forge remains side-effect free.

## Verification

The engine tests cover MCP framing, registry discovery, schema dispatch,
dependency validation, execution sequencing, client response contracts, and
server smoke behavior. Camera-image tests cover fixed-source compilation,
group contracts, API graph structure, and real PNG acceptance.

See [`docs/camera-image-flow.md`](../../camera-image-flow.md) and
[`skills/_mcp/README.md`](../../../skills/_mcp/README.md).
