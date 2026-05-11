# PromptControlLab Demo Pack

This document explains the project in the most product-facing way:

1. A 2-minute demo script.
2. A Claude Code / Cursor integration case.
3. A before/after table and pilot measurement template.

One-line positioning:

> PromptControlLab is a lightweight prompt preflight and regression-report toolkit for AI coding agents.

---

## 1. Two-minute demo script

### Title

**PromptControlLab: a prompt preflight layer for AI coding agents**

### 0:00--0:15 Pain point

Show a vague prompt:

```text
Fix this bug.
```

Narration:

> Many AI coding failures start before the model runs. The prompt does not say which files matter, what behavior is failing, what tests to run, or what must not be changed.

### 0:15--0:45 Run `pcl guard`

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced
```

Show the key output:

```text
Action: suggest
Risk: medium
Improved prompt: ...
Estimated token cost: ...
```

Narration:

> `pcl guard` checks the prompt before the agent runs. It returns a risk level, an improved prompt, reasons, and an estimated token cost.

### 0:45--1:10 Use stable JSON for IDEs and agents

```bash
echo "Refactor this module" | pcl guard --stdin --profile coding --json
```

Narration:

> The JSON interface can be used by Claude Code hooks, Cursor rules, MCP-style servers, or shell wrappers.

### 1:10--1:40 Generate a regression report

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

Show the artifacts:

```text
runs/quick/report.md
runs/quick/report.html
runs/quick/stats.json
runs/quick/explanation.json
```

Narration:

> Prompt changes should not be judged by intuition alone. `pcl analyze` turns baseline and candidate outputs into a reproducible report.

### 1:40--2:00 Summary

```text
Before: vague prompt -> risky agent execution
After: guarded prompt -> clearer task and test focus
Report: prompt change -> reproducible evidence
```

---

## 2. Claude Code / Cursor integration case

### Scenario

Original prompt:

```text
Fix this bug.
```

Problems:

- No target files.
- No failing behavior.
- No test plan.
- No edit boundary.

Guard first:

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced --json
```

Then send the returned `improved_prompt` to Claude Code, Cursor, or Codex.

### Claude Code

Hook file included in this repository:

```text
plugins/claude-code/hooks/prompt_guard.py
```

Manual test:

```powershell
'{"hook_event_name":"UserPromptSubmit","prompt":"Fix this bug"}' |
  python plugins\claude-code\hooks\prompt_guard.py --mode suggest --profile coding
```

Expected result: JSON with `additionalContext`, which can inject the prompt-guard recommendation into Claude Code context.

### Cursor

Project rule setup:

```powershell
New-Item -ItemType Directory -Force .cursor\rules
Copy-Item plugins\cursor\rules\prompt_control_lab.mdc .cursor\rules\prompt_control_lab.mdc
```

MCP-style server:

```bash
python plugins/cursor/mcp_server.py
```

Expected result: Cursor can call `guard_prompt` and read `plain_summary`, `risk_level`, `improved_prompt`, and `token_report`.

### Before / After example

Before:

```text
Fix this bug.
```

After:

```text
Fix the reported bug with the smallest safe code change.

Before editing:
1. Identify the failing behavior and relevant files.
2. State the likely root cause.
3. List the tests you will run.

Constraints:
- Do not refactor unrelated code.
- Do not change public APIs unless necessary.
- Keep the patch minimal and explain every changed file.

After editing:
1. Run the relevant tests.
2. Summarize the fix.
3. Mention any remaining uncertainty.
```

---

## 3. Before / After tables

### 3.1 Built-in smoke result

Run:

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

Built-in example result:

| id | slice | expected | baseline output | candidate output | baseline correct | candidate correct |
|---|---|---:|---:|---:|---:|---:|
| arith-1 | arithmetic | 4 | 4 | 4 | yes | yes |
| arith-2 | arithmetic | 7 | 6 | 7 | no | yes |
| format-1 | format | POSITIVE | POSITIVE | POSITIVE | yes | yes |
| format-2 | format | NEGATIVE | negative | NEGATIVE | no | yes |

Summary:

| metric | baseline | candidate | delta |
|---|---:|---:|---:|
| exact match overall | 2/4 = 0.50 | 4/4 = 1.00 | +0.50 |
| arithmetic slice | 1/2 = 0.50 | 2/2 = 1.00 | +0.50 |
| format slice | 1/2 = 0.50 | 2/2 = 1.00 | +0.50 |
| fixed examples | - | arith-2, format-2 | 2 fixed |
| broken examples | - | none | 0 broken |

This is a smoke test, not a large benchmark. It demonstrates that the pipeline can run from data and predictions to statistics and reports.

### 3.2 Real agent prompt-guard pilot table

Recommended protocol: collect 20--50 real AI coding prompts. Run each task twice:

- Before: send the raw prompt directly to the agent.
- After: run `pcl guard --profile coding`, then send the improved prompt to the agent.

Template:

| task id | prompt type | guard action | risk level | raw success | guarded success | raw touched files | guarded touched files | raw tests passed | guarded tests passed | note |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| bug-001 | vague bug fix | suggest | medium | no | yes | 8 | 3 | no | yes | guard forced target-file and test plan |
| refactor-002 | broad refactor | review | high | no | review | 15 | - | no | - | scope too broad |
| test-003 | test generation | auto | low | yes | yes | 2 | 2 | yes | yes | small prompt change |

Public summary template:

| measurement | before raw prompts | after `pcl guard` | desired direction |
|---|---:|---:|---|
| task success rate | TBD | TBD | higher |
| average touched files | TBD | TBD | lower or more focused |
| tests passed | TBD | TBD | higher |
| prompts sent to review | 0 | TBD | nonzero for risky prompts |
| average prompt token estimate | TBD | TBD | controlled |
| human intervention count | TBD | TBD | lower |

Careful wording:

> The built-in smoke test demonstrates the reproducible evaluation pipeline. The agent prompt-guard table is a pilot protocol for measuring real Claude Code/Cursor usage. We do not claim a universal success-rate improvement until a larger real-task benchmark is run.
