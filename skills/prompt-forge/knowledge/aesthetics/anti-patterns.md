# Anti-patterns

> 反模式层是 precedence 中的覆写层。一旦提示词命中下表任一模式，必须在编译前移除——不管其他五层怎么写。美学质量一半靠排除法决定。

## 核心公式
> 反模式 = 空泛强化词 + 矛盾搭配 + 模型学坏的指纹标签。一律以具体可替换的 tag pair 描述，每一行给出"错在哪 + 换什么"。

## 变体维度表

| 类别 | 禁止模式 | 正确替换 |
|---|---|---|
| 光线描述 | `sunlight` | `dappled sunlight` 或 `golden hour`（指定光源类型） |
| 光线描述 | `moonlight` | 移除或换 `blue hour`（冷调光源） |
| 光线描述 | `dim light` | `low contrast` + `ambient light`（声明对比度+环境光） |
| 光线描述 | `candlelight` | 改写为 `warm color` + `partially shadowed`（描述色彩与明暗） |
| 光线描述 | `neon light`（单数，词典未收录） | 用 `neon lights`（词典 canonical；cyberpunk 配方必备锚点；勿与 `pastel color` / `low contrast` 堆叠） |
| 光线描述 | `streetlights` | `neon lights` 或 `urban night` 整体氛围 |
| 光影技术 | `backlighting` | 描述结果（`silhouette`）而非技术名 |
| 光影技术 | `rim light` | 改写为 `partially shadowed`（光影效果） |
| 光影技术 | `warm lighting` | `warm color` + 光源（`golden hour`） |
| 光影技术 | `cool lighting` | `cool color` + 光源（`moonlight`/`blue hour`） |
| 光影技术 | `golden hour glow` | `golden hour`（标准命名） |
| 光影技术 | `soft lighting` | `soft lighting` 仅可单独写，禁止堆叠；与 `hard lighting` 互斥 |
| 色调描述 | `warm tone` | `warm color`（标准命名） |
| 色调描述 | `cool tone` | `cool color`（标准命名） |
| 色调描述 | `sepia` | 单独可接受，但优先用 Grade 维度声明 |
| 色调描述 | `blue tone` | `cool color` + `blue hour` |
| 色调描述 | `amber tone` | `warm color` + `golden hour` |
| 光学现象 | `god rays` | 仅在需要光束效果时使用，不可与 `sunlight` 叠加 |
| 光学现象 | `light rays` | 同 `god rays`，归入 Special 光效层 |
| 光学现象 | `light particles` | `Particle` 维度中已有，专门用于氛围细节 |
| 光学现象 | `volumetric light beams` | `volumetric lighting`（标准命名） |
| 光学现象 | `tyndall effect` | `volumetric lighting`（更通用） |
| 发光描述 | `glowing` | 改写为具体光源（`embers` / `lens flare`） |
| 发光描述 | `illuminated` | 删除或换具体光源 |
| 发光描述 | `lit` | 同 `illuminated` |
| 发光描述 | `backlit` | 同 `backlighting`，用结果描述（`silhouette`） |
| 发光描述 | `spotlight` | 改写为 `top lighting`（方向描述） |
| 发光描述 | `flash` | 删除或改为 `lens flare`（光学现象） |
| 空泛强化词 | `beautiful` / `gorgeous` / `stunning` / `pretty` / `lovely` | 删除；用具体美学标签代替 |
| 空泛强化词 | `highly detailed` / `ultra detailed` | 指定细节对象（`intricate lace collar`） |
| 空泛强化词 | `masterpiece` / `masterful` / `amazing` | 删除 |
| 空泛强化词 | `intricate` / `ornate`（单独） | 指定装饰对象（`intricate lacework on collar`） |
| 空泛强化词 | `professional`（单独） | 指定渲染介质（`photo (medium)`） |
| 空泛强化词 | `award-winning` / `prize-winning` | 删除或换为具体风格家族 |
| 分辨率噱头 | `8k` / `4k` / `2k` / `uhd`（单独） | 删除或组合意图（`highres` 为官方质量标签） |
| 分辨率噱头 | `high resolution` / `high quality`（单独） | `highres` |
| 平台标记 | `trending on artstation` / `trending on pixiv` | 删除（画廊引流指纹） |
| 平台标记 | `featured on pixiv` / `fanbox` / `patreon` | 删除 |
| 模型低质指纹 | `simple background`（无补偿标签） | `detailed background` 或具体环境标签 |
| 模型低质指纹 | `bad anatomy` / `bad hands`（positive 中） | 删除 |
| 模型低质指纹 | `watermark` / `signature`（positive 中） | 删除 |
| 模型低质指纹 | `lowres` / `worst quality` / `low quality`（positive 中） | 这些标签只能出现在 negative 流 |
| 模型低质指纹 | `score_4` / `score_5` / `score_6`（positive 中） | 同上，移到 negative |
| 矛盾搭配 | `cinematic lighting` + `flat color` + `cel shading` | 选一边：`cinematic lighting` + `illustration` |
| 矛盾搭配 | `monochrome` + `pastel color` + `vivid color` | 选一个 Grade |
| 矛盾搭配 | `low contrast` + `high contrast` | 选一极 |
| 矛盾搭配 | `warm color` + `cool color`（无背景） | 选一边；冷暖对比靠光源 |
| 矛盾搭配 | `soft lighting` + `hard lighting` | 选一种光质 |
| 矛盾搭配 | `low angle` + `high angle` | 选一个角度 |
| 矛盾搭配 | `centered` + `rule of thirds` | 选一种布局 |
| 矛盾搭配 | `shallow depth of field` + `panoramic` | 浅焦不可全景 |
| 矛盾搭配 | `photo (medium)` + `painting` + `watercolor` + `sketch` | 只选一个介质 |
| 矛盾搭配 | `cyberpunk` + `pastel color`（无中介风格） | 风格统一或换题材 |
| 重量语法 | 未校准/越界的权重（如 `(tag:5.0)`、`(tag:0.3)`） | 权重语法 `(text:weight)` 本身受支持：普通 1.0-2.0、artist 2.0-4.0（见 dialect.md 权重校准表） |
| 重复伪强化 | 同一标签写两遍 | 删除重复 |
| 堆叠过度 | 同一段中 5+ 光照标签 | 选 2-3 个互补项 |
| 末尾残留 | 末尾 `...` 或 `--` 等非标签符号 | 删除；audit 将拒绝 |

