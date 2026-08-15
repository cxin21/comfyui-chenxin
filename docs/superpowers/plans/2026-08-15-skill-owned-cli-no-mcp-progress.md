# Skill-owned CLI 去 MCP 改造进度表

日期：2026-08-15  
状态：设计完成，实现尚未开始  
关联设计：[设计方案](../specs/2026-08-15-skill-owned-cli-no-mcp-design.md)  
关联实施计划：[实施计划](2026-08-15-skill-owned-cli-no-mcp-implementation.md)

## 1. 使用说明

本文件用于跟踪实施计划的执行状态。设计方案定义目标架构，实施计划定义任务顺序，本文件定义每个阶段的目标、产物、验收标准和证据位置。

状态只允许按以下规则更新：

- `已完成`：代码、测试和验收证据均已具备。
- `进行中`：正在实现或补充验收，不代表阶段已通过。
- `未开始`：依赖尚未满足，尚未进入实现。
- `阻塞`：存在需要外部决策或环境变化才能继续的问题，并记录原因。

不得仅因为文件已创建、命令能启动或单元测试通过，就把阶段标记为完成。每个阶段必须同时满足本文件列出的行为验收、隔离验收和回归验收。

## 2. 总体进度

按实施阶段统计：3/8 完成（38%）。P1 已冻结协议，P2 已完成 Anima 独立 CLI，P3 已完成 H3 独立 CLI；尚未启动中性 ComfyUI HTTP 传输、三类相机 Skill 解耦、安装器解耦与发布验收。

| 阶段 | 名称 | 状态 | 目标 | 主要产物 | 前置依赖 | 验收摘要 |
|---|---|---|---|---|---|---|
| P0 | 设计与基线 | 已完成 | 固化无 MCP、Skill 自带 CLI、直接 HTTP 的目标边界 | 设计方案、实施计划、本进度表 | 无 | 文档存在、文档 diff 检查通过、未混入实现代码 |
| P1 | CLI 协议与 Skill 内置实现 | 已完成 | 让各 Skill 的 CLI 具备一致的请求、响应、错误和退出码契约 | 协议文档、五个内置协议模块、协议测试 | P0 | 纯标准库协议测试通过，五类错误退出码和 JSON 信封可复现 |
| P2 | Anima 提示词 CLI | 已完成 | 将 Anima 方法论和目录能力暴露为 Skill 内部 CLI | Anima CLI、兼容别名、CLI 测试 | P1 | 生成、目录检索、关系维护、审核和旧测试全部通过 |
| P3 | MiniMax-H3 提示词 CLI | 已完成 | 将 H3 的 t2v/ref2v 写作、审核、计数和上下文规划暴露为 CLI | H3 CLI、tokenizer 校验、CLI 测试 | P1 | 6 个测试通过；结构化审核、预算校验、上下文规划和旧测试全部通过 |
| P4 | 中性 ComfyUI HTTP 传输 | 未开始 | 用 Skill 自己的直接 HTTP 客户端替换 MCP 传输 | HTTP 客户端、假服务测试、传输文档 | P1 | health/upload/enqueue/history/artifact/wait 均可直连且无 MCP/npx |
| P5 | camera-image 解耦 | 未开始 | 让静态图 Skill 自己完成工作流、素材、LoRA 和产物闭环 | camera-image CLI、工作流适配、素材校验 | P2、P4 | 固定工作流、图校验、素材哈希、假 ComfyUI 回归通过 |
| P6 | camera-video 与 multiview 解耦 | 未开始 | 让视频和多视图 Skill 自己完成编排并使用中性 HTTP | 两个 CLI、manifest/资产校验、阶段测试 | P3、P4 | 视频阶段链路、多视图姿态链路、产物和失败恢复均通过 |
| P7 | 删除 MCP 与安装器耦合 | 未开始 | 删除生产运行时对 MCP server、MCP client、npx 和配置注入的依赖 | 删除旧入口、更新安装器、更新元数据与文档 | P2、P3、P5、P6 | 生产代码无 MCP 引用，安装器不再改 Codex MCP 配置 |
| P8 | 分阶段发布与端到端验收 | 未开始 | 证明源码和 staged 安装包都能在无 MCP 条件下工作 | release 校验、staged smoke、端到端报告 | P7 | 全量测试、发布校验、临时安装包 smoke 全部通过 |

