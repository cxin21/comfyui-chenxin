# Prompt Forge LLM-first 设计规格

日期：2026-08-04
状态：设计已获口头确认，待规格审阅
范围：仅重设计 `skills/prompt-forge/`，不把 ComfyUI、MCP、工作流存在性或执行状态纳入本技能

## 1. 目标与非目标

### 目标

Prompt Forge 是一个由 Claude/Codex 作为调用方使用的提示词创作与审查技能。它把剧情拆解、影视资产、美术风格、用户要求和目标提示词方言转化为高质量的 `PromptPackage`。

优化目标按以下顺序排列：

1. 不丢失已确认事实；
2. 不把未知内容伪装成事实；
3. 生成可见、可执行、具备因果关系的画面/动作描述；
4. 保持人物、场景、道具和风格连续性；
5. 匹配目标模型的提示词方言；
6. 用最少的冗余文字获得最大控制力。

### 非目标

Prompt Forge 不负责：

- 判断模型是否已安装或可用；
- 检查 ComfyUI、MCP、工作流、节点、哈希、槽位或显存；
- 提交、执行或保存生成任务；
- 判断某个提示词能否被实际工作流消费；
- 管理审批、RunRecord、artifact 或历史状态。

这些责任属于外部执行技能，例如 `character-video-pipeline`。

## 2. 第一性原理边界

模型和工作流是两个不同概念：

- 模型在本技能中只表示一种提示词方言和表达偏好；
- 工作流是外部消费者，决定把哪些字段写入哪里；
- 模型是否存在不影响提示词创作。

因此，本技能的核心函数是：

```text
CreativeEvidence + StyleLanguage + OptionalDialect
    -> LLM-authored PromptPackage
    -> deterministic quality lint
```

不得变成：

```text
CreativeEvidence
    -> inspect installed model/workflow
    -> decide whether generation is executable
```

## 3. 四象限证据协议

所有提示词生成先建立内部证据账本，但最终提示词不得包含报告式分析。

### 共同已知

确认任务目标、已有背景、交付标准和明确边界，直接执行，不重复询问。

### 用户已知、模型未知

识别画面语境、审美偏好、资产约束、现实限制和连续性要求。缺失信息只有在显著改变结果时才提问，最多三个关键问题；否则采用显式合理假设。

### 用户未知、模型已知

主动补充构图、光影、材质、动作物理、镜头语言、时间线和模型方言等知识。补充内容必须标记为合理推断，不得升级为剧情事实。

### 共同未知

将无法确定的问题转化为可验证假设：

```json
{
  "hypothesis": "...",
  "single_variable": "...",
  "success_signal": "...",
  "failure_signal": "...",
  "next_data": "..."
}
```

未知的模型安装状态、工作流状态和 ComfyUI 状态不属于阻塞条件。

## 4. 输入与输出合同

### 输入

输入可以来自：

- `前期剧情拆解模板.md` 的剧情、人物、场景、对白和不确定性；
- `影视资产.md` 的美术圣经、人物资产卡、环境资产卡和道具资产卡；
- `提示词公开版本.txt` 的 LTX 输出规范；
- 用户直接给出的创意 brief；
- 已有参考图片、故事板或资产描述。

输入先被归一化为 `CreativeEvidence`，而不是直接拼接成提示词。

### 输出

```json
{
  "schema_version": "2.0",
  "target": "image|video",
  "dialect": "...",
  "positive": "...",
  "negative": "...",
  "positive_zh": "...",
  "positive_en": "...",
  "global_prompt": "...",
  "timeline_segments": [],
  "dialogue_attribution": [],
  "style_locks": [],
  "continuity_locks": [],
  "assumptions": [],
  "uncertainties": [],
  "warnings": [],
  "quality": {
    "facts_preserved": true,
    "no_unsupported_invention": true,
    "style_coherent": true,
    "dialect_valid": true,
    "temporal_logic_valid": true,
    "ready_for_review": true
  }
}
```

禁止在 Prompt Forge 输出中使用 `ready_to_execute`、`execution`、`workflow_hash`、`profile_hash`、`node_id`、`slot_id` 等执行状态字段。

## 5. 模型方言层

模型资料统一收敛到 `dialects/`，不再使用混合了工作流和模型知识的 recipe 目录。

每个方言文件只描述：

- prompt 形式：tag、自然语言、结构化 brief、时间线等；
- 推荐信息顺序；
- 正向/反向表达策略；
- 参考图和身份保持表达方式；
- 字数、句式和镜头语言建议；
- 常见失败模式；
- 方言适用的质量检查。

不描述模型文件、显存、节点、工作流、哈希和执行条件。

初始方言包括：

- Anima/Danbooru tags；
- Pony/Illustrious/NoobAI/SD1.5/SDXL tags 或混合 tags；
- Flux/Qwen/GPT Image/Seedream 等自然语言或结构化图像方言；
- LTX、Wan、Kling、Seedance、Sora 等视频方言。

