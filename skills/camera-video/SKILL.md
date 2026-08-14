---
name: camera-video
description: Execute fixed MiniMax H3 text-to-video and reference-to-video ComfyUI workflows.
---

# Camera Video

This skill executes video workflows and does not author or audit prompts.
Supply the model-native H3 prompt directly:

```json
{"prompt": {"text": "..."}}
```

The envelope contains only `prompt.text`. Use `duration` and the required local
reference-image paths in `config`; `describe_config` lists stage-specific
requirements. Call `describe_config`, then `validate_config`, then `run_skill`.
