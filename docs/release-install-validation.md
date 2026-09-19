# Validating a built wheel outside the checkout

Run the wheel acceptance test against the exact file intended for release. A
source-tree test or editable install does not establish that the wheel contains
its templates, browser assets, or diagnostic entry points.

Build the React assets and Python distribution using the release process first.
Then select one wheel explicitly; do not let an old wheel in `dist` satisfy the
test accidentally. The test runner needs pytest, but the temporary environment it
creates starts with no PromptControlLab or optional dependencies.

PowerShell:

```powershell
$env:PCL_TEST_WHEEL = (Resolve-Path 'dist/promptcontrollab-<version>-py3-none-any.whl').Path
$env:PCL_WHEEL_EVIDENCE = Join-Path (Get-Location) '.integration/wheel-install-evidence.json'
python -m pytest tests/test_wheel_install.py -q
```

POSIX shells:

```sh
PCL_TEST_WHEEL="$(pwd)/dist/promptcontrollab-<version>-py3-none-any.whl" \
PCL_WHEEL_EVIDENCE="$(pwd)/.integration/wheel-install-evidence.json" \
python -m pytest tests/test_wheel_install.py -q
```

The acceptance test creates a fresh virtual environment, installs only the chosen
wheel with `--no-index --no-deps`, removes `PYTHONPATH` and `PYTHONHOME`, and runs
Python in isolated mode from a directory outside the checkout. It verifies the
import comes from that virtual environment, the CLI loads, doctor runs, packaged
plugin templates install, and missing UI dependencies produce the published
`promptcontrollab[ui]` install hint. It also checks that the React index and all
asset paths referenced by that index exist in the wheel. Interpreter caches and
`node_modules` must not be present.

If `PCL_TEST_WHEEL` is absent, the built-wheel test is explicitly skipped. The
remaining tests check the diagnostic fallbacks and both UI install hints against
the current source; that result must not be described as clean-wheel acceptance.
When `PCL_WHEEL_EVIDENCE` is supplied, a successful wheel test writes the wheel's
SHA-256, installed import path, doctor results, and browser asset references to
JSON. Rebuilding any deliverable requires testing its new bytes again.

## What doctor establishes

| Check | Wheel-install evidence |
| --- | --- |
| `guard_policy` | The packaged example policy parses. A present checkout policy is checked directly; invalid local policy is not hidden by fallback. |
| `claude_code_hook` | The packaged hook executes against a local synthetic prompt. This makes no model request and does not establish an editor integration session. |
| `cursor_rule_template` | A nonempty packaged Cursor rule is available. |
| `cursor_mcp_server` | Explicitly **skipped** when the checkout-only server is absent; no live initialization is claimed. |
| `demo_report` | Local deterministic example predictions generate a report. This is synthetic installation evidence. |

Missing credentials and optional research dependencies may leave doctor's overall
status at `warning`. These are distinct from a missing or broken packaged resource,
which fails its own check. A template-presence check never substitutes for an
actual Cursor MCP initialization.

The base-wheel test intentionally stops at the UI dependency hint. Validate the
React server after installing the `ui` extra in a separate clean environment, and
perform provider/GEPA acceptance separately with explicit finite budgets. Neither
live model quality nor browser interaction is established by the base-wheel test.

## Clean UI wheel and library acceptance

`scripts/validate_installed_wheel.py` runs under the new environment's isolated
Python. It compares every installed package file with the selected wheel before
testing the library, so an older installation cannot satisfy a newer wheel's
checks. Use a fresh environment and runs directory for each release candidate.

From the repository root, after building the final wheel:

```powershell
$releaseRoot = (Get-Location).Path
$wheelPath = (Resolve-Path 'dist/promptcontrollab-<version>-py3-none-any.whl').Path
$stageRoot = Join-Path $releaseRoot '.integration/wheel'
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
uv venv (Join-Path $stageRoot 'final-ui-env')
$wheelPython = Join-Path $stageRoot 'final-ui-env/Scripts/python.exe'
uv pip install --python $wheelPython "$($wheelPath)[ui]"
Push-Location $stageRoot
try {
  & $wheelPython -I (Join-Path $releaseRoot 'scripts/validate_installed_wheel.py') `
    --wheel $wheelPath --stage final --runs './final-runs' --output './final-ui-evidence.json'
} finally {
  Pop-Location
}
```

The installer may use `--offline` when all dependencies are already in uv's cache.
The validator removes Node from its process search path, verifies all four UI
dependencies and packaged research examples, and runs synthetic import and
evaluation jobs through the public library API. It exports both jobs and starts
the installed HTTP server to fetch the React index and referenced assets, inspect
the session and experiment endpoints, and reject a hostile Host header. Final
validation also requires the health endpoint to identify the mode as
`local_session`. These checks establish local server and library functionality;
they do not establish browser rendering quality or live model performance.

The output records the exact SHA-256 and a required `provisional` or `final` stage.
Keep a provisional wheel copy and its evidence separately. After rebuilding,
install and validate the final wheel again; a provisional pass does not validate
the final bytes. Cursor server initialization remains explicitly skipped when
the checkout-only server is absent.

The diagnostic fallbacks and published-extra hint adapt the installation fixes
from [PR #4](https://github.com/VeraPyuyi/prompt_control_lab/pull/4) to the current
React UI. Cursor template availability and server execution are reported as
separate checks.
