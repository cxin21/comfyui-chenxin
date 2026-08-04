---
name: prompt-forge
description: Use when compiling prompts for image or video models, or when an explicitly approved local ComfyUI generation needs an auditable PromptBuild, ExecutionPlan, artifact, and RunRecord.
---

# Prompt Forge

The runtime CLI now also provides `submit-character-base` for the approved and consumed Stage 1 graph, `submit-stage` for Stage 3/4, and `wait-stage` for read-only terminal polling. These commands do not approve, rebuild a plan, or retry an uncertain enqueue; they only cross the loopback transport boundary after the corresponding evidence has been validated.

## Stage 3/4 execution contract

The character-to-video pipeline is ordered and fail-closed:

1. `accept-reference` is the only transition that makes a verified Flux angle reusable by Stage 3.
2. `plan-stage-execution` binds the Stage 3 camera img2img or Stage 4 Yusu Director graph to a fresh local capability report, profile hash, and immutable PromptBuild lineage.
3. `approve-stage` requires a newly displayed exact draft hash; `consume-stage` uses an exclusive one-time consumption record.
4. `build-stage-submission` reconstructs the exact graph/request. Only `submit_stage(...)` with an injected trusted-local enqueue callable and the canonical consumed-namespace receipt path may cross the external side-effect boundary; it first writes an exclusive submission-intent sentinel. `runtime.comfy_submit.ComfyPromptSubmitter` is transport-only and must be injected there; calling its POST method directly bypasses approval and idempotency evidence.
5. `record-stage` requires a succeeded receipt, matching raw ComfyUI history (the raw history is mandatory), and a verified PNG/video artifact with lineage and technical metadata. For Stage 1, `submit-character-base` now provides the same consumed intent/receipt boundary; `record` may bind that submission, consumption file, receipt file, and raw history into the RunRecord.

Never synthesize approval from chat text, never treat a UI screenshot as an executable graph, and never claim a ComfyUI enqueue without a real response receipt. The camera source has one explicit `normalize-camera` bridge for the observed converter losses (LoRA widget text, disabled output switch and known orphan branches); it is an allowlisted, pinned repair of an MCP-produced graph, not a generic UI-to-API converter or a hand-written workflow. Any other conversion error remains a hard stop.

### Camera source normalization

For `文生图相机视角.json`, retain the exact UI workflow and the MCP-produced API/strip graph as source evidence. If MCP conversion reports the known missing `Lora Loader (LoraManager).text` or missing `images` on nodes `35/490`, call `runtime_cli.py normalize-camera` with `{api_graph, ui_workflow, profile}`. The command first requires UI node `26` to remain the profiled `Lora Loader (LoraManager)` and rejects a non-empty API LoRA text that conflicts with the UI literal; only the observed missing/`null` input is repaired. It verifies the pinned post-process chain `76 → 96 → 111`, reconnects both output sinks to node `111`, and removes only the pinned orphan set `[28, 41, 52, 62, 67, 70, 77]` after proving no removed node feeds a retained node. Then re-run MCP `validate_workflow(health=true)` and `check_workflow_runtime`; only zero errors, zero health warnings, `runtime=local`, an unchanged saved workflow, and a UI fingerprint matching the verified `camera-anima-v1` profile can proceed. The normalized graph hash—not the broken pre-normalization graph hash—must be used consistently in the draft, approval, submission, history, and RunRecord lineage.

### Production workflow selection (2026-08-03)

