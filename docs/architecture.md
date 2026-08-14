# Architecture

## Independent prompt skills

`anima-prompt` and `minimax-h3-prompt` are ordinary authoring packages. They
own their model dialect, knowledge assets, validation, and output records.
They do not import camera runtime code and do not expose execution artifacts.

## Execution skills

`camera-image` accepts `{prompt: {positive, negative}}` and owns the Anima
workflow, camera controls, image sizing, groups, and uploads.

`camera-video` accepts `{prompt: {text}}` and owns MiniMax H3 workflows,
duration, ordered reference images, and output downloads.

## MCP boundary

The MCP server exposes four operations: list skills, describe a stage, validate
an envelope/config pair, and run a stage. Prompt authoring is not an MCP
execution operation.
