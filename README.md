# comfyui-chenxin

Claude Code 插件：`anima-prompt-v1` / `minimax-h3-prompt` / `camera-image` /
`camera-video` / `camera-multiview` 五个独立 Skill，每个 Skill 暴露自己的
console script，不再依赖任何 MCP bridge。

## Skill 与 console script

| Skill | console script | 作用 |
|---|---|---|
| `skills/anima-prompt-v1/` | `anima-prompt-v1` | Anima 生图提示词 brief / 路由 / 审计 + Catalog 检索 + relation 维护 |
| `skills/minimax-h3-prompt/` | `minimax-h3-prompt` | MiniMax H3 T2VA / Ref2VA 提示词作者 + tokenizer / context-plan |
| `skills/camera-image/` | `camera-image` | 固定 Anima camera 工作流（text-to-image / image-to-image） |
| `skills/camera-video/` | `camera-video` | 固定 MiniMax H3 video 工作流（T2V / I2V / multi-I2V） |
| `skills/camera-multiview/` | `camera-multiview` | 固定 Flux2-Klein 一键多视图 |

每个 console script 都遵循 P1 JSON envelope 契约（`ok` / `command` /
`stage` / `result` / `errors` / `advisories`），并按错误类别映射退出码
（0 / 2 / 3 / 4 / 5 / 70）。

## 安装

Claude Code 走 marketplace：

1. 把这个仓库作为 `comfyui-chenxin` 插件的源加到 marketplace（或直接
   `pip install -e` 每个包）。
2. 在新会话里触发一次插件市场刷新，然后即可调用 `anima-prompt-v1`、
   `minimax-h3-prompt` 等。

POSIX / PowerShell 上一键安装：

```bash
bash scripts/install.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

安装器只把 `runtime/comfyui_http` + 五个 Skill 安装到 venv，不再写入任何
Codex `config.toml`。

## 调用示例

```bash
# Anima：构造作者 brief（输入 JSON 必须含 prompt.positive / prompt.negative）
anima-prompt-v1 author --request brief.json --json

# Anima：Catalog 检索
anima-prompt-v1 catalog search "blue coat" --json | jq .

# MiniMax H3：T2VA 作者
minimax-h3-prompt author --stage t2va --request h3-request.json --json

# MiniMax H3：校验 tokenizer 完整性
minimax-h3-prompt tokenizer verify \
  --tokenizer-dir skills/minimax-h3-prompt/knowledge --json

# Camera Image：列出 t2i 阶段的字段
camera-image describe --stage t2i-camera --json

# Camera Image：端到端运行
camera-image run \
  --stage t2i-camera \
  --envelope envelope.json --config config.json \
  --output-dir out/ --json

# Camera Multiview：5 张姿势图 + assets verify
camera-multiview assets verify --stage multiview --json
```

## 不再依赖 MCP

历史版本依赖一个 `comfyui-chenxin-mcp` 服务器桥接 Claude Code 跟
ComfyUI。`mcp_server/`、`mcp.json`、`.codex-plugin/` 已经在 v2.0 移除。
所有 Skill 都可以直接 `pip install -e` 后通过 console script 调用，
不再需要 Node / `npx` / Codex `config.toml`。

## 验证

```bash
# 源码 + 临时 staged 缓存都通过
python scripts/verify_release.py --source-root . --cache-root /path/to/release

# 跑端到端 smoke（stage → install → 14 子命令）
python scripts/smoke_cli.py --release-root /path/to/release

# pytest e2e gate
pytest tests/e2e/test_installed_cli.py
```

## 文档

- `docs/architecture.md` — 顶层架构。
- `docs/cli-protocol.md` — 每个 console script 共同的 P1 JSON envelope 契约。
- `docs/USAGE.md` — 每个 Skill 的具体调用方式。
- `docs/camera-*-flow.md` — 三个相机 Skill 的工作流图与节点映射。
- `docs/TROUBLESHOOTING.md` — 常见错误与最小复现。
- `docs/superpowers/specs/2026-08-15-skill-owned-cli-no-mcp-design.md` —
  v2.0 去 MCP 的设计与实施计划。

## 许可

`LICENSE` 文件注明仓库许可（继承自上游组件）。