The production Stage 2 profile is `flux2-klein-multiview-flat-v2` and loads
`PromptForge-Flux2-Klein-multiview-flat-v2.json`. Its live UI fingerprint is
`9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da`; the
current API graph validates with zero errors and zero health warnings and is
classified as local. The similarly named original
`Flux2-Klein人物一键多视图工作流.json` remains an audit/reference candidate,
not the production path, because its current converter output contains
unresolved custom-node buses and dangling references. Do not silently fall back
to that graph: if the promoted flat profile is unavailable or its fingerprint,
API hash, runtime, or validation evidence drifts, stop before upload or enqueue.
The promoted output map labels node `761` as `rear_45` and node `609` as `rear`;
node `565` emits a mixed side-view batch and remains `side_unknown` until
per-image batch semantics are explicitly profiled.
Stage 4 accepts only profile `ltx-yusu-director-v1` with the exact UTF-8 saved
workflow name `LTX全新导演台工作流.json`; a caller-authored or mojibake profile
is rejected before the Yusu timeline is patched. The profile also pins the live
Director graph's model, all three LTX LoRAs (including the guide LoRA), Euler
sampler, `linear_quadratic` scheduler, and the active `1280x720` selector. The
saved `custom_height=736` value is intentionally not treated as active because
the selector's `use_custom_resolution` is false; drift in any pinned node is
rejected before the timeline patch. The selector is a target box: the fixed
Stage 3 camera canvas plus `maintain aspect ratio` and 32-pixel snapping produce
an effective `1024x704` video canvas, which is part of the profile and is checked
from ffprobe metadata at artifact acceptance. LTX's 24 logical timeline frames
decode on the `8n+1` lattice to 25 output frames. The complete profile digest is
pinned in the Stage 4 execution boundary, so a caller cannot remove a contract
and replace it with a self-authored profile hash.

Prompt Forge 把用户意图编译为模型方言，并把本地 ComfyUI 执行绑定到可审计证据。默认只编译；生成是独立阶段。编译器始终保持 `execution.performed=false`。

## 不可突破的边界

- 用户显式事实优先于 recipe 和推断，所有显式事实锁定。
- 不安装模型或自定义节点，不修改或保存用户工作流，不清空 history/output。
- 仅执行经过能力协商、UI→API 转换、验证、指纹核对和明确审批的本地计划。
- 一次只允许一个 ComfyUI job；paid、mixed、unknown runtime 一律拒绝。
- 不假设 MCP 工具名存在。先检查当前实际可调用能力，再选择对应工具。

## v7 顺序合同

必须按以下顺序执行；任一硬门失败即停止，不跳步。

### 1. TaskContext

先建立 `TaskContext 1.0` 四象限：

1. `shared_known`: goal、background、acceptance、boundaries。
2. `user_known_agent_unknown`: references、aesthetic_preferences、real_world_constraints。
3. `agent_known_user_unknown`: capabilities、risks、alternatives。
4. `shared_unknown`: hypotheses、experiments。

不要重复询问 `shared_known`。整个任务最多提出 3 个会实质改变 artifact、workflow 选择或安全边界的澄清问题。非实质未知不询问：把假设写入 TaskContext，并把共享未知写成单变量、可证伪实验。展示后的执行审批是独立安全门，不占澄清问题预算。

### 2. PromptBuild

解析本 Skill 所在目录为 `SKILL_ROOT`，使用绝对路径调用内部脚本。

1. 确定 `target`、`generation_mode`、`mode`、模型、尺寸/时长、参考素材和 locked facts。
2. 用 `internals/recipe_lookup.py` 解析模型 recipe；未命中或 modality 冲突即停止。
3. 按 `references/prompt-contracts.md` 构造 `PromptIntent 6.1`。tag 方言只接受 exact/approved-alias；recipe control token 与语义 tag 分开。
4. 将 `intent` 和 `draft` 送入：

```text
python "<SKILL_ROOT>/internals/prompt_compile.py" --from-stdin
```

`ready_to_execute=false` 时只修正并重新编译。`mode=compile` 到此结束，交付 PromptBuild，不触碰 ComfyUI。

### 3. Capability discovery

执行模式先通过 `runtime/runtime_cli.py discover` 获取 10 分钟有效的 CapabilityReport，并从当前 MCP 工具注册表协商真实能力。至少确认：本地 URL、队列为空、硬件、节点、保存工作流，以及 MCP 是否具备 workflow load、UI→API conversion、strip/slice、runtime classification、validation、enqueue、monitor、artifact/history retrieval 等能力。

