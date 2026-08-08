# 05-submit：MCP 提交与下载

将验证通过的图提交到 ComfyUI 执行，轮询直到完成，然后下载产物。

## MCP 调用

### 1. enqueue_workflow(graph)

```python
result = mcp.enqueue(graph)
# -> enqueue_workflow({"workflow": graph})
prompt_id = result.get("prompt_id")
```

返回 `prompt_id` 和队列位置。`run_t2i()` 检查 `prompt_id` 非空。

### 2. 轮询 get_history(prompt_id)

```python
entry = _wait_for_completion(mcp, prompt_id, timeout=600, poll_interval=3)
```

每 3 秒调用 `get_history({"prompt_id": prompt_id})`，检查 `status.status_str`：

| status_str | 行为 |
|------------|------|
| `"success"` | 返回 history entry，继续下载 |
| `"error"` | 解析 `status.messages` 中的 `execution_error`，抛出 `RuntimeError` |
| 其他/不存在 | 继续轮询 |
| 超时（600s） | 抛出 `RuntimeError("timed out")` |

### 3. get_image(filename, subfolder, type)

```python
artifact = _download_artifact(mcp, entry, output_dir)
```

从 history entry 的 `outputs` 中提取第一个图片输出：
```python
image_info = entry["outputs"][node_id]["images"][0]
# {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}
```

调用 `get_image({"filename": ..., "subfolder": ..., "type": ...})` 获取图片字节，写入 `output_dir/filename`。

## 失败处理

任何步骤抛出异常时，`run_t2i()` 捕获并：
1. 调用 `record_attempt({"stage": "t2i-camera", "status": "failed", "error": str(exc)})`
2. 返回 `({"accepted": False, "error": str(exc)}, 1)`

## 输出

下载的图片文件路径 + artifact 字典（filename, subfolder, path, bytes, sha256），传入 06-record 步骤。
