# ComfyUI-Chenxin 项目工作约定

## 技能调用铁律

1. **职责内验证**：提示词技能独立完成作者侧审计；生产执行仅在进入对应技能的本地运行边界时，按该技能契约验证所需服务与依赖。
2. **不绕过**：硬性依赖缺失时立即停止并告知用户。禁止用其他语言重写运行时工具、禁止手工模拟、禁止 partial 执行。
3. **缓存即运行时**：Agent 从插件缓存读取技能内容。缓存与项目源不同步（关键文件缺失）时，运行 `scripts/install.ps1` 重新同步，不直接操作缓存目录。
4. **固定工作流**：所有 camera 技能的工作流都是固定 release asset（`runtime/workflow_assets/` 下的 JSON），不是运行时发现结果。不从 ComfyUI 本地库或磁盘搜索工作流文件。
5. **一次一步**：完成 Step 0 再做 Step 1，完成 Step 1 再做 Step 2。不跳步，不并行读无关文件。

## 环境依赖

- **Python 3.10+**：用于提示词编译与本地执行，可来自 PATH 或 ComfyUI 内嵌环境
- **ComfyUI**：运行在 `http://127.0.0.1:8188`
- **Node.js**：用于上游 `comfyui-mcp` 启动（通过 `npx`）
- **MCP 工具**：`check_workflow_runtime`、`get_workflow`、`strip_workflow`、`validate_workflow`、`list_local_models`（由上游 `comfyui-mcp` 提供）

## 缓存同步

项目源在 `D:\Projects\comfyui-chenxin`，插件缓存在 `%USERPROFILE%\.codex\plugins\cache\personal\comfyui-chenxin`。修改技能源码后必须重新运行安装脚本同步缓存：

    powershell -ExecutionPolicy Bypass -File scripts\install.ps1

安装脚本负责源与插件缓存同步；纯提示词编写不经过独立的前置脚本门禁。

## 目录结构

- `skills/anima-prompt-v1/`、`skills/minimax-h3-prompt/` — 独立提示词编写与质量审计（无副作用）
- `skills/camera-image/` — Anima T2I/I2I 固定工作流消费者
- `skills/camera-multiview/` — Flux2-Klein 固定多视图工作流消费者
- `skills/camera-video/` — MiniMax H3 固定文生视频/参考图生视频工作流消费者
- `mcp_server/` — 项目 MCP 服务器（统一暴露 `list_skills` / `describe_config` / `validate_config` / `run_skill`）
- `scripts/install.ps1` / `scripts/install.sh` — 一键安装与缓存同步
- `docs/` — 各技能的详细执行契约
- `.codex-plugin/plugin.json` — 插件元数据与版本
- `mcp/mcp_servers.json` — 上游 `comfyui-mcp` 启动规格