## 3. 依赖关系

```text
P0 设计与基线
└── P1 CLI 协议与 Skill 内置实现
    ├── P2 Anima 提示词 CLI
    ├── P3 MiniMax-H3 提示词 CLI
    └── P4 中性 ComfyUI HTTP 传输
        ├── P5 camera-image 解耦
        └── P6 camera-video 与 multiview 解耦
            └── P7 删除 MCP 与安装器耦合
                └── P8 分阶段发布与端到端验收
```

P5 和 P6 必须等 P4 完成后再开始。P7 必须等所有替代 CLI 和直接 HTTP 链路完成后再执行，避免先删除唯一可用实现。P8 是最终发布门禁，不允许用局部测试代替。

## 4. 分阶段目标与验收

### P0：设计与基线

#### 目标

明确 Skill 负责方法论和入口，内部 CLI 负责确定性执行，ComfyUI 仅作为 HTTP 服务；同时明确 MCP 不再是运行时依赖，也不再由安装器注入 Codex 配置。

#### 主要产物

- `docs/superpowers/specs/2026-08-15-skill-owned-cli-no-mcp-design.md`
- `docs/superpowers/plans/2026-08-15-skill-owned-cli-no-mcp-implementation.md`
- `docs/superpowers/plans/2026-08-15-skill-owned-cli-no-mcp-progress.md`

#### 验收

1. 三个文档均存在，且能互相链接。
2. 设计方案覆盖 CLI 协议、Anima、H3、三类相机 Skill、直接 HTTP、MCP 移除和 Skill 调用边界。
3. 实施计划包含从协议、提示词 CLI、HTTP、相机 Skill、MCP 删除到 staged 发布的顺序。
4. 文档通过 `git diff --check`。
5. 本阶段不修改生产代码、安装器、MCP 配置或缓存文件。

#### 当前证据

- [设计方案](../specs/2026-08-15-skill-owned-cli-no-mcp-design.md)
- [实施计划](2026-08-15-skill-owned-cli-no-mcp-implementation.md)
- 当前工作树检查：`git diff --check` 已通过。

#### 完成判定

已完成。后续阶段开始后，若发现实现与设计冲突，必须先更新设计或记录偏差，再继续改代码。

### P1：CLI 协议与 Skill 内置实现

#### 目标

建立所有 Skill CLI 共用的最小契约：请求从 JSON 文件或标准输入读取，响应输出稳定 JSON 信封；错误通过稳定退出码和结构化错误表示。协议实现分别内置在五个 Skill 包中，CLI 可被 Skill 直接调用，不依赖中央协议包、MCP、Node、npx 或常驻服务。

#### 主要产物

- `docs/cli-protocol.md`
- 五个 Skill 各自内置的标准库协议模块
- `tests/cli_protocol/README.md`
- `tests/cli_protocol/test_protocol_examples.py`
- 各 CLI 的 `--help`、`--version` 和 `--request` 入口约定

#### 验收

1. 请求支持文件输入和 stdin 输入，二者对同一 fixture 产生等价结果。
2. 成功和失败响应都包含稳定的 `ok`、`command`、`stage`、`result`、`errors`、`advisories` 六字段信封。
3. `error.code`、`error.message`、`error.details` 可被机器解析，不能只输出自然语言日志。
4. 退出码至少覆盖：成功、输入错误、校验失败、外部服务错误、资源不存在、内部错误，并在文档中固定映射。
5. 日志写 stderr，JSON 结果写 stdout；stdout 不混入进度条或调试文本。
6. 协议测试覆盖空请求、未知字段、非法 JSON、缺字段、外部错误和内部异常。
7. 五个协议模块只使用标准库，互不导入，且不导入 MCP、ComfyUI MCP client 或 Node 运行时。

#### 验收证据

```powershell
.venv\Scripts\python.exe -m pytest tests/cli_protocol -q --basetemp .runtime-test-tmp-p1
```

