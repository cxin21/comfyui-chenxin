# Usage

## Prompt authoring (Claude/Codex)

Supply a goal, CreativeEvidence, dialect, and optional style. The caller writes the draft fields, then calls the compiler or validator. A missing draft is a validation failure; Prompt Forge does not invent fallback prose and does not check model or workflow availability.

## PromptPackage fields

Image packages contain `positive` and `negative`. Video packages contain `positive_zh`, `positive_en`, `global_prompt`, `timeline_segments`, `dialogue_attribution`, and `continuity_locks` as applicable.

## External production

Pass the validated package to `character-video-pipeline` for ComfyUI, MCP, approval, submission, artifact verification, and RunRecord creation.

## Stage Config Surfaces

Each production stage loads a bundled fixed workflow asset and exposes only its declared Config Surface. Runtime reads semantic slots and compiles a local patch immediately before execution; it never returns the full workflow as configuration. `seed`, `sampler`, `sampler_name`, `scheduler`, `steps`, `cfg`, denoise, dimensions and other undeclared execution inputs remain internal.

The camera stages expose positive/negative prompts, Anima camera controls and extra prompt controls, the `Fast Groups Bypasser (rgthree)` and `Fast Groups Bypasser Post Processing` group controls, the atomic `Lora Loader (LoraManager)` + `TriggerWord Toggle (LoraManager)` unit, and the optional img2img reference image. Multiview exposes synchronized base images, declared view switches/prompts, and model-only LoRA slots with trigger words derived atomically into declared view prompts. Video exposes reference/timeline data, prompts, motion and output timing; its model/LoRA chain is fixed execution provenance rather than a user setting.

LoRA selection is discover-then-recommend: `runtime/lora_discovery.py` hashes the MCP `list_local_models` inventory, filters candidates against the stage base model, scores recommendations, and requires a fresh inventory hash and presence check at the enqueue boundary. Model metadata is authoritative when available; if the ComfyUI model-explorer node is unavailable, metadata recommendation fails closed and the runtime reports the environment limitation.
## Four-stage handoff

1. Base prompt to the pipeline base-image stage.
2. The generated base image to the multiview stage.
3. Shot prompt plus reference image to the image-to-image stage.
4. Bilingual video prompt plus shot image to the LTX director stage.

## Troubleshooting

Unknown dialect or tag, fact gaps, missing placeholders, invalid timelines, and dialogue-range errors are authoring failures. Workflow, model, transport, approval, and artifact errors belong to the external pipeline.

## Commands

```powershell
$env:PYTHONPATH = "skills/prompt-forge"
py -3 -m pytest -q skills/prompt-forge/internals/tests
$env:PYTHONPATH = "skills/character-video-pipeline"
py -3 -m pytest -q skills/character-video-pipeline/runtime/tests
```
