# Budget ruler

Token budget for both streams. See also [tag-count-ruler.md](tag-count-ruler.md) for attention-distribution guard.

## Positive target

```
target = clamp(128 + 48*(subjects-1) + 24*relations + 32*complex_actions
               + 24*environment_clusters + 64*bridges, 128, 512)
soft_limit   = ceil(target * 1.25)
quality_limit = min(768, ceil(target * 1.60))
```

| complexity | target | soft | quality | example |
|---|---|---|---|---|
| 1 subject | 128 | 160 | 205 | one subject + 5-layer polish |
| 2 subjects, 1 rel, 1 action, 3 env | 304 | 380 | 487 | two-figure battle (wasteland battle) |
| 3 subjects, 2 rel, 2 actions, 4 env | 432 | 540 | 691 | crowded brawl |

## Negative target

```
target = clamp(32 + 8*exclusion_groups, 32, 96)
soft = ceil(target * 1.25)
quality = min(128, ceil(target * 1.60))
```

Spend in this order:
1. **Three standard baselines** (mandatory floor): `score_4..6`, `lowres`, `worst quality`, `low quality`, anatomy/structure errors, technical defects.
2. **User exclusions** — only if user explicitly gave them; each `exclusion_groups` increment raises target by 8.
3. **Agent-added mood/style exclusions** — from compressible pool only; first to drop under pressure.

## Reading a budget conflict

`budget_conflict` means a stream could not be compressed under quality limit without touching protected content. Resolution order:
1. Drop agent-optional segments first (never protected facts).
2. Resolve via `user_choices.unlink_segment_<id>_from_protected_fact` if mandatory pool is stuck.
3. Never weaken a protected fact automatically.
