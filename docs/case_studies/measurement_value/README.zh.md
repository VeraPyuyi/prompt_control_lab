# 固定审计预算下的测量价值

[English](README.md)

这个边界明确的 [PromptControlLab](https://github.com/VeraPyuyi/prompt_control_lab)
研究案例连接控制理论问题、固定的软提示跨群体迁移分数以及实测审计成本。
它回答一个操作层问题：支付诊断测量成本后，按诊断分数审计能否发现更多行为变化。
交付内容是可导入的标准库模块和研究脚本，不增加 Cockpit 流程。

用户提供的[历史研究记录](source_records.json)覆盖
**54 个配对，原生生成长度上限为 8**。
该成本测试为 **NO_GO**：三个模型的来源数据均值中，直接审计发现数均高于付费选择器。
这属于用户记录中的历史观察。目前没有新的效率确认，也没有新的 384 步训练结果。
下面的小型输入明确属于合成测试，不能作为这些实证判断的来源。

## 运行案例

在源代码仓库中运行，无需安装 PromptControlLab 或可选依赖：

```console
python -S scripts/run_measurement_value_case.py --input docs/case_studies/measurement_value/source_records.json --out measurement-value-output
```

[已核对的英文报告](historical_replay/report.md)、
[中文报告](historical_replay/report.zh.md)与
[逐配对 CSV](historical_replay/strategies.csv)均由这一输入生成。
四条目快速示例可将输入替换为同目录的 `synthetic_test.json`。
参见[数据来源与许可](DATA.md)。脚本确定性地输出
`results.json`、`strategies.csv`、`report.md` 和 `report.zh.md`，并记录输入文件
原始字节的 SHA256。报告按模型和策略汇总；CSV 保留逐配对结果；JSON 还保留完整
队列、完成前缀和精确有理数分解。脚本不调用模型、不启动训练，也不估计未记录成本。

导入接口为 `promptcontrollab.measurement_value.analyze_document(document)`。
`fixed_order(case, strategy)` 只读取条目 ID 和对应固定分数。
研究脚本自行加载本地 `src`；普通调用者可安装包，或将仓库的 `src` 加入导入路径。

## 输入约定：`measurement-value/v1`

| 顶层字段 | 含义 |
|---|---|
| `schema_version` | 固定为 `measurement-value/v1` |
| `evidence_status` | 显式声明 `historical_observation`、`locked_prediction` 或 `independent_confirmation` |
| `synthetic` | 必填布尔值；合成输入必须为 `true` |
| `provenance` | 可选的可公开来源说明，包括计时口径与分数定义 |
| `cases` | 非空数组，`(model, pair)` 坐标不可重复 |

每个案例包含 `model`、`pair`、非空且唯一的字符串 `item_ids`，以及与 ID 对齐的
`scores.loss`、`scores.primary`、`scores.norm` 数组。
`behavior.risk_source` 和 `behavior.risk_target` 是对齐的二元 0/1 风险标签。
`costs` 对象的结构如下：

| 成本字段 | 单位及范围 |
|---|---|
| `generation_pair_seconds` | 每个条目来源加目标完整行为审计的秒数，数组与 ID 对齐 |
| `budget_seconds` | B，该模型与配对的总墙钟时间预算 |
| `direct_sort_seconds` | 直接审计固定队列的构建时间 |
| `scan_seconds` | 必须恰含 `loss`、`primary`、`norm`，分别为整个条目池的分数扫描时间 |
| `sort_seconds` | 必须恰含 `loss`、`primary`、`norm`，分别为排序时间 |
| `probe_seconds`、`selection_seconds` | 可选，但必须同时提供；额外诊断探针与策略选择时间 |

全部成本必须是有限、非负的 JSON 数值，布尔值和数字字符串会被拒绝。分数必须有限，
可以为负数。时间合计也必须可表示为有限输出数值；超出范围时给出验证错误，不截断。
成本须采用相同计时口径。如果实测 `selector_overhead_seconds` 已包括
探针和 CPU 选择时间，可将其放入 `probe_seconds`，并设置 `selection_seconds=0`，
同时在来源说明中记录该聚合口径，避免重复计费。两个可选付费字段均缺失时，不输出
付费策略行，`paid_cost_status` 为 `not_supplied`。

## 固定队列与预算恒等式

`direct` 按 UTF-8 条目 ID 的 SHA256 升序排列。`loss`、`primary`、`norm`
按所提供分数降序排列，同分时按相同 SHA256 升序；哈希碰撞时再按 ID 确定顺序。
标签与成本都不能改变队列。输入数组的位置用于字段对齐，不代表审计优先级。

基础策略支付直接队列排序成本，或对应分数的扫描与排序成本。
`paid_direct`、`paid_loss`、`paid_primary`、`paid_norm` 还支付所提供的探针与
选择时间。**即使选择器回退到 direct，paid_direct 仍支付探针成本。**
重放只完成“前置成本加累计配对审计时间不超过 B”的最长前缀；遇到第一个无法负担的
条目即停止，不能跳过它去做后面较便宜的条目。JSON 小数按其十进制值精确比较。
若前置成本本身超过 B，K 为零；`required_seconds` 记录该不可行前置需求，
不代表一个合规运行实际花费了这么多时间。

发现事件是 `abs(risk_target-risk_source)`，风险改善和恶化都计入。
分别报告的 `risk_increases` 与 `risk_decreases` 相加等于 Y。
K 为完整配对审计量，p 为发现比例，Y=Kp；相对于同一案例的未付费 direct：

```text
delta_Y = Y_s - Y_0
        = K_s * (p_s - p_0) - (K_0 - K_s) * p_0
```

这是标准计数恒等式。第一项描述所选审计量下的精度富集，第二项描述审计量变化的
影响；K_s 大于 K_0 时，第二项可以为负。JSON 以精确有理数字符串保存这两项。
K_s=0 时 p_s 为 null，第一项采用计数形式 `Y_s-K_s*p_0` 延拓。
K_0=0 时 p_0 与分解的两项均为 null，但 K、Y 和 delta_Y 仍然保留。

精度盈亏阈值为 `Y_0/K_s`，K_s=0 时未定义。
`precision_threshold_gt_one` 表示当前完成量下即使精度为 1 也无法追平 direct。
严格增加发现数要求精度高于阈值。这些是所提供案例的算术描述，不保证未来收益，
也不构成统计效应判断。

## 独立的无标签锁定决策

`locked_decision(request)` 使用 `measurement-value-decision/v1`。
[英文文档中的完整 JSON 示例](README.md#a-separate-label-free-locked-decision)
使用的是合成接口数值，不是实验预测。

`context` 必须恰含 `model`、`pair`、正整数 `decode_cap` 与非负 `budget_seconds`。
`forecast.validity_scope` 必须与这四个字段完全一致。
预测须在外部冻结，并给出 `freeze_id`、`frozen=true` 和
`basis=full_cost_net_discoveries`：即已经扣除全部成本、应用预算截断后的预测发现数。
不能把本次重放的观察 Y 复制过来当作冻结预测。该接口不学习预测，也无法核验调用者
真正冻结预测的时间。

基线 `baseline_discoveries` 必须包含 direct、loss、uniform；付费候选
`paid_discoveries` 必须包含 direct、loss、primary、norm。
`uniform_action` 记录来源数据上固定选出的诊断动作；uniform 不是随机审计。
原始全来源记录中三个模型都选择 loss，所以其队列就是 loss 队列，可调用
`fixed_order(case, uniform_action)` 获取。其净预测仍作为独立基线输入保留。

最好的付费预测必须唯一，并至少高于 direct、loss、uniform 中最佳基线的 5%。
零基线要求至少预测增加 1 个发现。付费最优值并列或增益不足时优先 direct。
预测缺失、未冻结、失败、不含完整成本或超出有效范围时，返回
`insufficient_evidence`。控制诊断有效时，这些分支在探针前回到 `direct`，
探针后回到 `paid_direct`；并列或增益不足也遵守这一阶段区分。
预测的可选 `status` 默认是 `valid`。选择付费策略仍属于锁定预测，并不确认实际收益。

`phase=before_probe` 会拒绝 `control_diagnostics`、`incurred_costs` 及未知字段，
包括已经计算出的昂贵控制分数。`after_probe` 的新增字段示例为：

```json
{
  "phase": "after_probe",
  "incurred_costs": {"probe_seconds": 1.5, "selection_seconds": 0.5},
  "control_diagnostics": {
    "status": "valid",
    "validity_scope": {"model": "m", "pair": "p", "decode_cap": 8, "budget_seconds": 100},
    "features": {"x6": 0.2}
  }
}
```

上述数值仅为合成接口示例。探针后必须提供 `incurred_costs`，且恰含有限、非负的
`probe_seconds` 和 `selection_seconds`。每个探针后结果，包括所有回退结果，都会
保留这个实际已发生的成本账本及其总和 `incurred_seconds`。账本缺失或格式错误时
拒绝输入，不把未记录成本默认为零。外部提供的预测已经包含完整成本，决策函数不会
再扣一次账本，也不会重新估计预测。

读取诊断或比较预测之前，接口先将实际已发生的总成本 C 与预算 B 比较。
C 等于或大于 B 时，返回 `insufficient_evidence`，保留 `paid_direct` 身份，并设置
`further_evaluation_allowed=false`。此时的付费身份只记录已发生成本，不允许再启动
审计。刚好耗尽时 `budget_status=exhausted`，超出时为 `exceeded`。
`remaining_budget_seconds` 保存有符号余额 B-C，耗尽时为零、超支后为负；原始成本
账本与合计保持不变。该检查优先于 uniform 回退、控制诊断失败和有利预测。
余额为正时，`budget_status=available` 且 `further_evaluation_allowed=true`，
其他有效性检查仍然适用。

诊断对象必须恰含 `status`、`validity_scope`、`features`。状态必须为 `valid`，
范围必须与 context 一致，特征映射必须非空，名称非空且每个值都是有限数值标量。
布尔值、数字字符串、数组、NaN、无穷、失败状态与未知字段都不可用。
这个约定检查声明的特征可用性与数值输入，不构成 Pontryagin 证书。
探针后默认要求有效控制诊断。若外部冻结的预测确实不使用控制特征，可显式设置
`forecast.requires_control_diagnostics=false` 并省略诊断对象；但一旦附带无效
诊断对象，即使这样声明，也不会忽略它。

控制诊断无效或所需诊断缺失时，不进行发现数比较。如果来源固定动作有效，则返回
`fallback_uniform`，策略为 `paid_<uniform_action>`。有效动作声明要求：锁定预测
请求中 `freeze_id` 非空、`frozen=true`、范围匹配，且 `uniform_action` 属于允许
动作。这个回退使用冻结动作本身，不使用预测发现数。否则返回
`insufficient_evidence` 与 `paid_direct`。两条路径都保留实际成本；探针后的任何
回退都不能恢复成未付费 direct。

改变有限诊断值不会改写外部提供的预测。两种阶段都完全忽略可选的 `behavior` 字段，
因此增加或更改标签不可能改变决策。阶段只记录信息可用边界；调用者仍需执行真实的
获取与冻结协议。

## 理论来源与实际测量对象

理论引用固定为 **arXiv:2606.17762v3**。HTML 与正式 PDF 的部分编号不同，应同时
根据结果标题识别：

| 结果标题 | HTML / PDF 编号 | 作用 |
|---|---|---|
| [Finite-horizon Green certificate](https://arxiv.org/html/2606.17762v3#S3.Thmtheorem2) | 定理 3.2 / 3.2 | 从双曲性与缩放边界横截条件得到一致线性逆估计 |
| [Uniform reconstruction with smooth endpoint rows](https://arxiv.org/html/2606.17762v3#S4.Thmtheorem1) | 定理 4.1 / 4.1 | 在 Green 性质与正则条件下重建局部非线性分支 |
| [A posteriori existence and local uniqueness certificate](https://arxiv.org/html/2606.17762v3#S5.Thmtheorem3) | 命题 5.3 / 5.2 | 用残差、Jacobian 逆与邻域界检查局部存在唯一性 |
| [Exponential decay of sensitivity to the terminal reward](https://arxiv.org/html/2606.17762v3#S5.Thmtheorem9) | 定理 5.9 / 5.5 | 在相应条件下得到终端至初始的敏感性衰减 |

参见[该版本正式 PDF](https://arxiv.org/pdf/2606.17762v3)。这些结果处理局部驻定
Pontryagin 分支；要解释为最优解，还需要额外条件。

**T** 是理论中的控制时域，**L** 是生成长度上限，**B** 是墙钟审计预算，不能互换。
AdamW 对静态软提示的训练不会自动实例化论文的 Pontryagin 边值系统。
选择器的归一化 gold-choice Taylor 特征 `x6` 是**读出线性化误差**，不是 primary
诊断分数，也不是完整的 Pontryagin 驻定残差。primary 与 norm 的冻结 ridge 定义
见 [DATA.md](DATA.md)。当前记录没有验证双曲转移 M、边界矩阵，或后验 Jacobian
逆与邻域界。

理论提供带前提的数学结构；固定控制分数是经验替代量；成本重放属于操作测量层。
重放成功或 delta_Y 为正都不构成控制理论证书。
三个证据状态分别声明历史观察、锁定预测与独立确认。文件存在、坐标有效或校验和
匹配都不会自动升级证据；独立确认必须由独立协议与记录提供。

## 验证

```console
python -m pytest tests/test_measurement_value.py
```

聚焦测试覆盖付费前置成本、双向风险变化、固定队列同分规则、标签隔离、完整前缀
预算、零完成量、精确分解、无效输入、预测冻结范围、增益门槛及独立运行输出的确定性。
