# prompt_control_lab 🧪✨

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

`prompt_control_lab` is an open-source toolkit for prompt improvement, prompt guarding,
prompt evaluation, reproducibility, and control-oriented diagnostics. It starts simple:
paste one prompt, get a clearer and more token-conscious version. Then it scales up to
CLI reports, IDE/agent plugins, withheld evaluation, soft-to-hard checks, trajectory
diagnostics, and Riccati surrogate analysis. ٩(ˊᗜˋ*)و

> 📌 The repository is currently private, so public badge services may show zero or
> unavailable counts until the repository is made public.

Chinese documentation is available in [README.zh.md](README.zh.md).

## Quick Map 🗺️

Use this order if you are new:

1. **Just improve one prompt** → `pcl improve`
2. **Guard prompts before Claude Code / Cursor / Codex** → `pcl guard` + `plugins/`
3. **Generate one complete report** → `pcl analyze`
4. **Control every evaluation step** → `split → eval → stats → report → explain → gate`
5. **Run research diagnostics** → `soft-hard → trajectory → riccati → tv-soft`

In this README, **Quick Mode** means the integrated `pcl analyze` path, while
**Expert Mode** means the flexible command-by-command workflow. Simple first, expert later.

![prompt_control_lab workflow](docs/assets/workflow.svg)

The main idea is small and practical: do not trust one score alone. Keep the split, outputs,
statistics, explanations, diagnostics, and prompt rewrites as inspectable artifacts.

![prompt_control_lab artifacts](docs/assets/artifacts.svg)

## Install The CLI ⚙️

### 1. Clone the repository

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
```

If you already have the repository locally, just enter the repo folder.

### 2. Install the lightweight CLI

```bash
pip install -e .
```

With `uv`:

```bash
uv pip install -e .
```

### 3. Install development and research extras

Use this when you want tests plus optional scientific diagnostics:

```bash
pip install -e ".[dev,research]"
```

With `uv`:

```bash
uv pip install -e ".[dev,research]"
```

### 4. Check that the CLI works

```bash
pcl --help
pcl improve --prompt "Answer the user question."
```

Expected result: `pcl --help` lists commands, and `pcl improve` prints an optimized prompt
plus estimated token cost.

## Install IDE / CLI Plugins And Skills 🧩

All integrations are thin adapters around the same stable command:

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced --json
```

For hooks and wrappers, use stdin:

```bash
echo "Fix this bug" | pcl guard --stdin --profile coding --json
```

### Claude Code Hook 🪝

Claude Code supports `UserPromptSubmit` hooks. This repository includes a working hook:

```text
plugins/claude-code/hooks/prompt_guard.py
```

Install steps:

1. Install the CLI first with `pip install -e .`.
2. Open your Claude Code settings file.
3. Add a `UserPromptSubmit` hook like this:

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

4. Adjust the path to your local checkout.
5. Test the hook manually:

```powershell
'{"hook_event_name":"UserPromptSubmit","prompt":"Fix this bug"}' |
  python plugins\claude-code\hooks\prompt_guard.py --mode suggest --profile coding
```

Expected result: JSON with `additionalContext`. In `--mode gate`, risky prompts can return
`decision: "block"` with a clear reason. (ง •̀_•́)ง

More details: [plugins/claude-code](plugins/claude-code).

### Cursor Rules 🖱️

Cursor is best supported today through rules plus explicit `pcl guard` commands.

Install steps inside a Cursor project:

```powershell
New-Item -ItemType Directory -Force .cursor\rules
Copy-Item plugins\cursor\rules\prompt_control_lab.mdc .cursor\rules\prompt_control_lab.mdc
```

Then ask Cursor to follow the rule, or run this before sending an expensive prompt:

```bash
pcl guard --prompt "Refactor this module" --profile coding --token-mode balanced
```

Expected result: Cursor has a project rule that nudges agents to use `pcl guard` for vague,
broad, risky, or expensive prompts. This is not full prompt interception yet; it is a practical
rules workflow.

More details: [plugins/cursor](plugins/cursor).

### Codex Skill 🛠️

The repository includes a local Codex skill template:

```text
plugins/codex/skills/prompt_control_lab/SKILL.md
```

Install steps on Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills\prompt_control_lab"
Copy-Item -Recurse -Force .\plugins\codex\skills\prompt_control_lab\* "$env:USERPROFILE\.codex\skills\prompt_control_lab\"
```

Then restart Codex so it can discover the skill. Use it when you want Codex to guard a prompt
before doing expensive work:

```text
$prompt_control_lab Guard this prompt before implementation: "Build the feature"
```

Expected result: Codex should consult the skill instructions and use `pcl guard` before
turning the prompt into a larger coding task. (｡•̀ᴗ-)✧

More details: [plugins/codex](plugins/codex).

### Generic Shell Wrapper 🐚

Any CLI tool can use the JSON interface:

```bash
echo "Write tests for this feature" | pcl guard --stdin --profile coding --json
```

Use the `improved_prompt` field as the prompt sent to your agent, or use `action=block` as
a stop signal in gate mode.

## Feature Path: Simple To Expert 🚀

The sections below are ordered from direct, friendly workflows to more flexible research tools.

### 1. `pcl improve`: rewrite one prompt directly ✨

Operation:

```bash
pcl improve --prompt "Answer the user question."
```

Token-conscious operation:

```bash
pcl improve --prompt "Answer the user question." --token-mode aggressive --max-tokens 80
```

Result:

- optimized prompt in the terminal
- estimated token count before and after rewriting
- with `--out runs/improve`: `improved_prompt.txt`, `prompt_improvement.json`, `prompt_diff.md`

What it means:

Use this when you only have a prompt string. It adds task goal, output-format constraints,
stability rules, and optional token-budget pressure without calling any external model.

### 2. `pcl guard`: protect prompts before IDE or CLI agents use them 🛡️

Operation:

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced --json
```

