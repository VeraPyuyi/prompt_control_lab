# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers) [![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**面向 prompt 优化的控制论诊断与可复现证据工具。**

`prompt_control_lab` 把 prompt 优化变成可审查证据：论文诊断、外部评测导入、prompt-only 有效性检查，以及本地 agent 治理。包名：`promptcontrollab`。英文：[README.md](README.md)。

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git && cd prompt_control_lab
pip install -e ".[research,ui]"
pcl start --choice demo --language zh --out demo && pcl start --guide --language zh
pcl research-demo --out runs/research-demo && pcl diagnose --run runs/research-demo
```

## 它补上了什么

- **论文诊断核心：** `pcl research-demo`、`pcl diagnose`、`pcl soft-hard`、`pcl trajectory`、`pcl riccati`、`pcl tv-soft`。
- **证据桥接：** `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`；`pcl ingest` 是 `pcl import` 的向后兼容别名。
- **Agent 应用层：** `pcl guard`、`pcl audit-diff`、模型溯源、本地 UI、插件和 GitHub 模板。

UI：`pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501`。演示视频：[中文](docs/assets/demo/prompt_control_lab_demo.zh.mp4) / [English](docs/assets/demo/prompt_control_lab_demo.en.mp4)。

证据边界：模型溯源记录公开 model id 和证据等级，不证明服务商隐藏权重版本。本地 pilots 是透明小样本，不是通用 benchmark。`guard` 和 `audit-diff` 是启发式治理工具，不是安全证明。

文档：[选择指南](docs/choice_guide.zh.md)、[教程](docs/tutorial.zh.md)、[安装](docs/release_install.zh.md)、[论文功能映射](docs/research_from_paper.zh.md)、[对比](docs/comparison.zh.md)、[production pilot](docs/production_pilot.zh.md)、[preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)、[paired pilot](docs/case_studies/agent_guard_paired_pilot.zh.md)、[插件](plugins/)、[scorecard](docs/assets/ecosystem_scorecard.zh.svg)、[证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)。

Apache-2.0。见 [LICENSE](LICENSE)。
