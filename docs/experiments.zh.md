# 评测、优化与解释

PromptControlLab 0.3 在本地运行。wheel 已包含 React 界面与样例，使用时不需要 Node。安装 wheel 及 `[ui,optimize,research]` 可选依赖后运行：

```bash
pcl ui --runs runs --language zh
```

## 第一次比较

1. 在“评测与优化”中点击“先体验离线样例”。它使用预置合成输出，没有模型调用。
2. 分别查看比较条件、效果、配对完成数与平均变化。完成运行本身不等于改进有效。
3. 查看逐条输出，下载可读报告、CSV 或完整结果包。
4. 换成自己的任务：编辑两版提示词，上传 CSV、JSONL 或 JSON，映射编号、输入与期望答案列。编号必须唯一；相关题目可共享 `meta.group_id`。
5. 选择实际评测、导入结果或自动优化。实际调用需要明确的提供方和模型名；凭据可来自环境变量或仅存于当前本地服务内存。

五分钟完成离线流程是设计目标。五名首次使用者的实测记录见[真人试用方案](releases/usability-trial.md)，未用助手自评分替代。

## 实际评测与导入

支持 OpenAI、Anthropic、Gemini、DeepSeek、Qwen、Kimi 和 OpenAI 兼容端点。远端 API 使用 HTTPS，本机回环地址可用 HTTP。Anthropic 兼容转发服务可显式选择 Bearer 鉴权。契约测试与真实模型调用验收分别记录。

确定性评分包括精确匹配、包含答案、分类准确率、数值容差和格式错误。格式错误按越低越好判断。缺失输出和服务错误不会被当成质量零分；已观察到的错误答案或无法解析的输出属于模型质量结果。逐条记录在可用时保留耗时、token 和失败信息。

支持 PCL 自身 JSON/CSV 与已有 Promptfoo、DeepEval、Langfuse、LangSmith、prompt-optimizer 导入器。多版本导出需要选择对应提示词或比较侧。提示词资产进入编辑与评测；显式的 `aggregate_metrics` 只做描述性比较，不生成成对统计。CSV 做了电子表格公式防护；无损复用请用 `records.json`。

## 有预算上限的 GEPA 搜索

通过 `optimize` 可选依赖安装 `gepa==0.1.4`。默认最多五轮、每轮一个提案，连续两轮验证集无提升时停止。反思默认使用所选评测模型，也可明确指定；界面将单次反思输出上限设为 512 token。

训练数据用于生成修改建议，验证数据用于选择候选。引擎锁定最终候选后，才读取并评测留出部分。共享输入或分组标识的题目会留在同一数据分区。GEPA 自带评估缓存已关闭，PCL 按阶段、题目和配置保存结果，避免训练与验证位置编号混淆。

评测和反思共用调用次数、输出 token 与时间预算，并预留最终比较额度。金额预算需要输入、输出单价，所有金额使用同一币种；模型单价不同时配置保守的共用单价。缺失用量与未知费用会明确保留。预算或时间停止可能导致最终比较不完整，结果页会如实显示。

搜索保存候选文本、来源关系、验证分数、成本与停止原因，不会自动覆盖原提示词。搜索文本最多 100,000 字符，至多含一个 `{input}`；未使用该占位符时会追加题目输入。

## 进度、取消、重试与恢复

每个结果目录默认只运行一个实验，最多两个模型请求并发。取消后停止新请求并保留完成项；已发出的请求可能稍后返回。进程退出时结果不明的请求会保留为“不确定”，其预算预留也会保留。

恢复会复用完成记录并继续未完成部分。“重试明确被拒绝的请求”需要显式选择，只重试确认未执行的拒绝或本地配置错误；超时、中断及响应损坏的请求不会自动重发。重启服务后需重新提供内存凭据，恢复时沿用记录中的环境变量引用名。

```bash
pcl experiment import --example --runs runs
pcl experiment run --config my-experiment.json --runs runs
pcl experiment optimize --config my-search.json --runs runs
pcl experiment status --runs runs
pcl experiment cancel EXPERIMENT_ID --runs runs
pcl experiment resume EXPERIMENT_ID --runs runs --retry-failed
pcl experiment replay --bundle experiment.zip --out replayed
```

配置中的数据文件路径相对于配置文件解析。结果包使用相对路径；重放不调用模型，分别核对文件完整性、数值重算和证据范围。身份哈希用于匹配内容，不等于时间顺序或独立性证明。

## 科研工具与旧工作流

科研工具页提供行为读出敏感性、控制响应画像、测量价值、迁移预测与结果重放五类离线工具，以及双语 HTML、JSON、CSV 和 SVG。响应画像需要保存的内部测量；闭源 API 用户仍能完成基础评测与成本分析。输入见[科研样例](../examples/research-tools/README.zh.md)。

Change Review、checkpoint 图表、trace 导入与原命令继续保留。快捷分析现会实际评测留出编号；`pcl analyze --evaluation-scope all` 显式请求全数据比较。旧报告的 `pass/clean` 含义不变，新实验使用 `comparison-assessment/v1`。

本地 API 只执行明确的实验操作，不接受任意命令。写操作需本机会话，公开演示保持只读。密钥应放入专用凭据输入框或环境变量，不应写入配置、提示词和数据集。