Gate operation:

```bash
echo "Answer the user question." | pcl guard --stdin --mode gate --max-tokens 80 --json
```

Result:

- `action`: `suggest`, `auto`, or `block`
- `risk_level`: `low`, `medium`, or `high`
- `improved_prompt`: guarded prompt
- `token_report`: estimated token cost
- `reasons`: why the guard suggested or blocked

What it means:

Use this before Claude Code, Cursor, Codex, or a shell wrapper spends tokens. It catches vague,
over-budget, or underspecified prompts early.

### 3. `pcl analyze`: one command, one report 📦

Operation:

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

Result:

- `runs/quick/splits.json`
- `runs/quick/baseline/metrics.json`
- `runs/quick/candidate/metrics.json`
- `runs/quick/stats.json`
- `runs/quick/explanation.json`
- `runs/quick/report.md`
- `runs/quick/report.html`

What it means:

This is the easiest full evaluation path. It answers: did the candidate improve, is the
evidence reliable, did any task slice regress, and what should be checked next?

### 4. `pcl init`: create a runnable example 🌱

Operation:

```bash
pcl init --path demo
cd demo
```

Result:

- `examples/tasks.jsonl`
- `examples/predictions_baseline.jsonl`
- `examples/predictions_candidate.jsonl`
- `promptcontrol.example.yaml`

What it means:

These files show the minimal input format: task `id`, `input`, `expected`, `slice`, and model
`output` records.

### 5. `pcl report`, `pcl explain`, `pcl gate`: read and decide ✅

Operations:

```bash
pcl report --run runs/quick --title "Candidate Prompt Report"
pcl explain --run runs/quick --level plain
pcl gate --run runs/quick --policy examples/gate.policy.yaml
```

Result:

- `report.md` / `report.html`
- `explanation.json`
- `gate_result.json`

What it means:

These commands turn artifacts into decisions: keep the prompt, review it, or hold it.

### 6. Expert evaluation: `split → eval → stats` 🧠

Operations:

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
pcl eval --data examples/tasks.jsonl --predictions examples/predictions_candidate.jsonl --out runs/candidate --method candidate
pcl stats --baseline runs/baseline/predictions.jsonl --candidate runs/candidate/predictions.jsonl --out runs/candidate/stats.json
```

Result:

- reproducible train/val/withheld split
- scored predictions and slice metrics
- paired confidence intervals, permutation p-values, and Holm-adjusted p-values

What it means:

This is for users who want full control over protocol hygiene and statistical comparison.

### 7. Deployment and research diagnostics 🔬

Soft-to-hard risk:

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

Hidden-state trajectory:

```bash
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
```

Riccati surrogate:

```bash
pcl riccati --matrices surrogate_mats.npz --out runs/candidate/diagnostics
```

Time-varying soft-control lane:

```bash
pcl tv-soft --predictions method_predictions.jsonl --out runs/candidate/diagnostics
```

What it means:

These commands move beyond output scores. They inspect soft-to-hard deployment risk,
hidden-state drift, fitted surrogate stability, and whether time-varying gains look like
temporal structure or just extra capacity.

![prompt_control_lab diagnostics](docs/assets/diagnostics.svg)

## Ecosystem Positioning 🌱

`prompt_control_lab` complements prompt optimizers, eval tools, and observability platforms.
Its focus is the diagnostic layer: withheld protocol, paired statistics, soft-to-hard risk,
hidden trajectory diagnostics, control surrogates, and prompt-input guarding.

Adjacent examples:

- DSPy, TextGrad, and OpenPrompt focus on prompt/program optimization or prompt-learning workflows.
- promptfoo and DeepEval focus on LLM evaluation, tests, red-team checks, and metrics.
- Langfuse, LangSmith, and Phoenix focus on traces, observability, experiments, and app-level evaluation.
- `prompt_control_lab` adds reproducible protocol hygiene, statistical comparison, deployment-risk checks, internal trajectory diagnostics, and prompt-input guarding.

![prompt_control_lab ecosystem position](docs/assets/ecosystem.svg)

![prompt_control_lab comparison matrix](docs/assets/comparison_matrix.svg)

![prompt_control_lab innovation stack](docs/assets/innovation_stack.svg)

## Who It Is For 👥

- People who want a clearer prompt quickly.
- Developers who want Claude Code, Cursor, or Codex prompts guarded before execution.
- LLM teams that need local prompt regression reports.
- Researchers comparing prompt optimizers with clean train/val/withheld protocols.
- Soft-prompt researchers checking soft-to-hard deployment risk.
- Interpretability/control researchers studying trajectories and surrogate stability.

## Documentation 📚

- [Background](docs/background.en.md)
- [Users](docs/users.en.md)
- [Tutorial](docs/tutorial.en.md)
- [Artifacts](docs/artifacts.en.md)
- [Innovation and Contribution](docs/innovation.en.md)
- [Plugin adapters](plugins/)

## License 📄

Apache-2.0
