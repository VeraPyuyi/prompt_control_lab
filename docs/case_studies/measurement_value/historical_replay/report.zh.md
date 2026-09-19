# 测量价值：固定预算案例

基于所提供记录的成本重放。

声明的证据状态：`historical_observation`。
输入文件 SHA256：`eafacdb018e50f40199012e6d422599bcd92477d6e34089f53e5ca45fbdd2257`。

该状态由输入显式声明；文件完整性与标签存在不会把历史观察升级为独立确认。
发现事件为 `abs(risk_target-risk_source)`；风险增加和减少都计数。
K 是预算内完整配对审计量，p 是其中发现比例，Y 是发现数。
所有 delta_Y 都相对于同一案例的未付费 direct。

下表在每个模型内按策略汇总。逐案例结果见 strategies.csv；完整队列及精确分解见 results.json。
未提供 probe_seconds 与 selection_seconds 的案例不会生成付费策略行。

| 模型 | 策略 | 配对数 | 总 K | 总 Y | 平均 Y | 总 delta_Y |
|---|---|---:|---:|---:|---:|---:|
| granite | direct | 19 | 4580 | 1286 | 67.684211 | 0 |
| granite | loss | 19 | 1207 | 626 | 32.947368 | -660 |
| granite | norm | 19 | 1883 | 619 | 32.578947 | -667 |
| granite | paid_direct | 19 | 4343 | 1219 | 64.157895 | -67 |
| granite | paid_loss | 19 | 971 | 506 | 26.631579 | -780 |
| granite | paid_norm | 19 | 1645 | 540 | 28.421053 | -746 |
| granite | paid_primary | 19 | 1333 | 442 | 23.263158 | -844 |
| granite | primary | 19 | 1567 | 528 | 27.789474 | -758 |
| ministral | direct | 19 | 5431 | 1144 | 60.210526 | 0 |
| ministral | loss | 19 | 1496 | 706 | 37.157895 | -438 |
| ministral | norm | 19 | 2143 | 285 | 15.000000 | -859 |
| ministral | paid_direct | 19 | 5051 | 1064 | 56.000000 | -80 |
| ministral | paid_loss | 19 | 1119 | 518 | 27.263158 | -626 |
| ministral | paid_norm | 19 | 1758 | 221 | 11.631579 | -923 |
| ministral | paid_primary | 19 | 831 | 150 | 7.894737 | -994 |
| ministral | primary | 19 | 1218 | 230 | 12.105263 | -914 |
| qwen35 | direct | 16 | 6400 | 690 | 43.125000 | 0 |
| qwen35 | loss | 16 | 1277 | 516 | 32.250000 | -174 |
| qwen35 | norm | 16 | 1624 | 272 | 17.000000 | -418 |
| qwen35 | paid_direct | 16 | 6293 | 677 | 42.312500 | -13 |
| qwen35 | paid_loss | 16 | 893 | 404 | 25.250000 | -286 |
| qwen35 | paid_norm | 16 | 1241 | 210 | 13.125000 | -480 |
| qwen35 | paid_primary | 16 | 1102 | 210 | 13.125000 | -480 |
| qwen35 | primary | 16 | 1485 | 256 | 16.000000 | -434 |

`delta_Y = K_s*(p_s-p_0) - (K_0-K_s)*p_0`.

这是标准计数恒等式，不是论文的新定理。精确有理数项在 JSON 中保留。K=0 时 p 为 null；K_0=0 时精度分解未定义，但 Y 与 delta_Y 仍保留。

精度盈亏阈值是 Y_0/K_s；大于 1 表示该完成量下即使全部命中也无法追平 direct。只有观察到的计数参与这项描述，不据此保证下一案例的表现。

T 是论文控制时域，L 是生成长度上限，B 是墙钟时间预算，三者不可互换。

理论边界和独立的锁定决策接口见 [measurement-value case documentation](https://github.com/VeraPyuyi/prompt_control_lab/tree/main/docs/case_studies/measurement_value).
