# comfyui-chenxin-mcp execution contract

Status: current execution contract

## Purpose

Expose a fixed four-tool MCP surface for installed skills while keeping
skill-specific workflow semantics inside each skill package.

## Four tools

1. `list_skills`
2. `describe_config(skill, stage)`
3. `validate_config(skill, stage, envelope, config)`
4. `run_skill(skill, stage, envelope, config, output_dir?)`

The tool count does not grow with the number of skills.

## Skill contract

Each installed skill exposes a Python entry point returning `SkillData`:

```python
SkillData(
    name=...,
    stages=...,
    source_workflow_path=...,
    groups_dir_pattern=...,
    field_map=...,
    dependency_rules=...,
    stage_images=...,
    output_type=...,
    describe_fn=...,
    prepare_fn=...,
    build_config_fn=...,
)
```

The engine calls function pointers. It does not import skill runtime modules or
know their node IDs.

## Execution sequence

```text
build RunConfig
  -> prompt-forge gate
  -> ordered image upload
  -> health / queue guard
  -> skill.prepare_fn
  -> final graph validation
  -> local runtime check
  -> enqueue workflow
  -> reject node_errors
  -> history wait
  -> artifact download/hash
  -> submitted graph + run record
```

For camera-image, `prepare_fn` itself is the compiler boundary:

```text
fixed UI source
  -> config widgets
  -> group modes
  -> strip_workflow once
  -> API graph structural validation
```

The engine submits the returned API graph unchanged.

## MCP client contract

The project client wraps the installed `comfyui-mcp@0.49.8` contract. Enqueue
uses only:

```json
{"workflow": {"<node_id>": {"class_type": "...", "inputs": {}}}}
```

The client exposes only the operations required by the current flow. Missing
tools or unexpected response shapes fail closed.

## Boundaries

- Engine modules do not import skill runtime modules.
- Skill runtime modules do not import the MCP engine.
- `skill_data.py` is the explicit bridge.
- Prompt Forge remains side-effect free.
- No runtime workflow discovery replaces the fixed source asset.
- No fallback graph, compatibility shim, or post-strip repair exists.

## Verification

The engine test suite covers tool dispatch, validation, execution sequencing,
client contracts, and server smoke behavior. Camera-image adds source/group
contract tests and live PNG acceptance tests.

See [`docs/camera-image-flow.md`](../../camera-image-flow.md) and
[`skills/_mcp/README.md`](../../../skills/_mcp/README.md).
