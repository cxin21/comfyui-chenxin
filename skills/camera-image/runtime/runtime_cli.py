"""Thin CLI for camera-image runtime inspection.

Read-only inspection commands: `describe-config` and `list-loras`.
Image generation is handled by the v2 engine (comfyui_chenxin_mcp.engine.execute),
not by this CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from .config_schema import STAGES
from .graph_patcher import describe_config
from .lora_resolver import (
    default_lora_plan,
    filter_anima_loras,
    parse_lora_inventory,
    render_stack_text,
)


def _resolve_mcp_launch() -> tuple[str, list[str]]:
    cmd = os.environ.get("CHENXIN_MCP_CMD")
    args_str = os.environ.get("CHENXIN_MCP_ARGS")
    if cmd and args_str:
        try:
            return cmd, json.loads(args_str)
        except json.JSONDecodeError:
            pass
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH; install Node.js or set CHENXIN_MCP_CMD/CHENXIN_MCP_ARGS")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    return npx, ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url]


def cmd_describe_config(args):
    config = describe_config(args.stage)
    print(json.dumps(config, ensure_ascii=False, indent=2))
    return 0


def cmd_list_loras(args):
    from .mcp_client import McpClient
    command, server_args = _resolve_mcp_launch()
    with McpClient.from_subprocess(command, server_args, timeout=60.0) as mcp:
        raw = mcp.list_loras()
    inventory = parse_lora_inventory(raw)
    anima = filter_anima_loras(inventory)
    print(f"Available Anima LoRAs ({len(anima)}):")
    for name in anima:
        print(f"  {name}")
    print(f"\nDefault stack: {render_stack_text(default_lora_plan())}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="camera-image-runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    p_dc = sub.add_parser("describe-config", help="show all configurable slots (workflow-bound)")
    p_dc.add_argument("--stage", default=STAGES.T2I, choices=[STAGES.T2I, STAGES.I2I])
    p_dc.set_defaults(func=cmd_describe_config)

    p_ll = sub.add_parser("list-loras", help="list available Anima LoRAs (read-only)")
    p_ll.set_defaults(func=cmd_list_loras)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
