from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = REPO_ROOT / "skills"
PROMPT_SKILL = SKILLS_ROOT / "prompt-forge" / "SKILL.md"
PIPELINE_SKILL = SKILLS_ROOT / "character-video-pipeline" / "SKILL.md"
DEPRECATED = (
    "ffmpeg-pipeline",
    "lora-trainer",
    "manga-orchestrator",
    "manga-stage-2-panels",
    "manga-stage-3-review",
    "manga-stage-4-motion",
)


def _frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"(?s)^---\s*(.*?)\s*---\s*(.*)$", text)
    assert match, f"missing frontmatter: {path}"
    values = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values, match.group(2)


def test_exact_active_skill_set():
    active = []
    for skill_file in SKILLS_ROOT.glob("*/SKILL.md"):
        values, _ = _frontmatter(skill_file)
        if values.get("status") == "active":
            active.append(skill_file.relative_to(REPO_ROOT).as_posix())
    assert sorted(active) == [
        "skills/character-video-pipeline/SKILL.md",
        "skills/prompt-forge/SKILL.md",
    ]


def test_prompt_forge_is_pure_compiler():
    values, body = _frontmatter(PROMPT_SKILL)
    assert values["status"] == "active"
    assert values["side_effects"] == "none"
    assert values["owner"] == "prompt-compiler"
    assert "MCP" not in body
    assert "ComfyUI" not in body
    assert "enqueue" not in body
    assert "RunRecord" not in body


def test_pipeline_owns_execution_boundary():
    values, body = _frontmatter(PIPELINE_SKILL)
    assert values["status"] == "active"
    assert values["side_effects"] == "approval-gated-local-comfyui"
    assert values["owner"] == "character-video-pipeline"
    assert "MCP" in body
    assert "approval" in body
    assert "RunRecord" in body
    assert (PIPELINE_SKILL.parent / "runtime").is_dir()


def test_deprecated_skill_directories_are_absent():
    for name in DEPRECATED:
        assert not (SKILLS_ROOT / name).exists(), name