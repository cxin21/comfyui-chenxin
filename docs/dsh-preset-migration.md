# DSH Agent Preset Migration Guide

本文档记录将 comfyui-chenxin 重构为 DSH 自定义 Agent Preset 的过程、架构决策和验证状态。

## 当前状态：Phase A (Minimal Viable)

**Preset 位置**: `~/.dsh/.agent-presets/comfyui-chenxin/`

**已实现**:
- ✅ Preset 目录结构符合规范 (`[a-z0-9][a-z0-9-]*`)
- ✅ `preset.yml` 包含 name 和 description
- ✅ `agent.cordis.yml` 包含 persona + 基础工具 (pwsh/fs/fs-search)
- ✅ 所有包名已验证存在于 `@deepseek-ai/dsh-*`
- ✅ `sampleOverCapGlobResults` required 字段已提供

**未实现 (Phase B)**:
- ⏳ SKILL.md 内容作为 prompt sections 自动加载
- ⏳ CLI wrapper tools 注册
- ⏳ standingKeyFor mount 验证（cordis_define 工具在当前会话不可用）

## 架构决策

### 为什么不用 `@deepseek-ai/dsh-prompt-section-file`？

**该包不存在**。通过枚举 `@deepseek-ai/dsh-*` 包列表确认。DSH 没有内置的"从文件加载 prompt section"的包。

替代方案：
1. **动态 Cordis Plugin**: 通过 `cordis_define` 创建 Host Plugin，在 `apply()` 中读取文件并调用 `ctx.systemPrompt.section()` 注册。这是推荐方式，但需要 cordis_define 可用。
2. **嵌入 persona text**: 将 SKILL.md 摘要直接写入 persona 的 text 字段。当前 Phase A 采用此方案作为 fallback。
3. **相对路径 JS 模块**: 在 preset 目录放置 JS 文件，composition 中用 `name: './loader.js'` 引用。无 shipped preset 先例，风险未知。

### 为什么 tool-pwsh 不需要 realm？

根据 standard preset 注释，`shell-env` 和 `ctx.shell` executor 都在 HOST composition 中。`tool-pwsh` 只消费这些 service，不发布新 service，因此不需要 isolate realm。

### 为什么 sampleOverCapGlobResults 是 required？

`dsh-tool-fs-search` README 明确说明该字段无默认值，部署必须显式选择 over-cap 排序契约。设为 `false` 保留 modification-time-ordered head。

## 验证方法

### Mount 验证（金标准）

```js
// 需要通过动态 plugin inject agentPresets 调用
await ctx.agentPresets.standingKeyFor('comfyui-chenxin')
// 返回 ScopeKey 表示成功；抛出异常表示失败
```

### 手动验证

1. 启动新 DSH 会话
2. 在 preset 选择器中选择 "ComfyUI Chenxin"
3. 检查工具列表是否包含 pwsh/read/write/glob/grep
4. 发送消息触发 persona 响应

## Phase B 计划

1. 创建动态 Cordis Plugin `comfyui-skills-loader`:
   - 读取 5 个 SKILL.md 文件
   - 注册为 prompt sections (order 200-204)
   - 注册 5 个 CLI wrapper tools
2. 通过 `cordis_run` 激活 plugin
3. 验证 skills 可被模型正确引用
4. 运行原有 pytest e2e 测试确认兼容性

## 已知限制

- Preset 文件在项目仓库外 (`~/.dsh/`)，不随 git 版本控制
- SKILL.md 内容变更需手动同步到 persona text（Phase A）
- CLI wrapper tools 尚未实现，当前需手动调用 pwsh
