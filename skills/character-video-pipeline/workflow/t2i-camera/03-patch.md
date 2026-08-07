# 03-patch：patch_graph() 写入固定 API 图

`graph_patcher.patch_graph()` 加载 `workflow.json` 并原地修改节点输入。不经过 strip，不经过 UI-to-API 转换。

## 加载固定资产

```python
graph = load_workflow("t2i-camera")    # workflow/t2i-camera/workflow.json
groups_meta = load_groups("t2i-camera")  # workflow/t2i-camera/groups.json
```

`workflow_loader.py` 直接读取 JSON 文件，返回 dict。文件是已验证的 API 格式图。

## patch 步骤

### 1. 提示词（node 24/25）

```python
_set_prompt(graph, "24", positive)  # node 24: ImpactWildcardProcessor
_set_prompt(graph, "25", negative)  # node 25: ImpactWildcardProcessor
```

写入 `wildcard_text` 和 `populated_text` 两个字段。

### 2. 相机坐标（node 583）

```python
coords = map_camera(direction, elevation, distance, roll)
_set_camera(graph, coords)  # node 583: CameraAngleNode
```

写入 `pos_x`、`pos_y`、`pos_z`、`roll` 四个 FLOAT 字段。

### 3. 相机额外配置（node 585）

```python
extra = validate_camera_extra(camera_extra)
_set_camera_extra(graph, extra)  # node 585: CameraExtraConfigNode
```

写入 13 个字段（extreme_type, extreme_weight, lens_*, dof_*, movement_*, composition_*, style_*）。

### 4. LoRA 栈（node 26/66）

```python
lora_patch = build_lora_patch(lora_selections, mcp_list_loras)
_set_lora(graph, lora_patch)
```

- node 26（Lora Loader）：写入 `text` 字段，值为 `<lora:name:strength>` 格式的栈文本
- node 66（TriggerWord Toggle）：写入 `trigger_words`（连接引用 `["26", 2]`）和 `orinalMessage`

### 5. G1/G2 组模式

```python
final_g1 = list(set((enabled_g1 or []) + DEFAULT_ENABLED_G1))
final_g2 = list(set((enabled_g2 or []) + DEFAULT_ENABLED_G2))
graph = apply_group_modes(graph, groups_meta, final_g1, final_g2)
```

`group_controller.apply_group_modes()` 遍历 groups.json 中的组标题：
- 在启用集中的组 -> 成员节点 mode=0（active）
- 不在启用集中的组 -> 成员节点 mode=4（bypass）
- **受保护节点**（sampler/saver/camera/prompts/LoRA/VAE 等 30 个节点）永远 mode=0

### 6. img2img 激活（仅 i2i-camera）

t2i-camera 跳过此步。i2i-camera 调用 `_activate_img2img(graph, image_name)`：
- node 21/57/58/59 设为 mode=0（active）
- node 21 的 `image` 字段设为上传后的图片名
- node 75（ImpactSwitch）`select` 设为 0（路由到 VAEEncode 而非 EmptyLatent）

## 输出

返回完整的 patched API 图 dict，传入 04-validate 步骤。
