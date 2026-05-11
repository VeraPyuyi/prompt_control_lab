# prompt_control_lab 🧪✨

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

`prompt_control_lab` 是一个开源工具包，用于 prompt 优化、prompt 输入守护、
prompt 评测、复现和控制论诊断。它可以从最简单的“一句话 prompt 改写”开始，
逐步扩展到 CLI 报告、Claude Code / Cursor / Codex 插件、withheld 评测、
soft-to-hard 风险、hidden-state trajectory 和 Riccati surrogate 分析。٩(ˊᗜˋ*)و

> 📌 当前仓库还是 private，公开徽章服务可能暂时显示 0 或无法显示真实统计；
> 仓库公开后，stars、forks 和 watching 徽章会更自然地展示出来。

English documentation is available in [README.md](README.md).

## 快速地图 🗺️

如果你第一次使用，建议按这个顺序看：

1. **只想直接优化一个 prompt** → `pcl improve`
2. **想在 Claude Code / Cursor / Codex 输入前守护 prompt** → `pcl guard` + `plugins/`
3. **想一键生成完整分析报告** → `pcl analyze`
4. **想专业控制每一步评测** → `split → eval → stats → report → explain → gate`
5. **想做研究诊断** → `soft-hard → trajectory → riccati → tv-soft`

![prompt_control_lab 工作流](docs/assets/workflow.zh.svg)

核心思想很直白：不要只相信一个分数。把切分、输出、统计、解释、诊断和 prompt
改写都留下来，方便复查和复现。

![prompt_control_lab 产物结构](docs/assets/artifacts.zh.svg)

## 安装 CLI ⚙️

### 1. 克隆仓库

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
```

如果你已经有本地仓库，直接进入仓库目录即可。

### 2. 安装轻量 CLI

```bash
pip install -e .
```

使用 `uv`：

```bash
uv pip install -e .
```

### 3. 安装开发和研究诊断依赖

如果你要跑测试，或者使用 `soft-hard`、`trajectory`、`riccati` 等研究诊断命令：

```bash
pip install -e ".[dev,research]"
```

使用 `uv`：

```bash
uv pip install -e ".[dev,research]"
```

### 4. 检查 CLI 是否可用

```bash
pcl --help
pcl improve --prompt "回答下面的问题"
```

预期结果：`pcl --help` 能看到命令列表，`pcl improve` 会输出优化后的 prompt 和
estimated token 成本。

## 安装 IDE / CLI 插件和 Skills 🧩

所有 IDE / CLI 集成都围绕同一个稳定命令：

```bash
pcl guard --prompt "修复这个 bug" --profile coding --token-mode balanced --json
```

给 hook 或 wrapper 使用时，推荐走 stdin：

```bash
echo "修复这个 bug" | pcl guard --stdin --profile coding --json
```

### Claude Code Hook 🪝

Claude Code 支持 `UserPromptSubmit` hook。本仓库已经提供可运行的 hook：

```text
plugins/claude-code/hooks/prompt_guard.py
```

安装步骤：

1. 先运行 `pip install -e .` 安装 CLI。
2. 打开你的 Claude Code settings 文件。
3. 加入下面的 `UserPromptSubmit` hook：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"D:/path/to/prompt_control_lab/plugins/claude-code/hooks/prompt_guard.py\" --mode suggest --profile coding --token-mode balanced --max-tokens 300"
          }
        ]
      }
    ]
  }
}
```

4. 把路径改成你的本地仓库路径。
5. 手动测试 hook：

```powershell
'{"hook_event_name":"UserPromptSubmit","prompt":"Fix this bug"}' |
  python plugins\claude-code\hooks\prompt_guard.py --mode suggest --profile coding
```

预期结果：输出包含 `additionalContext` 的 JSON。使用 `--mode gate` 时，高风险 prompt
可以返回 `decision: "block"` 和阻断原因。(ง •̀_•́)ง