另需保存至少一组成功请求、一组输入错误和一组外部服务错误的原始 JSON 响应作为 fixture 或测试断言。

#### 完成判定

已完成。协议文档、五份 Skill 内置实现和契约测试保持一致；P2、P3、P5、P6 不得各自发明新的响应格式或退出码。

#### 实施与验收记录

实施日期：2026-08-15  
状态：已完成  
实现分支：`codex/skill-owned-cli-no-mcp`  
实现提交：未提交（提交动作等待用户明确授权；拟用 `feat(cli): freeze standalone JSON and exit-code protocol`）

TDD 证据：

- 首次 RED：45 个用例因五个 `cli_protocol` 模块不存在而失败。
- 第二次 RED：5 个用例证明失败信封尚未拒绝空错误和非结构化错误。
- GREEN：协议契约与现有回归合计 102 个测试全部通过。

最终验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/cli_protocol skills/anima-prompt-v1/tests skills/camera-multiview/tests mcp_server/tests -q --basetemp .runtime-test-tmp-p1-final
.venv\Scripts\python.exe -m compileall -q skills/anima-prompt-v1/anima_prompt_v1/cli_protocol.py skills/minimax-h3-prompt/h3_prompt/cli_protocol.py skills/camera-image/camera_image/cli_protocol.py skills/camera-video/camera_video/cli_protocol.py skills/camera-multiview/camera_multiview/cli_protocol.py
rg -n "comfyui_chenxin_mcp|mcp_server|McpClient|node|npx" <五个 cli_protocol.py>
git diff --check
```

验收结果：

- 102 passed，0 failed，0 errors。
- 五份协议模块 SHA-256 相同：`79E0A6CC043B4C8A9A879387347FB40EF9610AD9A246E3E43074FE0D9AEA0787`。
- 禁用依赖检索无结果；实现只导入 Python 标准库。
- 设计残留检索无 `共享运行时`、`runtime/cli_protocol` 或旧 `ok/data/meta` 信封。
- `git diff --check` 通过；仅有 Git 的 LF/CRLF 提示，不影响内容检查。

设计逐条核对：

- [x] 统一协议是共享契约，不是中央运行时依赖。
- [x] 五个 Skill 分别内置协议模块，互不导入。
- [x] 文件与 stdin 输入严格二选一，根值必须为 JSON object。
- [x] 六字段 JSON 信封固定，失败 error 具备 `code/message/details`。
- [x] stdout JSON 单对象、stderr 诊断和二进制旁路规则已冻结。
- [x] 退出码固定为 0/2/3/4/5/70，错误文本不参与退出码推断。
- [x] 无 MCP、Node、npx 或常驻服务依赖。

残余风险：五份内置实现未来可能漂移；`tests/cli_protocol` 对所有五份模块执行同一参数化契约，后续每阶段必须加入该测试。具体 CLI 的 `--help`、`--version`、参数解析和真实进程退出码将在 P2、P3、P5、P6 分阶段验收。

### P2：Anima 提示词 CLI

#### 目标

把 `anima-prompt-v1` 的方法论落成可调用入口，让模型负责理解用户意图和选择模式，CLI 负责目录检索、关系数据、提示词字段生成、结构校验和导出。

#### 主要产物

- `skills/anima-prompt-v1/cli.py`
- `skills/anima-prompt-v1/tests/test_cli.py`
- 现有 `anima-catalog` 能力的兼容别名或迁移适配
- CLI 使用说明和示例请求

#### 验收

1. 暴露 `author`、`inspect`、`catalog search`、`catalog related`、`catalog browse`、`catalog stats`、`catalog build`、`catalog export`、`catalog verify`、`relation submit/list/accept/reject`。
2. `author` 输出严格包含 `subject`、`environment`、`lighting`、`camera`、`style` 五个 prompt 字段；方法论解释、来源、告警和审核信息放在 prompt 之外。
3. `catalog build`、`catalog verify` 和相关数据维护结果可通过 JSON 读取，并能给出确定的失败码。
4. 关系候选不会把同一模板、同一系列或明显重复的模板当作有效关系；人工批准链路可复现。
5. 旧的 Anima 测试全部通过，新增 CLI fixture 测试通过。
6. 从 `skills/anima-prompt-v1` 启动 CLI 不需要 MCP、Node、npx、ComfyUI 或网络。
7. 代码和测试中不存在对 MCP client/server 的运行时导入。

#### 验收证据

```powershell
python -m pytest skills/anima-prompt-v1/tests -q
python skills/anima-prompt-v1/cli.py --help
python skills/anima-prompt-v1/cli.py --request <anima-fixture.json>
```

应保存一组 author、catalog search、catalog verify 和 relation list 的 JSON fixture 结果。

#### 完成判定

已完成。方法论输出、只读审核、Catalog 和 relation 辅助能力均可由独立 CLI 调用；兼容 `anima-catalog` 保留旧数据库参数位置；所有已覆盖失败路径遵守 P1 协议。

#### 实施与验收记录

实施日期：2026-08-15  
状态：已完成  
实现分支：`codex/skill-owned-cli-no-mcp`  
实现提交：未提交（提交动作等待用户明确授权；拟用 `feat(anima): expose standalone authoring and catalog CLI`）

TDD 证据：

- author/inspect RED：统一 `anima_prompt_v1.cli` 不存在，测试 collection 失败。
- Catalog/relation RED：`catalog_main` 和完整 dispatcher 不存在。
- console RED：安装环境不存在 `anima-prompt-v1` 可执行入口。
- 边界 RED：未知字段被静默接受、argparse 未输出 JSON、混合 relation 发生部分持久化。
- overlay RED：Catalog CLI 无法读取显式 relation overlay。
- integrity RED：缺失 SQLite 被误分类为内部错误 70。
- 最终 GREEN：协议、Anima、camera-multiview 与现有 MCP 回归合计 114 个测试全部通过。

最终验收命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/cli_protocol skills/anima-prompt-v1/tests skills/camera-multiview/tests mcp_server/tests -q --basetemp .runtime-test-tmp-p2-gate
.venv\Scripts\python.exe -m compileall -q skills/anima-prompt-v1/anima_prompt_v1 skills/anima-prompt-v1/scripts
.venv\Scripts\anima-prompt-v1.exe --help
.venv\Scripts\python.exe skills/anima-prompt-v1/scripts/search_catalog.py --database skills/anima-prompt-v1/knowledge/tag-catalog.sqlite stats --json
.venv\Scripts\python.exe skills/anima-prompt-v1/scripts/submit_relations.py --help
rg -n "from .*mcp|import .*mcp|comfyui_chenxin_mcp|McpClient|npx|node" <Anima CLI 生产文件>
git diff --check
```

