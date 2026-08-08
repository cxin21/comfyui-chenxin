# i2i-camera 流程（图生图）

图像到图像的相机视角生成流程。与 t2i-camera 共用同一份源 UI workflow（`workflow/source/文生图相机视角.json`）+ `groups.json`，区别在于第一步上传参考图，且 patch 时激活 img2img 路径（加载图片（G1） 在 source 阶段被 strip 保留；具体 i2i 重连在 `apply_run_config` 内）。

## 与 t2i-camera 的差异

| 方面 | t2i-camera | i2i-camera |
|------|-----------|------------|
| 步骤 01 | MCP 查询（discover） | MCP 上传参考图（upload） |
| patch | 不激活 img2img | 激活 node 21/57/58/59 + 将 node 27 的 `latent_image` 重连到 VAEEncode（node 59） |
| 源 workflow | `workflow/source/文生图相机视角.json` | 同一份源（不同 G1 启用集） |
| groups | 默认 G1 + user.g1 | 默认 G1 + user.g1 + stage-mandatory `加载图片（G1）`（自动 enable） |
| 强制 denoise | 无 | `node 27.denoise = 0.6`（WORKFLOW_CONVENTIONS） |

步骤 02-06 与 t2i-camera 完全一致，参考 [t2i-camera/](../t2i-camera/) 对应文档。

## 可配置项

与 t2i-camera 共用同一份 `RunConfig`（见 `runtime/config_schema.py`），增加 `reference_image`（必填）。

| 配置项 | 节点 | 必填 | 说明 |
|--------|------|------|--------|
| `draft.positive` / `draft.negative` | 24 / 25 | 是 | 由 `--envelope` 经 prompt-forge 编译产出，不直传 |
| `reference_image` | 21 | 是 | 本地路径，上传后写入图片名 |
| `controlnet_image` | 129 | 否 | 仅当 ControlNet LLLite 组启用时必填 |
| `camera.*` | 583 | 否 | 同 t2i |
| `camera_extra.*` | 585 | 否 | 同 t2i |
| `lora` | 26/66 | 否 | 同 t2i |
| `sampling.*` | 50/51 | 否 | 同 t2i |
| `seed` | 65 | 否 | 同 t2i |
| `image_size.*` | 68/71 | 否 | 同 t2i |
| `groups.g1/g2` | - | 否 | 同 t2i（i2i 额外自动 enable `加载图片（G1）`） |

## 步骤

| 步骤 | 文件 | 说明 |
|------|------|------|
| 01 | [01-upload.md](01-upload.md) | MCP upload_image 上传参考图（+ 可选 controlnet 图） |
| 02 | [../t2i-camera/02-configure.md](../t2i-camera/02-configure.md) | 同 t2i |
| 03 | [03-patch.md](03-patch.md) | 复用 t2i prepare_temporary_workflow + apply_run_config 流程 + i2i 独有 img2img 激活 |
| 04 | [../t2i-camera/04-validate.md](../t2i-camera/04-validate.md) | 同 t2i |
| 05 | [../t2i-camera/05-submit.md](../t2i-camera/05-submit.md) | 同 t2i |
| 06 | [../t2i-camera/06-record.md](../t2i-camera/06-record.md) | 同 t2i（stage 字段为 "i2i-camera"） |

## 命令示例

```bash
python -m runtime.runtime_cli run-i2i \
  --envelope path/to/anima-envelope.json \
  --reference /tmp/source.png \
  --camera "direction=front,elevation=high,distance=cowboy_shot" \
  --sampling-steps-first 50 \
  --image-size "width=1024,height=1280" \
  --lora "add_detail,masterpiece"
```

注意 `--reference` 是 i2i 唯一专属 flag；其它 flag 与 t2i 共享同一 `CONFIG_FLAGS` 表。

## 运行时模块入口

```
runtime_cli.cmd_run_i2i
  -> _kwargs_to_run_config (CLI bridge)
  -> i2i_camera.run_i2i(mcp, output_dir, config: RunConfig)
       -> prompt_forge_bridge.compile_envelope  (硬性闸门)
       -> if config.reference_image: mcp.upload_image(reference_image)
       -> if config.controlnet_image: mcp.upload_image(controlnet_image)
       -> source_workflow.prepare_temporary_workflow(mcp, stage=I2I, user_g1, user_g2)
            -> 加载图片（G1） 自动 enable (MANDATORY_GROUPS_BY_STAGE[I2I])
            -> strip 出 API graph
       -> graph_patcher.apply_run_config(graph, stage=I2I, config, mcp_list_loras)
            -> 同 t2i 7 个值写入
            -> WORKFLOW_CONVENTIONS[I2I] 强制 node 27.denoise=0.6
            -> _activate_img2img: 重连 node 21/27/59（节点 id 来自 I2I_NODES）
       -> mcp.validate / mcp.check_runtime / mcp.enqueue
       -> mcp.get_history (text/dict dual-format parse)
       -> mcp.get_image (multipart content list)
       -> record_attempt (run-record.json schema_version 2.0)
```