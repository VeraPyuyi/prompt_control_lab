# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evaluation for prompt optimization.**

`prompt_control_lab` is the open-source toolkit for the Prompt-Engineering-Optimal-Control project.
Its research core turns prompt optimization experiments into reproducible splits, paired statistics,
soft-to-hard deployment diagnostics, hidden-state trajectory probes, Riccati surrogate checks, and
time-varying soft-control comparisons.

It also includes an applied engineering layer for AI coding agents: prompt policy guardrails, public
model provenance, diff audit, PR summaries, plugin templates, and a local UI. Those features are
downstream applications of the research workflow, not the main identity of the project.

Python package name: `promptcontrollab`. Repository and product name: `prompt_control_lab`.

Chinese documentation is available in [README.zh.md](README.zh.md).

## Start In 2 Minutes

```bash
# 0. Install the walkthrough extras.
pip install -e ".[research,ui]"

# 1. Run a paper-style research diagnostics demo.
pcl research-demo --out runs/research-demo

# 2. Re-run the unified diagnostics report from demo inputs.
pcl diagnose --run runs/research-demo

# 3. Create a reproducible prompt-evaluation demo project.
pcl init --path demo
cd demo

# 4. Run the tri-split evaluation/statistics/report pipeline.
pcl analyze --config promptcontrol.example.yaml --out runs/quick

# 5. Open the local dashboard for reports and research diagnostics.
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

What you get: split hash, train/validation/withheld hygiene, predictions, metrics, paired
statistics, comparison-validity audit, explanation, gate result, report artifacts, and a local UI.
No prompts, code, or artifacts are uploaded by the dashboard.

## Why This Exists

Most prompt optimization reports still collapse the experiment to one output score. That hides
important questions:

- Was train/validation/withheld separation clean?
- Is the candidate prompt better under paired uncertainty, or just lucky on one split?
- Does a learned soft prompt survive hard-token projection?
- Did the hidden-state trajectory become more stable or more drifting?
- Does a time-varying prompt help because of temporal structure or just extra capacity?
- Is a fitted Riccati surrogate internally stable, and what are the limits of that claim?

`prompt_control_lab` exists to make those questions concrete, reproducible, and inspectable.

![prompt_control_lab workflow](docs/assets/workflow.svg)

## Research Core

These are the paper-derived capabilities that drive the project:

| Paper concept | CLI / artifact | What it explains |
|---|---|---|
| Tri-split withheld protocol | `pcl split`, `pcl analyze`, `splits.json` | Whether prompt evaluation avoided train/validation/withheld leakage. |
| Paired statistical comparison | `pcl stats`, `stats.json` | Whether a prompt change is reliable under bootstrap CI, permutation p-value, and Holm correction. |
| Prompt-only comparison validity | `pcl validity`, `comparison_validity.json` | Whether a baseline/candidate result is clean prompt-only evidence rather than a model, split, or metric confound. |
| Prompt optimization evidence card | `pcl evidence-card`, `evidence_card.md/json` | One compact audit card for protocol hygiene, paired stats, comparison validity, deployment risk, hidden-state diagnostics, Riccati, and time-varying control evidence. |
| Prompt optimization claim check | `pcl claim-check`, `claim_check.md/json` | Whether the recorded evidence supports a paired, partial-research, or full-research claim. |
| Soft-to-hard deployment gap | `pcl soft-hard`, `diagnostics/soft_hard.json` | Whether soft prompt gains survive nearest-token hard projection. |
| HuggingFace hidden-state extraction | `pcl extract-hidden`, `hidden_states.npz` | Turns open-model prompts into trajectory-ready hidden-state artifacts. |
| Hidden-state trajectory diagnostic | `pcl trajectory`, `diagnostics/trajectory.json` | Whether internal trajectories show drift, decay, or turnpike-like signals. |
| Riccati surrogate diagnostic | `pcl riccati`, `diagnostics/riccati.json` | Whether a fitted finite-dimensional surrogate is self-consistent and stable. |
| Time-varying soft-control lane | `pcl tv-soft`, `diagnostics/tv_soft.json` | Whether time-varying gains look like temporal structure rather than parameter capacity. |

To experience the whole research stack without preparing model artifacts first, run
`pcl research-demo --out runs/research-demo`. To apply the same unified diagnostic report to your
own soft prompts, hidden states, matrices, and method predictions, use `pcl diagnose`. Research
demo now also writes a synthetic tri-split, baseline/candidate scored runs, paired statistics,
prompt-only comparison validity, `evidence_card.json` / `evidence_card.md`, and
`claim_check.json`. The local UI surfaces a research evidence map, the evidence card, and a claim
evidence ladder in the Research Overview, so reviewers can see whether the bundle has protocol
evidence, diagnostics, and claim support for paired, partial-research, or full-research claims.

See [Research From The Paper](docs/research_from_paper.en.md) for the direct mapping from paper
ideas to commands, inputs, outputs, and interpretation boundaries.

## Ecosystem Bridge

If you already use Promptfoo, Langfuse, or LangSmith for prompt/model evaluation and
observability, keep them. `prompt_control_lab` can import their exported artifacts and add the
research diagnostics layer on top:

```bash
# Fast all-tools demo with bundled Promptfoo/Langfuse/LangSmith-style exports.
pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo

