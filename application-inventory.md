# Application inventory and boundaries

## Active skills

| Path | Responsibility | Side effects |
|---|---|---|
| `skills/prompt-forge/SKILL.md` | Author and audit prompt envelopes | None |
| `skills/camera-image/SKILL.md` | Compile and execute Anima camera T2I/I2I images | Local ComfyUI/MCP |
| `skills/camera-multiview/SKILL.md` | Execute the fixed Flux2-Klein character multiview API workflow | Local ComfyUI/MCP |
| `skills/camera-video/SKILL.md` | Execute fixed MiniMax H3 text/image-to-video API workflows | Local ComfyUI/MCP |

## camera-image runtime ownership

`skills/camera-image/` owns:

- the fixed UI source workflow;
- stage group membership contracts;
- semantic config-to-UI compilation;
- LoRA and ControlNet feature contracts;
- final API graph structural validation.

`skills/camera-multiview/` owns:

- the bundled exported API workflow;
- the thirteen immutable pose image assets and node mapping;
- the two-image configuration contract;
- fixed-asset hashing, API graph validation, and all-output collection.

`mcp_server/` owns the generic execution engine:

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

## Source-of-truth rules

The camera runtime source is:

```text
skills/camera-image/camera_image/runtime/workflow_assets/camera-anima.json
```

`camera-image` runtime never uses a discovered workflow, temporary saved
workflow, or API snapshot as an alternate source.

The multiview runtime source is separately pinned to:

```text
skills/camera-multiview/camera_multiview/runtime/workflow_assets/Flux2-Klein人物一键多视图工作流.json
```

`camera-multiview` uses this API file directly. It is not an inspection
snapshot and is not converted from a UI graph at runtime. Its adjacent
`manifest.json` and `pose/` directory are part of the same release asset.

The video runtime source is the three hash-locked API files under:

```text
skills/camera-video/camera_video/runtime/workflow_assets/
```

`camera-video` owns the three stage schemas, prompt/duration/image node
mapping, release-time graph normalization, fixed-asset validation, and MP4
artifact contract. It does not own MCP transport or runtime compatibility
branches.

The video release asset is intentionally narrower than the original exports:
isolated `UniBlockSwap` nodes and the optional
`MiniMaxH3MemoryEfficientSageAttentionPatch` are removed before hashing. This
is source-asset normalization; runtime never conditionally restores or skips
nodes.
