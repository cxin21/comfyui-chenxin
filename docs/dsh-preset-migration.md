# ComfyUI Chenxin — DSH Agent Preset Migration

把 `comfyui-chenxin` 重构为 DSH 自定义 Agent Preset 的完整记录。所有结论均来自真实数据链。

## 最终交付物（新机器开箱即用）

**preset 目录**：`~/.dsh/.agent-presets/comfyui-chenxin/`

```
comfyui-chenxin/                   258 files, 1.85 GB
├── agent.cordis.yml               composition: persona + tools + loader
├── preset.yml                     name + description
├── loader-v7.js                   single plugin: SKILL.md sections + CLI tools
├── scripts/
│   ├── setup.ps1                  one-time setup (Windows)
│   ├── setup.sh                   one-time setup (POSIX)
│   └── (anima scripts/ copied for completeness)
├── runtime/
│   └── comfyui_http/              shared ComfyUI HTTP transport
│       ├── pyproject.toml
│       └── comfyui_http/          (Python source)
└── skills/                        5 skills, complete resources
    ├── anima-prompt-v1/
    │   ├── SKILL.md               ← registered as prompt section
    │   ├── references/*.md        5 detailed references
    │   ├── knowledge/
    │   │   ├── manifest.json      catalog build metadata
    │   │   ├── tag-catalog.sqlite 1.64 GB runtime catalog (used by catalog search)
    │   │   └── tags.sqlite        204 MB source snapshot
    │   ├── agents/openai.yaml
    │   ├── scripts/               catalog build/verify scripts
    │   ├── pyproject.toml         declares anima-prompt-v1 console script
    │   └── anima_prompt_v1/       (Python source: cli.py, authoring/, catalog/, inspection/)
    ├── minimax-h3-prompt/
    │   ├── SKILL.md               ← registered as prompt section
    │   ├── references/*.md        2 references (dialect.md, budget-policy.json)
    │   ├── knowledge/             tokenizer.json, manifest.json, LICENSE, NOTICE
    │   ├── agents/openai.yaml
    │   ├── pyproject.toml         declares minimax-h3-prompt console script
    │   └── h3_prompt/             (Python source)
    ├── camera-image/
    │   ├── SKILL.md               ← registered as prompt section
    │   ├── workflow/              bundled ComfyUI workflow assets
    │   │   ├── t2i-camera/groups.json
    │   │   └── i2i-camera/groups.json
    │   ├── pyproject.toml         declares camera-image console script
    │   └── camera_image/          (Python source: cli.py, runtime/*, workflow_assets/)
    ├── camera-video/
    │   ├── SKILL.md
    │   ├── workflow/              bundled h3 video workflows
    │   │   ├── minimax-h3-t2v.json
    │   │   ├── minimax-h3-i2v-single.json
    │   │   └── minimax-h3-i2v-multi.json
    │   ├── pyproject.toml
    │   └── camera_video/
    └── camera-multiview/
        ├── SKILL.md
        ├── workflow/
        │   └── Flux2-Klein人物一键多视图工作流.json
        ├── pyproject.toml
        └── camera_multiview/
```

**新机器使用流程**：
1. 复制上述目录到 `~/.dsh/.agent-presets/comfyui-chenxin/`
2. **5 个 SKILL.md 立即作为 prompt sections 加载**（无需任何设置）
3. 如需 CLI tools，运行一次 `scripts/setup.ps1`（Windows）或 `scripts/setup.sh`（POSIX）创建 venv + 安装 6 个包（comfyui-http-runtime + 5 个 skill）
4. 启动 DSH → 新会话 → 选择 "ComfyUI Chenxin" preset → 立即可用

**preset 完全自包含**——0 外部项目依赖。ComfyUI server 连接仍是用户提供的（camera-* 的 run 子命令需要外部 ComfyUI）。

## 架构决策（全部经真实验证）

### Plugin API
- preset 本地 plugin 用 `ctx.tools.register(definition)`（loader-v7 测试成功）
- `harness.registerTool` 是动态 plugin 沙箱 API，preset 本地 plugin 不可用
- config 通过 `apply(ctx, config)` 第二参数接收（cordis `Fiber.execute`）

### 配置注入方式
- `ctx.config` 不可用（报 `cannot get property "config" without inject`）
- `apply(ctx, config)` 第二参数（composition `config:` 字段自动传入）
- env vars `DSH_COMFYUI_PRESET_ROOT`（preset 进程环境，通过 `process.env`）
- `shellEnv.collect(execution).DSH_COMFYUI_PRESET_ROOT`
- **`__dirname` fallback**（**关键**：CJS Node 模块的 `__dirname` 是 loader.js 自身目录，恒等于 preset 目录——无需任何配置就在新机器上工作）

### 路径发现优先级
1. `config.presetRoot`（composition 显式覆盖）
2. `shellEnv.DSH_COMFYUI_PRESET_ROOT`（运行时 shell env）
3. `process.env.DSH_COMFYUI_PRESET_ROOT`（preset 进程 env）
4. **`__dirname`**（preset's own directory，**新机器无配置时正确**）
5. `process.cwd()`（仅在含 `skills/` 和 `runtime/` 时）

### 文件 IO
- preset 本地 plugin 用 Node `require('node:fs')` + `require('node:path')`（Cordis loader 走 CJS/ESM 互操作）
- 动态 plugin 沙箱无 `require` / `process`

### Process spawn
- `ctx.get('subprocess').spawn(spec)` 返回 SubprocessHandle
- `handle.collected.stdout.chunks` 是 `Uint8Array[]`，需 `TextDecoder('utf-8')` 解码

