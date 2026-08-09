# Application inventory and boundaries

## Active skills

| Path | Responsibility | Side effects |
|---|---|---|
| `skills/prompt-forge/SKILL.md` | Author and audit prompt envelopes | None |
| `skills/camera-image/SKILL.md` | Compile and execute Anima camera T2I/I2I images | Local ComfyUI/MCP |

## camera-image runtime ownership

`skills/camera-image/` owns:

- the fixed UI source workflow;
- stage group membership contracts;
- semantic config-to-UI compilation;
- LoRA and ControlNet feature contracts;
- final API graph structural validation;
- camera-image acceptance tests.

`skills/_mcp/` owns the generic execution engine:

- MCP tool dispatch;
- Prompt Forge gate invocation;
- image upload;
- ComfyUI queue and runtime checks;
- enqueue, history polling, artifact download, hashing, and run records.

The engine does not import skill runtime code directly. Skills provide
`SkillData` and function pointers through Python entry points.

## Prompt Forge boundary

Prompt Forge does not inspect or execute models, nodes, workflows, MCP, local
services, or hardware. It emits the prompt envelope consumed by the execution
engine.

## Source-of-truth rule

The camera runtime source is:

```text
skills/camera-image/camera_image/runtime/workflow_assets/camera-anima.json
```

Runtime never uses a discovered workflow, temporary saved workflow, or API
snapshot as an alternate source.
