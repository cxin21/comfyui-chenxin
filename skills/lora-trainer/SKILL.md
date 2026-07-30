---
name: lora-trainer
description: "Anima LoRA 训练编排 (v2.2) — 单路径：gazingstars123/Anima-Standalone-Trainer 独立 venv。8GB VRAM 友好，无需 ComfyUI 在线。Also load chenxin-core first for VRAM/recipe context."
version: 2.3.0
author: Claude Code
triggers:
  - "训练 LoRA"
  - "训 LoRA"
  - "训 Anima LoRA"
  - "train LoRA"
  - "lora training"
  - "训角色"
  - "训场景"
allowed-tools: Bash, Read, Write, "mcp__comfyui__*"
---

# Lora Trainer — Anima LoRA 训练编排 (v2.3, ported)

> **Plugin path**: `skills/lora-trainer/SKILL.md`
> **Upstream**: L5 application skill. Load `chenxin-core` (L4) first for VRAM/recipe context —
> this skill targets Anima 1.0 (~2B Cosmos DiT) so VRAM/quant choices from
> `hardware/8gb.json` directly affect training defaults.

## 1. 工具概览

| 维度 | 值 |
|------|-----|
| **工具** | [gazingstars123/Anima-Standalone-Trainer](https://github.com/gazingstars123/Anima-Standalone-Trainer) |
| **路径** | `E:/Comfy/Anima-Standalone-Trainer` |
| **venv** | `E:/Comfy/Anima-Standalone-Trainer/venv`（Python 3.12 + torch 2.7 + CUDA 12.8） |
| **入口脚本** | `skills/lora-trainer/scripts/train-anima-standalone.sh` |
| **训练入口** | `accelerate launch anima_train_network.py --config_file <toml>` |
| **VRAM** | < 6GB（Anima 小模型 + fused QKV + TP/SP 优化） |
| **ComfyUI 依赖** | **不需要**（独立 venv） |
| **配置方式** | toml 文件（训练 + 数据集分离） |
| **Web UI** | `training-ui/start_training_ui_anima.bat` → `http://localhost:3000` |

## 2. 触发词

```
"训练 LoRA" / "训 LoRA" / "train LoRA" / "lora training" / "训 Anima LoRA" / "训角色" / "训场景"
```

## 3. 必需模型

| 模型 | 路径 | 大小 |
|------|------|------|
| DiT | `E:/Comfy/comfyui-licyk-20260608/core/models/checkpoints/anima_baseV10.safetensors` | 4.18GB |
| Qwen3 TE | `E:/Comfy/comfyui-licyk-20260608/core/models/text_encoders/qwen_3_06b_base.safetensors` | 1.19GB |
| VAE | `E:/Comfy/comfyui-licyk-20260608/core/models/vae/qwen_image_vae.safetensors` | 254MB |

## 4. 入口命令

```bash
# 最小可用
bash skills/lora-trainer/scripts/train-anima-standalone.sh \
  --name <name> --refs "<refs_dir>"

# 自定义参数 + deploy 到 ComfyUI loras/
bash skills/lora-trainer/scripts/train-anima-standalone.sh \
  --name ninghongye --refs "E:/Comfy/LoRA/永劫-宁红夜" \
  --epochs 10 --lr 3e-5 --resolution 768,768 --deploy

# 复用已有 toml（不覆盖）
bash skills/lora-trainer/scripts/train-anima-standalone.sh \
  --name <name> --refs <dir> --train-toml <path> --no-auto-toml
```

完整参数：`--help` 查看（支持 `--name` / `--refs` / `--output` / `--train-toml` / `--dataset-toml` / `--epochs` / `--lr` / `--dim` / `--alpha` / `--resolution` / `--seed` / `--deploy` / `--log-dir` / `--no-auto-toml` / `--dry-run`）。

## 5. 输入参数

| 参数 | 必需 | 默认 | 说明 |
|------|------|------|------|
| `--name` | ✅ | - | LoRA 名称（用于文件命名 + trigger word） |
| `--refs` | ✅ | - | 参考图目录 |
| `--output` | ❌ | `<tool>/output/<name>` | 输出目录 |
| `--train-toml` | ❌ | `<tool>/train_<name>.toml` | 训练 toml（默认自动生成） |
| `--dataset-toml` | ❌ | `<tool>/dataset_<name>.toml` | 数据集 toml（默认自动生成） |
| `--epochs` | ❌ | 5 | 训练轮数 |
| `--lr` | ❌ | 5e-5 | 学习率 |
| `--dim` | ❌ | 16 | LoRA dim |
| `--alpha` | ❌ | 16 | LoRA alpha |
| `--resolution` | ❌ | 1024,1024 | 分辨率（8GB VRAM 友好降到 768,768） |
| `--seed` | ❌ | 42 | 随机种子 |
| `--deploy` | ❌ | false | 训练完后 deploy 到 ComfyUI loras/ |
| `--log-dir` | ❌ | `<tool>/output/<name>/logs` | 日志目录 |
| `--no-auto-toml` | ❌ | false | 不自动生成 toml（仅用已有的） |
| `--dry-run` | ❌ | false | 只显示要跑的命令 |

## 6. 前置检查

- 参考图 ≥ 5 张（**实测 2 张也能跑，仅供流程验证**；30+ 张才是生产质量门槛）
- venv 完整（`E:/Comfy/Anima-Standalone-Trainer/venv/Scripts/python.exe` + `accelerate.exe`）
- 三个模型文件存在（DiT + Qwen3 + VAE）

## 7. 自动 caption

缺失 `.txt` 时自动用模板生成（trigger word + 通用描述）：

```bash
"{name}, 1girl, detailed face, high quality, intricate detail"
```

可手动编辑 `<image_basename>.txt` 自定义。

## 8. 自动 toml

缺失 `train_<name>.toml` + `dataset_<name>.toml` 时自动生成：

- `train_<name>.toml`：`[model_arguments]` + `[dataset_arguments]` + `[training_arguments]` + `[anima_arguments]` + `[network_arguments]`
- `dataset_<name>.toml`：`[general]` (enable_bucket, min/max_bucket_reso) + `[[datasets]]` subsets (image_dir, num_repeats=10, caption_extension=".txt")

## 9. 测试图生成

5 个场景（自动用 `templates/test-prompts.yaml`）：

| 序号 | 风格 | filename_prefix |
|------|------|----------------|
| 001 | realistic | `<name>_test_001_realistic` |
| 002 | anime | `<name>_test_002_anime` |
| 003 | cinematic | `<name>_test_003_cinematic` |
| 004 | oilpaint | `<name>_test_004_oilpaint` |
| 005 | digitalart | `<name>_test_005_digitalart` |

每个 prompt 替换 `{trigger_word}` 占位符。

## 10. 评分与验证

```bash
# 用 aesthetic-judge skill 评分
# 5 张图：
#   总分 ≥ 7/10 → lora_verified: true
#   总分 < 7/10 → 调整 LoRA 强度/重训/换 trigger_word
```

**lora_verified** 必须写入 `02_assets/<target>/04_metadata.yaml.lora_verified`。

## 11. 输出 metadata 示例

```yaml
# 02_assets/<target>/04_metadata.yaml
name: ninghongye
arch: anima
trigger_word: ninghongye
lora_path: E:/Comfy/Anima-Standalone-Trainer/output/ninghongye/ning_hong_ye_v1.safetensors
lora_strength: 0.8
lora_verified: true
trained_at: 2026-07-28
training_tool: anima-standalone-trainer
training_params:
  epochs: 5
  network_dim: 16
  network_alpha: 16
  learning_rate: 5e-5
  min_refs: 5
test_generations: 02_assets/<target>/05_test_generations/
  - file: ninghongye_test_001_realistic.png
    score: 7.5
    verified: true
```

## 12. 架构

| 阶段 | 谁做 | 工具 |
|------|------|------|
| 检查参考图 | bash | `scripts/validate-refs.sh` |
| Caption 自动生成 | bash | 缺失时用 trigger word 模板 |
| Toml 自动生成 | bash | 缺失时生成训练 + 数据集 toml |
| 训练 | bash | `scripts/train-anima-standalone.sh` → `accelerate-launch` |
| 测试图 | Agent | `mcp__comfyui__generate_image` × 5 |
| 评分 | Agent | `aesthetic-judge` skill |
| deploy | bash | `scripts/train-anima-standalone.sh --deploy` |

## 13. 已知 Caveats

1. **数据量影响质量**：< 5 张图训练效果弱（仅供流程验证）；30+ 张图才能产出可用 LoRA
2. **Web UI 与 ComfyUI 不冲突**：Web UI (3000) vs ComfyUI (8188) 端口独立
3. **VRAM 共享**：独立 venv，但 ComfyUI 在线时仍共享 GPU（8GB 限制下需注意）
4. **lora_verified 必要**：未通过评分不能进入 Stage 2
5. **caption 模板可改**：自动生成的 .txt 是模板，复杂场景应手动编辑或用 WD14 Tagger

## 14. 版本

- **v2.3.0**（2026-07-30）：P1.1 ported — frontmatter 声明 chenxin-core 上游；路径全部改为 plugin 内
- v2.2.0（2026-07-28）：单路径（Anima Standalone Trainer only）；删除路径 A/B/C 相关 helper（`train-sd.sh`、`train-anima.sh`、`convert-anima.sh`、`deploy-lora.sh`、`path-detector.sh`）；SKILL.md 大幅简化
- v2.1.0（2026-07-27）：新增路径 D（4 路径并行）；默认推荐从 B 改 D
- v2.0.0（2026-07-27）：3 路径并行（lora-scripts / anima-lora-trainer / ai-toolkit-trainer）
- v1.0.0（旧）：仅 lora-scripts（kohya-ss）单路径

## 15. 相关引用

- **上游**: `skills/chenxin-core/SKILL.md`（L4 — 必须先加载 for VRAM/recipe）
- 工具：[gazingstars123/Anima-Standalone-Trainer](https://github.com/gazingstars123/Anima-Standalone-Trainer)
- 上游: `skills/manga-orchestrator/SKILL.md` (Stage 0)
- 下游: `skills/manga-stage-2-panels/SKILL.md` (Stage 2)
- 评分器: `aesthetic-judge` skill
