# Integrations（外部集成）

## 目的

`promptcontrollab.integrations` 将领域 API 连接到 Provider、Agent、开发工具、本地 Streamlit UI 和受限 Hugging Face Demo。Integration 负责转换外部协议，不重新定义核心证据或决策语义。

## 使用场景

- 通过统一的本地 Adapter 契约检查或调用受支持的模型 Provider。
- 安装和使用 DeepSeek Harness、Claude Code、Cursor、Codex 或 GitHub Action Adapter。
- 在不上传项目数据的前提下通过本地 Dashboard 查看 run。
- 构建公共安全、仅使用 CPU 的 Hugging Face Space Bundle。

## CLI 命令

```bash
pcl providers list
pcl providers inspect deepseek
pcl providers doctor deepseek
pcl harness init --project .
pcl harness doctor --project .
pcl install-plugin deepseek-harness
pcl install-plugin all --target ./installed-templates
pcl ui --runs runs --language zh
pcl github-app serve --host 0.0.0.0 --port 8080
pcl doctor --json
```

## Python API

批准后的 canonical package 提供 Integration Adapter 和 Installer：

```python
from promptcontrollab.integrations import (
    build_space_bundle,
    call_provider,
    doctor_harness,
    run_doctor,
    install_plugin,
    list_providers,
)
```

辅助 API 用于初始化和重放 Harness Session、验证 Hugging Face Demo 边界、读取 UI 数据和执行白名单内的 UI Workflow。安装诊断位于此模块，因为它需要组合 Policy、模板、Quick Analysis、插件和可选集成能力。

## 输入与产物

- 输入：Provider 配置、环境变量凭据、Harness Event JSONL、插件目标路径、run 目录和公共 Demo manifest。
- 输出：Provider response、已安装 Adapter 模板、Harness Control artifact、UI 视图/下载文件和经过筛选的 Space 部署 Bundle。
- 凭据只从环境变量读取，绝不能写入 artifact。

## 依赖

Provider 元数据和插件安装使用默认运行环境。UI 需要 `ui` extra，GitHub App 需要 `bot`，模型/后训练集成使用各自声明的可选 extra。DeepSeek Harness 插件使用独立的 TypeScript 工具链。

## 扩展点

- 通过共享 Provider Specification 和 Response Contract 增加 Provider。
- 通过把生命周期事件转换为 `ControlEvent` 增加 Agent Adapter。
- 增加消费结构化领域模型而不是解析渲染报告的 UI 页面和部署界面。

## 限制

- Provider 支持记录公开 API 行为，不识别隐藏模型内部实现。
- 轻量编辑器 Adapter 受宿主能力限制，无法拦截所有 Prompt 路径。
- Hugging Face Demo 会主动禁用 Provider、Git 修改、Shell 执行、插件安装和持久存储。

## 测试与示例

可参考 `plugins/`、`deploy/huggingface/`、Provider 文档、UI 测试和 Harness 契约测试。运行：

```bash
python -m pytest tests -k "provider or harness or plugin or ui or hf_demo or github_app"
```

原生 Harness 插件请在 `plugins/deepseek-harness` 中运行 `npm run check`。
