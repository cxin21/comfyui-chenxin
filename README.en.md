# comfyui-chenxin

Claude Code plugin that ships five independent Skill-owned CLIs
(`anima-prompt-v1`, `minimax-h3-prompt`, `camera-image`, `camera-video`,
`camera-multiview`) and no longer depends on any MCP bridge.

## Skills and console scripts

| Skill | console script | Purpose |
|---|---|---|
| `skills/anima-prompt-v1/` | `anima-prompt-v1` | Anima image-prompt briefs, routing, audits, Catalog search, relation maintenance |
| `skills/minimax-h3-prompt/` | `minimax-h3-prompt` | MiniMax H3 T2VA / Ref2VA prompt authoring plus tokenizer + context-plan |
| `skills/camera-image/` | `camera-image` | Fixed Anima camera workflow (text-to-image / image-to-image) |
| `skills/camera-video/` | `camera-video` | Fixed MiniMax H3 video workflow (T2V / I2V / multi-I2V) |
| `skills/camera-multiview/` | `camera-multiview` | Fixed Flux2-Klein character multi-view |

Each console script follows the P1 JSON envelope contract (`ok` /
`command` / `stage` / `result` / `errors` / `advisories`) and maps the
failure category to a stable exit code (0 / 2 / 3 / 4 / 5 / 70).

## Install

Claude Code picks the plugin up via its marketplace:

1. Register this repository as the `comfyui-chenxin` plugin source
   in the marketplace, or `pip install -e` each package directly.
2. Reload the marketplace and the five CLIs are immediately
   available on PATH.

POSIX / PowerShell one-shot installer:

```bash
bash scripts/install.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

The installer only installs `runtime/comfyui_http` plus the five Skill
packages into the active venv. It does not edit any Codex
`config.toml`.

## Invocation examples

```bash
# Anima: author a structured brief
anima-prompt-v1 author --request brief.json --json

# Anima: Catalog lookup
anima-prompt-v1 catalog search "blue coat" --json | jq .

# MiniMax H3: T2VA authoring
minimax-h3-prompt author --stage t2va --request h3-request.json --json

# MiniMax H3: verify tokenizer integrity
minimax-h3-prompt tokenizer verify \
  --tokenizer-dir skills/minimax-h3-prompt/knowledge --json

# Camera Image: describe a stage's field map
camera-image describe --stage t2i-camera --json

# Camera Image: end-to-end run
camera-image run \
  --stage t2i-camera \
  --envelope envelope.json --config config.json \
  --output-dir out/ --json

# Camera Multiview: 5-pose asset verify
camera-multiview assets verify --stage multiview --json
```

## No MCP dependency

Earlier versions relied on a `comfyui-chenxin-mcp` server to bridge
Claude Code and ComfyUI. `mcp_server/`, `.mcp.json`, and
`.codex-plugin/` were removed in v2.0. Every Skill installs and runs
through its console script — no Node, no `npx`, no Codex
`config.toml` edits.

## Verification

```bash
# Source + a freshly staged cache both pass
python scripts/verify_release.py --source-root . --cache-root /path/to/release

# End-to-end smoke (stage → install → 14 sub-commands)
python scripts/smoke_cli.py --release-root /path/to/release

# Pytest e2e gate
pytest tests/e2e/test_installed_cli.py
```

## Docs

- `docs/architecture.md` — top-level architecture.
- `docs/cli-protocol.md` — the P1 JSON envelope contract shared by every CLI.
- `docs/USAGE.md` — per-Skill invocation patterns.
- `docs/camera-*-flow.md` — workflow graphs and node maps for each camera Skill.
- `docs/TROUBLESHOOTING.md` — common failures and minimal repro steps.
- `docs/superpowers/specs/2026-08-15-skill-owned-cli-no-mcp-design.md` —
  the v2.0 design and implementation plan.

## License

See `LICENSE` (inherits from upstream components).
