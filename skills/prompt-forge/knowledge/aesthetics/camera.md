# Camera

> 镜头层给提示词一个物理渲染签名——是照片还是绘画，是广角还是微距，是数码还是胶片。Anima 词汇根植于图版文化，"镜头语言"指渲染介质 + 光学风格，不是哈苏型号。

## 核心公式
> Render medium（渲染介质）× Optical（光学风格）× Film（胶片/质感签名）三轴选一确定物理指纹，避免通用数字插画感。

## 变体维度表

| 维度 | 可选标签 |
|---|---|
| Render medium（介质） | `photo (medium)` / `photorealistic` / `illustration` / `painting` / `watercolor` / `sketch` / `lineart` / `comic` / `traditional media` / `digital media` |
| Optical（光学） | `depth of field` / `shallow depth of field` / `bokeh` / `motion blur` / `fisheye` / `macro` / `panoramic` / `wide angle` |
| Film（胶片） | `film grain` / `35mm` / `polaroid` / `instagram` |

## 氛围链
`photo (medium)` → `polaroid` → `35mm` → `film grain` → `instagram`

(从干净数字到怀旧滤镜，胶片感与色彩处理强度沿链递增。)

## 使用提示
- 一个 Render medium 只能选一个：`photo (medium)` + `painting` + `watercolor` 同时出现是矛盾。
- `shallow depth of field` + `panoramic` 互斥：全景隐含深焦，浅焦则无法容下全景。
- Optical 与 Render medium 独立：可以 `photo (medium)` + `fisheye`，也可以 `illustration` + `macro`。
- `polaroid` + `film grain` 允许同时出现——两者都是胶片质感特征，叠加更强化复古感。
- `photorealistic` 不等于 `photo (medium)`：前者强调"强烈照片渲染"，后者只声明"用照片方式呈现"。

## 法典验证场景
### 场景 A — 时尚人像
tags: `photo (medium)`, `shallow depth of field`, `35mm`
备注: 35mm 胶片 + 浅景深人像，杂志时尚摄影质感。

### 场景 B — 动漫线稿
tags: `lineart`, `illustration`, `digital media`
备注: 数字插画线稿风格，干净无杂色，漫画/番剧海报常用。

### 场景 C — 街拍速写
tags: `sketch`, `traditional media`, `motion blur`
备注: 速写笔触 + 运动模糊，街头速写感。

### 场景 D — 微距特写
tags: `photo (medium)`, `macro`, `bokeh`
备注: 微距镜头 + 焦外光斑，产品/昆虫/花卉特写。