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
  "story_breakdown_hash": "<lowercase sha256>",
  "art_bible_hash": "<lowercase sha256>",
  "asset_refs": [{
    "asset_id": "character-lee",
    "asset_type": "character",
    "content_hash": "<lowercase sha256>"
  }],
  "explicit_evidence": ["blonde hair"],
  "reasonable_inference": ["travel-worn fabric"],
  "prohibited_expansion": ["modern LED glasses"],
  "continuity_locks": {
    "identity": ["blonde hair"],
    "style": ["restrained ink wash"],
    "scene": [],
    "prop": []
  },
  "uncertainty": ["exact garment age"],
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
- Evidence-extension fields are optional for legacy callers. When present,
  hashes are lowercase SHA-256 values, asset references are JSON objects, and
  all returned values are deep copies. Explicit evidence and continuity locks
  join `locked_facts`; reasonable inference remains unlocked; prohibited
  expansion joins negative constraints. A fact appearing in an allowed tier or
  lock and `prohibited_expansion` fails closed.
- Unknown source facts remain in `uncertainty`; normalization never promotes
  them to identity truth.

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

### Evidence-bound image extension

Image builds keep the PromptBuild 1.0 `prompt` and `negative_prompt` fields and
may add:

```json
{
  "reference_roles": [
    {"asset_id": "character-lee", "role": "identity"}
  ],
  "identity_lock": ["blonde hair"],
  "style_lock": ["restrained ink wash"],
  "scene_lock": [],
  "prop_lock": [],
  "source_contract_hashes": {
    "story_breakdown": "<lowercase sha256>",
    "art_bible": "<lowercase sha256>",
    "character-lee": "<lowercase sha256>"
  }
}
```

The extension is all-or-nothing at the quality boundary. Reference roles must
identify a source and role, lock fields are string lists, and source hashes are
valid lowercase SHA-256 values. PromptIntent continuity locks must be preserved,
and a prohibited expansion cannot appear in a build lock.

### Evidence-bound LTX video extension

Video builds keep PromptBuild 1.0 and add:

```json
{
  "prompt": "<exact selected positive_en or positive_zh>",
  "negative_prompt": "",
  "positive_zh": "...〖0-1.7 s〗...〖1.7-4.2 s〗...",
  "positive_en": "...〖0-1.7 s〗...〖1.7-4.2 s〗...",
  "global_prompt": "<one selected director prompt>",
  "timeline_segments": [
    {
      "start": 0.0,
      "end": 1.7,
      "text_zh": "...",
      "text_en": "..."
    }
  ],
  "dialogue_attribution": [
    {
      "speaker": "女剑士",
      "speaker_en": "The swordswoman",
      "text": "快走。",
      "start": 1.7,
      "end": 4.2
    }
  ],
  "continuity_requirements": ["same character", "same courtyard"],
  "split_recommendation": {"required": false, "reason": ""},
  "source_shot_plan_hash": "<lowercase sha256>"
}
```

`parse_ltx_timeline` accepts only explicit `〖start-end s〗` markers with
positive duration. The first segment starts at `0`, and each following start
equals the preceding end within floating-point tolerance, so the execution
timeline is monotonic, non-overlapping, and gap-free. Bare, hidden, malformed,
zero-duration, non-zero-start, gap, overlap, or placeholder intervals fail
closed.

Dialogue is bound by `dialogue_attribution`, not inferred from quotation marks.
Each entry's `speaker` occurs in `positive_zh`; `speaker_en` (or the shared
`speaker` when omitted) occurs in `positive_en`; `text` occurs exactly in both.
Chinese dialogue is therefore copied code-point-for-code-point into
`positive_en`. An explicit `对白:`, `台词:`, `dialogue:`, or `spoken line:`
marker also requires a matching attribution. Quoted signage, titles, and UI
labels do not become dialogue merely because they use quotation marks and may
preserve source glyphs. Other surrounding scene, action, and camera text is
English.

`input_type` is one of `reference`, `script`, `storyboard`, or
`character_sheet`; the corresponding value in PromptIntent `global_prompts` is
selected exactly once and never concatenated with competing candidates. A
scene/time change, more than three core characters, more than four complex
beats, multiple major events, or mixed complex action/dialogue requires a split.
Extreme-wide framing is rejected unless explicitly requested. Motion, camera,
continuity, dialogue ownership, and the source shot-plan hash are mandatory.
No `negative_*` companion field is allowed: the workflow-owned LTX negative
remains the only negative system.