# Then open runs/ecosystem-demo/README.md, research_diagnostics.md,
# and each bridge_summary.md.

promptfoo eval --output results.json

# One-command bridge: import baseline/candidate exports, compare them,
# then write stats, comparison validity, evidence card, and report artifacts.
pcl evidence-from \
  --tool promptfoo \
  --baseline-input results.json \
  --candidate-input results.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --provider openai:gpt-4o-mini-20260601 \
  --split-hash eval-split-2026-06 \
  --out runs/from-promptfoo-evidence

# Lower-level import: PCL detects Promptfoo, Langfuse, or LangSmith exports.
pcl ingest auto --input results.json --out runs/from-external --score-name exact_match
pcl report --run runs/from-external

# Use explicit importers when you need tool-specific filters.
pcl ingest promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate

pcl ingest langfuse --input langfuse-export.json --out runs/from-langfuse \
  --name candidate --score-name exact_match

pcl ingest langsmith --input langsmith-runs.csv --out runs/from-langsmith \
  --experiment candidate --score-name exact_match

# Once you have two imported/scored runs, compare them as one evidence bundle.
pcl compare-runs \
  --baseline runs/from-promptfoo-baseline \
  --candidate runs/from-promptfoo-candidate \
  --out runs/from-promptfoo-comparison

pcl evidence-card \
  --run runs/from-promptfoo-comparison \
  --out runs/from-promptfoo-comparison/evidence_card.md

pcl claim-check \
  --run runs/from-promptfoo-comparison \
  --claim paired \
  --out runs/from-promptfoo-comparison/claim_check.json
