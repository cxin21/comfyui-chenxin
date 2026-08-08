# 03-patch：patch_graph() 写入固定 API 图

`graph_patcher.patch_graph(*, stage, config: RunConfig, mcp_list_loras=None)` 加载 `workflow.json` 并原地修改节点输入。不经过 strip，不经过 UI-to-API 转换。

## 加载固定资产

```python
graph = load_workflow(stage)        # workflow/<stage>/workflow.json
groups_meta = load_groups(stage)    # workflow/<stage>/groups.json
```

`workflow_loader.py` 直接读取 JSON 文件，返回 dict。文件是已验证的 API 格式图。

## patch 步骤

### 1. 提示词（node 24/25）

```python
_set_prompt(graph, "24", config.draft["positive"].strip())
_set_prompt(graph, "25", config.draft["negative"].strip())
```

写入 `wildcard_text` 和 `populated_text` 两个字段。

> `config.draft` 由 `run_t2i()` 内 `prompt_forge_bridge.compile_envelope` 校验通过后传入 patch_graph；evidence/draft 不得含 `camera / lora / sampler / cfg / steps / seed / denoise` 等执行字段（prompt-forge `_reject` 把关）。

### 2. 相机坐标（node 583）

```python
coords = map_camera(config.camera.direction or "front",
                    config.camera.elevation or "eye-level",
                    config.camera.distance or "full_body",
                    float(config.camera.roll or 0.0))
_set_camera(graph, coords)  # node 583: CameraAngleNode
```

写入 `pos_x`、`pos_y`、`pos_z`、`roll` 四个 FLOAT 字段。

### 3. 相机额外配置（node 585）

```python
extra = validate_camera_extra(config.camera_extra)
_set_camera_extra(graph, extra)  # node 585: CameraExtraConfigNode
```

写入 13 个字段（extreme_type, extreme_weight, lens_*, dof_*, movement_*, composition_*, style_*）。

### 4. LoRA 栈（node 26/66）

```python
lora_patch = build_lora_patch(run_config_lora=config.lora,
                              mcp_list_loras=mcp_list_loras)
_set_lora(graph, lora_patch)
```

- node 26（Lora Loader）：写入 `text` 字段，值为 `<lora:name:strength>` 格式的栈文本
- node 66（TriggerWord Toggle）：写入 `trigger_words`（连接引用 `["26", 2]`）和 `orinalMessage`

### 5. sampling / seed / image_size（node 50/51/65/68/71）

```python
if config.sampling:    _apply_sampling(graph, config.sampling)   # node 50/51
if config.seed is not None: _apply_seed(graph, config.seed)       # node 65
if config.image_size:  _apply_image_size(graph, config.image_size) # node 68/71
```

`_apply_*` 辅助函数按字段写入；`None` 字段落回 workflow.json 静态值（默认 40 / 25 steps、1.0 / 0.2 denoise、dpmpp_2m / karras、1216 × 832）。

### 6. G1/G2 组模式

```python
final_g1 = list(set(user_g1) | DEFAULT_ENABLED_G1 | MANDATORY_GROUPS_BY_STAGE[stage])
final_g2 = list(set(user_g2) | DEFAULT_ENABLED_G2)
graph = apply_group_modes(graph, groups_meta, final_g1, final_g2)
```

`group_controller.apply_group_modes()` 遍历 groups.json 中的组标题：
- 在启用集中的组 -> 成员节点 mode=0（active）
- 不在启用集中的组 -> 成员节点 mode=4（bypass）
- **受保护节点**（sampler/saver/camera/prompts/LoRA/VAE 等 30 个节点）永远 mode=0

### 7. controlnet_image 校验 + 写入（node 129）

启用 ControlNet LLLite 组必须提供 `config.controlnet_image`，否则抛 `ValueError`；提供后通过 `_apply_controlnet_image(graph, uploaded_filename)` 写入 node 129。

### 8. WORKFLOW_CONVENTIONS 应用

例如 i2i 强制 `node 27.denoise = 0.6`（来自 `WORKFLOW_CONVENTIONS[STAGES.I2I]`），保证即使 i2i 链路被中途截断也保持参考图语义。

### 9. i2i-camera 流程

i2i-camera 流程详见 `../i2i-camera/03-patch.md`，此处不再重复。

## 输出

返回完整的 patched API 图 dict，传入 04-validate 步骤。

### patch_graph flow (2026-08-07)

`patch_graph(*, stage, config: RunConfig, mcp_list_loras=None)` 内部按以下顺序处理 RunConfig 字段：

1. load_workflow(stage) + load_groups(stage)
2. 写 prompts (24/25) from `config.draft` (prompt-forge 校验后)
3. 写 camera (583) + camera_extra (585) if set
4. 写 lora (26/66) via `build_lora_patch` if set
5. 写 sampling (50/51), seed (65), image_size (68/71) via `_apply_*` helpers
6. 合并 groups: `final_g1 = set(user_g1) | DEFAULT_ENABLED_G1 | MANDATORY_GROUPS_BY_STAGE[stage]`
7. cross-validate controlnet_image <-> ControlNet LLLite 组
8. `apply_group_modes(graph, groups_meta, final_g1, final_g2)`
9. 写 controlnet_image (129) if enabled
10. apply WORKFLOW_CONVENTIONS (e.g. i2i forces node 27.denoise=0.6)

NODE_FIELD_MAP（11 项）是 patcher 与 describe_config helper 的单源真相；workflow.json 静态值通过 `_node_static_default` 读取。