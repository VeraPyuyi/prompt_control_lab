# 为 PromptControlLab 做贡献

感谢你帮助改进 PromptControlLab。项目欢迎围绕 Prompt 与 Agent 控制、checkpoint
诊断、证据 adapter、Provider/Agent 集成、本地 UI、测试和文档提交范围明确的贡献。

英文说明：[CONTRIBUTING.md](CONTRIBUTING.md)。

## 开始修改之前

1. 先搜索已有 Issue 和 Pull Request。
2. 如果要新增较大的协议、adapter 或 artifact schema，请先提交 Feature Request。
3. 不要在 Issue、PR、fixture 或生成 artifact 中加入 API key、私有 Prompt、隐藏推理、
   私有数据集、模型权重或本机绝对路径。
4. 安全漏洞必须按照 [SECURITY.md](SECURITY.md) 使用 GitHub Private Vulnerability
   Reporting 报告，不要创建公开 Issue。

PromptControlLab 不是论文复现仓库。PEOC 等研究方法为部分诊断能力提供来源，但贡献
应当形成可复用、Provider 中立的能力，并明确结论边界。

## 开发环境

PromptControlLab 需要 Python 3.10 或更高版本。DeepSeek Harness 插件还需要 Node.js 22。

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
python -m pip install -e ".[dev,research]"
cd plugins/deepseek-harness
npm ci
cd ../..
```

开发 UI 时还需安装 `.[ui]`。Provider live test 必须保持为显式启用；缺少凭据时应当
清楚跳过，不能失败或尝试使用仓库中的凭据。

## 修改要求

- 控制修改范围，不做无关重构或生成文件抖动。
- 行为变化必须增加或更新测试。
- JSON artifact 应保持向后兼容；如需变更，必须采用版本化迁移并测试。
- 用户流程变化时同步更新中英文文档。
- `plugins/` 中的适配器与 `src/promptcontrollab/template_data/` 中的安装模板保持一致。
- 不修改上游论文、外部实验归档或导入证据的来源目录。

## 证据与结论边界

证据贡献必须分别写明：

1. 观察到了什么；
2. 可以解释什么；
3. 不能证明什么；
4. 下一步应采取什么行动。

不得把相关性、拟合 surrogate、小样本试点、replay、fixture 或未完成运行包装成严格
因果、普遍性能、生产安全或通用提升结论。必须保留 `hold`、
`insufficient_evidence`、置信区间和 p-value 等原始状态。公开案例只应包含支持独立
复核所需的最小聚合证据。

## 必须运行的检查

请求 review 前运行：

```bash
python -m pytest
python -m ruff check .
python -m mypy src tests
cd plugins/deepseek-harness
npm run check
```

如果修改了打包逻辑，还要按照[发布安装说明](docs/release_install.zh.md)，在全新环境中
构建并安装 wheel，同时构建 sdist 并检查文件列表，确保其中没有 VCS 数据、虚拟环境、
构建输出、运行 artifact、依赖目录、凭据或大型 Demo 媒体。

## Pull Request

请使用仓库 PR 模板，并写明：

- 用户遇到的问题和本次修改边界；
- 变化的 artifact 或 schema；
- 实际执行的验证命令和结果；
- 隐私与结论边界影响；
- 可见 UI 变化的截图。

如果一个 PR 混合了彼此独立的行为修改、生成证据和展示调整，维护者可能要求拆分。
