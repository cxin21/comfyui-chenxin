# MCP execution bridge

The MCP bridge is deliberately limited to executable ComfyUI skills:

1. `list_skills`
2. `describe_config`
3. `validate_config`
4. `run_skill`

Prompt authors run independently and pass their resulting model-native text to
the camera envelope. No prompt registry, BuildLog, reference ID, or server-side
authoring dispatch exists.
