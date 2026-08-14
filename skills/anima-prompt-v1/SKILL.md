---
name: anima-prompt-v1
description: Create explainable, copyable prompts for Anima-Base, Anima-Aesthetic, and Anima-Turbo with typed intent, mandatory variant quality policy, provenance-aware Catalog retrieval, explicit route selection, independent positive and negative authoring, immutable drafts, read-only inspection, and post-authoring relation submissions. Use for Anima prompt creation, refinement, tag lookup, and relation-aware Catalog maintenance.
---

# Anima Prompt v1

Use this skill only for Anima. The current skill LLM is the semantic author: it
decides what the user asked for, which authorized creative additions to make,
how to express them, and whether a reusable semantic relation exists. The
Catalog supplies evidence and provenance; it never rewrites user facts or
invents visual meaning.

The normative baseline is
`../../docs/superpowers/specs/2026-08-14-anima-prompt-v1-bplus-design.md`.
Do not add a generic-model route, legacy compatibility layer, or competing
relation workflow.
Do not introduce `RelationAnalyzer(provider)`, provider injection, or the old
`anima_prompt` interface.

## Hard behavior contract

Execute these phases in order:

```text
request/profile -> PromptBrief -> quality seed -> Catalog
-> VisualRelationGraph -> ModelProfile/RouteDecision
-> independent authors -> PromptPlan -> immutable PromptDraft
-> read-only InspectionReport -> PromptOutput
-> post-authoring relation decision/submission -> serialization
```

Do not skip, silently merge, or replace a phase with an ad-hoc script or
post-hoc text rewrite. At every phase use one status: `PASS`, `ADVISORY`, or
`UNVERIFIED`. Never claim verification or workflow completion without evidence.
If a canonical entry point is unavailable, record a degradation advisory and do
not claim that the canonical workflow ran.

Keep these layers separate:

- user facts and exclusions;
- official model facts and defaults;
- inferred additions and unknowns;
- Catalog hits and provenance;
- diagnostics and relation proposals.

`PromptPlan` is staging. `PromptDraft` is the frozen fidelity boundary. Positive
and negative authors are independent. Inspection is read-only and advisory. The
base Catalog is read-only; only the independent relation overlay is writable.
Relation validation checks structured proposals and never infers semantics.

## 1. Establish variant and quality seed

Identify one variant before authoring scene content:

```text
Anima-Base | Anima-Aesthetic | Anima-Turbo
```

If the user only says `Anima`, select Anima-Base and put this exact entry in
`assumptions`:

```text
variant_unspecified: using Anima-Base default
```

Never fall back to `Unknown` or `Custom` quality behavior.

| Variant | Positive quality | Negative quality |
|---|---|---|
| Base | `masterpiece`, `best quality`, `score_7` | `worst quality`, `low quality`, `score_1`, `score_2`, `score_3` |
| Aesthetic | `masterpiece`, `best quality` | `worst quality`, `low quality` |
| Turbo | `masterpiece`, `best quality` | `worst quality`, `low quality` |

Create this mandatory seed before scene authoring. Represent mandatory quality
terms as official typed facts with reason `required_by_anima_variant`. For an
ordinary non-explicit prompt, also include official `safe`; `safe` is a separate
safety/meta tag, not a quality term. `highres` and `absurdres` are optional meta
tags. Resolve every mandatory term through Catalog before freezing. If a term
cannot be verified, preserve the literal and add an advisory.

## 2. Build PromptBrief and fact ledger

Use typed structures, never a free-form notes string as the source of truth:

```text
facts[], exclusions[], locked_segments[], subjects[], relations[],
scene, style, lighting, camera, inferred[], unknowns[], notes,
source_priority
```

Every fact retains:

```text
fact_id, value, kind, source, locked, confidence, user_text,
subject_id, representation_hint, notes
```

Allowed values:

```text
kind: explicit | inferred | unknown
source: user | local_model | official | community | default
representation_hint: auto | tag | prose
```

Maintain this ledger before authoring:

```text
fact_id | original user_text | rendered value | kind | source | reason
```

Preserve the user's original wording in `user_text`, even when a canonical tag
is selected. Treat only directly stated requirements as user facts. Mark every
creative addition as `inferred` with a reason. Preserve unresolved material as
`unknown` or prose. Preserve trigger, wildcard, weight, and locked text
byte-faithfully. Never infer an actor, target, interaction, occlusion, position,
or causal relation merely because it seems likely; missing relations become
advisories.

Use source priority:

```text
user > local_model > official > community > default
```

## 3. Resolve Catalog facts

For every atomic fact that may be a tag, call `Catalog.search()` in this order:

```text
exact canonical -> exact alias -> prefix -> category/facet constrained
-> accepted related -> fuzzy candidate
```

`related` uses only accepted evidence-backed relations. `fuzzy` is a candidate,
never a confirmed fact or silent replacement. Retain the complete `TagHit`:

```text
record_id, canonical_name, prompt_form, category, score,
matched_name, match_type, aliases, source, source_version,
facets, provenance
```

Mandatory quality terms require exact canonical or exact alias hits from the
official Anima source. A fuzzy quality hit cannot satisfy the policy. Aliases
are name mappings, not semantic relations. Catalog results provide provenance
and representation guidance; they never rewrite user wording.

## 4. Build graph and choose route

Build `VisualRelationGraph` only from typed Brief facts and explicit
`RelationClaim` values. Never serialize the graph into prompt text. Preserve:

```text
subject --has_attribute--> attribute
subject --performs--> action
subject --located_at--> region
subject --interacts_with/occludes/faces--> subject
scene --contains--> subject
scene --uses_style/lighting/camera--> node
```

Actions retain performers and targets. For multiple subjects, missing spatial,
interaction, occlusion, or explicit non-interaction relations produce advisories,
not guesses.

