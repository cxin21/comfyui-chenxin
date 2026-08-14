# comfyui-chenxin

本项目把“提示词创作”和“ComfyUI 执行”拆成独立边界：

- `skills/anima-prompt-v1`：Anima 生图提示词的 brief、路由、审计与本地知识库。
- `skills/minimax-h3-prompt`：MiniMax H3 的 T2VA/Ref2VA 提示词作者。
- `skills/camera-image`、`skills/camera-video`：只接收模型原生提示词并执行固定工作流。

提示词技能返回普通文本或普通记录，不创建 BuildLog、引用 ID 或执行门禁。相机执行输入分别是：

```json
{"prompt": {"positive": "...", "negative": "..."}}
```

```json
{"prompt": {"text": "..."}}
```

MCP 服务器负责发现、校验和执行 ComfyUI 技能，也通过 `author_prompt` 暴露
Anima 与 MiniMax-H3 的模型原生提示词作者流程。
