# skills/prompt-forge/internals/_aliases.py
"""Shared model alias table for recipe_lookup.py and recipe_yaml.py.

Maps common variant names to canonical recipe ids in recipes/MODELS.md.
Maintained via `python recipe_yaml.py --add-alias <alias>=<canonical>`.
"""

ALIASES: dict[str, list[str]] = {
    # Anima
    "anima_basev10": ["anima"],
    "animastandardv7": ["anima"],
    "anima_standardv7": ["anima"],
    "anima_base_v10": ["anima"],
    "anima-basev10": ["anima"],

    # SDXL
    "sdxl_base": ["sdxl"],
    "sdxl_base_1.0": ["sdxl"],
    "stable_diffusion_xl": ["sdxl"],
    "stable-diffusion-xl": ["sdxl"],

    # Pony
    "pony_diffusion_v6_xl": ["pony"],
    "pony_diffusion_v6": ["pony"],
    "pony_v6": ["pony"],

    # Illustrious
    "illustrious_xl": ["illustrious"],
    "illustriousxl": ["illustrious"],

    # NoobAI
    "noobai_xl": ["noobai"],
    "noobai-xl": ["noobai"],

    # Flux.1
    "flux_1_dev": ["flux_1"],
    "flux_1_schnell": ["flux_1"],
    "flux1_dev": ["flux_1"],
    "flux1_schnell": ["flux_1"],
    "flux_dev": ["flux_1"],
    "flux_schnell": ["flux_1"],

    # Flux.2
    "flux_2_klein": ["flux_2"],
    "flux_2_pro": ["flux_2"],
    "flux2_klein": ["flux_2"],
    "flux2_pro": ["flux_2"],

    # SD 1.5
    "sd_1.5": ["sd15"],
    "sd15": ["sd15"],
    "stable_diffusion_1.5": ["sd15"],
    "stable-diffusion-1.5": ["sd15"],

    # SD 3.5
    "sd_3.5": ["sd35"],
    "sd35_large": ["sd35"],
    "sd35_medium": ["sd35"],

    # Qwen-Image
    "qwen_image": ["qwen-image"],
    "qwen-image-edit": ["qwen-image"],

    # Seedream
    "seedream_4.5": ["seedream"],
    "seedream-4.5": ["seedream"],

    # HunyuanImage
    "hunyuan_image_3.0": ["hunyuan-image"],
    "hunyuan_image_2.1": ["hunyuan-image"],

    # Wan
    "wan_2.1": ["wan"],
    "wan_2.2": ["wan"],
    "wan_2.5": ["wan"],
    "wan_2.6": ["wan"],
    "wan2.1": ["wan"],
    "wan2.2": ["wan"],
    "wan2.5": ["wan"],

    # LTX
    "ltx_2.3": ["ltx"],
    "ltx_2_pro": ["ltx"],
    "ltx_video": ["ltx"],
    "ltx-video": ["ltx"],
    "ltx23": ["ltx"],

    # Kling
    "kling_1.6": ["kling"],
    "kling_2.0": ["kling"],

    # Hailuo
    "hailuo_video": ["hailuo"],
    "hailuo-02": ["hailuo"],
    "_smoke_fix2_alias": ["anima"],
}


def resolve_alias(alias: str) -> str | None:
    """Return canonical id for a known alias (case-insensitive), or None."""
    key = alias.lower().strip()
    canonicals = ALIASES.get(key)
    return canonicals[0] if canonicals else None


def all_aliases() -> list[str]:
    """Return all alias keys."""
    return list(ALIASES.keys())