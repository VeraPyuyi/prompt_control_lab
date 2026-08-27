# Integrations

## Purpose

`promptcontrollab.integrations` connects the domain APIs to providers, agents, developer tools, the local Streamlit UI, and the bounded Hugging Face demo. Integrations translate external protocols; they do not redefine core evidence or decision semantics.

## Use cases

- Inspect or call a supported model provider through one local adapter contract.
- Install and operate the DeepSeek Harness, Claude Code, Cursor, Codex, or GitHub Action adapters.
- Explore runs in the local dashboard without uploading project data.
- Build a public-safe, CPU-only Hugging Face Space bundle.

## CLI commands

```bash
pcl providers list
pcl providers inspect deepseek
pcl providers doctor deepseek
pcl harness init --project .
pcl harness doctor --project .
pcl install-plugin deepseek-harness
pcl install-plugin all --target ./installed-templates
pcl ui --runs runs --language en
pcl github-app serve --host 0.0.0.0 --port 8080
```

## Python API

The approved canonical package exposes integration adapters and installers:

```python
from promptcontrollab.integrations import (
    build_space_bundle,
    call_provider,
    doctor_harness,
    install_plugin,
    list_providers,
)
```

Supporting APIs initialize and replay Harness sessions, validate the Hugging Face demo boundary, load UI data, and execute allowlisted UI workflows.

## Inputs/Artifacts

- Inputs: provider configuration, environment credentials, Harness event JSONL, plugin targets, run directories, and public-demo manifests.
- Outputs: provider responses, installed adapter templates, Harness control artifacts, UI views/downloads, and a filtered Space deployment bundle.
- Credentials are read from environment variables and must never be written to artifacts.

## Dependencies

Provider metadata and plugin installation use the default runtime. The UI requires the `ui` extra, the GitHub App requires `bot`, and model/post-training integrations use their declared optional extras. The DeepSeek Harness plugin has its own TypeScript toolchain.

## Extension points

- Add providers through the shared provider specification and response contract.
- Add agent adapters by translating lifecycle events into `ControlEvent` records.
- Add UI pages and deployment surfaces that consume structured domain models rather than parsing rendered reports.

## Limitations

- Provider support records public API behavior, not hidden model internals.
- Thin editor adapters may depend on host capabilities and cannot intercept every prompt path.
- The Hugging Face demo intentionally disables providers, Git changes, shell execution, plugin installation, and durable storage.

## Tests/Examples

See `plugins/`, `deploy/huggingface/`, provider docs, UI tests, and Harness contract tests. Run:

```bash
python -m pytest tests -k "provider or harness or plugin or ui or hf_demo or github_app"
```

For the native Harness plugin, run `npm run check` in `plugins/deepseek-harness`.
