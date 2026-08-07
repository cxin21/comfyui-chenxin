# Workflow 流程索引

每个 stage 是一个独立的流程目录。运行时只读当前 stage 目录，按编号步骤顺序执行。

## Stage 列表

| Stage | 目录 | 状态 | 编译路径 |
|-------|------|------|---------|
| t2i-camera（文生图） | [t2i-camera/](t2i-camera/) | 已实现 | 加载固定 API 图 -> patch 输入 -> MCP validate -> MCP enqueue |
| i2i-camera（图生图） | [i2i-camera/](i2i-camera/) | 已实现 | 上传参考图 -> 加载固定 API 图 -> patch 输入 -> MCP validate -> MCP enqueue |
| multiview（多视角） | [multiview/](multiview/) | 占位 | 未实现 |
| video（视频） | [video/](video/) | 占位 | 未实现 |

## 编译路径说明

```
load_fixed_api_graph  ->  patch_graph()  ->  MCP validate_workflow  ->  MCP enqueue_workflow
```

- **固定 API 图**：`workflow/<stage>/workflow.json` 是已通过 MCP validate_workflow 验证的 ComfyUI API 格式图（35 节点，0 错误）。运行时直接加载，不经过 strip、不经过 UI-to-API 转换。
- **patch 输入**：`graph_patcher.patch_graph()` 对图节点原地修改（prompts、camera、camera_extra、LoRA、groups、img2img 激活）。
- **MCP validate**：提交前调用 `validate_workflow(graph)` 确认 0 错误，`check_workflow_runtime(graph)` 确认 `runtime="local"`。
- **MCP enqueue**：调用 `enqueue_workflow(graph)` 返回 `prompt_id`，轮询 `get_history` 直到完成。

## 固定资产

| 文件 | 说明 |
|------|------|
| `t2i-camera/workflow.json` | t2i/i2i 共用的固定 API 图（35 节点） |
| `t2i-camera/groups.json` | G1（22 组）/ G2（15 组）成员映射 |
| `i2i-camera/workflow.json` | 与 t2i-camera 相同（复制） |
| `i2i-camera/groups.json` | 与 t2i-camera 相同（复制） |

## 运行时模块

| 模块 | 职责 |
|------|------|
| `workflow_loader.py` | 加载 workflow.json + groups.json |
| `camera_mapper.py` | 语义相机值 -> node 583 坐标映射 |
| `lora_resolver.py` | LoRA 发现、短名匹配、默认栈 |
| `group_controller.py` | G1/G2 组模式控制（active/bypass） |
| `graph_patcher.py` | 声明式 API 图 patch（所有输入写入） |
| `mcp_client.py` | MCP 工具调用封装 |
| `t2i_camera.py` | t2i 端到端流程 |
| `i2i_camera.py` | i2i 端到端流程 |
| `runtime_cli.py` | CLI 入口 |
