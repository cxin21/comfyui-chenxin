# comfyui-chenxin

Prompt authoring and ComfyUI execution are separate boundaries:

- `skills/anima-prompt-v1`: Anima image-prompt briefs, routes, audits, and local knowledge.
- `skills/minimax-h3-prompt`: MiniMax H3 T2VA and Ref2VA prompt authoring.
- `skills/camera-image` and `skills/camera-video`: fixed workflow execution only.

Authoring returns ordinary prompt text/records. There is no BuildLog, prompt
reference ID, or execution gate. Camera envelopes use direct model-native data:

```json
{"prompt": {"positive": "...", "negative": "..."}}
```

```json
{"prompt": {"text": "..."}}
```

The MCP server only discovers, validates, and executes ComfyUI skills.
