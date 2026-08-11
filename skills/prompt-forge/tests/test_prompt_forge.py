from __future__ import annotations

import pytest

from prompt_forge import ForgeRequest, PromptForgeError, forge_prompt


def test_anima_returns_authored_prompt_without_creative_rewrite() -> None:
    request = ForgeRequest(
        profile_id="anima.miaomiao-harem.anima-1.5",
        operation="t2i",
        positive="masterpiece, best quality, score_7, safe, 1girl, solo, red coat",
        negative="worst quality, low quality, artist name",
    )
    artifact = forge_prompt(request).to_dict()
    assert artifact["prompt"]["positive"] == request.positive
    assert artifact["prompt"]["negative"] == request.negative
    assert artifact["profile_id"] == request.profile_id
    assert artifact["lint"]["passed"] is True


def test_h3_t2va_requires_the_official_three_sections() -> None:
    prompt = (
        "integrated_multimodal_description: [Shot 1] A static shot holds on a room.\n\n"
        "overall_soundscape: Quiet room tone.\n\n"
        "non_diegetic_music: N/A"
    )
    artifact = forge_prompt(ForgeRequest("minimax-h3.base.t2va", "t2va", prompt, duration=5.0))
    assert artifact.lint["passed"] is True


def test_h3_ref2va_rejects_unstructured_chinese_scene_brief() -> None:
    with pytest.raises(PromptForgeError, match="prompt lint failed"):
        forge_prompt(
            ForgeRequest(
                "minimax-h3.base.ref2va",
                "ref2va",
                "生成一段人物在街上走路的视频。",
                reference_count=1,
            )
        )


def test_h3_never_accepts_negative_prompt() -> None:
    prompt = (
        "integrated_multimodal_description: [Shot 1] A static shot holds on a room.\n\n"
        "overall_soundscape: Quiet room tone.\n\n"
        "non_diegetic_music: N/A"
    )
    with pytest.raises(PromptForgeError, match="does not accept a negative prompt"):
        forge_prompt(ForgeRequest("minimax-h3.base.t2va", "t2va", prompt, negative="blurry"))
