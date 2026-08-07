# 01-upload：上传参考图（+ 可选 controlnet 图）

> i2i-camera 同样走 prompt-forge envelope 路径（详见 `../t2i-camera/02-configure.md`）。本步骤只负责：
> 1. 上传 `RunConfig.reference_image`（必填，本地路径 → mcp.upload_image）
> 2. 可选上传 `RunConfig.controlnet_image`（仅当 ControlNet LLLite 组被启用时）
> 3. 在 patch_graph 阶段自动 append `加载图片（G1）` 到 enabled_g1

## MCP 调用

### 1. health_check()

```python
mcp.health()  # -> health_check({})
```

同 t2i：检查队列空闲（running=0, pending=0）。

### 2. upload_image(source_path)

```python
upload_result = mcp.upload_image(config.reference_image)
# -> upload_image({"source_path": "/tmp/source.png"})
```

返回：
```json
{"name": "source.png", "subfolder": ""}
```

`i2i_camera.run_i2i()` 提取 `image_name`：
```python
image_name = upload_result.get("name")
subfolder = upload_result.get("subfolder", "")
if subfolder:
    image_name = f"{subfolder}/{image_name}"
```

### 3. upload_image(controlnet_image)（可选）

`config.controlnet_image` 非空时走同一条上传链路，上传后的文件名交给 patch_graph 写入 node 129。
是否必填由 patch_graph 与 ControlNet LLLite 组做双向交叉校验：启用该组却没给图会抛 `ValueError`。

## 后续步骤

上传完成后，流程与 t2i-camera 步骤 02-06 一致：
- 02-configure：编译 envelope，组装 `RunConfig`
- 03-patch：见 [03-patch.md](03-patch.md)（在通用流程后追加 img2img 激活）
- 04-validate：MCP 验证
- 05-submit：MCP 提交 + 下载
- 06-record：记录（stage="i2i-camera"）

## 失败处理

上传失败时，`run_i2i()` 抛出 `RuntimeError`，记录 attempt（status="failed"）。
