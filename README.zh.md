# prompt_control_lab

**面向 prompt 优化的控制论诊断与可复现证据工具。** 包名：`promptcontrollab`。英文版：[README.md](README.md)。

导入真实 PEOC 复现包，直接看清哪些证据可用、验证失败、不可用或缺失，避免把小范围结果包装成过大的主张。

```bash
pip install -e ".[research,ui]"
pcl research-import peoc --bundle <nmi_replication_bundle-路径> --out runs/peoc-real --portable --language zh
pcl ui --runs runs --language zh
```

## 它补上了什么

- **真实证据优先：** 来源哈希、归一化 PEOC 证据、带边界的案例报告、主张检查、缺口计划和可验证 research bundle。
- **新执行的研究诊断：** `pcl research-quickstart`、`pcl research-demo`、`pcl diagnose`，以及 `soft-hard`、`trajectory`、`riccati`、`tv-soft`。
- **可复现评测：** 三段 withheld protocol、成对统计、prompt-only 有效性、证据卡和 fail-closed 主张层级。
- **Applied Agent Layer：** `guard`、模型溯源、`audit-diff`、本地 UI、IDE/CLI 适配器和 GitHub 审查 artifact 复用同一套证据纪律。

## 从这里开始

- 一步一步导入真实 PEOC：[教程](docs/research_import_peoc.zh.md)
- 论文概念 -> 命令 -> 解释边界：[功能映射](docs/research_from_paper.zh.md)
- 暂时没有真实复现包：`pcl research-quickstart --out runs/research-demo --language zh --open-report`
- 导入外部评测：`pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`（`pcl ingest` 是向后兼容别名）
- 选择最短路径：`pcl choose --need "<你的目标>" --language zh` 和 [工具选择](docs/choice_guide.zh.md)

真实边界化证据：[PEOC 案例](docs/case_studies/peoc_real/README.zh.md)。演示：[4K 实操视频](docs/assets/demo/prompt_control_lab_demo.zh.mp4)。安装：[发布安装说明](docs/release_install.zh.md)。

边界：导入结果不是重新运行；特定任务 hard 分数不是通用排名；trajectory/Riccati 只是诊断或拟合 surrogate 检查；公开 model id 和哈希不能证明隐藏权重；guard/audit 是启发式工具，不是安全证明。

Apache-2.0。见 [LICENSE](LICENSE)。
