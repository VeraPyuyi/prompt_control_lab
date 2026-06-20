# prompt_control_lab

**面向 prompt 优化的控制论诊断与可复现证据工具。**

把论文里的 prompt 诊断做成本地 CLI/UI，并沉淀评测、模型溯源和 agent 审计证据。包名：`promptcontrollab`。英文版：[README.md](README.md)。

```bash
pip install -e ".[research,ui]"
pcl start --guide --language zh
pcl choose --need "安全评测和红队检查" --language zh
pcl start --choice demo --language zh --out demo
pcl research-demo --out runs/research-demo && pcl diagnose --run runs/research-demo
```

## 它补上了什么

**论文研究核心：** `pcl research-demo` -> `pcl diagnose`；深入用 `soft-hard`、`trajectory`、`riccati`、`tv-soft`。

**证据桥接：** `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`；`pcl ingest` 是 `pcl import` 的向后兼容别名。

**Applied Agent Layer：** `pcl guard`、`audit-diff`、模型溯源、UI（`pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501`）、插件、GitHub 模板。

文档：[教程](docs/tutorial.zh.md) | [论文功能映射](docs/research_from_paper.zh.md) | [工具选择](docs/choice_guide.zh.md) | [对比](docs/comparison.zh.md) | [安装](docs/release_install.zh.md)。

文档、证据和素材：[production pilot](docs/production_pilot.zh.md) | [preflight pilot](docs/case_studies/agent_guard_pilot.zh.md) | [paired pilot](docs/case_studies/agent_guard_paired_pilot.zh.md) | [scorecard](docs/assets/ecosystem_scorecard.zh.svg) / [证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg) | [演示视频](docs/assets/demo/prompt_control_lab_demo.zh.mp4)。

边界：记录公开 model id，不证明隐藏权重；pilot 是小样本，不是通用 benchmark；guard/audit 是启发式工具，不是安全证明。

Apache-2.0。见 [LICENSE](LICENSE)。
