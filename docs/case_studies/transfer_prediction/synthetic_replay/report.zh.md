# 控制诊断的独立迁移预测

**合成测试数据，不是实验结果。**

Evidence status: `historical_observation`.
Input SHA256: `cee3817d64f54eb4817282e384b7831c33acdf76fb1945389b416713ec36beee`.
External prediction lock: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.

G = AUC(state diagnostic) - AUC(reference loss).

| Model | Score | Valid pairs | Full MAE | Cheap MAE | Mean MAE | Zero MAE |
|---|---|---:|---:|---:|---:|---:|
| synthetic-model | primary | 1/1 | 0.2 | 0.4 | 0.5 | 1 |
| synthetic-model | norm | 1/1 | 0.2 | 0.4 | 0.5 | 1 |

输入声明历史观察、锁定预测或独立确认状态。本脚本只复算固定分数的 AUC 差和预测误差，不从行为标签拟合规则。
无定义 AUC 保留为空；逐对结果见 pairs.csv。独立性、原始张量和 token 重放、同时区间应由研究复现包另外核验。
优于统一均值与优于廉价预测分别回答逐对信息和控制测量的增量价值；单个点估计不能替代校正区间。
预测误差改善也不等于评估效率改善；后者还需计入探针、评分和行为检查成本。

Theory and practice: [control-response theory](https://arxiv.org/abs/2606.17762), [PromptControlLab](https://github.com/VeraPyuyi/prompt_control_lab).
