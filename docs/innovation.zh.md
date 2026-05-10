# 创新点和贡献

PromptControlLab 的目标不是再做一个只输出平均分的 prompt 评测脚本。它的贡献在于把 prompt 评测扩展成一个更完整的诊断流程。

## 1. 从单一分数走向可复现协议

工具把 train/validation/withheld 切分、split hash、leakage check 和 run manifest 固化下来。这样别人不仅能看到分数，还能知道分数是否来自干净的协议。

推动作用：减少 validation overfitting 和 test leakage，让 prompt optimization 的实验报告更可信。

## 2. 从平均分走向统计可靠性

工具内置 paired bootstrap、paired permutation 和 Holm correction。它不只报告 candidate 比 baseline 高多少，还报告这个差异是否可靠。

推动作用：让 prompt 改动更接近软件工程里的 regression testing，而不是只凭一次小样本分数判断。

## 3. 系统化 soft-to-hard 风险

很多 soft prompt 研究最终需要面对 hard prompt 部署。PromptControlLab 把 nearest-token projection gap 做成标准诊断结果。

推动作用：帮助 soft prompt 研究更诚实地报告部署风险，也帮助研究者理解 embedding 几何和 hard prompt 可用性之间的关系。

## 4. 把 hidden-state trajectory 变成可复用诊断对象

工具支持导入 hidden-state trajectory，输出 drift、decay slope 和 turnpike-like signal。用户可以比较不同 prompt、不同任务、不同模型下的内部轨迹变化。

推动作用：把 prompt evaluation 从“只看输出”推进到“同时看内部动态”。

## 5. 提供 Riccati surrogate 诊断

工具可以对有限维 surrogate 做 Riccati/DARE 稳定性检查，并明确说明这只是 surrogate diagnostic，不是对完整语言模型的证明。

推动作用：为 LLM control、prompt control 和 trajectory diagnostics 提供一个可复用的实验接口。

## 6. 提供 time-varying soft-control lane

工具把 static、time-varying、shuffled 和 random 方法放在同一个比较框架中，帮助判断收益来自时序结构还是参数容量。

推动作用：让 time-varying prompt 的机制分析更系统，减少只报告最好结果的倾向。

## 总体贡献

PromptControlLab 可以帮助相关领域向这些方向发展：

- prompt optimization 更可复现；
- prompt regression testing 更工程化；
- soft prompt 部署风险更可量化；
- hidden-state trajectory 成为常规诊断对象；
- prompt engineering 向 prompt control engineering 发展。

