# 故障排查

## ComfyUI 无法连接

确认 ComfyUI 正在监听 `http://127.0.0.1:8188/`：

```powershell
Invoke-WebRequest http://127.0.0.1:8188/system_stats
```

Prompt Forge 不会安装模型、节点或工作流；连接和资源问题由 `character-video-pipeline` 处理。

## 提示词校验失败

确认调用方已经提供最终 PromptPackage 草稿，并检查目标、CreativeEvidence、连续性锁、方言和风格字段。缺失草稿、占位符、未声明事实或未知 tag 会 fail closed；Prompt Forge 不会用猜测补写 prose。

## 方言或风格不匹配

方言必须使用 canonical ID 或批准的 alias。模糊查询只能得到建议，不能成为最终方言。风格只改变 medium、palette、lighting、composition、material、texture、depth 和 motion language，不得改变人物、剧情、道具或 continuity locks。

## MCP 工具不可用

确认宿主提供 `host_call_tool(tool_name, arguments)`，并且 `mcp/mcp_servers.json` 中的工具名已登记。缺少 workflow discovery、validation 或 runtime capability 证据时，生产 pipeline 必须停止，不得伪造 receipt。

## 阶段资产不可用

只有经过 raw history、PNG/hash、lineage、orientation 和 acceptance 校验的阶段资产才能进入下一阶段。Stage 2 的 accepted multiview 才能进入 Stage 3；Stage 3 的 accepted shot image 才能进入 Stage 4。

## 队列或提交不确定

保留 request ID、consumption receipt 和 raw history，先查询 terminal history 再决定。不要盲目重试、删除 sentinel 或把“请求已发送”当成成功。

## 视频验证失败

Stage 4 必须同时验证 raw history、视频 hash、ffprobe 的 FPS/帧数/时长以及 profile 合同。任何一项失败都不能写入 RunRecord。
