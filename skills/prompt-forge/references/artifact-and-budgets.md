# Exact budgets and PromptArtifact contract

> Operational sizing guide — worked examples, the negative spending order, and reading a
> budget conflict — is [budget-ruler.md](budget-ruler.md). This file holds the canonical
> formulas and the artifact contract.

## Dynamic targets

Use exact offline tokenizers pinned by repository revision and SHA-256.

```text
Anima positive = clamp(
  128 + 48*max(0, subjects-1) + 24*relations + 32*complex_actions
  + 24*environment_clusters + 64*natural_language_bridges,
  128, 512
)
Anima negative = clamp(32 + 8*exclusion_groups, 32, 96)

H3 T2VA = clamp(
  140 + 20*duration_seconds + 70*max(0, shots-1) + dialogue_tokens,
  180, 900
)

H3 Ref2VA = clamp(
  420 + 90*reference_count + 24*duration_seconds
  + 80*max(0, shots-1) + dialogue_tokens,
  650, 1600
)
```

For every target, `soft_limit = ceil(target * 1.25)`. Use `quality_limit = min(path_cap, ceil(target * 1.60))`: Anima positive 768, Anima negative 128, H3 T2VA 1,200, and H3 Ref2VA 2,400. Physical limits are 32,768 for Anima and 262,144 for H3.

Targets guide information allocation; they are not padding goals. Identity, count, reference identity, and user-locked facts never lend budget. Borrow optional budget in the fixed order encoded by the task policy.

## Compression and conflicts

Apply exact dedupe, equal-fact semantic dedupe, structure extraction, lexical compression of agent-only wording, then removal of lowest-utility agent embellishment. Utility density is:

```text
priority * adherence_risk * source_confidence * non_redundancy / exact_token_cost
```

Never truncate tokens or remove protected facts. Return `budget_conflict` with protected causes and explicit user choices when lossless compression cannot satisfy the quality limit.

## Artifact

Every result is canonical JSON with version, status, exact task/model, model-native prompt or null, facts, rendering trace, token report, audit, compression operations, conflict or null, empty `sacrificed_facts`, exact-token verification, knowledge hash, and canonical artifact hash.

`production_ready` requires a non-null prompt and every hard gate passing. `quality_rejected` and `budget_conflict` expose no executable prompt. Camera consumers take the model-native `prompt` dict (and optional `prompt_ref`) via `envelope.prompt`; with a ref id they resolve the BuildLog and revalidate status, task, model, token verification, reference context, and H3 duration before writing workflow nodes.
