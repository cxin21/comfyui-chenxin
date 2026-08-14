# Usage

Use `anima-prompt-v1` for Anima positive/negative prompt authoring and
`minimax-h3-prompt` for H3 video prompt authoring. Pass the returned text
directly to the matching camera skill.

Before execution, call `describe_config` and `validate_config`; then call
`run_skill` with the direct prompt envelope and camera-owned settings.
