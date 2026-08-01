---
okm: timeless
status: active
kind: knowledge
type: reference
description: "媒介描述词速查表——50+ 媒介的视觉特征与适用模型。媒介是第一性约束：命名媒介 = 选择 latent 子空间。"
source: "CivitAI + 行业实践 — 2026-07-30"
updated: 2026-07-30
tags:
  - prompt-forge
  - medium
  - style
  - reference
---

# 媒介描述词速查

> **为什么这是第一性约束？** 扩散模型从所有视觉模式的混合分布中采样。
> 不指定媒介 → 输出来自「所有风格的加权平均」= generic 感。
> 指定媒介 → 约束采样到一个特定子空间 = 立即获得该媒介的统计特性。

## 核心原则

- **媒介必须在 prompt 前 25% 位置出现**（token 注意力幂律衰减）
- **自然语言模型**：媒介词融入第一句描述
- **Tag 模型**：媒介词作为风格锚点 tag，紧跟质量前缀之后
- **一个 prompt 只选 1-2 个媒介锚点**，过多媒介会冲突

---

## 传统艺术媒介

| 媒介描述（自然语言） | Danbooru Tag 等价 | 视觉特征 | 适用模型 |
|---------------------|-------------------|---------|---------|
| `alcohol ink and watercolor on traditional washi paper` | (不适用于 tag 模型) | 颜料渗透/边缘羽化/纸纤维纹理/柔和渐变 | Flux |
| `oil painting on canvas` | `oil_painting_(medium)` | 可见笔触/厚涂肌理/光泽表面/颜料层叠 | Flux, SDXL |
| `ink wash painting / sumi-e` | `ink_wash` | 水墨渗透/浓淡层次/留白/毛笔笔触 | Flux, SDXL |
| `watercolor` | `watercolor_(medium)` | 透明感/边缘渗色/纸纹理/淡雅渐变 | 全部 |
| `gouache painting` | `gouache_(medium)` | 不透明水粉/平涂色块/哑光表面 | Flux, SDXL |
| `charcoal drawing` | `charcoal_(medium)` | 炭笔线条/涂抹痕迹/灰度层次/粗糙纸面 | Flux, SDXL |
| `pencil sketch` | `sketch` | 铅笔线条/未完成感/纸张纹理/灰色调 | 全部 |
| `woodblock print / ukiyo-e` | `ukiyo-e` | 平面色块/墨线轮廓/木纹/和风构图 | Flux, SDXL, Pony |
| `acrylic pour painting` | (不适用于 tag 模型) | 流体颜料/大理石纹/细胞图案/高光泽 | Flux |
| `pastel drawing` | (不适用于 tag 模型) | 粉彩笔触/柔光效果/粉末质感 | Flux, SDXL |
| `fresco / mural painting` | (不适用于 tag 模型) | 墙面肌理/矿物颜料/宏大尺度/岁月痕迹 | Flux |

---

## 数字艺术媒介

| 媒介描述 | Danbooru Tag 等价 | 视觉特征 | 适用模型 |
|---------|-------------------|---------|---------|
| `digital illustration` | (不需要 tag) | 锐利边缘/完美渐变/无物理纹理 | 全部 |
| `digital painting` | `digital_painting_(medium)` | 模拟笔触 + 数字精度/图层感 | 全部 |
| `concept art` | `concept_art` | 笔触可见/设计感/环境光为主/半完成感 | 全部 |
| `anime style` | (不需要 tag) | 赛璐珞着色/墨线轮廓/简化阴影 | 全部 |
| `pixel art` | `pixel_art` | 像素网格/有限色板/锯齿边缘/复古感 | Flux, SDXL |
| `voxel art` | (不适用于 tag 模型) | 三维像素块/等距视角/玩具感 | Flux |
| `3D render / CGI` | `3d`, `cg` | 完美材质/全局光照/锐利阴影 | 全部 |
| `low poly 3D` | (不适用于 tag 模型) | 多边形可见/简化几何/游戏感 | Flux |
| `vector art / flat design` | (不适用于 tag 模型) | 扁平色块/无渐变/几何线条 | Flux |

---

## 摄影媒介

