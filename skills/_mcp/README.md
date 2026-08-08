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

The MCP server exposes 4 unified tools that work across all installed skills:

### `list_skills()`
List installed camera skills and their stages.

### `describe_config(skill, stage)`
Return the full schema (defaults, groups, enums, dependencies) for a skill stage.

**Parameters**:
- `skill`: Skill name (e.g. `"camera-image"`)
- `stage`: Stage name (e.g. `"t2i-camera"` or `"i2i-camera"`)

### `validate_config(skill, stage, config)`
Validate a config dict before running generation.

**Parameters**:
- `skill`: Skill name
- `stage`: Stage name
- `config`: Configuration object to validate

### `run_skill(skill, stage, envelope, config)`
Run a skill stage.

**Parameters**:
- `skill`: Skill name
- `stage`: Stage name
- `envelope`: Prompt package envelope object
- `config`: Configuration object (RunConfig fields)

## Architecture note

Skills are discovered via Python setuptools entry-points. Adding a new skill only requires:
1. Installing the skill package
2. Declaring the `comfyui_chenxin_mcp.skills` entry-point in `pyproject.toml`

No changes to the core MCP server code are needed.

## Reference

See the full spec: `docs/superpowers/specs/2026-08-08-comfyui-chenxin-mcp.md`