"""Bridge to prompt-forge skill.

Enforces the project rule: ALL prompt text for every camera skill stage
must be authored through prompt-forge before reaching a ComfyUI submit.

Boundary (mirrored from prompt-forge):
- The compile envelope (evidence / scene_brief / dialect) MUST NOT carry
  any execution fields (workflow / node / hash / gpu / execution / mode /
  runtime / profile / camera / lens / lora / loras / checkpoint /
  sampler / seed / steps / cfg / denoise).
- Camera / LoRA / sampler / cfg / steps / seed stay in the camera skill;
  prompt-forge only owns the prompt text.

Flow:
1. Caller supplies a single natural-language scene_brief (the entire
   intent in prose) plus an evidence ledger (locked_facts,
   continuity_locks, ...). The caller never writes a Specification
   dataclass or a draft dict.
2. Bridge builds a minimal v3 Specification from scene_brief based on
   dialect (image -> Subject.identity; video -> Transition.action),
   normalises evidence via prompt-forge.internals, and calls
   internals.compile.compile() in-process.
3. The returned PromptPackage is converted to a dict and returned.
4. The caller refuses to continue if quality.ready_for_review is False
   or quality.errors is non-empty.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Path to prompt-forge skill root (sibling of mcp_server under the project).
PROMPT_FORGE_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "skills"
    / "prompt-forge"
)

# Fields forbidden inside prompt-forge envelopes. Belt-and-suspenders:
# the local check fires before we hand the envelope to prompt-forge.
_FORBIDDEN_IN_ENVELOPE = frozenset({
    "workflow", "node", "hash", "gpu", "execution", "mode", "runtime",
    "profile", "camera", "lens", "lora", "loras", "checkpoint", "sampler",
    "seed", "steps", "cfg", "denoise",
})

_VIDEO_DIALECTS = frozenset({
    "minimax_h3", "wan", "ltx", "kling", "sora", "veo", "seedance",
    "hunyuan", "hailuo", "runway", "luma", "vidu", "pika", "svd",
    "pixverse", "gemini_omni_flash",
})


def _check_evidence_shape(evidence: Any) -> None:
    """Reject any evidence that carries execution-only fields."""
    if not isinstance(evidence, dict):
        return
    bad = [k for k in evidence if k.lower() in _FORBIDDEN_IN_ENVELOPE]
    if bad:
        raise ValueError(
            "prompt-forge evidence must not carry execution fields: "
            + ", ".join(sorted(bad))
            + " - those belong to the camera skill"
        )


def _ensure_prompt_forge_on_path() -> None:
    """Add prompt-forge root to sys.path so we can `import internals`."""
    pf_root = str(PROMPT_FORGE_ROOT)
    if pf_root not in sys.path:
        sys.path.insert(0, pf_root)


def _scene_to_spec(scene_brief: str, dialect_id: str) -> Any:
    """Build a minimal v3 Specification from a single natural-language brief.

    The caller writes ONE prose string describing what they want. The
    bridge derives a minimal Specification whose initial_state carries
    the brief as Subject.identity (image) or whose transitions carry it
    as Transition.action (video). The dialect's projector renders the
    rest from there.

    Image: spec.modality='image', Subject(identity=brief)
    Video: spec.modality='video', single Transition over 0..5s with
           brief as both action and trigger
    """
    from internals.spec import Specification, State, Subject, Transition

    brief = scene_brief.strip()
    if not brief:
        raise ValueError("scene_brief must be a non-empty string")

    if dialect_id in _VIDEO_DIALECTS:
        # Default duration 5s; the camera-video skill's config.duration
        # takes precedence in the downstream RunConfig.
        result_state = State(subjects=(Subject(identity=brief),))
        transition = Transition(
            start=0.0,
            end=5.0,
            trigger="opening shot of the scene",
            action=brief,
            result=result_state,
        )
        return Specification(
            modality="video",
            initial_state=result_state,
            transitions=(transition,),
            duration=5.0,
        )

    return Specification(
        modality="image",
        initial_state=State(subjects=(Subject(identity=brief),)),
    )


def compile_envelope(
    scene_brief: str,
    evidence: dict | None = None,
    dialect_id: str = "anima",
) -> dict:
    """Run prompt-forge.internals.compile on a natural-language scene brief.

    Args:
        scene_brief: caller-authored prose describing the entire scene in
            natural language. The bridge derives a minimal Specification
            from this string; callers do not write draft dicts or
            Specification dataclasses.
        evidence: CreativeEvidence-shaped ledger (no execution fields).
            May be empty {} for a one-shot prompt with no persistence
            requirements.
        dialect_id: prompt-forge dialect id (default "anima"). Camera-video
            skills pass "minimax_h3".

    Returns:
        PromptPackage dict with quality flags. Raises if
        quality.ready_for_review is False or quality.errors is non-empty.

    Raises:
        FileNotFoundError: prompt-forge skill not installed.
        ValueError: scene_brief is empty or envelope violated boundary.
        RuntimeError: prompt-forge rejected the spec, or compilation failed.
    """
    if not (PROMPT_FORGE_ROOT / "internals").is_dir():
        raise FileNotFoundError(
            f"prompt-forge skill not found at {PROMPT_FORGE_ROOT}; "
            "run scripts/install.ps1 to sync"
        )

    if not isinstance(scene_brief, str):
        raise ValueError(
            f"scene_brief must be a string, got {type(scene_brief).__name__}: "
            f"{scene_brief!r}"
        )
    if not scene_brief.strip():
        raise ValueError("scene_brief must be a non-empty string")

    _check_evidence_shape(evidence or {})

    _ensure_prompt_forge_on_path()

    # Import after sys.path is updated.
    from internals.evidence import normalize_evidence
    from internals.compile import compile as pf_compile

    try:
        evidence_obj = normalize_evidence(evidence or {})
    except ValueError as exc:
        # Surface the field path so callers can locate the bad key.
        raise RuntimeError(f"prompt-forge rejected evidence: {exc}") from exc

    spec = _scene_to_spec(scene_brief, dialect_id)

    try:
        package = pf_compile(spec, dialect_id, evidence_obj)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"prompt-forge rejected spec for dialect {dialect_id!r}: {exc}"
        ) from exc

    pkg_dict = package.to_dict()
    errors = pkg_dict.get("violations") or []
    missing = pkg_dict.get("missing_facts") or ()
    if errors:
        raise RuntimeError(
            "prompt-forge flagged errors in prompt draft: "
            + "; ".join(f"{v.get('code','?')}:{v.get('message','?')}" for v in errors)
        )
    if not pkg_dict.get("ready_for_review", False):
        reasons: list[str] = []
        for key in (
            "facts_preserved",
            "no_unsupported_invention",
            "style_coherent",
            "dialect_valid",
            "temporal_logic_valid",
        ):
            if not pkg_dict.get(key, True):
                reasons.append(f"{key}=false")
        if missing:
            reasons.append(f"missing_facts={len(missing)}")
        raise RuntimeError(
            "prompt-forge marked prompt not ready_for_review: "
            + ", ".join(reasons)
            + "; refine scene_brief to mention the missing fact and re-run"
        )

    return pkg_dict