REST 只可作为 health、queue、object info、saved workflow 和 history 的只读回退；唯一例外是审批/消费之后显式调用 `submit-character-base` 或 `submit-stage`，它们只把已重建且已消费的请求交给 loopback transport，并由 intent/receipt 记录一次性副作用。能力缺失时说明缺口和安全替代方案，不虚构工具，不自行实现通用 UI→API 转换器；相机只允许使用上面的 pinned normalization bridge。`wait-stage` 只轮询 history，不会重新提交。

### 4. MCP load / strip / validate

由已协商到的 MCP 能力加载用户指定的保存工作流，并负责 UI→API 转换、strip/slice、runtime classification 与 executable validation。禁止让 Python runtime 猜 widget-to-input 映射；相机的 `normalize-camera` 只执行 profile 中已观察、可审计的差异。受控 orchestrator 必须在相邻执行证据中保留未修改的 source API graph（`raw_source_api_graph_hash`）、normalized executable source（`normalized_source_api_graph_hash`）和归一化结果；runtime draft 当前的 `source_api_graph_hash` 明确指 normalized source hash。saved workflow 保持不变。若 caller 丢失 raw graph 或无法证明 normalized source 来自同一份 source，必须停止，不得用 normalized graph 反推来源。

### 5. Fingerprint

对实际 UI workflow 运行 `runtime_cli.py fingerprint`。指纹必须与已批准 WorkflowProfile 匹配，语义 slot 必须唯一解析。漂移、歧义或无法证明指定 workflow 与 API graph 的对应关系时 fail closed。

### 6. ExecutionDraft

将 PromptBuild、当前 CapabilityReport、profile、实际 UI workflow、source API graph 和 allowlisted patches 送入 `runtime_cli.py plan`。该命令先完成全部质量、能力、profile、UI/API、patch 与 preflight 校验，只能返回 `plan_state=draft`、`execution_approved=false` 和自洽 `draft_hash`。它不接受任何 approval 布尔值。模型、LoRA、sampler、scheduler 和图结构默认不可变。

### 7. 展示实际 draft

enqueue 前向用户展示最终 positive prompt、negative prompt、workflow/profile、完整 graph mutation/patches、immutable inputs、预期输出、主要风险、单变量实验和 exact `draft_hash`。初始“生成”请求只允许准备 draft；`true`、旧授权或未绑定本次 hash 的确认都不是审批。

### 8. 明确审批

展示后才可从外部取得新的 approval event。事件必须精确绑定所展示的 `draft_hash`，且包含 `decision=approved`、UTC `displayed_at/approved_at/expires_at`、`scope=enqueue-once`、非空 `actor/source`，以及 caller run-dir 的 canonical resolved absolute `consumption_root`；该目录必须已存在，不能使用相对路径、parent/child 替换或 symlink/path alias。顺序为 `displayed_at <= approved_at <= trusted_now < expires_at`，总窗口不超过 600 秒。不要自动生成事件，不要把对话意图改写成事件，也不要交互式假确认。

把 `{draft, approval_event}` 送入 `runtime_cli.py approve-plan --run-dir <dir>`。只有该命令返回的 `plan_state=approved`、`execution_approved=true` 计划可进入执行；approval event、approved plan 与 `approval_id` 必须在 caller run-dir 相邻保留。内容修改、错误 hash、事件过期、能力报告过期、workflow/profile 漂移或队列变化都使审批失效，必须重建、重展示并取得新事件。

需要跨进程等待审批时，使用 runtime 的 `write_pending_bundle` exclusive-create immutable bundle（Stage 2 文件名为 `pending-c-<draft_hash>.json`）：它绑定 exact draft、stage-specific frozen critical inputs、canonical `consumption_root`、`<stage>:<draft_hash>` consumption namespace、created/expiry UTC 时间与 `bundle_hash`。恢复只能用 `load_pending_bundle` 对该绝对 canonical 路径执行 exact-hash、stage、frozen-input、namespace 和 expiry 校验；parent/child/alias/symlink、跨 stage、篡改或超过 600 秒一律拒绝。bundle 不替换新的 CapabilityReport，也不重跑前序实验。

