---
name: ffmpeg-pipeline
description: "AI 漫剧 Stage 5 — 字幕 + 视频拼接。Bash + ffmpeg CLI，零 MCP 依赖。从 Stage 4 mp4 + 对话文本生成 final.mp4。Also load chenxin-core first for VRAM/recipe context."
version: 1.1.0
author: Claude Code
triggers:
  - "加字幕"
  - "合成视频"
  - "concat"
  - "make final"
  - "stage 5"
  - "拼接视频"
allowed-tools: Bash, Read, Write
---

# FFmpeg Pipeline — AI 漫剧 Stage 5 (v1.1, ported)

> **Plugin path**: `skills/ffmpeg-pipeline/SKILL.md`
> **Upstream**: L5 application skill. Stage 5 of the manga pipeline. Although ffmpeg itself
> is model-agnostic (no ComfyUI involved), the `chenxin-core` L4 mega-skill should still be
> consulted upstream so the final output preserves any VRAM-tier codec choices made in
> Stage 4 (e.g. Q4 GGUF outputs may need re-encode before concat).

## 1. 任务

接收 Stage 4 输出（mp4 视频+音频）和 Stage 3 对话文本，生成**最终带字幕的连续视频 final.mp4**。

**纯 ffmpeg CLI** + Bash，**零 MCP 依赖**，**零 ComfyUI** 调用。

## 2. 4 步流水线

```
Stage 4 输出
  ├─ 04_outputs/02_micro_motion/scene_NN.mp4
  └─ 03_storyboard/03_prompts/scene_NN.md (含 dialogue)
                ↓
        bash scripts/bootstrap.sh --project-root <path> --stage manga-stage-3-review
                ↓
  ┌─────────────────────────────────────────┐
  │ Step 1: concat-list    ← 拼接 scene 列表 │
  │ Step 2: subtitles.srt  ← 从 dialogue 生成 SRT │
  │ Step 3: burn-subs      ← 字幕烧入（可选）│
  │ Step 4: concat + finalize               │
  └─────────────────────────────────────────┘
                ↓
  04_outputs/05_final/
    ├── final.mp4
    ├── final_with_subs.mp4
    ├── subtitles.srt
    └── manifest.json
```

## 3. 输入参数

| 参数 | 必需 | 默认 | 说明 |
|------|------|------|------|
| `--project-root` | ✅ | - | 项目根 |
| `--burn-subs` | ❌ | false | 是否烧入字幕 |
| `--subtitle-style` | ❌ | anime | `anime` / `plain` / `cinematic` |
| `--font` | ❌ | Microsoft YaHei | 中文字体名 |
| `--font-size` | ❌ | 24 | 字体大小 |
| `--max-clip-len` | ❌ | 10 | 单段最长秒数 |

## 4. 端到端流程

```
bash skills/ffmpeg-pipeline/bootstrap.sh --project-root $PROJECT_ROOT
```

**自动执行**：
1. **扫描** `04_outputs/02_micro_motion/` 按 scene_NN 顺序
2. **生成 concat.txt**（ffmpeg concat demuxer 格式）
3. **读** `03_storyboard/03_prompts/scene_NN.md` 的 dialogue，生成 SRT 字幕
4. **拼接 + 字幕** → final.mp4
5. **写 manifest.json**

## 5. Step 实现

### Step 1: 拼接 scene 列表

```bash
ls -1 $PROJECT_ROOT/04_outputs/02_micro_motion/scene_*.mp4 | sort > $PROJECT_ROOT/05_manifests/concat_list.txt
```

### Step 2: 生成 SRT

```bash
python3 skills/ffmpeg-pipeline/scripts/gen_srt.py \
  --prompts-dir $PROJECT_ROOT/03_storyboard/03_prompts/ \
  --output $PROJECT_ROOT/04_outputs/05_final/subtitles.srt \
  --max-clip-len 10
```