```

`pcl evidence-from` writes a self-contained bridge directory: `imports/` keeps the external-tool
baseline/candidate snapshots, `comparison/` keeps the PCL paired statistics and prompt-only
validity audit, and the root directory exposes `bridge_summary.md`, `evidence_card.md`,
`claim_check.md`, `research_diagnostics.md`, `report.html`, and `evidence_from_result.json`
for reviewers. Start with
`bridge_summary.md` to see what the external tool supplied, what PCL added, and which evidence is
still missing. Use `research_diagnostics.md` to see which paper-derived diagnostics are present
or still missing, and which copy-paste commands can close each missing gap, without fabricating
hidden-state or Riccati evidence. Use `claim_check.md` to see the strongest
prompt-optimization claim supported. Use a
new or empty `--out` directory so stale artifacts cannot contaminate the audit. The local UI also
surfaces the bridge in Research Overview, including detected external tools, PCL-added evidence,
comparison validity, claim-check status, and missing evidence.

The lower-level imported run still contains `predictions.jsonl`, `metrics.json`, and
`manifest.json`, so it can be used with `pcl compare-runs`, `pcl stats`, `pcl validity`, and
downstream reports. This is intentionally a bridge, not a replacement for Promptfoo's red-team /
provider ecosystem, Langfuse's tracing platform, or LangSmith's observability/evaluation
workflows.

For a copy-paste walkthrough with bundled sample exports, see
[Ecosystem Bridge](docs/ecosystem_bridge.en.md) and
[examples/external](examples/external/).

## Applied Engineering Layer

The agent guard, model provenance, diff audit, GitHub Action, plugins, and UI are practical
applications built around the research core. They help teams use the same evidence trail when a
prompt is handed to Claude Code, Cursor, Codex, or another coding agent.

## Local Case Studies

A small local preflight pilot is included in [agent_guard_pilot.csv](docs/case_studies/agent_guard_pilot.csv). It contains 20 raw coding prompts paired with prompts produced by `pcl guard --profile coding --policy examples/guard.policy.yaml --token-mode balanced`.

| Metric | Local preflight pilot |
|---|---:|
| Paired prompts | 20 |
| Medium-risk prompts | 17 |
| High-risk prompts | 3 |
| Policy violations flagged | 84 |
| Avg raw estimated prompt tokens | 8.75 |
| Avg guarded estimated prompt tokens | 51.75 |

This is **not** a universal benchmark and does **not** claim task-success improvement. The paired agent executions were not run, so success/test/file-change fields are explicitly marked `not_run`. The pilot shows how the guard rewrites and classifies this prompt set before execution.

A second, real paired pilot is included in [agent_guard_paired_pilot.csv](docs/case_studies/agent_guard_paired_pilot.csv). It runs local Codex twice per task from the same fresh fixture repo: once with the raw prompt and once with the guarded prompt. The current set has 12 isolated Python tasks, including multi-file and stateful bug fixes.

| Metric | Raw agent | Guarded agent |
|---|---:|---:|
| Completed tasks | 12/12 | 12/12 |
| Tests passed | 12/12 | 12/12 |
| Average touched files | 1.25 | 1.0 |
| Total unexpected file edits | 3 | 0 |
| Average estimated prompt tokens | 8.08 | 51.08 |
| Average duration seconds | 173.74 | 119.97 |

![Real paired Codex guard pilot visualization](docs/assets/agent_guard_paired_pilot.svg)

Interpretation: guarded prompts still did **not** improve success rate because raw Codex solved all 12 tasks too. After compacting the guard output, guarded prompts used fewer tokens than the earlier 83-token template but still more than raw prompts. In this run they touched fewer files, produced zero unexpected edits, and completed faster on average. See the full notes in [agent_guard_paired_pilot.en.md](docs/case_studies/agent_guard_paired_pilot.en.md).

## Demo And UI

The repository includes narrated 4K hands-on demo videos generated from real UI screenshots and scripted operation replay.

[![prompt_control_lab English demo poster](docs/assets/demo/poster.en.png)](docs/assets/demo/prompt_control_lab_demo.en.mp4)

- [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4)
- [English subtitles](docs/assets/demo/prompt_control_lab_demo.en.srt)
- [Chinese MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4)
- [Chinese subtitles](docs/assets/demo/prompt_control_lab_demo.zh.srt)

![prompt_control_lab UI workflows tutorial screenshot](docs/assets/tutorial_workflows.en.png)

## Quick Map

1. `pcl research-demo`: generate synthetic paper-style inputs, a small comparison bundle, and all research diagnostics.
2. `pcl diagnose`: run soft-hard, trajectory, Riccati, and tv-soft as one diagnostic workflow.
3. `pcl split` / `pcl analyze`: tri-split prompt evaluation and report generation.
4. `pcl stats`: paired bootstrap CI, permutation p-value, and Holm correction.
5. `pcl validity`: check whether a baseline/candidate comparison is clean prompt-only evidence.
6. `pcl soft-hard`: soft-to-hard projection gap and deployment risk.
7. `pcl extract-hidden`: extract HuggingFace hidden states into trajectory-ready `.npz`.
8. `pcl trajectory`: hidden-state drift, decay slope, and turnpike-like signal.
9. `pcl riccati`: fitted finite-dimensional Riccati/DARE surrogate diagnostics.
10. `pcl tv-soft`: static/time-varying/shuffled/random soft-control comparison.
11. `pcl ecosystem-demo`: run all bundled external-tool bridge examples as one comparison bundle.
12. `pcl evidence-from`: import external baseline/candidate exports and generate a PCL evidence card in one command.
13. `pcl ingest auto` / `promptfoo` / `langfuse` / `langsmith`: import external eval/trace artifacts into PCL research artifacts.
14. `pcl compare-runs`: turn two imported/scored runs into stats, validity, and a report in one command.
15. `pcl claim-check`: say what claim the current evidence tier can safely support.
16. `pcl report` / `pcl explain` / `pcl gate`: turn artifacts into readable decisions.
17. `pcl guard` / `pcl audit-diff`: applied AI coding agent preflight and post-run audit.

## Install The CLI ⚙️

Python 3.10 or newer is required. On some machines the command is `python`,
on others it is `python3` or `py -3.10`. If `pip install -e .` fails because
Python is not found, try:

```bash
python --version
python3 --version
py -3.10 --version
```

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

For HuggingFace hidden-state extraction, install the HF extra:

```bash
pip install -e ".[hf]"
```

Use a small local/open model first; this command loads the model on your machine.

### 4. Install local UI extras

Use this when you want the interactive dashboard:

```bash
pip install -e ".[ui]"
```

With `uv`:

```bash
uv pip install -e ".[ui]"
```

### 5. Build and test a local wheel

The PyPI package name is `promptcontrollab`. The repository and product name are
`prompt_control_lab`.

```bash
python -m build
pipx install dist/promptcontrollab-0.1.0-py3-none-any.whl
pcl doctor
```

If the package has not been published to PyPI in your environment, use the local wheel or editable
source install above. Do not use `prompt_control_lab` as the pip package name.

### 6. Check that the CLI works

```bash
pcl --help
pcl start --choice improve --prompt "Answer the user question."
pcl improve --prompt "Answer the user question."
pcl doctor
pcl ui --help
```

Expected result: `pcl --help` lists commands, `pcl start` shows the beginner path,
`pcl improve` prints an optimized prompt plus estimated token cost, and `pcl doctor` checks Python,
package import, CLI parser, guard policy parsing, Claude Code hook, Cursor MCP server, demo report
generation, API-key presence, and optional research dependencies.

## Optional Project Defaults ⚙️

`pcl init` now writes `.promptcontrol.yaml` next to `promptcontrol.example.yaml`. The project file
keeps local defaults for day-to-day commands:

```yaml
guard_policy: examples/guard.policy.yaml
gate_policy: examples/gate.policy.yaml
runs_dir: runs
expected_paths:
  - src
  - tests
