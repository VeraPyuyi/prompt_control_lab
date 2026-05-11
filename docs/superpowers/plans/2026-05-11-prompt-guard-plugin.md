# Prompt Guard Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a prompt-input guard mode that can optimize or gate user prompts before Claude Code, Cursor, Codex, or other IDE/CLI agents process them.

**Architecture:** Implement a small core module, `prompt_guard.py`, that wraps the existing offline `improve_prompt` engine and returns a structured decision: `allow`, `suggest`, or `block`. Add a `pcl guard` CLI command with plain and JSON output, stdin support for hooks, and a Claude Code `UserPromptSubmit` hook prototype under `plugins/claude-code`.

**Tech Stack:** Python standard library, existing `prompt_improver`, `pytest`, `ruff`, `mypy`, Markdown docs, Claude Code hook JSON output format.

---

### Task 1: Core Guard API

**Files:**
- Create: `src/promptcontrollab/prompt_guard.py`
- Test: `tests/test_cli.py`

- [ ] Write failing tests for:
  - `pcl guard --prompt "Fix this" --json` emits `action`, `risk_level`, `improved_prompt`, and `token_report`.
  - `pcl guard --stdin --mode gate --max-tokens 8 --json` returns `action: block` for an over-budget rewrite.

- [ ] Implement `PromptGuardResult` and `guard_prompt()` in `prompt_guard.py`.

- [ ] Run `pytest tests/test_cli.py -k guard`.

### Task 2: CLI Integration

**Files:**
- Modify: `src/promptcontrollab/cli.py`
- Test: `tests/test_cli.py`

- [ ] Add `guard` subcommand with:
  - `--prompt`
  - `--prompt-file`
  - `--stdin`
  - `--mode suggest|auto|gate`
  - `--profile general|coding|research`
  - `--token-mode balanced|aggressive`
  - `--max-tokens`
  - `--json`

- [ ] Ensure plain output is human-readable and JSON output is stable for hooks.

- [ ] Run `pytest tests/test_cli.py -k guard`.

### Task 3: Claude Code Hook Prototype

**Files:**
- Create: `plugins/claude-code/README.md`
- Create: `plugins/claude-code/hooks/prompt_guard.py`
- Create: `plugins/claude-code/settings.example.json`
- Test: `tests/test_cli.py`

- [ ] Add hook script that reads Claude Code `UserPromptSubmit` JSON from stdin, calls guard logic, and prints Claude-compatible JSON:
  - `additionalContext` for `suggest` and `auto`
  - `decision: block` plus `reason` for `gate` blocks

- [ ] Add a lightweight test that runs the hook script with fixture JSON and validates JSON output.

- [ ] Document installation and limitations.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `docs/tutorial.en.md`
- Modify: `docs/tutorial.zh.md`

- [ ] Add a short “Prompt Guard Plugins” section.

- [ ] Verify:
  - `pytest`
  - `ruff check .`
  - `mypy src tests`
  - `git diff --check`

- [ ] Commit and push.
