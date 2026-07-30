# Attribution

comfyui-chenxin is built on the shoulders of:

- **[Claude Code](https://claude.com/claude-code)** by Anthropic — the agent host platform that runs this plugin.
- **[comfyui-mcp](https://github.com/artokun/comfyui-mcp)** by [artokun](https://github.com/artokun) — the MCP driver (Layer 2) that provides the ~108 structured tools we route through.
- **[ComfyUI-Agent-Kit](https://github.com/SlavaSexton/ComfyUI-Agent-Kit)** by [SlavaSexton](https://github.com/SlavaSexton) — main inspiration for the multi-recipe breadth, knowledge substrate pattern, and 4-layer stack concept. Recipes in `recipes/MODELS.md` are "Adapted from SlavaSexton, MIT" where derivable.
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)** by comfyanonymous / Comfy-Org — the engine everything runs on.
- **[workflow_templates](https://github.com/Comfy-Org/workflow_templates)** by Comfy-Org — the 500+ workflow templates indexed in `templates_index.json`.
- **[ComfyUI-WaveSpeed](https://github.com/fofrpw/ComfyUI-WaveSpeed)** and **[KJNodes](https://github.com/kijai/ComfyUI-KJNodes)** by kijai — adapted-by references for Wan 2.2 node graph used in our `examples/`.

Individual file headers preserve upstream notices where applicable. License terms of each upstream project retain priority over this MIT license for their respective components.

## Inherited non-commercial notes

Some recipes inherit upstream license restrictions. Examples:

- **Anima** base weights: non-commercial
- **SUPIR** weights: non-commercial
- **Topaz / Magnific**: paid services (not bundled)

These are listed in their respective recipe YAML frontmatter so users can audit before generating.