test_commands:
  - pytest
allowed_models: gpt-4o,gpt-5.2
ui.default_view: workflows
```

CLI arguments still win. The precedence is: explicit CLI flags → command-specific config such as
`promptcontrol.example.yaml` → `.promptcontrol.yaml` → built-in defaults.

## Watch The Demo Videos 🎬

The repository includes two narrated 4K, hands-on demo videos. They use scripted UI operation
replay: enlarged dashboard screenshots, cursor movement, click highlights, typed command cards,
result callouts, and subtitles. English and Chinese versions walk through the same local workflow:
prompt guard, prompt improvement, analyze/gate/report, model provenance, agent diff audit, history,
plugins, CI, and advanced research diagnostics.

[![prompt_control_lab English demo poster](docs/assets/demo/poster.en.png)](docs/assets/demo/prompt_control_lab_demo.en.mp4)

- [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4)
- [English subtitles](docs/assets/demo/prompt_control_lab_demo.en.srt)
- [English storyboard](docs/demo/storyboard.en.md)

[![prompt_control_lab Chinese demo poster](docs/assets/demo/poster.zh.png)](docs/assets/demo/prompt_control_lab_demo.zh.mp4)

- [中文 MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4)
- [中文字幕](docs/assets/demo/prompt_control_lab_demo.zh.srt)
- [中文分镜脚本](docs/demo/storyboard.zh.md)

The videos are generated reproducibly from [video_manifest.json](docs/demo/video_manifest.json)
and real UI screenshots with:

```bash
python scripts/build_demo_video.py
```

## Open The Local UI Dashboard 🖥️

The UI is a local Streamlit dashboard. It reads artifacts from disk and does not upload prompts,
code, or reports.

```bash
pcl ui --runs runs/ --port 8501
```

For a first demo:

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

The local dashboard now opens with a **Research Overview** tab inspired by compact design-system
dashboards: paper diagnostics first, engineering agent views second. The **Tutorial** tab teaches
the workflow with screenshots from the current UI plus step-by-step instructions; the **Workflows** tab can run local actions
from the browser:
guard a prompt, run analyze, run gate, audit a git diff, build `agent_run.json`, generate a PR
summary, import Promptfoo/Langfuse/LangSmith exports into an external evidence bundle, or export a
report zip. Execution mode defaults to `confirm`; advanced users can choose
`auto` or `command`.

CLI equivalent for the zip export:

```bash
pcl export-report --run runs/quick --out runs/quick/report.zip
```

- **Workflows:** trigger allowlisted local workflows while previewing outputs before files are
  written, including `pcl evidence-from` for external eval/observability exports.
- **Tutorial:** learn each feature as “screenshot -> steps -> artifact -> meaning -> next step”,
  with synchronized English and Chinese UI screenshots.
- **Guard Prompt:** try `pcl guard` interactively and inspect risk, policy violations, token cost,
  and prompt diff.
- **Run Report:** read recommendation, gate status, score delta, confidence interval, p-value,
  slice scores, and model provenance.
- **Model Drift:** inspect provider/model records, alias risk, warnings, and drift artifacts.
- **Agent Diff Audit:** read `audit_result.json`, changed-file breakdown, dangerous paths, tests,
  and review requirement.
- **History:** inspect `history_index.json` timelines, gate trends, score trends, model changes,
  prompt identity, and risk category changes.

![prompt_control_lab UI workflows tutorial screenshot](docs/assets/tutorial_workflows.en.png)

![prompt_control_lab UI guard tutorial screenshot](docs/assets/tutorial_guard.en.png)

![prompt_control_lab UI run report tutorial screenshot](docs/assets/tutorial_report.en.png)

![prompt_control_lab UI audit tutorial screenshot](docs/assets/tutorial_audit.en.png)

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
            "command": "python \"D:/path/to/prompt_control_lab/plugins/claude-code/hooks/prompt_guard.py\" --mode suggest --profile coding --token-mode balanced --max-tokens 300 --policy \"D:/path/to/prompt_control_lab/examples/guard.policy.yaml\""
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

Cursor can be used in two layers: a simple rules workflow, or an optional MCP-style
server that exposes `guard_prompt` as a callable tool.

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

Optional MCP-style server:

```bash
python plugins/cursor/mcp_server.py
```

Point your Cursor MCP configuration at that command if your Cursor setup supports local MCP
servers. Expected result: Cursor can call `guard_prompt` and display the returned
`plain_summary`, `risk_level`, `improved_prompt`, and token estimate.

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

If you installed from a wheel, `pipx`, or `uvx`, install adapter templates with:

```bash
pcl install-plugin codex
pcl install-plugin cursor
pcl install-plugin claude-code
pcl install-plugin github-action
```

Existing files are not overwritten unless you pass `--force`.

### Generic Shell Wrapper 🐚

Any CLI tool can use the JSON interface:

```bash
echo "Write tests for this feature" | pcl guard --stdin --profile coding --json
```

Use the `improved_prompt` field as the prompt sent to your agent, or use `action=block` as
a stop signal in gate mode.

Boundary: `pcl guard` is a local heuristic and policy preflight. It catches obvious risk and
missing context, but it does not prove an agent action is safe.

### GitHub Action / PR Comment Example 🧪

The repository includes a copy-ready workflow template:

```text
examples/github-action/prompt-control-lab-gate.yml
```

Copy it into `.github/workflows/` when you want PRs to run `pcl gate`, optionally audit the PR
diff with `pcl audit-diff`, and post a short prompt_control_lab result comment.

For a reusable local summary artifact:

```bash
pcl pr-summary \
  --audit runs/agent-audit/audit_result.json \
  --gate runs/quick/gate_result.json \
  --out runs/pr_summary.md \
  --json-out runs/pr_summary.json
