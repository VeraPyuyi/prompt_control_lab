# 五分钟快速上手

这份快速上手不需要 API key、模型下载或 Agent 执行，也能生成一份完整的本地报告。

## 1. 安装当前源码

```bash
python -m pip install -e ".[ui]"
```

得到什么：可以使用 `pcl` 命令和可选的本地仪表盘。

## 2. 一条命令生成 Demo

```bash
pcl quickstart --out demo --open-report
```

得到什么：`demo/` 中包含固定数据、baseline/candidate 预测、可复现 split、指标、配对统计、门禁结果、解释和 HTML 报告。

说明什么：这条命令验证完整 artifact 流程能够运行。它使用合成 fixture，不证明某个 Prompt 在所有任务上都更好。

## 3. 查看决策

打开 `demo/runs/quick/report.html`，也可以运行：

```bash
pcl ui --runs demo/runs --language zh
```

按顺序回答四个问题：

1. 观察到了什么？
2. 这些证据可以解释什么？
3. 不能证明什么？
4. 下一步应该做什么？

## 4. 接入真实证据

```bash
pcl evidence scan --root /path/to/evidence --profile prompt-reach-v2 --out manifest.json
pcl evidence import --manifest manifest.json --out runs/prompt-reach-v2 --portable
```

扫描器只读取允许的结构化证据并记录哈希，不会执行来源实验脚本，也不会反序列化不可信模型 checkpoint。

比较 checkpoint 请继续阅读[后训练说明](posttraining.zh.md)；接入 Agent 生命周期请阅读 [DeepSeek Harness 说明](deepseek_harness.zh.md)。
