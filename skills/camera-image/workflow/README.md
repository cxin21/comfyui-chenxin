# Workflow 流程索引

每个 stage 是一个独立的流程目录。运行时只读当前 stage 目录，按编号步骤顺序执行。

## Stage 列表

| Stage | 目录 | 状态 | 编译路径 |
|-------|------|------|---------|
| t2i-camera（文生图） | [t2i-camera/](t2i-camera/) | 已实现 | prompt-forge validate -> RunConfig -> prepare_temporary_workflow -> apply_run_config -> validate -> enqueue |
| i2i-camera（图生图） | [i2i-camera/](i2i-camera/) | 已实现 | prompt-forge validate -> mcp.upload_image -> RunConfig -> prepare_temporary_workflow -> apply_run_config -> validate -> enqueue |
| multiview（多视角） | [multiview/](multiview/) | 占位 | 未实现 |
| video（视频） | [video/](video/) | 占位 | 未实现 |

## 编译路径说明

```
prompt-forge compile_envelope  ->  build RunConfig (CLI bridge: _kwargs_to_run_config)
                                ->  source_workflow.prepare_temporary_workflow
                                      (UI workflow -> temp file -> MCP strip -> API graph)
                                ->  apply_run_config (single source: NODE_FIELD_MAP)
                                ->  apply WORKFLOW_CONVENTIONS (e.g. i2i denoise=0.6)
                                ->  MCP validate_workflow  ->  MCP enqueue_workflow
```

- **源 UI workflow**：`workflow/source/文生图相机视角.json` 是通过 MCP 验证的 ComfyUI UI workflow（141 节点，44 组）。运行时每次加载、临时改 mode 字段、上传到 ComfyUI user library、调 strip_workflow 产出 API 图。
- **两步 patch**：第一步用 mode 字段控制节点启/禁（决定哪条 path 走），第二步用 apply_run_config 写节点 input 值。
- **MCP validate**：提交前调用 `validate_workflow(graph)` 确认 0 错误，`check_workflow_runtime(graph)` 确认 `runtime="local"`。
- **MCP enqueue**：调用 `enqueue_workflow(graph)` 返回 `prompt_id`，轮询 `get_history` 直到完成。

## 固定资产

| 文件 | 说明 |
|------|------|
| `source/文生图相机视角.json` | **唯一** UI workflow 源（141 节点 / 44 组）；t2i + i2i 共用 |
| `t2i-camera/groups.json` | G1（22 组）/ G2（15 组）成员映射（title → node id 列表） |
| `i2i-camera/groups.json` | 与 t2i-camera 相同（同一份复制） |

`workflow.json` 已被删除（旧 42 节点 stub 不可信）。运行时每次从源 UI workflow strip 出新鲜的 API 图。

## 运行时模块

| 模块 | 职责 |
|------|------|
| `source_workflow.py` | 加载源 UI workflow、计算启用组、写 mode 字段、调 MCP strip 出 API 图 |
| `graph_patcher.py` | 声明式 API 图 patch（apply_run_config + describe_config） |
| `camera_mapper.py` | 语义相机值 -> node 583 坐标映射 |
| `lora_resolver.py` | LoRA 发现、短名匹配、默认栈 |
| `mcp_client.py` | MCP 工具调用封装（含 save_workflow / strip_workflow） |
| `t2i_camera.py` | t2i 端到端流程 |
| `i2i_camera.py` | i2i 端到端流程 |
| `runtime_cli.py` | CLI 入口 |