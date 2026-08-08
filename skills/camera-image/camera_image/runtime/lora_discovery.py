"""LoRA discovery, recommendation, and lora_unit consistency for the camera workflow.

Implements the P1 slice of the config-surface design
(docs/superpowers/specs/2026-08-05-config-surface-lora-unit-design.md).

The module is pure and host-neutral: MCP results arrive as plain dicts
(``inventory`` from ``list_local_models``, ``metadata`` from
``model_metadata``), so discovery logic stays testable offline.  Nothing here
mutates a graph or performs submission; recommendation output is data with
hash lineage, never an action.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from .contracts import canonical_json, content_hash


class LoraDiscoveryError(ValueError):
    """Raised when LoRA discovery, recommendation, or unit consistency fails."""


_TIER_WEIGHTS = {"metadata": 3, "folder": 2, "filename": 1}

def parse_local_model_listing(value: object) -> dict:
    """Normalize the MCP list_local_models response into an inventory object."""
    if isinstance(value, dict):
        return {"loras": _require_inventory(value)}
    if isinstance(value, list):
        return {"loras": _require_inventory({"loras": value})}
    if not isinstance(value, str):
        raise LoraDiscoveryError("MCP LoRA listing must be text, list, or object")
    names = []
    in_loras = False
    for line in value.splitlines():
        if line.strip().lower().startswith("## loras"):
            in_loras = True
            continue
        if in_loras:
            match = re.match(r"^\s*-\s+(.+?)\s*$", line)
            if match:
                names.append(match.group(1).strip().strip("`"))
    if not names:
        raise LoraDiscoveryError("MCP LoRA listing contains no loras")
    return {"loras": _require_inventory({"loras": names})[0:]}


@dataclass(frozen=True)
class LoraSelection:
    """One approved LoRA entry of the bound lora_unit (loader + trigger toggle)."""

    name: str
    strength_model: float = 1.0
    strength_clip: float = 1.0
    active: bool = True
    trigger_words: list = field(default_factory=list)


def _require_inventory(inventory: object) -> list[str]:
    if not isinstance(inventory, dict):
        raise LoraDiscoveryError("LoRA inventory must be an object")
    loras = inventory.get("loras")
    if not isinstance(loras, list):
        raise LoraDiscoveryError("LoRA inventory requires a loras list")
    for item in loras:
        if not isinstance(item, str) or not item.strip():
            raise LoraDiscoveryError("LoRA inventory entries must be non-empty strings")
    return copy.deepcopy(loras)


def hash_inventory(inventory: object) -> str:
    """Hash the LoRA inventory order-insensitively and canonically."""
    loras = _require_inventory(inventory)
    return content_hash({"schema_version": "1.0", "loras": sorted(loras)})


def _folder_family(name: str) -> str | None:
    if "\\" not in name:
        return None
    family = name.split("\\", 1)[0].strip()
    return family or None


def _metadata_matches(name: str, base_model: str, metadata: dict) -> bool | None:
    entry = metadata.get(name)
    if not isinstance(entry, dict):
        return None
    declared = entry.get("base_model")
    if not isinstance(declared, str) or not declared.strip():
        return None
    return declared.strip().casefold() in base_model.casefold()


def _matching_family_tokens(inventory_names: list[str], base_model: str) -> set[str]:
    tokens = set()
    for name in inventory_names:
        family = _folder_family(name)
        if family and family.casefold() in base_model.casefold():
            tokens.add(family.casefold())
    return tokens


def compatibility_tier(name: str, base_model: str, metadata: dict) -> str | None:
    """Return the strongest compatibility evidence tier, or None when incompatible.

    Evidence hierarchy: embedded metadata beats folder family, folder family
    beats filename keywords.  A readable metadata declaration that contradicts
    the base model is authoritative and rejects the candidate.
    """
    if not isinstance(name, str) or not name.strip():
        raise LoraDiscoveryError("LoRA name must be a non-empty string")
    if not isinstance(base_model, str) or not base_model.strip():
        raise LoraDiscoveryError("base model must be a non-empty string")
    if not isinstance(metadata, dict):
        raise LoraDiscoveryError("LoRA metadata must be an object")
    declared = _metadata_matches(name, base_model, metadata)
    if declared is True:
        return "metadata"
    if declared is False:
        return None
    family = _folder_family(name)
    if family is not None:
        return "folder" if family.casefold() in base_model.casefold() else None
    return None


def hard_filter(
    inventory: object, base_model: str, metadata: dict | None = None
) -> tuple[list[dict], list[dict]]:
    """Split the inventory into compatible candidates and rejected entries."""
    loras = _require_inventory(inventory)
    meta = metadata or {}
    if not isinstance(meta, dict):
        raise LoraDiscoveryError("LoRA metadata must be an object")
    tokens = _matching_family_tokens(loras, base_model)
    keep: list[dict] = []
    rejected: list[dict] = []
    for name in loras:
        tier = compatibility_tier(name, base_model, meta)
        if tier is None and _folder_family(name) is None:
            filename = name.rsplit("\\", 1)[-1].casefold()
            if any(token in filename for token in tokens):
                tier = "filename"
        if tier is None:
            rejected.append(
                {"name": name, "reason": f"no compatibility evidence for base model {base_model}"}
            )
        else:
            keep.append({"name": name, "tier": tier})
    return keep, rejected


def recommend(
    inventory: object,
    base_model: str,
    metadata: dict | None = None,
    *,
    style_tags: list[str] | None = None,
) -> dict:
    """Produce a deterministic, evidence-bearing LoRA recommendation."""
    inventory_hash = hash_inventory(inventory)
    keep, _rejected = hard_filter(inventory, base_model, metadata)
    if not keep:
        raise LoraDiscoveryError(f"no compatible LoRA candidates for base model {base_model}")
    meta = metadata or {}
    wanted = {tag.casefold() for tag in style_tags or [] if isinstance(tag, str) and tag.strip()}
    candidates = []
    for item in keep:
        entry = meta.get(item["name"])
        tags = entry.get("tags", []) if isinstance(entry, dict) else []
        tags = [tag for tag in tags if isinstance(tag, str) and tag.strip()]
        overlap = len({tag.casefold() for tag in tags} & wanted)
        score = _TIER_WEIGHTS[item["tier"]] * 10 + overlap
        reason = f"compatibility tier: {item['tier']}"
        if overlap:
            reason += f"; style tag overlap: {overlap}"
        candidates.append(
            {
                "name": item["name"],
                "tier": item["tier"],
                "score": score,
                "recommended": False,
                "trigger_words": copy.deepcopy(tags),
                "reason": reason,
            }
        )
    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["name"]))
    candidates[0]["recommended"] = True
    recommendation = {
        "schema_version": "1.0",
        "base_model": base_model,
        "inventory_hash": inventory_hash,
        "candidates": candidates,
    }
    recommendation["recommendation_hash"] = content_hash(recommendation)
    return recommendation




def build_lora_plan(
    recommendation: dict,
    *,
    selected_names: list[str] | None = None,
    strength_model: float = 1.0,
    strength_clip: float = 1.0,
) -> dict:
    """Turn an explicit recommendation choice into the canonical lora_plan."""
    if not isinstance(recommendation, dict):
        raise LoraDiscoveryError("LoRA recommendation must be an object")
    candidates = recommendation.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise LoraDiscoveryError("LoRA recommendation has no candidates")
    recommended = next((item.get("name") for item in candidates if item.get("recommended")), None)
    chosen = selected_names or ([recommended] if recommended else [])
    if not chosen or any(not isinstance(name, str) or not name.strip() for name in chosen):
        raise LoraDiscoveryError("selected LoRA names must be non-empty strings")
    by_reference = {normalize_lora_reference(item.get("name")): item for item in candidates}
    selections = []
    for name in chosen:
        candidate = by_reference.get(normalize_lora_reference(name))
        if candidate is None:
            raise LoraDiscoveryError(f"selected LoRA is not in recommendation: {name}")
        selections.append({
            "name": candidate["name"],
            "strength_model": float(strength_model),
            "strength_clip": float(strength_clip),
            "active": True,
            "trigger_words": copy.deepcopy(candidate.get("trigger_words", [])),
        })
    stack_text = render_lora_stack([LoraSelection(**item) for item in selections])
    return {
        "base_model": recommendation.get("base_model"),
        "selections": selections,
        "inventory_hash": recommendation.get("inventory_hash"),
        "recommendation_hash": recommendation.get("recommendation_hash"),
        "stack_text": stack_text,
    }

def render_lora_stack(selections: list[LoraSelection]) -> str:
    """Deterministically render the node 26 stack text from selections."""
    parts = []
    for selection in selections:
        if not isinstance(selection, LoraSelection):
            raise LoraDiscoveryError("lora stack selections must be LoraSelection objects")
        reference = normalize_lora_reference(selection.name)
        if abs(selection.strength_clip - selection.strength_model) < 1e-9:
            parts.append(f"<lora:{reference}:{selection.strength_model:.2f}>")
        else:
            parts.append(
                f"<lora:{reference}:{selection.strength_model:.2f}:{selection.strength_clip:.2f}>"
            )
    return "".join(parts)


def validate_unit_invariants(selections: list[LoraSelection], active_words: list[str]) -> None:
    """Validate the bound lora_unit invariants (loader 26 + trigger toggle 66)."""
    if not isinstance(selections, list) or not isinstance(active_words, list):
        raise LoraDiscoveryError("lora_unit invariants require selection and word lists")
    expected: list[str] = []
    for selection in selections:
        if not isinstance(selection, LoraSelection):
            raise LoraDiscoveryError("lora_unit selections must be LoraSelection objects")
        if selection.active:
            expected.extend(selection.trigger_words)
    if list(active_words) == expected:
        return
    inactive_words = {
        word
        for selection in selections
        if not selection.active
        for word in selection.trigger_words
    }
    unexpected = [word for word in active_words if word not in expected]
    if unexpected and any(word in inactive_words for word in unexpected):
        offenders = sorted(set(unexpected) & inactive_words)
        raise LoraDiscoveryError(
            "trigger words belong to an inactive LoRA: " + ", ".join(offenders)
        )
    if unexpected:
        raise LoraDiscoveryError(
            "active trigger words do not match lora_unit selections: " + ", ".join(unexpected)
        )
    missing = [word for word in expected if word not in list(active_words)]
    raise LoraDiscoveryError(
        "active selections are missing trigger words: " + ", ".join(dict.fromkeys(missing))
    )


def to_lora_reference(name: object) -> str:
    """Convert an inventory filename to its extensionless ComfyUI reference."""
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise LoraDiscoveryError("LoRA name must be a non-empty trimmed string")
    suffix = ".safetensors"
    if not name.endswith(suffix) or name == suffix:
        raise LoraDiscoveryError("LoRA inventory name must end with .safetensors")
    return name[: -len(suffix)]


def normalize_lora_reference(name: object) -> str:
    """Accept either an inventory filename or an existing ComfyUI reference."""
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise LoraDiscoveryError("LoRA name must be a non-empty trimmed string")
    suffix = ".safetensors"
    if name == suffix:
        raise LoraDiscoveryError("LoRA name must contain a reference")
    return name[: -len(suffix)] if name.endswith(suffix) else name

def verify_lora_presence(inventory: object, selections: object) -> list[str]:
    """Fail closed when any approved selection is no longer in the inventory.

    Selections carry ComfyUI references (see ``to_lora_reference``) while the
    inventory carries file names, so a selection is present exactly when
    ``reference + ".safetensors"`` appears in the inventory.
    """
    loras = set(_require_inventory(inventory))
    if not isinstance(selections, list) or not selections:
        raise LoraDiscoveryError("lora presence check requires at least one selection")
    references: list[str] = []
    for selection in selections:
        if isinstance(selection, LoraSelection):
            raw_name = selection.name
        elif isinstance(selection, dict):
            raw_name = selection.get("name")
        else:
            raise LoraDiscoveryError(
                "lora presence selections must be LoraSelection objects or dicts"
            )
        reference = normalize_lora_reference(raw_name)
        references.append(reference)
    inventory_names = {reference + ".safetensors" for reference in references}
    missing = sorted(inventory_names - loras)
    if missing:
        raise LoraDiscoveryError(
            "LoRA selections missing from inventory: " + ", ".join(missing)
        )
    return sorted(inventory_names)








