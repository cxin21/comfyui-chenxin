# multiview

多视角转盘生成 stage。

> **占位** -- 尚未实现。当 multiview 流程被实际使用时，在此目录下补充步骤文档。

## 预期设计

- 使用固定 Flux 资产，两个 model-only LoRA loader 槽位
- 编译路径待定（可能复用 camera 流程的 load-fixed-graph -> patch -> validate -> enqueue 模式）
- 步骤文档结构参考 [t2i-camera/](../t2i-camera/)
