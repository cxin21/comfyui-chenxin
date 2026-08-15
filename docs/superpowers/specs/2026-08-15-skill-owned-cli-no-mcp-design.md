# Skill-Owned CLI and MCP-Free Runtime Design

**状态：** 实施中（P1 协议已冻结）

**日期：** 2026-08-15

**目标目录：** `skills/`

## 1. 目标

把每个 Skill 和它自己的确定性辅助脚本变成可独立安装、独立调用的 CLI 包。Skill 文档负责方法论和调用时机；CLI 负责 Catalog、结构校验、审计、固定工作流组装和 ComfyUI 执行。

MCP 不再是任何 Skill 的运行前置条件。Prompt/Catalog/H3 链路完全离线运行；Camera 链路直接访问本地 ComfyUI HTTP API。

## 2. 非目标

- 不让 CLI 代替大模型进行视觉语义理解、故事创作、镜头创意或关系推断。
- 不把自然语言自动拆成完整 PromptBrief/H3 fact ledger，并把结果伪装成模型语义判断。
- 不暴露任意 ComfyUI 节点 ID、任意 workflow JSON、隐藏组开关或固定资产内部映射。
- 不保留 MCP 作为隐式 fallback。
- 不新增旧 `anima_prompt`、旧 provider 或旧 schema 的兼容层。

## 3. 架构原则

```text
SKILL.md
  -> 方法论、语义决策、CLI 调用顺序、不可用时的降级规则

skill package
  -> 内置 CLI 协议、结构化请求校验、确定性 author/audit/catalog/workflow 逻辑

skill CLI
  -> JSON stdin/file 输入、JSON stdout 输出、退出码和诊断

ComfyUI HTTP runtime
  -> health、upload、queue、history、view、prompt
```

每个 Skill 包必须可以在没有 `mcp_server/`、没有 Codex MCP 配置、没有 MCP entry-point 的环境中独立安装和执行。

统一 CLI 协议是共享契约，不是共享运行时依赖。五个 Skill 分别内置标准库 `cli_protocol.py`，并通过同一组契约测试保持行为一致；任何 Skill 不得为使用协议而依赖另一个 Skill 或中央 dispatcher。

相机 Skill 可以共享一个非常小的中性 HTTP 传输包，但该包不得包含 MCP、Skill registry、MCP schema 或 Codex 配置逻辑。Skill 之间的发现和调度不由中央服务完成。

## 4. 目标包边界

```text
skills/anima-prompt-v1/
  anima_prompt_v1/
    cli_protocol.py           # Skill 内置协议实现
  scripts/
  pyproject.toml              # anima-prompt-v1 CLI

skills/minimax-h3-prompt/
  h3_prompt/
    cli_protocol.py           # Skill 内置协议实现
  scripts/
  pyproject.toml              # minimax-h3-prompt CLI

skills/camera-image/
  camera_image/
    cli_protocol.py           # Skill 内置协议实现
  scripts/
  pyproject.toml              # camera-image CLI

skills/camera-video/
  camera_video/
    cli_protocol.py           # Skill 内置协议实现
  scripts/
  pyproject.toml              # camera-video CLI

skills/camera-multiview/
  camera_multiview/
    cli_protocol.py           # Skill 内置协议实现
  scripts/
  pyproject.toml              # camera-multiview CLI

runtime/comfyui_http/         # 可选中性 HTTP transport，仅相机包依赖
```

目标依赖关系：

```text
anima-prompt-v1       -> Python standard library
minimax-h3-prompt     -> tokenizers
camera-image          -> comfyui-http-runtime
camera-video          -> comfyui-http-runtime
camera-multiview      -> comfyui-http-runtime
comfyui-http-runtime  -> Python standard library
```

任何目标包都不得依赖 `comfyui-chenxin-mcp`。

## 5. 统一 CLI 协议

每个 CLI 使用自己的命令名，不引入必须安装的中央 dispatcher：

```text
anima-prompt-v1 ...
minimax-h3-prompt ...
camera-image ...
camera-video ...
camera-multiview ...
```

公共约定：

- `--request FILE` 从 UTF-8 JSON 文件读取结构化请求；`--stdin` 从 stdin 读取。
- `--json` 输出一个完整 JSON 对象到 stdout；默认的人类输出只用于人工终端。
- stdout 不混入日志、进度或 traceback；诊断写 stderr。
- 成功退出码为 `0`。
- 参数/JSON 错误退出码为 `2`。
- 结构化请求校验失败退出码为 `3`。
- 固定资产或 Catalog 完整性失败退出码为 `4`。
- ComfyUI 连接、排队、执行或下载失败退出码为 `5`。
- 未捕获内部错误退出码为 `70`，同时把完整 traceback 写入 stderr。
- 所有路径参数在进入执行层前解析为绝对路径；输出目录不得覆盖输入资产。

命令必须返回可机器判断的字段：`ok`、`command`、`stage`、`result`、`errors`、`advisories`。失败时 `result` 为 null，`errors` 至少包含一条带 `code`、`message`、`details` 的结构化错误。Prompt 输出中的 `positive`/`negative`/`text` 只能包含可复制提示词，诊断和 provenance 放在旁路字段。完整冻结协议见 `docs/cli-protocol.md`。

