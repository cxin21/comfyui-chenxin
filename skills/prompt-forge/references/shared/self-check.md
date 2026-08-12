# Self-check (pre-compile gate)

Run all 6 checks before calling `compile_prompt_artifact`. Failures here cost a compile cycle; catching them earlier saves time.

## The 6 checks

### 1. 人数一致 (count consistency)
`count` tag matches actual character count.
Pass: `2boys` + 2 subjects, no `1boy,2boys` contradiction.

### 2. 互斥冲突 (conflict)
No hard conflict per [quality/conflict-table.md](../quality/conflict-table.md).
Pass: no `pov` + `full body`, no `completely nude` + specific clothing, etc.

### 3. 重复标签 (duplicate tags)
Same tag does not appear twice in the same stream.
Pass: `running` not doubled; emphasis comes from position, not repetition.

### 4. 场景物理合理 (scene × action compatibility)
Scene + action are physically compatible.
Pass: `underwater` not with `cigarette`; `snow` not with `beach`.

### 5. 风格一致 (style consistency)
No cross-worldview mismatch per [quality/style-consistency.md](../quality/style-consistency.md).
Pass: no `hanfu` + `cyberpunk city`.

### 6. 标签总数 (tag count)
Within bounds per [quality/tag-count-ruler.md](../quality/tag-count-ruler.md).
Pass: total ≤ hard cap for complexity tier.

## Automation

Checks 2, 5, 6 are automated by [scripts/preflight.py](../../scripts/preflight.py).
Checks 1, 3, 4 are manual or covered by `compile_prompt_artifact` audit.
