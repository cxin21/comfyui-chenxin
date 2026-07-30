"""mcp.extensions — Layer-2 augmenting CLI tools for comfyui-mcp.

Each module is a standalone, stdlib-only Python CLI that emits JSON on stdout
and human-readable status on stderr. Designed to be invoked as subprocesses by
Claude Code agents (or any LLM agent with Bash access) to add capabilities the
upstream comfyui-mcp npm driver does not provide out of the box:

- auto_launch  : bring up a local ComfyUI on demand
- vram_decide  : hardware-aware model + quant + sampler recommendation
- template_get : lookup workflow templates from the index
- gui_save     : persist a workflow graph under <ComfyUI>/user/default/workflows/

All tools exit 0 on success, 2 on usage error, 3 on missing dependency, and
4 on network timeout.
"""