## 6. Anima CLI

### 6.1 Author

```text
anima-prompt-v1 author --request brief.json --json
```

请求是结构化 `PromptBrief`，字段包括：

- `variant`
- `facts`
- `exclusions`
- `subjects`
- `relations`
- `locked_segments`
- `route`
- `source_priority`
- `trigger_words`

命令顺序必须覆盖：

```text
PromptBrief
-> quality seed
-> Catalog resolution
-> VisualRelationGraph
-> RouteDecision
-> independent positive/negative authors
-> PromptPlan
-> immutable PromptDraft
-> read-only InspectionReport
-> PromptOutput
```

返回固定五字段：

```json
{
  "positive": "...",
  "negative": "...",
  "notes": [],
  "assumptions": [],
  "advisories": []
}
```

同时返回 `phase_status`、`catalog_hits` 和 relation submission 所需的 exact record IDs，但这些元数据不能进入两个 prompt 字段。

CLI 不负责替大模型从原始自然语言生成完整 Brief。若输入只有自然语言，命令应返回结构化错误，并由 Skill LLM 先构造 Brief；简单的 `IntentParser.parse_text()` 只能作为明确标注为 heuristic 的辅助命令。

### 6.2 Inspect

```text
anima-prompt-v1 inspect --draft draft.json --brief brief.json --json
```

只读调用 `inspect_draft()`，返回 issue、severity、token estimate 和未改变的 draft 摘要。Inspector 不改写 prompt、不阻断 author 输出、不自动修复关系。

### 6.3 Catalog

```text
anima-prompt-v1 catalog search <query> [filters]
anima-prompt-v1 catalog related <record-id> [filters]
anima-prompt-v1 catalog browse [filters]
anima-prompt-v1 catalog stats
anima-prompt-v1 catalog build --source SOURCE --output DB [--manifest FILE]
anima-prompt-v1 catalog export --database DB --format jsonl|csv --output FILE [filters]
anima-prompt-v1 catalog verify --database DB [--manifest FILE]
```

搜索必须支持 `auto`、`exact`、`alias`、`prefix`、`category/facet`、`accepted related` 和 `fuzzy`，并完整输出 `TagHit` provenance。fuzzy 只能是候选，不能静默替换用户值。

现有 `anima-catalog` 保留为无 MCP 的兼容别名，内部转到新的 Catalog 子命令。

### 6.4 Relations

```text
anima-prompt-v1 relation submit --database DB --overlay FILE --payload relation.json
anima-prompt-v1 relation list --overlay FILE [--status candidate|accepted|rejected|all]
anima-prompt-v1 relation accept --overlay FILE <proposal-id>
anima-prompt-v1 relation reject --overlay FILE <proposal-id>
```

提交只验证和持久化，不推断语义。必须禁止 `cooccurrence`，只接受 exact 当前 Catalog record IDs；候选不得自动变成 accepted。

## 7. MiniMax-H3 CLI

### 7.1 Author

```text
minimax-h3-prompt author --stage t2va --request request.json --json
minimax-h3-prompt author --stage ref2va --request request.json --json
```

`t2va` 请求必须包含 `facts`、`duration_seconds`、`shot_count`、`integrated_multimodal_description`，音景和非叙事音乐可选。

`ref2va` 额外必须包含 `references`、`subject_definitions`、`summary`、`retention_analysis`、`detailed_description`。

作者必须返回：

```json
{
  "text": "...",
  "findings": [],
  "advisories": []
}
```

### 7.2 Audit

```text
minimax-h3-prompt audit --stage t2va|ref2va --request request.json --json
```

覆盖 shot 顺序、时长、镜头切换、动作落点、dialogue 保真、visible text 保真、sound/music 分离和 reference ownership。

### 7.3 Budget and tokenizer

```text
minimax-h3-prompt tokenizer verify
minimax-h3-prompt count --text FILE [--references N]
minimax-h3-prompt context-plan --request request.json --tokenizer-dir DIR --json
```

`TokenCounter` 的 manifest、文件 hash、模型 hard limit 和 H3 chat template 必须经过验证后才允许返回 `verified=true`。`plan_h3_context()` 必须真正接入 ref2va 的预算检查，不能只保留为未调用的内部函数。

## 8. Camera CLI

三个 Camera 包都采用同一组命令名，但每个包独立安装：

```text
<camera-command> describe --stage STAGE --json
<camera-command> validate --stage STAGE --envelope envelope.json --config config.json --json
<camera-command> run --stage STAGE --envelope envelope.json --config config.json --output-dir DIR --json
<camera-command> assets verify --stage STAGE --json
```

### 8.1 camera-image

阶段：`t2i-camera`、`i2i-camera`。

公开输入：

- envelope：`prompt.positive`、`prompt.negative`；
- config：`camera`、`camera_extra`、`lora`、`groups`、`sampling`、`seed`、`image_size`、`controlnet_image`、阶段允许的 `reference_image`。

