"""P8 final-gate e2e: stage a release locally and prove it survives
``scripts/smoke_cli.py`` + ``scripts/verify_release.py`` end to end.

These tests are deliberately **end-to-end**: each one stages a fresh
directory under ``$TEMP``, installs every Skill + the
``comfyui-http-runtime`` transport from the staged tree, and then
runs the staged smoke gate. Slow on purpose; gated to run once per
CI matrix.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_DIRS: tuple[tuple[Path, str], ...] = (
    (REPO_ROOT / "runtime" / "comfyui_http", "comfyui-http-runtime"),
    (REPO_ROOT / "skills" / "anima-prompt-v1", "anima-prompt-v1"),
    (REPO_ROOT / "skills" / "minimax-h3-prompt", "minimax-h3-prompt"),
    (REPO_ROOT / "skills" / "camera-image", "camera-image"),
    (REPO_ROOT / "skills" / "camera-video", "camera-video"),
    (REPO_ROOT / "skills" / "camera-multiview", "camera-multiview"),
)


def _venv_python() -> str:
    candidate = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if candidate.is_file():
        return str(candidate)
    return sys.executable


def _run(argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy() if env is None else {**os.environ, **env}
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else None,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.fixture(scope="module")
def staged_release(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Stage a fresh release under tempdir, install every Skill, smoke-run them."""
    base = tmp_path_factory.mktemp("p8-staged")
    release_root = base / "release"

    stage = _run(
        [
            _venv_python(),
            str(REPO_ROOT / "scripts" / "stage_release.py"),
            "--source-root",
            str(REPO_ROOT),
            "--destination-root",
            str(release_root),
        ]
    )
    assert stage.returncode == 0, stage.stderr

    for pkg_dir, name in PYPROJECT_DIRS:
        install = _run(
            [_venv_python(), "-m", "pip", "install", "-e", str(pkg_dir), "--quiet"],
            cwd=base,
        )
        assert install.returncode == 0, f"pip install {name} failed: {install.stderr}"

    return release_root


def test_release_verifies_against_source_tree() -> None:
    verify = _run(
        [_venv_python(), str(REPO_ROOT / "scripts" / "verify_release.py"), "--source-root", str(REPO_ROOT)]
    )
    assert verify.returncode == 0, verify.stderr
    assert "OK" in verify.stdout


def test_release_verifies_against_staged_cache(staged_release: Path) -> None:
    verify = _run(
        [
            _venv_python(),
            str(REPO_ROOT / "scripts" / "verify_release.py"),
            "--source-root",
            str(REPO_ROOT),
            "--cache-root",
            str(staged_release),
        ]
    )
    assert verify.returncode == 0, verify.stderr


def test_smoke_cli_passes_against_staged_release(staged_release: Path) -> None:
    smoke = _run(
        [
            _venv_python(),
            str(REPO_ROOT / "scripts" / "smoke_cli.py"),
            "--release-root",
            str(staged_release),
        ]
    )
    assert smoke.returncode == 0, smoke.stdout + "\n" + smoke.stderr
    assert "[smoke_cli] OK" in smoke.stdout


def test_legacy_paths_absent_from_staged_release(staged_release: Path) -> None:
    """P7 invariant: mcp_server/, .mcp.json, .codex-plugin/ must not appear."""
    for name in ("mcp_server", ".mcp.json", ".codex-plugin"):
        assert not (staged_release / name).exists(), f"legacy path leaked: {name}"
