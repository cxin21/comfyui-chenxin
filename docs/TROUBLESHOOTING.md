# Troubleshooting

Common failure modes and their fixes, indexed by symptom.

## Symptom: `bash scripts/validate-plugin-schema.sh` errors with `plugin.json: missing commands/agents/hooks/mcp paths`

You removed or renamed one of the plugin directories. Either restore the directory or update `plugin.json` to point at the new path.

## Symptom: smoke test for obsidian-sync finds an `unknown` file even though I passed an event

That's by design: `EVENT_RAW` is sanitized through `tr -cd 'A-Za-z0-9._-'`. If your event name contains only illegal characters, the script falls back to `unknown` and writes `decision-YYYY-MM-DD-unknown.md`.

## Symptom: `python3 scripts/check_updates.py --apply` writes 0 changes despite upstream drift

Confirm `git remote -v` lists a remote. The daemon compares local `recipes/MODELS.md` to upstream `SlavaSexton/ComfyUI-Agent-Kit` via `curl`, but `git fetch` failures cause the daemon to fall back to a no-diff report.

## Symptom: `bash tests/test_obsidian_sync.sh` fails because /tmp missing

On Windows Git Bash, `/tmp` resolves to the user temp dir. If that's read-only (corporate lockdown), set `TMPDIR=$HOME/tmp` before running.

## Symptom: `bash scripts/obsidian-sync.sh` exits 0 but writes nothing

Either the vault doesn't exist (idempotent non-fatal skip) or `EVENT` was empty after sanitization (defaults to `unknown`). Check by setting `OBSIDIAN_VAULT_PATH=` to point at a writable location.

## Symptom: ComfyUI workflow fails with "VRAM exceeded"

`mcp/extensions/vram_decide.py` reads `skills/prompt-forge/hardware/<vram_gb>.json` (or `<vram_gb>gb.json` — both conventions are honored). If neither file exists for your VRAM, the script returns `sampler_defaults` from the conservative SDXL-style defaults rather than refuse. Update the `hardware/XX.json` profile (or copy `8gb.json` to your actual VRAM tier) to gate correctly.

## Symptom: recipe_yaml.py modified a recipe's body, not just added YAML frontmatter

The script is conservative — body content should be unchanged. If you see body change, open an issue with a diff. Likely cause: a recipe line began with `### Foo` inside its body (header collision).
