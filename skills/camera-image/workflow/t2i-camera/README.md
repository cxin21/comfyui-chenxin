# t2i-camera 流程（文生图）

文本到图像的相机视角生成流程。运行时从单一 UI workflow 源（`workflow/source/文生图相机视角.json`）strip 出 API 图，patch 用户输入，经 MCP 验证后提交。

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
| `sampling.*` | 50/51 | KSampler | 否 | 7 字段各有默认 |
| `seed` | 65 | Seed (rgthree) | 否 | `-1` (random) |
| `image_size.{width,height}` | 68/71 | easy int | 否 | `1216 × 832` |
| `controlnet_image` | 129 | Load Image ControlNet | 仅当 ControlNet LLLite 启用 | - |

### 禁止暴露的字段

无（已包含所有 NODE_FIELD_MAP 字段；后续如需移除可编辑 `graph_patcher.NODE_FIELD_MAP`）。

## 步骤

| 步骤 | 文件 | 说明 |
|------|------|------|
| 01 | [01-discover.md](01-discover.md) | MCP 查询：LoRA 清单、节点 schema、健康检查 |
| 02 | [02-configure.md](02-configure.md) | 组装配置：prompts、camera、camera_extra、lora、groups、sampling、seed、image_size |
| 03 | [03-patch.md](03-patch.md) | 两步 patch：prepare_temporary_workflow + apply_run_config |
| 04 | [04-validate.md](04-validate.md) | MCP validate_workflow + check_workflow_runtime |
| 05 | [05-submit.md](05-submit.md) | MCP enqueue + 轮询 get_history + 下载图片 |
| 06 | [06-record.md](06-record.md) | 写 run-record.json、submitted-graph.json、attempts.jsonl |

## 命令示例

```bash
python -m runtime.runtime_cli run-t2i \
  --envelope path/to/anima-envelope.json \
  --camera "direction=front,elevation=high,distance=cowboy_shot" \
  --sampling-steps-first 50 \
  --sampling-cfg 7 \
  --seed 12345 \
  --image-size "width=1024,height=1280" \
  --lora "add_detail,masterpiece" \
  --g1 "保存图片（G1）,手部 ADetailer（G1）" \
  --g2 "图像锐化（G2）"
```

## 运行时模块入口

```
runtime_cli.cmd_run_t2i
  -> _kwargs_to_run_config (CLI bridge: csv->dict, kv->dataclass)
  -> t2i_camera.run_t2i(mcp, output_dir, config: RunConfig)
       -> prompt_forge_bridge.compile_envelope  (硬性闸门)
       -> if controlnet_image: mcp.upload_image
       -> source_workflow.prepare_temporary_workflow(mcp, stage=T2I, user_g1, user_g2)
            -> loads workflow/source/文生图相机视角.json (UI, 141 节点)
            -> computes enabled G1/G2 (DEFAULT + user + mandatory)
            -> applies mode=0/4 in a temp file
            -> mcp.save_workflow + mcp.strip_workflow -> API graph
       -> graph_patcher.apply_run_config(graph, stage=T2I, config, mcp_list_loras)
            -> writes prompts (24/25) from config.draft
            -> writes camera (583) + camera_extra (585) if set
            -> writes lora (26/66) via build_lora_patch
            -> writes sampling (50/51), seed (65), image_size (68/71) if set
            -> cross-validates controlnet_image <-> ControlNet LLLite group
            -> applies WORKFLOW_CONVENTIONS
       -> mcp.validate / mcp.check_runtime / mcp.enqueue
       -> mcp.get_history (text/dict dual-format parse)
       -> mcp.get_image (multipart content list)
       -> record_attempt (run-record.json schema_version 2.0)
```