# Tag count ruler

Budget on **tag count**, separate from token budget. Tag count is the leading indicator of attention dilution; token count is a soft ceiling.

## Total count percentiles

| Complexity | p50 | p75 | p90 | hard cap |
|---|---|---|---|---|
| simple (single subject) | 18 | 25 | 32 | 40 |
| standard (two-subject) | 25 | 33 | 42 | 50 |
| complex (multi / themed) | 35 | 45 | 55 | 70 |

A prompt with > hard cap violates attention distribution — split into multiple scenes.

## Per-slot targets

| Slot | min | max | note |
|---|---|---|---|
| count/gender | 2 | 4 | fixed format |
| character/series | 0 | 2 | IP only |
| appearance | 3 | 8 | hair+eye+body+skin |
| clothing/state | 2 | 10 | largest slot by nature |
| pose/action | 2 | 8 | |
| expression | 1 | 4 | |
| camera/shot | 1 | 5 | |
| scene/environment | 2 | 6 | |

Clothing slot is naturally largest — base garment + material + 1-3 modification dimensions. Other slots stay lean; diversity comes from cross-slot combination, not stacking.

## Relationship to token budget

Token budget (see `budget-ruler.md`) is the hard ceiling; tag count is the attention-distribution guard. Both must pass.
