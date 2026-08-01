#!/usr/bin/env python3
"""hardware_decide — wrapper around `mcp/extensions/vram_decide.py` with a recipe-override layer.

The P0.2 vram_decide tool returns hardware-driven defaults (quant, swap_blocks,
sampler_defaults) for a model on a given VRAM budget. The P0.1 recipes in
`skills/chenxin-core/recipes/MODELS.md` carry their own dialect rules and,
implicitly, their own sampler/quant opinions. When a recipe declares its own
`quant` / `steps` / `cfg` / `scheduler` overrides, those win over hardware defaults.

This script imports vram_decide by file path (so we don't have to install
`mcp/extensions` as a Python package) and then merges in the recipe overrides.

Stdlib only (Python 3.11+).

Usage:
    python hardware_decide.py --vram 8 --model anima [--n 5]

Output JSON:
    {
      "model": "anima",
      "vram_gb": 8,
      "quant": "fp8_e4m3fn",         # recipe override if present, else hardware
      "swap_blocks": 40,
      "sampler_defaults": {...},     # recipe override if present, else hardware
      "blocked": false,
      "reason": "...",
      "source": "hardware/8gb.json#anima (recipe-overridden)",
      "recipe_overrides_applied": ["quant", "steps"]
    }
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

# recipe_lookup is a sibling module.
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent))

import recipe_lookup as _lookup

_THIS = Path(__file__).resolve()
INTERNALS_DIR = _THIS.parent
SKILL_DIR = INTERNALS_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent
MCP_EXTENSIONS = REPO_ROOT / "mcp" / "extensions"


def _require_python_311() -> None:
    if sys.version_info < (3, 11):
        sys.stderr.write("Python 3.11+ required\n")
        sys.exit(3)


def _load_vram_decide():
    """Import `vram_decide.py` from mcp/extensions by file path."""
    spec = importlib.util.spec_from_file_location("vram_decide", MCP_EXTENSIONS / "vram_decide.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load vram_decide from {MCP_EXTENSIONS / 'vram_decide.py'}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["vram_decide"] = module  # so `from _shared import ...` works inside vram_decide
    # vram_decide uses `from _shared import ...` which requires _shared to be importable.
    spec_sh = importlib.util.spec_from_file_location("_shared", MCP_EXTENSIONS / "_shared.py")
    if spec_sh is not None and spec_sh.loader is not None:
        mod_sh = importlib.util.module_from_spec(spec_sh)
        sys.modules["_shared"] = mod_sh
        spec_sh.loader.exec_module(mod_sh)
    spec.loader.exec_module(module)
    return module


# Fields that hardware can recommend AND that a recipe may override.
_OVERRIDE_KEYS = ("quant", "steps", "cfg", "scheduler", "sampler")


def _apply_recipe_overrides(rec: dict, recipe: dict) -> dict:
    """Return a copy of `rec` with recipe overrides applied where they exist.

    The recipe may declare overrides in two places:
      - `frontmatter["overrides"]` — explicit dict from the recipe author
      - `frontmatter["dialect"]`    — text containing `quant:` / `steps:` / `cfg:` hints
        (parsed heuristically; only triggered if an explicit overrides dict is absent)

    We only override keys in `_OVERRIDE_KEYS` and only when the recipe value is non-empty.
    """
    out = dict(rec)
    fm = recipe.get("frontmatter", {}) or {}
    overrides = fm.get("overrides") or {}

    applied: list[str] = []
    for key in _OVERRIDE_KEYS:
        v = overrides.get(key)
        if v in (None, ""):
            continue
        if key == "steps" or key == "cfg":
            try:
                v_cast = int(v) if key == "steps" else float(v)
            except (TypeError, ValueError):
                continue
        else:
            v_cast = str(v)
        if key in ("steps", "cfg", "scheduler", "sampler"):
            sd = dict(out.get("sampler_defaults") or {})
            if key in ("steps", "cfg"):
                sd[key] = v_cast
            else:
                sd[key] = v_cast
            out["sampler_defaults"] = sd
        elif key == "quant":
            out["quant"] = v_cast
        applied.append(key)

    if applied:
        existing = str(out.get("source", ""))
        out["source"] = f"{existing} (recipe-overridden: {','.join(applied)})"
        out["recipe_overrides_applied"] = applied
    return out


def main(argv: list[str] | None = None) -> int:
    _require_python_311()
    parser = argparse.ArgumentParser(
        prog="hardware_decide",
        description="Recommend quant/sampler with recipe-level overrides applied on top of hardware defaults.",
    )
    parser.add_argument("--vram", type=int, required=True, help="VRAM in GB (e.g. 8, 12, 16, 24)")
    parser.add_argument("--model", required=True, help="Model id, e.g. anima, flux, wan, sdxl")
    parser.add_argument("--n", type=int, default=5, help="Body lines to scan for dialect overrides (default 5)")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Override path to MODELS.md (rarely needed)",
    )
    args = parser.parse_args(argv)

    if args.vram < 1 or args.vram > 96:
        sys.stderr.write("[hardware_decide] --vram out of plausible range (1..96)\n")
        return 2

    vram_decide = _load_vram_decide()
    rec = vram_decide._recommend(vram_decide.load_hardware(args.vram), args.vram, args.model)
    if rec.get("blocked"):
        # No point looking up a recipe override if the model is blocked.
        json.dump(rec, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # Look up the recipe (don't fail if not found).
    recipes = _lookup._parse_recipes(_lookup.MODELS_PATH.read_text(encoding="utf-8"))
    recipe = _lookup._match(recipes, args.model)

    if recipe is None:
        sys.stderr.write(f"[hardware_decide] no recipe override for: {args.model}\n")
        json.dump(rec, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    merged = _apply_recipe_overrides(rec, recipe)
    json.dump(merged, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())