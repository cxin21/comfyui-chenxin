# Audit and recovery

> **Preflight catches common errors; audit catches schema errors. Together they form the quality gate.** `scripts/preflight.py` (see [self-check.md](../shared/self-check.md)) runs before `compile_prompt_artifact`; the audit runs inside the tool.

---

(content from previous file below — unchanged)

`compile_prompt_artifact` returns a slim `{ref_id, prompt, metadata}`. When the build is not
`production_ready`, read the full build log with `get_build_audit(ref_id)` — it carries
`status`, `hard_gate_codes`, per-stream audit `findings`, and (for budget failures) `conflict`.
Fix **every** code, then recompile once.

## Statuses

| status | meaning | next step |
|---|---|---|
| `production_ready` | every gate passed; `prompt` is executable | pass `prompt` (and `prompt_ref`) to `camera-image` / `camera-video` |
| `quality_rejected` | one or more hard-gate errors; no prompt | read `hard_gate_codes`, fix all, recompile |
| `budget_conflict` | a stream over its quality limit with protected content; no prompt | read `conflict` + `hard_gate_codes` (which also lists any protocol errors), fix, recompile |

Camera skills reject every status except `production_ready`, and reject any build whose hash or
exact-token verification is invalid.

## Hard-gate codes → fix

| code | meaning | fix |
|---|---|---|
| `invalid_protocol_tag` | a reserved namespace is malformed, or a segment holds a comma list | one tag per segment; `score_N` exact `score_1..9`; `year` four digits; `@` artist resolves |
| `wrong_underscore_form` | an ordinary tag uses an underscore | use spaces (`blue hair`, not `blue_hair`) |
| `missing_protocol_prefix` | positive stream lacks a `protocol_prefix` segment (enforced quality baseline) | add one `protocol_prefix` segment carrying the baseline tags |
| `unsupported_positive_field` / `unsupported_negative_field` | unknown field name | use the enumerated fields in [authoring-contract.md](../shared/authoring-contract.md) |
| `natural_language_bridge_count` | bridge count mismatches `complexity` or exceeds 1 | set `complexity.natural_language_bridges` to the actual bridge count |
| `tag_bridge_fact_overlap` | the bridge and a tag render the same fact | bind each fact once — tags or bridge, not both |
| `unsupported_bridge_semantic` | bridge fact dimension outside the allowed set | a bridge only binds ownership/spatial/causal/result/relation |
| `duplicate_semantics` | same semantic resolved twice, or rendered by tag and bridge | dedupe; keep one rendering per semantic |
| `possible_binding_conflict` | one unbound tag matches facts owned by multiple subjects | bind the tag to one fact or split it |
| `positive_negative_contradiction` | same semantic in both streams | remove it from one stream |
| `token_quality_limit` | a stream exceeded its quality limit | see `conflict`; drop/unlink agent segments first |
| `token_quality_limit` + others on a `budget_conflict` | over budget **and** protocol errors | fix all codes in one pass — budget and protocol are independent |

> **Severity nuance:** `possible_binding_conflict` is emitted with `severity == "warning"` in
> the findings, but it **is release-blocking** — the audit includes it in `hard_gate_codes`
> and a build reporting it will not reach `production_ready`. Fix it (bind the tag to one fact
> or split it) before shipping.

`unverified` findings are **warnings, not errors** — advisory only. Treat them per
[dictionary-preflight.md](dictionary-preflight.md), not as gates.

## Reading `conflict`

See [budget-ruler.md](budget-ruler.md) for the full walkthrough. Short version:
`mandatory_tokens` can't be auto-compressed; `user_choices` lists your exits —
`unlink_segment_<id>_from_protected_fact` first, `simplify_<dimension>` only as a human
decision. Never "fix" a conflict by weakening a protected fact automatically — the tool will
not, and neither should you.

## The one-pass principle

The audit reports **all** hard-gate failures in one build, including over-budget builds.
Serial fixes — fix one code, recompile, discover the next — are a symptom of skipping the
preflight step, not a normal loop. Preflight the dictionary, budget with the ruler, then compile
once and fix everything it reports.