不得公开 sampler、scheduler、任意节点参数、区域 prompt 组或任意 workflow JSON。

`lora.selections` 的自定义解析必须由 CLI 自己完成。它不能再调用 MCP 的 `list_local_models`；运行时接受显式 `--lora-root`/`COMFYUI_LORA_ROOT` 扫描本地 LoRA 文件，或者要求用户提交已验证的 inventory 文件。没有 inventory 时，自定义 LoRA 选择必须明确失败，默认 LoRA 栈仍可运行。

现有 `skill_data` 声明的 `red_image`、`green_image`、`blue_image`、`signature_image` 与 `RunConfig` 不一致；在契约统一前不加入 CLI。区域 prompt 组当前也被实现明确拒绝，不得从 CLI 暴露。

### 8.2 camera-video

阶段：`t2v-video`、`i2v-video`、`multi-i2v-video`。

公开输入只有：

- `prompt.text`；
- `duration`，范围 2–15 秒；
- `i2v-video` 的 `reference_image_1`；
- `multi-i2v-video` 的 `reference_image_1..3`。

固定视频 API workflow、node count、prompt/duration/image 节点映射和输出 artifact mode 必须由 manifest 校验，不允许运行时发现或替换工作流。

### 8.3 camera-multiview

阶段：`multiview`。

envelope 必须是 `{}`，config 只有：

- `full_body_image`；
- `face_image`。

固定 workflow、13 个 pose 文件、节点 `111`/`667` 映射和全部输出 artifact 必须保持 fail closed。

## 9. 直接 ComfyUI HTTP runtime

Camera 执行引擎不再调用 `McpClient`。中性 transport 提供以下能力：

```text
health() -> queue/runtime status
upload_image(path) -> uploaded filename
get_history(prompt_id) -> raw history JSON
get_artifact(filename, subfolder, type) -> bytes
enqueue(workflow) -> prompt_id
```

逻辑操作与标准 ComfyUI HTTP endpoint 的映射固定为：

- health：`GET /system_stats` 或等价的本地运行状态检查；
- upload：`POST /upload/image`；
- enqueue：`POST /prompt`；
- history：`GET /history/{prompt_id}`；
- artifact：`GET /view`。

`validate_workflow` 和 `check_workflow_runtime` 改为本地确定性校验：

- 每个 Skill 自己校验 graph schema、固定 node topology 和 asset manifest；
- ComfyUI 本地可达性由 health 检查完成；
- 不再依赖上游 MCP 的文本包装结果。

`camera-image` 目前依赖上游 MCP 的 `strip_workflow`。移除 MCP 时必须先把固定 UI workflow 转换为 API workflow 的逻辑本地化，或者发布等价的固定 API asset；不得把 strip 结果改成运行时猜测。

## 10. MCP 移除范围

实现完成后删除或移出生产路径：

- `mcp_server/`；
- 所有 `comfyui_chenxin_mcp.*` import；
- `[project.entry-points."comfyui_chenxin_mcp.skills"]`；
- `[project.entry-points."comfyui_chenxin_mcp.prompt_skills"]`；
- 安装器写入 `config.toml` 的 MCP block；
- `.mcp.json`；
- `comfyui-chenxin-mcp` 作为技能依赖；
- 文档中把 MCP 作为必须调用链的说明。

插件安装器只安装每个独立 Python 包和 Skill 文档，并验证各包的 CLI 可执行文件。

## 11. Skill 文档调用规则

每份 `SKILL.md` 必须明确：

1. 什么时候调用本 Skill；
2. 大模型先构造什么结构化请求；
3. 调用哪个 CLI 命令；
4. 如何读取 JSON 输出；
5. 哪些阶段是 `PASS`、`ADVISORY`、`UNVERIFIED`；
6. CLI 不可用时如何继续方法论流程；
7. 哪些字段绝对不能由模型或 CLI 静默补齐。

CLI 是增强能力，不是 Skill 方法论的前置条件。Prompt 脚本不可用时，大模型仍须按方法论生成，并明确标记未验证阶段。

## 12. 验收标准

- 五个 Skill 均可独立 pip 安装和调用。
- 不安装 `mcp_server`、不配置 Codex MCP，Prompt/Catalog/H3 全部测试通过。
- 不安装 `mcp_server`、只运行本地 ComfyUI，三种 Camera CLI 可完成 describe/validate/run。
- 任意 CLI 的 stdout 都是可解析 JSON 或明确的人类输出，不混入日志。
- Anima 质量策略、Catalog provenance、PromptDraft、Inspection 和 relation validation 全部保留。
- H3 shot audit、reference ownership、dialogue 保真和 token manifest 校验全部可从 CLI 触发。
- Camera 固定 workflow、manifest、节点映射和 artifact hash 验证全部保留。
- 失败时返回稳定退出码和结构化错误，不静默 fallback 到旧 workflow。
- 安装器不修改 Codex `config.toml`，也不要求重启 Codex 才能使用 Skill。
- `rg` 扫描确认生产路径不存在 `comfyui_chenxin_mcp` 依赖。
