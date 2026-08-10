# 故障排查

所有 camera 技能都采用 fail-closed 流程。先定位失败边界，再修正唯一
责任层；不要通过旧工作流、备用 API 图或运行时补线绕过错误。

## 1. 环境与 ComfyUI

Prompt Forge 提示词编写没有强制前置门禁。生产执行失败时，先检查实际运行
边界；确认 ComfyUI 是否可访问可运行：

```powershell
Invoke-RestMethod http://127.0.0.1:8188/system_stats
```

检查：

- 需要确定性校验或本地执行时，Python 版本与插件缓存完整；
- ComfyUI 正在 `127.0.0.1:8188` 监听；
- 所选固定工作流需要的模型和自定义节点已安装；
- MCP 工具完整且版本契约匹配。

缺少硬依赖时停止，不用其他工具模拟运行时。

## 2. `validate_config` 失败

这是请求契约错误，不是 ComfyUI 执行错误。

常见原因：

- `draft.positive` 或 `draft.negative` 为空；
- I2I 缺少 `reference_image`；
- ControlNet 缺少控制图或没有启用 ControlNet 组；
- 启用了区域提示组但缺少 R/G/B 图像或提示词；
- 启用了签名组但缺少 `signature_image`。

修正配置后重新校验，不把错误配置降级为基础文生图。

## 3. 组编译失败

错误包括：

- `unknown group title`：组名不是 `describe_config` 返回的当前组名；
- `references missing source node`：组资产引用了不存在的固定源节点；
- `configured default group ... missing`：固定默认组与组资产不一致。

源工作流中未启用组的节点是正常的。不要删除它们；只检查组资产是否
正确引用固定源节点，以及最终选中子图是否闭合。

## 4. API 图结构失败

常见错误：

- `dangling input reference`：API 输入连接指向已不存在的节点；
- `output node ... has no images input`：输出节点没有图像输入；
- `compiled API graph has no image output node`：最终图没有可执行图像输出。

排查 `submitted-graph.json` 和固定源拓扑。修复应发生在源 UI 工作流、组
资产或编译顺序中；禁止在 strip 后添加兼容性重连。

## 5. MCP 校验或执行失败

按顺序检查：

1. `validate_workflow` 返回值；
2. `check_workflow_runtime` 是否为本地运行时；
3. `enqueue_workflow` 是否使用 `{ "workflow": graph }`；
4. 返回结果是否包含 `node_errors`；
5. ComfyUI history 中的具体失败节点。

LoRA 必须使用可序列化的 `LoRA Text Loader (LoraManager)` 输入。
ControlNet 必须保留 `ModelPatchLoader -> AnimaLLLiteApply.model_patch` 的
真实连接。不要将旧自定义输入类型或缺失连接转换成字符串兜底。

## 6. 没有输出图片

不能只看队列是否变空。检查：

- history 是否成功完成；
- 输出节点是否存在并连接到最终图像；
- 输出记录是否包含 `images`；
- 下载文件是否存在、非空、可解码；
- `run-record.json` 是否记录了实际 artifact 和 SHA-256。


## 8. camera-video 专项

### 配置失败

`camera-video` 只接受：

- `t2v-video`: `prompt`, `duration`；
- `i2v-video`: 上述字段加 `reference_image_1`；
- `multi-i2v-video`: 上述字段加 `reference_image_1/2/3`。

时长必须是 2–15 秒的有限数字。多图场景不允许缺图、复用图片或传入
groups、LoRA、ControlNet、模型和采样器配置。

### 固定 API 图失败

确认 `manifest.json` 中的工作流哈希未变，且运行时没有调用
`strip_workflow`、发现本地工作流或修改非声明字段。`camera-video` 的
提交图必须直接来自固定 API 图，只写入提示词、时长和上传后图片文件名。

### `ComfyMathExpression` 报 `values` 缺失

`values.a` 是 ComfyUI V3 动态输入格式。若 MCP 校验器不识别该格式，先
检查项目规定的 `comfyui-mcp` 工具版本和完整工具集；不要为通过校验器而
改写固定 API 图。

### `MiniMaxH3MemoryEfficientSageAttentionPatch` 不可执行

该节点是可选显存优化，不是 MiniMax H3 生成必需节点。它依赖精确匹配的
SageAttention、CUDA、PyTorch、ComfyUI-KJNodes 组合；不同 ComfyUI Python
环境可能表现不同。发布的 `camera-video` 单图/多图固定资产已在发布前移除
该节点，并直连固定 LoRA 模型路径。不要在运行时重新添加或条件跳过它。

### 没有输出视频

不能只看队列是否变空。检查：

- history 是否成功完成；
- `VHS_VideoCombine` 是否产生 `gifs` 条目；
- 条目实际 MIME/扩展名是否为 MP4；
- 下载文件是否存在且非空；
- `run-record.json` 是否记录所有 artifact 的字节数和 SHA-256。

完整流程见 [`camera-video-flow.md`](camera-video-flow.md)；图像和多视图流程
分别见 [`camera-image-flow.md`](camera-image-flow.md) 和
[`camera-multiview-flow.md`](camera-multiview-flow.md)。
