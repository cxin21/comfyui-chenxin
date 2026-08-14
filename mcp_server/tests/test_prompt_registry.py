from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for skill_root in (ROOT / "skills" / "anima-prompt-v1", ROOT / "skills" / "minimax-h3-prompt"):
    if str(skill_root) not in sys.path:
        sys.path.insert(0, str(skill_root))

from anima_prompt_v1.mcp import get_prompt_skill as get_anima_prompt_skill
from h3_prompt.mcp import get_prompt_skill as get_h3_prompt_skill


def test_anima_prompt_adapter_returns_camera_compatible_prompt() -> None:
    skill = get_anima_prompt_skill()

    result = skill["author_fn"](
        "author",
        {
            "facts": [
                {
                    "fact_id": "fact:hair",
                    "value": "long_hair",
                    "domain": "hair",
                    "kind": "explicit",
                    "source": "user",
                    "representation_hint": "tag",
                }
            ],
            "subjects": [{"subject_id": "subject:0", "label": "woman"}],
        },
    )

    assert set(result["prompt"]) == {"positive", "negative"}
    assert "long_hair" in result["prompt"]["positive"]
    assert isinstance(result["advisories"], list)


def test_h3_prompt_adapter_returns_text_prompt_and_findings() -> None:
    skill = get_h3_prompt_skill()

    result = skill["author_fn"](
        "t2va",
        {
            "facts": [
                {
                    "fact_id": "fact:action",
                    "value": "the ball rolls and stops",
                    "origin": "user_explicit",
                    "locked": True,
                    "owner": "scene",
                    "dimension": "action_result",
                }
            ],
            "duration_seconds": 5,
            "shot_count": 1,
            "integrated_multimodal_description": [
                {
                    "segment_id": "segment:shot-1",
                    "field": "integrated_multimodal_description",
                    "text": "[Shot 1] the ball rolls and stops beside the wall.",
                    "fact_ids": ["fact:action"],
                }
            ],
        },
    )

    assert set(result["prompt"]) == {"text"}
    assert result["prompt"]["text"].startswith("integrated_multimodal_description:")
    assert result["findings"] == []


def test_prompt_skill_descriptors_expose_model_and_stages() -> None:
    anima = get_anima_prompt_skill()
    h3 = get_h3_prompt_skill()

    assert anima["name"] == "anima-prompt-v1"
    assert anima["stages"] == ("author",)
    assert h3["name"] == "minimax-h3-prompt"
    assert h3["stages"] == ("t2va", "ref2va")