更多说明见 [plugins/claude-code](plugins/claude-code)。

### Cursor Rules 🖱️

Cursor 当前最适合用 rules + 显式 `pcl guard` 命令接入。

在 Cursor 项目中安装：

```powershell
New-Item -ItemType Directory -Force .cursor\rules
Copy-Item plugins\cursor\rules\prompt_control_lab.mdc .cursor\rules\prompt_control_lab.mdc
```

然后在发送高成本或模糊 prompt 前运行：

```bash
pcl guard --prompt "重构这个模块" --profile coding --token-mode balanced
```

预期结果：Cursor 项目里会有一条规则，提醒 agent 遇到模糊、宽泛、高风险或高成本
prompt 时先使用 `pcl guard`。这还不是 Cursor 的全自动输入拦截，但已经是可用的
项目级工作流。

更多说明见 [plugins/cursor](plugins/cursor)。

### Codex Skill 🛠️

本仓库提供了一个本地 Codex skill 模板：

```text
plugins/codex/skills/prompt_control_lab/SKILL.md
```

Windows PowerShell 安装：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills\prompt_control_lab"
Copy-Item -Recurse -Force .\plugins\codex\skills\prompt_control_lab\* "$env:USERPROFILE\.codex\skills\prompt_control_lab\"
```

然后重启 Codex，让它重新发现 skill。使用时可以这样说：

```text
$prompt_control_lab 请先守护这个 prompt 再开始实现："实现这个功能"
```

预期结果：Codex 会根据 skill 说明优先调用 `pcl guard`，先整理 prompt，再进入更大的
实现任务。(｡•̀ᴗ-)✧

更多说明见 [plugins/codex](plugins/codex)。

### 通用 Shell Wrapper 🐚

任何 CLI agent 都可以使用 JSON 接口：

```bash
echo "给这个功能写测试" | pcl guard --stdin --profile coding --json
```

你可以把 `improved_prompt` 作为真正发给 agent 的 prompt；如果是 gate 模式，也可以把
`action=block` 当作停止信号。

## 功能路径：从简单到专业 🚀

下面的功能顺序是从“最直白、最高度集成”到“更专业、更灵活”。

### 1. `pcl improve`：直接改写一个 prompt ✨

操作：

```bash
pcl improve --prompt "回答下面的问题"
```

控制 token 成本：

```bash
pcl improve --prompt "回答下面的问题" --token-mode aggressive --max-tokens 80
```

得到：

- 终端输出优化后的 prompt
- 改写前后的 estimated token 数
- 加上 `--out runs/improve` 后会写出 `improved_prompt.txt`、`prompt_improvement.json`、`prompt_diff.md`

说明什么问题：

如果你只有一段 prompt 字符串，这就是最简单入口。它会补充任务目标、输出格式约束、
稳定性要求，并且可以按 token 预算压缩措辞。

### 2. `pcl guard`：在 IDE 或 CLI agent 使用前守护 prompt 🛡️

操作：

```bash
pcl guard --prompt "修复这个 bug" --profile coding --token-mode balanced --json
```

Gate 操作：

```bash
echo "回答用户问题" | pcl guard --stdin --mode gate --max-tokens 80 --json
```

得到：

- `action`：`suggest`、`auto` 或 `block`
- `risk_level`：`low`、`medium` 或 `high`
- `improved_prompt`：守护后的 prompt
- `token_report`：estimated token 成本
- `reasons`：为什么建议或阻断

说明什么问题：

在 Claude Code、Cursor、Codex 或 shell wrapper 真正花 token 前，先检查 prompt 是否
太模糊、超预算或缺少关键约束。

### 3. `pcl analyze`：一个命令生成完整报告 📦

操作：

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

得到：

- `runs/quick/splits.json`
- `runs/quick/baseline/metrics.json`
- `runs/quick/candidate/metrics.json`
- `runs/quick/stats.json`
- `runs/quick/explanation.json`
- `runs/quick/report.md`
- `runs/quick/report.html`

说明什么问题：

这是最简单的完整评测路径。它会回答 candidate 是否更好、证据是否可靠、有没有任务
slice 退化、下一步应该检查哪里。

### 4. `pcl init`：生成可运行示例 🌱

操作：

```bash
pcl init --path demo
cd demo
```

得到：

- `examples/tasks.jsonl`
- `examples/predictions_baseline.jsonl`
- `examples/predictions_candidate.jsonl`
- `promptcontrol.example.yaml`

说明什么问题：

这些文件展示最小输入格式：任务 `id`、`input`、`expected`、`slice`，以及模型
`output`。

### 5. `pcl report`、`pcl explain`、`pcl gate`：阅读并做决定 ✅

操作：

```bash
pcl report --run runs/quick --title "Candidate Prompt Report"
pcl explain --run runs/quick --level plain
pcl gate --run runs/quick --policy examples/gate.policy.yaml
```

得到：

- `report.md` / `report.html`
- `explanation.json`
- `gate_result.json`

说明什么问题：

这些命令把产物变成结论：保留 prompt、继续复查，或者暂时不要使用。

### 6. 专家评测：`split → eval → stats` 🧠

操作：

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
pcl eval --data examples/tasks.jsonl --predictions examples/predictions_candidate.jsonl --out runs/candidate --method candidate
pcl stats --baseline runs/baseline/predictions.jsonl --candidate runs/candidate/predictions.jsonl --out runs/candidate/stats.json
```

