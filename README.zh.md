# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers) [![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**面向 prompt 优化的控制论诊断与可复现证据工具。**

本地 CLI/UI，用来复现论文诊断，并把 prompt 评测、模型溯源和 AI agent 审计变成可检查的证据。包名：`promptcontrollab`。英文版：[README.md](README.md)。

```bash
pip install -e ".[research,ui]"
pcl start --choice demo --language zh --out demo
pcl research-demo --out runs/research-demo && pcl diagnose --run runs/research-demo
```

想看菜单：`pcl start --guide --language zh`。

## 它补上了什么

- **论文研究核心：** `pcl research-demo`、`pcl diagnose`、`soft-hard`、`trajectory`、`riccati`、`tv-soft`。
- **证据桥接：** 导入外部评测，例如 `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`；`pcl ingest` 是 `pcl import` 的向后兼容别名。
- **Applied Agent Layer：** `pcl guard`、`audit-diff`、模型溯源、本地 UI、插件和 GitHub 模板。

UI：`pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501`。演示：[中文](docs/assets/demo/prompt_control_lab_demo.zh.mp4) / [English](docs/assets/demo/prompt_control_lab_demo.en.mp4)。

边界：记录公开 model id，不证明隐藏权重；pilot 是小样本，不是通用 benchmark；`guard` / `audit-diff` 是启发式工具，不是安全证明。

<details>
<summary>文档、证据和素材</summary>

文档：[选择指南](docs/choice_guide.zh.md)、[教程](docs/tutorial.zh.md)、[安装](docs/release_install.zh.md)、[论文功能映射](docs/research_from_paper.zh.md)、[对比](docs/comparison.zh.md)。证据：[production pilot](docs/production_pilot.zh.md)、[preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)、[paired pilot](docs/case_studies/agent_guard_paired_pilot.zh.md)。素材：[插件](plugins/)、[scorecard](docs/assets/ecosystem_scorecard.zh.svg)、[证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)。

</details>

Apache-2.0。见 [LICENSE](LICENSE)。
