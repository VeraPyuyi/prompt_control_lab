# Real PEOC Evidence Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-command, fail-closed import path that converts the real PEOC NMI replication bundle into auditable PromptControlLab evidence, reports, and UI views without overstating incomplete or negative findings.

**Architecture:** A focused `peoc_import.py` module discovers, hashes, normalizes, classifies, and optionally copies PEOC source artifacts. A separate `peoc_reporting.py` renders one structured case-study payload to Markdown and HTML. Existing evidence-card, claim-check, gap-plan, research-bundle, ReportModel, and Streamlit UI code consume the normalized `peoc_evidence.json` rather than duplicating scientific claim logic.

**Tech Stack:** Python 3.10+, standard-library JSON/hash/path/copy utilities, existing PromptControlLab reporting helpers, pytest, Ruff, strict mypy, Streamlit for the existing optional UI.

---

## File Structure

### New files

- `src/promptcontrollab/peoc_import.py`
  - PEOC bundle validation and deterministic source discovery.
  - SHA-256 provenance and optional compact-source copying.
  - Strict finite-value normalization.
  - Evidence-section classification and case-study data construction.
- `src/promptcontrollab/peoc_reporting.py`
  - English/Chinese Markdown and standalone HTML rendering from
    `research_case_study.json`.
- `tests/test_peoc_import.py`
  - Compact PEOC bundle fixture builder and core/CLI/integration tests.
- `docs/research_import_peoc.en.md`
  - English operation -> output -> interpretation tutorial.
- `docs/research_import_peoc.zh.md`
  - Chinese operation -> output -> interpretation tutorial.
- `docs/case_studies/peoc_real/README.md`
  - Public-safe explanation of the generated real-data case study.
- `docs/case_studies/peoc_real/README.zh.md`
  - Chinese public-safe explanation of the generated real-data case study.
- `docs/case_studies/peoc_real/research_case_study.json`
  - Normalized real PEOC result without local absolute paths.

### Modified files

- `src/promptcontrollab/cli.py`
  - Add `pcl research-import peoc` and orchestrate downstream evidence outputs.
- `src/promptcontrollab/report_model.py`
  - Load `peoc_evidence.json`, source manifest, and research case study.
- `src/promptcontrollab/evidence_card.py`
  - Expose imported paper evidence while keeping claim tiers fail-closed.
- `src/promptcontrollab/research_workflow.py`
  - Generate a PEOC gap plan and include PEOC artifacts in bundle indexing.
- `src/promptcontrollab/ui/data.py`
  - Recognize and normalize PEOC run artifacts.
- `src/promptcontrollab/ui/app.py`
  - Render real evidence, failed validation, and missing/unusable sections.
- `src/promptcontrollab/ui/components.py`
  - Replace fixed metric columns with an escaped responsive grid.
- `tests/test_evidence_card.py`
  - Verify PEOC evidence is visible but does not inflate claim scope.
- `tests/test_claim_check.py`
  - Verify full-research claims fail with missing/failed PEOC diagnostics.
- `tests/test_research_workflow_cli.py`
  - Verify CLI output chain and bundle inclusion.
- `tests/test_ui.py`
  - Verify PEOC normalization, status visibility, and responsive metric markup.
- `tests/test_research_positioning_docs.py`
  - Verify bilingual documentation links and claim boundaries.
- `README.md`
  - Add the real-evidence command without expanding the concise first screen.
- `README.zh.md`
  - Add the matching Chinese entry.
- `docs/research_from_paper.en.md`
  - Explain synthetic versus real evidence paths.
- `docs/research_from_paper.zh.md`
  - Add the synchronized Chinese explanation.

## Task 1: Bundle Discovery and Provenance

**Files:**
- Create: `src/promptcontrollab/peoc_import.py`
- Create: `tests/test_peoc_import.py`

- [ ] **Step 1: Write failing discovery tests**

Add a compact fixture builder and these tests:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptcontrollab.peoc_import import (
    HARD_SUMMARY,
    HETEROGENEITY_SUMMARY,
    PeocSourceOverrides,
    discover_peoc_sources,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_minimal_bundle(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "README_MANIFEST.md").write_text("# PEOC bundle\n", encoding="utf-8")
    strong = (
        root
        / "experiments"
        / "redesign_v2"
        / "results_server_pull_20260524"
        / "strong_main_grid"
    )
    _write_json(
        strong / "summary_acc_hard_test.json",
        {
            "metric": "acc_hard_test",
            "summary": [
                {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "task": "gsm8k",
                    "T": 4,
                    "L0": 4,
                    "budget": 16,
                    "method": "static",
                    "mean": 0.5,
                    "sd": 0.1,
                    "n": 10,
                }
            ],
            "tests": [],
        },
    )
    _write_json(strong / "summary_soft_segmented.json", {"summary": [{"n": 0}]})
    _write_json(
        root / "experiments" / "redesign_v2" / "stage_heterogeneity" / "shi_r27_summary.json",
        {
            "verdict": "FAIL",
            "held_spearman_rho": 0.1,
            "held_bootstrap_ci": [-0.2, 0.3],
            "cells": [],
        },
    )
    trajectory_root = root / "experiments" / "turnpike_trace" / "results_a800"
    _write_json(
        trajectory_root / "stationary_arith_Qwen__Qwen2.5-7B-Instruct_s0.json",
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "n_streams": 16,
            "hidden_dim": 3584,
            "alpha_emp_mean": 0.024,
            "R2_mean": 0.60,
        },
    )
    (
        trajectory_root / "stationary_arith_Qwen__Qwen2.5-7B-Instruct_s0.npz"
    ).write_bytes(b"stationary-array")
    _write_json(
        trajectory_root / "turnpike_gsm8k_Qwen__Qwen2.5-7B-Instruct_s0.json",
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "n_prompts": 32,
            "hidden_dim": 3584,
            "alpha_emp_mean": 0.002,
            "R2_mean": 0.09,
        },
    )
    (
        trajectory_root / "turnpike_gsm8k_Qwen__Qwen2.5-7B-Instruct_s0.npz"
    ).write_bytes(b"heterogeneous-array")
    return root


