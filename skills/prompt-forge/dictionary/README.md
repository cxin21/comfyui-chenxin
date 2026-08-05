# dictionary/ — runtime tag index

Prompt Forge retains only the checked-in 	ag-index.json runtime index.
It is read by exact canonical/approved-alias validation; no source CSV or rebuild script is part of this skill.

## Runtime contract

- 	ag-index.json is read-only prompt-language data.
- Unknown tags are rejected and never guessed into canonical tags.
- Recipe control tokens remain separate from semantic tags.

## Provenance

The compact index is the retained runtime artifact. Source datasets and generation tooling are intentionally outside this skill boundary.
