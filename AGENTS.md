# AGENTS.md

## Cursor Cloud specific instructions

This is a pure Python CLI project (`promptcontrollab`) with **zero runtime dependencies** (stdlib only). There are no servers, databases, Docker containers, or external services to start.

### Quick reference

| Task | Command |
|------|---------|
| Install (editable + all extras) | `pip install -e ".[dev,research]"` |
| Lint | `ruff check .` |
| Type check | `mypy` |
| Tests | `pytest` |
| CLI help | `pcl --help` |

### Notes for Cloud Agents

- The `pcl` CLI and dev tools (`ruff`, `mypy`, `pytest`) install to `~/.local/bin`. Ensure `$HOME/.local/bin` is on `PATH` before running commands.
- CI uses Python 3.12. The environment ships Python 3.12.3 which matches.
- `mypy` emits one note about an unused `scipy.*` override section in `pyproject.toml` — this is expected and not an error.
- All data files are flat (JSONL/JSON/YAML/NPZ). No database or network access is needed.
- To run a full end-to-end demo: `pcl init --path /tmp/demo && cd /tmp/demo && pcl analyze --config promptcontrol.example.yaml --out runs/quick`.
