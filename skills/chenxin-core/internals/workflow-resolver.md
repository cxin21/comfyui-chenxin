# workflow_resolver.md — 工作流锁定与节点映射

> 跨 skill 共享：manga-stage-2-panels（AnimaStandardV7）、manga-stage-4-motion（LTX 2.3）、manga-stage-5-talking-head（LTX 2.3）。
> **不再动态探测**。工作流固定为两个，节点映射硬编码。

## 1. 工作流锁定

| 用途 | 工作流文件 | 节点数 | 说明 |
|------|-----------|--------|------|
| **文生图** | `AnimaStandardV7.json` | 73 | 含 Detailer + hiresFix + GLSL 后处理 |
| **文/图/视频生视频** | `ltx23AllInOneWorkflowForRTX_v44.json` | 78 | LTX-2.3 GGUF 量化，自带音频生成 |

**不允许使用其他工作流。** 如需切换，必须先修改本文件并同步所有引用方。

## 2. AnimaStandardV7.json 节点映射

### 可修改节点（白名单）

| 节点 ID | class_type | widget | 当前默认值 | 用途 |
|---------|-----------|--------|-----------|------|
| **3** | `ImpactWildcardProcessor` "POSITIVE" | `wildcard_text` | （见工作流） | 正向提示词 |
| **4** | `ImpactWildcardProcessor` "NEGATIVE" | `wildcard_text` | `worst quality,low quality,score_1,score_2,score_3,artist name,blurry,jpeg artifacts,lowres,censor` | 反向提示词 |

### 只读节点（了解但不修改）

| 节点 ID | class_type | 关键 widget | 当前值 | 说明 |
|---------|-----------|------------|--------|------|
| 1 | `UNETLoader` | `unet_name` | `miaomiaoHarem_anima15.safetensors` | Anima 基础模型 |
| 5 | `Lora Loader (LoraManager)` | 无可见 widget | LoraManager 管理 | 固定 3 个 LoRA |
| 18 | `CLIPLoader` | `clip_name` | `qwen_3_06b_base.safetensors` | 文本编码器 |
| 23 | `VAELoader` | `vae_name` | `qwen_image_vae.safetensors` | VAE 解码器 |
| 24 | `Input Parameters (Image Saver)` | `steps`/`cfg`/`sampler`/`scheduler` | 30 / 4.5 / dpmpp_2m / karras | 采样参数 |
| 39 | `easy int` "Width" | `value` | 832 | 分辨率宽 |
| 47 | `easy int` "Height" | `value` | 1216 | 分辨率高 |
| 6 | `KSampler` | - | - | 主采样器 |
| 22 | `DetailerForEach` | `steps`/`denoise` | 18 / 0.24 | 通用细节增强 |
| 27 | `FaceDetailerPipe` "HandDetailer" | `steps`/`denoise` | 16 / 0.4 | 手部修复 |
| 28 | `FaceDetailerPipe` "NSFWDetailer" | `steps`/`denoise` | 16 / 0.3 | NSFW 修复 |
| 29 | `FaceDetailerPipe` | `steps`/`denoise` | 16 / 0.26 | 面部修复 |
| 59 | `easy hiresFix` | `model_name`/`width`/`height` | 4x_foolhardy_Remacri / 1024 / 1024 | 高分辨率放大 |

### 数据流概览

```
UNETLoader(1) → LoraManager(5) → CFGZeroStar(49) → KSampler(6)
CLIPLoader(18) → LoraManager(5) → CLIPTextEncode(54/55)
ImpactWildcard(3/4) → StringConcat(46/48/51) → CLIPTextEncode(54/55)
KSampler(6) → VAEDecode(43) → hiresFix(59) → DetailerForEach(22)
DetailerForEach(22) → HandDetailer(27) → NSFWDetailer(28) → FaceDetailer(29)
FaceDetailer(29) → hiresFix(60) → AdjustContrast(62) → ImageSharpen(72) → GLSL(435/419/423)
```

### modify_workflow 模板

```python
operations = [
    {"op": "set_input", "node_id": "3", "input_name": "wildcard_text", "value": positive_prompt},
    {"op": "set_input", "node_id": "4", "input_name": "wildcard_text", "value": negative_prompt}
]
```

## 3. ltx23AllInOneWorkflowForRTX_v44.json 节点映射

### 可修改节点（白名单）

| 节点 ID | class_type | widget | 当前默认值 | 用途 |
|---------|-----------|--------|-----------|------|
| **121** | `CLIPTextEncode` "positive" | `text` | （见工作流） | 正向提示词 |
| **593** | `CLIPTextEncode` "negative" | `text` | `animation, cartoon` | 反向提示词 |
| **149** | `LoadImage` "First Frame" | `image` | （上次使用的首帧） | 首帧图片（图生视频） |
| **1792** | `PrimitiveInt` "Longer Edge" | `value` | 2000 | 视频较长边分辨率 |
| **1793** | `PrimitiveInt` "Clip Length" | `value` | 10 | 视频时长（秒） |

