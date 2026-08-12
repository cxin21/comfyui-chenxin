# MCP PromptArtifact bridge

The MCP bridge has two responsibilities: expose the three explicit Prompt Forge author calls to Python consumers, and validate complete artifacts before camera execution. It does not convert raw prompt prose into a request and does not infer a task.

## Authoring calls

- `author_anima(request)`
- `author_h3_t2va(request)`
- `author_h3_ref2va(request)`

Each accepts its exact frozen request type and returns canonical artifact JSON.

## Camera boundary

`validate_config` and `run_skill` receive:

```json
{
  "envelope": {"prompt_artifact": {"...": "complete artifact"}},
  "config": {"...": "camera-owned runtime settings"}
}
```

The envelope contains exactly `prompt_artifact`. Validation fails for unknown or missing artifact fields, non-production status, task/model mismatch, false token verification, nonempty sacrificed facts, conflicts, wrong model-native prompt keys, malformed knowledge hash, changed content hash, mismatched reference count/order/owner/dimensions, or changed H3 duration.

Camera graph patchers re-run the same validator before extracting artifact text. There is no second prompt source and no direct-patcher bypass.

The shared execution engine records the artifact SHA-256 and audit, uploads declared assets, validates the exact graph and local runtime, enqueues once, waits for terminal history, downloads outputs, and records output SHA-256. Prompt Forge remains offline and ignorant of graph nodes and execution settings.
