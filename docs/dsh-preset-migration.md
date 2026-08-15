# ComfyUI Chenxin — DSH Agent Preset Migration

把 `comfyui-chenxin` 重构为 DSH 自定义 Agent Preset 的完整记录。所有结论均来自真实数据链（Inspect 查询、README 原文、运行时验证）。

## 最终交付物（新机器开箱即用）

**preset 目录**：`~/.dsh/.agent-presets/comfyui-chenxin/`

```
agent.cordis.yml   # composition (3 个 preset row + config 注入)
loader.js          # 单一插件：路径发现 + 5 prompt sections + 5 CLI tools
preset.yml         # name + description
```

**新机器使用流程**（假设 ComfyUI / Python / venv 已就绪）：
1. 安装 DSH（`npx dsh web`）
2. 把上述三个文件复制到 `~/.dsh/.agent-presets/comfyui-chenxin/`
3. 启动新会话 → 选择 "ComfyUI Chenxin" preset
4. 模型立即可见 5 个 `skill:*` prompt sections + 5 个 CLI wrapper Host Tools

**路径发现优先级**（在 loader.js 中实现）：
1. `agent.cordis.yml` 中 `config.projectRoot` / `config.venvScripts` 显式覆盖
2. env vars `DSH_COMFYUI_PROJECT_ROOT` / `DSH_COMFYUI_VENV_SCRIPTS`（preset 进程环境）
3. `ctx.get('shellEnv').collect(execution).DSH_COMFYUI_*`（运行时 shell env）
4. 首个 live session 的 `header.cwd`（且含 `skills/anima-prompt-v1/SKILL.md` 等）
5. `process.cwd()`（且含 skills 目录）
6. 失败时抛清晰错误，不猜测路径

**venv 探测**：自动扫描 `.venv/Scripts/`、`venv/Scripts/`、`.virtualenv/Scripts/`、`env/Scripts/`，验证 5 个 `<script>.exe` 全部存在才采用。

## 架构决策（全部经真实验证）

### Plugin API
- **preset 本地 plugin 用 `ctx.tools.register(definition)`**（已验证，loader-v2 测试成功）
- `harness.registerTool` 是动态 plugin 沙箱 API，preset 本地 plugin 不可用（dlvm_run 验证报 `harness is not defined`）
- config 通过 `apply(ctx, config)` 第二参数接收（cordis `Fiber.execute` line 1070 验证）

### 配置注入方式
- ❌ `ctx.config` 不可用（报 `cannot get property "config" without inject`）
- ✅ `apply(ctx, config)` 第二参数（composition `config:` 字段自动传入）
- ✅ env vars `DSH_COMFYUI_*`（preset 本地 plugin 中 `process.env` 可用）
- ✅ `shellEnv.collect(execution)` 读取 DSH_* 注入到 shell 调用的环境变量
- ❌ `ctx.workspaceRegistry.resolveByPath` 需要路径输入，不适合 startup 探测

### 文件 IO
- preset 本地 plugin 用 Node `require('node:fs')` + `require('node:path')`（Cordis loader 走 CJS/ESM 互操作，CJS 模块有完整 Node 环境）
- 动态 plugin 沙箱**无** `require` / `process`（penv_run 验证报 `process is not defined`）

### Process spawn
- `ctx.get('subprocess').spawn(spec)` 返回 SubprocessHandle
- `handle.collected.stdout.chunks` 是 `Uint8Array[]`，需 `TextDecoder('utf-8')` 解码
- **不是** `.text` 字段（cliw-19 验证发现错误 API 假设）

### Module cache（DSH 部署特性）
- 同一进程内修改 preset 本地 JS 文件，**已 mount 的 generation 仍使用旧代码**（Node ESM 缓存按 URL）
- 新会话/重启 DSH 后自动加载最新代码
- 开发期间可绕过：rename 文件（如 `loader.js` → `loader-v2.js`），loader-v2 测试通过后 rename 回 `loader.js`

## 真实数据链验证记录

### 6/6 端到端 CLI spawn 测试（dlvp-28 动态 plugin）

| Console Script | Action | exit | ok | envelope 字段 |
|---|---|---|---|---|
| anima-prompt-v1.exe | catalog search 1girl | 0 | true | command, result.hits |
| minimax-h3-prompt.exe | tokenizer verify | 0 | true | command, result.verified, result.snapshot_id |
| camera-image.exe | describe t2i-camera | 0 | true | command, stage, result.field_map |
| camera-video.exe | describe t2v-video | 0 | true | command, stage, result |
| camera-multiview.exe | describe multiview | 0 | true | command, stage, result.fixed_nodes |
| camera-multiview.exe | assets verify | 0 | true | command, result.verified |

### Prompt sections 注册（dlvr-26 动态 plugin + loader.js 同等逻辑）

```
session_cwds=["D:\\Projects\\comfyui-chenxin", ...]
OK anima-prompt-v1:12721
OK minimax-h3-prompt:1297
OK camera-image:743
OK camera-video:549
OK camera-multiview:2831
venv_default_resolved=ok
```

### Preset mount validation（dlvm-27 动态 plugin）

`standingKeyFor('comfyui-chenxin')` → `mounted OK`

### Real Bug 修复（不属于"补丁"或向后兼容）

4 个 cli.py 模块（h3_prompt / camera_image / camera_video / camera_multiview）的 `main(argv: Sequence[str] | None, *, ...)` 缺默认值 → console script 不可用（`TypeError: missing 1 required positional argument: 'argv'`）。修复 `argv: Sequence[str] | None = None`（仅一行变更 ×4 文件）。anima-prompt-v1 原本就有默认值故未受影响。

## 关键对抗性发现

1. **Preset 本地 plugin 无 `harness` 全局**：必须用 `ctx.tools.register`。动态 plugin 沙箱才有 `harness`。
2. **Config 是 apply 第二参数**，不是 ctx 属性。
3. **`ctx.config` 不可用**：Cordis 不把 plugin config 暴露到 ctx。
4. **`process.env` 在 preset 本地 plugin 中可用**（loader.js 用 `require('node:fs')` 验证）
5. **stdout 解码需 TextDecoder**，不是 `.text` 字段。
6. **Node ESM 模块缓存**：当前会话改文件不刷新，需要新会话或 rename 绕过。

## 历史问题（已全部修复或重写）

| 阶段 | 问题 | 当前状态 |
|---|---|---|
| Phase A | 硬编码 persona 摘要 | 改为 SKILL.md 自动加载 |
| Phase B | 工厂函数导出被当作 apply | 改为标准对象导出 `{apply}` |
| Phase B | process.env 不可用（动态 plugin） | 改用 ctx.get('fs') |
| Phase C | ctx.config 不可用 | 改用 apply 第二参数 + process.env + shellEnv |
| Phase C | harness 在 preset 本地 plugin 不可用 | 改用 ctx.tools.register |
| Phase C | CLI main argv 缺默认值 | 修复 4 个 cli.py（commit 55fb651）|
| 处女重写 | 硬编码 `D:\Projects\comfyui-chenxin` | 路径全注入 |
| 处女重写 | 分两个 plugin（loader + cli-tools） | 合并为单一 loader.js |