```

For a self-hosted GitHub App webhook:

```bash
pcl github-app serve --host 0.0.0.0 --port 8080
```

## Feature Path: Simple To Expert 🚀

The sections below are ordered from direct, friendly workflows to more flexible research tools.

### 1. `pcl start`: beginner scenario menu 🌈

Operation:

```bash
pcl start
```

Non-interactive operation:

```bash
pcl start --choice improve --prompt "Answer the user question."
pcl start --choice guard --prompt "Fix this bug"
```

Result:

- a simple menu with three scenarios: improve, guard, or analyze
- plain-language output without needing to understand `profile`, `gate`, or JSON first
- all expert commands remain available after the beginner path

What it means:

Use this when you only know what you want in ordinary language: make the prompt clearer,
check whether it is too broad, or learn how to generate a full report.

### 2. `pcl improve`: rewrite one prompt directly ✨

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

### 3. `pcl guard`: protect prompts before IDE or CLI agents use them 🛡️

Operation:

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced --json
```

Gate operation:

```bash
echo "Answer the user question." | pcl guard --stdin --mode gate --max-tokens 80 --json
```

Team policy operation:

```bash
pcl guard --prompt "Fix this bug" \
  --profile coding \
  --policy examples/guard.policy.yaml \
  --json
```

Result:

