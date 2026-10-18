# Publication status — single source of truth

Source version: **0.3.0a2**. This branch builds local preview artifacts. Public PyPI availability and a GitHub Release are **not verified or claimed** by this implementation. Publication remains external pending; no upload, tag, release or remote push was performed.

Install a locally built `promptcontrollab-0.3.0a2-py3-none-any.whl` using its actual path. Run `python -m build --no-isolation`, record the SHA256 of the final wheel, and install it in a fresh virtual environment from a clean directory. Use `pcl --help`, `pcl doctor`, and the offline experiment import/export/replay workflow for smoke verification.

Five first-time human trials remain **pending**. No volunteers were recruited and no results are inferred from automated tests. Live provider evaluation and new paid benchmark runs remain pending.

Standalone HTML uses inline CSS and embedded text; static parsing can verify absence of script, external styles, image URLs and network resources. This is a structural offline check, not a claim of file:// visual verification in every browser.
