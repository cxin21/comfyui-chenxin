# 03-patch：source UI workflow -> temp strip -> apply_run_config

`run_t2i` 和 `run_i2i` 在 MCP 提交前分两步构建可执行 API 图：

1. **`source_workflow.prepare_temporary_workflow(mcp, stage, user_g1, user_g2)`**
   - 加载 `workflow/source/文生图相机视角.json`（UI workflow，141 节点 / 44 组）。
   - 计算最终启用的 G1/G2 组标题（DEFAULT + user + stage-mandatory）。
   - 在内存拷贝上对节点写 `mode=0`（启用）/ `mode=4`（禁用）。
   - 写入 `temp_*.json` 临时文件（系统 temp 目录）。
   - 调 `mcp.save_workflow(temp_filename, ui)` 上传到 ComfyUI user library。
   - 调 `mcp.strip_workflow(path=temp_filename, format="api")` 产出 API 图。
   - 删除本地临时文件。
   - 返回 API 图 dict（不含 `mode` 字段）。

2. **`graph_patcher.apply_run_config(graph, stage, config, mcp_list_loras)`**
   - 把 RunConfig 的 tunables 写入已 strip 的 API 图：
     - prompts (24/25) from `config.draft`（prompt-forge 校验后）
     - camera (583) + camera_extra (585) if set
     - lora (26/66) via `build_lora_patch` if set
     - sampling (50/51), seed (65), image_size (68/71)
     - controlnet_image (129) — 仅 ControlNet LLLite 组启用时
     - WORKFLOW_CONVENTIONS per stage（i2i 强制 `node 27.denoise=0.6`）
     - i2i 激活：node 21/27/59 latent rewire（节点 id 来自 `I2I_NODES`）

## 两步分离的关键设计

| 步骤 | 关注点 | 失败模式 |
|------|--------|----------|
| prepare_temporary_workflow | 节点启/禁（哪条 path 走） | 启错节点 → 渲染空图/渲染错图 |
| apply_run_config | 节点值（值是多少） | 值错 → 渲染错值，但 path 还在 |

任何一步失败都 `RuntimeError`，不静默降级。

## 为什么不用 cached workflow.json

旧实现缓存一份 API 图到 `workflow/<stage>/workflow.json`（42 节点），但：
- 该资产是 `commit 06c1739` revert 后的 stale 残留。
- API 图不携带 G1/G2 mode 信息；通过 patch_graph 在 API JSON 上改 `mode` 字段。
- strip_workflow 会丢弃 bypassed 节点——意味着旧 API JSON 已经被 strip 过了，再改 mode 字段没有意义。

正确路径：**完整 UI workflow**（保留所有节点和 mode 字段）→ 运行时改 mode → strip 出新 API JSON。