Choose exactly one route with `choose_route()`:

- `tag-led`: discrete Catalog-backed attributes dominate;
- `hybrid`: default; tags express identity, appearance, clothing, expression,
  and quality while prose expresses action, relation, space, and narrative;
- `natural-language-led`: complex space, causality, occlusion, or narrative
  dominates.

The route changes representation only. It never changes facts, quality policy,
triggers, wildcards, weights, or locked content.

## 5. Author independent channels

Use `build_positive_segments()` and `build_negative_segments()` independently.
Never build one channel by negating or post-processing the other.

Positive organization:

```text
quality/meta/safety -> locked content -> subject/appearance
-> clothing/expression -> action/relations -> scene/style -> lighting/camera
```

The mandatory positive quality/meta/safety terms begin the positive channel.
Tags express discrete attributes; prose expresses action, space, relations,
occlusion, causality, and narrative.

Negative organization:

```text
required variant quality -> user exclusions -> structural defects
-> small number of profile-backed defects
```

The mandatory negative quality terms are the only fixed model baseline. Do not
inject a long generic negative list or negate a requested subject, attribute,
color, style, composition, lighting, trigger, wildcard, weight, or unknown.

## 6. Freeze and inspect

Prefer `run_authoring_workflow()`. It must perform authoring, graph/routing
integration, draft freezing, inspection, and initial output before relation
submission. Do not use an ad-hoc script or manual priority patch to simulate it.

Build `PromptPlan`, then freeze immutable `PromptDraft`. Render both channels
from the draft's own segments. Each segment retains channel, text, origin,
representation, lock state, fact/subject IDs, Catalog hit fields, fact
kind/source, relation IDs, and quality-policy provenance.

After freezing, call read-only `inspect_draft()`, then perform an independent
semantic self-check. A tool returning no issue is not proof that every invariant
was checked. Verify:

- selected variant's positive and negative quality terms are complete;
- Base retains `score_7`;
- Aesthetic/Turbo have no unrequested `score_*`;
- `safe` is not counted as quality;
- quality terms have official provenance and occur in the correct channel;
- user facts/exclusions are preserved;
- inferred, unknown, and fuzzy material is labeled;
- no duplicate or positive/negative conflict was silently introduced.

Inspection never mutates, rewrites, invents relations, blocks output, or turns
token estimates into quality gates. Every issue is an advisory.

## 7. Produce PromptOutput

Always construct exactly:

```json
{
  "positive": "...",
  "negative": "...",
  "notes": [],
  "assumptions": [],
  "advisories": []
}
```

Prompt fields contain only copyable text. Put complete Catalog/official and
accepted-relation provenance in `notes`; variant defaults, inferred additions,
unknowns, fuzzy candidates, and unaccepted proposals in `assumptions`; and
inspection, missing-provenance, conflict, degradation, and relation failures in
`advisories`. Never put IDs, diagnostics, provenance, or relation state into
prompt fields.

Human output is exactly:

```text
POSITIVE:
...

NEGATIVE:
...
```

## 8. Submit relations after authoring

Only after PromptOutput is complete, decide whether a stable reusable semantic
relation exists. Do not create relations merely because tags co-occur. The
current skill LLM must never create `cooccurrence`.

Always form a submission, including an empty one:

```json
{"catalog_record_ids": ["exact-hit-id-a", "exact-hit-id-b"], "relations": []}
```

Use only exact current Catalog record IDs and only `parent`, `child`, or
`related`. Proposals require non-empty confidence, rationale, and evidence. Pass
the payload to `submit_relation_payload()` or `scripts/submit_relations.py`;
never write SQLite directly.

Valid proposals enter only the independent overlay as `candidate`; they are not
used by default `auto`/`related` search and are never auto-promoted. Run
`attach_relation_submission()` after initial output; it must not change either
prompt channel. If validation fails, keep the prompt and report the issue.

## Final delivery gate

Before returning, verify:

```text
[ ] variant/profile selected and default assumption recorded if needed
[ ] quality/meta/safety seed created before scene authoring
[ ] mandatory terms have exact/alias official provenance or an advisory
[ ] original user facts and exclusions preserved
[ ] inferred, unknown, and fuzzy material separated
[ ] graph built from typed facts; no guessed relations
[ ] one route selected without changing facts
[ ] positive and negative authored independently
[ ] PromptDraft frozen before inspection
[ ] inspection plus semantic self-check completed
[ ] machine output has exactly five fields
[ ] human output has only POSITIVE and NEGATIVE blocks
[ ] relation submission performed after prompt authoring
[ ] relation IDs are current exact Catalog hits only
[ ] no candidate was auto-promoted
```

If any box is not satisfied, return the prompt only with the precise issue in
`advisories`; never silently mark the workflow complete.

## Canonical entry points and references

Use these entry points when behavior is unclear:

```text
anima_prompt_v1.authoring.intent.IntentParser
anima_prompt_v1.authoring.relation_graph.build_relation_graph
anima_prompt_v1.authoring.routing.choose_route
anima_prompt_v1.authoring.build_prompt_plan
anima_prompt_v1.authoring.workflow.run_authoring_workflow
anima_prompt_v1.inspection.inspect_draft
anima_prompt_v1.output.output_from_draft
anima_prompt_v1.catalog.Catalog.search
anima_prompt_v1.authoring.relation_submission.submit_relation_payload
```

Load only the reference needed for the current phase:

- `references/intent-and-relation-graph.md`
- `references/catalog-architecture.md`
- `references/authoring-and-routing.md`
- `references/inspection-and-output.md`
- `references/evaluation.md`

Use `BPLUS_IMPLEMENTATION_PROGRESS.md` only as an implementation status ledger,
never as runtime instructions.
