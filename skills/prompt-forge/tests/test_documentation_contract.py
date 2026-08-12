from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOCUMENTS = (
    ROOT / "skills" / "prompt-forge" / "SKILL.md",
    ROOT / "skills" / "prompt-forge" / "references" / "anima.md",
    ROOT / "skills" / "prompt-forge" / "references" / "minimax-h3.md",
    ROOT / "skills" / "prompt-forge" / "references" / "artifact-and-budgets.md",
    ROOT / "skills" / "camera-image" / "SKILL.md",
    ROOT / "skills" / "camera-video" / "SKILL.md",
    ROOT / "docs" / "camera-image-flow.md",
    ROOT / "docs" / "camera-video-flow.md",
    ROOT / "docs" / "MCP_BRIDGE.md",
    ROOT / "docs" / "architecture.md",
)


def test_documentation_has_one_greenfield_prompt_contract() -> None:
    for path in DOCUMENTS:
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "prompt_artifact" in text or path.name in {
            "anima.md",
            "minimax-h3.md",
            "artifact-and-budgets.md",
        }
        for forbidden in (
            "ForgeRequest",
            "PromptPackage",
            "profile_id",
            "dialect_id",
            "adapter_manifest",
            "approximate token",
            "estimated token",
            "future model",
            "model registry",
            "checkpoint overlay",
            "LoRA overlay",
        ):
            assert forbidden not in text, f"{path}: {forbidden}"


def test_skill_documents_exactly_three_paths_and_script_boundary() -> None:
    text = (ROOT / "skills" / "prompt-forge" / "SKILL.md").read_text(encoding="utf-8")
    for author in (
        "author_anima_prompt",
        "author_h3_t2va_prompt",
        "author_h3_ref2va_prompt",
    ):
        assert author in text
    assert "scripts do not" in text
    assert "exact offline tokenizer" in text
    assert "protected fact" in text


def test_obsolete_design_and_skill_readme_are_deleted() -> None:
    assert not (ROOT / "skills" / "prompt-forge" / "README.md").exists()
    assert not (ROOT / "docs" / "prompt-forge-v4-refactor-design.md").exists()
