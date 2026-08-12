# Method

## 5-step process

1. **Ledger** — Extract every explicit requirement into immutable facts (stable ID, owner, dimension, origin, lock state). Treat user facts as protected. See [authoring-contract.md](authoring-contract.md).
2. **Budget** — Size streams with the offline tokenizer. See [quality/budget-ruler.md](../quality/budget-ruler.md) and [quality/tag-count-ruler.md](../quality/tag-count-ruler.md).
3. **Write** — Author in model-native fields, one tag per segment, in the model's order, visible facts before aesthetic polish. See [authoring-contract.md](authoring-contract.md).
4. **Polish** — Apply mandatory aesthetic retrieval (5 layers). See [aesthetic-coverage.md](aesthetic-coverage.md).
5. **Preflight + compile** — Run pre-compile gates, compile, then audit. See [self-check.md](self-check.md) + [quality/audit-and-recovery.md](../quality/audit-and-recovery.md).

Never truncate a prompt or remove a protected fact. If protected content stays above the quality limit, resolve the conflict through `user_choices` — never weaken a protected fact automatically.

## Quality hierarchy

Prioritize in this order:

1. user-locked facts, exact dialogue, visible text, negation, count, ownership, reference identity, action results
2. model adherence and executable temporal/reference structure
3. subject and scene coherence
4. composition, camera, lighting, motion, sound, style
5. optional embellishment

Additional tokens must add non-redundant information. Never pad toward a target.

## Output boundary

Pass the production-ready `prompt` dict from `compile_prompt_artifact(task, request)` under `envelope.prompt` (optionally with `prompt_ref`) to:
- `camera-image` (anima)
- `camera-video` (h3_t2va / h3_ref2va)

Camera skills accept only `production_ready` builds with valid content hash and exact-token verification. `camera-multiview` uses a fixed-prompt Flux2-Klein workflow and takes no prompt.

## Script boundary

Scripts may:
- build and verify knowledge assets
- count exact tokens
- query the dictionary
- benchmark deterministic artifacts
- prepare generation-pair manifests
- verify a release

Scripts must NOT:
- select aesthetic concepts
- decide story beats
- invent shots
- resolve ambiguous intent
- write final prompt prose
- run ComfyUI, discover workflows, choose checkpoints, apply local checkpoint/LoRA knowledge
