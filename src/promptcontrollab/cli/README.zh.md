# CLI（命令行入口）

## 目的

`promptcontrollab.cli` 是稳定的命令行组合层。它注册命令、校验参数、解析项目默认值、调用领域 API、格式化人类可读或 JSON 输出，并把已知异常转换为简洁的 `pcl: error:` 信息。

## 使用场景

- 通过统一 `pcl` 入口发现可用工作流。
- 从本地终端、脚本、CI 和 Adapter 调用领域操作。
- 在内部模块演进时保持 Flag、默认值、输出 schema 和退出行为稳定。
- 提供中英文指引，同时不改变机器可读的内部值。

## CLI 命令

```bash
pcl --help
pcl start --guide --language zh
pcl quickstart --out demo --language zh --open-report
pcl choose --need "比较两个 Prompt" --language zh
pcl doctor --json
```

领域命令由对应模块 README 说明，此处不重复完整列表。

## Python API

Console Entry Point 保持可导入：

```python
from promptcontrollab.cli import build_parser, main

parser = build_parser()
exit_code = main(["doctor", "--json"])
```

`_reconfigure_windows_pipe` 是现有 Console Entry Point 的兼容工具；其他以下划线开头的 Helper 均视为私有实现。

## 输入与产物

- 输入：命令参数、标准输入、项目配置、环境变量和领域专属文件。
- 输出：终端文本或 JSON、领域 artifact 和常规进程退出码。
- CLI 负责展示与调度；领域模块负责 artifact 语义。

## 依赖

参数解析只使用 Python 标准库。具体命令会导入对应领域实现，并在可选 extra 缺失时给出可直接执行的安装提示。

## 扩展点

- 在对应领域命令模块中注册 Parser 和 Handler。
- 复用共享路径、语言、JSON 和错误格式化工具。
- 保持 Command Handler 轻量，把业务逻辑放在领域 package 中。

## 限制

- CLI 不是领域逻辑的第二套实现。
- 私有命令 Helper 不属于兼容 API。
- 交互式输出可以演进，但已文档化的 JSON schema 和公共 Flag 变更必须经过兼容性审查。

## 测试与示例

CLI 测试覆盖 Parser 构建、Help、错误、Windows Pipe 行为和工作流 Smoke Test。运行：

```bash
python -m pytest tests -k "cli or quickstart or start or choose or doctor"
```
