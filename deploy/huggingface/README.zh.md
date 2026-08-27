# prompt_control_lab 公共演示

这个 Docker Space 是 [prompt_control_lab](https://github.com/VeraPyuyi/prompt_control_lab)
的公开、仅 CPU 演示入口。项目面向 Prompt 和 AI Agent 的本地控制、归因与稳定性诊断；
其中受控制理论启发的诊断与作者关于 Prompt Engineering 和 Latent Dynamics 的数学工作
相关（[arXiv:2606.17762](https://arxiv.org/abs/2606.17762)）。

演示版可以离线运行 Prompt Guard 和 Prompt 改进建议，查看经过筛选的 Quick Analysis、
Checkpoint、Agent Audit、Model Drift、History、Terminal Sensitivity、Green Certificate
和 Posterior Certificate Artifact，并下载当前会话结果。证书和诊断只适用于页面中明确
标注的 Surrogate 或 Run，不能证明完整语言模型或 Agent 动作在全局范围内安全或最优。

## 公共演示边界

- 不使用 API Key，也不调用外部模型。
- 不提供 Shell 命令、Git 修改、插件安装、模型训练或实时 Agent Bridge。
- 上传仅支持受限的 JSON/JSONL Artifact，单文件最大 5 MB，并受会话累计容量和全局临时
  存储配额约束。
- 每个浏览器会话使用独立临时目录。原始 Prompt 不写入服务器 Artifact；上传内容只在该
  会话的服务端临时目录中保存，Space 重启后会消失。
- 完整本地 CLI 和源代码位于
  [GitHub](https://github.com/VeraPyuyi/prompt_control_lab)。请通过
  [Issues](https://github.com/VeraPyuyi/prompt_control_lab/issues) 报告问题，或在 GitHub
  提交 Pull Request。

本地安装、插件、真实仓库审计、Provider Adapter 和后训练工作流请使用 GitHub 项目，
不要依赖这个受限的在线演示。
