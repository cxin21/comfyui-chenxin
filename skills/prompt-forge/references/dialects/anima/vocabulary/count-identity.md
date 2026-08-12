# Count & Identity

## 核心公式
> 主体层——决定画面有几个角色、性别构成、是否命中 IP、体型与年龄差如何表达。

## 变体维度表

| 维度 | 可选标签 |
|---|---|
| 单人女 | `1girl, solo` |
| 单人男 | `1boy, solo` |
| 单人性别模糊 | `solo, ambiguous gender` |
| 单人特殊 | `1girl, solo` / `1boy, solo` / `futanari, solo` / `otoko no ko, femboy, trap, solo` |
| 双人混合 | `1girl, 1boy, hetero` |
| 双女 | `2girls` / `2girls, yuri` |
| 双男 | `2boys` |
| 多人女 | `Xgirls, multiple girls` |
| 多人男 | `Xboys, multiple boys` |
| 多人混合 | `Xgirls, Xboys, multiple girls, multiple boys, group sex` |
| 多人百合 | `2girls, yuri` / `3girls, multiple girls, yuri` |
| IP 角色 | `character, series` + 至少 5 个外观锚点 |
| 原创角色 | 不写 `character` / `series`，直接描述外观 |
| 身高差 | `height difference, size difference` |
| 大×小 | `tall male, petite female, height difference, size difference` |
| 体差 | `fat man, petite female, size difference` |
| 年龄差 | `age difference, older male, younger female` |
| 扶她 | `futanari, 1girl` |
| 男娘 | `otoko no ko, femboy, trap, 1boy` |

## 氛围链

> 本章离散——人数与身份是离散值，无 light→heavy 递进。

## 使用提示

- 多人场景每个角色必须配 ≥3 个外观锚点，避免模型串脸或属性归属错乱。
- 命中 IP 角色时，`character` + `series` + 至少 5 个外观锚点（发型/发色/眼色/标志服饰/配饰）缺一不可。
- 原创角色不写 `character` / `series`，直接描述外观。
- `yuri` 必须仅用于明确的双女恋爱/情色互动；多名女性日常合影（摸头、拥抱）不应加 `yuri`。
- 男娘(`otoko no ko, femboy, trap`)与扶她(`futanari`)是两个独立体系，不能混用。
- 不确定的角色特征（发色、瞳色、标志服装）禁止凭空编造——查 dictionary 或询问用户。

## 法典验证场景

### 场景 A — 单人原创
tags: `1girl, solo`
备注: 单人原创画面，count 锚点仅 2 个标签构成。

### 场景 B — 双人 IP 混合
tags: `1girl, 1boy, hetero, character, series`
备注: 必须后续补 ≥5 个外观锚点，否则模型无法加载角色。

### 场景 C — 多人群体
tags: `3girls, multiple girls, yuri`
备注: 百合情色场景才加 `yuri`，日常合影不加。

### 场景 D — 体型差双人
tags: `1girl, 1boy, hetero, tall male, petite female, height difference, size difference`
备注: 视觉上呈现明显的体型反差——高大男 × 娇小女。
