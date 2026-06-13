from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json


def test_research_demo_generates_paper_diagnostics(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-demo"

    assert main(["research-demo", "--out", str(run_dir)]) == 0

    assert (run_dir / "inputs" / "soft_prompt.npz").exists()
    assert (run_dir / "inputs" / "vocab_embeddings.npz").exists()
    assert (run_dir / "inputs" / "hidden_states.npz").exists()
    assert (run_dir / "inputs" / "hidden_states.npz.metadata.json").exists()
    assert (run_dir / "inputs" / "surrogate_mats.npz").exists()
    assert (run_dir / "inputs" / "method_predictions.jsonl").exists()

    diagnostics = run_dir / "diagnostics"
    for name in ["soft_hard.json", "trajectory.json", "riccati.json", "tv_soft.json"]:
        assert (diagnostics / name).exists()

    summary = read_json(run_dir / "research_diagnostics.json")
    assert summary["kind"] == "research_diagnostics"
    assert summary["mode"] == "demo"
    assert summary["inputs"]["hidden_states"]["source"] == "synthetic_demo"
    assert summary["inputs"]["hidden_states"]["states_shape"] == [6, 2]
    assert set(summary["diagnostics"]) == {"soft_hard", "trajectory", "riccati", "tv_soft"}
    concept_names = {item["concept"] for item in _mapping(summary)}
    assert "tri-split withheld protocol" in concept_names
    assert "HuggingFace hidden-state extraction" in concept_names
    assert "Riccati surrogate" in concept_names
    assert "time-varying soft-control lane" in concept_names
    report = (run_dir / "research_diagnostics.md").read_text(encoding="utf-8")
    assert "Research Diagnostics Report" in report
    assert "Hidden-state input" in report
    assert "soft-to-hard projection gap" in report
    assert "Riccati surrogate" in report


def test_diagnose_reuses_research_demo_inputs(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-demo"
    assert main(["research-demo", "--out", str(run_dir)]) == 0
    for path in (run_dir / "diagnostics").glob("*.json"):
        path.unlink()
    (run_dir / "research_diagnostics.json").unlink()
    (run_dir / "research_diagnostics.md").unlink()

    assert main(["diagnose", "--run", str(run_dir)]) == 0

    summary = read_json(run_dir / "research_diagnostics.json")
    assert summary["mode"] == "diagnose"
    assert summary["diagnostics"]["trajectory"]["turnpike_like_signal"] is True
    assert (run_dir / "diagnostics" / "soft_hard.json").exists()
    assert (run_dir / "diagnostics" / "tv_soft.json").exists()


def test_diagnose_requires_enough_inputs(tmp_path: Path) -> None:
    assert main(["diagnose", "--out", str(tmp_path / "diag")]) == 2


def _mapping(summary: dict[str, Any]) -> list[dict[str, str]]:
    value = summary["paper_mapping"]
    assert isinstance(value, list)
    return value