### Module cache（DSH 部署特性）
- 同一进程内修改 preset 本地 JS 文件，已 mount 的 generation 仍使用旧代码（Node ESM 缓存按 URL）
- 新会话/重启 DSH 后自动加载最新代码
- 开发期间可绕过：rename 文件

### Preset isolation
- 工具注册到 preset 的 standing scope layer
- 只有加入该 preset 的 agent session 才能看到工具

## 真实 Bug 修复（不属于"补丁"或向后兼容）

4 个 cli.py 模块（h3_prompt / camera_image / camera_video / camera_multiview）的 `main(argv: Sequence[str] | None, *, ...)` 缺默认值 → console script 不可用。修复 `argv: Sequence[str] | None = None`（仅一行变更 ×4 文件）。Commit `55fb651`。

## 端到端测试记录

### Test 1-7: 早期版本（v6 loader + 外部项目）— 见 git log
已 commit 8 个版本（loader-v6.js + Phase A/B/C 迭代）。

### Test 8: 新版本（v7 loader + bundle + 自动 setup）
**6/6 CLI 端到端验证**：

| CLI | Action | exit | ok |
|---|---|---|---|
| anima-prompt-v1 | catalog search "1girl" | 0 | true |
| minimax-h3-prompt | tokenizer verify | 0 | true |
| camera-image | describe t2i-camera | 0 | true |
| camera-video | describe t2v-video | 0 | true |
| camera-multiview | describe multiview | 0 | true |
| camera-multiview | assets verify | 0 | true |

**关键数据链**：
- `anima catalog search "1girl"` → 命中 `tag-catalog.sqlite` (1.64 GB) → 返回 `1girl` 和 `_1girl` tag，完整 provenance (source, source_version, checksums)
- `h3 tokenizer verify` → 命中 `tokenizer.json` (7 MB) → verified:true, snapshot_id:h3-qwen3-vl
- `camera-image describe t2i-camera` → 命中 `workflow/t2i-camera/groups.json` → asset_fingerprint + 完整 field_map
- `camera-video describe t2v-video` → 命中 `workflow/minimax-h3-t2v.json` → workflow_name: t2v-video
- `camera-multiview assets verify` → 命中 `Flux2-Klein人物一键多视图工作流.json` → verified:true

### Test 9: 路径发现
- config.presetRoot / shellEnv / process.env 优先级全部存在
- `__dirname` 在新机器（无任何配置）下返回 loader.js 自身目录 = preset 目录 = 正确

### Test 10: 优雅降级
- 无 `.venv` → loader 打印 setup hint，不注册 CLI tools，prompt sections 仍工作
- 有 `.venv` → loader 注册 5 个 CLI tools

## 最终 preset 目录结构（258 文件，1.85 GB）

```
.venv/                     ❌ 不分发（setup 脚本在每台机器上重新创建）
agent.cordis.yml           ✅ 2.9 KB
preset.yml                 ✅ 227 B
loader-v7.js               ✅ 10 KB
scripts/setup.ps1          ✅ Windows setup
scripts/setup.sh           ✅ POSIX setup
scripts/                   ✅ anima build scripts
runtime/                   ✅ comfyui_http shared dep
skills/                    ✅ 5 skills, 240 files
```

## 处女原则验证

- ✅ **0 硬编码绝对路径**（`grep` 验证：preset 目录中无 `D:\...` 或 `C:\Users\...`）
- ✅ **完整自包含**：0 外部项目依赖
- ✅ **setup 一次完成**：无需 `pip install -r` 反复操作
- ✅ **环境变量覆盖**：`DSH_COMFYUI_PRESET_ROOT` 可覆盖默认 `__dirname` 路径
- ✅ **跨平台**：`setup.ps1` (Windows) + `setup.sh` (POSIX) + `loader-v7.js` 平台无关

## 对抗性发现记录

1. cordis_define oneOf "plugin not match" — 参数序列化错误（字符串 vs 对象），不是 DSH bug
2. harness.registerTool 在 preset 本地 plugin 不可用 — 必须用 `ctx.tools.register`
3. ctx.config 不可用 — config 通过 `apply(ctx, config)` 第二参数
4. preset 本地 plugin Node 全局（process/require）可用 — 动态 plugin 沙箱不可用
5. subprocess stdout 需 `TextDecoder.decode(Uint8Array)` — 不是 `.text` 字段
6. Node ESM module cache — preset 本地 JS 文件按 URL 缓存
7. Preset 隔离 — 工具只在加入该 preset 的 agent session 中可见
8. **cli.py main 缺默认值** — 4 个文件需要 `argv: Sequence[str] | None = None` 修复
9. **pyproject.toml 依赖顺序** — `runtime\comfyui_http` 必须在 `skills\camera-*` 之前 install
10. **robo vs PowerShell copy** — PowerShell 的 `Copy-Item` 在某些子目录结构下会 null 引用错误；用 `robocopy /MIR` 更可靠

## 反思与未来改进

### 体积优化
当前 1.85 GB 主要来自 `tag-catalog.sqlite` (1.64 GB)。如果用户不需要精确 catalog 搜索，preset 仍能工作（无 SQLite 时 catalog search 报错，模型降级为 LLM 知识）。但用户明确要求完整 bundle，故保持当前体积。

### 离线支持
当前 setup.ps1 需要网络（pip install）。完全离线场景需要：
- prebuilt wheels 目录
- 或 vendor 目录（包含所有依赖 wheel 文件）

### 跨平台 CLI script 生成
setup 脚本在 Windows 和 POSIX 都用相同的 `pyproject.toml`，但 console script 后缀不同（.exe / 无）。loader-v7.js 已用 `process.platform === 'win32'` 正确处理。