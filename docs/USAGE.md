# Usage

## Prompt authoring (Claude/Codex)

Supply a goal, CreativeEvidence, dialect, and optional style. The caller writes the draft fields, then calls the compiler or validator. A missing draft is a validation failure; Prompt Forge does not invent fallback prose and does not check model or workflow availability.

## PromptPackage fields

Image packages contain `positive` and `negative`. Video packages contain `positive_zh`, `positive_en`, `global_prompt`, `timeline_segments`, `dialogue_attribution`, and `continuity_locks` as applicable.

## External production

Pass the validated package to `character-video-pipeline` for ComfyUI, MCP, approval, submission, artifact verification, and RunRecord creation.

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
