# Record provenance and licensing / 数据来源与许可

`source_records.json` is a byte-preserving copy of the compact historical fixture
supplied by the researcher for this case. Its SHA256 is
`eafacdb018e50f40199012e6d422599bcd92477d6e34089f53e5ca45fbdd2257`.
It contains 54 model/pair coordinates, each with 400 aligned item IDs, fixed scores,
binary risk labels, and recorded costs: 19 ministral pairs, 19 granite pairs, and
16 qwen35 pairs. The condition is native decode cap 8 with the strict parser.

`source_records.json` 是研究者为本案例提供的紧凑历史输入的逐字节副本。
文件包含 54 个模型与配对坐标，每个坐标含 400 个对齐条目 ID、固定分数、二元风险
标签和记录成本：ministral 19 对、granite 19 对、qwen35 16 对。
条件为原生生成长度上限 8 与严格解析器。

The score definitions retained by the source implementation are:

| Array | Frozen source definition |
|---|---|
| `loss` | Absolute right-minus-left teacher-forced gold-answer loss difference; larger predicts risk change |
| `primary` | Original fixed ridge diagnostic on empirical state/readout features from `feature_vector(left_state, right_state, left_readout_gradient, basis, prompt_distance, tail_energy)` |
| `norm` | Separately fixed ridge using left/right state norms, prompt distance, and tail energy; its first two feature-vector entries are zero |

Coefficients, standardization, and ranking direction were frozen in calibration.
The module consumes the resulting fixed scores; this fixture is not a reconstruction
of score fitting. The normalized gold-choice Taylor readout error is the selector’s
control feature `x6`, **not the primary diagnostic score**. These definitions follow
the retained `selection_runtime.py::immutable_diagnostic` and
`prompt_control_independent_io::feature_vector` implementations identified by the
researcher.

来源实现中的 `loss` 是右侧减左侧的 teacher-forced 正确答案损失差的绝对值；
数值越大越倾向预测风险变化。`primary` 是基于经验状态与读出特征的原始固定 ridge
诊断，使用 `feature_vector(left_state, right_state, left_readout_gradient, basis,
prompt_distance, tail_energy)`。`norm` 是独立固定的 ridge，使用左右状态范数、
提示距离和尾部能量，其特征向量的前两项为零。
系数、标准化与排序方向均在校准阶段冻结；这里消费固定分数，不重新拟合评分器。
归一化 gold-choice Taylor 读出误差是选择器的控制特征 `x6`，**不是 primary 分数**。
定义对应研究者指出的保留实现 `selection_runtime.py::immutable_diagnostic` 与
`prompt_control_independent_io::feature_vector`。

The packaged numeric records and synthetic fixture are distributed under the
repository’s [Apache-2.0 license](../../../LICENSE). They include no question text,
prompt text, model weights, or generated answer text. Underlying models and datasets
retain their own licenses; this package does not relicense or redistribute them.

这里的数值记录与合成输入按仓库的 [Apache-2.0 许可](../../../LICENSE)分发。
文件不包含问题文本、提示文本、模型权重或生成回答。底层模型与数据集保留其各自的
许可，本包不重新授权或分发这些内容。

`probe_seconds` deliberately contains the original combined probe, aggregation,
and selector CPU timing interval; `selection_seconds=0` prevents counting the same
interval twice. Scan and sorting costs remain separate. Array positions preserve
alignment; the replay constructs audit queues independently from the fixed scores
and item IDs. Input `provenance.input_id` is a supplied record identifier; the
file SHA256 above independently identifies the delivered bytes.

`probe_seconds` 特意包含原始探针、聚合和选择器 CPU 的合并计时区间；
`selection_seconds=0` 避免重复计费。扫描与排序成本单列。
数组位置保持字段对齐；重放根据固定分数与 ID 独立构建队列。
输入中的 `provenance.input_id` 是来源记录标识；上面的文件 SHA256 标识实际交付字节。

The following unpaid direct/loss means are checked against the supplied receipt:

| Model / 模型 | Pairs / 配对数 | Direct mean Y | Loss mean Y |
|---|---:|---:|---:|
| ministral | 19 | 60.21052631578947 | 37.15789473684210 |
| granite | 19 | 67.68421052631580 | 32.94736842105263 |
| qwen35 | 16 | 43.125 | 32.25 |

`historical_replay/` is deterministic replay output, not an independent experiment.
`synthetic_test.json` contains invented four-item values solely for testing.
Neither adding complete labels nor matching these checksums upgrades the declared
`historical_observation` evidence status. Locked predictions and independent
confirmation require their own separately supplied records.

`historical_replay/` 是确定性重放输出，不是独立实验。
`synthetic_test.json` 的四条目数值专用于测试，不属于实证证据。
增加完整标签或匹配校验和都不会升级 `historical_observation` 证据状态。
锁定预测与独立确认需要各自单独提供的记录。
