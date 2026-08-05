# Prompt contracts

Prompt Forge separates evidence, visual-language choices, and the authored draft.

## CreativeEvidence

Required evidence groups are `shared_known`, `user_known_agent_unknown`, `assistant_known_user_unknown`, `joint_unknown`, `locked_facts`, `continuity_locks`, `style_evidence`, `asset_refs`, and `uncertainty`.

Every sourced item may carry:

- `source_id`: document or asset identifier
- `source_section`: local heading, scene, shot, or asset entry
- `origin`: explicit, inferred, or advisory
- `confidence`: known or uncertain

## PromptPackage envelope

```json
{
  "dialect_id": "explicit dialect",
  "evidence": {"locked_facts": [], "continuity_locks": {}},
  "draft": {"positive": "caller-authored image prompt"}
}
```

The draft is authored in the selected image or video dialect. Validation reports `warnings`, `errors`, and quality flags. It does not add prose or facts.

## Image fields

Image packages use `positive` and, only where supported, `negative`. Video-only fields are absent.

## Video fields

Video packages use `positive_zh`, `positive_en`, `global_prompt`, contiguous `timeline_segments`, `dialogue_attribution`, and `continuity_locks`. Image-only fields are absent.

## Evidence and style boundary

Identity, plot facts, props, dialogue, and continuity locks are protected. Medium, palette, lighting, texture, camera feel, and motion quality are advisory visual-language fields. A style variant must preserve the protected values exactly.