同一创意可以根据不同方言生成多个版本，必须保持事实和风格锁一致。

## 6. 风格层

风格与模型方言正交。风格库描述视觉语言，不描述执行条件。

风格由以下轴组成：

- medium；
- lighting；
- composition；
- color；
- material；
- grain/texture；
- depth/density；
- motion language。

自然语言模型和 tag 模型可以使用不同表达，但必须指向同一视觉指纹。

以下规则不再作为硬约束：

- 媒介必须出现在前 25%；
- 运动必须占提示词 50% 以上；
- 用户未指定风格时随机抽取风格；
- 根据场景关键词自动注入风格。

风格选择应遵循：明确指定优先、合理推断次之、显著影响结果才提问，否则明确假设并继续。

## 7. LLM 生成流程

1. 建立证据账本；
2. 提取主体、动作、场景、镜头、光线、色彩、材质、对白、时间线和连续性；
3. 选择目标方言和风格表达；
4. 由 Claude/Codex 直接写最终提示词；
5. 对抗性审查：事实、未知、风格、动作、镜头、时序、对白和方言；
6. 由确定性校验器检查结构，不自动创作缺失正文；
7. 输出 PromptPackage。

生产模式没有 LLM 草稿时必须返回缺失错误。若需要探索性草稿，必须显式使用开发模式，且不能标记为质量通过。

## 8. 当前四阶段的调用约定

Prompt Forge 不判断以下阶段是否存在，只按调用方要求生成对应提示词：

1. Anima 基础人物图：输出 tag 方言正向/反向提示词；
2. Flux2-Klein 多视图：如调用方需要，输出自然语言或结构化多视图提示词；是否使用由执行层决定；
3. Anima 镜头图：输出继承人物和风格锁的镜头差异提示词；
4. LTX Yusu：输出双语时间线、全局提示词、对白归属和连续性要求。

Stage 2 是否实际有 prompt 槽、Stage 4 是否使用工作流自带 negative，都不由 Prompt Forge 判断；这些属于外部适配器。

## 9. 文件重组原则

### 保留并重写

- `SKILL.md`；
- `SPEC.md`；
- `references/prompt-contracts.md`；
- `references/image-dialects.md`；
- `references/video-dialects.md`；
- `internals/intent_normalize.py`；
- `internals/prompt_compile.py`；
- `internals/tag_lookup.py`；
- `internals/evaluate.py`；
- `dictionary/tag-index.json`；
- `dictionary/zh-en.json`。

### 整合

- `models/*.md` 与 `recipes/MODELS.md` 合并为 `dialects/`；
- `aesthetics/` 合并为结构化 style atoms 和 style packs；
- `negative/negative-prompts.md` 合并到各方言的 negative policy；
- 三份用户文档转为 `CreativeEvidence` 输入说明和 LTX/资产规则参考。

### 删除或移出 Prompt Forge

- `recipe_lookup.py`；
- `recipe_yaml.py`；
- 自动注入风格的 `scene_match.py`；
- `concept-archetypes.md`；
- `video-archetypes.md`；
- `hardware/8gb.json`；
- `danbooru.csv`、`wd14-tags.csv`、`build_tag_index.py` 的维护源数据和构建脚本；
- `.pytest_cache`、`.ruff_cache`、`__pycache__`。

工作流、MCP、节点、显存和执行质量门继续留在 `character-video-pipeline`，不迁入本技能。

## 10. 质量评测

离线评测不启动 ComfyUI，也不验证模型文件存在性。评测维度包括：

- 明确事实覆盖率；
- 未知信息误填率；
- 风格一致性；
- 模型方言正确率；
- 正负向冲突率；
- 动作是否可见且有因果关系；
- 镜头是否清晰稳定；
- LTX 时间线是否连续；
- 对白归属是否明确；
- 多模型版本之间事实锁是否一致；
- 多风格版本之间身份和剧情是否不变。

ComfyUI 实际执行测试属于外部 pipeline 的测试集，不属于 Prompt Forge 的验收标准。

## 11. 验收标准

设计完成后，必须满足：

1. 同一创意可以生成至少两个不同模型方言版本；
2. 同一创意可以生成至少两个不同风格版本；
3. 风格变化不会改变人物、剧情和道具事实；
4. 目标模型未安装时仍可生成提示词；
5. 没有 LLM 草稿时不会静默生成生产提示词；
6. Prompt Forge 不读取或校验 ComfyUI 工作流；
7. Prompt Forge 输出不含执行状态字段；
8. 所有未知信息、假设和警告可追溯；
9. LTX 双语时间线、对白归属和连续性规则通过离线校验；
10. tag 方言只使用精确或批准的 canonical tag。
