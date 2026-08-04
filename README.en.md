# comfyui-chenxin

Local-first Prompt Forge runtime for a controlled character-to-video pipeline in ComfyUI. The production path is host-neutral: Codex, Claude Code, or another MCP host can provide the MCP invoker.

## Production path

```text
Prompt Forge positive/negative prompts
  → camera text-to-image → accepted front CharacterBaseImage
  → Flux2-Klein flat-v2 → accepted multiview reference
  → camera G1 img2img → accepted shot image
  → LTX Yusu Director + shot image/prompt → verified video
```

The runtime is fail-closed. Every handoff binds profile, workflow fingerprint, graph hash, artifact hash, lineage, raw ComfyUI history, approval, and one-time consumption evidence.

## Scope

The only active production skill is `skills/prompt-forge/SKILL.md`. Its runtime contains the prompt contracts, camera/Flux/Yusu adapters, trusted profiles, JSON CLI, local orchestrator, and host-neutral [`McpBridge`](docs/MCP_BRIDGE.md).

The old manga, LoRA-training, and ffmpeg skills are retained only for compatibility reading. They have `status: legacy` and empty trigger lists; they are not alternative production entry points. The unimplemented `manga-stage-1-lora` placeholder was removed.

## Prerequisites

- ComfyUI at `http://127.0.0.1:8188`;
- the exact saved workflows, models and Custom Nodes required by the profiles;
- Python 3.11+ for the runtime and `ffprobe` for video metadata checks;
- an MCP host registered with `mcp/mcp_servers.json`.

The repository does not ship ComfyUI, model weights, Custom Nodes, saved workflow entities, or host SDKs.

## Install

`bash scripts/install.sh` and `scripts/install.ps1` install the upstream MCP registration and provide a Claude Code registration example. Other MCP hosts should register the same stdio server using their own configuration and pass a `host_call_tool(tool_name, arguments)` function to `McpBridge`.

## Verification

```bash
PYTHONPATH=skills/prompt-forge pytest -q skills/prompt-forge
python -m compileall -q skills/prompt-forge/runtime
ruff check skills/prompt-forge/runtime
```

See:

- [`README.md`](README.md) — Chinese scope and usage;
- [`docs/USAGE.md`](docs/USAGE.md) — four-stage handoffs;
- [`docs/architecture.md`](docs/architecture.md) — layer boundaries;
- [`docs/MCP_BRIDGE.md`](docs/MCP_BRIDGE.md) — host adapter contract;
- [`skills/prompt-forge/SPEC.md`](skills/prompt-forge/SPEC.md) — prompt/runtime invariants.