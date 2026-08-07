# 03-patch：与 t2i-camera 共享同一 patch_graph 流程

i2i-camera 复用 `patch_graph(stage=STAGES.I2I, config: RunConfig)` —— 完整流程见 [`../t2i-camera/03-patch.md`](../t2i-camera/03-patch.md)。

i2i 独有的 patch_graph 步骤（在通用 11 步之后追加）：

- **步骤 11 (i2i only)**：require `config.reference_image` 非空；调用 `_activate_img2img(graph, reference_image)` 重连：
    - 节点 21 (LoadImage) `image` ← 上传后的 filename
    - 节点 59 (VAEEncode) `pixels` ← `[21, 0]`
    - 节点 27 (KSampler) `latent_image` ← `[59, 0]`
    - 节点 27 (KSampler) `denoise` ← 0.6
    - 节点 21/57/58/59 mode ← 0 (active)

  以上节点 ID 来自 `I2I_NODES` 常量表（不是硬编码字面量）。

- **i2i 硬约定**：`WORKFLOW_CONVENTIONS[STAGES.I2I]` 强制 `node 27.denoise = 0.6`（与 `_activate_img2img` 内部赋值是同一约束的两次应用；先于 group activation 应用，确保即使 i2i 链路被中途截断也保持参考图语义）。
