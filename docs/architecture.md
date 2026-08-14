# Architecture

## Prompt skills

`anima-prompt-v1` and `minimax-h3-prompt` are authoring packages. They own
their model dialect, knowledge assets, validation, and output records. Each
also registers an MCP prompt-skill entry point, so the MCP server can call the
canonical authoring API without importing camera runtime code.

## Execution skills

`camera-image` accepts `{prompt: {positive, negative}}` and owns the Anima
workflow, camera controls, image sizing, groups, and uploads.

`camera-video` accepts `{prompt: {text}}` and owns MiniMax H3 workflows,
duration, ordered reference images, and output downloads.

## MCP boundary

The MCP server exposes the four execution operations (`list_skills`,
`describe_config`, `validate_config`, `run_skill`) and two authoring operations
(`describe_prompt`, `author_prompt`). Prompt output is model-native and can be
passed directly into the matching camera skill's envelope.
