# Natural language bridge

A bridge is a concise natural-language phrase appended after all tags. Use when independent tags cannot bind the semantic.

## When required

- **Multi-character attribution** — tags can't say "Subject A holds Subject B's umbrella"
- **Spatial relations** — tags can't bind "A behind B"
- **Special pose combinations** — multiple action tags stack ambiguously; bridge clarifies who-does-what
- **Storyboard / contrast** — "left panel: dressed, right panel: nude"

## Rules

- **Count ≤ 1** — one bridge per prompt.
- **Position = end of positive stream** — after all tags, separated by `, `.
- **Fact dimensions allowed**: `ownership`, `spatial_relation`, `causal_action`, `action_result`, `relation`.
- **No overlap with tag segments** — bind each fact once (tag or bridge, never both).

## Examples

| Scenario | Bridge |
|---|---|
| `1boy` + `2girls`, ambiguous action | `Subject 1 holds Subject 2's hand while Subject 3 watches` |
| Symmetric pose | `two girls mirroring each other across the table` |
| Spatial chain | `Subject A standing behind Subject B looking over their shoulder` |

## When NOT to use

- Decoration or "polish" prose → DROP; tags only
- Long descriptive paragraph → break into tags or split scene
- Anything that could be a tag → use the tag instead