得到：

- 可复现的 train/val/withheld 切分
- 每条样本和每个 slice 的分数
- paired confidence interval、permutation p-value、Holm-adjusted p-value

说明什么问题：

适合需要精细控制评测协议和统计比较的研究者或工程团队。

### 7. 部署和研究诊断 🔬

Soft-to-hard 风险：

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

Hidden-state trajectory：

```bash
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
```

Riccati surrogate：

```bash
pcl riccati --matrices surrogate_mats.npz --out runs/candidate/diagnostics
```

Time-varying soft-control lane：

```bash
pcl tv-soft --predictions method_predictions.jsonl --out runs/candidate/diagnostics
```

说明什么问题：

这些命令不只看输出分数，还检查 soft prompt 转 hard prompt 的风险、内部轨迹漂移、
代理控制模型稳定性，以及 time-varying prompt 的收益是否更像来自时序结构。

![prompt_control_lab 研究诊断](docs/assets/diagnostics.zh.svg)

## 生态定位 🌱

`prompt_control_lab` 不替代 prompt optimizer、eval 工具或 observability 平台。它补的是
诊断层：withheld 协议、paired statistics、soft-to-hard 风险、hidden trajectory、
control surrogate，以及 prompt 输入守护。

![prompt_control_lab 生态位置](docs/assets/ecosystem.zh.svg)

![prompt_control_lab 能力对比矩阵](docs/assets/comparison_matrix.zh.svg)

![prompt_control_lab 创新栈](docs/assets/innovation_stack.zh.svg)

## 面向谁 👥

- 只想快速得到更好 prompt 的普通用户。
- 希望 Claude Code、Cursor、Codex 在执行前先整理 prompt 的开发者。
- 需要本地 prompt regression report 的 LLM 工程团队。
- 需要干净 train/val/withheld 协议的 prompt optimization 研究者。
- 需要 soft-to-hard 部署风险分析的 soft prompt 研究者。
- 研究 trajectory、turnpike-like 行为和 Riccati surrogate 的解释性 / 控制方向研究者。

## 文档 📚

- [使用背景](docs/background.zh.md)
- [面向群体](docs/users.zh.md)
- [一步一步教程](docs/tutorial.zh.md)
- [产物说明](docs/artifacts.zh.md)
- [创新点和贡献](docs/innovation.zh.md)
- [插件适配](plugins/)

## License 📄

Apache-2.0
