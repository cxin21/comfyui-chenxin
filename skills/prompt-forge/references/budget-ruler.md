# Budget ruler

How to size an Anima prompt so it fits its budget **before** you compile — not by trial and
error against `budget_conflict`. The canonical formulas and artifact fields live in
[artifact-and-budgets.md](artifact-and-budgets.md); this file is the operational guide.

## The ruler

Each tag is roughly 1–2 tokens plus a separator. A well-formed Anima positive prompt is almost
always **45–60 tags ≈ 90–130 tokens**. That fits every realistic target. The failure mode is
not "too many tags", it is **unbounded natural-language prose** and **duplicate semantics** —
both compress poorly and read amateur.

## Positive target by complexity

```
target = clamp(128 + 48*(subjects-1) + 24*relations + 32*complex_actions
               + 24*environment_clusters + 64*bridges, 128, 512)
soft_limit   = ceil(target * 1.25)
quality_limit = min(768, ceil(target * 1.60))
```

Worked examples:

| complexity | target | soft | quality | what fits |
|---|---|---|---|---|
| 1 subject, no rel/action/env | 128 | 160 | 205 | one subject + five-layer polish, easily |
| 2 subjects, 1 rel, 1 action, 3 env | 304 | 380 | 487 | a two-figure action scene with ruins and lighting (this is the size of a full wasteland battle) |
| 3 subjects, 2 rel, 2 actions, 4 env | 432 | 540 | 691 | a crowded brawl; stay under ~70 tags |

Never pad toward a target. Extra tokens must add non-redundant information.

## Negative target and the spending order

The negative stream is **tight**: `target = clamp(32 + 8*exclusion_groups, 32, 96)`,
`soft = ceil(target*1.25)`, `quality = min(128, ceil(target*1.60))` — roughly **40–64 tokens**.
Spend it in this order:

1. **The three standard baselines** (mandatory floor): official quality (`score_4..6`,
   `lowres`, `worst quality`, `low quality`), anatomy/structure errors, technical defects.
   These may link protected facts.
2. **User exclusions** — only if the user explicitly gave exclusions; each `exclusion_groups`
   increment raises the target by 8. Do not raise it as a filler.
3. **Agent-added mood/style exclusions** — only from the compressible pool (link them to agent
   facts only, see [authoring-contract.md](authoring-contract.md)). Expect them to be the first
   thing dropped under pressure; if you are over budget, cut these first, never protected facts.

A negative near its limit is normal. A negative **over** its limit is a `budget_conflict` whose
only automatic fix is dropping agent-added tokens — so keep the mandatory floor lean.

## Reading a budget conflict

`budget_conflict` means a stream could not be compressed under its quality limit without
touching protected content. The `conflict` object tells you exactly where:

- `mandatory_tokens` — segments pinned by protected facts (can't be auto-compressed).
- `agent_optional_tokens` — purely-agent segments that were already deleted; `0` means
  compression already removed everything it was allowed to.
- `excess_tokens = actual - quality_limit` — how far over you are.
- `user_choices` — your escape hatches, in order of preference:
  1. `unlink_segment_<id>_from_protected_fact` — an agent segment is pinned by a protected
     fact; unlink it (drop that protected `fact_id` from the segment's `fact_ids`) to move its
     tokens into the compressible pool. **This is the fix for a conflict that reports
     `agent_optional_tokens == 0`.**
  2. `simplify_<dimension>` — you (the human) explicitly approve simplifying a protected
     dimension. The tool never does this automatically.

## The one-pass principle

`compile_prompt_artifact` reports **every** hard-gate failure in one build, including
over-budget builds — a `budget_conflict` carries the same audit findings a
`quality_rejected` build would. Fix **all** codes in `hard_gate_codes`, then recompile once.
Do not fix one gate, recompile, and discover the next; that is a sign you skipped the preflight
in [dictionary-preflight.md](dictionary-preflight.md).
