---
name: camera-image
description: Execute the fixed ComfyUI Anima still-image workflow for text-to-image and image-to-image runs.
---

# Camera Image

This skill executes camera controls and image-generation settings. It does not
author, audit, resolve, or rewrite prompts. Supply the model-native prompt
directly in the envelope:

```json
{"prompt": {"positive": "...", "negative": "..."}}
```

The only envelope key is `prompt`; its two fields are required strings. Camera
configuration remains in `config` and includes `camera`, `sampling`, `seed`,
`image_size`, `groups`, `reference_image`, and `controlnet_image` as described
by `describe_config`.

Call `describe_config`, then `validate_config`, then `run_skill`.
