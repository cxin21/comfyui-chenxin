"""End-to-end test: run_skill against live ComfyUI; verifies get_history_raw.

This script boots a real McpClient subprocess, enqueues a minimal workflow,
waits via _wait_for_completion (which now hits /history/<id> directly), and
downloads the artifact. Exit code 0 == success.

Per the cleanup, this exercises the new code path:
- McpClient.from_subprocess(..., comfyui_url=...)
- mcp.get_history_raw(prompt_id) -> dict from /history/<id>
- _parse_history -> (entry, "success", "") -> download artifact
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path("D:/Projects/comfyui-chenxin")
sys.path.insert(0, str(ROOT / "skills/_mcp/src"))

from comfyui_chenxin_mcp.engine.mcp_client import McpClient
from comfyui_chenxin_mcp.engine.execute import run_skill
from comfyui_chenxin_mcp.registry import discover_skills


# Minimal workflow: EmptyImage -> SaveImage.
# EmptyImage produces IMAGE directly (no VAE/KSampler dependency, no model
# required), and SaveImage accepts IMAGE. This is the most install-agnostic
# path that exercises both the new get_history_raw poll loop AND the
# artifact download path. If EmptyImage isn't bundled on a given ComfyUI
# version, switch to ImageOnlyCheckpointLoader + EmptyImage.
MINIMAL_GRAPH: dict = {
    "1": {
        "class_type": "EmptyImage",
        "inputs": {"width": 64, "height": 64, "batch_size": 1, "color": 0},
    },
    "2": {
        "class_type": "SaveImage",
        "inputs": {"images": ["1", 0], "filename_prefix": "e2e_history_raw"},
    },
}


async def _async_main() -> int:
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        print("[!] npx not found", file=sys.stderr)
        return 2
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")

    skills = discover_skills()
    if not skills:
        print("[!] no skills installed", file=sys.stderr)
        return 2
    sd = next(s for s in skills if s.name == "camera-image")

    # Build a minimal RunConfig-like object that bypasses prepare_fn
    # so we hit the engine's wait/download path with our minimal graph.
    from dataclasses import dataclass, replace
    from comfyui_chenxin_mcp.engine.execute import _wait_for_completion, _download_artifact
    from comfyui_chenxin_mcp.engine.skill_data import ImageSpec, Rule

    sd_test = type(sd)(
        name=sd.name, stages=sd.stages,
        source_workflow_path=sd.source_workflow_path,
        groups_dir_pattern=sd.groups_dir_pattern,
        field_map=sd.field_map,
        dependency_rules=sd.dependency_rules,
        stage_images={},  # no images to upload for the minimal test
        output_type="images",
        describe_fn=sd.describe_fn,
        apply_fn=lambda graph, stage, config, **kw: None,
        prepare_fn=lambda mcp, stage, groups: MINIMAL_GRAPH,
        build_config_fn=sd.build_config_fn,
    )

    @dataclass(frozen=True)
    class _TestConfig:
        evidence: dict
        draft: dict
        dialect_id: str = "anima"
        camera: object = None
        camera_extra: dict = None
        lora: dict = None
        groups: object = None
        sampling: object = None
        seed: int = None
        image_size: object = None
        reference_image: str = None
        controlnet_image: str = None

    cfg = _TestConfig(
        evidence={},
        draft={"positive": "1girl", "negative": "lowres"},
        dialect_id="anima",
    )

    output_dir = ROOT / "outputs" / "e2e_history_raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    with McpClient.from_subprocess(
        npx,
        ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url],
        timeout=600.0,
        comfyui_url=comfy_url,
    ) as mcp:
        # First verify get_history_raw hits the HTTP endpoint correctly
        # (unrelated prompt_id -> 404 -> empty dict).
        empty = mcp.get_history_raw("nonexistent-prompt-id-xyz")
        print(f"[1] get_history_raw on missing prompt returned: {empty!r}")
        assert empty == {}, f"expected empty dict, got {empty!r}"

        payload, code = run_skill(
            mcp=mcp, skill_data=sd_test, stage="t2i-camera", config=cfg,
            output_dir=output_dir, timeout=120.0, poll_interval=1.0,
        )
    dt = time.monotonic() - t0

    print(f"[2] run_skill exit_code={code}, accepted={payload.get('accepted')}, "
          f"duration={dt:.1f}s")
    if code != 0:
        print(f"[!] error: {payload.get('error')}")
        return 1

    print(f"[3] artifact: {payload['artifact']}")
    print(f"[4] run_record: {payload['run_record_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_async_main()))