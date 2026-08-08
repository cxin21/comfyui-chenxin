"""comfyui-chenxin-mcp stdio server entrypoint.

Called by `comfyui-chenxin-mcp-server` console script (pyproject.toml).
Boots: protocol server + entry-point discovery + workflow_dir scan.

No hardcoded skill names. Skills declare themselves via Python entry-points
(see registry.discover()).
"""
from __future__ import annotations

import asyncio

from .protocol import Server
from .registry import discover as _discover_skills


def main() -> None:
    server = Server(name="comfyui-chenxin-mcp", version="0.1.0")
    skills = _discover_skills()
    if not skills:
        # Empty registry is a valid state (no skill packages installed yet);
        # server still serves list_skills / describe_skill (returns empty).
        pass
    for skill in skills:
        skill.register_fn(server)
    asyncio.run(server.serve_stdio())


if __name__ == "__main__":
    main()