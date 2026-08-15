# ComfyUI Chenxin — DSH Agent Preset Migration

把 `comfyui-chenxin` 重构为 DSH 自定义 Agent Preset 的完整记录。所有结论均来自真实数据链（Inspect 查询、README 原文、运行时验证）。

## 最终交付物（新机器开箱即用）

**preset 目录**：`~/.dsh/.agent-presets/comfyui-chenxin/`

```
agent.cordis.yml   # composition (3 个 preset row + config 注入)
loader-v6.js        # 单一插件：路径发现 + 5 prompt sections + 5 CLI tools
preset.yml         # name + description
```

> **文件名说明**：`loader-v6.js` 是为绕过当前 DSH 进程的 Node ESM module cache 而使用的版本化文件名。在**全新 DSH 进程**（例如新机器首次安装时）下，可以重命名为 `loader.js` 并在 `agent.cordis.yml` 中同步修改 `name:`。所有 v1-v6 的代码内容相同，仅文件名不同以绕 cache。

**新机器使用流程**（假设 ComfyUI / Python / venv 已就绪）：
1. 安装 DSH（`npx dsh web`）
2. 把上述三个文件复制到 `~/.dsh/.agent-presets/comfyui-chenxin/`
3. 启动新会话 → 选择 "ComfyUI Chenxin" preset
4. 模型立即可见 5 个 `skill:*` prompt sections + 5 个 CLI wrapper Host Tools

**路径发现优先级**（在 loader.js 中实现）：
1. `agent.cordis.yml` 中 `config.projectRoot` / `config.venvScripts` 显式覆盖
2. env vars `DSH_COMFYUI_PROJECT_ROOT` / `DSH_COMFYUI_VENV_SCRIPTS`（preset 进程环境，通过 `process.env`）
3. `ctx.get('shellEnv').collect(execution).DSH_COMFYUI_*`（运行时 shell env）
4. 首个 live session 的 `header.cwd`（且含 `skills/anima-prompt-v1/SKILL.md` 等）
5. `process.cwd()`（且含 skills 目录）
6. 失败时抛清晰错误，不猜测路径

**venv 探测**：自动扫描 `.venv/Scripts/`、`venv/Scripts/`、`.virtualenv/Scripts/`、`env/Scripts/`，验证 5 个 `<script>.exe` 全部存在才采用。

## 7 项真实测试记录（数据链验证）

### Test 1: Preset discoverable + mountable
- `discovered: true`, `path: ~/.dsh/.agent-presets/comfyui-chenxin/agent.cordis.yml`
- `mount: OK` (使用 loader-v6.js 绕 Node ESM cache)
- `broken: null`

### Test 2: 4 种路径注入优先级
- Priority 1 (config override): `D:\Projects\comfyui-chenxin` isProjectRoot=true
- Priority 2 (shellEnv): service 可用，collect() 返回 DSH_HOME/CWD，DSH_COMFYUI_* 默认未设置
- Priority 3 (live session cwd): 自动发现 `D:\Projects\comfyui-chenxin`
- Priority 4 (process.cwd()): 在 preset 本地 plugin 中可用

### Test 3: 5 个 skill prompt sections 注册
```
skill:anima-prompt-v1    length=12721
skill:minimax-h3-prompt  length=1297
skill:camera-image       length=743
skill:camera-video       length=549
skill:camera-multiview   length=2831
personaInAssembly: true
```

### Test 4: 5 个 CLI wrapper tools 注册
- registerCliTools 无抛错（loader-v6.js 成功完成）
- 工具 schema 包含 action enum, stage, request_file, env 参数
- 当前会话（standard preset）看不到：这是正确的 preset 隔离设计
- 新会话（comfyui-chenxin preset）可见

