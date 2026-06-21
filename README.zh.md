# prompt_control_lab

**面向 prompt 优化的控制论诊断与可复现证据工具。** 包名：`promptcontrollab`。英文版：[README.md](README.md)。

```bash
pip install -e ".[research,ui]"
pcl start --guide --language zh
pcl research-quickstart --out runs/research-demo --language zh --open-report
```

## 它补上了什么

- **论文研究核心：** `pcl research-quickstart`；底层命令是 `pcl research-demo` + `pcl diagnose`；深入使用 `soft-hard`、`trajectory`、`riccati`、`tv-soft`。
- **证据桥接：** `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`；`pcl ingest` 是向后兼容别名。
- **Applied Agent Layer：** `pcl choose --need "安全评测" --language zh` 会指向 `guard`、`audit-diff`、本地 UI、插件和 GitHub 模板。

上手：[教程](docs/tutorial.zh.md)、[工具选择](docs/choice_guide.zh.md)、[安装](docs/release_install.zh.md)。快速 demo：`pcl quickstart --language zh --out demo --open-report`；别名：`pcl start --choice demo --language zh --out demo`。

<details><summary>文档、证据和素材</summary>

论文：[功能映射](docs/research_from_paper.zh.md)、[对比](docs/comparison.zh.md)。证据：[production pilot](docs/production_pilot.zh.md)、[preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)、[paired pilot](docs/case_studies/agent_guard_paired_pilot.zh.md)、[scorecard](docs/assets/ecosystem_scorecard.zh.svg)、[证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)、[演示视频](docs/assets/demo/prompt_control_lab_demo.zh.mp4)。

边界：记录公开 model id，不证明隐藏权重；pilot 是小样本，不是通用 benchmark；guard/audit 是启发式工具，不是安全证明。

</details>

Apache-2.0。见 [LICENSE](LICENSE)。
