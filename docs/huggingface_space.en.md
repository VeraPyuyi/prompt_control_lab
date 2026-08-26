# Hugging Face public demo

The Hugging Face Space is a restricted, stateless product preview. It lets someone understand the
PromptControlLab evidence model before installing the full local tool, while GitHub remains the
single upstream repository for source, Issues, Pull Requests, and releases.

## What the Space supports

- Run the offline Prompt Guard and inspect/download the improved prompt.
- Browse curated Quick Analysis, model drift, Agent Audit, History, checkpoint, and control
  certificate artifacts.
- Upload one recognized PromptControlLab JSON or JSONL artifact, up to 5 MB, into the current
  temporary session.
- Switch between English and Chinese and download current-session JSON, text, and report outputs.

The online demo does not execute arbitrary commands, mutate a Git repository, install plugins,
connect to a provider, run a DeepSeek Harness bridge, train a model, or accept ZIP, pickle, PT, or
NPZ uploads. Direct backend workflow calls enforce the same restrictions as the visible UI.

Each browser session receives `/tmp/prompt_control_lab/sessions/<random-id>`. Curated demo data is
copied into that directory, session uploads remain below it, and marked directories expire after a
bounded interval. Uploads are additionally bounded by per-session file/byte quotas and a global
temporary-storage quota. Raw Prompt text is used in Streamlit session memory for Guard output and is not
written to a server artifact. Hugging Face Space disk is ephemeral, so a restart removes temporary
data. Do not upload secrets or private production artifacts to a public Space.

## Deploy from GitHub

1. Create a public Docker Space, normally `<HF_NAMESPACE>/prompt-control-lab`, on free CPU hardware.
2. Add repository secrets `HF_SPACE_ID` and `HF_TOKEN`. Give the token write access only to the
   target Space.
3. Run the `Deploy Hugging Face Space` workflow manually, or publish a GitHub Release.
4. The workflow runs the Python quality gates, builds the wheel, creates an allowlisted bundle,
   uploads it, waits for a running Space, checks the Streamlit health endpoint, and verifies that
   `space_manifest.json` records the source commit.

The deployment workflow is intentionally not triggered on every `main` update.

## Build locally

```bash
python -m pip install -e ".[dev,research,ui]"
python -m build
python scripts/build_hf_space_bundle.py \
  --output .hf-space \
  --wheel dist/promptcontrollab-0.2.0a1-py3-none-any.whl \
  --source-commit "$(git rev-parse HEAD)"
docker build -t prompt-control-lab-hf .hf-space
docker run --rm -p 7860:7860 prompt-control-lab-hf
```

Open `http://localhost:7860`. The image runs as an unprivileged user and exposes only port `7860`.

The deployment follows Hugging Face's current [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker)
configuration. Storage behavior is described in the official
[Spaces storage guide](https://huggingface.co/docs/hub/en/spaces-storage).

## Bundle boundary

`scripts/build_hf_space_bundle.py` copies only the files declared by the checked-in Space manifest,
creates a runtime wheel without plugin templates, and includes curated demo artifacts. It rejects
undeclared files, symlinks, model weights, pickle-like files, NPZ inputs, and videos. The generated
`space_manifest.json` records the package version, Git commit, demo-data version, wheel filename,
and wheel digest. Tests, plugin source, private experiments, server trees, and full repository media
are not uploaded.

A future `prompt-control-lab-evidence` Dataset may host only public-safe summaries, schemas, source
references, and claim boundaries. That Dataset is not required for the first Space release.
