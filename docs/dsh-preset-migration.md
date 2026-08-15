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

## Phase B 详细实施计划（供新会话执行）

**前置条件**: cordis_define 工具可用。如不可用，先调查修复。

### Step 1: 查询 Inspect Provider

```
cordis_inspect_list
→ 确认 Host Service.listService 中有 systemPrompt
→ 确认 Host Builtin.listBuiltins 中有 harness
→ 确认 Host Tool.listTools 返回当前工具列表
```

### Step 2: 查询 systemPrompt.section 签名

```
cordis_inspect_query(platform:"host", provider:"Service", method:"listService", input:{service:"systemPrompt"})
→ 确认 section() 的参数类型 PromptSection = { name, order, text, complete? }
```

### Step 3: 查询 harness.defineTool 签名

```
cordis_inspect_query(platform:"host", provider:"Builtin", method:"listBuiltins")
→ 确认 harness.defineTool(definition: ToolDefinition): ToolDefinition
→ 确认 harness.registerTool(ctx, tool): () => void
```

### Step 4: 创建 comfyui-skills-loader Plugin

```js
// code.host 内容（纯 JavaScript，无 import/require）
return {
  name: 'comfyui-skills-loader',
  inject: ['systemPrompt'],
  apply(ctx) {
    // 项目根目录从环境变量或 cwd 获取
    const projectRoot = process.env.DSH_CWD || process.cwd()
    
    // Skill 定义
    const skills = [
      { name: 'anima-prompt-v1', file: 'skills/anima-prompt-v1/SKILL.md', order: 200 },
      { name: 'minimax-h3-prompt', file: 'skills/minimax-h3-prompt/SKILL.md', order: 201 },
      { name: 'camera-image', file: 'skills/camera-image/SKILL.md', order: 202 },
      { name: 'camera-video', file: 'skills/camera-video/SKILL.md', order: 203 },
      { name: 'camera-multiview', file: 'skills/camera-multiview/SKILL.md', order: 204 },
    ]
    
    // 注意：动态 plugin 中不能用 require('fs')
    // 需要通过 ctx.get('fs') 获取 filesystem service 来读取文件
    // 或者使用 harness.handle + Client RPC 方式
    // 具体实现需根据 Inspect 结果确定
    
    // TODO: 读取文件并注册 prompt sections
    // TODO: 注册 CLI wrapper tools
  }
}
```

**关键问题**: 动态 plugin 中如何读取本地文件？
- `require('fs')` 被禁止
- 需要查询 `ctx.get('fs')` 是否提供 readText 方法
- 或者通过 `harness.handle` 注册 Host RPC，由 Client 调用触发文件读取

### Step 5: 定义 Plugin

```
cordis_define(
  plugin: { kind: "new", idPrefix: "skil" },
  name: "comfyui-skills-loader",
  purpose: "Load SKILL.md as prompt sections and register CLI wrapper tools",
  code: { host: "<上述代码>" }
)
→ 记录返回的 pluginId 和 packageId
```

### Step 6: 激活 Plugin

```
cordis_run(pluginId, packageId, mode: "run")
→ 等待 starting → 成功/失败
→ 如失败，用 cordis_inspect_self 读诊断，修复后重新 define + run
```

### Step 7: 验证

1. 检查 Tool.listTools 是否包含新增的 CLI wrapper tools
2. 发送测试消息，确认模型能看到 SKILL.md 内容
3. 运行 `pytest tests/e2e/test_installed_cli.py` 确认原有测试不受影响

### Step 8: 更新 agent.cordis.yml（可选）

如果 skills-loader plugin 需要随 preset 自动加载，考虑：
- 将 plugin 定义为 preset 目录中的 JS 文件（相对路径引用）
- 或在 composition 中添加一行引用该 plugin

## CLI Wrapper Tools 设计

每个 console script 对应一个 Tool：

| Tool Name | CLI Command | Input Schema | Output |
|---|---|---|---|
| `anima_prompt_v1_author` | `anima-prompt-v1 author --request <file> --json` | `{ request_file: string }` | P1 Envelope |
| `anima_prompt_v1_catalog_search` | `anima-prompt-v1 catalog search <query> --json` | `{ query: string }` | P1 Envelope |
| `minimax_h3_prompt_author` | `minimax-h3-prompt author --stage <s> --request <f> --json` | `{ stage, request_file }` | P1 Envelope |
| `camera_image_run` | `camera-image run --stage <s> --envelope <e> --config <c> --output-dir <d> --json` | `{ stage, envelope, config, output_dir }` | P1 Envelope |
| `camera_video_run` | `camera-video run --stage <s> --envelope <e> --config <c> --output-dir <d> --json` | `{ stage, envelope, config, output_dir }` | P1 Envelope |
| `camera_multiview_run` | `camera-multiview run --stage <s> --envelope <e> --config <c> --output-dir <d> --json` | `{ stage, envelope, config, output_dir }` | P1 Envelope |

所有 Tool 通过 `pwsh` 调用 CLI，解析 stdout JSON，返回结构化结果。退出码映射：
- 0 → ok: true
- 2 → validation error
- 3 → runtime error  
- 4 → network error
- 5 → config error
- 70 → internal error

## 已知限制

- Preset 文件在项目仓库外 (`~/.dsh/`)，不随 git 版本控制
- SKILL.md 内容变更需手动同步到 persona text（Phase A fallback）
- CLI wrapper tools 尚未实现，当前需手动调用 pwsh
- cordis_define 在某些会话中可能不可用（原因待查）
