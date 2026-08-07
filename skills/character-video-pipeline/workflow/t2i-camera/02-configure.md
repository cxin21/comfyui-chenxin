# 02-configure：组装配置

将用户输入组装为 `RunConfig`（单一入口配置对象）。`RunConfig` 内部包含 5 个可选的子-dataclass（`CameraConfig` / `SamplingConfig` / `ImageSizeConfig` / `GroupsConfig` / `camera_extra dict`）；任何 `None` 字段都落回 `workflow.json` 静态值。

## 配置项

### envelope（必填，提示词闸门）

```python
from runtime.config_schema import (
    RunConfig, SamplingConfig, ImageSizeConfig, GroupsConfig, CameraConfig,
)

config = RunConfig(
    evidence={...},        # CreativeEvidence ledger
    draft={...},            # caller-authored {"positive": "...", "negative": "..."}
    dialect_id="anima",      # 默认 anima
    strict_prompt=False,    # True 时 ready_for_review==False 直接抛错

    # 可选 tunables (None = 用 workflow.json 静态值)
    camera=CameraConfig(direction="front", elevation="high", distance="cowboy_shot", roll=0.0),
    camera_extra={"lens_value": "85mm lens", "composition_value": "rule of thirds"},
    lora={"selections": ["add_detail", "anima-base-1-masterpiece-v51"]},
    groups=GroupsConfig(g1=["手部 ADetailer（G1）"], g2=["图像锐化（G2）"]),

    sampling=SamplingConfig(steps_first=50, cfg=7, sampler="dpmpp_2m",
                            scheduler="karras", denoise_first=1.0,
                            steps_refine=25, denoise_refine=0.2),
    seed=12345,
    image_size=ImageSizeConfig(width=1024, height=1280),

    controlnet_image=None,   # t2i + i2i: 启用 ControlNet LLLite 组时必填
    reference_image=None,    # i2i only: 必填
)

run_t2i(mcp=mcp, output_dir=Path("outputs"), config=config)
```

`run_t2i()` 第一行调用 `prompt_forge_bridge.compile_envelope`（或退路 `compile_or_minimal`），把 evidence/draft 喂给 `prompt-forge internals.prompt_compile`。校验通过的 PromptPackage.positive/negative 才进入 node 24/25 的 `wildcard_text` 和 `populated_text` 字段；空字符串会被 prompt-forge 拒绝。

evidence/draft 不得含 `camera / lora / sampler / cfg / steps / seed / denoise` 等执行字段（prompt-forge `_reject` 把关）。

`t2i-camera` 和 `i2i-camera` 共享同一份 `workflow.json` + `groups.json` + 同一 `RunConfig` schema。i2i 唯一额外要求是 `config.reference_image` 非空；i2i 模式下 `patch_graph` 自动 append `加载图片（G1）` 到 `groups.g1`。

### camera（可选，默认 front/eye-level/full_body/0）

通过 `CameraConfig(direction, elevation, distance, roll)` 传入。`camera_mapper.map_camera()` 将语义值映射为 node 583 的 `pos_x/pos_y/pos_z/roll` 坐标。

### camera_extra（可选，13 字段各有默认）

通过 dict 传入（自由 kv 结构）。`camera_mapper.validate_camera_extra()` 填充默认值并校验类型。

### lora（可选，默认 3-LoRA 栈）

通过 `{"selections": [short_name_or_full_filename, ...]}` 传入。`build_lora_patch()` 读取 `selections` 字段做短名匹配（`add_detail` 匹配 `Anima\add_detail.safetensors`）。

不提供时使用默认栈：
```
<lora:anima-base-1-masterpiece-v51:1.00><lora:add_detail:1.00><lora:gpt-image-2_anima-base1_v1-1:1.00>
```

### groups（可选，按组标题）

通过 `GroupsConfig(g1=[...], g2=[...])` 传入。用户提供的组与默认启用组合并（并集）。未在启用集中的组成员节点被设为 bypass（mode=4），但受保护的核心节点（sampler/saver/camera/prompts/LoRA/VAE）永远不会被 bypass。

### sampling（可选，7 字段各有默认）

通过 `SamplingConfig(steps_first, cfg, sampler, scheduler, denoise_first, steps_refine, denoise_refine)` 传入。覆盖 node 50/51（首轮 / refine KSampler）的字段。

### seed（可选，默认 random）

通过 `RunConfig.seed: int` 直接传入。写入 node 65。

### image_size（可选，默认 1216×832）

通过 `ImageSizeConfig(width, height)` 传入。写入 node 68/71 的 `value` 字段（easy int），再喂给 node 86 EmptyLatentImage。

### controlnet_image（可选，仅 ControlNet LLLite 组启用时必填）

通过 `RunConfig.controlnet_image: str` 传入本地路径；`run_t2i` 通过 `mcp.upload_image` 上传后再写入 node 129。如启用 ControlNet LLLite 组但未提供 image，patch_graph 抛 ValueError。

## 输出

组装好的 `RunConfig`，传入 `run_t2i(mcp=..., output_dir=..., config=...)`。