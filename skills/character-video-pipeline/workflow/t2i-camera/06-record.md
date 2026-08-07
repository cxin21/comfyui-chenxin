# 06-record：记录运行结果

生成运行成功后，写入三类记录文件。

## 1. run-record.json

```json
{
  "schema_version": "1.0",
  "stage": "t2i-camera",
  "prompt_id": "abc-123-def",
  "artifact": {
    "filename": "ComfyUI_00001_.png",
    "subfolder": "",
    "path": "outputs/ComfyUI_00001_.png",
    "bytes": 2097152,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb924..."
  },
  "duration_ms": 45230,
  "config": {
    "positive": "1girl, solo, outdoor",
    "negative": "lowres, bad anatomy",
    "camera": {"direction": "front", "elevation": "eye-level", "distance": "full_body"},
    "lora_selections": ["add_detail", "anima-base-1-masterpiece-v51"]
  }
}
```

写入 `run_dir/run-record.json`（`run_dir` 默认为 `output_dir/runs/t2i-<timestamp>/`）。

### artifact 字段

| 字段 | 来源 |
|------|------|
| filename | history entry outputs 图片信息 |
| subfolder | history entry outputs 图片信息 |
| path | 写入磁盘的绝对路径 |
| bytes | 图片字节大小 |
| sha256 | 图片内容的 SHA-256 哈希 |

## 2. submitted-graph.json

```python
(run_dir / "submitted-graph.json").write_text(
    json.dumps(graph, ensure_ascii=False, indent=2)
)
```

保存实际提交的 patched API 图，用于复现和调试。

## 3. attempts.jsonl

```python
record_attempt({
    "stage": "t2i-camera",
    "status": "success",
    "prompt_id": prompt_id,
    "artifact": artifact.get("path"),
})
```

追加一行到 `~/.codex/state/comfyui-chenxin/attempts.jsonl`（可通过 `COMFYUI_CHENXIN_STATE_DIR` 环境变量覆盖路径）。

每条记录格式：
```json
{
  "schema_version": "1.0",
  "recorded_at": "2026-08-07T12:00:00Z",
  "stage": "t2i-camera",
  "status": "success",
  "prompt_id": "abc-123-def",
  "artifact": "outputs/ComfyUI_00001_.png"
}
```

失败时同样记录（`status: "failed"`，包含 `error` 字段）。主机 agent 在下次启动时读取最近一条记录，避免重复已知错误。

## 返回值

```python
return {
    "accepted": True,
    "stage": "t2i-camera",
    "prompt_id": prompt_id,
    "artifact": artifact,
    "duration_ms": duration_ms,
    "run_record_path": str(run_dir / "run-record.json"),
}, 0
```
