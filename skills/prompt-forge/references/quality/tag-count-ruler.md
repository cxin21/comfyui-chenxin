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
| protocol_prefix | 2 | 4 | quality/meta/safety baseline |
| count | 1 | 2 | subject count |
| character | 0 | 2 | IP only |
| series | 0 | 1 | source work / franchise |
| artist | 0 | 3 | `@artist`, weighted |
| appearance | 3 | 8 | hair+eye+body+clothing |
| general | 5 | 12 | action/expression + 5 aesthetic layers |
| environment | 2 | 6 | location/props/weather |
| scene_description | 0 | 1 | NL bridge, after a period |

`general` is naturally the largest slot — action/expression plus the five aesthetic layers (composition → lighting → palette → camera → mood). Other slots stay lean; diversity comes from cross-slot combination, not stacking.

## Relationship to token budget

Token budget (see `budget-ruler.md`) is the hard ceiling; tag count is the attention-distribution guard. Both must pass.
