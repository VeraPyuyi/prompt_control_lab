# Core（核心基础设施）

## 目的

`promptcontrollab.core` 提供所有功能域共享的基础设施，包括配置、JSON/JSONL 读写、公共 schema、错误类型、可选依赖检查和版本信息。该模块保持独立于产品功能模块。

## 使用场景

- 从 `.promptcontrol.yaml` 读取项目默认配置。
- 读写确定性的本地 artifact。
- 在模块间共享任务、预测和指标记录。
- 在不导入产品领域的前提下提示缺失的可选依赖。

## CLI 命令

Core 没有独立 CLI 命令；面向用户的命令通过各自所属领域使用这些基础能力。

## Python API

批准后的 canonical package 将导出以下基础能力：

```python
from promptcontrollab.core import (
    PromptControlLabError,
    TaskRecord,
    load_project_config,
    read_json,
    stable_digest,
    write_json,
)
```

实现模块包括 `config`、`files`、`schemas`、`errors`、`optional` 和 `version`。

## 输入与产物

- 输入：`.promptcontrol.yaml`、JSON、JSONL、路径和环境状态。
- 输出：规范化配置、类型化记录、JSON/JSONL 文件和稳定摘要。
- Core 工具不定义具体业务域的 run artifact。

## 依赖

Core 只使用 Python 标准库和项目默认的零额外依赖运行环境。它不得导入 preflight、evaluation、control、audit、evidence、diagnostics、provenance 或 integrations。

## 扩展点

- 增加向后兼容的配置读取接口。
- 只有在两个或更多领域共享同一契约时，才增加公共 schema。
- 通过显式依赖检查和可操作的安装提示注册可选功能。

## 限制

- YAML 读取器只支持轻量、零依赖的子集，不支持完整 YAML 规范。
- 稳定摘要用于识别序列化内容，不是签名或真实性证明。

## 测试与示例

配置、文件、schema 和错误处理的覆盖位于 `tests/`。可运行：

```bash
python -m pytest tests -k "config or files or schema or errors"
```
