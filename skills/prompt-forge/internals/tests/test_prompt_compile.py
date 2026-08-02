import json
from pathlib import Path
import subprocess

from internals.prompt_compile import compile_payload, compile_prompt


WORKSPACE = Path(__file__).resolve().parents[4]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCRIPT = WORKSPACE / "skills/prompt-forge/internals/prompt_compile.py"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_tag_build_validates_semantic_tags_and_separates_recipe_controls():
    build = compile_prompt(_fixture("anima-intent.json"))
    assert build["ready_to_execute"] is True
    assert build["dialect"] == "tags"
    assert build["recipe_control_tokens"] == ["score_9", "score_8_up"]
    assert "blonde_hair" in build["validated_tags"]
    assert "long_hair" not in build["prompt"]
    assert build["execution"]["performed"] is False


def test_natural_language_draft_must_represent_every_locked_fact():
    intent = _fixture("flux-intent.json")
    bad = compile_prompt(intent, {"prompt": "A neon street photographed at night."})
    assert bad["ready_to_execute"] is False
    assert any("locked facts" in error for error in bad["errors"])

    good_prompt = (
        "A female mage stands in a neon night street, rendered as cyberpunk cinematic "
        "photography with neon reflections and cinematic rim light."
    )
    good = compile_prompt(intent, {"prompt": good_prompt})
    assert good["ready_to_execute"] is True


def test_video_build_requires_motion_and_camera_contract():
    build = compile_prompt(_fixture("wan-video-intent.json"))
    assert build["ready_to_execute"] is True
    assert build["target"] == "video"
    assert build["dialect"] == "video-timeline"
    assert "the camera slowly dollies forward" in build["prompt"]
    assert build["negative_prompt"] == "jittery motion, morphing, watermark"
    assert build["execution"]["tool"] is None
    assert build["execution"]["capability"] == "video-generation"
    assert build["execution"]["performed"] is False


def test_compile_mode_never_performs_generation():
    intent = _fixture("anima-intent.json")
    intent["mode"] = "execute"
    build = compile_prompt(intent)
    assert build["execution"] == {
        "mode": "execute",
        "requested": True,
        "performed": False,
        "tool": None,
        "capability": "image-generation",
    }


def test_compile_payload_accepts_intent_and_draft_envelope():
    intent = _fixture("flux-intent.json")
    prompt = (
        "A female mage stands in a neon night street, rendered as cyberpunk cinematic "
        "photography with neon reflections and cinematic rim light."
    )
    build = compile_payload({"intent": intent, "draft": {"prompt": prompt}})
    assert build["prompt"] == prompt
    assert build["ready_to_execute"] is True


def test_recipe_modality_mismatch_is_a_hard_stop():
    intent = _fixture("flux-intent.json")
    intent["target"] = "video"
    intent["generation_mode"] = "text-to-video"
    build = compile_prompt(intent)
    assert build["ready_to_execute"] is False
    assert any("modality" in error for error in build["errors"])


def test_unsupported_negative_is_withheld():
    intent = _fixture("flux-intent.json")
    intent["negative_constraints"] = ["watermark"]
    build = compile_prompt(intent)
    assert build["negative_prompt"] == ""
    assert any("negative prompt withheld" in warning for warning in build["warnings"])


def test_unresolved_source_without_explicit_representation_is_a_hard_stop():
    intent = _fixture("flux-intent.json")
    intent["original_query"] = "未知机械生命体"
    intent["locked_facts"] = []
    for dimension in intent["dimensions"]:
        intent["dimensions"][dimension] = []
    intent["dimensions"]["style"] = [{"value": "cinematic photography", "origin": "recipe"}]
    build = compile_prompt(intent)
    assert build["ready_to_execute"] is False
    assert any("unresolved" in error for error in build["errors"])


def test_cli_accepts_raw_intent_and_emits_prompt_build():
    result = subprocess.run(
        ["python", str(SCRIPT), "--input", str(FIXTURES / "wan-video-intent.json")],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1.0"
    assert payload["ready_to_execute"] is True