### 只读节点（了解但不修改）

| 节点 ID | class_type | 关键 widget | 当前值 | 说明 |
|---------|-----------|------------|--------|------|
| 366 | `UnetLoaderGGUF` | `unet_name` | `ltx-2.3-22b-distilled-Q4_K_M.gguf` | LTX-2.3 GGUF 量化模型 |
| 146 | `DualCLIPLoader` | `type` | `ltxv` | 双 CLIP 编码器 |
| 591 | `VAELoader` | `vae_name` | `taeltx2_3.safetensors` | 视频 VAE |
| 174 | `VAELoaderKJ` "Video" | `vae_name` | `LTX23_video_vae_bf16.safetensors` | 视频 VAE（bf16） |
| 175 | `VAELoaderKJ` "Audio" | `vae_name` | `LTX23_audio_vae_bf16.safetensors` | 音频 VAE |
| 211 | `Power Lora Loader` | `lora_1`/`lora_2` | LTX 动态 LoRA + detailer LoRA | 视频 LoRA |
| 869 | `JWInteger` "Framerate" | `value` | （帧率） | 输出帧率 |
| 1805/1809/1819 | `LTXVImgToVideoInplace` | `strength` | 0.8 | 图生视频强度 |

### 数据流概览

```
LoadImage(149) → ImageScaleByAspectRatio(1797) → LTXVPreprocess(1863) → LTXVImgToVideoInplace(1805)
UnetLoaderGGUF(366) → PowerLoraLoader(211) → LTXVChunkFeedForward(700)
DualCLIPLoader(146) → CLIPTextEncode(121/593)
LTXVImgToVideoInplace(1805/1809) → LTXVConcatAVLatent(1799) → SamplerCustomAdvanced(1830)
SamplerCustomAdvanced(1830) → LTXVSeparateAVLatent(1893) → LTXVLatentUpsampler(1887)
→ 二次采样(1888) → LTXVSeparateAVLatent(1889) → VAEDecodeTiled(1884) + LTXVAudioVAEDecode(1891)
→ VHS_VideoCombine(188) [视频+音频]
```

### modify_workflow 模板

```python
# 图生视频模式
operations = [
    {"op": "set_input", "node_id": "149", "input_name": "image", "value": first_frame_filename},
    {"op": "set_input", "node_id": "121", "input_name": "text", "value": positive_prompt},
    {"op": "set_input", "node_id": "593", "input_name": "text", "value": negative_prompt},
    {"op": "set_input", "node_id": "1792", "input_name": "value", "value": longer_edge},
    {"op": "set_input", "node_id": "1793", "input_name": "value", "value": clip_length}
]

# 文生视频模式（不改首帧）
operations = [
    {"op": "set_input", "node_id": "121", "input_name": "text", "value": positive_prompt},
    {"op": "set_input", "node_id": "593", "input_name": "text", "value": negative_prompt},
    {"op": "set_input", "node_id": "1792", "input_name": "value", "value": longer_edge},
    {"op": "set_input", "node_id": "1793", "input_name": "value", "value": clip_length}
]
```

## 4. 工作流配置守护

所有 modify_workflow 操作必须遵循 `_shared/workflow_config_guard.md` 的四步闭环：

1. **备份**：query_workflow 读取白节点当前值
2. **修改**：仅 set_input 白名单节点
3. **执行**：enqueue_workflow + get_job_status + get_image
4. **恢复**：set_input 恢复备份值 + query_workflow 验证

## 5. manifest.json 持久化

```json
{
  "workflow": "AnimaStandardV7.json",
  "workflow_locked": true,
  "workflow_node_count": 73,
  "workflow_family": "anima",
  "workflow_resolved_at": "2026-07-26T10:30:00+08:00"
}
```

## 6. 已知约束

1. **LoraManager 无 widget**：AnimaStandardV7 的 LoRA 走 LoraManager 外部协议，不通过 modify_workflow 修改
2. **LTX Power Lora Loader**：2 个 LoRA 槽位已配 LTX 专用 LoRA，不建议修改
3. **LTX Clip Length 节点 1793**：当前未连接到下游，实际帧数可能由其他节点控制
4. **分辨率由 ImageScaleByAspectRatio 控制**：LTX 工作流中，节点 1792 的 `value` 是较长边像素，实际分辨率由 `ImageScaleByAspectRatio V2` 按比例计算