def test_discover_peoc_sources_is_deterministic_and_hashed(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")

    discovered = discover_peoc_sources(bundle, PeocSourceOverrides())

    assert discovered["schema"] == "prompt_control_lab.peoc_source_manifest.v1"
    assert discovered["bundle"]["manifest_sha256"].startswith("sha256:")
    roles = [row["role"] for row in discovered["sources"]]
    assert roles == [
        "bundle_manifest",
        "hard_test_summary",
        "soft_segmented_summary",
        "stage_heterogeneity",
        "trajectory_stationary",
        "trajectory_heterogeneous",
        "trajectory_binary",
        "trajectory_binary",
    ]
    assert all(row["sha256"].startswith("sha256:") for row in discovered["sources"])


def test_discover_peoc_sources_rejects_missing_manifest(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()

    with pytest.raises(ValueError, match="README_MANIFEST.md"):
        discover_peoc_sources(bundle, PeocSourceOverrides())


def test_discover_peoc_sources_rejects_missing_hard_summary(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    (bundle / HARD_SUMMARY).unlink()

    with pytest.raises(ValueError, match="hard-test summary"):
        discover_peoc_sources(bundle, PeocSourceOverrides())
```

- [ ] **Step 2: Run the discovery tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_peoc_import.py -k discover -v
```

Expected: collection fails because `promptcontrollab.peoc_import` does not
exist.

- [ ] **Step 3: Implement source discovery**

Create `peoc_import.py` with these public interfaces and constants:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.files import JsonDict

HARD_SUMMARY = Path(
    "experiments/redesign_v2/results_server_pull_20260524/"
    "strong_main_grid/summary_acc_hard_test.json"
)
SOFT_SUMMARY = Path(
    "experiments/redesign_v2/results_server_pull_20260524/"
    "strong_main_grid/summary_soft_segmented.json"
)
HETEROGENEITY_SUMMARY = Path(
    "experiments/redesign_v2/stage_heterogeneity/shi_r27_summary.json"
)
TRAJECTORY_ROOT = Path("experiments/turnpike_trace/results_a800")


@dataclass(frozen=True)
class PeocSourceOverrides:
    hard_summary: Path | None = None
    trajectory_files: tuple[Path, ...] = ()
    heterogeneity_summary: Path | None = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def discover_peoc_sources(
    bundle_root: Path,
    overrides: PeocSourceOverrides,
) -> JsonDict:
    root = bundle_root.resolve()
    manifest_path = root / "README_MANIFEST.md"
    if not root.is_dir():
        raise ValueError(f"PEOC bundle directory does not exist: {root}")
    if not manifest_path.is_file():
        raise ValueError(f"PEOC bundle is missing README_MANIFEST.md: {root}")
    selected = _selected_source_paths(root, overrides)
    rows = [
        _source_row(root=root, role="bundle_manifest", path=manifest_path, selection="required"),
        *[
            _source_row(root=root, role=role, path=path, selection=selection)
            for role, path, selection in selected
        ],
    ]
    return {
        "schema": "prompt_control_lab.peoc_source_manifest.v1",
        "bundle": {
            "resolved_path": str(root),
            "manifest_relative_path": "README_MANIFEST.md",
            "manifest_sha256": _sha256_file(manifest_path),
        },
        "sources": rows,
        "warnings": [],
    }
```

Implement `_selected_source_paths()` so explicit overrides win, exact default
files are used next, trajectory globs are sorted by POSIX relative path, and
missing optional sources are omitted for later classification. The hard-test
summary is required and must raise a clear error when absent. Relative override
paths resolve under the bundle root; resolved override paths outside the bundle
are rejected. For every selected trajectory JSON, include its `.npz` sibling,
when present, as a `trajectory_binary` source after the JSON rows. `_source_row()`
must record role, relative path, resolved path, byte count, hash, media type,
selection reason, and `copied_path: None`.

- [ ] **Step 4: Run the discovery tests**

Run:

```powershell
python -m pytest tests/test_peoc_import.py -k discover -v
```

Expected: both discovery tests pass.

- [ ] **Step 5: Commit discovery**

```powershell
git add src/promptcontrollab/peoc_import.py tests/test_peoc_import.py
git commit -m "Add PEOC bundle source discovery"
```

## Task 2: Evidence Normalization and Fail-closed Statuses

**Files:**
- Modify: `src/promptcontrollab/peoc_import.py`
- Modify: `tests/test_peoc_import.py`

- [ ] **Step 1: Add failing evidence-classification tests**

```python
from promptcontrollab.peoc_import import build_peoc_evidence


def _section(payload: dict[str, object], name: str) -> dict[str, object]:
    sections = payload["sections"]
    assert isinstance(sections, dict)
    section = sections[name]
    assert isinstance(section, dict)
    return section


def test_build_peoc_evidence_preserves_negative_and_unavailable_results(
    tmp_path: Path,
) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    manifest = discover_peoc_sources(bundle, PeocSourceOverrides())

    evidence = build_peoc_evidence(bundle, manifest)

    assert _section(evidence, "hard_method_evaluation")["display_status"] == "REAL"
    assert _section(evidence, "trajectory_decay")["display_status"] == "REAL"
    assert _section(evidence, "stage_heterogeneity")["display_status"] == (
        "FAILED_VALIDATION"
    )
    assert _section(evidence, "soft_segmented_evaluation")["display_status"] == (
        "UNUSABLE"
    )
    assert _section(evidence, "riccati_surrogate")["display_status"] == "MISSING"
    assert _section(evidence, "soft_to_hard")["display_status"] == "MISSING"
    boundary = evidence["claim_boundary"]
    assert isinstance(boundary, dict)
    assert boundary["full_research_claim_supported"] is False


def test_non_finite_source_values_become_null_with_warning(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    path = (
        bundle
        / "experiments"
        / "redesign_v2"
        / "stage_heterogeneity"
        / "shi_r27_summary.json"
    )
    path.write_text('{"verdict":"FAIL","held_spearman_rho":NaN}', encoding="utf-8")
    manifest = discover_peoc_sources(bundle, PeocSourceOverrides())

    evidence = build_peoc_evidence(bundle, manifest)

    heterogeneity = _section(evidence, "stage_heterogeneity")
    observations = heterogeneity["observations"]
    assert isinstance(observations, dict)
    assert observations["held_spearman_rho"] is None
    assert any(
        warning["code"] == "non_finite_value" for warning in evidence["warnings"]
    )


def test_malformed_optional_source_is_unusable_with_warning(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    heterogeneity = bundle / HETEROGENEITY_SUMMARY
    heterogeneity.write_text("[]", encoding="utf-8")
    manifest = discover_peoc_sources(bundle, PeocSourceOverrides())

    evidence = build_peoc_evidence(bundle, manifest)

    section = _section(evidence, "stage_heterogeneity")
    assert section["status"] == "unusable"
    assert any(
        warning["code"] == "invalid_optional_source"
        for warning in evidence["warnings"]
    )
```

- [ ] **Step 2: Run the normalization tests and verify failure**

Run:

```powershell
python -m pytest tests/test_peoc_import.py -k "preserves or non_finite" -v
```

Expected: FAIL because `build_peoc_evidence()` is missing.

- [ ] **Step 3: Implement recursive finite normalization and source readers**

Add:

```python
import json
import math
from typing import cast


def _read_json_object(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in PEOC source: {path}")
    return cast(JsonDict, value)


def _finite_json(
    value: object,
    *,
    source_role: str,
    json_path: str,
    warnings: list[JsonDict],
) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        warnings.append(
            {
                "code": "non_finite_value",
                "source_role": source_role,
                "json_path": json_path,
                "message": "Non-finite value was normalized to null.",
            }
        )
        return None
    if isinstance(value, dict):
        return {
            str(key): _finite_json(
                item,
                source_role=source_role,
                json_path=f"{json_path}.{key}",
                warnings=warnings,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _finite_json(
                item,
                source_role=source_role,
                json_path=f"{json_path}[{index}]",
                warnings=warnings,
            )
            for index, item in enumerate(value)
        ]
    return value
```

Add section builders with a shared constructor:

```python
def _evidence_section(
    *,
    origin: str,
    status: str,
    source_roles: list[str],
    observations: object,
    limitations: list[str],
) -> JsonDict:
    display = {
        ("real", "available"): "REAL",
        ("synthetic", "available"): "SYNTHETIC",
        ("real", "failed_validation"): "FAILED_VALIDATION",
        ("real", "unusable"): "UNUSABLE",
        ("none", "missing"): "MISSING",
    }.get((origin, status), status.upper())
    return {
        "origin": origin,
        "status": status,
        "display_status": display,
        "source_roles": source_roles,
        "observations": observations,
        "limitations": limitations,
    }
```

`build_peoc_evidence()` must:

- keep only hard-summary rows with numeric `mean`, numeric `n`, and `n > 0`
  in `observations.rows`;
- reject a malformed required hard-test summary with a concise `ValueError`;
- classify malformed optional soft, trajectory, or stage sources as unusable
  and record an `invalid_optional_source` warning instead of aborting the whole
  import;
- retain rejected rows in `observations.excluded_rows` with a reason;
- classify the soft summary as unusable when every row has `n <= 0`;
- normalize every valid trajectory file and pair stationary/heterogeneous rows
  by model and seed; when `seed` is absent in JSON, parse `_s<integer>` from the
  source filename and record `seed_source: filename`;
- select Qwen2.5-7B seed 0 as the headline pair when present;
- preserve the exact stage-heterogeneity verdict and map `FAIL` to
  `failed_validation`;
- mark Riccati and soft-to-hard missing when no source exists;
- include allowed/disallowed claim language in `claim_boundary`.

- [ ] **Step 4: Add deterministic trajectory-pairing and zero-count tests**

```python
def test_trajectory_pair_prefers_qwen_7b_seed_zero(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    manifest = discover_peoc_sources(bundle, PeocSourceOverrides())

    evidence = build_peoc_evidence(bundle, manifest)

    trajectory = _section(evidence, "trajectory_decay")
    observations = trajectory["observations"]
    assert isinstance(observations, dict)
    selected = observations["selected_pair"]
    assert isinstance(selected, dict)
    assert selected["model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert selected["seed"] == 0


def test_zero_count_hard_rows_are_retained_but_not_evidence(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    hard = bundle / HARD_SUMMARY
    payload = json.loads(hard.read_text(encoding="utf-8"))
    payload["summary"].append(
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "task": "gsm8k",
            "method": "tv_pmp",
            "mean": 0.9,
            "sd": 0.0,
            "n": 0,
        }
    )
    _write_json(hard, payload)
    manifest = discover_peoc_sources(bundle, PeocSourceOverrides())

    evidence = build_peoc_evidence(bundle, manifest)

    observations = _section(evidence, "hard_method_evaluation")["observations"]
    assert isinstance(observations, dict)
    assert len(observations["rows"]) == 1
    assert observations["excluded_rows"][0]["reason"] == "non_positive_observation_count"
```

- [ ] **Step 5: Run normalization tests**

Run:

```powershell
python -m pytest tests/test_peoc_import.py -v
```

Expected: all current PEOC tests pass.

- [ ] **Step 6: Commit normalization**

```powershell
git add src/promptcontrollab/peoc_import.py tests/test_peoc_import.py
git commit -m "Normalize PEOC research evidence"
```

## Task 3: Import Orchestration and Case-study Reports

**Files:**
- Modify: `src/promptcontrollab/peoc_import.py`
- Create: `src/promptcontrollab/peoc_reporting.py`
- Modify: `tests/test_peoc_import.py`

- [ ] **Step 1: Add failing import-output tests**

```python
from promptcontrollab.files import read_json
from promptcontrollab.peoc_import import PeocImportOptions, import_peoc_bundle


def test_import_peoc_bundle_writes_strict_self_contained_case_study(
    tmp_path: Path,
) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    out = tmp_path / "run"

    result = import_peoc_bundle(
        PeocImportOptions(bundle_root=bundle, out_dir=out, language="en")
    )

    assert result["kind"] == "peoc_research_import"
    for name in [
        "manifest.json",
        "source_manifest.json",
        "peoc_evidence.json",
        "research_case_study.json",
        "research_case_study.md",
        "research_case_study.html",
    ]:
        assert (out / name).exists()
    case_study = read_json(out / "research_case_study.json")
    assert case_study["evidence_source"] == "REAL PEOC BUNDLE"
    html_text = (out / "research_case_study.html").read_text(encoding="utf-8")
    assert str(bundle.resolve()) not in html_text
    assert "FAILED_VALIDATION" in html_text
    assert "UNUSABLE" in html_text


def test_import_requires_overwrite_for_generated_artifacts(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    out = tmp_path / "run"
    import_peoc_bundle(PeocImportOptions(bundle_root=bundle, out_dir=out))

    with pytest.raises(ValueError, match="--overwrite"):
        import_peoc_bundle(PeocImportOptions(bundle_root=bundle, out_dir=out))
```

- [ ] **Step 2: Add failing portable-copy tests**

```python
def test_portable_copy_copies_small_json_but_never_npz(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    out = tmp_path / "portable"

    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle,
            out_dir=out,
            portable=True,
        )
    )

    manifest = read_json(out / "source_manifest.json")
    assert (out / "source").is_dir()
    assert any((out / "source").rglob("*.json"))
    assert not any((out / "source").rglob("*.npz"))
    assert sum(
        1 for row in manifest["sources"] if row["role"] == "trajectory_binary"
    ) == 2
    assert all(
        row["copied_path"] is None
        for row in manifest["sources"]
        if row["role"] == "trajectory_binary"
    )
    assert all(
        row.get("copied_path") is None
        or str(row["copied_path"]).startswith("source/")
        for row in manifest["sources"]
    )
```

- [ ] **Step 3: Run import tests and verify failure**

Run:

```powershell
python -m pytest tests/test_peoc_import.py -k "import or portable" -v
```

Expected: FAIL because `PeocImportOptions`, `import_peoc_bundle`, and renderers
are missing.

- [ ] **Step 4: Implement strict artifact writing and portable copying**

Add:

```python
import shutil

MAX_PORTABLE_FILE_BYTES = 10 * 1024 * 1024
MAX_PORTABLE_TOTAL_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class PeocImportOptions:
    bundle_root: Path
    out_dir: Path
    overrides: PeocSourceOverrides = PeocSourceOverrides()
    portable: bool = False
    language: str = "en"
    overwrite: bool = False


def _write_strict_json(path: Path, payload: JsonDict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
```

`_copy_portable_sources()` must:

- copy only `.json` and `.csv`;
- preserve bundle-relative paths under `out/source/`;
- skip NPZ and unsupported extensions without reading them;
- enforce 10 MiB per-file and 50 MiB total limits;
- update `copied_path` with a forward-slash relative path;
- append stable warning objects for skipped oversized files.

- [ ] **Step 5: Implement the case-study rendering module**

Create:

```python
from __future__ import annotations

import html
from pathlib import Path

from promptcontrollab.files import JsonDict


def render_peoc_case_study_markdown(payload: JsonDict, *, language: str) -> str:
    sections = _sections(payload)
    if language == "zh":
        return _render_markdown_zh(payload, sections)
    return _render_markdown_en(payload, sections)


def render_peoc_case_study_html(payload: JsonDict, *, language: str) -> str:
    labels = _labels(language)
    return f"""<!doctype html>
<html lang="{html.escape(language)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(labels["title"])}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f5f7fb; color: #17202f;
      font: 15px/1.55 Inter, ui-sans-serif, system-ui, sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    .hero, .panel {{ background: #fff; border: 1px solid #dbe2ec;
      border-radius: 8px; padding: 22px; }}
    .grid {{ display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px; margin-top: 16px; }}
    .status {{ font-weight: 750; overflow-wrap: anywhere; }}
    .failed_validation {{ color: #a32020; }}
    .unusable, .missing {{ color: #8a4b08; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e4e8ef; padding: 9px;
      text-align: left; overflow-wrap: anywhere; }}
  </style>
</head>
<body><main>{_render_html_body(payload, labels)}</main></body>
</html>
"""
```

The renderers must include:

- real-source badge and manifest hash;
- status counts;
- hard-method rows;
- selected trajectory pair;
- stage-validation verdict;
- missing/unusable table;
- relative source paths and hashes;
- safe claim and limitations.

Every interpolated source value must pass through `html.escape`.

- [ ] **Step 6: Implement `import_peoc_bundle()`**

The function must:

1. reject pre-existing generated artifacts unless `overwrite=True`;
2. reject an output directory that resolves to the bundle root or one of the
   selected source files;
3. validate `language` as `en` or `zh`;
4. call source discovery;
5. optionally copy compact sources;
6. build normalized evidence;
7. construct `manifest.json` and `research_case_study.json`;
8. write strict JSON artifacts;
9. render Markdown and HTML;
10. return a concise import summary.

Use this manifest shape:

```python
manifest = {
    "tool": "prompt_control_lab",
    "mode": "research_import",
    "adapter": "peoc",
    "source_manifest": "source_manifest.json",
    "evidence": "peoc_evidence.json",
    "case_study": "research_case_study.json",
    "evidence_origin": "real",
    "portable": options.portable,
}
```

The case-study payload must use only relative source paths and hashes. Do not
copy `bundle.resolved_path` from the local source manifest into the case study.

- [ ] **Step 7: Run import and report tests**

Run:

```powershell
python -m pytest tests/test_peoc_import.py -v
```

Expected: all PEOC importer tests pass.

- [ ] **Step 8: Commit importer and reports**

```powershell
git add src/promptcontrollab/peoc_import.py src/promptcontrollab/peoc_reporting.py tests/test_peoc_import.py
git commit -m "Generate PEOC evidence case studies"
```

## Task 4: `pcl research-import peoc`

**Files:**
- Modify: `src/promptcontrollab/cli.py`
- Modify: `tests/test_peoc_import.py`
- Modify: `tests/test_research_workflow_cli.py`

- [ ] **Step 1: Add failing CLI parser and output tests**

```python
from promptcontrollab.cli import main


def test_research_import_peoc_cli_writes_primary_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    out = tmp_path / "run"

    assert (
        main(
            [
                "research-import",
                "peoc",
                "--bundle",
                str(bundle),
                "--out",
                str(out),
                "--language",
                "zh",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    assert "REAL PEOC BUNDLE" in stdout
    assert "FAILED_VALIDATION" in stdout
    assert str(out / "research_case_study.html") in stdout
```

Also add:

```python
def test_research_import_peoc_help_is_available(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["research-import", "peoc", "--help"])
    assert exc.value.code == 0
    assert "--hard-summary" in capsys.readouterr().out
```

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```powershell
python -m pytest tests/test_peoc_import.py -k "cli or help" -v
```

Expected: argparse rejects `research-import`.

- [ ] **Step 3: Add nested CLI parser**

In `_build_parser()`:

```python
research_import_parser = subcommands.add_parser(
    "research-import",
    help="Import native paper-replication evidence.",
)
research_import_subcommands = research_import_parser.add_subparsers(
    dest="research_import_kind",
    required=True,
)
peoc_parser = research_import_subcommands.add_parser(
    "peoc",
    help="Import a PEOC NMI replication bundle.",
)
peoc_parser.add_argument("--bundle", type=Path, required=True)
peoc_parser.add_argument("--out", type=Path, required=True)
peoc_parser.add_argument("--hard-summary", type=Path, default=None)
peoc_parser.add_argument(
    "--trajectory-file",
    type=Path,
    action="append",
    default=[],
)
peoc_parser.add_argument("--heterogeneity-summary", type=Path, default=None)
peoc_parser.add_argument("--portable", action="store_true")
peoc_parser.add_argument("--language", choices=["en", "zh"], default="en")
peoc_parser.add_argument("--overwrite", action="store_true")
peoc_parser.set_defaults(func=_cmd_research_import_peoc)
```

Add imports for `PeocImportOptions`, `PeocSourceOverrides`, and
`import_peoc_bundle`.

- [ ] **Step 4: Add the command handler**

```python
def _cmd_research_import_peoc(args: argparse.Namespace) -> None:
    payload = import_peoc_bundle(
        PeocImportOptions(
            bundle_root=args.bundle,
            out_dir=args.out,
            overrides=PeocSourceOverrides(
                hard_summary=args.hard_summary,
                trajectory_files=tuple(args.trajectory_file),
                heterogeneity_summary=args.heterogeneity_summary,
            ),
            portable=args.portable,
            language=args.language,
            overwrite=args.overwrite,
        )
    )
    print(_format_peoc_import_output(payload, language=args.language))
```

`_format_peoc_import_output()` must print the output directory, source count,
status counts, strongest safe claim, warnings, case-study path, and next command.
The Chinese branch must use Chinese explanations while preserving enum values.

- [ ] **Step 5: Run focused CLI tests**

Run:

```powershell
python -m pytest tests/test_peoc_import.py tests/test_research_workflow_cli.py -k "research_import or peoc" -v
```

Expected: new CLI tests pass and existing research CLI tests remain green.

- [ ] **Step 6: Commit CLI**

```powershell
git add src/promptcontrollab/cli.py tests/test_peoc_import.py tests/test_research_workflow_cli.py
git commit -m "Add PEOC research import command"
```

## Task 5: Evidence Card, Claim Check, Gap Plan, and Bundle Integration

**Files:**
- Modify: `src/promptcontrollab/report_model.py`
- Modify: `src/promptcontrollab/evidence_card.py`
- Modify: `src/promptcontrollab/research_workflow.py`
- Modify: `src/promptcontrollab/cli.py`
- Modify: `tests/test_evidence_card.py`
- Modify: `tests/test_claim_check.py`
- Modify: `tests/test_research_workflow_cli.py`
- Modify: `tests/test_peoc_import.py`

- [ ] **Step 1: Add failing ReportModel and claim-boundary tests**

```python
def test_report_model_loads_peoc_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    write_json(run / "peoc_evidence.json", {"schema": "prompt_control_lab.peoc_evidence.v1"})
    write_json(run / "research_case_study.json", {"kind": "peoc_research_case_study"})
    write_json(run / "source_manifest.json", {"schema": "prompt_control_lab.peoc_source_manifest.v1"})

    model = ReportModel.from_run(run)

    assert model.peoc_evidence["schema"] == "prompt_control_lab.peoc_evidence.v1"
    assert model.peoc_case_study["kind"] == "peoc_research_case_study"
    assert "peoc_evidence.json" in model.artifacts


def test_peoc_import_does_not_support_full_research_claim(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    run = tmp_path / "run"

    assert main(["research-import", "peoc", "--bundle", str(bundle), "--out", str(run)]) == 0

    claim = read_json(run / "claim_check.json")
    assert claim["requested_claim"] == "full-research"
    assert claim["status"] == "fail"
    assert "full" not in str(claim["safe_claim"]).lower()
```

- [ ] **Step 2: Add failing negative-evidence and gap tests**

```python
def test_peoc_evidence_card_exposes_real_negative_evidence_without_promoting_it(
    tmp_path: Path,
) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    run = tmp_path / "run"
    main(["research-import", "peoc", "--bundle", str(bundle), "--out", str(run)])

    card = read_json(run / "evidence_card.json")
    paper = card["sections"]["paper_replication_evidence"]
    assert paper["origin"] == "real"
    assert paper["failed_validation_count"] == 1
    assert card["evidence_tier"] != "tier_4_full_research_diagnostics"
    assert card["recommendation"] in {"needs_review", "not_supported"}

    gap = read_json(run / "research_gap_status.json")
    assert gap["status"] == "needs_work"
    assert any(row["concept"] == "Riccati surrogate" for row in gap["actions"])
```

- [ ] **Step 3: Extend ReportModel**

Add dataclass fields:

```python
source_manifest: JsonDict
peoc_evidence: JsonDict
peoc_case_study: JsonDict
```

Load:

```python
source_manifest=_read_optional(run_dir / "source_manifest.json"),
peoc_evidence=_read_optional(run_dir / "peoc_evidence.json"),
peoc_case_study=_read_optional(run_dir / "research_case_study.json"),
```

Add all PEOC JSON/Markdown/HTML names to `_existing_artifacts()`.

- [ ] **Step 4: Add a paper-replication evidence-card section**

In `build_evidence_card()`:

```python
"paper_replication_evidence": _paper_replication_evidence(model),
```

Implement:

```python
def _paper_replication_evidence(model: ReportModel) -> JsonDict:
    payload = model.peoc_evidence
    if not payload:
        return {
            "status": "skipped",
            "reason": "No peoc_evidence.json artifact found.",
        }
    sections = payload.get("sections")
    section_map = sections if isinstance(sections, dict) else {}
    statuses = [
        str(value.get("status"))
        for value in section_map.values()
        if isinstance(value, dict)
    ]
    return {
        "status": "review",
        "origin": "real",
        "available_count": statuses.count("available"),
        "failed_validation_count": statuses.count("failed_validation"),
        "unusable_count": statuses.count("unusable"),
        "missing_count": statuses.count("missing"),
        "safe_claim": _peoc_safe_claim(payload),
        "reason": (
            "Imported PEOC evidence includes real measurements and explicit "
            "negative or unavailable sections; review the case study before claiming support."
        ),
    }
```

Update Markdown/HTML section ordering to show this section. Do not count
`skipped` as missing. Do not map `failed_validation` to a passing diagnostic.

When PEOC trajectory evidence exists but `diagnostics/trajectory.json` does
not, `_hidden_state_diagnostics()` may expose it with `status: review`,
`input_source: peoc_nmi_replication_bundle`, and the selected pair. It must not
set `status: pass` because the source is a summary, not a fresh fitted
operational diagnostic.

When PEOC hard method rows include time-varying methods,
`_time_varying_control()` may expose them with `status: review` and
`evidence_kind: aggregate_summary`. It must not infer a best universal method.

- [ ] **Step 5: Add a public PEOC gap-plan writer**

In `research_workflow.py` add:

```python
def write_peoc_research_gap_plan(run_dir: Path) -> JsonDict:
    evidence = read_json(run_dir / "peoc_evidence.json")
    sections = evidence.get("sections")
    section_map = sections if isinstance(sections, dict) else {}
    actions = _peoc_gap_actions(section_map)
    payload = {
        "kind": "research_gap_plan",
        "run_dir": str(run_dir),
        "diagnostic_type": "peoc_real_evidence",
        "action_count": len(actions),
        "actions": _numbered_actions(actions),
        "boundary": (
            "This plan records missing, unusable, or failed-validation paper evidence. "
            "An artifact is not treated as positive evidence merely because its source file exists."
        ),
    }
    write_json(run_dir / "research_gap_plan.json", payload)
    (run_dir / "research_gap_plan.md").write_text(
        _render_research_gap_plan_markdown(payload),
        encoding="utf-8",
    )
    (run_dir / "research_gap_plan.html").write_text(
        render_research_gap_plan_html(payload),
        encoding="utf-8",
    )
    return payload
```

`_peoc_gap_actions()` must create actions for Riccati, soft-hard, zero-count
segmented-soft, and failed stage validation. Each action must include the
existing gap-plan keys `concept`, `artifact`, `required_inputs`, `command`, and
`explains`, so `write_research_gap_status()` can consume it unchanged.

- [ ] **Step 6: Include PEOC artifacts in research bundle indexing**

Add these names to `_bundle_artifacts()`:

```python
"source_manifest.json",
"peoc_evidence.json",
"research_case_study.json",
"research_case_study.md",
"research_case_study.html",
```

Add `research_case_study.html` to the review order when present. Update the
bundle summary so `peoc_evidence.json` sets `evidence_origin: real` but does not
override the fail-closed evidence tier from `evidence_card.json`.

- [ ] **Step 7: Complete CLI orchestration**

After `import_peoc_bundle()`:

```python
write_evidence_card(args.out)
run_claim_check(
    args.out,
    claim="full-research",
    out_path=args.out / "claim_check.json",
)
write_peoc_research_gap_plan(args.out)
write_research_gap_status(run_dir=args.out)
write_research_bundle_index(args.out)
```

Refresh the returned/printed summary after downstream files exist.

- [ ] **Step 8: Run focused evidence-chain tests**

Run:

```powershell
python -m pytest tests/test_peoc_import.py tests/test_evidence_card.py tests/test_claim_check.py tests/test_research_workflow_cli.py -v
```

Expected: all focused tests pass; existing synthetic demo still reaches its
existing tier and the real PEOC fixture does not reach full-research.

- [ ] **Step 9: Commit evidence-chain integration**

```powershell
git add src/promptcontrollab/report_model.py src/promptcontrollab/evidence_card.py src/promptcontrollab/research_workflow.py src/promptcontrollab/cli.py tests/test_peoc_import.py tests/test_evidence_card.py tests/test_claim_check.py tests/test_research_workflow_cli.py
git commit -m "Connect PEOC evidence to research claims"
```

## Task 6: Research Overview and Responsive Metric Cards

**Files:**
- Modify: `src/promptcontrollab/ui/components.py`
- Modify: `src/promptcontrollab/ui/data.py`
- Modify: `src/promptcontrollab/ui/app.py`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Add failing responsive-card test**

```python
from promptcontrollab.ui.components import metric_cards


class _MarkdownCapture:
    def __init__(self) -> None:
        self.markdown_calls: list[tuple[str, bool]] = []

    def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
        self.markdown_calls.append((body, unsafe_allow_html))


def test_metric_cards_use_wrapping_escaped_grid() -> None:
    fake = _MarkdownCapture()

    metric_cards(fake, [("<unsafe>", "a&b"), ("Long metric", 2)])

    body, unsafe = fake.markdown_calls[0]
    assert unsafe is True
    assert "repeat(auto-fit, minmax(180px, 1fr))" in body
    assert "&lt;unsafe&gt;" in body
    assert "a&amp;b" in body
```

- [ ] **Step 2: Add failing PEOC UI-data tests**

```python
from promptcontrollab.ui.data import (
    peoc_method_rows,
    peoc_status_summary,
    peoc_trajectory_rows,
)


def test_peoc_ui_rows_keep_failed_and_unusable_visible(tmp_path: Path) -> None:
    bundle = _write_minimal_bundle(tmp_path / "bundle")
    run = tmp_path / "run"
    main(["research-import", "peoc", "--bundle", str(bundle), "--out", str(run)])
    detail = load_run_detail(run)

    summary = peoc_status_summary(detail, "en")
    assert summary["origin"] == "REAL"
    assert summary["failed_validation"] == 1
    assert summary["unusable"] == 1
    assert peoc_method_rows(detail)
    trajectories = peoc_trajectory_rows(detail)
    assert {row["trace_type"] for row in trajectories} == {
        "stationary",
        "heterogeneous",
    }
```

- [ ] **Step 3: Run UI tests and verify failure**

Run:

```powershell
python -m pytest tests/test_ui.py -k "metric_cards or peoc_ui" -v
```

Expected: missing data helpers and old `st.columns()` behavior fail.

- [ ] **Step 4: Replace fixed metric columns**

Implement:

```python
def metric_cards(st: Any, cards: list[tuple[str, object]]) -> None:
    items = "".join(
        (
            '<div class="pcl-metric-card">'
            f'<div class="pcl-metric-label">{html.escape(str(label))}</div>'
            f'<div class="pcl-metric-value">{html.escape("-" if value is None else str(value))}</div>'
            "</div>"
        )
        for label, value in cards
    )
    st.markdown(
        (
            '<div class="pcl-metric-grid">'
            f"{items}</div>"
            "<style>"
            ".pcl-metric-grid{display:grid;"
            "grid-template-columns:repeat(auto-fit,minmax(180px,1fr));"
            "gap:12px;width:100%;}"
            ".pcl-metric-card{min-width:0;border:1px solid #dce3ec;"
            "border-radius:8px;padding:14px;background:#fff;}"
            ".pcl-metric-label{font-size:12px;color:#667085;overflow-wrap:anywhere;}"
            ".pcl-metric-value{margin-top:6px;font-size:22px;font-weight:700;"
            "overflow-wrap:anywhere;}"
            "</style>"
        ),
        unsafe_allow_html=True,
    )
```

Import `html` in `components.py`. Do not use `st.columns()` in this helper.

- [ ] **Step 5: Add PEOC artifacts and data helpers**

Add PEOC artifacts to `RUN_ARTIFACTS` and `RUN_LEVEL_ARTIFACTS`, expose them
from `load_run_detail()`, and implement:

```python
def peoc_status_summary(detail: JsonDict, language: str) -> JsonDict: ...
def peoc_method_rows(detail: JsonDict) -> list[JsonDict]: ...
def peoc_trajectory_rows(detail: JsonDict) -> list[JsonDict]: ...
def peoc_limitation_rows(detail: JsonDict, language: str) -> list[JsonDict]: ...
```

Helpers must return empty values for old runs and never count missing,
unusable, or failed-validation sections as available.

- [ ] **Step 6: Render PEOC evidence at the top of Research Overview**

When `peoc_evidence` is present, render in this order:

1. `REAL PEOC BUNDLE` badge and source manifest hash;
2. available / failed validation / unusable / missing metric cards;
3. hard-method table;
4. stationary-versus-heterogeneous trajectory table;
5. red failed-validation panel;
6. missing/unusable diagnostics panel;
7. limitations and link to `research_case_study.html`.

Use localized labels from `TEXT["en"]` and `TEXT["zh"]`. Keep enum values in
English for stable schemas but add plain-language explanations beside them.

- [ ] **Step 7: Run UI unit tests**

Run:

```powershell
python -m pytest tests/test_ui.py -v
```

Expected: all UI tests pass.

- [ ] **Step 8: Run a 1280-pixel browser smoke check**

Start the UI:

```powershell
pcl ui --runs runs/peoc-real --language zh --port 8511 --no-browser
```

Use Playwright to capture 1280x720 and 390x844 screenshots. Verify:

- no horizontal document overflow;
- the rightmost metric card is visible;
- status labels wrap inside cards;
- failed validation remains visible without relying only on color.

Save temporary screenshots outside the repository unless documentation needs a
new image.

- [ ] **Step 9: Commit UI**

```powershell
git add src/promptcontrollab/ui/components.py src/promptcontrollab/ui/data.py src/promptcontrollab/ui/app.py tests/test_ui.py
git commit -m "Show real PEOC evidence in the research UI"
```

## Task 7: Bilingual Onboarding and Research Positioning

**Files:**
- Create: `docs/research_import_peoc.en.md`
- Create: `docs/research_import_peoc.zh.md`
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `docs/research_from_paper.en.md`
- Modify: `docs/research_from_paper.zh.md`
- Modify: `tests/test_research_positioning_docs.py`

- [ ] **Step 1: Add failing documentation-contract tests**

```python
def test_readmes_link_real_peoc_import_without_losing_concise_first_screen() -> None:
    english = Path("README.md").read_text(encoding="utf-8")
    chinese = Path("README.zh.md").read_text(encoding="utf-8")

    assert "pcl research-import peoc" in english
    assert "pcl research-import peoc" in chinese
    assert "docs/research_import_peoc.en.md" in english
    assert "docs/research_import_peoc.zh.md" in chinese
    assert len(english.splitlines()) <= 40
    assert len(chinese.splitlines()) <= 40


def test_peoc_tutorials_explain_operation_output_meaning_and_boundary() -> None:
    for path in [
        Path("docs/research_import_peoc.en.md"),
        Path("docs/research_import_peoc.zh.md"),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "pcl research-import peoc" in text
        assert "source_manifest.json" in text
        assert "peoc_evidence.json" in text
        assert "research_case_study.html" in text
        assert "FAILED_VALIDATION" in text
        assert "UNUSABLE" in text
        assert "hidden weights" in text or "隐藏权重" in text
```

- [ ] **Step 2: Run the doc tests and verify failure**

Run:

```powershell
python -m pytest tests/test_research_positioning_docs.py -k peoc -v
```

Expected: missing tutorial and README-link assertions fail.

- [ ] **Step 3: Write the English tutorial**

Use this exact section order:

1. Who this is for.
2. What the command reads.
3. Install.
4. Step 1: locate the NMI bundle.
5. Step 2: run `pcl research-import peoc`.
6. Step 3: open `research_case_study.html`.
7. Step 4: inspect source hashes.
8. Step 5: read failed/missing evidence.
9. Step 6: continue with evidence-card, claim-check, and UI.
10. Artifact dictionary.
11. Troubleshooting.
12. Scientific boundary.

Every step uses:

```markdown
### Operation
...
### You get
...
### It tells you
...
### Next
...
```

- [ ] **Step 4: Write the synchronized Chinese tutorial**

Use plain Chinese explanations:

- `FAILED_VALIDATION`: "真实运行过，但没有通过预先设定的验证条件";
- `UNUSABLE`: "文件存在，但没有有效样本，不能当作正面证据";
- `MISSING`: "没有找到对应结果文件";
- `REAL`: "来自导入的真实实验 artifact，不等于结论已经通过".

Keep commands, file names, hashes, and enum values unchanged.

- [ ] **Step 5: Tighten README entry points**

Keep both README files at 40 lines or fewer. Add one real-evidence command near
the synthetic quickstart:

```bash
pcl research-import peoc --bundle <nmi_replication_bundle> --out runs/peoc-real
```

Explain in one sentence:

> Synthetic demo for learning; PEOC import for real replication evidence.

Chinese:

> synthetic demo 用于学习流程；PEOC import 用于读取真实复现实验证据。

Link the dedicated tutorial. Do not add a large comparison matrix to README.

- [ ] **Step 6: Update paper-to-tool mapping**

Add a small table distinguishing:

| Path | Source | Appropriate claim |
|---|---|---|
| `research-demo` | synthetic fixture | workflow demonstration only |
| `research-import peoc` | real PEOC bundle | bounded description of imported evidence |
| `diagnose` with user inputs | user-provided artifacts | scope determined by evidence card |

Add the matching Chinese table.

- [ ] **Step 7: Run documentation tests**

Run:

```powershell
python -m pytest tests/test_research_positioning_docs.py -v
```

Expected: all documentation checks pass.

- [ ] **Step 8: Commit documentation**

```powershell
git add README.md README.zh.md docs/research_import_peoc.en.md docs/research_import_peoc.zh.md docs/research_from_paper.en.md docs/research_from_paper.zh.md tests/test_research_positioning_docs.py
git commit -m "Document real PEOC evidence import"
```

## Task 8: Real Bundle Integration and Public-safe Case Study

**Files:**
- Create: `docs/case_studies/peoc_real/README.md`
- Create: `docs/case_studies/peoc_real/README.zh.md`
- Create: `docs/case_studies/peoc_real/research_case_study.json`
- Modify: `tests/test_research_positioning_docs.py`

- [ ] **Step 1: Run the importer against the actual PEOC bundle**

Run:

```powershell
python -m promptcontrollab research-import peoc `
  --bundle "D:\Vibe Research Projects\02-Prompt-Engineering-Optimal-Control\experiments\nmi_replication_bundle" `
  --out runs\peoc-real `
  --language en `
  --overwrite
```

Expected:

- source discovery succeeds;
- hard-test and trajectory sections are `REAL`;
- stage heterogeneity is `FAILED_VALIDATION`;
- segmented soft is `UNUSABLE`;
- Riccati is `MISSING`;
- full-research claim check fails;
- no source NPZ is copied.

- [ ] **Step 2: Verify authoritative values and hashes**

Run:

```powershell
python -c "import json,pathlib; p=json.loads(pathlib.Path('runs/peoc-real/peoc_evidence.json').read_text(encoding='utf-8')); print(json.dumps({'statuses':{k:v['display_status'] for k,v in p['sections'].items()},'claim':p['claim_boundary']},indent=2))"
```

Expected: output matches the status requirements above.

Run:

```powershell
python -m promptcontrollab research-bundle --run runs\peoc-real --verify --strict
```

Expected: status `pass`, zero mismatches, and zero missing hashed artifacts.

- [ ] **Step 3: Verify portable mode without copying large binary inputs**

Run:

```powershell
python -m promptcontrollab research-import peoc `
  --bundle "D:\Vibe Research Projects\02-Prompt-Engineering-Optimal-Control\experiments\nmi_replication_bundle" `
  --out runs\peoc-real-portable `
  --portable `
  --overwrite
```

Run:

```powershell
Get-ChildItem -LiteralPath runs\peoc-real-portable\source -Recurse -File |
  Where-Object { $_.Extension -eq ".npz" }
```

Expected: no output.

- [ ] **Step 4: Produce a public-safe normalized case-study artifact**

Copy only `research_case_study.json` into
`docs/case_studies/peoc_real/research_case_study.json`. Before committing,
assert:

```powershell
rg -n "D:\\\\|C:\\\\|Users\\\\|Vibe Research Projects" docs\case_studies\peoc_real
```

Expected: no matches.

The two README files must summarize:

- source bundle manifest hash;
- real hard-method evidence coverage;
- stationary and heterogeneous trajectory measurements;
- failed stage-heterogeneity validation;
- zero-count soft-segmented limitation;
- absent Riccati evidence;
- explicit statement that this is a bounded case study, not a universal
  benchmark.

Numbers must be generated from `research_case_study.json`, not typed from
memory.

- [ ] **Step 5: Add a public-case-study consistency test**

```python
def test_public_peoc_case_study_is_sanitized_and_bounded() -> None:
    path = Path("docs/case_studies/peoc_real/research_case_study.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = path.read_text(encoding="utf-8")
    assert "Vibe Research Projects" not in raw
    assert "Users\\\\" not in raw
    assert payload["evidence_source"] == "REAL PEOC BUNDLE"
    assert payload["status_counts"]["failed_validation"] >= 1
    assert payload["status_counts"]["missing"] >= 1
    assert payload["claim_boundary"]["full_research_claim_supported"] is False
```

- [ ] **Step 6: Run case-study tests**

Run:

```powershell
python -m pytest tests/test_research_positioning_docs.py -k "public_peoc" -v
```

Expected: pass.

- [ ] **Step 7: Commit public-safe case study**

```powershell
git add docs/case_studies/peoc_real tests/test_research_positioning_docs.py
git commit -m "Add bounded real PEOC case study"
```

Do not add `runs/peoc-real`, `source_manifest.json`, copied source data, NPZ
files, or absolute local paths.

## Task 9: Full Verification, Review, and Push

**Files:**
- Review all files changed since commit `e68daf6`

- [ ] **Step 1: Run the complete unit/integration suite**

```powershell
python -m pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run lint and strict typing**

```powershell
python -m ruff check .
python -m mypy src tests
```

Expected: both commands exit 0.

- [ ] **Step 3: Run repository and package health checks**

```powershell
git diff --check
python -m promptcontrollab doctor --json
```

Expected: no whitespace errors; doctor reports no required check failures.

- [ ] **Step 4: Verify documentation links and boundaries**

Run:

```powershell
python -m pytest tests/test_research_positioning_docs.py -v
rg -n "universal turnpike|always superior|proves.*hidden weights" README.md README.zh.md docs src/promptcontrollab
```

Expected: documentation tests pass; search returns no overclaiming language
outside explicit boundary examples.

- [ ] **Step 5: Run the request-code-review checklist**

Use `superpowers:requesting-code-review` over base `e68daf6` and current
`HEAD`. Review:

- source selection and override safety;
- strict JSON and non-finite handling;
- zero-count and failed-validation semantics;
- claim-check fail-closed behavior;
- HTML escaping and absolute-path redaction;
- portable-copy limits;
- UI responsive behavior;
- public case-study number/source consistency.

Fix every Critical or Important finding, rerun the affected focused tests, and
commit fixes separately.

- [ ] **Step 6: Inspect final worktree and commit history**

```powershell
git status --short
git log --oneline e68daf6..HEAD
```

Expected: clean worktree; commits correspond to discovery, normalization,
reports, CLI, evidence integration, UI, docs, and case study.

- [ ] **Step 7: Push to GitHub**

```powershell
git fetch origin
git status --short --branch
git push origin main
```

If `origin/main` advanced, inspect the remote commits and rebase without
overwriting remote work, then rerun affected verification.

- [ ] **Step 8: Verify GitHub CI**

Use `gh run list --branch main --limit 5` and `gh run watch <run-id>`.

Expected: the pushed `main` workflow completes successfully. If it fails, read
the failed job log, fix the root cause, rerun local checks, commit, push, and
watch the replacement run to completion.

## Completion Evidence

Implementation is complete only when all of the following are true:

- `pcl research-import peoc` imports the real bundle with one command.
- Every evidence section has origin, status, source roles, observations, and
  limitations.
- Stage validation remains failed, zero-count soft evidence remains unusable,
  and absent Riccati evidence remains missing.
- Source hashes are recorded and large NPZ files are not copied by default.
- Evidence-card and claim-check outputs remain fail-closed.
- The real case study is public-safe and derived from the imported JSON.
- Research Overview visibly distinguishes real, synthetic, failed, unusable,
  and missing evidence.
- Metric cards do not clip at 1280-pixel or mobile widths.
- English and Chinese onboarding remain concise and synchronized.
- Full tests, Ruff, strict mypy, doctor, bundle verification, code review, push,
  and GitHub CI all pass.