SRT 格式：
```
1
00:00:00,000 --> 00:00:10,000
我要打败你！

2
00:00:10,000 --> 00:00:20,000
看我的飞天御剑流！
```

### Step 3: 字幕烧入（可选）

```bash
ffmpeg -f concat -safe 0 -i $PROJECT_ROOT/05_manifests/concat_list.txt \
  -vf "subtitles=$PROJECT_ROOT/04_outputs/05_final/subtitles.srt:force_style='FontName=Microsoft YaHei,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'" \
  -c:a copy \
  $PROJECT_ROOT/04_outputs/05_final/final_with_subs.mp4
```

### Step 4: 无字幕拼接

```bash
ffmpeg -f concat -safe 0 -i $PROJECT_ROOT/05_manifests/concat_list.txt \
  -c copy $PROJECT_ROOT/04_outputs/05_final/final.mp4
```

## 6. 字幕风格

### `anime`（默认）

```
FontName: Microsoft YaHei
FontSize: 24
PrimaryColour: &H00FFFFFF (白)
OutlineColour: &H00000000 (黑描边)
Outline: 2 (描边宽度)
BackColour: &H80000000 (半透明黑底)
MarginV: 30 (底部 30px 边距)
```

### `plain`

```
FontSize: 20
PrimaryColour: white
Outline: 1
```

### `cinematic`

```
FontSize: 28
PrimaryColour: white
Outline: 3
BackColour: 透明
Shadow: 2
```

## 7. 输出 schema

### 04_outputs/05_final/manifest.json

```json
{
  "project": "wuyin_jianxin",
  "generated_at": "2026-07-27T10:00:00",
  "input_scenes": 24,
  "output": {
    "final.mp4": {
      "size_mb": 12.4,
      "duration_sec": 240,
      "has_audio": true,
      "has_subtitles": false
    },
    "final_with_subs.mp4": {
      "size_mb": 12.5,
      "has_audio": true,
      "has_subtitles": true
    }
  },
  "subtitles.srt": {
    "lines": 24,
    "language": "zh-CN"
  },
  "config_restored": true
}
```

## 8. 失败处理

| 失败 | 策略 |
|------|------|
| mp4 编码参数不一致 | 中间编码一次：`-c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k` |
| SRT 时间戳错位 | 重新跑 `gen_srt.py --audio-offset 0` |
| 字体未安装 | 用 fallback：`SimSun` / `WenQuanYi Micro Hei` / `Noto Sans CJK SC` |
| 磁盘满 | 标 `failed: disk`，中间产物保留 |

## 9. 已知约束

1. **ffmpeg 必须本地安装**（用户已有，否则可用 Docker）
2. **中文字体**：`fc-list :lang=zh` 检查；缺则降级到英文 fallback
3. **scale 不一致**：Step 3 失败概率最高，可能需 `scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720` filter
4. **长视频（>10min）**：分段拼接，或 `-c:v libx264 -crf 28` 压缩

## 10. 升级路径

- [ ] 多语言字幕（自动翻译）
- [ ] 字幕样式编辑器（前端 UI）
- [ ] BGM 混音层
- [ ] 自动转场（cross-dissolve / cut）
- [ ] GPU 加速（h264_nvenc / h264_qsv）

## 11. 版本

- v1.1.0（2026-07-30）：P1.1 ported — frontmatter 声明 chenxin-core 上游；路径全部改为 plugin 内
- v1.0.0（2026-07-27）：MVP — concat + SRT + 字幕烧入，可选风格

## 12. 相关引用

- **上游**: `skills/chenxin-core/SKILL.md`（L4 — 路由提示，ffmpeg 阶段无 ComfyUI 调用但要保持 codec 一致）
- 上游: `skills/manga-stage-4-motion/SKILL.md` (Stage 4 视频)
- 下游: 交付（用户观看）
- orchestrator: `skills/manga-orchestrator/SKILL.md` §4 Stage 5
- 依赖: `ffmpeg` CLI（PATH）
