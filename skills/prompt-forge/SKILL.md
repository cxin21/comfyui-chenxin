---
name: prompt-forge
description: |
  为生成模型编写模型专属 prompt。目标：文生图；图像编辑；文生视频；图生视频；参考素材生成。动作：编写；优化；转换；审查。触发意图包括：提示词；negative prompt；Danbooru tags；image edit；分镜；运镜；镜头语言；时序描述；以及明确要求把提示词用于生成。不用于软件安装、节点排障、工作流修复、权重下载、硬件比较、价格新闻或泛泛介绍。
---

# Prompt Forge

把用户意图编译为目标模型真正接受的提示方言，并交付可审计的 `PromptBuild`。默认只编译；只有用户明确要求“生成/运行/执行”时才进入执行模式。

## 不可破坏的约束

- 用户明确事实优先于 recipe 和推断，显式事实必须锁定。
- 开放语义由模型理解；Python 只负责契约、查表、匹配、tag 验证和最终审计。
- 不把中文逐字替换成英文，不把未知词伪装成已翻译内容。
- Danbooru 语义 tag 必须 exact/alias 验证；recipe 控制 token 与语义 tag 分开保存。
- 编译器从不调用生成工具。执行属于单独的、显式授权后的动作。

## 0. 解析 Skill 根目录

将本 `SKILL.md` 所在目录记为 `SKILL_ROOT`。下面所有脚本都用绝对路径调用，例如：

```text
python "<SKILL_ROOT>/internals/recipe_lookup.py" --model <model-hint>
```

不要假设当前工作目录位于 Skill 内。

## 1. 确定任务边界

先确定：

- `target`: `image` 或 `video`
- `generation_mode`: 如 `text-to-image`、`image-edit`、`text-to-video`、`image-to-video`
- `mode`: 默认 `compile`；仅明确要求生成时设为 `execute`
- 模型、画幅/尺寸/时长/fps、参考素材及不可改变的事实

模型不明确且不同模型会显著改变方言时，询问一次；否则用最可信的模型提示继续。

## 2. 解析模型 recipe

```text
python "<SKILL_ROOT>/internals/recipe_lookup.py" --model <model-hint>
```

读取 `matched_id`、`frontmatter.modality`、`frontmatter.dialect`、`negative_policy` 和 `dialect_block`。recipe 未命中或 modality 与 target 冲突时停止编译，不套用相似模型。

## 3. 构造 PromptIntent 6.1

按 [Prompt contracts](references/prompt-contracts.md) 构造完整 JSON。固定维度为：

`subject, action, scene, lighting, composition, camera, motion, timeline, audio, color, style, mood, medium, quality`

每项标记 `explicit`、`recipe` 或 `inferred`。显式项设置 `locked: true`，尽量保留 `source_text`；同时把所有不可变事实列入 `locked_facts`。缺失维度使用 `[]`。

## 4. 受控补全

补全优先级恒为：`explicit > recipe > inferred`。

场景查询只使用场景、光照、色彩、氛围相关短语：

```text
python "<SKILL_ROOT>/internals/scene_match.py" --query "<scene terms>" --top 3
```

命中时只补空维度。返回 `_no_scene_match` 时，`choices` 是候选而非默认值；没有足够依据就保持为空或让用户选择。

## 5. 按方言写 draft

只加载当前分支需要的参考：

- tag / 自然语言图像：读 [Image dialects](references/image-dialects.md)
- 视频：读 [Video dialects](references/video-dialects.md)
- 中文概念映射需要维护时：读 [Concept map](references/concept-map.md)

渲染一个 `draft.prompt`，必要时渲染 `draft.negative_prompt`。自然语言 draft 必须逐项体现 `locked_facts`；视频 draft 必须明确主体动作、运动连续性、一个可执行的镜头意图和时间演进。

## 6. 编译并审计 PromptBuild

把 `intent` 与 `draft` 作为一个 JSON envelope 送入：

```text
python "<SKILL_ROOT>/internals/prompt_compile.py" --from-stdin
```

输入形状：

```json
{"intent": {"schema_version": "6.1"}, "draft": {"prompt": "...", "negative_prompt": "..."}}
```

编译器会解析 recipe、验证 tag、检查 locked facts、negative policy 与视频契约，并返回 `PromptBuild 1.0`。若 `ready_to_execute` 为 `false`，根据 `errors` 修正意图或 draft 后重编译；不要绕过错误。

## 7. 交付或执行

- `mode: compile`：返回最终 prompt、negative prompt、目标模型、关键参数和 warnings；到此结束。
- `mode: execute`：先向用户展示可审计 prompt。仅当 `ready_to_execute: true` 且用户本次请求明确要求生成时，才调用可用的图像或视频生成工具。
- 工具不可用时只交付 PromptBuild，不声称已生成。
- 调用后把实际工具、参数和结果补充到会话答复；不要篡改编译器输出中的 `execution.performed: false`，它表示编译阶段没有副作用。

## 最终质量门

1. 所有显式事实均在 prompt/tag 中可追踪。
2. recipe 或推断没有覆盖显式事实。
3. tag 方言无未验证语义 tag，控制 token 来源明确。
4. unsupported negative 模型没有收到 negative 字段。
5. 视频具备主体、动作、motion、camera；多事件任务具备 timeline。
6. 无 `[unset]`、内部 provenance 字段或虚构 canonical。
7. 输出约束与参考素材保持在独立字段，未偷偷改写成视觉事实。
