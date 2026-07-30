# mcp/ — Layer-2 augmenting tools for `comfyui-mcp`

> **Status: P0.2** — four CLI extensions that augment the upstream
> [comfyui-mcp](https://github.com/artokun/comfyui-mcp) MCP driver (npm, ~108
> tools) without forking it. Each tool is a standalone, stdlib-only Python
> 3.11 script invoked by Claude Code agents as a subprocess.

## Why this exists

`comfyui-mcp` is an upstream npm package. We do not fork it. When we need a
capability that is not in the upstream set (auto-launch ComfyUI, hardware-aware
model recommendation, templates lookup, save a graph to the GUI workflow
folder), we add a **thin CLI layer** here. Each tool:

- returns **JSON on stdout** (machine-readable contract);
- writes human-readable status to **stderr** (so stdout stays parseable);
- exits `0` success / `2` usage / `3` missing dependency / `4` timeout;
- depends only on the Python 3.11 standard library (`urllib.request`, `json`,
  `argparse`, `subprocess`, `socket`, `hashlib`, `pathlib`).

This keeps the agent's mental model uniform: one tool == one process ==
JSON in / JSON out. No fork, no npm patch, no custom MCP protocol.

## Layout

```
mcp/
└── extensions/
    ├── _shared.py        # helpers: wait_for_port, wait_for_http, load_hardware,
    │                     # load_templates_index, compute_sha256, resolve_comfyui_path,
    │                     # exit codes, emit_json/emit_human
    ├── auto_launch.py    # start ComfyUI on demand, wait for /system_stats 200
    ├── vram_decide.py    # read hardware/<vram>.json, recommend quant + sampler
    ├── template_get.py   # lookup templates_index.json (graceful if absent)
    ├── gui_save.py       # save graph JSON to <ComfyUI>/user/default/workflows/
    ├── __init__.py       # package marker + module docstring
    └── test_smoke.sh     # --help + bogus-args + friendly probe assertions
```

## Tools

### 1. `auto_launch.py` — bring up ComfyUI on demand

Probe `http://127.0.0.1:8188/system_stats`; on connection refused, spawn
`python -m comfyui.cmd.main --listen 127.0.0.1 --port <port> --gpu-only`
as a detached subprocess, then poll `/system_stats` until 200 (default
60s timeout). Idempotent: if ComfyUI is already up, returns immediately
without launching.

```bash
python mcp/extensions/auto_launch.py --port 8188 --timeout 60
python mcp/extensions/auto_launch.py --no-launch        # probe only
```

**Output JSON:**
```json
{
  "started": true,
  "port": 8188,
  "uptime_s": 12,
  "system_stats": { "...ComfyUI /system_stats payload...": "..." },
  "elapsed_s": 12.34
}
```

**Exit codes:** `0` ready (or already up); `4` port bind or HTTP timeout.
`--no-launch` returns `0` either way but reports `"started": false`.

### 2. `vram_decide.py` — hardware-aware model recommendation

Reads `skills/chenxin-core/hardware/<vram_gb>.json` (built by the P0.1
worker) and emits a JSON recommendation: quant, swap-block count, sampler
defaults, and a `blocked` flag. Tolerates a missing hardware file by emitting
an empty recommendation; tolerates a model not listed by emitting
`"blocked": true` with a "consult recipes/MODELS.md" reason.

```bash
python mcp/extensions/vram_decide.py --vram 8 --model anima
python mcp/extensions/vram_decide.py --vram 16 --model flux --seed 42
```

**Output JSON:**
```json
{
  "model": "anima",
  "vram_gb": 8,
  "quant": "fp8_e4m3fn",
  "swap_blocks": 40,
  "sampler_defaults": {"sampler": "euler", "scheduler": "normal", "steps": 25, "cfg": 5.5},
  "blocked": false,
  "reason": "8 GB VRAM fits anima-fp8 with 40 swap blocks; euler/25/5.5 are conservative defaults",
  "source": "hardware/8.json#anima"
}
```

### 3. `template_get.py` — workflow template lookup

Reads `skills/chenxin-core/templates_index.json` (also built by P0.1; if it
does not exist when this CLI runs, the tool degrades gracefully to
`matches: []` and `index_present: false`). Filters by `--use-case`,
`--modality`, and optional `--category`.

```bash
python mcp/extensions/template_get.py --use-case txt2img --modality image
python mcp/extensions/template_get.py --use-case img2vid --modality video --category wan --limit 20
```

