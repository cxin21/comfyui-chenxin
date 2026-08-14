# Authoring and Routing

This reference defines Anima variant policy, expression routes, and the private
authoring plan. It does not change the Brief's facts.

## Anima ModelProfile

`ModelProfile` retains:

```text
variant, tag_preference, natural_language_preference,
negative_tolerance, quality_tag_policy, trigger_words,
token_limit, source, evidence_level
```

Supported variants are `base`, `aesthetic`, and `turbo`. If the request says only
Anima, use `base` and record an assumption. This skill does not fall back to a
generic Unknown/Custom quality policy.

The quality policy is mandatory:

| Variant | Positive must contain | Negative must contain |
|---|---|---|
| Base | `masterpiece, best quality, score_7` | `worst quality, low quality, score_1, score_2, score_3` |
| Aesthetic | `masterpiece, best quality` | `worst quality, low quality` |
| Turbo | `masterpiece, best quality` | `worst quality, low quality` |

For ordinary non-explicit prompts add `safe`. Do not treat `safe` as a quality
term. `highres` and `absurdres` are optional meta terms. For Aesthetic, do not
add `score_*` unless the user explicitly requests it or local model evidence
requires it. For Base, never silently omit `score_7`.

The official general Anima prefix is `masterpiece, best quality, score_7, safe`.
The official Aesthetic guidance permits `masterpiece, best quality` but warns
against score tags. The skill's mandatory policy follows those version rules.

All mandatory terms are Catalog-backed official facts and keep provenance. A
user-provided quality term is preserved without replacement or duplication.

## RouteDecision

`choose_route(brief, graph, requested, profile)` returns:

- `tag-led`: discrete Catalog-backed facts dominate;
- `hybrid`: default; tags express quality, identity, clothing, appearance, and
  expression while prose expresses actions, relations, space, occlusion,
  causality, and narrative;
- `natural-language-led`: complex narrative or spatial relations dominate prose.

An explicit route wins. Routes change representation, never facts or mandatory
quality terms. They cannot rewrite locked syntax or stack synonyms.

## Independent authors

`build_positive_segments()` and `build_negative_segments()` are separate.
Positive starts with the required quality/meta/safety terms, then preserves
locked content, subject, general attributes, clothing, expression, action,
relations, scene, style, lighting, and camera. This is an ordering preference,
not a generic fixed-slot template.

Negative starts with the required variant quality terms, then user exclusions,
relevant structural defects, and a small number of profile-backed defects. Do not
inject a long global negative list or negate a user target.

## PromptPlan and PromptDraft

`build_prompt_plan()` combines independent typed segments and carries route,
profile, quality provenance, and other provenance. It is internal staging.

`build_draft()` freezes immutable segments and renders positive/negative text from
those segments. Each segment retains channel, origin, representation, fact/source
metadata, subject/fact IDs, Catalog hit fields, relation IDs, and quality policy
provenance. Inspection starts only after the freeze.

The workflow does not call an LLM or write relations. The skill LLM decides
relations only after authoring is complete.
