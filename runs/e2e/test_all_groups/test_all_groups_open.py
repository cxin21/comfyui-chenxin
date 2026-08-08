"""Test: cp source UI workflow -> enable ALL G1/G2 groups -> upload to ComfyUI.

Per user instruction "先复制一个原工作流然后打开所有的组节点然后MCP传到comfyui上我检查一下".
The local temp file is NOT deleted so the user can inspect it.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path("D:/Projects/comfyui-chenxin")
sys.path.insert(0, str(ROOT / "skills/character-video-pipeline"))

from runtime.mcp_client import McpClient
from runtime.source_workflow import _load_source_ui, _load_groups, _apply_modes_to_ui, SOURCE_WORKFLOW_PATH


def main() -> None:
    # Step 1: copy source UI workflow to local temp file (user's "复制" requirement)
    fd, temp_path = tempfile.mkstemp(prefix="temp_", suffix=".json", dir=tempfile.gettempdir())
    os.close(fd)
    shutil.copyfile(SOURCE_WORKFLOW_PATH, temp_path)
    print(f"[1] copied source -> {temp_path}")

    # Read the copy into memory
    with open(temp_path, encoding="utf-8") as f:
        ui = json.load(f)

    # Step 2: load groups metadata
    groups_meta = _load_groups("t2i-camera")
    print(f"[2] loaded groups: {len(groups_meta['g1'])} G1 + {len(groups_meta['g2'])} G2")

    # Step 3: enable only the user's selected groups
    selected_g1 = [
        "第二轮采样器（G1）",
        "高清 PreDetailer（G1）",
        "高清 PostDetailer（G1）",
    ]
    selected_g2: list[str] = []
    print(f"[3] enabling {len(selected_g1)} G1 + {len(selected_g2)} G2 (only second-pass sampler + hi-res Pre/Post)")
    _apply_modes_to_ui(ui, set(selected_g1), set(selected_g2), groups_meta)

    # Persist modified copy
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(ui, f, ensure_ascii=False)

    # Step 4: launch subprocess MCP and upload
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        print("[!] npx not found; aborting", file=sys.stderr)
        sys.exit(2)
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")

    temp_filename = os.path.basename(temp_path)
    with McpClient.from_subprocess(
        npx, ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url], timeout=600.0
    ) as mcp:
        # Upload temp file
        result = mcp.save_workflow(temp_filename, ui)
        print(f"[4] uploaded: filename={temp_filename} | save_workflow result={result}")

        # Pull back as API JSON to verify it round-trips
        api = mcp.get_workflow(filename=temp_filename, format="api")
        print(f"[5] get_workflow format=api returned {len(api)} nodes")
        with open(SOURCE_WORKFLOW_PATH, encoding="utf-8") as f:
            source_ui = json.load(f)
        src_bypassed = [n["id"] for n in source_ui["nodes"] if n.get("mode") == 4]
        api_present = set(int(k) for k in api.keys())
        newly_active = [nid for nid in src_bypassed if nid in api_present]
        still_absent = [nid for nid in src_bypassed if nid not in api_present]
        print(f"[6] previously-bypassed source nodes: {sorted(src_bypassed)}")
        print(f"    now in API graph (active after enable): {sorted(newly_active)}")
        print(f"    still absent: {sorted(still_absent)}")

        # Show which groups the selected nodes belong to
        from collections import defaultdict
        active_group_map: dict[str, list[int]] = defaultdict(list)
        for grp_title, members in groups_meta["g1"].items():
            if grp_title in selected_g1:
                active_group_map[grp_title] = members
        for grp_title, members in groups_meta["g2"].items():
            if grp_title in selected_g2:
                active_group_map[grp_title] = members
        print(f"[7] selected groups -> node ids:")
        for grp_title, members in active_group_map.items():
            print(f"    {grp_title}: {members}")

    print(f"\n[!] LOCAL TEMP FILE PRESERVED FOR INSPECTION: {temp_path}")
    print(f"[!] ComfyUI user library file: {temp_filename}")


if __name__ == "__main__":
    main()