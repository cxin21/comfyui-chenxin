# 故障排查

## ComfyUI 无法连接

确认 ComfyUI 已启动并监听 `http://127.0.0.1:8188`。插件不会替你启动缺失的 ComfyUI，也不会自动安装节点和模型。先检查：

```powershell
Invoke-WebRequest http://127.0.0.1:8188/system_stats
```

## MCP 工具不可用

检查 MCP 宿主是否注册 `mcp/mcp_servers.json` 中的 `comfyui-mcp`，并确认宿主实际工具名已映射到 `McpBridge`。不要根据文档猜工具名；先做能力协商。缺少 `get_workflow`、`strip_workflow`、`validate_workflow` 或 `check_workflow_runtime` 时，生产 Stage 2/3/4 必须停止。

## 工作流 profile 不匹配

工作流名称、UI fingerprint、API graph hash、节点、模型、LoRA、分辨率或输出 map 任一漂移，旧 draft 和 approval 都不能复用。重新读取真实工作流、重新规划并重新审批。原始分组 Flux 工作流不是 flat-v2 的 fallback。

## 队列非空

当前生产策略一次只允许一个 ComfyUI job。队列有 running 或 pending 时不提交新任务；等待 terminal history 后重新生成 live CapabilityReport。

## 相机转换出现已知缺口

只允许 `runtime_cli.py normalize-camera` 对受信相机 profile 执行 pinned normalization。不要自行编写通用 UI→API converter，也不要把 caller-authored conversion receipt 作为证明。归一化后必须重新验证 UI fingerprint、API graph、runtime 和 validation。

## Stage 2 找不到可用角度

只有通过 raw history、PNG hash、lineage 和 acceptance 校验的角度图才能被 `accept-reference` 接受。DiagnosticImage、hash 不匹配、front-facing 未确认或 semantic conflict 的资产不能进入 Stage 3。

## enqueue 超时或结果不确定

保留 consumption 和 submission-intent receipt，先按稳定 request id 查询 ComfyUI history。不要删除 sentinel、不要盲目重试、不要把“请求已发出”当成生成成功。

## 视频技术验证失败

Stage 4 需要同时通过 raw history、视频字节 hash、`ffprobe` 的分辨率/FPS/帧数/时长和 profile 合同。任何一项失败都不能写成功 RunRecord。

## 旧技能被触发

`skills/manga-*`、`skills/lora-trainer/` 和 `skills/ffmpeg-pipeline/` 已设置 `status: legacy`、`triggers: []`。如果宿主仍显示旧技能，重载插件并确认当前工作树；生产请求统一显式使用 `skills/prompt-forge/SKILL.md`。

## 纯 JSON CLI 被拒绝

这是预期的安全行为。`runtime_cli.py` 可以规划、审批、消费和验证 JSON，但不能携带受控 Python callable。生产 MCP conversion 必须由本地 orchestrator 注入 `McpBridge`，不能用 JSON 自填 receipt 冒充可信调用。