- `plain_summary`: a human-readable sentence for non-technical users
- `action`: `suggest`, `auto`, or `block`
- `risk_level`: `low`, `medium`, or `high`
- `improved_prompt`: guarded prompt
- `token_report`: estimated token cost
- `reasons`: why the guard suggested or blocked
- `risk_categories`: examples include `destructive_change`, `security`, `production_path`,
  `broad_refactor`, `token_budget`, or team policy categories
- `policy_violations`: exact policy or built-in guard violations
- `required_review`: whether a human should review before execution

What it means:

Use this before Claude Code, Cursor, Codex, or a shell wrapper spends tokens. It catches vague,
over-budget, dangerous, or underspecified prompts early. With `--policy`, teams can turn it into
a configurable preflight gate for AI coding agents.

Policy files are dependency-free: the bundled example uses flat keys such as
`rule.destructive_action.patterns`, and v0.1 also accepts a small nested `rules:` form for users
who naturally write YAML lists.

### 4. `pcl analyze`: one command, one report 📦

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

### 5. `pcl model-detect`: record model identity 🔎

Operations:

```bash
pcl model-detect --response response.json --provider openai
pcl model-detect --predictions examples/predictions_candidate.jsonl
pcl model-detect --model gpt-5.2 --provider openai --verify
```

Result:

```json
{
  "provider": "openai",
  "model_id": "gpt-5.2",
  "source": "response.model",
  "confidence": "high",
  "provenance_level": "level_1_observed_in_response",
  "verified": false,
  "warnings": []
}
```

What it means:

