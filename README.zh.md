# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**面向 prompt 优化的控制论诊断与可复现证据工具。**

`prompt_control_lab` 是 Prompt-Engineering-Optimal-Control 项目的开源工具包。它把 prompt
实验变成可审计 artifact：干净切分、成对统计、prompt-only 有效性检查、soft-to-hard gap、
hidden-state trajectory 诊断、Riccati surrogate 探针和 time-varying soft-control 对比。

它也提供 AI 编程 agent 应用层：prompt policy guard、公开模型溯源、diff audit、
IDE/GitHub 模板和本地 dashboard。这些工程能力围绕研究证据层展开，不替代论文诊断主线。

Python 包名：`promptcontrollab`。仓库名：`prompt_control_lab`。
英文文档：[README.md](README.md)。

## 快速开始

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"

pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo

pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

你会得到 split hash、metrics、成对不确定性、prompt-only 有效性、evidence gate、研究诊断、
报告和本地仪表盘。UI 只读取本地文件。

![prompt_control_lab 工作流](docs/assets/workflow.zh.svg)

## 它补上了什么

| 层级 | 命令 | 主要问题 |
|---|---|---|
| 可复现协议 | `pcl split`, `pcl analyze`, `pcl stats`, `pcl validity` | 对比是否干净、成对、统计上可解释？ |
| 论文诊断 | `pcl soft-hard`, `pcl trajectory`, `pcl riccati`, `pcl tv-soft`, `pcl diagnose` | 除了输出分数，还发生了什么？ |
| 证据包 | `pcl evidence-card`, `pcl evidence-gate`, `pcl claim-check` | 当前证据支持哪一级 claim？ |
| 生态桥接 | `pcl import`, `pcl evidence-from`, `pcl evidence-audit` | 在已有工具之上，PCL 补了哪些证据？ |
| Agent 应用层 | `pcl guard`, `pcl model-detect`, `pcl audit-diff`, `pcl history` | Agent 执行前后是否留下可审计记录？ |

## 研究流程

```bash
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
```

这会覆盖 tri-split 评测、成对统计、prompt-only 有效性、evidence card、claim check、
soft-hard gap、trajectory、Riccati surrogate 和 time-varying soft-control。
完整映射：[论文功能映射](docs/research_from_paper.zh.md)。

## 本地 UI

```bash
pip install -e ".[ui]"
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

页面：Research Overview、Tutorial、Workflows、Guard Prompt、Run Report、Model Drift、
Agent Diff Audit 和 History。

![prompt_control_lab UI 工作流教程截图](docs/assets/tutorial_workflows.zh.png)

4K 实操演示：[中文 MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4) |
[English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4)

## 生态桥接

PCL 不替代 Promptfoo、DeepEval、Langfuse、LangSmith 或 prompt optimizer。它补的是
prompt-only 有效性、成对不确定性、claim check、hash 验证和诊断缺口追踪。

```bash
pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import auto --input results.json --out runs/from-external --score-name exact_match
pcl evidence-audit --tool promptfoo --baseline-input results.json --candidate-input results.json --out runs/from-promptfoo-audit
```

`pcl ingest` 仍作为 `pcl import` 的向后兼容别名保留。

文档和图示：[生态桥接](docs/ecosystem_bridge.zh.md)，[对比说明](docs/comparison.zh.md)，
[生态 scorecard](docs/assets/ecosystem_scorecard.zh.svg)，
[PCL 补充证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)。

## Agent 应用层

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl model-detect --response response.json --provider openai
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl history index --runs runs/ --out runs/history_index.json
pcl export-report --run runs/quick --out runs/quick/report.zip
pcl install-plugin all
```

边界：`pcl guard` 和 `pcl audit-diff` 是启发式 preflight / governance 工具。它们能减少明显风险并产出审计记录，
但不能证明 agent 行为一定安全。

## 证据边界

- 模型溯源记录公开 model id 和证据等级，不证明服务商隐藏权重版本。见
  [决策指南](docs/decision_guide.zh.md)。
- 本地 paired pilots 用于透明记录，不是通用 benchmark：
  [preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)，
  [paired agent pilot](docs/case_studies/agent_guard_paired_pilot.zh.md)。
- Guarded prompt 可能比 raw prompt 更长，因为它补充范围、约束和测试计划。

## 安装和文档

```bash
pip install -e .
pip install -e ".[research]"  # 论文诊断
pip install -e ".[hf]"        # 可选 hidden-state 提取
pip install -e ".[ui]"        # 本地 dashboard
pcl doctor
```

`pcl init` 会写入 `.promptcontrol.yaml`；显式 CLI 参数仍然优先。wheel / pipx 细节：
[发布和安装验证](docs/release_install.zh.md)。

主要文档：[使用背景](docs/background.zh.md)、[面向用户](docs/users.zh.md)、
[一步一步教程](docs/tutorial.zh.md)、[Artifact 说明](docs/artifacts.zh.md)、
[创新点和贡献](docs/innovation.zh.md)、[生产级试点协议](docs/production_pilot.zh.md)、
[插件模板](plugins/)。

## License

Apache-2.0。见 [LICENSE](LICENSE)。
