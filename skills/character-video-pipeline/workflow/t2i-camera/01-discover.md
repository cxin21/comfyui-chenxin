# 01-discover：MCP 查询

运行前通过 MCP 工具查询环境状态和节点 schema，确认 ComfyUI 可用且节点定义符合预期。

> ⚠️ **提示词闸门（硬性规则）**：本 stage 的 `positive` / `negative` 必须先经过 prompt-forge 校验。`runtime.t2i_camera.run_t2i`（CLI `run-t2i`）是唯一入口，它强制吃 envelope 并在内部调 `prompt_forge_bridge.compile_envelope`，不存在绕过闸门的旁路。

## MCP 调用

### 1. health_check()

```python
mcp.health()  # -> health_check({})
```

返回 ComfyUI 版本、GPU/VRAM、队列状态。t2i_camera.run_t2i 检查队列必须空闲（running=0, pending=0），否则拒绝提交。

### 2. list_local_models(loras)

```python
mcp.list_loras()  # -> list_local_models({"model_type": "loras"})
```

返回所有已安装的 LoRA 文件名列表。`lora_resolver.parse_lora_inventory()` 解析响应，`filter_anima_loras()` 过滤出 `Anima\` 前缀的 LoRA。

仅在用户提供了 `lora_selections` 时调用；使用默认栈时跳过。

### 3. get_node_info("CameraAngleNode")

```python
mcp._call("get_node_info", {"node_type": "CameraAngleNode"})
```

确认 node 583 的输入 `pos_x/pos_y/pos_z/roll` 为 FLOAT 类型，范围 `[-1, 1]`。camera_mapper.py 的映射值均在此范围内：

| 语义值 | 字段 | 坐标值 |
|--------|------|--------|
| front | pos_x | 0.0 |
| right | pos_x | 0.5 |
| back | pos_x | 1.0 |
| left | pos_x | -0.5 |
| high | pos_y | 0.5 |
| eye-level | pos_y | 0.0 |
| low | pos_y | -0.5 |
| extreme_close_up | pos_z | 0.9 |
| close_up | pos_z | 0.5 |
| medium | pos_z | 0.1 |
| cowboy_shot | pos_z | -0.2 |
| full_body | pos_z | -0.5 |
| wide | pos_z | -0.9 |

### 4. get_node_info("CameraExtraConfigNode")

确认 node 585 的 13 个输入字段（extreme_type, extreme_weight, lens_enabled, lens_value, dof_enabled, dof_value, dof_weight, movement_enabled, movement_value, composition_enabled, composition_value, style_enabled, style_value）。

### 5. get_node_info("Lora Loader (LoraManager)")

确认 node 26 接受 `text` 输入（LoRA 栈文本），node 66 接受 `trigger_words` 和 `orinalMessage`。

## 输出

本步骤不产生文件。查询结果供 02-configure 步骤使用。