### 9. Enqueue

批准后获取新的只读 CapabilityReport，只用于确认当前资源、runtime classification 和队列安全；它不能替换 frozen report 或改变获批 draft。生成稳定 `enqueue_request_id`，把 `{approved_plan, enqueue_request_id}` 送入 `runtime_cli.py consume-approval --run-dir <consumption_root>`。`approve-plan` 与 `consume-approval` 的 `--run-dir` 都必须 exact 等于 approval event 和 bundle 绑定的 canonical root；sentinel 只能写入该 namespace。只有 atomic exclusive-create `<approval_id>.consumed.json` 成功后才能 POST；该文件已存在时一律拒绝，即使内容相同也不得幂等复用。

consume 成功后使用实际协商到的 MCP enqueue/monitor 能力提交 executable API graph，并把同一 `enqueue_request_id` 传给服务端。一次只提交一个 job。POST 超时、断连或返回不确定时不得删除 consumption 或盲目重试；服务器可能已经接收，必须先按 request/client id 查询 history。等待 terminal success/failure 后才开始下一实验。不要调用保存工作流、安装、删除或清理接口。生产路径必须有真实 MCP 能力协商证据；live REST A/B 只属于 render/graph characterization，不能证明 MCP 路径合规。

### 10. Artifact verification

从 raw ComfyUI history 取得 prompt ID、真实 executable graph、terminal status 和 output descriptors；不得用摘要代替 raw history。raw-history graph 必须与获批并提交的 executable graph canonical-equal，否则拒绝 RunRecord。逐个验证新 output artifact 存在、可解码，且绝对路径位于已确认的 ComfyUI output 根目录内（`record-stage` 可用 `artifact_root` 显式绑定），并计算 SHA-256。只有 terminal success 与 artifact 均验证后才能声称生成成功。

### 11. RunRecord

使用 `runtime_cli.py record --run-dir <dir>` 消费 raw history，生成并保留 append-only RunRecord。Record 只接受 `approve-plan` 产出的 approved plan，并重验 draft lineage、approval event/ID、plan hash、source/executable graph 与 PromptBuild。Record 保存 TaskContext/PromptBuild hashes、完整 PromptBuild、ExecutionPlan、已核对的 history status/output descriptors、prompt ID 与 artifact hashes；若输入 Stage 1 的 submission/consumption/receipt 证据，还会保存这些对象及 hash、原始 history 及 hash，并核对 history 中的 stable enqueue request。文件名为 `<record_hash>.json`：同内容重复写入幂等，不同内容绝不覆盖。

旧格式 RunRecord 若只有 `execution_approved=true`、没有绑定 displayed `draft_hash` 的严格 approval event，只能作为历史 render/graph/history 证据；它连当次展示后审批都不能证明，更不能授权新执行。不得追溯补造事件或把旧记录升级为 production approval evidence。

### Stage 2：Flux 多视图交接

> The numbered Stage 2 notes below describe the original workflow evidence. For
> production execution, the promoted flat-v2 profile and its zero-warning MCP
> conversion described above are authoritative; the legacy fingerprint is not a
> fallback.

Stage 2 只接受已成功且 history 已核对的 Stage 1 RunRecord，以及独立接受的 `CharacterBaseImage` descriptor。descriptor 必须包含真实 PNG 的 lowercase SHA-256、与 RunRecord 相同的 `source_record_hash`、安全 `lineage_id`、canonical `artifact_root/artifact_path`，并明确 `visual_acceptance.front_facing=true` 与 `identity_visible=true`。路径必须实际位于 root 内，文件字节 hash、RunRecord output hash 与 descriptor hash 必须三者相等。`DiagnosticImage`、未接受 artifact、错误 type、空/伪 hash、lineage 不一致或未通过 front-facing acceptance 一律拒绝。