**Output JSON:**
```json
{
  "use_case": "txt2img",
  "modality": "image",
  "category": null,
  "matches": [
    {"id": "anima-txt2img-v7", "name": "AnimaStandardV7", "category": "anima", "modality": "image", "use_case": "txt2img"}
  ],
  "truncated": false,
  "total_indexed": 578,
  "index_present": true
}
```

### 4. `gui_save.py` — save a graph to the GUI workflow folder

Saves a workflow JSON graph (file path or stdin) to
`<ComfyUI>/user/default/workflows/<timestamp>_<sanitized_name>.json`. Auto-detects
the ComfyUI root from `$COMFYUI_PATH` (env) or `~/ComfyUI` (default). Validates
the input is UTF-8 JSON, computes a SHA-256 fingerprint, and — bonus — drops a
`_manifest.json` sidecar when an installed skill context is detected under
`~/.claude/skills/`.

```bash
python mcp/extensions/gui_save.py --graph /tmp/my.json --name my_workflow
python mcp/extensions/gui_save.py --graph - --name my_workflow   # read JSON from stdin
python mcp/extensions/gui_save.py --graph my.json --name foo --no-sidecar
```

**Output JSON:**
```json
{
  "saved_to": "C:\\Users\\you\\ComfyUI\\user\\default\\workflows\\20260730-153045_my_workflow.json",
  "byte_size": 48231,
  "sha256": "9b3f...e0c",
  "name": "my_workflow",
  "timestamp": "20260730-153045",
  "workflows_dir": "C:\\Users\\you\\ComfyUI\\user\\default\\workflows",
  "sidecar": "C:\\Users\\you\\ComfyUI\\user\\default\\workflows\\20260730-153045_my_workflow._manifest.json",
  "manifest": {
    "schema_version": "1.0",
    "saved_by": "mcp.extensions.gui_save",
    "context": "manga-stage-2-panels",
    "workflow_name": "my_workflow",
    "timestamp": "20260730-153045",
    "byte_size": 48231,
    "sha256": "9b3f...e0c",
    "generator": "comfyui-chenxin/mcp/extensions/gui_save.py"
  }
}
```

## How agents invoke them

These tools are designed to be called from any LLM agent that has Bash (or
subprocess) access. Typical usage in a Claude Code skill or hook:

```python
import json, subprocess
r = subprocess.run(
    ["python", "mcp/extensions/vram_decide.py", "--vram", "8", "--model", "anima"],
    capture_output=True, text=True, cwd=repo_root,
)
recommendation = json.loads(r.stdout)
```

Or from Bash within a tool call:

```bash
result=$(python mcp/extensions/auto_launch.py --timeout 60)
echo "$result" | python -c "import sys,json; print(json.load(sys.stdin)['started'])"
```

## Tests

A single shell script asserts the four tools' CLI surfaces are sane:

```bash
bash mcp/extensions/test_smoke.sh
```

It runs:

1. `--help` on each tool → exit `0`;
2. bogus-arg variants on each tool → exit `2` (usage error contract);
3. friendly probes that exercise real code paths but require no live ComfyUI:
   - `auto_launch --no-launch` → exit `0`, valid JSON on stdout;
   - `vram_decide --vram 8 --model anima` → exit `0`, valid JSON on stdout;
   - `vram_decide --vram 8 --model __nonexistent` → exit `0`, `blocked: true`;
   - `template_get --use-case txt2img --modality image` → exit `0`, valid JSON;
   - `gui_save` is **skipped** unless `$COMFYUI_PATH` or `~/ComfyUI` exists
     (writing into the real workflow folder should be a deliberate user action).

The tests do **not** require a live ComfyUI server, the P0.1 hardware profile
files, or the P0.1 templates index. They are runnable in isolation during
adversarial review.

## Exit code contract

| Code | Meaning |
|------|---------|
| `0`  | Success |
| `2`  | Usage error (bad arguments, missing input file, out-of-range value) |
| `3`  | Dependency missing (e.g. Python < 3.11) |
| `4`  | Network timeout (port bind or HTTP readiness) |

## Boundary with the upstream `comfyui-mcp` driver

This layer **augments** L2; it does **not** replace or fork it. `comfyui-mcp`
remains the registered MCP server providing the ~108 core tools (`generate_image`,
`enqueue_workflow`, `list_models`, …). P0.2 adds four orthogonal capabilities
that are awkward or impossible to express in the upstream JSON-RPC surface
(particularly anything that **starts a subprocess**, like `auto_launch`, or
that **writes into ComfyUI's user-default directory**, like `gui_save`).