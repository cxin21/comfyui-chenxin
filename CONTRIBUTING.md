# Contributing

## Workflow

1. Find or open an issue on the GitHub tracker.
2. Branch off `main` as `phase/PX.Y-task-short-name`.
3. Implement + commit + push.
4. Open a PR using `.github/PULL_REQUEST_TEMPLATE.md` (auto-populated).
5. Wait for 5-dim adversarial review (≥4/5 PASS) + human approval.
6. Auto-merge via `phase-gate.yml` opens the next phase branch.

## Review criteria

PR is auto-merged only when:

- `blockers == []` from 5-dim review
- ≥ 4/5 reviewers PASS
- All CI checks pass (`pr-review-bot.yml`)
- `CODEOWNERS` approval recorded (for milestones)

## Coding conventions

- All path identifiers in ASCII kebab-case.
- YAML frontmatter per Claude Code skill/agent spec.
- Functions ≤ 50 lines; files ≤ 800 lines.
- "First principles" reasoning should be visible in commit messages for non-trivial changes.
- All public-facing strings (skill descriptions, command descriptions) under 1024 chars.

## License

By contributing, you agree your contributions are MIT-licensed.
