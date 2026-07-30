# comfyui-chenxin

> **Local-first ComfyUI mega-skill for Claude Code.**
> 74 model prompt recipes · 578 workflow templates · hardware-aware model selection · self-updating knowledge substrate · manga end-to-end pipeline.

[![License: MIT](https://img.shields.io/badge/License-MIT-FFD27D.svg)](LICENSE)
[![Claude Code: required](https://img.shields.io/badge/Claude_Code-plugin-5BAEE3.svg)](https://claude.com/claude-code)
[![ComfyUI: required](https://img.shields.io/badge/ComfyUI-local--GPU-9aa3b2.svg)](https://www.comfy.org/)

## What this is

A Claude Code plugin that turns your local ComfyUI + GPU into a media-generation lab. One install, one slash command, no cloud, no per-generation cost. Built on the official [comfyui-mcp](https://github.com/artokun/comfyui-mcp) MCP driver and inspired by [SlavaSexton/ComfyUI-Agent-Kit](https://github.com/SlavaSexton/ComfyUI-Agent-Kit)'s multi-agent, multi-recipe breadth.

## Install

```bash
/plugin marketplace add chenxin/comfyui-chenxin
/plugin install comfyui@chenxin
```

Then in any Claude Code session:

```text
/chenxin-init
```

Required: a local ComfyUI on `http://127.0.0.1:8188` and at least 8 GB of VRAM.

## Commands

| Command | Purpose |
|---|---|
| `/chenxin-init` | One-shot install + bootstrap machine block |
| `/chenxin-build [phase]` | Execute next unchecked phase; auto-opens PR |
| `/chenxin-review [--strict]` | Manually trigger 5-dim adversarial review |
| `/chenxin-doctor` | Health check + VRAM decision |
| `/chenxin-publish` | Bump version + release |
| `/chenxin-update` | Pull L3 knowledge deltas (recipes, templates) |

## Phases

This repo develops in 9 phases via git PRs, each gated by 5-dim adversarial review:

| # | Phase | Goal |
|---|---|---|
| P0.1 | Knowledge substrate | 74 recipes + 578 templates index |
| P0.2 | MCP enhancements | auto-launch, vram-decide, template-get, gui-save |
| P0.3 | Mega-skill | `chenxin-core` SKILL.md consolidates 11 prior skills |
| P1.1 | L5 decoupling | Apps moved into `skills/` |
| P1.2 | Self-update daemon | `check_updates.py` weekly |
| P1.3 | Obsidian sync | vault-bridge hook script |
| P2.1 | Marketplace publish | plugin.json + marketplace.json |
| P2.2 | Docs + tutorials | README, CONTRIBUTING, tutorials |

See [ROADMAP.md](ROADMAP.md) and [SPEC.md](SPEC.md) for live status.

## Architecture

See [docs/architecture.md](docs/architecture.md).

## License

MIT — see [LICENSE](LICENSE). Third-party components retain their own licenses — see [ATTRIBUTION.md](ATTRIBUTION.md).
