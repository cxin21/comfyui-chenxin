# Live evidence fixtures

This directory contains sanitized read-only evidence for camera-image workflow
contracts. It is test evidence, not a runtime workflow source. It contains no
credentials, request headers, prompt history, or generated media.

## Runtime authority

The checked-in source used by runtime is:

```text
camera_image/runtime/workflow_assets/camera-anima.json
```

The live ComfyUI workflow library is evidence used to refresh and verify the
release asset. Runtime does not discover or substitute a live workflow.

## Read-only preflight evidence

The original evidence run queried local ComfyUI read-only endpoints and made no
generation, upload, approval, or prompt request. Retrieval hashes are evidence
only; they do not authorize execution.

| Asset | Evidence role | Runtime decision |
|---|---|---|
| `camera-anima.json` | Fixed UI source fingerprint | Runtime source |
| `camera-anima.api.json` | Generated T2I graph inspection | Never runtime source |
| `camera-anima-shot-image.api.json` | Generated I2I graph inspection | Never runtime source |

## Required release checks

1. Verify the fixed UI asset fingerprint against `workflow_assets/manifest.json`.
2. Verify T2I and I2I group maps reference source nodes that exist.
3. Strip the selected UI graph through the current MCP contract.
4. Validate references and image outputs in the resulting API graph.
5. Execute the live acceptance matrix and retain submitted graph and artifact
   hashes.

Warnings from intentionally bypassed source groups are not source defects. The
selected final API graph must still be structurally valid and executable.

## Live acceptance boundary

Live generation requires ComfyUI at `http://127.0.0.1:8188`, the required
models/custom nodes, and the project MCP tools. A read-only evidence fixture or
an offline graph test cannot be reported as a real image-generation pass.
