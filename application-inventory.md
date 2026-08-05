# Plugin inventory and boundaries

## Active skills

| Path | Responsibility | Side effects |
|---|---|---|
| `skills/prompt-forge/SKILL.md` | Claude/Codex-authored image and video prompts; deterministic audit | None |
| `skills/character-video-pipeline/SKILL.md` | Four-stage production orchestration and artifact verification | Approval-gated local ComfyUI/MCP |

## Prompt Forge retained surface

- `dialects/` and `styles/`: prompt-language and visual-language knowledge only.
- `internals/intent_normalize.py`: CreativeEvidence normalization and provenance.
- `internals/dialect_lookup.py`, `style_lookup.py`: exact lookup and advisory style rendering.
- `internals/prompt_package.py`, `prompt_compile.py`: caller-draft validation and quality lint.
- `internals/tag_lookup.py`: exact canonical and approved-alias tag validation.
- `dictionary/tag-index.json`, `dictionary/zh-en.json`: checked-in language indexes.
- `references/` and `aesthetics/`: auditable prompt vocabulary and evidence policy.

Prompt Forge does not inspect or execute models, nodes, workflows, MCP, hardware, hashes, or local services.

## Production consumer

`skills/character-video-pipeline/` is the only owner of workflow profiles, ComfyUI transport, MCP calls, approvals, submissions, artifacts, history, and RunRecords. It consumes PromptPackage; it does not ask Prompt Forge to recompile prompts.
