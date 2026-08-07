# t2i-camera 流程（文生图）

文本到图像的相机视角生成流程。加载固定 API 图，patch 用户输入，经 MCP 验证后提交。

## 可配置项

| 配置项 | 节点 | 类型 | 必填 | 默认值 |
|--------|------|------|------|--------|
| `positive` | 24 | ImpactWildcardProcessor | 是 | - |
| `negative` | 25 | ImpactWildcardProcessor | 是 | - |
| `camera.direction` | 583 | CameraAngleNode | 否 | `front` |
| `camera.elevation` | 583 | CameraAngleNode | 否 | `eye-level` |
| `camera.distance` | 583 | CameraAngleNode | 否 | `full_body` |
| `camera.roll` | 583 | CameraAngleNode | 否 | `0.0` |
| `camera_extra.*` | 585 | CameraExtraConfigNode | 否 | 13 字段各有默认 |
| `lora_selections` | 26/66 | LoraManager | 否 | 默认 3-LoRA 栈 |
| `enabled_g1` | - | 组控制 | 否 | 3 组默认启用 |
| `enabled_g2` | - | 组控制 | 否 | 2 组默认启用 |

### 禁止暴露的字段

`seed`、`sampler`、`sampler_name`、`scheduler`、`steps`、`cfg` 不作为配置项，保持固定资产默认值。

## 步骤

| 步骤 | 文件 | 说明 |
|------|------|------|
| 01 | [01-discover.md](01-discover.md) | MCP 查询：LoRA 清单、节点 schema、健康检查 |
| 02 | [02-configure.md](02-configure.md) | 组装配置：prompts、camera、camera_extra、lora、groups |
| 03 | [03-patch.md](03-patch.md) | patch_graph()：将配置写入固定 API 图 |
| 04 | [04-validate.md](04-validate.md) | MCP validate_workflow + check_workflow_runtime |
| 05 | [05-submit.md](05-submit.md) | MCP enqueue + 轮询 get_history + 下载图片 |
| 06 | [06-record.md](06-record.md) | 写 run-record.json、submitted-graph.json、attempts.jsonl |

## 命令示例

```bash
python -m runtime.runtime_cli run-t2i \
  --positive "1girl, solo, outdoor, sunlight" \
  --negative "lowres, bad anatomy, bad hands" \
  --camera "direction=front,elevation=eye-level,distance=full_body" \
  --loras "add_detail,anima-base-1-masterpiece-v51" \
  --g1 "保存图片（G1）,第二轮采样器（G1）" \
  --g2 "图像锐化（G2）"
```

## 运行时模块入口

```
runtime_cli.cmd_run_t2i -> t2i_camera.run_t2i -> patch_graph -> mcp.validate/enqueue -> download -> record
```
