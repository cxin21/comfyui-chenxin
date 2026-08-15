# CLI protocol contract tests

These tests freeze the machine-facing contract shared by every independently
installed Skill CLI. The implementation is intentionally vendored into each
Skill package so no central runtime package is required.

The contract covers:

- UTF-8 JSON object input from exactly one of `--request` or `--stdin`;
- a stable six-field response envelope;
- structured errors and advisories;
- exit-code mapping independent from error message contents;
- deterministic JSON output with diagnostics kept out of stdout.

