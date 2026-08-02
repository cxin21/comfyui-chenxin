---
name: prompt-forge
description: Use when compiling prompts for image or video models, or when an explicitly approved local ComfyUI generation needs an auditable PromptBuild, ExecutionPlan, artifact, and RunRecord.
---

# Prompt Forge

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

REST 只可作为 health、queue、object info、saved workflow 和 history 的只读回退。能力缺失时说明缺口和安全替代方案，不虚构工具，不自行实现通用 UI→API 转换器。

### 4. MCP load / strip / validate

由已协商到的 MCP 能力加载用户指定的保存工作流，并负责 UI→API 转换、strip/slice、runtime classification 与 executable validation。禁止让 Python runtime 猜 widget-to-input 映射。转换结果必须保留为未修改的 source API graph；saved workflow 保持不变。

### 5. Fingerprint

对实际 UI workflow 运行 `runtime_cli.py fingerprint`。指纹必须与已批准 WorkflowProfile 匹配，语义 slot 必须唯一解析。漂移、歧义或无法证明指定 workflow 与 API graph 的对应关系时 fail closed。

### 6. ExecutionPlan

将 PromptBuild、当前 CapabilityReport、profile、实际 UI workflow、source API graph 和 allowlisted patches 送入 `runtime_cli.py plan`。计划必须 local-only、队列为空、`execution_approved=true`，且只改变 profile 暴露的 slot。这里的字段只表示当前显式生成请求允许构造 production plan；它本身不是 enqueue 许可。模型、LoRA、sampler、scheduler 和图结构默认不可变。

### 7. 展示 prompt 与 plan

enqueue 前向用户展示最终 positive/negative prompt、workflow/profile、所有 patches、immutable inputs、预期输出、主要风险和单变量实验。初始“生成”请求允许准备计划，但不能替代看到实际 prompt/plan 后的审批。

### 8. 明确审批

只有用户对本次展示的 prompt 和 ExecutionPlan 给出明确肯定后，才把 `execution_approved` 视为有效。内容变更、能力报告过期、workflow/profile 漂移或队列状态变化都使审批失效，必须重新 preflight 并展示。

### 9. Enqueue

审批有效且队列仍为空时，使用实际协商到的 MCP enqueue/monitor 能力提交 executable API graph。一次只提交一个 job，等待 terminal success/failure 后才开始下一实验。不要调用保存工作流、安装、删除或清理接口。

### 10. Artifact verification

从 raw ComfyUI history 取得 prompt ID、真实 executable graph、terminal status 和 output descriptors；不得用摘要代替 raw history。raw-history graph 必须与获批并提交的 executable graph canonical-equal，否则拒绝 RunRecord。逐个验证新 output artifact 存在、可解码，且绝对路径位于已确认的 ComfyUI output 根目录内，并计算 SHA-256。只有 terminal success 与 artifact 均验证后才能声称生成成功。

### 11. RunRecord

使用 `runtime_cli.py record --run-dir <dir>` 消费 raw history，生成并保留 append-only RunRecord。Record 保存 TaskContext/PromptBuild hashes、完整 PromptBuild、ExecutionPlan、source/executable graph hashes、已核对的 history status/output descriptors、prompt ID 与 artifact hashes；审批事件、被审批 plan hash、raw history 及其 hash、artifact 绝对路径作为相邻执行证据保留。文件名为 `<record_hash>.json`：同内容重复写入幂等，不同内容绝不覆盖。

最终答复至少给出 prompt ID、seed、artifact 绝对路径、artifact hash、RunRecord 路径和 terminal status；没有这些证据时只报告已到达的阶段。

## CLI 退出合同

`runtime_cli.py` 的 `discover`、`fingerprint`、`plan`、`patch-camera`、`record` 均接受 UTF-8 JSON 文件或 stdin，只把 JSON 写到 stdout。stderr 只有单行 `[prompt-forge-runtime]` 诊断：`0` 成功，`1` 计划被拒，`2` 输入或运行时失败。

## 常见错误

| 错误 | 正确处理 |
|---|---|
| 看到 MCP 文档中的名字就直接调用 | 先枚举当前真实工具并按能力协商 |
| 初始生成请求后直接 enqueue | 展示实际 prompt/plan，再取得明确审批 |
| 从 UI JSON 猜 API inputs | 让 MCP 完成转换、strip 和 validate |
| 只保存 prompt ID 或截图 | 保留 raw history、artifact hash 和 RunRecord |
| 失败后换 workflow/model 重试 | 停止并报告 hard gate，不静默替代 |
