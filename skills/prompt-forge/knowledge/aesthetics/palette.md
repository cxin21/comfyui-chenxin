# Palette

> 调色层只做"一个明确的色彩决定"——选择一个命名级色或一个文化调色板，最多再叠加一个温度修饰。混搭两个命名调色板（如 `Wes Anderson` + `cyberpunk`）是矛盾，模型将随机二选一。

## 核心公式
> Grade（明度级色）× Temperature（温度）× Cultural（文化调色板）三轴选一为主，其余为辅，确保画面只有一个清晰色彩身份。

## 变体维度表

| 维度 | 可选标签 |
|---|---|
| Grade（明度级色） | `monochrome` / `black and white` / `sepia` / `grayscale` / `high contrast` / `low contrast` |
| Temperature（温度） | `warm color` / `cool color` |
| Cultural（文化） | `teal and orange color grade` / `pastel color` / `vivid color` / `muted color` / `dark` / `noir` / `cyberpunk` / `vintage` / `retro` / `washed colors` |

## 氛围链
`pastel color` → `muted color` → `vivid color` → `high contrast` → `noir`

(从低饱和柔和到高饱和极致黑白，对比度与戏剧性沿链递增。)

## 使用提示
- `monochrome` 排斥所有 Cultural 标签——它本身就定义了"只用一种色调"。
- `high contrast` + `low contrast` 互斥：对比度只能选一极。
- `warm color` + `cool color` 互斥：温度二选一；如要冷暖对比，靠光源对比（如 `golden hour` 暖光 + 阴影冷蓝）。
- `dark` 与 `low contrast` 不等价：前者压暗整体亮度，后者压缩明度区间。
- `noir` 是 `black and white` + `high contrast` + 阴影密度的合成短语，等价于黑白犯罪片美学的整体指派。

## 法典验证场景
### 场景 A — 黑帮电影定场
tags: `noir`, `high contrast`
备注: 黑白高对比，强烈阴影，犯罪片默认调色。

### 场景 B — 暖夕户外
tags: `warm color`, `golden hour`, `pastel color`
备注: 暖色 + 低饱和 + 黄金时刻光线，浪漫复古。

### 场景 C — 赛博城市夜景
tags: `cyberpunk`, `cool color`, `high contrast`
备注: 冷色霓虹主导，黑底高对比，未来都市。

### 场景 D — 复古明信片
tags: `vintage`, `sepia`, `muted color`
备注: 褐色调 + 整体褪色，怀旧摄影效果。