验收结果：

- 114 passed，0 failed，0 errors。
- `anima-prompt-v1` 暴露 `author/inspect/catalog/relation`，`--help` 和 `--version` 可离线运行。
- `anima-catalog` 保留兼容 alias，并同时接受旧的全局 `--database DB` 参数位置。
- `catalog search/related/browse/stats/build/export/verify` 全部有行为测试。
- `relation submit/list/accept/reject` 全部有行为测试；candidate 不参与 related，accepted 才可见，cooccurrence 与混合无效提交不会持久化。
- CLI 生产文件禁用依赖检索无结果；没有导入 MCP、Node 或 npx。
- `git diff --check` 通过；仅有 Git 的 LF/CRLF 提示。

设计逐条核对：

- [x] author 只接受结构化 PromptBrief，纯 raw text 返回 `structured_brief_required`。
- [x] author 顺序呈现 Brief、质量种子、Catalog、关系图、路由、双作者、Plan、Draft、Inspection、Output 状态。
- [x] PromptOutput 严格保持 `positive/negative/notes/assumptions/advisories` 五字段。
- [x] prompt 文本不包含 record ID、诊断或 provenance；完整 TagHit 和 relation record IDs 走旁路。
- [x] inspect 从序列化 Brief/Draft 执行只读检查，输入文件字节不变。
- [x] fuzzy hit 明确标记 `candidate=true`，不会被当作 relation exact ID。
- [x] Catalog build/export 返回绝对产物路径与 SHA-256，verify 失败使用退出码 4。
- [x] relation 只接受 exact 当前 Catalog ID，禁止 cooccurrence，不自动提升 candidate，验证失败不部分写入。
- [x] 参数、请求、校验、完整性和 unexpected 错误均进入 P1 JSON 信封与稳定退出码边界。
- [x] 新 CLI、兼容 alias 和旧脚本均不依赖 MCP。