| 媒介描述 | Danbooru Tag 等价 | 视觉特征 | 适用模型 |
|---------|-------------------|---------|---------|
| `photo realism` | `realistic`, `photorealistic` | 镜头光学/真实材质/自然光/景深 | 全部 |
| `vintage RAW photo` | (不适用于 tag 模型) | 胶片颗粒/有限动态范围/色偏/柔焦 | Flux, SDXL |
| `cinematic film still` | (不适用于 tag 模型) | 宽画幅/浅景深/电影级布光/色彩分级 | Flux, SDXL |
| `national geographic style` | (不适用于 tag 模型) | 自然光为主/高饱和度/纪实构图/锐利细节 | Flux, SDXL |
| `polaroid photo` | (不适用于 tag 模型) | 白色边框/低饱和度/柔焦/暖色调 | Flux |
| `daguerreotype` | (不适用于 tag 模型) | 金属银光泽/镜像反射/高细节/19世纪感 | Flux |
| `long exposure photography` | `long_exposure` | 运动模糊/光轨/水面雾化/星空拖尾 | Flux, SDXL |
| `tilt-shift photography` | (不适用于 tag 模型) | 微缩模型感/选择性聚焦/俯视角度 | Flux |
| `lomography` | (不适用于 tag 模型) | 高饱和度/暗角/光漏/塑料镜头感 | Flux |
| `infrared photography` | (不适用于 tag 模型) | 白色植被/暗色天空/超现实色彩 | Flux |
| `macro photography` | (不适用于 tag 模型) | 极浅景深/微观细节/放大比例 | 全部 |
| `street photography` | (不适用于 tag 模型) | 抓拍感/自然光/城市环境/人文纪实 | Flux, SDXL |

---

## 印刷与出版媒介

| 媒介描述 | Danbooru Tag 等价 | 视觉特征 | 适用模型 |
|---------|-------------------|---------|---------|
| `comic book art` | (不需要 tag) | 墨线轮廓/网点/半色调/对话框/画格 | 全部 |
| `manga style` | `manga` | 黑白/网点/速度线/日式分镜 | Pony, SDXL |
| `movie poster` | (不适用于 tag 模型) | 标题字/演职员表/戏剧化构图/大片感 | Flux, SDXL |
| `book cover illustration` | (不适用于 tag 模型) | 标题空间/装饰性/明确视觉焦点 | Flux, SDXL |
| `newspaper print` | (不适用于 tag 模型) | 半色调网点/新闻纸色/粗粒印刷 | Flux |
| `sticker art` | (不适用于 tag 模型) | 白边框/鲜艳色/简洁造型/die-cut感 | Flux |
| `trading card illustration` | (不适用于 tag 模型) | 卡片画框/稀有度效果/角色展示 | Flux, SDXL |
| `tarot card art` | (不适用于 tag 模型) | 对称构图/象征元素/装饰边框/金色点缀 | Flux, SDXL |

---

## 工艺与材质媒介

| 媒介描述 | Danbooru Tag 等价 | 视觉特征 | 适用模型 |
|---------|-------------------|---------|---------|
| `stained glass window` | (不适用于 tag 模型) | 铅线分割/彩色玻璃/透光效果/教堂感 | Flux, SDXL |
| `mosaic art` | `mosaic` | 小块拼接/缝隙可见/石材或玻璃 | Flux, SDXL |
| `embroidery / textile art` | `embroidery` | 线迹纹理/布料基底/刺绣光泽 | Flux |
| `papercraft / paper cutout` | (不适用于 tag 模型) | 纸层叠/投影/立体纸艺 | Flux |
| `clay sculpture` | (不适用于 tag 模型) | 指纹痕迹/泥土材质/手工感 | Flux |
| `origami` | `origami` | 折痕锐利/纸质感/几何造型 | Flux |
| `sand art` | (不适用于 tag 模型) | 颗粒质感/流动造型/沙色 | Flux |
| `ice sculpture` | (不适用于 tag 模型) | 透明/折射/融化边缘/冷光 | Flux |

---

## 混合媒体

| 媒介描述 | 视觉特征 | 适用模型 |
|---------|---------|---------|
| `mixed media collage` | 不同素材拼接/纹理冲突/层次感 | Flux |
| `analog + digital hybrid` | 手绘 + 数字后期/有机 vs 几何 | Flux |
| `photobashing / matte painting` | 照片拼接 + 手绘/电影级场景 | Flux, SDXL |
| `double exposure photography` | 两图叠加/透明层叠/诗意 | Flux |

---

## 使用策略

### 自然语言模型（Flux/Qwen/Anima/SD3.5）
媒介词直接融入第一句：
```
[famous artwork], [medium] on [surface], [scene description]...
```

### Tag 模型（Pony/Illustrious/SDXL/SD1.5）
媒介词作为风格锚点 tag，紧跟质量前缀之后：
```
[quality prefix], [medium tag], [subject tags]...
```

### 媒介组合规则
- ✅ `oil painting on canvas` — 媒介 + 载体的自然组合
- ✅ `vintage RAW photo, cinematic film still` — 同属摄影大类，互补
- ❌ `oil painting, photo realism, pixel art` — 三个互斥媒介，模型无法调和
- ❌ `digital illustration and watercolor` — 除非故意做混合媒体效果