1. 枚举当前 MCP 注册表，使用实际存在的 saved-workflow load、UI→API、strip/slice、runtime classification 与 validate 能力处理 `Flux2-Klein人物一键多视图工作流.json`。生产 draft 只能由受控本地 orchestrator 调用 `build_multiview_draft_with_mcp`：它在进程内实际执行 `get_workflow({workflow_id, format:"ui"})`、`get_workflow({workflow_id, format:"api"})`、`strip_workflow({workflow_id})`、`validate_workflow({workflow: api_graph})` 与 `check_workflow_runtime({workflow: api_graph})`，再把真实响应摘要、comfyui-mcp 版本和本地 provenance 绑定进 draft。禁止猜工具名、禁止手写 UI converter，也禁止让 JSON caller 用自填 receipt/`trust_model` 代替这些调用。只有 runtime 明确为 local、validation 零 error、当前 UI fingerprint 精确为 `fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf`、profile/节点/模型/资源验证通过且队列为空，才能继续；转换 warning 导致断线或 required input 缺失时 fail closed。在这一步通过前不得上传。
2. `lineage_id` 必须匹配 ASCII `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`。随后以 `prompt-forge/<lineage_id>/character-base-<content_hash>.png` 这个 lineage+content-derived 名称，通过当前真实 `comfyui-mcp` image-upload 能力上传 Stage 1 PNG；MCP 返回的 stored filename 必须与请求名称完全相同，并须保留源 hash、上传 receipt 和服务器端可读确认。禁止覆盖已有不同内容。
3. 由同一个受控本地 orchestrator 调用 `build_multiview_draft_with_mcp` 构建 production draft。纯 JSON `runtime_cli.py plan-multiview` 没有 callable，必须 typed fail closed，不能把 caller-authored conversion receipt 变成可审批 draft；`validate_multiview_mcp_preflight` 若用于离线 receipt/回归 fixture，只是 audit，不产生 production draft，也不得进入 `approve-plan`。production draft 从 artifact hash 派生 uploaded filename，只允许 node `111` 与 `667` 的 `inputs.image` 变为同一文件，并让两个 patch 都携带同一 `source_hash`。pose `LoadImage` 节点 `368/151/152/154/360/364/148/149/147/373/150/367`、CR Text/view instructions、模型、LoRA、sampler、scheduler 和所有其他字段必须与 source API graph 完全相同；不得注入 negative prompt，draft 展示时明确写 `negative_prompt: absent`。此时只生成 draft，不 patch、更不提交。
4. 完整展示 Stage 2 draft 与 `draft_hash`，随后严格复用第 8–9 节的外部 approval event、`approve-plan`、canonical consumption root 与 `consume-approval`。不得为 Stage 2 恢复旧 `execution_approved=True` 输入或创建第二套授权。缺 `PROMPT_FORGE_APPROVAL_FILE` 时只 exclusive-create `pending-c-<draft_hash>.json`、报告 exact hash/path 并停止；绝不自动生成 approval、consume 或 enqueue。
5. consume 成功后，受控本地 orchestrator 才能以获批 plan 构造 executable graph 并调用实际 `enqueue_workflow` MCP；它必须先 exclusive-create 以 consumption id 绑定的 submission-intent sentinel（同时绑定 request id、submission hash、graph hash 和 exact args），随后才可调用。已有 in-progress/success/failed sentinel 时不得再次调用；callable 失败时保留 typed failed receipt，并先查询 server 状态而非删除或盲目重试。它必须把 sentinel 的 stable request id 放入 `prompt[3].extra_data.prompt_forge_enqueue_request_id`，保留 exact tool arguments、response digest、provenance 和 receipt。纯 JSON CLI 的 `patch-flux` 没有此可信 callable，必须 fail closed，绝不声称已提交。
6. terminal 后保留 raw history；history 内 prompt graph 必须 canonical-equal executable graph，且其请求 ID 必须从 `history[prompt_id]["prompt"][3]["extra_data"]["prompt_forge_enqueue_request_id"]`（兼容该 metadata dict 的直接字段）读取并等于 immutable consumption sentinel。Stage 1 accepted descriptor 必须恰好匹配一条 raw history `type=output`、subfolder、filename，并解析到相同 canonical artifact path。`record` 还必须消费 exact submission、enqueue receipt、sentinel 和 canonical ComfyUI output root；逐个重新读取 PNG、校验结构并计算 SHA-256。按 verified profile output map normalize image artifacts，全部绑定 Stage 1 `source_artifact_hash` 和 `lineage_id`，并标记 `hash_verified=true`；Stage 3 还必须有明确 `accepted=true`，并同时满足 `CharacterAngleView`、非冲突和 `reference_eligible=true`。未知 output 是 `DiagnosticImage`，默认不接受任何 Stage 2 artifact。相邻保留 approval、consumption、submission、enqueue receipt、raw history 和 artifact path/hash 证据。

