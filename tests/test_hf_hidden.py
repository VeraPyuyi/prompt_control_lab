from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.files import read_json
from promptcontrollab.hf_hidden import load_prompt_texts


def test_load_prompt_texts_reads_jsonl_and_plain_text(tmp_path: Path) -> None:
    jsonl = tmp_path / "prompts.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps({"id": "a", "input": "First prompt"}),
                json.dumps({"id": "b", "prompt": "Second prompt"}),
                json.dumps({"id": "c", "text": "Third prompt"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    text = tmp_path / "prompts.txt"
    text.write_text("Alpha\n\nBeta\n", encoding="utf-8")

    assert load_prompt_texts(jsonl, max_items=2) == ["First prompt", "Second prompt"]
    assert load_prompt_texts(text, max_items=None) == ["Alpha", "Beta"]


def test_cli_extract_hidden_writes_npz_and_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab.cli import main
    from promptcontrollab.cli.handlers import diagnostics as cli_diagnostics

    prompts = tmp_path / "prompts.txt"
    out_path = tmp_path / "hidden_states.npz"
    prompts.write_text("alpha\nbeta\n", encoding="utf-8")

    def fake_extract_hidden_states(**kwargs: Any) -> dict[str, Any]:
        import numpy as np

        np.savez(kwargs["out_path"], states=np.array([[1.0, 0.0], [0.5, 0.2], [0.1, 0.1]]))
        payload = {
            "kind": "hidden_state_extraction",
            "model_id": kwargs["model_id"],
            "prompts_path": str(kwargs["prompts_path"]),
            "out_path": str(kwargs["out_path"]),
            "states_shape": [3, 2],
            "pool": kwargs["pool"],
            "layer": kwargs["layer"],
        }
        metadata_path = Path(str(kwargs["out_path"]) + ".metadata.json")
        metadata_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(cli_diagnostics, "extract_hidden_states", fake_extract_hidden_states)

    assert (
        main(
            [
                "extract-hidden",
                "--model",
                "tiny-model",
                "--prompts",
                str(prompts),
                "--out",
                str(out_path),
                "--pool",
                "last-token",
                "--layer",
                "-1",
            ]
        )
        == 0
    )

    assert out_path.exists()
    metadata = read_json(Path(str(out_path) + ".metadata.json"))
    assert metadata["kind"] == "hidden_state_extraction"
    assert metadata["model_id"] == "tiny-model"
    assert metadata["states_shape"] == [3, 2]
