# Prompt Forge

Greenfield prompt authoring for the fixed Anima and MiniMax-H3 production workflows.

The core API is:

```python
from prompt_forge.contracts import ForgeRequest
from prompt_forge.forge import forge_prompt

artifact = forge_prompt(ForgeRequest(
    profile_id="anima.miaomiao-harem.anima-1.5",
    operation="t2i",
    positive="score_9, score_8_up, ...",
    negative="low quality, bad anatomy",
))
```

The caller authors the text. Prompt Forge selects the exact profile, validates objective constraints, lints the native grammar, and returns a structured artifact. It does not maintain a cross-model dialect registry, projection pipeline, compatibility adapter, or creative post-processor.
