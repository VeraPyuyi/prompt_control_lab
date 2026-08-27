# Provenance（来源与身份）

## 目的

`promptcontrollab.provenance` 记录公开的 Prompt 和模型身份，比较不同 run 的身份信息，并在模型漂移或来源不完整影响结论时给出提示。

## 使用场景

- 从 API response 或预测文件中提取 Provider 声明的模型 ID。
- 在 run manifest 中记录 Prompt ID、版本、文件和内容摘要。
- 检测当前 run 与历史 run 之间的 Provider/模型变化。
- 提示模型 alias、未知模型和不满足 Prompt-only 条件的比较。

## CLI 命令

```bash
pcl model-detect --response response.json --provider openai
pcl model-detect --model gpt-4o --provider openai --verify
pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json
pcl validity --baseline runs/previous --candidate runs/current --out runs/current/comparison_validity.json
```

## Python API

批准后的 canonical package 提供身份构建与比较函数：

```python
from promptcontrollab.provenance import (
    build_prompt_identity,
    compare_model_identities,
    detect_model_identity,
    run_model_drift,
)
```

`ModelIdentity` 保存 Provider、公开模型 ID、信息来源、可信度、验证元数据、警告和有边界的来源证据。

## 输入与产物

- 输入：response JSON、预测 JSONL、声明的 Provider/模型、Prompt 文件和 run manifest。
- 输出：模型身份、Prompt 身份区块、来源警告和 `model_drift.json`。
- Prompt 与 response 摘要可用于比较和完整性检查，但不能替代经过认证的回执。

## 依赖

离线检测只使用标准库和 `core`。在线验证由具体 Provider 决定，需要用户明确提供凭据，并始终是可选能力。

## 扩展点

- 增加 Provider 专属的 response 提取和元数据验证。
- 在保留日期锁定模型标识的同时增加 alias 风险规则。
- 在不改变较低追溯等级的前提下接入更强的签名回执或 Provider 日志证据。

## 限制

- Response 中的 `model` 字段表示 Provider 报告的公开模型 ID，不能证明隐藏权重或内部构建版本。
- 被拦截或篡改的 response 可以伪造未经认证的元数据。
- 行为探针可以辅助调查，但不能可靠证明模型身份。

## 测试与示例

相关覆盖包括模型身份、漂移、有效性和 manifest 测试。运行：

```bash
python -m pytest tests -k "model_identity or model_drift or prompt_identity or validity"
```
