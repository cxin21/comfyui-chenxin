# workflow_config_guard.md — 工作流配置守护协议

> 所有修改 ComfyUI 工作流的操作必须遵循本协议。核心原则：**仅改配置，不改结构；先备份，后恢复**。

## 1. 核心约束

| 约束 | 说明 |
|------|------|
| **禁止新增节点** | 不允许 `add_node` 操作 |
| **禁止删除节点** | 不允许 `remove_node` 操作 |
| **仅改 widget 值** | 只允许 `set_input` 修改已有节点的 widget |
| **白名单制** | 每个工作流有明确的可修改节点白名单 |
| **备份-修改-执行-恢复** | 四步闭环，任何一步失败都中止 |

## 2. 白名单定义

### AnimaStandardV7.json（文生图）

| 节点 ID | class_type | 可修改 widget | 用途 |
|---------|-----------|--------------|------|
| 3 | `ImpactWildcardProcessor` "POSITIVE" | `wildcard_text` | 正向提示词 |
| 4 | `ImpactWildcardProcessor` "NEGATIVE" | `wildcard_text` | 反向提示词 |

**不允许修改的**：所有其他节点（采样器、分辨率、Detailer、hiresFix、GLSL 等共 71 个节点）

### ltx23AllInOneWorkflowForRTX_v44.json（视频生成）

| 节点 ID | class_type | 可修改 widget | 用途 |
|---------|-----------|--------------|------|
| 121 | `CLIPTextEncode` "positive" | `text` | 正向提示词 |
| 593 | `CLIPTextEncode` "negative" | `text` | 反向提示词 |
| 149 | `LoadImage` "First Frame" | `image` | 首帧图片（图生视频时） |
| 1792 | `PrimitiveInt` "Longer Edge" | `value` | 视频较长边分辨率 |
| 1793 | `PrimitiveInt` "Clip Length" | `value` | 视频时长（秒） |

**不允许修改的**：所有其他节点（采样器、LoRA、VAE 等共 73 个节点）

## 3. 四步闭环 SOP

### Step 1: 备份

Agent 侧操作：
```
1. mcp__comfyui__query_workflow(filename=workflow, ids=白名单节点IDs, fields="detail")
2. 将返回的 widget 当前值写入 $BACKUP_DIR/backup_manifest.json
```

### Step 2: 修改

```
operations = []
for each 白名单节点:
    operations.append({
        "op": "set_input",
        "node_id": 节点ID,
        "input_name": widget名,
        "value": 新值
    })

mcp__comfyui__modify_workflow(workflow=workflow_json, operations=operations)
```

**修改后立即验证**：
```
mcp__comfyui__query_workflow(ids=修改的节点IDs, fields="detail")
→ 确认 widget 值已更新
```

### Step 3: 执行

```
mcp__comfyui__enqueue_workflow(workflow=modified_workflow)
→ prompt_id
mcp__comfyui__get_job_status(prompt_id=prompt_id)
→ 等待完成
mcp__comfyui__get_image(filename=output_filename)
→ 保存结果
```

### Step 4: 恢复

```
operations = []
for each 备份的节点:
    operations.append({
        "op": "set_input",
        "node_id": 节点ID,
        "input_name": widget名,
        "value": 备份值
    })

mcp__comfyui__modify_workflow(workflow=workflow_json, operations=operations)
```

**恢复后验证**：
```
mcp__comfyui__query_workflow(ids=恢复的节点IDs, fields="detail")
→ 确认 widget 值已恢复
```

## 4. LoraManager 专属处理

LoraManager 节点（AnimaStandardV7 节点 5）没有可见 widget，LoRA 配置由 LoraManager 外部管理。

### 固定 LoRA（不可修改）

```
<lora:gpt-image-2_anima-base1_v1-1:0.80:0.80>
<lora:anima-base-1-masterpiece-v51:0.80>
<lora:细节调整:0.50>
```

这三个 LoRA 由 LoraManager 持久化管理，任何操作不得修改其名称、权重或删除。

### 额外 LoRA（可添加）

1. 查元数据：`mcp__comfyui__model_metadata_read(category="loras", name="<lora名>")`
2. 如有 CivitAI 数据：`mcp__comfyui__model_metadata_fetch_civitai(category="loras", name="<lora名>")`
3. 分析最佳权重和触发词
4. 通过 LoraManager 协议注入（不改固定 LoRA）
5. 执行后恢复 LoraManager 到原始状态

## 5. 异常处理

| 异常 | 处理 |
|------|------|
| 备份失败 | 中止操作，不执行修改 |
| 修改后验证失败 | 立即恢复，中止执行 |
| 执行失败（OOM/超时） | 仍然执行恢复步骤 |
| 恢复失败 | 记录错误，通知用户手动恢复 |
| 白名单外节点被修改 | 拒绝操作，报错 |

## 6. 审计日志

每次工作流修改记录到 `$PROJECT_ROOT/.workflow_backups/audit.log`：

```
[2026-07-26T10:30:00] WORKFLOW=AnimaStandardV7.json ACTION=modify NODES=3,4
[2026-07-26T10:30:05] WORKFLOW=AnimaStandardV7.json ACTION=execute PROMPT_ID=abc123
[2026-07-26T10:35:00] WORKFLOW=AnimaStandardV7.json ACTION=restore NODES=3,4 STATUS=success
```