This records the public model id declared in API responses, prediction files, or command-line
metadata. It helps answer whether a baseline and candidate were run on the same model. It does
not prove the provider's hidden internal weight build.

Provenance levels are explicit:

| Level | Meaning |
|---|---|
| `level_0_declared_by_user` | model id came from a user argument or config |
| `level_1_observed_in_response` | model id was observed in response or prediction artifacts |
| `level_2_provider_metadata_verified` | public provider metadata confirmed the model object |
| `level_3_provider_log_reference_recorded` | provider-side log reference was recorded |
| `level_4_signed_receipt_recorded` | signed receipt reference was recorded; this is not signature verification |

For stronger provenance, attach request evidence:

```bash
pcl model-detect \
  --response response.json \
  --provider openai \
  --request-id req_123 \
  --provider-log-reference usage-log:req_123
```

You can also attach model identity to evaluation artifacts:

```bash
pcl eval --data examples/tasks.jsonl \
  --predictions examples/predictions_candidate.jsonl \
  --out runs/candidate \
  --method candidate \
  --provider openai \
  --model gpt-5.2

pcl analyze --config promptcontrol.example.yaml \
  --baseline-model gpt-4o \
  --candidate-model gpt-5.2
```

If baseline and candidate use different model ids, `report.md` shows a warning because the
comparison is no longer prompt-only.

Model drift audit:

```bash
pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json
```

This reports whether a prompt comparison is clean or confounded by a model/provider change or
alias model id.

### 6. `pcl audit-diff`: inspect what the agent changed 🔎

Operation:

```bash
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
```

Optional scope and tests:

```bash
pcl audit-diff \
  --before HEAD~1 \
  --after HEAD \
  --expected-path src \
  --test-command "pytest tests/test_session.py" \
  --out runs/audit
```

Optional SARIF and external secret scanner entrypoints:

```bash
pcl audit-diff \
  --before HEAD~1 \
  --after HEAD \
  --out runs/audit \
  --sarif runs/audit/pcl.sarif \
  --secret-scanner builtin
```

`builtin` scans added diff lines. `gitleaks` and `trufflehog` are optional workspace-level
scanner entrypoints; their findings may include pre-existing files outside the selected
`before`/`after` diff.

By default, `--test-command` runs without shell control syntax, records stdout/stderr snippets,
and times out per command. Prefer `--tests-run` / `--tests-passed` when tests were already run
elsewhere. Use `--allow-shell-test-command` only for trusted local input.

Result:

- `runs/audit/audit_result.json`
- `runs/audit/audit_summary.md`
- optional `runs/audit/pcl.sarif`

What it means:

Use this after a coding agent runs. It records touched files, source/test/docs/config changes,
dangerous paths such as auth or billing code, public API changes, test evidence, unexpected file
edits, and whether human review is required.

To connect prompt identity, model provenance, gate status, and audit evidence into one compact
artifact:

```bash
pcl agent-run build --run runs/quick --audit runs/audit --agent codex --out runs/agent_run.json
```

### 7. `pcl history`: index and compare runs 🧭

Operations:

```bash
pcl history index --runs runs/ --out runs/history_index.json
pcl history compare --a runs/old --b runs/new --out runs/history_compare.json
```

What it means:

The index turns run directories into a small local history. The comparison highlights prompt
identity changes, model/provider changes, score deltas, gate status changes, slice regressions,
and new risk categories.

### 8. `pcl init`: create a runnable example 🌱

Operation:

```bash
pcl init --path demo
cd demo
```

Result:

- `examples/tasks.jsonl`
- `examples/predictions_baseline.jsonl`
- `examples/predictions_candidate.jsonl`
- `examples/guard.policy.yaml`
- `examples/gate.policy.yaml`
- `promptcontrol.example.yaml`

What it means:

These files show the minimal input format: task `id`, `input`, `expected`, `slice`, model
`output`, and optional `provider` / `model` provenance records.

