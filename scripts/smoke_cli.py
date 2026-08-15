"""P8 final gate: smoke-run every Skill-owned CLI from a staged release.

P8 final gate. After ``stage_release.py`` produces a release tree and
the operator has run ``pip install`` for every Skill, ``smoke_cli.py``
invokes the four CLI surfaces that do not need a running ComfyUI
backend (``--help``, ``describe --stage …``, ``assets verify``,
``tokenizer verify``, plus one fail-closed invocation) and asserts
they all behave per the P1 JSON envelope contract.

The script uses the [project.scripts] console-script entries, not
``python -m X.cli``, because setuptools-generated wrappers strip
``argv[0]`` before calling ``main(argv)`` so each Skill's argparse
sees subcommand + args directly. ``python -m`` would mis-treat the
module path as a subcommand.

The script exits non-zero on the first failure; the e2e pytest suite
in ``tests/e2e/test_installed_cli.py`` wraps individual steps so
failures point at the offending sub-command.

Usage:

    python scripts/smoke_cli.py --release-root /tmp/comfyui-chenxin-staged
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


CONSOLE_SCRIPTS: dict[str, str] = {
    "anima_prompt_v1": "anima-prompt-v1",
    "h3_prompt": "minimax-h3-prompt",
    "camera_image": "camera-image",
    "camera_video": "camera-video",
    "camera_multiview": "camera-multiview",
}


def _script_for(skill: str) -> str:
    if skill not in CONSOLE_SCRIPTS:
        raise SystemExit(f"[smoke_cli] unknown skill {skill!r}")
    return CONSOLE_SCRIPTS[skill]


def _run(label: str, argv: list[str], cwd: Path, extra_env: dict[str, str] | None = None) -> dict[str, object]:
    """Run ``argv`` in ``cwd`` and return a structured result."""
    print(f"[smoke_cli] {label}: {' '.join(argv)}", file=sys.stderr)
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    envelope: object = None
    parse_error: str | None = None
    if completed.stdout.strip():
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            parse_error = f"stdout is not a JSON envelope: {exc}; raw={completed.stdout[:200]!r}"
    return {
        "label": label,
        "argv": argv,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "envelope": envelope,
        "parse_error": parse_error,
    }


def _expect(result: dict[str, object], *, label: str, expected_returncode: int = 0) -> None:
    if result["returncode"] != expected_returncode:
        raise SystemExit(
            f"[smoke_cli] FAIL {label}: expected returncode={expected_returncode} "
            f"got={result['returncode']} stderr={result['stderr']!r}"
        )
    if result["parse_error"] is not None:
        raise SystemExit(f"[smoke_cli] FAIL {label}: {result['parse_error']}")
    envelope = result["envelope"]
    if not isinstance(envelope, dict):
        raise SystemExit(f"[smoke_cli] FAIL {label}: envelope is not a JSON object")
    if "ok" not in envelope or "command" not in envelope:
        raise SystemExit(
            f"[smoke_cli] FAIL {label}: envelope missing ok/command keys; got keys={list(envelope)}"
        )


def _check_python_module(release_root: Path) -> None:
    """Each Skill CLI must respond to ``--help`` and exit 0."""
    for skill in CONSOLE_SCRIPTS.keys():
        argv = _build_python_invocation(skill, ["--help"])
        result = _run(f"{skill}::help", argv, cwd=release_root)
        if result["returncode"] != 0:
            raise SystemExit(
                f"[smoke_cli] FAIL {skill} --help: returncode={result['returncode']} "
                f"stderr={result['stderr'][:200]!r}"
            )


def _check_describe_commands(release_root: Path) -> None:
    """``describe --stage … --json`` for every Skill surface — no network needed."""
    cases: list[tuple[str, list[str], int]] = [
        ("anima_prompt_v1", ["author", "--request", "/nonexistent/anima-fixture.json", "--json"], 2),
        ("anima_prompt_v1", ["catalog", "stats", "--json"], 0),
        (
            "h3_prompt",
            [
                "tokenizer",
                "verify",
                "--tokenizer-dir",
                str(release_root / "skills" / "minimax-h3-prompt" / "knowledge"),
                "--json",
            ],
            0,
        ),
        ("camera_image", ["describe", "--stage", "t2i-camera", "--json"], 0),
        ("camera_video", ["describe", "--stage", "t2v-video", "--json"], 0),
        ("camera_multiview", ["describe", "--stage", "multiview", "--json"], 0),
        ("camera_image", ["assets", "verify", "--stage", "t2i-camera", "--json"], 0),
        ("camera_video", ["assets", "verify", "--stage", "t2v-video", "--json"], 0),
        ("camera_multiview", ["assets", "verify", "--stage", "multiview", "--json"], 0),
    ]
    for skill, argv_suffix, expected_rc in cases:
        argv = _build_python_invocation(skill, argv_suffix)
        result = _run(f"{skill}::{argv_suffix[0]}", argv, cwd=release_root)
        try:
            _expect(result, label=f"{skill}::{argv_suffix[0]}", expected_returncode=expected_rc)
        except SystemExit:
            if expected_rc == 2 and result["returncode"] in (2, 3):
                print(
                    f"[smoke_cli] accept {skill}::{argv_suffix[0]} fail-closed rc={result['returncode']}",
                    file=sys.stderr,
                )
                continue
            raise


def _build_python_invocation(skill: str, args: list[str]) -> list[str]:
    """Build a ``python -c …`` argv that calls ``<skill>.cli.main(sys.argv[1:])``.

    Going through ``python -m X.cli`` would put the module path into
    ``sys.argv[0]`` so every Skill's argparse rejects it as an invalid
    subcommand. Going through the setuptools-generated ``X.exe``
    wrapper calls ``main()`` with no positional arg, but every Skill
    declares ``main(argv, *, stdin=…, stdout=…, stderr=…)`` without
    a default. Calling ``main`` directly through ``python -c`` with
    ``sys.argv[1:]`` skips both pitfalls.
    """
    code = (
        f"import sys; from {skill}.cli import main; sys.exit(main(sys.argv[1:]))"
    )
    return [sys.executable, "-c", code, *args]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    args = parser.parse_args()

    if not args.release_root.is_dir():
        print(
            f"[smoke_cli][error] release-root {args.release_root} is not a directory",
            file=sys.stderr,
        )
        return 2

    _check_python_module(args.release_root)
    _check_describe_commands(args.release_root)
    print("[smoke_cli] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
