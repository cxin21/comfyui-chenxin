"""Production seam for the model-native Prompt Forge module."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROMPT_FORGE_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "skills"
    / "prompt-forge"
)

_FORBIDDEN = frozenset({
    "workflow", "node", "gpu", "execution", "runtime", "profile",
    "camera", "lens", "lora", "loras", "checkpoint", "sampler",
    "seed", "steps", "cfg", "denoise",
})


def _ensure_prompt_forge_on_path() -> None:
    root = str(PROMPT_FORGE_ROOT)
    if not (PROMPT_FORGE_ROOT / "prompt_forge").is_dir():
        raise FileNotFoundError(
            f"new prompt-forge module is missing at {PROMPT_FORGE_ROOT}; "
            "run scripts/install.ps1 to sync the plugin source"
        )
    if root not in sys.path:
        sys.path.insert(0, root)


def _check_evidence(evidence: Any) -> dict[str, Any]:
    if evidence is None:
        return {}
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")
    bad = [key for key in evidence if str(key).casefold() in _FORBIDDEN]
    if bad:
        raise ValueError("evidence contains execution-only fields: " + ", ".join(sorted(bad)))
    return evidence


def _adapter_hash(value: Any) -> str | None:
    if value in (None, {}, [], ""):
        return None
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def forge_prompt(
    *,
    prompt: str,
    profile_id: str,
    operation: str,
    negative: str | None = None,
    duration: float | None = None,
    reference_count: int = 0,
    evidence: dict[str, Any] | None = None,
    regional: dict[str, str] | None = None,
    asset_bindings: tuple[dict[str, Any], ...] = (),
    workflow_sha256: str | None = None,
    adapter_manifest: Any = None,
) -> dict[str, Any]:
    """Validate one already authored prompt and return a Prompt Artifact.

    This seam deliberately does not expand or rewrite creative text. A caller
    that needs authoring must provide the LLM-authored final prompt first.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty authored string")
    evidence = _check_evidence(evidence)
    _ensure_prompt_forge_on_path()
    from prompt_forge import ForgeRequest, forge_prompt as _forge

    locked = tuple(
        {"statement": str(item), "evidence_location": "caller-authored"}
        for item in (evidence.get("locked_facts") or ())
        if str(item).strip()
    )
    request = ForgeRequest(
        profile_id=profile_id,
        operation=operation,
        positive=prompt,
        negative=negative,
        duration=duration,
        reference_count=reference_count,
        regional=regional or {},
        constraints=locked,
        asset_bindings=asset_bindings,
        workflow_sha256=workflow_sha256,
        adapter_manifest_sha256=_adapter_hash(adapter_manifest),
    )
    return _forge(request).to_dict()
