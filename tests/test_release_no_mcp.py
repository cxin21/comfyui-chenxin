"""Release-time P7 tests.

These tests pin the post-P7 invariants for the Claude Code install path:

* The legacy ``mcp_server/`` directory does not exist in the source tree.
* The root ``.mcp.json`` and the legacy ``.codex-plugin/`` path do not exist.
* No production file imports ``comfyui_chenxin_mcp``, ``mcp_server``,
  ``McpClient`` or ``McpServer``.
* The installers in ``scripts/`` do not write a ``[mcp_servers.comfyui-mcp]``
  block to a Codex ``config.toml`` (the project ships for Claude Code;
  the legacy Codex path is retired).
* Each Skill declares a ``[project.scripts]`` entry whose target module
  imports cleanly without the MCP package on the import path.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_mcp_server_directory_absent():
    assert not (REPO_ROOT / "mcp_server").exists(), (
        "mcp_server/ must be removed in P7 — Claude Code no longer needs an MCP bridge."
    )


def test_root_mcp_json_absent():
    assert not (REPO_ROOT / ".mcp.json").exists(), (
        ".mcp.json (Codex entry-point manifest) must be removed in P7."
    )


def test_codex_plugin_directory_absent():
    assert not (REPO_ROOT / ".codex-plugin").exists(), (
        ".codex-plugin/ is legacy; Claude Code lives in .claude-plugin/."
    )


def test_no_mcp_imports_in_production_code():
    forbidden = ("comfyui_chenxin_mcp", "mcp_server", "McpClient", "McpServer")
    bad: list[str] = []
    for sub in ("skills", "runtime", "scripts"):
        base = REPO_ROOT / sub
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if path.name.startswith("test_") or "_test" in path.name:
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.lstrip()
                if not (stripped.startswith("import ") or stripped.startswith("from ")):
                    continue
                for token in re.findall(r"[A-Za-z_]\w*", line):
                    if token in forbidden:
                        bad.append(f"{path}: {line.rstrip()}")
    assert not bad, "imports of MCP modules remain:\n" + "\n".join(bad)


def test_install_scripts_do_not_write_codex_mcp_block():
    forbidden_phrase = "[mcp_servers.comfyui-mcp]"
    for script in ("install.ps1", "install.sh"):
        path = REPO_ROOT / "scripts" / script
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert forbidden_phrase not in text, (
            f"{script} still references {forbidden_phrase}; the P7 installer must drop the legacy Codex MCP block."
        )


def test_console_scripts_declare_each_skill():
    skills_root = REPO_ROOT / "skills"
    skills = ("anima-prompt-v1", "minimax-h3-prompt", "camera-image", "camera-video", "camera-multiview")
    for skill in skills:
        config = (skills_root / skill / "pyproject.toml").read_text(encoding="utf-8")
        assert "[project.scripts]" in config, f"{skill} must declare a [project.scripts] entry"


def test_runtime_package_no_mcp_dependency():
    target = REPO_ROOT / "runtime" / "comfyui_http" / "pyproject.toml"
    text = target.read_text(encoding="utf-8")
    assert "comfyui-chenxin-mcp" not in text
    assert "mcp" not in text.lower()


def test_claude_code_plugin_path_intact():
    """Claude Code stays in `.claude-plugin/`; the legacy Codex path is removed."""
    assert (REPO_ROOT / ".claude-plugin").is_dir()
    assert (REPO_ROOT / ".claude-plugin" / "plugin.json").is_file()
    assert (REPO_ROOT / ".claude-plugin" / "marketplace.json").is_file()
