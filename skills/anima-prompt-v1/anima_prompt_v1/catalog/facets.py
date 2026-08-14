from __future__ import annotations

import re


_CATEGORY_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("style", ("watercolor", "watercolour", "illustration", "painting", "sketch", "manga", "comic", "render", "cinematic")),
    ("clothing", ("dress", "coat", "shirt", "skirt", "uniform", "armor", "armour", "bodysuit", "stockings", "gloves", "boots", "shoes", "jacket", "pants", "shorts", "underwear", "bikini", "swimsuit", "lingerie")),
    ("hair", ("hair", "ponytail", "braid", "bangs")),
    ("appearance", ("eyes", "eye", "skin", "face", "breasts", "chest", "body", "makeup", "freckles", "scar")),
    ("expression", ("smile", "frown", "blush", "crying", "angry", "serious")),
    ("pose", ("standing", "sitting", "lying", "kneeling", "walking", "running", "pose")),
    ("action", ("holding", "waving", "looking", "fighting", "shooting", "touching", "eating")),
    ("composition", ("portrait", "full_body", "upper_body", "close-up", "closeup", "wide_shot")),
    ("camera", ("view", "angle", "depth_of_field", "bokeh", "lens")),
    ("lighting", ("light", "lighting", "shadow", "rim_light", "sunlight", "backlight")),
    ("environment", ("sky", "forest", "street", "room", "station", "city", "beach", "ruins")),
    ("object", ("weapon", "sword", "gun", "flower", "book", "vehicle")),
    ("medium", ("photo", "photorealistic", "3d", "oil_painting")),
    ("model", ("checkpoint", "lora", "embedding", "trigger")),
)


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def classify_category(canonical: str, source_category: str) -> str:
    if source_category == "artist":
        return "artist"
    if source_category == "copyright":
        return "franchise"
    if source_category == "character":
        return "character"
    if source_category == "quality":
        return "quality"
    if source_category == "meta":
        return "meta"
    if source_category == "safety":
        return "nsfw"
    normalized = normalize(canonical)
    for category, markers in _CATEGORY_MARKERS:
        if any(re.search(rf"(?:^| ){re.escape(marker.replace('_', ' '))}(?:$| )", normalized) for marker in markers):
            return category
    return "general"


def derived_facets(canonical: str, source_category: str, category: str) -> tuple[str, ...]:
    facets = {f"category:{category}", f"source_category:{source_category}"}
    normalized = normalize(canonical)
    if source_category == "safety" or any(marker in normalized for marker in ("nude", "nudity", "naked", "nsfw", "nipples", "breasts")):
        facets.add("nsfw")
    if category == "style":
        facets.add("style")
    return tuple(sorted(facets))
