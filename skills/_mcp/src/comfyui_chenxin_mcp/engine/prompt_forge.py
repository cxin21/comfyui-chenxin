"""Bridge to prompt-forge skill.

Enforces the project rule: ALL prompt text for every character-video-pipeline
stage must be authored through prompt-forge before reaching a ComfyUI submit.

Boundary (from prompt-forge prompt_package._BAD):
- The compile envelope (evidence / draft / dialect) MUST NOT carry any of:
    workflow, node, hash, gpu, execution, mode, runtime, profile, camera,
    lens, lora, loras, checkpoint, sampler, seed, steps, cfg, denoise.
- Camera / LoRA / sampler / cfg / steps / seed stay in character-video-pipeline;
  prompt-forge only owns the prompt text (positive, negative).

Flow:
1. Caller supplies a draft (positive, negative) already authored by Claude.
2. Caller supplies an evidence ledger (locked_facts, continuity_locks, ...).
3. Bridge invokes prompt-forge internals.prompt_compile (subprocess, stdin JSON).
4. Returns PromptPackage. Refuses to continue if quality.ready_for_review is false.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

# Path to prompt-forge skill root (sibling skill directory).
PROMPT_FORGE_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent / "prompt-forge"

# Fields forbidden inside prompt-forge envelopes (mirrors prompt_package._BAD).
# Belt-and-suspenders: enforce here too so we don't ship evidence that would
# later be rejected by prompt-forge.
_FORBIDDEN_IN_ENVELOPE = frozenset({
    "workflow", "node", "hash", "gpu", "execution", "mode", "runtime",
    "profile", "camera", "lens", "lora", "loras", "checkpoint", "sampler",
    "seed", "steps", "cfg", "denoise",
})


def _check_envelope(envelope: dict) -> None:
    """Reject any envelope that carries execution-only fields.

    prompt-forge also enforces this (see _reject in prompt_package.py) but we
    want a clear, local error before subprocess spawn.
    """
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
            + " - those belong to character-video-pipeline"
        )


def _resolve_python() -> str:
    """Python interpreter that can import prompt-forge internals."""
    return sys.executable or shutil.which("python") or "python"


def compile_envelope(
    evidence: dict,
    draft: dict,
    dialect_id: str = "anima",
    *,
    timeout: float = 60.0,
) -> dict:
    """Run prompt-forge internals.prompt_compile on the supplied envelope.

    Args:
        evidence: CreativeEvidence ledger (no execution fields).
        draft: caller-authored prompt fields (positive, negative for image).
        dialect_id: prompt-forge dialect id (default "anima").
        timeout: subprocess timeout in seconds.

    Returns:
        PromptPackage dict with quality flags. Refuses (raises) if
        quality.ready_for_review is False or quality.errors is non-empty.

    Raises:
        FileNotFoundError: prompt-forge skill not installed.
        RuntimeError: prompt-forge rejected the draft, or subprocess failed.
        ValueError: envelope violated boundary (forbidden fields detected locally).
    """
    if not (PROMPT_FORGE_ROOT / "internals" / "prompt_compile.py").exists():
        raise FileNotFoundError(
            f"prompt-forge skill not found at {PROMPT_FORGE_ROOT}; "
            "run scripts/install.ps1 to sync"
        )

    envelope = {"evidence": evidence, "draft": draft, "dialect_id": dialect_id}
    _check_envelope(envelope)

    payload = json.dumps(envelope, ensure_ascii=False)
    py = _resolve_python()
    cmd = [py, "-m", "internals.prompt_compile", "--stdin"]

    proc = subprocess.run(
        cmd,
        input=payload,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROMPT_FORGE_ROOT),
    )

    if proc.returncode == 2 and proc.stderr:
        # compile_payload raised ValueError - invalid envelope
        try:
            err_obj = json.loads(proc.stderr.strip())
            raise RuntimeError(f"prompt-forge rejected envelope: {err_obj.get('error', proc.stderr)}")
        except json.JSONDecodeError:
            raise RuntimeError(f"prompt-forge rejected envelope: {proc.stderr.strip()}")
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"prompt-forge subprocess failed (rc={proc.returncode}): "
            f"stderr={proc.stderr.strip()}"
        )

    try:
        package = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"prompt-forge returned non-JSON output: {proc.stdout[:500]}") from exc

    quality = package.get("quality", {})
    errors = package.get("errors", []) or []

    if errors:
        raise RuntimeError(
            "prompt-forge flagged errors in prompt draft: " + "; ".join(errors)
        )
    if not quality.get("ready_for_review", False):
        reasons: list[str] = []
        for key in (
            "facts_preserved",
            "no_unsupported_invention",
            "style_coherent",
            "dialect_valid",
            "temporal_logic_valid",
        ):
            if not quality.get(key, True):
                reasons.append(f"{key}=false")
        raise RuntimeError(
            "prompt-forge marked prompt not ready_for_review: "
            + ", ".join(reasons)
            + "; fix draft and re-run"
        )

    return package


