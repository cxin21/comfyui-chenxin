# Contributing

## Workflow

1. Find or open an issue on the GitHub tracker.
2. Branch off `main` and implement + commit + push.
3. Open a PR.
4. Wait for review and human approval before merge.

## Coding conventions

- All path identifiers in ASCII kebab-case.
- YAML frontmatter per Codex skill spec.
- Functions <= 50 lines; files <= 800 lines.
- First-principles reasoning should be visible in commit messages for non-trivial changes.
- All public-facing strings (skill descriptions, command descriptions) under 1024 chars.
- No backward-compatibility shims. New code is the contract; old code is deleted.

## License

By contributing, you agree your contributions are MIT-licensed.
