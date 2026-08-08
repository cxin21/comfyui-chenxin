# 03-patch：与 t2i-camera 共享 prepare_temporary_workflow + apply_run_config

i2i-camera 复用 t2i-camera 的两步 patch 流程，差异在第二阶段。

完整两步流程见 [`../t2i-camera/03-patch.md`](../t2i-camera/03-patch.md)。

## i2i 独有阶段（在 apply_run_config 内追加）

`apply_run_config(graph, stage=STAGES.I2I, config)` 末尾会：

1. **校验** `config.reference_image` 非空，否则抛 `ValueError`。
2. **重连**（节点 id 来自 `I2I_NODES`）：
   - 节点 21 (LoadImage) `image` ← 上传后的 filename
   - 节点 59 (VAEEncode) `pixels` ← `[21, 0]`
   - 节点 27 (KSampler) `latent_image` ← `[59, 0]`
   - 节点 27 (KSampler) `denoise` ← 0.6
3. **i2i 硬约定**：`WORKFLOW_CONVENTIONS[STAGES.I2I]` 在写入 controlnet_image 后再次强制 `node 27.denoise = 0.6`（双保险）。

## 加载图片（G1） 来源

`MANDATORY_GROUPS_BY_STAGE[STAGES.I2I] = [GROUPS.LOAD_IMAGE]` 在 `compute_enabled_groups` 阶段加入最终 G1 启用集。运行时把节点 21/57/58/59 的 mode 写为 0（启用），再 strip 出 API graph——所以这些节点必然出现在 strip 后的 API 图里，`_activate_img2img` 才能安全地重连它们。