### 9. `pcl report`, `pcl explain`, `pcl gate`: read and decide ✅

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
- a top-of-report deployment recommendation: `yes`, `no`, or `needs_review`

What it means:

These commands turn artifacts into decisions: keep the prompt, review it, or hold it.
The gate can check metrics, statistical evidence, soft-hard risk, and model provenance.

### 10. Expert evaluation: `split → eval → stats` 🧠

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

### 11. Advanced / Research Mode diagnostics 🔬

Soft-to-hard risk:

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

Hidden-state trajectory:

```bash
pcl extract-hidden \
  --model Qwen/Qwen2.5-0.5B \
  --prompts examples/tasks.jsonl \
  --out runs/candidate/inputs/hidden_states.npz \
  --pool last-token \
  --max-items 32

pcl trajectory \
  --states runs/candidate/inputs/hidden_states.npz \
  --out runs/candidate/diagnostics
```

`extract-hidden` is optional and requires `pip install -e ".[hf]"`. It writes
`hidden_states.npz` plus `hidden_states.npz.metadata.json`, so open-model users can produce the
artifact that `trajectory`, `riccati --trajectory`, and `diagnose` expect.

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

`prompt_control_lab` should not be read as another broad LLM dashboard or prompt manager. Its core
lane is **control-theoretic prompt diagnostics + reproducible prompt optimization evidence**.

Adjacent tools cover important neighboring layers:

- promptfoo and DeepEval focus on LLM evaluation, tests, red-team checks, and metrics.
- Langfuse, LangSmith, and Phoenix focus on traces, observability, experiments, and app-level evaluation.
- DSPy, TextGrad, and OpenPrompt focus on prompt/program optimization or prompt-learning workflows.
- `prompt_control_lab` adds paper-derived diagnostics around prompt optimization: tri-split
  protocol hygiene, paired statistical evidence, soft-hard deployment gap, hidden-state trajectory
  probes, Riccati surrogates, and time-varying soft-control comparisons.

The guard/policy/model-audit workflow remains useful, but it is an applied engineering layer around
the research diagnostics rather than the center of gravity.

The ecosystem bridge is deliberately narrow: import external eval/trace evidence first, then run
PCL's comparison validity and paper-derived diagnostics on top.

![prompt_control_lab ecosystem position](docs/assets/ecosystem.svg)

![prompt_control_lab comparison matrix](docs/assets/comparison_matrix.svg)

![prompt_control_lab innovation stack](docs/assets/innovation_stack.svg)

## Who It Is For 👥

- Researchers and reproducibility-focused teams comparing prompt methods with train/val/withheld
  splits and paired statistics.
- Prompt optimization and soft-prompt researchers studying soft-hard deployment risk,
  hidden-state trajectories, Riccati surrogates,
  and time-varying soft-control behavior.
- LLM teams that need prompt regression reports, model provenance, model drift warnings, and
  prompt-only comparison checks.
- Developers using Claude Code, Cursor, Codex, or shell-based coding agents who want to apply the
  same evidence trail to local agent runs.
- Engineering teams that need configurable prompt policy gates for risky, broad, destructive,
  security-sensitive, or untested coding requests.

## Documentation 📚

- [Background](docs/background.en.md)
- [Users](docs/users.en.md)
- [Tutorial](docs/tutorial.en.md)
- [Artifacts](docs/artifacts.en.md)
- [Research From The Paper](docs/research_from_paper.en.md)
- [Ecosystem Bridge](docs/ecosystem_bridge.en.md)
- [Agent guard pilot case study](docs/case_studies/agent_guard_pilot.en.md)
- [Real paired agent pilot case study](docs/case_studies/agent_guard_paired_pilot.en.md)
- [Production pilot protocol](docs/production_pilot.en.md)
- [Release and install readiness](docs/release_install.en.md)
- [Innovation and Contribution](docs/innovation.en.md)
- [Decision Guide](docs/decision_guide.en.md)
- [Plugin adapters](plugins/)

## License 📄

Apache-2.0
