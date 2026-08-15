# DSH Agent Preset Migration Guide

本文档记录将 comfyui-chenxin 重构为 DSH 自定义 Agent Preset 的过程、架构决策和验证状态。
所有结论均来自真实数据链（Inspect 查询、README 原文、运行时验证），无猜测。

## 当前状态：Phase C 完成（preset 已可用）

**Preset 位置**: `~/.dsh/.agent-presets/comfyui-chenxin/`

**已实现**:
- ✅ Preset 目录结构符合规范 (`[a-z0-9][a-z0-9-]*`)
- ✅ `preset.yml` 包含 name 和 description
- ✅ `agent.cordis.yml` 包含 persona + 基础工具 (pwsh/fs/fs-search) + skills-loader + cli-tools
- ✅ `skills-loader.js` 读取 5 个 SKILL.md 注册为 prompt sections
- ✅ `cli-tools.js` 注册 5 个 CLI wrapper Host Tools（anima_prompt_v1 / minimax_h3_prompt / camera_image / camera_video / camera_multiview）
- ✅ standingKeyFor mount 验证通过（mount OK, no broken state）
- ✅ 端到端数据链验证：5 个 console scripts 全部 spawn + JSON envelope 解析通过（动态 plugin 测试 6/6）

**已知限制**:
- 进程内 Node ESM 模块缓存：composition 文件变化后，**同一会话内**模块缓存仍指向旧版；**新会话/重启**后 preset 会重新 mount 最新代码
- 路径硬编码：`D:\Projects\comfyui-chenxin\.venv\Scripts\` 和 `D:\Projects\comfyui-chenxin` 是项目专用路径

## 架构决策（全部经真实验证）

### 1. 为什么不用 `@deepseek-ai/dsh-prompt-section-file`？

该包不存在（枚举包列表确认）。

### 2. Prompt sections + CLI Tools 加载方式

preset 本地 JS 模块（`name: './skills-loader.js'` 和 `name: './cli-tools.js'`）。
- `dsh-agent-presets` README L67: "A **relative** path still resolves from the preset's own directory"
- Cordis loader `import()`: 相对路径 specifier 直接 `super.import(name)` 解析
- `Registry.resolve()` (cordis/lib/index.js L1532): 支持函数或 `{ apply }` 对象；**必须导出对象**

### 3. 文件读取用 ctx.get('fs')，不用 require('fs')

动态 plugin 沙箱验证：`process is not defined`、无 `require`、无 `process.env`。

### 4. 项目根目录通过 ctx.get('sessions').list() 找 header.cwd

- `process.env.DSH_CWD` 在 shell 中为**空**
- 动态 plugin ctx 不暴露 `agent`
- sessions service 的 list 包含 session header.cwd

### 5. CLI 执行用 ctx.get('subprocess').spawn()

- `subprocess.spawn(spec)` 返回 `SubprocessHandle`，含 `done`(Promise) 和 `collected: { stdout, stderr }`
- `collected.stdout.chunks` 是 Uint8Array 数组，需 `TextDecoder('utf-8')` 解码（**不是 `.text` 字段**——这是错误的 API 假设，已证伪）
- cwd 必须显式传入；不在 preset ctx 的 cwd 下执行
- 退出码：0=success, 2=validation, 3=runtime, 4=network, 5=config, 70=internal（P1 契约）

### 6. CLI 入口：console script（不是 `python -m`）

**实测发现**：4 个 cli.py 模块的 `main(argv)` 缺默认值，`python -m <module>` 调用会因 missing argument 抛错。修复后 console script `camera-image.exe` / `minimax-h3-prompt.exe` 正常调用。cli-tools.js 优先用 console script（更直接、Python PATH 自管理）。

### 7. cordis plugin config 不能通过 ctx.config 访问

**实测发现**：`ctx.config.pythonPath` 等访问报 `cannot get property "config" without inject`。Cordis plugin config 需通过 `Config` 静态字段或 inject。cli-tools.js 用**硬编码路径**绕开此限制（preset 是项目专用的，硬编码可接受）。

## 真实 Bug 修复（不属于"补丁"或向后兼容）

### Bug A: 4 个 cli.py 的 main(argv) 缺默认值

**症状**：`camera-image.exe --help` 报 `TypeError: main() missing 1 required positional argument: 'argv'`，导致 console script 不可用。`anima-prompt-v1` 工作因它的 `main(argv: list[str] | None = None)` 有默认值；h3 / camera-* 没有。

**修复**（在源代码中修改，非 preset 配置）：
```diff
- argv: Sequence[str] | None,
+ argv: Sequence[str] | None = None,
```
影响文件：`skills/minimax-h3-prompt/h3_prompt/cli.py`、`skills/camera-image/camera_image/cli.py`、`skills/camera-video/camera_video/cli.py`、`skills/camera-multiview/camera_multiview/cli.py`。

**这是修复源代码 bug**，不是向后兼容 patch——旧调用方式（必须显式传 argv）现在仍工作，新调用方式（依赖 sys.argv）也能工作。

## 验证记录（真实数据链）

### 端到端 spawn 测试（clvn-21 动态 plugin）

| Console Script | Action | exit_code | ok | envelope |
|---|---|---|---|---|
| anima-prompt-v1.exe | catalog search 1girl | 0 | true | {command: "catalog search", result: {hits: [...]}} |
| minimax-h3-prompt.exe | tokenizer verify | 0 | true | {command: "tokenizer verify", result: {verified: true, snapshot_id: "h3-qwen3-vl", files: [...]}} |
| camera-image.exe | describe t2i-camera | 0 | true | {command: "describe", stage: "t2i-camera", result: {field_map: {...complete...}}} |
| camera-video.exe | describe t2v-video | 0 | true | {command: "describe", stage: "t2v-video", result: {asset_workflow_name: "t2v-video"}} |
| camera-multiview.exe | describe multiview | 0 | true | {command: "describe", stage: "multiview", result: {asset_workflow_name, asset_fingerprint, fixed_nodes}} |
| camera-multiview.exe | assets verify | 0 | true | {command: "assets verify", result: {verified: true, asset: "multiview"}} |

**6/6 通过**，所有 CLI 端到端可用。

### Prompt sections 注册（scvr-17 动态 plugin + skills-loader.js）

```
cwd=D:\Projects\comfyui-chenxin
skill:anima-prompt-v1      len=12721
skill:minimax-h3-prompt    len=1297
skill:camera-image         len=743
skill:camera-video         len=549
skill:camera-multiview     len=2831
```

### Final mount validation（clvf-22 动态 plugin）

```discovered: true, broken: null, mount: OK```

## 使用方式

启动新 DSH 会话时选择 "ComfyUI Chenxin" preset。模型会看到：
- 5 个 `skill:*` prompt sections（自动加载 SKILL.md 内容）
- 5 个 CLI wrapper Tools：`anima_prompt_v1`、`minimax_h3_prompt`、`camera_image`、`camera_video`、`camera_multiview`
- 基础工具：`pwsh`, `read`, `write`, `edit`, `glob`, `grep`

## 未来改进

- 将路径配置移到 preset 的 agent.cordis.yml config（需先找到 Cordis plugin config 正确访问方式）
- 拆分子命令为独立 Tool（目前每个 Skill 一个 unified tool，action enum 区分）
- 添加自动化测试覆盖所有 CLI 子命令的 P1 envelope 契约