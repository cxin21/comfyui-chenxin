# DSH Agent Preset Migration Guide

本文档记录将 comfyui-chenxin 重构为 DSH 自定义 Agent Preset 的过程、架构决策和验证状态。
所有结论均来自真实数据链（Inspect 查询、README 原文、运行时验证），无猜测。

## 当前状态：Phase B 完成（skills-loader 已实现并验证）

**Preset 位置**: `~/.dsh/.agent-presets/comfyui-chenxin/`

**已实现**:
- ✅ Preset 目录结构符合规范 (`[a-z0-9][a-z0-9-]*`)
- ✅ `preset.yml` 包含 name 和 description
- ✅ `agent.cordis.yml` 包含 persona + 基础工具 (pwsh/fs/fs-search)
- ✅ `skills-loader.js`（preset 本地插件）读取 5 个 SKILL.md 注册为 prompt sections
- ✅ standingKeyFor mount 验证通过（`mounted OK`）
- ✅ 会话内完整数据链验证：5 个 `skill:*` sections 全部注册成功

**未实现 (Phase C)**:
- ⏳ CLI wrapper tools（调用 5 个 console script 的 Host Tools）

## 架构决策（全部经真实验证）

### 1. 为什么不用 `@deepseek-ai/dsh-prompt-section-file`？

**该包不存在**。通过枚举 `@deepseek-ai/dsh-*` 包列表确认。

### 2. Prompt sections 如何加载？

**最终方案：preset 本地 JS 模块**（`name: './skills-loader.js'`）。

验证链：
- `dsh-agent-presets` README L67: "A **relative** path still resolves from the preset's own directory"
- Cordis loader `import()`: 相对路径 specifier 直接 `super.import(name)` 解析
- `Registry.resolve()` (cordis/lib/index.js L1532): 支持函数或 `{ apply }` 对象两种插件形态
- **坑**：早期用 `module.exports = function () { return { name, apply } }`（工厂函数）失败——Cordis 会把函数本身当作 `apply(ctx)` 调用，返回值被丢弃。**必须导出对象** `module.exports = { name, apply }`

### 3. 为什么用 ctx.get('fs') 而非 require('fs')？

**动态 plugin 沙箱验证**：`process is not defined`、无 `require`、无 `process.env`。
`ctx.get('fs')` → `resolve(path)` → `readText(target)` 是唯一可移植的读取路径。

### 4. 项目根目录如何确定？

**验证结果**：
- `process.env.DSH_CWD` 在 shell 中为**空**
- `exec.agent.session.header.cwd` = `D:\Projects\comfyui-chenxin`（Tool execute 内可用）
- 但 **plugin apply() 的 ctx 是沙箱 ctx，不暴露 `agent`**
- **最终方案**：`ctx.get('sessions').list()` 遍历取第一个 `header.cwd`

### 5. 为什么 tool-pwsh / tool-fs / tool-fs-search 不需要 realm？

它们只消费 host 提供的 services（shell/fs/policy），不发布新 service。standard preset 同款注释确认。

### 6. 为什么 sampleOverCapGlobResults 是 required？

`dsh-tool-fs-search` README L23: "`sampleOverCapGlobResults` is required and has no fallback"。设为 `false`。

### 7. cordis_define oneOf 报错根因

**不是 DSH bug，是参数序列化错误**：
- 错误：`"plugin": "{\"kind\": \"new\", \"idPrefix\": \"pval\"}"`（JSON 字符串）
- 正确：`plugin: {"kind": "new", "idPrefix": "pval"}`（对象）
- schema 两个 oneOf 分支都要求 `type: "object"`，字符串不匹配任何分支 → `matched 0`
- **修复后 cordis_define 正常可用**

### 8. standingKeyFor 与模块缓存

**关键发现**：`standingKeyFor` 在同一进程内**复用 standing mount**（`ensureStanding` 比较 composition 文件 stamp：mtimeMs + size）。stamp 变化会创建新 generation，但**旧 generation 不 dispose**，且 **Node 模块缓存**导致同路径模块文件变更后，进程内 mount 仍加载旧代码。

**含义**：进程内验证新 sections 不可靠（看到的是旧 mount）。**新会话/重启后 preset 加载最新代码**。会话内动态 plugin 复现验证是可靠替代。

## 验证记录（真实数据链）

### 会话内完整链路验证（skills-chain-verify plugin）

```
cwd=D:\Projects\comfyui-chenxin
OK anima-prompt-v1:12721
OK minimax-h3-prompt:1297
OK camera-image:743
OK camera-video:549
OK camera-multiview:2831
```

### 注册后的 systemPrompt assembly（当前会话）

```
skill:anima-prompt-v1      len=12721
skill:minimax-h3-prompt    len=1297
skill:camera-image         len=743
skill:camera-video         len=549
skill:camera-multiview     len=2831
```

### 最终 mount 验证

```
mount: OK
key: {"agentPreset":"comfyui-chenxin"}
discovered: true
broken: null
```

## Phase C 计划：CLI wrapper tools

目标：5 个 console script → 结构化 Host Tools。

### 数据链（已验证）

| 命令 | 状态 |
|---|---|
| `python -m anima_prompt_v1.cli author --help` | ✅ 可用 |
| `python -m anima_prompt_v1.cli catalog search --help` | ✅ 可用 |
| `python -m h3_prompt.cli author --help` | ✅ 可用 |
| `python -m camera_image.cli run --help` | ❌ 缺 comfyui_http 依赖 |
| `python -m camera_video.cli run --help` | ❌ 缺 comfyui_http 依赖 |
| `python -m camera_multiview.cli run --help` | ❌ 缺 comfyui_http 依赖 |

### 实现方式

在 skills-loader.js 中追加 `harness.registerTool`，或新建独立 preset 本地模块：
- Tool execute 内通过 `ctx.get('subprocess').spawn()` 调用 `python -m <module> <args>`
- 解析 stdout 的 P1 JSON Envelope 返回结构化结果
- 退出码映射：0→ok / 2→validation / 3→runtime / 4→network / 5→config / 70→internal

### 前置条件

- camera-* 依赖 `comfyui_http`，需 `pip install -e runtime/comfyui_http`（见 README 安装章节）
- CLI 调用需在项目 venv 中执行（`D:\Projects\comfyui-chenxin\.venv`）

## 已知限制

- Preset 文件在项目仓库外 (`~/.dsh/`)，不随 git 版本控制（用户级配置）
- 进程内 standingKeyFor 复用 mount，新 sections 需新会话验证
- CLI wrapper tools 尚未实现（Phase C）
