# Prompt contracts

## PromptIntent 6.1

PromptIntent is semantic intermediate representation. It contains facts and
constraints, not a finished prompt.

```json
{
  "schema_version": "6.1",
  "original_query": "...",
  "target": "image",
  "mode": "compile",
  "generation_mode": "text-to-image",
  "model_id": "anima",
  "dialect": "danbooru",
  "negative_constraints": ["watermark"],
  "output_constraints": {"aspect_ratio": "2:3"},
  "references": [],
  "locked_facts": ["blonde hair"],
  "dimensions": {
    "subject": [{
      "value": "blonde-haired elf",
      "origin": "explicit",
      "locked": true,
      "source_text": "金发精灵",
      "tag_candidates": ["blonde_hair", "elf"]
    }],
    "action": [], "scene": [], "lighting": [], "composition": [],
    "camera": [], "motion": [], "timeline": [], "audio": [],
    "color": [], "style": [], "mood": [], "medium": [], "quality": []
  }
}
```

Rules:

- `mode=execute` is an assertion that the user explicitly requested generation
  in the current request. It is not inferred from model names or from asking for
  a prompt.
- `references` items require `kind` (`image`, `video`, or `audio`) and `source`.
  Optional `purpose` should state identity, style, composition, first frame,
  last frame, motion, edit source, or audio timing.
- `output_constraints` stores technical output constraints; do not turn them
  into invented scene details.
- Every explicit dimension item is locked. `locked_facts` may repeat the English
  semantic values to make final-render auditing deterministic.
- `tag_candidates` are proposals, not canonical facts, until the compiler
  validates them.

## Compile envelope

The LLM writes the target-dialect draft; the deterministic compiler audits it.

```json
{
  "intent": {"schema_version": "6.1"},
  "draft": {
    "prompt": "target-dialect prompt",
    "negative_prompt": "optional model-supported negative"
  }
}
```

Omit `draft` only for deterministic fallback rendering. A production answer
should normally provide a model-aware draft.

## PromptBuild 1.0

Important fields:

- `prompt`, `negative_prompt`, `parameters`, `references`
- `validated_tags`, `rejected_tags`, `recipe_control_tokens`
- `locked_facts`, `provenance`, `warnings`, `errors`
- `lexicon_unresolved` as audit evidence; it becomes a hard stop only when the
  structured intent contains no explicit representation
- `ready_to_execute`
- `execution.mode`, `execution.requested`, `execution.performed`, `execution.tool`

The compiler always returns `execution.performed=false`; generation is a later
side effect. `ready_to_execute=false` is a hard stop.
