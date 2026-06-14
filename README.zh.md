# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**面向 prompt 优化的控制论诊断与可复现证据工具。**

`prompt_control_lab` 是 Prompt-Engineering-Optimal-Control 项目的开源工具包。它把 prompt
优化实验变成可审计的 artifact：干净的 train/validation/withheld 切分、成对统计、prompt-only
有效性检查、soft-to-hard gap、hidden-state trajectory 诊断、Riccati surrogate 探针和
time-varying soft-control 对比。

它也包含工程应用层：prompt policy guard、公开模型溯源、diff audit、GitHub/IDE 模板和本地
dashboard。这些是围绕研究证据链做出的应用，不替代论文中的诊断主线。

Python 包名是 `promptcontrollab`。仓库和项目名是 `prompt_control_lab`。

English documentation is available in [README.md](README.md).

## 快速开始

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"

# 一键体验论文风格 demo。
pcl research-demo --out runs/research-demo

# 基于 demo artifact 重新生成统一研究诊断。
pcl diagnose --run runs/research-demo

# 创建可复现 prompt 评测 demo，并打开本地 UI。
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

你会得到：split hash、scored predictions、metrics、成对 bootstrap/permutation 统计、
prompt-only 比较有效性、解释、gate 结果、研究诊断、报告 artifact 和本地仪表盘。UI 只读取本地文件，
不会上传 prompt、代码或报告。

![prompt_control_lab 工作流](docs/assets/workflow.zh.svg)

## 它补上了什么

| 层级 | 主要命令 | 能回答什么问题 |
|---|---|---|
| 可复现协议 | `pcl split`, `pcl analyze`, `pcl stats`, `pcl validity` | 这次 prompt 对比是否切分干净、成对可比、统计上可解释？ |
| 论文诊断 | `pcl soft-hard`, `pcl trajectory`, `pcl riccati`, `pcl tv-soft`, `pcl diagnose` | 除了输出分数，内部轨迹和控制论 surrogate 发生了什么？ |
| 证据包 | `pcl evidence-card`, `pcl evidence-gate`, `pcl claim-check` | 当前证据最多能支持哪一级 claim？ |
| 生态桥接 | `pcl import`, `pcl evidence-from`, `pcl evidence-audit` | 在 Promptfoo、DeepEval、Langfuse、LangSmith 或 prompt optimizer 之上，PCL 补了哪些证据？ |
| Agent 工作流 | `pcl guard`, `pcl model-detect`, `pcl audit-diff`, `pcl history` | AI 编程 agent 执行前后是否留下了可审计记录？ |

## 研究流程

最快体验论文功能：

```bash
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
```

`research-demo` 会生成可检查的 synthetic artifact，覆盖 tri-split 评测、成对统计、prompt-only
有效性、evidence card、evidence gate、claim check、soft-hard gap、trajectory、Riccati surrogate
和 time-varying soft-control。

如果你已经有自己的 soft prompt、hidden states、surrogate matrices 或 method predictions，
可以直接用 `pcl diagnose` 生成统一诊断报告。

论文概念到命令的完整映射见：[论文功能映射](docs/research_from_paper.zh.md)。

![prompt_control_lab 诊断图](docs/assets/diagnostics.zh.svg)

## 本地 UI

```bash
pip install -e ".[ui]"
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

dashboard 包含研究总览、教程、工作流、Guard Prompt、Run Report、Model Drift、Agent Diff Audit
和 History。它既能查看 artifact，也能触发受控的本地工作流：guard、analyze、gate、audit-diff、
agent-run、PR summary、外部证据导入和报告 zip 导出。

![prompt_control_lab UI 工作流教程截图](docs/assets/tutorial_workflows.zh.png)

4K 实操演示视频：
[中文 MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4)，
[English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4)。

## 生态桥接

如果你已经在用 Promptfoo、DeepEval、Langfuse、LangSmith 或 prompt optimizer，不需要替换它们。
PCL 的作用是补一层研究证据：prompt-only 比较有效性、成对不确定性、evidence card、claim check、
source/bundle hash 验证，以及论文诊断缺口追踪。

```bash
pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo
pcl evidence-audit --tool promptfoo --baseline-input results.json --candidate-input results.json --out runs/from-promptfoo-audit
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import auto --input results.json --out runs/from-external --score-name exact_match
```

`pcl ingest` 仍作为 `pcl import` 的向后兼容别名保留。

详见：[生态桥接](docs/ecosystem_bridge.zh.md) 和
[与 Promptfoo、LangSmith、Langfuse、Prompt Optimizer 的对比](docs/comparison.zh.md)。
更多图示：[生态 scorecard](docs/assets/ecosystem_scorecard.zh.svg) 和
[PCL 补充证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)。

![prompt_control_lab 生态定位](docs/assets/ecosystem.zh.svg)

## Agent 应用层

工程应用层把同一套证据习惯用于 Claude Code、Cursor、Codex 和 shell agent：

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl model-detect --response response.json --provider openai
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl history index --runs runs/ --out runs/history_index.json
pcl export-report --run runs/quick --out runs/quick/report.zip
```

安装本地模板：

```bash
pcl install-plugin codex
pcl install-plugin cursor
pcl install-plugin claude-code
pcl install-plugin github-action
```

边界：`pcl guard` 和 `pcl audit-diff` 是启发式 preflight / governance 工具。它们能减少明显风险并产出审计记录，
但不能证明 agent 行为一定安全。

## 证据边界

- 模型溯源记录的是公开 model id 和证据等级，不证明服务商隐藏权重版本。见
  [决策指南](docs/decision_guide.zh.md)。
- 本地 paired pilots 用于透明记录，不是通用 benchmark。见
  [preflight pilot](docs/case_studies/agent_guard_pilot.zh.md) 和
  [paired agent pilot](docs/case_studies/agent_guard_paired_pilot.zh.md)。
- Guarded prompt 可能比 raw prompt 更长，因为它补充了范围、约束和测试计划。目标不总是“更短”，而是更清楚、
  更可控、更容易审计。

## 安装说明

```bash
pip install -e .
pip install -e ".[research]"
pip install -e ".[hf]"      # 可选：HuggingFace hidden-state 提取
pip install -e ".[ui]"      # 可选：本地 dashboard
pcl doctor
```

本地 wheel / pipx 验证：

```bash
python -m build
pipx install dist/promptcontrollab-0.1.0-py3-none-any.whl
pcl doctor
```

`pcl init` 会写入 `.promptcontrol.yaml`，保存 guard policy、gate policy、runs 目录、expected paths
和 UI 默认页等本地默认值。显式 CLI 参数仍然优先。

## 文档

- [使用背景](docs/background.zh.md)
- [面向用户](docs/users.zh.md)
- [一步一步教程](docs/tutorial.zh.md)
- [Artifact 说明](docs/artifacts.zh.md)
- [论文功能映射](docs/research_from_paper.zh.md)
- [生态桥接](docs/ecosystem_bridge.zh.md)
- [与 Promptfoo、LangSmith、Langfuse、Prompt Optimizer 的对比](docs/comparison.zh.md)
- [创新点和贡献](docs/innovation.zh.md)
- [生产级试点协议](docs/production_pilot.zh.md)
- [发布和安装验证](docs/release_install.zh.md)
- [插件模板](plugins/)

## License

Apache-2.0。见 [LICENSE](LICENSE)。
