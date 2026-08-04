from pathlib import Path
import re


SKILL_ROOT = Path(__file__).parents[1].parent
LEGACY_SKILLS = (
    "manga-orchestrator",
    "manga-stage-2-panels",
    "manga-stage-3-review",
    "manga-stage-4-motion",
    "lora-trainer",
    "ffmpeg-pipeline",
)


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"missing frontmatter: {path}"
    return match.group(1)


def test_prompt_forge_is_the_only_active_skill_boundary():
    active = _frontmatter(SKILL_ROOT / "SKILL.md")
    assert re.search(r"^status:\s*active\s*$", active, re.MULTILINE)

    for name in LEGACY_SKILLS:
        frontmatter = _frontmatter(SKILL_ROOT.parent / name / "SKILL.md")
        assert re.search(r"^status:\s*legacy\s*$", frontmatter, re.MULTILINE)
        assert re.search(r"^triggers:\s*\[\]\s*$", frontmatter, re.MULTILINE)

    assert not (SKILL_ROOT.parent / "manga-stage-1-lora" / "SKILL.md").exists()