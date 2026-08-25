# Contributing to PromptControlLab

Thank you for helping improve PromptControlLab. The project welcomes focused contributions to
prompt and agent control, checkpoint diagnosis, evidence adapters, provider and agent
integrations, the local UI, tests, and documentation.

Chinese guidance: [CONTRIBUTING.zh.md](CONTRIBUTING.zh.md).

## Before opening a change

1. Search existing issues and pull requests.
2. For a substantial new protocol, adapter, or artifact schema, open a feature request first.
3. Do not include API keys, private prompts, hidden reasoning, private datasets, model weights,
   or machine-specific paths in an issue, pull request, fixture, or generated artifact.
4. Report security vulnerabilities through GitHub Private Vulnerability Reporting, following
   [SECURITY.md](SECURITY.md), rather than a public issue.

PromptControlLab is not a paper-reproduction repository. PEOC and other research methods inform
some diagnostics, but contributions should expose reusable, provider-neutral capabilities and
clear claim boundaries.

## Development setup

PromptControlLab requires Python 3.10 or newer. The DeepSeek Harness plugin additionally uses
Node.js 22.

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
python -m pip install -e ".[dev,research]"
cd plugins/deepseek-harness
npm ci
cd ../..
```

For UI work, also install `.[ui]`. Provider live tests must remain opt-in and must skip cleanly
when their credential is absent.

## Making a change

- Keep the change scoped. Avoid unrelated refactors and generated-file churn.
- Add or update tests for behavior changes.
- Keep JSON artifacts backward compatible or document and test a versioned migration.
- Update English and Chinese documentation together when a user-facing workflow changes.
- Keep the Python plugin template in `src/promptcontrollab/template_data/` synchronized with
  its source adapter.
- Do not modify an upstream paper, external experiment archive, or imported evidence source.

## Evidence and claim rules

Evidence contributions must separate:

1. what was observed;
2. what the evidence can explain;
3. what it cannot prove; and
4. the recommended next action.

Do not turn a correlation, fitted surrogate, small pilot, replay, fixture, or incomplete run into
a causal, universal, production-safety, or performance claim. Preserve raw status values such as
`hold`, `insufficient_evidence`, confidence intervals, and p-values. Public cases should contain
only the minimum aggregate evidence needed for independent review.

## Required checks

Run the complete checks before requesting review:

```bash
python -m pytest
python -m ruff check .
python -m mypy src tests
cd plugins/deepseek-harness
npm run check
```

For packaging changes, also build and install the wheel in a fresh environment as described in
the [release installation guide](docs/release_install.en.md). Build the sdist as well and inspect
its member list for VCS data, environments, build outputs, runtime artifacts, vendored dependency
trees, credentials, and oversized demo media.

## Pull requests

Use the pull request template and include:

- the user-visible problem and the chosen boundary;
- artifacts or schemas changed;
- exact verification commands and results;
- privacy and claim-boundary implications; and
- screenshots for visible UI changes.

Maintainers may ask to split a pull request when independent behavior, generated evidence, and
presentation changes are mixed together.
