---
description: Health check + VRAM decision. Use when generation fails or feels slow.
argument-hint: (no args)
---

# /chenxin-doctor

Runs the haiku-powered `chenxin-doctor` agent:

1. `mcp__comfyui-mcp__health_check`  — ComfyUI version, GPU/VRAM, queue depth,
   per-category model populations, recent errors.
2. `python mcp/extensions/vram_decide.py --vram <N> --model <name>`  — for
   each recently-used model, re-print the recommended quant + sampler.
3. Smoke test the local P0.2 CLIs (`auto_launch`, `vram_decide`,
   `template_get`, `gui_save`) with `--help`.

Output: a one-screen report with:

- ComfyUI status (up/down, version, free VRAM)
- Queue depth (running + pending)
- Models that are present but should not be / missing but should be
- VRAM decision table for the top 5 most-used models

## When to run

- After `chenxin-build` if generation feels broken
- After upgrading ComfyUI or a custom node pack
- Weekly as part of `/chenxin-update` follow-up

## Exit semantics

| Result | Meaning                                                  |
|--------|----------------------------------------------------------|
| 0      | All checks passed                                        |
| 1      | One or more soft warnings (e.g. low free VRAM)            |
| 2      | ComfyUI unreachable — print manual start instructions    |
| 3      | Health check tool unavailable (MCP not connected)         |