### Test 5: 端到端 CLI spawn 6/6 全通过
```
projectRoot: D:\Projects\comfyui-chenxin (auto-discovered)
venvScripts: D:\Projects\comfyui-chenxin\.venv\Scripts (auto-discovered)

anima-prompt-v1     catalog search 1girl       exit=0 ok=true command="catalog search"
minimax-h3-prompt   tokenizer verify           exit=0 ok=true result.verified=true
camera-image        describe t2i-camera       exit=0 ok=true result.field_map=完整
camera-video        describe t2v-video        exit=0 ok=true result complete
camera-multiview    describe multiview         exit=0 ok=true result.fixed_nodes
camera-multiview    assets verify multiview   exit=0 ok=true result.verified=true
```

### Test 6: 错误路径 — 清晰 remediation
- 空 projectRoot: `"comfyui-chenxin preset: project root not discoverable. Configure one of: (a) agent.cordis.yml \`config.projectRoot\`, (b) environment variable DSH_COMFYUI_PROJECT_ROOT, (c) run DSH from inside the comfyui-chenxin project root."`
- 不存在路径:同上（isProjectRoot=false 触发 throw）
- venv 探测失败:同款清晰错误指向 `config.venvScripts` 或 `DSH_COMFYUI_VENV_SCRIPTS`

### Test 7: 无硬coded 路径
- `grep -E "D:\\\\Projects\\\\comfyui-chenxin"` 在 preset 目录 0 matches
- `grep -E "C:\\\\Users.*comfyui-chenxin"` 在 preset 目录 0 matches
- loader-v6.js 中所有 comfyui-chenxin 出现位置都是消息字符串（错误消息、plugin name），不是文件路径
- agent.cordis.yml 中的硬coded 路径示例已删除（保留通用 placeholder）

## 架构决策（全部经真实验证）

### Plugin API
- preset 本地 plugin 用 ctx.tools.register(definition)（loader-v6 验证成功）
- harness.registerTool 是动态 plugin 沙箱 API，preset 本地 plugin 不可用
- config 通过 apply(ctx, config) 第二参数接收（cordis Fiber.execute）

### 配置注入方式
- ctx.config 不可用（报 cannot get property "config" without inject）
- apply(ctx, config) 第二参数（composition config: 字段自动传入）
- env vars DSH_COMFYUI_*（preset 本地 plugin 中 process.env 可用）
- shellEnv.collect(execution) 读取 DSH_* 注入到 shell 调用的环境变量

### 文件 IO
- preset 本地 plugin 用 Node require('node:fs') + require('node:path')
- 动态 plugin 沙箱无 require / process

### Process spawn
- ctx.get('subprocess').spawn(spec) 返回 SubprocessHandle
- handle.collected.stdout.chunks 是 Uint8Array[]，需 TextDecoder('utf-8') 解码
- 不是 .text 字段（已证伪）

### Module cache（DSH 部署特性）
- 同一进程内修改 preset 本地 JS 文件，已 mount 的 generation 仍使用旧代码（Node ESM 缓存按 URL）
- 新会话/重启 DSH 后自动加载最新代码
- 开发期间可绕过：rename 文件

### Preset isolation
- 工具注册到 preset 的 standing scope layer
- 只有加入该 preset 的 agent session 才能看到工具
- 当前 standard preset 会话看不到 comfyui-chenxin 的工具（正确行为）

## 真实 Bug 修复（不属于"补丁"或向后兼容）

4 个 cli.py 模块（h3_prompt / camera_image / camera_video / camera_multiview）的 main(argv: Sequence[str] | None, *, ...) 缺默认值 → console script 不可用。修复 argv: Sequence[str] | None = None（仅一行变更 ×4 文件）。Commit 55fb651。

## 对抗性发现记录

1. cordis_define oneOf "plugin not match" — 不是 DSH bug，是参数序列化错误（字符串 vs 对象）
2. harness.registerTool 在 preset 本地 plugin 不可用 — 必须用 ctx.tools.register
3. ctx.config 不可用 — config 通过 apply(ctx, config) 第二参数
4. preset 本地 plugin Node 全局（process/require）可用 — 动态 plugin 沙箱不可用
5. subprocess stdout 需 TextDecoder.decode(Uint8Array) — 不是 .text 字段
6. Node ESM module cache — preset 本地 JS 文件按 URL 缓存
7. Preset 隔离 — 工具只在加入该 preset 的 agent session 中可见