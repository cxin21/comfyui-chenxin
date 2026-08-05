# comfyui-chenxin

A local ComfyUI plugin with two bounded skills: `prompt-forge` is an LLM-first authoring and audit boundary, while `character-video-pipeline` is the approval-gated production consumer.

## Active skills

| Skill | Responsibility | Side effects |
| --- | --- | --- |
| `skills/prompt-forge/SKILL.md` | CreativeEvidence, prompt dialects, visual styles, exact tag validation, and PromptPackage lint | None |
| `skills/character-video-pipeline/SKILL.md` | Four-stage workflow discovery, approval, ComfyUI/MCP submission, history, and artifacts | Approval-gated local ComfyUI/MCP |

Claude or Codex writes the final prompt fields. Prompt Forge never checks installed models, reads workflows, calls MCP, or emits execution state. The production skill consumes an approved PromptPackage and does not silently rewrite it.

## Production path

```text
CreativeEvidence + Claude/Codex
  -> base image PromptPackage -> camera-view text-to-image -> front base image
  -> Flux2-Klein multiview -> accepted character sheet
  -> shot PromptPackage + G1 reference -> camera-view img2img -> shot image
  -> bilingual video PromptPackage -> LTX Yusu Director -> verified video + RunRecord
```

The repository does not ship ComfyUI, model weights, Custom Nodes, or saved workflow entities.

## Prerequisites and install

Assume ComfyUI is already running at `http://127.0.0.1:8188/`. Install only registers MCP configuration and host examples:

```bash
bash scripts/install.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

## Verification

```bash
PYTHONPATH=skills/prompt-forge pytest -q skills/prompt-forge/internals/tests
PYTHONPATH=skills/character-video-pipeline pytest -q skills/character-video-pipeline/runtime/tests
python -m compileall -q skills/prompt-forge/internals skills/character-video-pipeline/runtime
```

See [`docs/USAGE.md`](docs/USAGE.md), [`docs/architecture.md`](docs/architecture.md), [`docs/MCP_BRIDGE.md`](docs/MCP_BRIDGE.md), [`skills/prompt-forge/SPEC.md`](skills/prompt-forge/SPEC.md), and [`skills/character-video-pipeline/SKILL.md`](skills/character-video-pipeline/SKILL.md).
