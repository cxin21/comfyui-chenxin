# Usage

Use the MCP `author_prompt` tool with `skill=anima-prompt-v1` and
`stage=author` for Anima positive/negative prompt authoring, or with
`skill=minimax-h3-prompt` and `stage=t2va`/`ref2va` for H3 video prompt
authoring. Pass the returned `prompt` object directly to the matching camera
skill.

Call `describe_prompt` first when the request schema is unclear. Before
execution, call `describe_config` and `validate_config`; then call `run_skill`
with the direct prompt envelope and camera-owned settings.
