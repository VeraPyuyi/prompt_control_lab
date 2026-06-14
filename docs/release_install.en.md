# Release And Install Readiness

This checklist helps maintainers and early users verify that `prompt_control_lab`
is installable from source, wheel, `pipx`, or `uvx`-style workflows.

The Python package name is `promptcontrollab`. The repository and project brand
name is `prompt_control_lab`.

## Source Install

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e .
pcl doctor
```

Expected result: `pcl doctor` reports Python version, package import, CLI parser,
guard policy parsing, plugin adapter checks, demo report generation, and optional
dependency status.

## Local Wheel Build

```bash
python -m pip install build
python -m build
```

Expected result: `dist/` contains a wheel named like:

```text
promptcontrollab-0.1.0-py3-none-any.whl
```

Do not commit `dist/` artifacts unless a release process explicitly asks for
them.

If your environment cannot reach PyPI to install isolated build dependencies,
install the build backend in the current environment and run:

```bash
python -m build --wheel --no-isolation
```

This fallback verifies the project package layout when the failure is caused by
network or proxy access to build dependencies rather than by the project itself.

## Wheel Smoke Test

Create a temporary environment or use `pipx`:

```bash
pipx install dist/promptcontrollab-0.1.0-py3-none-any.whl
pcl --help
pcl doctor
pcl install-plugin all --target ./tmp-pcl-templates
```

Expected result: the CLI is available, `pcl doctor` runs, and template installers
can write Codex, Cursor, Claude Code, and GitHub Action templates.

When the current environment already has the `research` extra installed, also
verify the paper-derived workflow from the built wheel:

```bash
python -m pip install --force-reinstall --no-deps dist/promptcontrollab-0.1.0-py3-none-any.whl
pcl research-demo --out ./tmp-pcl-research-demo
pcl diagnose --run ./tmp-pcl-research-demo
```

Expected result: `research_bundle.html`, `research_diagnostics.html`,
`evidence_card.html`, and `claim_check.html` are generated from the wheel-installed
package.

## uv / uvx Notes

For editable development:

```bash
uv pip install -e ".[dev,ui]"
```

For a local wheel smoke test, install the wheel path directly. If the package is
not published to PyPI in your environment, do not use `uvx prompt_control_lab`.
Use the package name `promptcontrollab` only after it is published.

## Template Data Check

The adapter templates are packaged under `promptcontrollab.template_data`.
After installing from a wheel, verify:

```bash
pcl install-plugin codex --target ./tmp-pcl-codex
pcl install-plugin cursor --target ./tmp-pcl-cursor
pcl install-plugin claude-code --target ./tmp-pcl-claude
pcl install-plugin github-action --target ./tmp-pcl-action
```

Existing files are not overwritten unless `--force` is used.

## Release Boundary

If no PyPI token is configured, stop after local build and wheel smoke tests.
Document the package as "PyPI-ready" rather than "published". Do not claim a
PyPI install path until the package is actually available under
`promptcontrollab`.