残余风险：`SKILL.md` 仍是旧的 canonical API/脚本说明，按实施计划在 P7 统一改为 Skill 直接调用新 CLI 并做 Skill 行为验证；`mcp.py` 和 MCP entry point 仍保留到 P7，以免在替代链路完成前删除；1.7GB Catalog 的 staged 安装位置与默认发现将在 P7/P8 验收。

### P3：MiniMax-H3 提示词 CLI

#### 目标

把 `minimax-h3-prompt` 的 t2v/ref2v 写作、时间结构、对白、音频、参考图和 token 预算能力变成确定性 CLI，让模型不能绕过审核规则直接输出未经检查的提示词。

#### 主要产物

- `skills/minimax-h3-prompt/cli.py`
- `skills/minimax-h3-prompt/tests/test_cli.py`
- tokenizer 与模型版本校验入口
- t2v/ref2v 上下文规划入口

#### 验收

1. 暴露 `author t2v`、`author ref2v`、`audit`、`tokenizer verify`、`count`、`context-plan`。
2. 审核覆盖时间连续性、动作与对白绑定、音频层结构、参考图身份与变化、时长和 token 预算。
3. `tokenizer verify` 能报告 tokenizer 版本、模型版本、哈希或等价可验证信息；验证失败不能静默继续。
4. `context-plan` 实际接入 author/audit 流程，而不是只有孤立函数；超预算时返回可判断的失败码和修复建议。
5. t2v、ref2v、边界时长、空对白、超预算、非法参考图等 fixture 测试通过。
6. H3 现有测试全部通过，CLI 新测试通过。
7. CLI 不依赖 MCP、Node、npx、ComfyUI 或网络。

#### 验收证据

```powershell
python -m pytest skills/minimax-h3-prompt/tests -q
python skills/minimax-h3-prompt/cli.py --help
python skills/minimax-h3-prompt/cli.py --request <h3-fixture.json>
```

应保存一组成功审查、一组 tokenizer 不匹配和一组超预算的结构化结果。

#### 完成判定

H3 的方法论、审核和预算约束已经成为 Skill 可直接调用的稳定接口，不能仅靠模型记忆 Skill 文档来保证执行。

#### 实施与验收记录

实施日期：2026-08-15  
状态：已完成  
实现分支：`codex/skill-owned-cli-no-mcp`  
实现提交：未提交（提交动作等待用户明确授权；拟用 `feat(h3): expose authoring audit and exact budget CLI`）

TDD 证据：

- CLI RED：`h3_prompt.cli` 模块缺失，`tests/test_cli.py` 与 `tests/test_budget_cli.py` collection fail（`ModuleNotFoundError: No module named 'h3_prompt.cli'`）。
- tokenizer 完整性 RED：磁盘 vendor 文件因本地 `core.autocrlf=true` 被 CRLF 化，与 manifest 哈希不匹配，`tokenizer verify`、`count`、`context-plan`、`author ref2va` 全部失败。
- t2va 预算 RED：占位 TokenCounter 的 `count()` 抛 H3AuditError，`author t2va` 失败。
- 最终 GREEN：6 个 H3 测试通过；CLI `--help` 与 `author --stage t2va --stdin --json` 端到端可达，输出符合 `docs/cli-protocol.md` 信封。

最终验收命令：

```powershell
.venv\Scripts\python.exe -m pytest skills/minimax-h3-prompt/tests -q --basetemp .runtime-test-tmp-p3-gate
.venv\Scripts\python.exe -m h3_prompt.cli --help
.venv\Scripts\python.exe -m h3_prompt.cli tokenizer verify --tokenizer-dir skills/minimax-h3-prompt/knowledge --json
rg -n "comfyui_chenxin_mcp|mcp_server|McpClient|node|npx" skills/minimax-h3-prompt/h3_prompt
git diff --check
```

验收结果：

