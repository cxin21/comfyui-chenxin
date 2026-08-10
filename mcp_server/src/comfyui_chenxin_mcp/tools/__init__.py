"""Tool modules. Empty by default.

Each installed skill package provides its own `skill_data.py` that declares
its `get_skill_data` entry-point (see registry.discover_skills()). The MCP
server discovers and calls them - no tools are registered by
comfyui-chenxin-mcp itself.
"""