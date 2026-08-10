"""Entry point for `python -m comfyui_chenxin_mcp`.

Allows plugin loaders to spawn the server via the Python interpreter
alone, without depending on a PATH-resident `comfyui-chenxin-mcp-server`
executable.
"""
from .server import main


if __name__ == "__main__":
    main()