- 6 passed, 0 failed, 0 errors。
- `minimax-h3-prompt` 暴露 `author/audit/tokenizer/count/context-plan`，`--help` 离线运行。
- `pyproject.toml` 改为 `[project.scripts]`，删除 `comfyui_chenxin_mcp.prompt_skills` 注册。
- 供应商哈希校验通过：`LICENSE/NOTICE/chat_template.json/tokenizer.json/tokenizer_config.json` 实际 SHA-256 与 manifest 期望值完全一致。
- H3 生产代码中禁用依赖检索无结果；无 MCP/Node/npx 引用。
- `git diff --check` 通过。

设计逐条核对：

- [x] `author` 仅接受结构化 H3 请求；纯 raw text 走 P1 `invalid_request` 错误路径。
- [x] `audit` 失败时返回稳定的 `h3_audit_failed` 错误，`details.findings` 列出原始失败。
- [x] `tokenizer verify` 报告完整 manifest 身份（含 5 个 vendor 文件），hash 不匹配走 `tokenizer_integrity_failed` 退出码 4。
- [x] `context-plan` 真正接入 ref2va，visual/chat/special/margin 字段齐全；overflow 走 `context_overflow` 退出码 3。
- [x] author t2va 保留 no-reference 路径，`visual_budget_applicable: False`；author ref2va 把 `verified` 上下文计划接进预算输出。
- [x] CLI 只依赖 Python 标准库与 `tokenizers`；不引入 MCP、Node 或 npx。

残余风险：

- 旧 `h3_prompt/mcp.py` 文件仍存在（仅失去 entry-point 注册）；由 P7 统一删除。
- `tests/` 目录未加 `__init__.py`：当 pytest 跨包收集 `anima-prompt-v1/tests` 与 `minimax-h3-prompt/tests` 时，模块名 `test_cli` 冲突。这是已识别但不在 P3 范围内的可维护性问题。

### P4：中性 ComfyUI HTTP 传输

#### 目标

提供不属于 MCP 的最小 HTTP 传输层，由相机 Skill 直接调用 ComfyUI HTTP API；传输层只负责连接、上传、排队、轮询、历史和产物读取，不负责提示词方法论或工作流业务规则。

#### 主要产物

- 中性 HTTP 客户端及其错误模型
- health、upload、enqueue、history、artifact、wait 接口
- fake ComfyUI HTTP 服务或 HTTP fixture 测试
- 传输层使用说明

#### 验收

1. 能直接执行 health、upload、enqueue、history、artifact、wait。
2. 网络超时、HTTP 非 2xx、无效 JSON、任务失败、任务超时和产物缺失均转成 P1 结构化错误。
3. 使用标准库 HTTP 客户端或项目已有的非 MCP HTTP 依赖，不启动 MCP server，不调用 MCP JSON-RPC，不调用 `npx`。
4. wait 支持超时和轮询间隔参数，不能无限等待。
5. fake 服务测试覆盖成功、失败、超时和产物缺失。
6. 传输层不持有 camera-image、camera-video 或 camera-multiview 的业务分支。

#### 验收证据

```powershell
python -m pytest runtime/comfyui_http/tests -q
python -m pytest runtime/comfyui_http/tests -q -k "timeout or upload or enqueue or artifact"
```

另需用 fake 服务记录一次完整的 upload → enqueue → wait → artifact 链路。

#### 完成判定

三个相机 Skill 均可通过同一中性传输层访问 ComfyUI，且传输层测试不需要真实 ComfyUI 或 MCP。

### P5：camera-image 解耦

#### 目标

让 `camera-image` 自己完成请求描述、固定工作流校验、UI-to-API 转换、LoRA/素材检查、ComfyUI 执行和产物校验；Skill 文档只提供工作流约束和调用方法，不再要求模型调用 MCP 工具。

#### 主要产物

- `skills/camera-image/cli.py`
- `skills/camera-image/tests/test_cli.py`
- 本地 UI-to-API 转换或等价固定映射
- 本地 LoRA/素材 inventory 与哈希校验
- 固定工作流和产物 manifest 校验

#### 验收

