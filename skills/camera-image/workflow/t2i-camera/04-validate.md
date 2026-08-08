# 04-validate：MCP 验证

提交前通过 MCP 验证 patched 图无错误且为本地运行时。

## MCP 调用

### 1. validate_workflow(graph)

```python
validation = mcp.validate_workflow(graph)
# -> validate_workflow({"workflow": graph})
```

检查项：
- 节点 class_type 是否已注册
- 连接是否完整（无断线）
- 输出索引是否有效
- 引用的模型是否存在

**通过条件**：`error_count == 0`。否则 `run_t2i()` 抛出 `RuntimeError`。

固定资产 `workflow.json` 已在构建时通过 MCP 验证（35 节点，0 错误）。patch 只修改输入值，不改变图结构，因此验证应始终通过。

### 2. check_workflow_runtime(graph)

```python
runtime_check = mcp.check_runtime(graph)
# -> check_workflow_runtime({"graph": graph})
```

扫描图中的节点 class_type，判断是否使用付费 API 节点。

**通过条件**：`runtime == "local"`。确认所有节点在本地 GPU 运行，不消耗 API 额度。

## 受保护节点不变式

`group_controller._PROTECTED_NODES` 中的 30 个核心节点（22, 24, 25, 26, 27, 35, 40, 48, 50, 51, 65, 66, 75, 76, 78, 79, 80, 83, 84, 86, 87, 88, 89, 96, 111, 490, 550, 557, 583, 585, 587）在 patch 后必须 `mode == 0`（active）。

这些节点涵盖：
- 采样器（KSampler）
- 图片保存（SaveImage）
- 相机节点（CameraAngleNode, CameraExtraConfigNode）
- 提示词节点（ImpactWildcardProcessor）
- LoRA 加载器（LoraManager）
- VAE 解码
- ImpactSwitch（latent 路由）

验证步骤不显式检查此不变式，但 `apply_group_modes()` 在 patch 阶段已强制保证。

## 输出

验证通过后，patched 图传入 05-submit 步骤。
