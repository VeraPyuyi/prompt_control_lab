from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.files import write_jsonl
from promptcontrollab.riccati import analyze_riccati
from promptcontrollab.soft_hard import analyze_soft_hard
from promptcontrollab.trajectory import analyze_trajectory
from promptcontrollab.tv_soft import summarize_tv_soft


def test_soft_hard_trajectory_and_riccati(tmp_path: Path) -> None:
    np: Any = pytest.importorskip("numpy")
    soft_path = tmp_path / "soft.npz"
    vocab_path = tmp_path / "vocab.npz"
    states_path = tmp_path / "states.npz"
    matrices_path = tmp_path / "matrices.npz"
    np.savez(soft_path, soft=np.array([[0.9, 0.1], [0.1, 0.8]]))
    np.savez(vocab_path, embeddings=np.array([[1.0, 0.0], [0.0, 1.0]]))
    np.savez(states_path, states=np.array([[3.0, 0.0], [2.0, 0.0], [1.2, 0.0], [1.0, 0.0]]))
    np.savez(
        matrices_path,
        A=np.array([[0.8]]),
        B=np.array([[1.0]]),
        Q=np.array([[1.0]]),
        R=np.array([[1.0]]),
    )

    soft = analyze_soft_hard(soft_path=soft_path, vocab_path=vocab_path, out_dir=tmp_path / "diag")
    trajectory = analyze_trajectory(states_path=states_path, out_dir=tmp_path / "diag")
    riccati = analyze_riccati(matrices_path=matrices_path, out_dir=tmp_path / "diag")

    assert soft["risk"] == "low"
    assert trajectory["log_decay_slope"] < 0
    assert riccati["stable_surrogate"] is True


def test_tv_soft_summary(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.jsonl"
    write_jsonl(
        predictions,
        [
            {
                "id": "a",
                "output": "x",
                "expected": "x",
                "score": 0.5,
                "slice": "s",
                "method": "static",
            },
            {
                "id": "b",
                "output": "x",
                "expected": "x",
                "score": 1.0,
                "slice": "s",
                "method": "time_varying",
            },
            {
                "id": "c",
                "output": "x",
                "expected": "x",
                "score": 0.25,
                "slice": "s",
                "method": "shuffled_tv",
            },
        ],
    )
    summary = summarize_tv_soft(predictions_path=predictions, out_dir=tmp_path / "diag")
    deltas = summary["delta_vs_baseline"]
    assert isinstance(deltas, dict)
    assert deltas["time_varying"] == 0.5


def test_npz_diagnostics_disable_pickle_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    np: Any = pytest.importorskip("numpy")
    soft_path = tmp_path / "soft.npz"
    vocab_path = tmp_path / "vocab.npz"
    states_path = tmp_path / "states.npz"
    matrices_path = tmp_path / "matrices.npz"
    np.savez(soft_path, soft=np.array([[0.9, 0.1]]))
    np.savez(vocab_path, embeddings=np.array([[1.0, 0.0]]))
    np.savez(states_path, states=np.array([[3.0], [2.0], [1.0]]))
    np.savez(
        matrices_path,
        A=np.array([[0.8]]),
        B=np.array([[1.0]]),
        Q=np.array([[1.0]]),
        R=np.array([[1.0]]),
    )
    original_load = np.load
    allow_pickle_values: list[object] = []

    def tracked_load(*args: object, **kwargs: object) -> Any:
        allow_pickle_values.append(kwargs.get("allow_pickle"))
        return original_load(*args, **kwargs)

    monkeypatch.setattr(np, "load", tracked_load)
    analyze_soft_hard(soft_path=soft_path, vocab_path=vocab_path, out_dir=tmp_path / "diag")
    analyze_trajectory(states_path=states_path, out_dir=tmp_path / "diag")
    analyze_riccati(matrices_path=matrices_path, out_dir=tmp_path / "diag")

    assert allow_pickle_values
    assert all(value is False for value in allow_pickle_values)