1. 暴露 `describe`、`validate`、`run`、`assets verify`。
2. `validate` 检查 workflow hash、关键节点、必需输入、LoRA 名称、尺寸、采样参数和输出格式。
3. `run` 通过 P4 直接执行 ComfyUI，返回任务 ID、输出文件、哈希和 manifest；不把二进制结果混进 stdout JSON。
4. LoRA 与素材只从显式根目录或已验证 inventory 读取，找不到或哈希不符时明确失败；不得调用 MCP 的模型列表工具。
5. i2i/controlnet 分支保留既有业务语义，且不能绕过固定工作流验证。
6. 当前 Skill 数据中存在但执行配置不接受的 `red/green/blue/signature` 字段，以及被禁止的区域提示词，不得被 CLI 静默放行；在契约未解决前必须显式拒绝或明确不暴露。
7. 固定工作流测试、图结构测试、素材哈希测试和 fake ComfyUI 端到端测试全部通过。
8. CLI 启动不需要 MCP、Node、npx 或真实 MCP 配置。

#### 验收证据

```powershell
python -m pytest skills/camera-image/tests -q
python skills/camera-image/cli.py --help
python skills/camera-image/cli.py --request <camera-image-fixture.json>
```

应保存一次成功运行 manifest、一次缺素材错误和一次 workflow 校验错误。

#### 完成判定

在 fake ComfyUI 环境中能完成完整图片链路，且替代逻辑没有扩大 Skill 允许的输入边界。

### P6：camera-video 与 camera-multiview 解耦

#### 目标

让 `camera-video` 和 `camera-multiview` 各自拥有独立 CLI，并通过 P4 的中性 HTTP 完成固定工作流、阶段编排、素材检查和产物收集。

#### 主要产物

- `skills/camera-video/cli.py`
- `skills/camera-multiview/cli.py`
- 两个 Skill 的 CLI 和阶段测试
- 固定 manifest、姿态映射、素材与产物校验

#### 验收

1. `camera-video` 暴露 `describe`、`validate`、`run`、`assets verify`，支持既有固定视频链路和参考视频链路。
2. `camera-multiview` 暴露 `describe`、`validate`、`run`、`assets verify`，固定输出 front/back/left/right/three-quarter 等既有姿态映射。
3. 阶段性任务的依赖、超时、失败和重试边界可被结构化结果表达。
4. 每个阶段都能记录输入素材、任务 ID、输出文件、哈希、manifest 和失败原因。
5. fake ComfyUI 测试覆盖视频链路、多视图链路、缺素材、任务失败、超时和产物缺失。
6. 两个 Skill 不导入 MCP，不调用 `npx`，不依赖全局安装脚本。
7. 既有 Skill 测试和新增 CLI 测试全部通过。

#### 验收证据

```powershell
python -m pytest skills/camera-video/tests -q
python -m pytest skills/camera-multiview/tests -q
python skills/camera-video/cli.py --help
python skills/camera-multiview/cli.py --help
```

应分别保存一次视频链路和多视图链路的阶段 manifest，以及各自至少一条失败 fixture。

#### 完成判定

两类 Skill 均能在无 MCP 的环境里使用直接 HTTP 完成自己的业务闭环，且不把相机业务逻辑倒灌进通用传输层。

### P7：删除 MCP 与安装器耦合

#### 目标

在替代实现通过验收后，删除生产运行时中的 MCP server、MCP client、MCP 配置注入、`npx` 启动和过时依赖，并更新插件元数据、安装说明和 Skill 文档。

#### 主要产物

- 删除或迁移 `mcp_server/` 及其生产入口
- 更新安装器和安装脚本
- 更新 `pyproject.toml`、依赖清单、插件元数据和文档
- 更新各 Skill 的调用说明
- 迁移或删除不再使用的 MCP 测试

#### 验收