## 使用提示
- 光线/色调标签本身是合法词典标签（见 lighting.md / palette.md / cyberpunk-neon 配方）；反模式只针对空泛或冲突写法（如 `sunlight` 单独、`neon lights` 叠加 `pastel color`）。
- 环境天气（`rain` / `snow` / `fog` / `steam` / `stormy` / `dust particles` / `underwater`）与时辰/大气标签可直接使用。
- `monochrome` 内部包含光线信息，写 `monochrome` 时不要再加 `soft lighting` 等光质标签。
- 凡包含"绝对/极致/完美"等评价词的形容词（`stunning`、`masterpiece`）一律删除。
- 矛盾对消解优先级：先选符合用户意图的术语，再删除另一项，不要简单保留两者。

## 法典验证场景
### 场景 A — 黄金时刻逆光人像（合规版）
tags: `golden hour`, `warm color`, `partially shadowed`, `silhouette`
备注: 用 Grade/Cultural + 描述光影结果的标签，避免空泛光线词。

### 场景 B — 黄金时刻逆光人像（违规版）
tags: `sunlight`, `backlighting`, `rim light`, `golden hour glow`, `warm tone`, `beautiful`
修正: 删除 `sunlight` / `backlighting` / `rim light` / `golden hour glow` / `warm tone` / `beautiful`，改用场景 A 版本。

### 场景 C — 雨夜都市（合规版）
tags: `cyberpunk`, `cool color`, `high contrast`, `rain`, `bokeh`
备注: 利用环境天气（`rain`）+ 调色板与光影结果标签。

### 场景 D — 雨夜都市（违规版）
tags: `streetlights`, `warm lighting`, `cool lighting`, `atmospheric`
修正: `neon lights` 是 cyberpunk 配方必备锚点（保留）；`warm lighting` / `cool lighting` 改用标准命名 `warm color` / `cool color`；`streetlights` 用 `neon lights` 或 `urban night` 整体氛围；`atmospheric` 替换为 `rain` + `fog`。