"""Verify the source tree (or staged release) contains the P8 surface.

P8 final gate. Replaces the P7-era REQUIRED list (which still
referenced ``mcp_server``) with the post-P7 list:

* Every Skill directory carries SKILL.md + pyproject.toml + cli.py
  + runtime/types.py + cli_protocol.py + tests/.
* runtime/comfyui_http is shipped as a normal Python package.
* .claude-plugin/ declares the Claude Code marketplace manifest.
* tests/cli_protocol and tests/test_release_no_mcp.py cover the
  Skill-owned CLI / no-MCP invariants.

Run against the source tree:

    python scripts/verify_release.py --source-root .

Run against a previously staged release (e.g. produced by
``scripts/stage_release.py``):

    python scripts/verify_release.py --source-root . --cache-root /tmp/release
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REQUIRED: tuple[str, ...] = (
    "skills/anima-prompt-v1/SKILL.md",
    "skills/anima-prompt-v1/pyproject.toml",
    "skills/anima-prompt-v1/anima_prompt_v1/__init__.py",
    "skills/anima-prompt-v1/anima_prompt_v1/cli.py",
    "skills/anima-prompt-v1/anima_prompt_v1/cli_protocol.py",
    "skills/anima-prompt-v1/scripts/search_catalog.py",
    "skills/anima-prompt-v1/scripts/submit_relations.py",
    "skills/minimax-h3-prompt/SKILL.md",
    "skills/minimax-h3-prompt/pyproject.toml",
    "skills/minimax-h3-prompt/h3_prompt/__init__.py",
    "skills/minimax-h3-prompt/h3_prompt/cli.py",
    "skills/minimax-h3-prompt/h3_prompt/cli_protocol.py",
    "skills/camera-image/SKILL.md",
    "skills/camera-image/pyproject.toml",
    "skills/camera-image/camera_image/__init__.py",
    "skills/camera-image/camera_image/cli.py",
    "skills/camera-image/camera_image/cli_protocol.py",
    "skills/camera-image/camera_image/runtime/__init__.py",
    "skills/camera-multiview/SKILL.md",
    "skills/camera-multiview/pyproject.toml",
    "skills/camera-multiview/camera_multiview/__init__.py",
    "skills/camera-multiview/camera_multiview/cli.py",
    "skills/camera-multiview/camera_multiview/cli_protocol.py",
    "skills/camera-multiview/camera_multiview/runtime/__init__.py",
    "skills/camera-video/SKILL.md",
    "skills/camera-video/pyproject.toml",
    "skills/camera-video/camera_video/__init__.py",
    "skills/camera-video/camera_video/cli.py",
    "skills/camera-video/camera_video/cli_protocol.py",
    "skills/camera-video/camera_video/runtime/__init__.py",
    "runtime/comfyui_http/pyproject.toml",
    "runtime/comfyui_http/comfyui_http/__init__.py",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "tests/cli_protocol/test_protocol_examples.py",
    "tests/test_release_no_mcp.py",
    "scripts/install.sh",
    "scripts/install.ps1",
    "scripts/stage_release.py",
    "scripts/verify_release.py",
    "scripts/smoke_cli.py",
    "README.md",
    "LICENSE",
)

# These resource IDs MUST NOT appear in the release surface; their
# presence is a P7 regression.
FORBIDDEN: tuple[str, ...] = (
    "mcp_server",
    ".mcp.json",
    ".codex-plugin",
)


def _check_root(root: Path) -> list[str]:
    if not root.is_dir():
        return [f"{root} is not a directory"]
    missing = [path for path in REQUIRED if not (root / path).is_file()]
    return missing


def _check_forbidden(root: Path) -> list[str]:
    leaked = [name for name in FORBIDDEN if (root / name).exists()]
    return leaked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    args = parser.parse_args()

    exit_code = 0
    for label, root in (("source", args.source_root), ("cache", args.cache_root)):
        if root is None:
            continue
        missing = _check_root(root)
        leaked = _check_forbidden(root)
        if missing:
            print(
                f"[verify_release][error] {label} root {root} is missing: {missing}",
                file=sys.stderr,
            )
            exit_code = 1
        if leaked:
            print(
                f"[verify_release][error] {label} root {root} still carries legacy paths: {leaked}",
                file=sys.stderr,
            )
            exit_code = 1
    if exit_code == 0:
        print("[verify_release] OK")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
