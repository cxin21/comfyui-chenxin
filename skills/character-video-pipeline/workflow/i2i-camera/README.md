# i2i-camera 流程（图生图）

图像到图像的相机视角生成流程。与 t2i-camera 共用同一份 `workflow.json` + `groups.json`，区别在于第一步上传参考图，且 patch 时激活 img2img 路径。

## 与 t2i-camera 的差异

| 方面 | t2i-camera | i2i-camera |
|------|-----------|------------|
| 步骤 01 | MCP 查询（discover） | MCP 上传参考图（upload） |
| patch | 不激活 img2img | 激活 node 21/57/58/59 + 切换 node 75 |
| 工作流资产 | `t2i-camera/workflow.json` | `i2i-camera/workflow.json`（同一份复制） |
| groups.json | `t2i-camera/groups.json` | `i2i-camera/groups.json`（同一份复制） |

步骤 02-06 与 t2i-camera 完全一致，参考 [t2i-camera/](../t2i-camera/) 对应文档。

## 可配置项

与 t2i-camera 相同，增加 `reference_image`（必填）。

| 配置项 | 节点 | 必填 | 说明 |
|--------|------|------|------|
| `positive` | 24 | 是 | 正向提示词 |
| `negative` | 25 | 是 | 负向提示词 |
| `reference_image` | 21 | 是 | 上传后的图片名 |
| `camera.*` | 583 | 否 | 同 t2i |
| `camera_extra.*` | 585 | 否 | 同 t2i |
| `lora_selections` | 26/66 | 否 | 同 t2i |
| `enabled_g1/g2` | - | 否 | 同 t2i |

## 步骤

| 步骤 | 文件 | 说明 |
|------|------|------|
| 01 | [01-upload.md](01-upload.md) | MCP upload_image 上传参考图 + patch 激活 img2img |
| 02 | [../t2i-camera/02-configure.md](../t2i-camera/02-configure.md) | 同 t2i |
| 03 | [../t2i-camera/03-patch.md](../t2i-camera/03-patch.md) | 同 t2i（额外激活 img2img 路径） |
| 04 | [../t2i-camera/04-validate.md](../t2i-camera/04-validate.md) | 同 t2i |
| 05 | [../t2i-camera/05-submit.md](../t2i-camera/05-submit.md) | 同 t2i |
| 06 | [../t2i-camera/06-record.md](../t2i-camera/06-record.md) | 同 t2i（stage 字段为 "i2i-camera"） |

## 命令示例

```bash
python -m runtime.runtime_cli run-i2i \
  --positive "1girl, solo, outdoor, sunlight" \
  --negative "lowres, bad anatomy, bad hands" \
  --reference path/to/reference.png \
  --camera "direction=front,elevation=eye-level,distance=full_body" \
  --loras "add_detail,anima-base-1-masterpiece-v51"
```

## 运行时模块入口

```
runtime_cli.cmd_run_i2i -> i2i_camera.run_i2i
  -> mcp.upload_image -> patch_graph(reference_image=...) -> mcp.validate/enqueue -> download -> record
```
