# MCP bridge

The MCP bridge exposes ComfyUI execution and model-native prompt authoring:

1. `list_skills`
2. `describe_config`
3. `validate_config`
4. `run_skill`
5. `describe_prompt`
6. `author_prompt`

`anima-prompt-v1` and `minimax-h3-prompt` register through the
`comfyui_chenxin_mcp.prompt_skills` entry-point group. `author_prompt` returns
the model-native `prompt` object, which can be passed directly into the
matching camera skill's envelope. Prompt authoring does not create a BuildLog
or server-side reference ID; diagnostics remain alongside the copyable prompt.
