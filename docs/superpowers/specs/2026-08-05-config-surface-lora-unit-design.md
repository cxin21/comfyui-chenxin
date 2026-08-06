# Config Surface and LoRA Unit Design

## Status

Approved design, 2026-08-05. Extends the controlled character-to-video pipeline design with an explicit configuration surface for the camera workflow and an MCP-driven LoRA discovery/recommendation flow. Implementation follows the phase plan at the bottom, test-first.

## Goal

Every output-affecting configuration item of `文生图相机视角.json` must be either a declared, approval-gated variable or a value-pinned constant. This design declares the seven atomic configuration slots of the camera workflow and adds a discover-then-recommend LoRA flow for the bound `Lora Loader (LoraManager)` + `TriggerWord Toggle (LoraManager)` pair.

## MCP evidence (2026-08-05 session)

- comfyui-mcp 0.49.3 (stdio). Default compact mode exposes only `list_tools` / `describe_tool` / `call_tool`; the bridge requires `--full` so that `get_workflow` and siblings are directly addressable. Registered in the Codex config with `args = ["--full"]`.
- Twelve workflows in the live library; the four production files were synced via `get_workflow` in both api and ui formats.
- Camera workflow live shape: 141 UI nodes / 42 groups, 42-node API conversion with 10 warnings. Group controllers: node 23 `Fast Groups Bypasser (rgthree)` with `matchTitle: "（G1）"` (17 groups) and node 90 titled `Fast Groups Bypasser Post Processing` with `matchTitle: "（G2）"` (15 effect groups). Both pinned on canvas. Saved default state: t2i mode (加载图片（G1） bypassed), second-round sampler active, G2 contrast + sharpen active (nodes 96 / 111 mode=0).
- Local LoRA inventory via `list_local_models`: 28 files. The `Anima\` family (12 files) is the compatibility set for the camera base model `miaomiaoHarem_anima15.safetensors` (node 22). `FLux\`, `LTX\`, `WAN\`, `Qwen\` families serve other stages.
- Node 26 `widgets_values`: `[config header, lora stack text, structured list]`. Stack syntax `<lora:name:strength_model[:strength_clip]>`. Saved stack: `anima-base-1-masterpiece-v51` + `细节调整` + `gpt-image-2_anima-base1_v1-1` active, `Anima_in_real_epoch_10` inactive.
- Node 66 output feeds 79 (concat with camera+positive text) -> 83 (comma trim) -> 80 positive CLIPTextEncode. Node 26 output 3 (stack text) feeds only 87 -> 89 saver metadata, never the conditioning. Trigger word table matches active LoRAs only.

## First-principles axioms

1. Completeness: every output-affecting item is declared variable or value-pinned. No third state.
2. Discoverability: variable value domains come from live environment enumeration (MCP), never hardcoded assumptions.
3. Recommendation/decision separation: the system emits deterministic, evidence-bearing recommendations; selection is a human approval act.
4. Auditability: configuration -> config_hash -> draft -> approval -> consumption -> receipt, one lineage chain.
5. Fail closed: missing inventory entries, hash mismatches, or absent approval reject execution.

## Seven atomic configuration slots

| Slot | Nodes | Stage 1 | Stage 3 |
|---|---|---|---|
| prompts | 24 / 25 | PromptPackage text | shot PromptPackage text |
| camera_angle | 583 | pinned front / eye-level / full_body or medium / roll 0 | shot-directed, 4 allowlisted fields |
| camera_extra | 585 | neutral 13-field set | may enable, complete 13-field set required |
| groups_g1 | 23 (emulated) | all disabled | exactly the enabled_g1 set (img2img: 加载图片（G1）) |
| groups_g2 | 90 (emulated) | saved state, fingerprint-locked | saved state, fingerprint-locked |
| lora_unit | 26 + 66 (bound) | discovery -> recommendation -> approval | same unit, stage-appropriate selection |
| img2img_reference | 21 | unused (bypass) | accepted reference image name |

Group controllers are emulated deterministically by setting member-node modes (`patch_group_toggles`), never by depending on the FGB node classes being loadable.

## Profile schema: config_surface

Camera-family profiles add:

```json
"config_surface": {
  "schema_version": "1.0",
  "prompts": { "nodes": [24, 25], "fields": ["wildcard_text", "populated_text"] },
  "camera": { "angle_node": 583, "extra_node": 585 },
  "group_controllers": {
    "g1": { "node_id": 23, "match_title": "（G1）" },
    "g2": { "node_id": 90, "match_title": "（G2）" }
  },
  "lora_unit": {
    "loader_node": 26,
    "stack_widget_index": 1,
    "list_widget_index": 2,
    "trigger_toggle_node": 66,
    "binding": "atomic",
    "inventory_source": "mcp:list_local_models",
    "metadata_source": "mcp:model_metadata",
    "policy": "recommend-then-approve"
  },
  "img2img": "existing section unchanged"
}
```

## StageConfig contract

One canonical object per execution; its `config_hash` joins the draft lineage.

Fields: `schema_version`, `stage` (`character-base` | `shot-image`), `prompts`, `camera`, `camera_extra`, `groups` (`enabled_g1`, `enabled_g2`), `lora_plan`, `reference_image` (stage 3 only), `config_hash`.

`lora_plan` fields: `base_model` (read from pinned node 22), `selections` (list of `{name, strength_model, strength_clip, active, trigger_words, reason}`), `stack_text` (deterministically rendered), `inventory_hash`, `recommendation_hash`.

## lora_unit binding and invariants

Nodes 26 and 66 are one atomic slot: patches write both or neither. Consistency invariants, all fail-closed:

1. Stack text and structured list must be derivable from each other (round-trip).
2. Active trigger-word set in 66 equals the union of trigger words of `active: true` selections, in declared order.
3. An `active: false` LoRA must not contribute active trigger words (no prompt contamination without effect).
4. Node 66's concatenated word string equals the deterministic render of its word table.

## Discovery and recommendation

Flow: `discover-loras` -> `recommend-loras` -> approval -> `plan-lora`.

1. Inventory: `list_local_models`, keep the loras group, canonical hash -> `inventory_hash`.
2. Hard compatibility filter, evidence hierarchy:
   - tier 1: `model_metadata` (modelspec base model / ss_base_model_version) when readable;
   - tier 2: folder family (`Anima\` for the anima base model);
   - tier 3: filename keywords.
   Higher tiers override lower ones; conflicts emit explicit drift warnings. `FLux\`, `LTX\`, `WAN\`, `Qwen\` are rejected for camera stages.
3. Intent scoring: compatibility tier x style-tag overlap (art bible visual fingerprint vs `ss_tag_frequency` / civitai info) x stack-role diversity (style / detail / texture priors derived from the saved stack).
4. Output: `LoraRecommendation` = ranked candidates with per-item reason and evidence hashes, `recommended: true` on top pick, plus recommended trigger words per candidate. Pure data; never an action.
5. Decision rule (approved): recommendation is the default; the human may veto or hand-pick. Hand-picks must come from the current inventory; external names are rejected. Veto is recorded in the approval evidence.

## Patch chain

Fixed order, each step allowlisted diff + identity check with allowlisted values excluded:

normalize -> `patch_lora_unit` (26 stack text + structured list, 66 word table + concat string) -> `patch_group_toggles` (per-stage enabled sets) -> prompts 24/25 -> camera 583/585 -> reference 21 (stage 3 only).

Post-patch: run the four lora_unit invariants and the img2img path proof (stage 3).

## Gates and execution

- `StageExecutionDraft` gains `config_hash`, `lora_recommendation_hash`, `lora_inventory_hash`; approval events bind the draft hash as today.
- Pre-submission re-validation: fresh workflow re-read and fingerprint match; selected LoRAs still present in a fresh inventory; queue idle; URL matches CapabilityReport. Any miss fails closed.

## CLI surface

New: `discover-loras`, `recommend-loras`, `plan-lora`. Unchanged: plan/approve/consume/submit/wait chains.

## Migration

Profiles gain `config_surface_version`. Absent `config_surface` falls back to current behavior (LoRA state stays as saved in the workflow, fingerprint-locked). Stage 2 (Flux) and Stage 4 (LTX) keep their `immutable_node_inputs` pinning for now; the same discover/recommend flow may extend to them later without contract changes.

## Phase plan (test-first)

- P1: `lora_discovery.py` - inventory hashing, hard filter, scoring, stack/text round-trip, invariants. Fixtures for inventory + metadata.
- P2: `config_surface` schema validation + StageConfig contract.
- P3: `patch_lora_unit` + `patch_group_toggles` adapters.
- P4: draft/approval field integration + pre-submission LoRA presence re-check.
- P5: docs (USAGE + profile notes) + live opt-in verification.

## Decision log

- 2026-08-05: recommendation-as-default with explicit veto (user-approved).
- 2026-08-05: group controllers emulated via member-node modes, not FGB widgets.
- 2026-08-05: nodes 26 + 66 treated as one bound atomic slot (user-confirmed linkage).
- 2026-08-05 (live verification): fresh re-read proved the saved t2i state keeps three structural G1 groups active: 保存图片（G1）, 第二轮采样器（G1）, 相机视角生图（G1）. Added optional `pinned_groups` to config_surface; pinned group members are forced mode 0 and cannot appear in an enabled set. StageConfig enabled sets describe toggleable groups only; camera-slot nodes remain node-level exempt as defense in depth. MCP `get_workflow` api conversion drops mode-4 nodes entirely, and node 26 text input only survives via the normalization literal bridge, so the patch chain order stays UI-first, normalize-last.