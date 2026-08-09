# 故障排查

camera-image 采用 fail-closed 流程。先定位失败边界，再修正唯一责任层；
不要通过旧工作流、备用 API 图或运行时补线绕过错误。

## 1. 环境与 ComfyUI

先运行：

```powershell
powershell -ExecutionPolicy Bypass -File skills\prompt-forge\preflight-env.ps1
Invoke-RestMethod http://127.0.0.1:8188/system_stats
```

检查：

- Python 版本和插件缓存完整；
- ComfyUI 正在 `127.0.0.1:8188` 监听；
- Anima checkpoint 和所需自定义节点已安装；
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

## 7. 测试命令

```powershell
$root = (Get-Location).Path
Push-Location (Join-Path $root "skills/camera-image/camera_image")
$env:PYTHONPATH = (Get-Location).Path
python -m pytest runtime/tests -q
Pop-Location
$env:PYTHONPATH = $root
python -m pytest skills/_mcp/src/comfyui_chenxin_mcp/tests -q
```

完整真实验收场景见 [`camera-image-flow.md`](camera-image-flow.md)。
