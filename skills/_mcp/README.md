# comfyui-chenxin-mcp

Model Context Protocol (MCP) server for comfyui-chenxin plugin skills, exposing ComfyUI workflows as stdio-transported tools.

## What this package does

This is a stdio MCP 2024-11-05 server that exposes comfyui-chenxin plugin skills (camera-image, camera-multiview, camera-video, etc.) to MCP-compatible hosts like Claude Desktop, Codex, or Codex CLI.

The server automatically discovers any installed skill package that declares the `comfyui_chenxin_mcp.skills` entry-point group — no hardcoded skill names live in this package.

## Install instructions

1. Install the MCP server package:
   ```bash
   pip install -e skills/_mcp
   ```

2. Install the camera-image skill (and any other comfyui-chenxin skills):
   ```bash
   pip install -e skills/camera-image
   ```

## Usage

### Automatic launch (recommended)

The server is automatically launched by your MCP-compatible host via the `.codex-plugin/plugin.json` configuration.

### Manual launch

You can also run the server directly:
```bash
comfyui-chenxin-mcp-server
```

The server speaks JSON-RPC 2.0 over stdin/stdout.

## Tool catalog

The actual tool surface is provided by individual skill packages. The camera-image skill exposes these tools:

### `describe_camera_config(stage)`
Return the full schema (defaults, groups, enums) for a camera stage.

**Parameters**: 
- `stage`: Either `"t2i-camera"` or `"i2i-camera"`

### `validate_camera_config(stage, config)`
Validate a RunConfig dict before running generation.

**Parameters**: 
- `stage`: Either `"t2i-camera"` or `"i2i-camera"`
- `config`: Configuration object to validate

### `list_camera_loras()`
List available Anima LoRA short names.

### `run_t2i_camera(envelope, ...)`
Run text-to-image camera generation.

**Parameters**: 
- `envelope`: Prompt package envelope object
- `stage`: Defaults to `"t2i-camera"`
- `camera`: Camera configuration object
- `camera_extra`: Additional camera parameters
- `lora`: LoRA configuration object
- `groups`: Group controller selections
- `sampling`: Sampling configuration
- `seed`: Random seed (integer)
- `image_size`: Image dimensions
- `controlnet_image`: Optional controlnet input image path
- `output_dir`: Output directory (default: "outputs")

### `run_i2i_camera(envelope, reference, ...)`
Run image-to-image camera generation.

**Parameters**: 
- `envelope`: Prompt package envelope object
- `reference`: Reference image path
- `stage`: Defaults to `"i2i-camera"`
- `camera`: Camera configuration object
- `lora`: LoRA configuration object
- `groups`: Group controller selections
- `sampling`: Sampling configuration
- `seed`: Random seed (integer)
- `image_size`: Image dimensions
- `controlnet_image`: Optional controlnet input image path
- `output_dir`: Output directory (default: "outputs")

## Architecture note

Skills are discovered via Python setuptools entry-points. Adding a new skill only requires:
1. Installing the skill package
2. Declaring the `comfyui_chenxin_mcp.skills` entry-point in `setup.py`

No changes to the core MCP server code are needed.

## Reference

See the full spec: `docs/superpowers/specs/2026-08-08-comfyui-chenxin-mcp.md`