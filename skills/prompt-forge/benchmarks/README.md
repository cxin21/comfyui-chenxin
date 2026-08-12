# Prompt Forge benchmark and calibration

The corpus contains 30 original, hand-reviewed cases for each production path, evenly split across simple, boundary, and adversarial strata. Cases store a fact ledger and authored model-native fields; they do not copy gallery prompts.

Run the deterministic hard-gate benchmark with:

```powershell
python scripts/run_benchmarks.py --verify-baseline
```

Metrics remain separate. Protected-fact recall, duplicate semantics, binding violations, exact token count, compression savings, status, and deterministic hash never collapse into a compensating total score. Baseline changes require a reviewed per-case diff and a machine-readable reason in the change record.

Prepare real-generation manifests with:

```powershell
python scripts/run_benchmarks.py --prepare-generation-pairs output/pairs.jsonl
```

This only emits paired manifests; it never contacts or executes ComfyUI. Fill workflow hashes and expert-authored variants before generation. Use identical workflows and seeds, hide variant identity, randomize A/B order, and collect independent human decisions under `calibration.schema.json`.

For Anima, review fact adherence, owner/count binding, and technical quality separately. For H3, review continuity, action completion, reference retention, audio synchronization, and technical quality separately. Automated checks may reject obvious failures but cannot declare visual quality.

Calibrate each path and complexity stratum independently. Select the shortest token range within one percentage point of the observed maximum fact adherence; derive the soft limit from the 90th percentile; set the quality limit where added text stops improving adherence or increases conflicts. Do not change hard fact-preservation, ownership, reference, dialogue, or timing gates from preference scores. Policy changes require coverage of Anima tag-only and hybrid cases, every H3 duration stratum, and H3 one- and three-reference cases.
