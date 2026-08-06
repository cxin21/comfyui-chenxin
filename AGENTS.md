# ComfyUI-Chenxin 项目工作约定

## 技能调用铁律

1. **前提优先**：触发任何生产技能后，第一步永远是运行 `preflight-env.ps1` 验证环境。前提不满足时不读业务代码、不写文件、不探测能力。
2. **不绕过**：硬性依赖缺失时立即停止并告知用户。禁止用其他语言重写运行时工具、禁止手工模拟、禁止 partial 执行。
3. **缓存即运行时**：Agent 从插件缓存读取技能内容。缓存与项目源不同步（关键文件缺失）时，运行 `scripts/install.ps1` 重新同步，不直接操作缓存目录。
4. **固定工作流**：Anima camera 工作流是固定 release asset（`runtime/workflow_assets/camera-anima.json`），不是运行时发现结果。不从 ComfyUI 本地库或磁盘搜索工作流文件。
5. **一次一步**：完成 Step 0 再做 Step 1，完成 Step 1 再做 Step 2。不跳步，不并行读无关文件。

## 环境依赖

- **Python 3.10+**：在 PATH 中，或位于 ComfyUI 内嵌 Python 路径（`preflight-env.ps1` 自动检测）
- **ComfyUI**：运行在 `http://127.0.0.1:8188`
- **Node.js**：用于安装脚本和 MCP 服务器
- **MCP 工具**：`check_workflow_runtime`、`get_workflow`、`strip_workflow`、`validate_workflow`、`list_local_models`

## 缓存同步

项目源在 `D:\Projects\comfyui-chenxin`，插件缓存在 `%USERPROFILE%\.codex\plugins\cache\personal\comfyui-chenxin`。修改技能源码后必须重新运行安装脚本同步缓存：

    powershell -ExecutionPolicy Bypass -File scripts\install.ps1

`preflight-env.ps1` 在运行时检测缓存是否过期（关键文件缺失即判定过期）。

## 目录结构

- `skills/character-video-pipeline/` — 四阶段 ComfyUI 生产消费者
- `skills/prompt-forge/` — LLM-first 提示词编写与质量审计
- `scripts/install.ps1` — 一键安装与缓存同步
- `.codex-plugin/plugin.json` — 插件元数据与版本