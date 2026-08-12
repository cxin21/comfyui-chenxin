# Lighting

> 光影是情绪最大的杠杆。每一条标签同时编码"质感（软/硬）"和"方向（光从哪里来）"——只写 `warm light` 是没用的，模型需要知道光的硬度、方向与光源类型。

## 核心公式
> 用 Quality（光质）× Direction（方向）× Source（光源类型）三轴决定氛围底色，Special（特殊光效）按场景需要挂接。

## 变体维度表

| 维度 | 可选标签 |
|---|---|
| Quality（光质） | `cinematic lighting` / `dramatic lighting` / `soft lighting` / `hard lighting` / `volumetric lighting` / `god rays` |
| Direction（方向） | `backlighting` / `rim light` / `side lighting` / `from below` / `top lighting` / `front lighting` |
| Source（光源） | `golden hour` / `blue hour` / `sunlight` / `dappled sunlight` / `moonlight` / `candlelight` / `neon lights` / `studio lighting` / `ambient light` |
| Special（特殊） | `chiaroscuro` / `silhouette` / `lens flare` / `bloom` / `reflections` / `partially shadowed` |

## 氛围链
`ambient light` → `soft lighting` → `cinematic lighting` → `dramatic lighting` → `chiaroscuro`

(从无明确光源到极致明暗对比，光影戏剧张力随链长递增。)

## 使用提示
- Quality 只选一个：`soft lighting` + `hard lighting` 是矛盾对，模型会随机选其一。
- Source 默认搭配一个 Quality：`golden hour` 自带暖软光，`moonlight` 自带冷蓝光，但显式写 `cinematic lighting` + `golden hour` 仍可叠加。
- Direction 与 Quality 独立：`rim light` 是方向而非软硬，可以挂任何光质。
- `volumetric lighting` 与 `fog` / `dust` 共用效果最佳——没有空气介质，看不见光束。
- `chiaroscuro` 是 Baroque / Renaissance 戏剧化光影的命名短语，等价于极致 `dramatic lighting` + `partially shadowed`。

## 法典验证场景
### 场景 A — 文艺复兴肖像
tags: `chiaroscuro`, `side lighting`, `partially shadowed`
备注: 经典油画戏剧光影，半脸明亮半脸阴影。

### 场景 B — 黄金时刻人像
tags: `soft lighting`, `rim light`, `golden hour`
备注: 逆光 + 暖低太阳光，典型户外浪漫照。

### 场景 C — 赛博朋克街道
tags: `cinematic lighting`, `backlighting`, `neon lights`
备注: 背光剪影加霓虹主光源，城市夜景主体被色光勾边。

### 场景 D — 林间圣光
tags: `god rays`, `volumetric lighting`, `dappled sunlight`
备注: 森林或教堂中由上方穿透的光束，常带神秘感或神圣感。