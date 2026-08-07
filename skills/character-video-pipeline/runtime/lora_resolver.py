"""LoRA discovery, short-name matching, and default stack for camera runs.

Uses MCP list_local_models to discover available LoRAs. Supports short-name
matching so users can pass "add_detail" instead of "Anima\\add_detail.safetensors".

`build_lora_patch(run_config_lora, mcp_list_loras=None)` accepts the
`RunConfig.lora` dict shape (see config_schema.RunConfig.lora) and reads the
optional `selections` key. None / empty dict / missing key fall through to
the default 3-LoRA plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


DEFAULT_LORA_STACK_TEXT = (
    "<lora:anima-base-1-masterpiece-v51:1.00>"
    "<lora:add_detail:1.00>"
    "<lora:gpt-image-2_anima-base1_v1-1:1.00>"
)

DEFAULT_TRIGGER_WORDS = ["masterpiece", "very aesthetic", "@gpt-image-2"]
DEFAULT_TRIGGER_MESSAGE = "masterpiece,, very aesthetic,, @gpt-image-2,"

_ANIMA_FOLDER = "anima"


@dataclass(frozen=True)
class LoraSelection:
    """One LoRA entry for the LoraManager loader."""
    name: str
    strength_model: float = 1.0
    strength_clip: float = 1.0
    active: bool = True
    trigger_words: list[str] = field(default_factory=list)


def _normalize_filename(name: str) -> str:
    """Strip folder prefix and .safetensors extension."""
    name = name.strip()
    if "\\" in name:
        name = name.rsplit("\\", 1)[-1]
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    if name.endswith(".safetensors"):
        name = name[: -len(".safetensors")]
    return name


def _is_anima_lora(filename: str) -> bool:
    """Check if a LoRA file belongs to the Anima model family."""
    folder = filename.split("\\", 1)[0].strip().casefold() if "\\" in filename else ""
    return _ANIMA_FOLDER in folder


def parse_lora_inventory(raw: Any) -> list[str]:
    """Parse MCP list_local_models response into LoRA filename list."""
    if isinstance(raw, dict):
        loras = raw.get("loras")
        if isinstance(loras, list):
            return [str(item) for item in loras if isinstance(item, str)]
    if isinstance(raw, list):
        return [str(item) for item in raw if isinstance(item, str)]
    if isinstance(raw, str):
        names = []
        in_loras = False
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("## loras"):
                in_loras = True
                continue
            if in_loras and stripped.startswith("- "):
                names.append(stripped[2:].strip().strip("`"))
        return names
    raise ValueError(f"cannot parse LoRA inventory from type {type(raw).__name__}")


def filter_anima_loras(inventory: list[str]) -> list[str]:
    """Filter inventory to Anima-family LoRAs."""
    return [name for name in inventory if _is_anima_lora(name)]


def resolve_lora_names(
    selections: list[str],
    inventory: list[str],
) -> list[LoraSelection]:
    """Resolve user-provided LoRA names against inventory.

    Matching priority:
    1. Exact short-name match (normalized filename)
    2. Exact full-name match
    3. Case-insensitive substring match on short name
    """
    by_short: dict[str, str] = {}
    for full_name in inventory:
        short = _normalize_filename(full_name)
        by_short[short.casefold()] = full_name

    resolved: list[LoraSelection] = []
    for sel in selections:
        sel = sel.strip()
        if not sel:
            continue
        key = sel.casefold()
        if key in by_short:
            resolved.append(LoraSelection(
                name=_normalize_filename(by_short[key]),
            ))
            continue
        matched = False
        for full_name in inventory:
            if full_name == sel or full_name.casefold() == key:
                resolved.append(LoraSelection(
                    name=_normalize_filename(full_name),
                ))
                matched = True
                break
        if matched:
            continue
        matches = [
            short for short in by_short
            if key in short or short in key
        ]
        if len(matches) == 1:
            full = by_short[matches[0]]
            resolved.append(LoraSelection(
                name=_normalize_filename(full),
            ))
        elif len(matches) > 1:
            raise ValueError(
                f"LoRA name {sel!r} is ambiguous, matches: {matches}"
            )
        else:
            raise ValueError(f"LoRA {sel!r} not found in inventory")
    return resolved


def default_lora_plan() -> list[LoraSelection]:
    """Return the default 3-LoRA stack."""
    return [
        LoraSelection(
            name="anima-base-1-masterpiece-v51",
            trigger_words=["masterpiece", "very aesthetic"],
        ),
        LoraSelection(name="add_detail", trigger_words=[]),
        LoraSelection(
            name="gpt-image-2_anima-base1_v1-1",
            trigger_words=["@gpt-image-2"],
        ),
    ]


def render_stack_text(selections: list[LoraSelection]) -> str:
    """Render LoRA selections as LoraManager stack text."""
    parts = []
    for sel in selections:
        if abs(sel.strength_clip - sel.strength_model) < 1e-9:
            parts.append(f"<lora:{sel.name}:{sel.strength_model:.2f}>")
        else:
            parts.append(
                f"<lora:{sel.name}:{sel.strength_model:.2f}:{sel.strength_clip:.2f}>"
            )
    return "".join(parts)


def render_trigger_concat(selections: list[LoraSelection]) -> str:
    """Render the TriggerWord Toggle orinalMessage string."""
    words = []
    for sel in selections:
        if sel.active:
            words.extend(sel.trigger_words)
    return ", ".join(f"{word}," for word in words) if words else ""


def build_lora_patch(
    run_config_lora: dict | None,
    mcp_list_loras: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Build the node 26 + node 66 patch values from RunConfig.lora dict.

    run_config_lora supported shape:
      {"selections": [short_name_or_full_filename, ...]}  (optional key)
    If run_config_lora is None or empty, uses the default 3-LoRA stack.
    If "selections" key is present and non-empty, resolves against MCP
    inventory.
    """
    selections = None
    if isinstance(run_config_lora, dict):
        raw = run_config_lora.get("selections")
        if isinstance(raw, list) and raw:
            selections = raw

    if selections:
        if mcp_list_loras is None:
            raise ValueError("LoRA selections provided but no MCP resolver available")
        raw_inv = mcp_list_loras()
        inventory = parse_lora_inventory(raw_inv)
        anima_loras = filter_anima_loras(inventory)
        resolved = resolve_lora_names(selections, anima_loras)
    else:
        resolved = default_lora_plan()

    stack_text = render_stack_text(resolved)
    trigger_message = render_trigger_concat(resolved)

    return {
        "node_26": {"text": stack_text},
        "node_66": {
            "trigger_words": ["26", 2],
            "orinalMessage": trigger_message,
        },
        "selections": [
            {
                "name": s.name,
                "strength_model": s.strength_model,
                "strength_clip": s.strength_clip,
                "active": s.active,
                "trigger_words": list(s.trigger_words),
            }
            for s in resolved
        ],
        "stack_text": stack_text,
    }
