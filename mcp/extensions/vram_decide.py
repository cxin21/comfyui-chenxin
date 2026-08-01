#!/usr/bin/env python3
"""vram_decide — hardware-aware model + quant + sampler recommendation.

Reads `skills/prompt-forge/hardware/<vram_gb>.json` and emits a JSON
recommendation. Stdlib only.

Usage:
    python vram_decide.py --vram 8 --model anima
    python vram_decide.py --vram 16 --model flux [--seed 42]

Output JSON:
    {
      "model": "anima",
      "vram_gb": 8,
      "quant": "fp8_e4m3fn",
      "swap_blocks": 40,
      "sampler_defaults": {"sampler": "euler", "scheduler": "normal", "steps": 25, "cfg": 5.5},
      "blocked": false,
      "reason": "8 GB VRAM fits anima-fp8 with 40 swap blocks; euler/25/5.5 are conservative defaults",
      "source": "hardware/8.json#anima"
    }

When the model is not listed in the hardware profile, or VRAM is too low,
the tool emits `blocked: true` with a reason and an empty recommendation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _shared import EXIT_OK, emit_human, emit_json, err_exit, load_hardware, require_python_311

# ----- conservative sampler defaults --------------------------------------- #
# These are the *defaults* when the hardware profile does not specify
# sampler_defaults for a given model. They are intentionally generic — the
# the per-model recipe (P0.1 knowledge substrate) is the source of truth for
# prompt dialects; this CLI just answers "will it fit and at what quant".

_DEFAULT_SAMPLER: dict = {
    "sampler": "euler",
    "scheduler": "normal",
    "steps": 25,
    "cfg": 5.5,
}


def _recommend(profile: dict, vram_gb: int, model: str) -> dict:
    """Compute the recommendation dict from the loaded hardware profile."""
    models = profile.get("models", {})
    if not isinstance(models, dict):
        models = {}

    if model not in models:
        # Not in profile at all: surface a soft-block, suggest checking recipes.
        return {
            "model": model,
            "vram_gb": vram_gb,
            "quant": "",
            "swap_blocks": 0,
            "sampler_defaults": {},
            "blocked": True,
            "reason": f"model '{model}' not listed in hardware/{vram_gb}.json; consult recipes/MODELS.md",
            "source": f"hardware/{vram_gb}.json",
        }

    entry = models[model]
    if not isinstance(entry, dict):
        return {
            "model": model,
            "vram_gb": vram_gb,
            "quant": "",
            "swap_blocks": 0,
            "sampler_defaults": {},
            "blocked": True,
            "reason": f"hardware entry for '{model}' is malformed",
            "source": f"hardware/{vram_gb}.json#{model}",
        }

    blocked = bool(entry.get("blocked", False))
    quant = str(entry.get("quant", "fp16"))
    swap_blocks = int(entry.get("swap_blocks", 0))
    sampler = entry.get("sampler_defaults") or _DEFAULT_SAMPLER
    if not isinstance(sampler, dict):
        sampler = _DEFAULT_SAMPLER

    reason = str(
        entry.get(
            "reason",
            f"{vram_gb} GB VRAM fits '{model}' at {quant} with {swap_blocks} swap blocks",
        )
    )

    return {
        "model": model,
        "vram_gb": vram_gb,
        "quant": quant,
        "swap_blocks": swap_blocks,
        "sampler_defaults": sampler,
        "blocked": blocked,
        "reason": reason,
        "source": f"hardware/{vram_gb}.json#{model}",
    }


def main(argv: list[str] | None = None) -> int:
    require_python_311()
    parser = argparse.ArgumentParser(
        prog="vram_decide",
        description="Recommend quant, sampler, and block-swap count for a model on given VRAM.",
    )
    parser.add_argument("--vram", type=int, required=True, help="VRAM in GB (e.g. 8, 12, 16, 24)")
    parser.add_argument("--model", required=True, help="Model id, e.g. anima, flux, wan, sdxl")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed echoed in the output (no functional effect)",
    )
    args = parser.parse_args(argv)

    if args.vram < 1 or args.vram > 96:
        err_exit(2, "--vram out of plausible range (1..96)", vram_gb=args.vram)

    profile = load_hardware(args.vram)
    if not profile:
        emit_human(
            f"no hardware profile at hardware/{args.vram}.json — emitting empty recommendation"
        )

    rec = _recommend(profile, args.vram, args.model)
    if args.seed is not None:
        rec["seed"] = args.seed

    emit_human(
        f"{args.model} on {args.vram}GB -> quant={rec['quant']} swap_blocks={rec['swap_blocks']} blocked={rec['blocked']}"
    )
    emit_json(rec)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())