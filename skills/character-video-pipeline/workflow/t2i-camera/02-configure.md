# 02-configure：组装配置

将用户输入组装为 `patch_graph()` 的参数。所有配置项有默认值，仅 `positive` 和 `negative` 必填。

## 配置项

### positive / negative（必填）

正负提示词文本，写入 node 24/25 的 `wildcard_text` 和 `populated_text` 字段。空字符串会被拒绝。

### camera（可选，默认 front/eye-level/full_body/0）

```python
camera = {
    "direction": "front",      # front|right|back|left|right_45|left_45|rear_45
    "elevation": "eye-level",  # high|eye-level|low
    "distance": "full_body",   # extreme_close_up|close_up|medium|cowboy_shot|full_body|wide
    "roll": 0.0,               # float [0.0, 1.0]
}
```

`camera_mapper.map_camera()` 将语义值映射为 node 583 的 `pos_x/pos_y/pos_z/roll` 坐标。

### camera_extra（可选，13 字段各有默认）

```python
camera_extra = {
    "extreme_type": "无",            # 无|极限俯视|极限仰视
    "extreme_weight": 10,           # non-negative number
    "lens_enabled": True,           # bool
    "lens_value": "85mm lens",      # str
    "dof_enabled": False,           # bool
    "dof_value": "shallow depth of field",  # str
    "dof_weight": 1.3,             # non-negative number
    "movement_enabled": False,      # bool
    "movement_value": "handheld camera",    # str
    "composition_enabled": True,    # bool
    "composition_value": "rule of thirds", # str
    "style_enabled": False,         # bool
    "style_value": "cinematic",     # str
}
```

`camera_mapper.validate_camera_extra()` 填充默认值并校验类型。

### lora_selections（可选，默认 3-LoRA 栈）

```python
lora_selections = ["add_detail", "anima-base-1-masterpiece-v51"]
```

不提供时使用默认栈：
```
<lora:anima-base-1-masterpiece-v51:1.00><lora:add_detail:1.00><lora:gpt-image-2_anima-base1_v1-1:1.00>
```

提供时通过 MCP `list_local_models` 查询 Anima LoRA 清单，`lora_resolver.resolve_lora_names()` 做短名匹配（`add_detail` 匹配 `Anima\add_detail.safetensors`）。

### enabled_g1 / enabled_g2（可选，按组标题）

```python
enabled_g1 = ["保存图片（G1）", "第二轮采样器（G1）", "相机视角生图（G1）"]
enabled_g2 = ["图像锐化（G2）", "对比度（G2）"]
```

用户提供的组与默认启用组合并（并集）。未在启用集中的组成员节点被设为 bypass（mode=4），但受保护的核心节点（sampler/saver/camera/prompts/LoRA/VAE）永远不会被 bypass。

## 输出

组装好的配置字典，传入 `patch_graph()`。
