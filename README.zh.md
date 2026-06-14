# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**面向 prompt 优化的控制论诊断与可复现证据工具。**

`prompt_control_lab` 把 prompt 优化实验变成可审计 artifact：干净切分、成对统计、soft-to-hard gap、hidden-state trajectory、Riccati 探针和 time-varying soft-control 对比。Agent guard、模型溯源、diff audit、本地 UI、IDE/GitHub 模板是可选工作流层。

Python 包名：`promptcontrollab`。仓库名：`prompt_control_lab`。英文文档：[README.md](README.md)。

## 快速开始

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

## 常用命令

它补上了什么：论文诊断核心、证据桥接、Agent 应用层。

```bash
# 论文诊断核心
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo

# 证据桥接
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl scaffold-check --run runs/from-promptfoo

# Agent 应用层
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
```

`pcl ingest` 是 `pcl import` 的向后兼容别名。

## UI 和演示

运行 `pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501` 打开本地仪表盘。它只读取本地 artifacts。

4K 实操演示：[中文 MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4) | [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4)。

## 证据边界

模型溯源记录公开 model id 和证据等级，不证明服务商隐藏权重版本。本地 pilots 是透明小样本，不是通用 benchmark。`pcl guard` 和 `pcl audit-diff` 是启发式治理工具，不是安全证明。

## 文档

[论文功能映射](docs/research_from_paper.zh.md) | [教程](docs/tutorial.zh.md) | [Artifacts](docs/artifacts.zh.md) | [生态桥接](docs/ecosystem_bridge.zh.md) | [决策指南](docs/decision_guide.zh.md) | [对比](docs/comparison.zh.md) | [production pilot](docs/production_pilot.zh.md) | [preflight pilot](docs/case_studies/agent_guard_pilot.zh.md) | [paired pilot](docs/case_studies/agent_guard_paired_pilot.zh.md) | [scorecard](docs/assets/ecosystem_scorecard.zh.svg) | [证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg) | [安装/发布](docs/release_install.zh.md) | [插件](plugins/)

Apache-2.0。见 [LICENSE](LICENSE)。