Experiment C（Flux 多视图）一次只提交一个 job、不保存 workflow、不删除 history/output、不改 models/nodes。相机的 `normalize-camera` bridge 不适用于 Flux；Flux 的 MCP conversion、profile fingerprint、双输入一致性和资源验证必须独立通过。信任边界是本地受控 orchestrator 与其实际调用的 MCP：receipt 是可审计的本地观察，不是虚构的 MCP 加密签名；跨不可信进程/主机不得把 receipt/self-hash 当认证。REST live 只能标记为 characterization，不能替代 MCP production proof。默认 live 测试 skip；未完成 exact approval/consumption/receipt/history 链前，仍不得上传或 enqueue，也不得声称 Experiment C 已完成。

最终答复至少给出 prompt ID、seed、artifact 绝对路径、artifact hash、RunRecord 路径和 terminal status；没有这些证据时只报告已到达的阶段。

## CLI 退出合同

`runtime_cli.py` 的 `discover`、`fingerprint`、`plan`、`plan-multiview`、`approve-plan`、`consume-approval`、`patch-camera`、`normalize-camera`、`patch-flux`、`activate-g1`、`verify-img2img-path`、`record` 均接受 UTF-8 JSON 文件或 stdin，只把 JSON 写到 stdout。`normalize-camera` 只执行 pinned source bridge，不保存 workflow，也不 enqueue。`plan-multiview` 是明确的 JSON fail-closed 边界：没有受控本地 callable 时返回 exit `1` 与 typed rejection，不生成 draft；Stage 2 production planning 只能走本地授权 orchestrator 的 `build_multiview_draft_with_mcp`。`patch-flux` 同理不负责 production submit，受控提交只走 `submit_multiview`。`approve-plan`、`consume-approval` 和 `record` 还要求 caller `--run-dir`。stderr 只有单行 `[prompt-forge-runtime]` 诊断：`0` 成功，`1` draft 被运行时证据拒绝，`2` 输入、审批、重复消费或运行时失败。

## 常见错误

| 错误 | 正确处理 |
|---|---|
| 看到 MCP 文档中的名字就直接调用 | 先枚举当前真实工具并按能力协商 |
| 初始生成请求后直接 enqueue | 构造 draft，展示实际 prompt/negative/graph mutation/draft_hash，再取得外部新鲜事件 |
| 把 `execution_approved=true` 或旧 approval 当许可 | 只接受 `approve-plan` 对本次 exact displayed draft 产出的 approved plan |
| 把旧 boolean-only RunRecord 称为审批证明 | 仅称为历史 render/graph/history 证据；没有 display-bound event 就没有可审计审批 |
| 恢复时生成新 CapabilityReport 并重建 draft | 从 run-dir 的 immutable pending bundle 用 frozen inputs 重建 exact draft；fresh report 只做当前安全门 |
| `enqueue-once` 只是事件字符串 | POST 前 atomic `consume-approval`；任何已有 consumption 都拒绝 |
| POST 超时后删除 consumption 再试 | 保留消费记录，先按稳定 request/client id 查 history，绝不盲目重复 enqueue |
| 从 UI JSON 猜 API inputs | 让 MCP 完成转换、strip 和 validate |
| 只保存 prompt ID 或截图 | 保留 raw history、artifact hash 和 RunRecord |
| 失败后换 workflow/model 重试 | 停止并报告 hard gate，不静默替代 |
