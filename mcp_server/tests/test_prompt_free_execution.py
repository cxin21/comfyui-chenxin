from __future__ import annotations

import json
from dataclasses import dataclass

from comfyui_chenxin_mcp.engine.execute import run_skill
from comfyui_chenxin_mcp.engine.skill_data import SkillData


@dataclass(frozen=True)
class PromptFreeConfig:
    groups: None = None
    lora: None = None


class SuccessfulMcp:
    def health(self) -> dict:
        return {"queue": {"running": [], "pending": []}}

    def validate_workflow(self, graph: dict) -> dict:
        return {"valid": True}

    def check_runtime(self, graph: dict) -> dict:
        return {"runtime": "local"}

    def enqueue(self, graph: dict) -> dict:
        return {"prompt_id": "prompt-free"}

    def get_history_raw(self, prompt_id: str) -> dict:
        return {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "1": {
                        "images": [
                            {"filename": "result.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            }
        }

    def get_image(self, filename: str, subfolder: str, image_type: str) -> bytes:
        return b"verified image bytes"


def test_prompt_free_skill_executes_without_a_compatibility_artifact(tmp_path) -> None:
    skill = SkillData(
        name="prompt-free",
        stages=("fixed",),
        source_workflow_path="fixed.json",
        groups_dir_pattern="",
        field_map={},
        dependency_rules=(),
        stage_images={"fixed": ()},
        output_type="images",
        describe_fn=lambda stage: {},
        prepare_fn=lambda mcp, **kwargs: {"1": {"inputs": {}, "class_type": "SaveImage"}},
        build_config_fn=lambda envelope, **tunables: PromptFreeConfig(),
    )

    payload, code = run_skill(
        mcp=SuccessfulMcp(),
        skill_data=skill,
        stage="fixed",
        config=PromptFreeConfig(),
        output_dir=tmp_path,
        poll_interval=0,
    )

    assert code == 0
    assert payload["accepted"] is True
    assert payload["prompt"] is None
    run_record = json.loads(
        next((tmp_path / "runs").glob("fixed_*/run-record.json")).read_text(encoding="utf-8")
    )
    assert run_record["prompt"] is None
