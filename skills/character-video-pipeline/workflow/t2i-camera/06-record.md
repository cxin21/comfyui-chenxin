# 06-record：记录运行结果

生成运行成功后，写入三类记录文件。

## 1. run-record.json

```json
{
  "schema_version": "2.0",
  "stage": "t2i-camera",
  "prompt_id": "abc-123-def",
  "artifact": {
    "filename": "2026-08-07-121510__0.png",
    "subfolder": "",
    "path": "outputs/2026-08-07-121510__0.png",
    "bytes": 611226,
    "sha256": "523209d41ecab4ce7c02347aa760db0b52a9ba735c2239dd42da6e7ae4e34c95"
  },
  "duration_ms": 117406,
  "config": {
    "evidence": {"locked_facts": ["1girl"]},
    "draft": {"positive": "1girl, solo, anime", "negative": "lowres"},
    "dialect_id": "anima",
    "camera": {"direction": "front", "elevation": "high", "distance": "cowboy_shot", "roll": 0.0},
    "camera_extra": {"lens_value": "85mm lens"},
    "lora": {"selections": ["add_detail"]},
    "groups": {"g1": ["手部 ADetailer（G1）"], "g2": ["图像锐化（G2）"]},
    "sampling": {"steps_first": 50, "cfg": 7.0, "sampler": "dpmpp_2m", "scheduler": "karras",
                 "denoise_first": 1.0, "steps_refine": 25, "denoise_refine": 0.2},
    "seed": 12345,
    "image_size": {"width": 1024, "height": 1280},
    "controlnet_image": null,
    "reference_image": null
  },
  "prompt_package_quality": {
    "ready_for_review": true,
    "facts_preserved": true,
    "dialect_valid": true
  }
}
```

写入 `run_dir/run-record.json`（`run_dir` 默认为 `output_dir/runs/t2i-<timestamp>/`）。

`schema_version` is "2.0" (was "1.0" before 2026-08-07). The `config`
field is the full frozen RunConfig serialized via dataclasses.asdict. All
RunConfig fields appear even when None, so consumers can rely on the
schema being stable.

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