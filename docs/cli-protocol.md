# Skill CLI Protocol

状态：冻结（P1）  
版本：1  
日期：2026-08-15

## 1. 适用范围

本协议适用于以下五个独立 CLI：

- `anima-prompt-v1`
- `minimax-h3-prompt`
- `camera-image`
- `camera-video`
- `camera-multiview`

协议是共享契约，不是中央运行时。每个 Skill 包内置自己的 `cli_protocol.py`，仅使用 Python 标准库，不导入其他 Skill、MCP、Node 或 `npx`。因此任意 Skill 都能独立安装和调用。

## 2. 请求输入

机器调用必须从且仅从一种来源读取 UTF-8 JSON 对象：

```text
--request FILE   从文件读取
--stdin          从标准输入读取
```

规则：

1. 两者必须二选一；同时提供或都不提供均为 request error。
2. 根 JSON 值必须是 object；array、string、number、boolean 和 null 均拒绝。
3. JSON 解码、UTF-8 解码和文件读取错误均为 request error。
4. 命令自己的必需字段、未知字段和业务约束由命令校验层处理，不由公共协议静默补齐。
5. 路径字段在进入执行层前由对应命令解析为绝对路径；输出目录不得覆盖输入资产。

## 3. JSON 响应信封

使用 `--json` 时，stdout 只输出一个 JSON 对象和一个结尾换行。六个顶层字段始终存在：

```json
{
  "ok": true,
  "command": "author",
  "stage": "t2va",
  "result": {},
  "errors": [],
  "advisories": []
}
```

字段含义：

| 字段 | 类型 | 约束 |
|---|---|---|
| `ok` | boolean | 成功为 `true`，失败为 `false` |
| `command` | string | 当前逻辑命令，例如 `author`、`catalog search`、`run` |
| `stage` | string 或 null | 模型/工作流阶段；不适用时为 null |
| `result` | 任意 JSON 值 | 成功结果；失败时必须为 null |
| `errors` | array | 成功时为空；失败时至少包含一条结构化错误 |
| `advisories` | array | 不阻断执行的提示；不得混入 prompt 文本 |

失败示例：

```json
{
  "ok": false,
  "command": "validate",
  "stage": "i2i-camera",
  "result": null,
  "errors": [
    {
      "code": "reference_required",
      "message": "reference_image is required",
      "details": {"field": "reference_image"}
    }
  ],
  "advisories": []
}
```

每条 error 必须包含：

- `code`：稳定、机器可判断的错误代码；
- `message`：面向人的简短说明；
- `details`：结构化上下文，没有额外信息时使用空 object。

Prompt 的 `positive`、`negative` 或 `text` 只能出现在 `result` 内，且只包含可复制提示词。provenance、findings、assumptions、phase status 和 diagnostics 必须位于旁路字段中。

## 4. 输出通道

- stdout：仅承载最终 JSON 信封或明确请求的人类输出。
- stderr：日志、进度、调试信息和 unexpected error 的 traceback。
- 二进制产物：写入显式输出目录，JSON 只返回绝对路径、类型、大小和 SHA-256。
- JSON 模式不得在 stdout 输出 banner、进度条、警告前缀或 traceback。

## 5. 退出码

退出码由错误类别决定，不通过匹配错误文本推断：

| 退出码 | 类别 | 含义 |
|---:|---|---|
| 0 | success | 命令成功完成 |
| 2 | request | 参数、输入源、UTF-8 或 JSON 错误 |
| 3 | validation | 结构化请求或业务规则校验失败 |
| 4 | integrity | 固定资产、Catalog、manifest 或 tokenizer 完整性失败 |
| 5 | runtime | ComfyUI 连接、排队、执行、轮询或下载失败 |
| 70 | unexpected | 未捕获内部错误 |

JSON 信封中的 `error.code` 不等于进程退出码。命令先根据失败边界选择类别，再使用固定映射退出；错误消息内容不得改变退出码。

## 6. 人类输出

不使用 `--json` 时，CLI 可以渲染面向终端的人类输出，但必须遵守以下规则：

1. 退出码和 JSON 模式一致。
2. 不隐瞒 JSON 模式会报告的错误或未验证状态。
3. `--help` 和 `--version` 不读取请求，不访问网络，不连接 ComfyUI。
4. Skill 文档和自动化调用统一使用 JSON 模式。

## 7. 内置实现

五个包分别提供：

```text
anima_prompt_v1.cli_protocol
h3_prompt.cli_protocol
camera_image.cli_protocol
camera_video.cli_protocol
camera_multiview.cli_protocol
```

每个模块公开：

- `RequestInputError`
- `emit_success()`
- `emit_failure()`
- `load_json_request()`
- `exit_code_for_error()`
- `write_json()`

实现允许随各包独立发布，但行为必须持续通过 `tests/cli_protocol/test_protocol_examples.py`。后续命令不得创建新的顶层信封、退出码映射或 stdout 规则。

## 8. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/cli_protocol -q --basetemp .runtime-test-tmp-p1
```

P2 至 P8 的每个阶段都必须把此契约测试加入回归范围。

