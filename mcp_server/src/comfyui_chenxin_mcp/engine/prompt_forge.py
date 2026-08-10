"""Bridge to prompt-forge skill.

Enforces the project rule: ALL prompt text for every camera skill stage
must be authored through prompt-forge before reaching a ComfyUI submit.

Boundary (mirrored from prompt-forge):
- The compile envelope (evidence / draft / dialect) MUST NOT carry any
  execution fields (workflow / node / hash / gpu / execution / mode /
  runtime / profile / camera / lens / lora / loras / checkpoint /
  sampler / seed / steps / cfg / denoise).
- Camera / LoRA / sampler / cfg / steps / seed stay in the camera skill;
  prompt-forge only owns the prompt text.

Flow:
1. Caller supplies evidence (locked_facts, continuity_locks, ...) and a
   draft (positive + negative for image; global_prompt + duration_seconds
   + reference_count for video).
2. Bridge builds a minimal v3 Specification from the draft, normalises
   the evidence via prompt-forge.internals, and calls
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


def _check_envelope(envelope: dict) -> None:
    """Reject any envelope that carries execution-only fields."""
    bad: list[str] = []
    for section in ("evidence", "draft"):
        body = envelope.get(section)
        if not isinstance(body, dict):
            continue
        for key in body:
            if key.lower() in _FORBIDDEN_IN_ENVELOPE:
                bad.append(f"{section}.{key}")
    if bad:
        raise ValueError(
            "prompt-forge envelope must not carry execution fields: "
            + ", ".join(sorted(set(bad)))
            + " - those belong to the camera skill"
        )


def _ensure_prompt_forge_on_path() -> None:
    """Add prompt-forge root to sys.path so we can `import internals`."""
    pf_root = str(PROMPT_FORGE_ROOT)
    if pf_root not in sys.path:
        sys.path.insert(0, pf_root)


def _draft_to_spec(draft: dict, dialect_id: str) -> Any:
    """Build a minimal v3 Specification from the simple camera draft.

    Image drafts: {"positive": str, "negative": str, "tags": [...], "structure": [...]}
    Video drafts: {"global_prompt": str, "duration_seconds": int, "reference_count": int}

    The new prompt-forge v3 takes typed concept objects (Subject, Costume,
    etc.) rather than flat strings. The bridge maps the flat draft into a
    minimal Specification whose initial_state.subjects[0].identity is the
    positive/global_prompt text. The dialect renders that into the
    project-specific prompt. Quality is the gate; exact byte-for-byte
    equality with the input draft is not promised.
    """
    from internals.spec import Specification, State, Subject, Style, Transition

    is_video = (
        "global_prompt" in draft
        or "duration_seconds" in draft
        or dialect_id in ("minimax_h3", "wan", "ltx", "kling", "sora", "veo", "seedance", "hunyuan", "hailuo", "runway", "luma", "vidu", "pika", "svd", "pixverse", "gemini_omni_flash")
    )

    if is_video:
        global_prompt = str(draft.get("global_prompt") or "").strip()
        if not global_prompt:
            raise ValueError("video draft.global_prompt must be a non-empty string")
        duration = float(draft.get("duration_seconds") or 5.0)
        # P2-0/P4-5: videos need at least one transition; P2-1/P5-1 require
        # the transition's trigger to name the cause with at least 2 word
        # tokens. The bridge synthesises a single beat so the runtime can
        # produce a ready_for_review video without inventing story beats;
        # the camera-video skill supplies the real beat structure via
        # config.
        result_state = State(subjects=(Subject(identity=global_prompt),))
        transition = Transition(
            start=0.0,
            end=duration,
            trigger="opening shot of the scene",
            action=global_prompt,
            result=result_state,
        )
        spec = Specification(
            modality="video",
            initial_state=result_state,
            transitions=(transition,),
            duration=duration,
            h3_flow=draft.get("h3_flow"),
        )
        return spec

    positive = str(draft.get("positive") or "").strip()
    if not positive:
        raise ValueError("image draft.positive must be a non-empty string")
    negative = str(draft.get("negative") or "").strip()
    style_directives = tuple(
        str(t).strip() for t in (draft.get("tags") or []) if str(t).strip()
    )
    style = Style(directives=style_directives) if style_directives else None
    spec = Specification(
        modality="image",
        initial_state=State(subjects=(Subject(identity=positive),)),
        negative=(negative,) if negative else (),
        style=style,
    )
    return spec


def compile_envelope(
    evidence: dict,
    draft: dict,
    dialect_id: str = "anima",
) -> dict:
    """Run prompt-forge.internals.compile on the supplied envelope.

    Args:
        evidence: CreativeEvidence-shaped ledger (no execution fields).
        draft: caller-authored prompt fields (positive + negative for image,
            global_prompt + duration_seconds + reference_count for video).
        dialect_id: prompt-forge dialect id (default "anima").

    Returns:
        PromptPackage dict with quality flags. Raises if
        quality.ready_for_review is False or quality.errors is non-empty.

    Raises:
        FileNotFoundError: prompt-forge skill not installed.
        ValueError: envelope violated boundary or draft is incomplete.
        RuntimeError: prompt-forge rejected the spec, or compilation failed.
    """
    if not (PROMPT_FORGE_ROOT / "internals").is_dir():
        raise FileNotFoundError(
            f"prompt-forge skill not found at {PROMPT_FORGE_ROOT}; "
            "run scripts/install.ps1 to sync"
        )

    envelope = {"evidence": evidence, "draft": draft, "dialect_id": dialect_id}
    _check_envelope(envelope)

    _ensure_prompt_forge_on_path()

    # Import after sys.path is updated.
    from internals.evidence import normalize_evidence
    from internals.compile import compile as pf_compile

    try:
        evidence_obj = normalize_evidence(evidence or {})
    except ValueError as exc:
        raise RuntimeError(f"prompt-forge rejected evidence: {exc}") from exc

    spec = _draft_to_spec(draft, dialect_id)

    try:
        package = pf_compile(spec, dialect_id, evidence_obj)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"prompt-forge rejected spec: {exc}") from exc

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
            + "; fix draft and re-run"
        )

    return pkg_dict