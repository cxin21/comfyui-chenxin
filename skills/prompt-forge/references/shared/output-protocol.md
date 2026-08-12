# Output protocol

Hard rules for the rendered prompt string. Violations break parsing or signal sloppy authoring.

1. **Single line, no newlines.** Comma-separated tags on one line.
2. **Separator: `", "`** (comma + space). No other separator.
3. **Lowercase only.** Ordinary tags use spaces, no underscores. `score_*` keeps underscore. `@artist` keeps `@`.
4. **No weight syntax.** `(tag:1.2)` is forbidden — field order is implicit weight.
5. **No markdown.** No code fences, no preamble, no explanation in the prompt string itself.
6. **Bridge at end.** If a natural-language bridge is used, it goes after all tags, separated by `, `.
