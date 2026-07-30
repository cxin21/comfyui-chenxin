---
description: One-shot install + bootstrap the comfyui-chenxin plugin.
argument-hint: (no args)
---

# /chenxin-init

Run the platform-appropriate installer followed by the machine-block bootstrap:

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts/install.ps1

# POSIX (bash / zsh)
bash scripts/install.sh
```

After install finishes, run the bootstrap:

```bash
bash scripts/bootstrap.sh
```

The installer (one of `scripts/install.{ps1,sh}`):

1. Registers the plugin in `~/.claude/settings.json` under `plugins` (uses
   the `Skill(update-config)` pattern — never edits `settings.json` directly
   via `Edit`).
2. Copies `mcp/mcp_servers.json` to `~/.claude/mcp_servers/comfyui-chenxin.json`.
3. Prints `/plugin install` instructions and the manual fallback if the
   user can't reach the marketplace yet.

The bootstrap (`scripts/bootstrap.sh`):

1. Calls `python mcp/extensions/auto_launch.py` to ensure ComfyUI is up.
2. Calls `python mcp/extensions/vram_decide.py` once to print the "machine
   block" (8 GB / 16 GB / 24 GB recommendation for the active models).

## When this fails

- If ComfyUI isn't reachable on `:8188`, the bootstrap prints the exact
  `python mcp/extensions/auto_launch.py --port 8188` command to launch it
  and waits up to 60 s.
- If `~/.claude/settings.json` is read-only, fall back to manual install:
  see `docs/architecture.md`.