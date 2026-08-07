# 01-upload：上传参考图 + 激活 img2img

i2i-camera 的第一步：通过 MCP 上传参考图，然后在 patch_graph 中激活 img2img 路径。

## MCP 调用

### 1. health_check()

```python
mcp.health()  # -> health_check({})
```

同 t2i：检查队列空闲（running=0, pending=0）。

### 2. upload_image(source_path)

```python
upload_result = mcp.upload_image(reference_image_path)
# -> upload_image({"source_path": "path/to/reference.png"})
```

返回：
```json
{"name": "reference.png", "subfolder": ""}
```

`i2i_camera.run_i2i()` 提取 `image_name`：
```python
image_name = upload_result.get("name")
subfolder = upload_result.get("subfolder", "")
if subfolder:
    image_name = f"{subfolder}/{image_name}"
```

## patch_graph 激活 img2img

`patch_graph(stage="i2i-camera", reference_image=image_name)` 在完成 t2i 所有 patch 步骤后，额外调用 `_activate_img2img(graph, image_name)`：

### 激活 LoadImage 组（node 21/57/58/59）

```python
for nid in ("21", "57", "58", "59"):
    graph[nid]["mode"] = MODE_ACTIVE  # mode=0
```

这 4 个节点在 t2i 模式下被 bypass（mode=4），i2i 模式下激活。

### 设置 LoadImage 图片名（node 21）

```python
graph["21"]["inputs"]["image"] = image_name
```

### 切换 latent 来源（node 75 ImpactSwitch）

```python
graph["75"]["inputs"]["select"] = 0
```

ImpactSwitch `select=0` 路由到 input2（VAEEncode，从参考图编码 latent），`select=1` 路由到 input1（EmptyLatent，从噪声生成）。

## 后续步骤

上传和激活完成后，流程与 t2i-camera 步骤 02-06 一致：
- 02-configure：组装配置（reference_image 已设置）
- 03-patch：patch_graph 完成（img2img 已激活）
- 04-validate：MCP 验证
- 05-submit：MCP 提交 + 下载
- 06-record：记录（stage="i2i-camera"）

## 失败处理

上传失败时，`run_i2i()` 抛出 `RuntimeError`，记录 attempt（status="failed"）。
