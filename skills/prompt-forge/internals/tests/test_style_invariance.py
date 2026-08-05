import copy
import re
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
DOCS = [
    SKILL_DIR / "aesthetics/INDEX.md",
    SKILL_DIR / "aesthetics/style-presets.md",
    SKILL_DIR / "aesthetics/medium-glossary.md",
    SKILL_DIR / "aesthetics/motion-glossary.md",
    SKILL_DIR / "references/image-dialects.md",
    SKILL_DIR / "references/video-dialects.md",
    SKILL_DIR / "references/prompt-contracts.md",
    SKILL_DIR / "references/creative-evidence.md",
]


def _text(path):
    return path.read_text(encoding="utf-8")


def _field_list(text, name):
    match = re.search(rf"^{name}:\s*(.+)$", text, re.MULTILINE)
    assert match, f"missing {name} declaration"
    return [item.strip() for item in match.group(1).split(",")]


def _apply_style(evidence, style):
    return {"evidence": copy.deepcopy(evidence), "visual_language": copy.deepcopy(style)}


def test_guidance_is_prompt_language_only_and_contains_no_system_claims():
    assert all(path.exists() for path in DOCS)
    combined = "\n".join(_text(path) for path in DOCS)
    banned = (
        r"\bComfyUI\b", r"\bMCP\b", r"\bGPU\b", r"\bworkflow\b",
        r"\bnode\b", r"\bhash(?:es)?\b", r"\bexecution\b",
        r"model[- ]install", r"瀹夎妯″瀷",
    )
    for pattern in banned:
        assert re.search(pattern, combined, re.IGNORECASE) is None, pattern


def test_guidance_has_no_random_injection_or_hard_percentage_rules():
    combined = "\n".join(_text(path) for path in DOCS)
    banned = (
        r"\brandom(?:ly)?\b", r"闅忔満", r"50\s*%", r"25\s*%",
        r"token.{0,24}(?:position|浣嶇疆)", r"silent.{0,20}inject", r"闈欓粯.{0,10}娉ㄥ叆",
    )
    for pattern in banned:
        assert re.search(pattern, combined, re.IGNORECASE) is None, pattern


def test_creative_evidence_uses_conditional_mapping_without_source_attribution():
    text = _text(SKILL_DIR / "references/creative-evidence.md")
    for source in ("前期剧情拆解模板.md", "提示词公开版本.txt", "影视资产.md"):
        assert source in text
    for phrase in (
        "may populate", "when provided",
        "no content is inferred or attributed without a supplied excerpt",
        "potential destination fields",
    ):
        assert phrase in text.casefold()
    for field in (
        "identity", "plot_facts", "props", "continuity_locks", "art_direction",
        "character_assets", "environment_assets", "prop_assets", "shot_plan",
        "dialogue", "uncertainty", "source_id", "source_section", "source_text",
    ):
        assert field in text
    assert "field-level synthesis" in text
    assert "jade-hilt sword" not in text
    assert "source_quote_summary" not in text
    assert "evidence extracted" not in text.casefold()

def test_style_variants_preserve_evidence_and_only_visual_language_differs():
    policy = _text(SKILL_DIR / "references/creative-evidence.md")
    protected = _field_list(policy, "protected_fields")
    style_fields = _field_list(policy, "style_fields")
    assert protected == ["identity", "plot_facts", "props", "continuity_locks"]
    assert style_fields == [
        "medium", "palette", "lighting", "texture", "camera_feel", "motion_quality"
    ]
    evidence = {
        "identity": ["red-robed swordswoman", "scar over left eyebrow"],
        "plot_facts": ["draws the same sword after the warning"],
        "props": ["jade-hilt sword"],
        "continuity_locks": ["red robe", "same sword", "rain continues"],
    }
    ink = {"medium": "ink wash", "palette": "charcoal and vermilion", "lighting": "soft rain haze"}
    noir = {"medium": "cinematic photography", "palette": "cool cyan and red", "lighting": "hard rim light"}
    first, second = _apply_style(evidence, ink), _apply_style(evidence, noir)
    for field in protected:
        assert first["evidence"][field] == second["evidence"][field] == evidence[field]
    assert first["visual_language"] != second["visual_language"]
    assert set(first["visual_language"]).issubset(style_fields)
    assert set(second["visual_language"]).issubset(style_fields)