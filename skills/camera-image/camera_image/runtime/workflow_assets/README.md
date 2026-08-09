# camera-image workflow assets

## Runtime authority

`camera-anima.json` is the only runtime workflow source. It is a complete
ComfyUI UI graph containing the base path and all optional feature groups.
Runtime loads this file, applies the request configuration and group modes in
memory, then calls MCP `strip_workflow` once to produce the API graph.

The runtime does not:

- discover a workflow from ComfyUI;
- save or reload a temporary workflow;
- load an API snapshot as the execution source;
- repair or rewire the graph after strip;
- fall back to an older asset.

## Asset roles

| File | Role |
|---|---|
| `camera-anima.json` | Fixed UI source of truth |
| `camera-anima.api.json` | Generated T2I API inspection/release artifact |
| `camera-anima-shot-image.api.json` | Generated I2I API inspection/release artifact |
| `manifest.json` | Asset fingerprints and generated graph metadata |

The API JSON files are not alternate runtime sources. They exist to make the
release graph inspectable and to detect source/converter drift.

## Group contract

Group membership is maintained outside the UI JSON:

- `skills/camera-image/workflow/t2i-camera/groups.json`
- `skills/camera-image/workflow/i2i-camera/groups.json`

Every member ID in those files must exist in `camera-anima.json`. The compiler
rejects unknown group titles and invalid member IDs before strip.

An inactive group is expected to contain bypassed source nodes. Do not remove
those nodes from the fixed source merely because a particular stage leaves the
group disabled.

## Release checks

For every release asset set:

1. Verify the fixed UI JSON is present and its fingerprint matches the manifest.
2. Verify both stage group maps reference existing source node IDs.
3. Generate API inspection artifacts from the selected source UI through the
   current MCP strip contract.
4. Validate each generated API graph for resolved references and valid image
   outputs.
5. Run ComfyUI validation and the live acceptance matrix in
   [`docs/camera-image-flow.md`](../../../../../docs/camera-image-flow.md).

Any mismatch is a release failure. Do not compensate in runtime code.
