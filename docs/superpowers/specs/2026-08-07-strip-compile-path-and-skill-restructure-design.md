# camera-image UI-to-API compile contract

Status: current execution contract

## Decision

Compile every camera-image request from the fixed UI source
`camera-anima.json`. Apply semantic configuration and group modes before one
MCP `strip_workflow` call. Validate the returned API graph, then submit that
same graph.

## Source model

The fixed UI graph is a complete superset. It contains every optional group;
disabled groups remain in the source with bypass mode. Stage `groups.json`
files map group titles to source node IDs.

The compiler rejects:

- unknown caller group titles;
- group members absent from the source UI;
- missing stage dependencies;
- invalid final API references;
- output nodes without image links.

## Compile sequence

```text
load fixed UI
  -> load stage groups
  -> validate group membership
  -> apply RunConfig to widgets_values
  -> compute defaults + caller + mandatory groups
  -> set node modes
  -> strip_workflow(ui)
  -> validate_api_graph(api)
  -> ComfyUI validate/runtime checks
  -> enqueue {"workflow": api}
```

No temporary workflow save/load, API snapshot loading, post-strip graph
normalization, or compatibility path exists in this contract.

## Feature contracts

- LoRA is written to the ordinary `lora_syntax` input of
  `LoRA Text Loader (LoraManager)` before strip.
- I2I writes the uploaded image to the source LoadImage node, selects the VAE
  reference branch, and enforces `denoise=0.6` before strip.
- ControlNet requires the uploaded control image and a real
  `ModelPatchLoader -> AnimaLLLiteApply.model_patch` link.
- Final output remains connected to node 111 and the designated saver/preview
  outputs.

## Acceptance

Offline tests cover config, group membership, converter contracts, and API
graph structure. Live tests require actual PNG output and submitted-graph
assertions for T2I, I2I, LoRA, ControlNet, and the LoRA+ControlNet combinations.

See [`docs/camera-image-flow.md`](../../camera-image-flow.md) for the full
flow and acceptance matrix.