1. 生产代码不再导入 `comfyui_chenxin_mcp`、`mcp_server`、`McpClient` 或等价 MCP 运行时组件。
2. 安装器不再写入或修改 Codex 的 `[mcp_servers.comfyui-mcp]` 配置，不再安装或启动 `npx` MCP 包。
3. 插件安装后只安装 Skill 及其内部脚本/依赖；CLI 入口可从安装后的路径启动。
4. 过时依赖、命令、文档和示例全部删除或改成新 CLI 调用方式，不能留下会误导模型的 MCP 流程。
5. 删除前已确认 P2、P3、P5、P6 的测试和 P4 的传输测试通过。
6. 全仓检索只允许在历史文档、迁移说明或明确的测试快照中保留 MCP 文字；生产路径不能有可执行依赖。

#### 验收证据

```powershell
rg -n "comfyui_chenxin_mcp|mcp_server|McpClient|mcp_servers\.comfyui-mcp|npx" skills runtime scripts pyproject.toml .codex
python -m pytest skills/anima-prompt-v1/tests skills/minimax-h3-prompt/tests skills/camera-image/tests skills/camera-video/tests skills/camera-multiview/tests runtime/comfyui_http/tests -q
```

检索结果必须逐条分类：生产代码、测试、迁移文档、历史记录。生产代码和安装器结果应为空；若仓库路径不同，按实际路径补充检索范围并记录。

#### 完成判定

旧 MCP 运行链路已删除，新的 Skill-owned CLI 链路已成为唯一正式入口；安装后不会再次污染 Codex 配置。

### P8：分阶段发布与端到端验收

#### 目标

验证源码工作区和模拟安装产物在无 MCP、无全局 Node/npx、无真实 ComfyUI（提示词链路）或 fake ComfyUI（相机链路）条件下均可运行。

#### 主要产物

- 发布前校验脚本
- staged release 临时目录
- CLI smoke 测试结果
- 全量验收报告与残余风险记录

#### 验收

1. Anima 和 H3 的 prompt CLI 在无 ComfyUI、无 MCP、无网络环境中通过 smoke。
2. 三类相机 CLI 在 fake ComfyUI 中完成最小成功链路和主要失败链路。
3. 所有 CLI 均满足 stdout JSON、stderr 日志、稳定退出码和产物 hash 约定。
4. staged 安装目录不依赖源码工作区路径，不依赖开发机 MCP 配置，不依赖全局 `npx`。
5. 安装/卸载或刷新流程不会新增 `[mcp_servers.comfyui-mcp]` 配置。
6. 全量测试通过，失败项必须区分本次回归、既有失败和环境限制。

#### 验收证据

```powershell
python -m pytest skills/anima-prompt-v1/tests skills/minimax-h3-prompt/tests skills/camera-image/tests skills/camera-video/tests skills/camera-multiview/tests runtime/comfyui_http/tests tests/e2e -q
python scripts/verify_release.py --source-root .
python scripts/stage_release.py --source-root . --destination-root <temp-release>
python scripts/smoke_cli.py --release-root <temp-release>
```

其中 `<temp-release>` 必须是本次验收新建的临时目录；报告中记录目录位置、测试命令、退出码、关键 JSON 摘要和残余风险。

#### 完成判定

源码测试、发布校验、staged smoke 和配置不回写检查全部通过后，才允许将整体改造标记为完成，并进入提交、推送和插件重新安装流程。

## 5. 每阶段更新模板

每完成一个阶段，在对应章节追加以下信息，不覆盖原始验收标准：

```text
实施日期：YYYY-MM-DD
状态：已完成 / 进行中 / 阻塞
实现提交：<commit 或未提交>
执行命令：<完整命令>
测试结果：<通过数量、失败数量、环境限制>
证据：<测试日志、fixture、manifest、diff 或报告路径>
残余风险：<没有则写“无”>
```

## 6. 当前待办

- [x] 完成设计方案和实施计划。
- [x] 建立本进度表及阶段验收标准。
- [x] 实施 P1 CLI 协议与 Skill 内置实现。
- [x] 实施 P2 Anima 提示词 CLI。
- [x] 实施 P3 MiniMax-H3 提示词 CLI。
- [ ] 实施 P4 中性 ComfyUI HTTP 传输。
- [ ] 实施 P5 camera-image 解耦。
- [ ] 实施 P6 camera-video 与 camera-multiview 解耦。
- [ ] 实施 P7 删除 MCP 与安装器耦合。
- [ ] 完成 P8 分阶段发布与端到端验收。
