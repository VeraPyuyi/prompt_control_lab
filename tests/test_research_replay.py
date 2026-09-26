"""Synthetic checks for the separate frozen statistical replay protocol."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest


def test_entry_import_is_lazy() -> None:
    import subprocess

    code = (
        "import sys; from promptcontrollab.diagnostics.research_replay "
        "import describe_bundle; assert 'numpy' not in sys.modules"
    )
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


def test_profile_rejects_scientific_override_and_paths(tmp_path: Path) -> None:
    from promptcontrollab.diagnostics.research_replay import describe_bundle, run_suite

    assert describe_bundle(tmp_path)["suites"] == []
    for profile in ({"draws": 20}, {"readout_models": ["../escape"]}):
        with pytest.raises(ValueError):
            run_suite(tmp_path, "readout", tmp_path / "output", profile=profile)


@pytest.mark.parametrize("module", ["independent", "gsm8k", "readout"])
def test_auc_ties_and_undefined(module: str) -> None:
    pytest.importorskip("numpy")
    kernel = importlib.import_module(f"promptcontrollab.diagnostics.research_replay.{module}")
    assert kernel.weighted_auc([0, 1], [1.0, 1.0]) == 0.5
    assert kernel.weighted_auc([0, 0], [1.0, 2.0]) is None
    assert kernel.weighted_auc([0, 1], [0.0, 1.0], [0.0, 1.0]) is None


def gsm_inputs() -> dict[str, Any]:
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(82)
    return {
        "score_arrays": {name: rng.normal(size=(16, 20)) for name in ("primary", "norm", "loss")},
        "risk_change_labels": np.tile([0, 1] * 10, (16, 1)),
        "pair_ids": [f"pair-{i:02d}" for i in range(16)],
        "pairing_types": ["adjacent_seed"] * 8 + ["selection_loss"] * 8,
        "fixed_predictions": {
            family: {
                p: np.full(16, i / 10)
                for i, p in enumerate(("full", "cheap", "uniform_mean", "zero"))
            }
            for family in ("primary", "norm")
        },
    }


def test_gsm_shared_stratified_streams_and_fixed_forecasts() -> None:
    import hashlib

    np = pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay.gsm8k import forecast_mae_statistics

    inputs = gsm_inputs()
    first = forecast_mae_statistics(**inputs, n_bootstrap=40, chunk_size=7)
    second = forecast_mae_statistics(**inputs, n_bootstrap=40, chunk_size=19)
    assert first == second
    assert first["bonferroni_family_size"] == 22
    assert first["common_valid_pairs_per_type"] == {"adjacent_seed": 8, "selection_loss": 8}
    streams = np.random.SeedSequence(20260911).spawn(3)
    strata = [
        np.random.default_rng(stream).multinomial(8, np.full(8, 1 / 8), size=40)
        for stream in streams[1:]
    ]
    pair_counts = np.concatenate(strata, axis=1)
    np.testing.assert_array_equal(pair_counts[:, :8].sum(axis=1), np.full(40, 8))
    np.testing.assert_array_equal(pair_counts[:, 8:].sum(axis=1), np.full(40, 8))
    expected_digest = hashlib.sha256(pair_counts.astype("<u4").tobytes()).hexdigest()
    assert first["resampling"]["pair_count_sha256"] == expected_digest
    before = {
        f: {k: v.copy() for k, v in ps.items()} for f, ps in inputs["fixed_predictions"].items()
    }
    inputs["risk_change_labels"] = np.zeros((16, 20))
    undefined = forecast_mae_statistics(**inputs, n_bootstrap=32)
    assert undefined["common_valid_original_pairs"] == 0
    assert undefined["comparisons"]["primary"]["cheap"]["interval"] is None
    assert not undefined["forecasts_refit"]
    for f, predictors in before.items():
        for predictor, value in predictors.items():
            np.testing.assert_array_equal(inputs["fixed_predictions"][f][predictor], value)


def test_cross_streams_keep_fresh_and_source_pair_draws_identical() -> None:
    np = pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay.crossed import make_bootstrap_weights

    source = make_bootstrap_weights({"old": 8, "new": 12}, 16, draws=32, seed=29)
    fresh = make_bootstrap_weights({"fresh": 8}, 16, draws=32, seed=29)
    np.testing.assert_array_equal(source.pair_weights, fresh.pair_weights)
    assert not np.array_equal(source.item_weights["old"], fresh.item_weights["fresh"])
    assert source.pair_weights.shape == (32, 16)


def test_compare_keeps_rng_digest_and_coverage() -> None:
    from promptcontrollab.diagnostics.research_replay import compare, scientific_view

    expected = {"schema": "old", "value": 0.5, "rng_digest": "a", "coverage": 0.95}
    actual = {"schema": "new", "value": 0.5 + 1e-13, "rng_digest": "b", "coverage": 0.9}
    errors = compare(scientific_view(actual), scientific_view(expected))
    assert len(errors) == 2
    assert any("rng_digest" in error for error in errors)
    assert any("coverage" in error for error in errors)
    assert compare(True, 1)


def make_readout_bundle(root: Path) -> None:
    np = pytest.importorskip("numpy")
    inputs = root / "bootstrap_replay" / "inputs"
    inputs.mkdir(parents=True)
    (inputs.parent / "profile.json").write_text(
        json.dumps({"readout_models": ["model_a", "model_b"]})
    )
    for model in ("model_a", "model_b"):
        np.savez(
            inputs / f"readout_{model}.npz",
            pair_ids=np.array([f"pair-{i:02d}" for i in range(19)]),
            item_ids=np.array([f"item-{i:03d}" for i in range(400)]),
            labels=np.zeros((19, 400), dtype=np.uint8),
            scores=np.ones((19, 3, 400)),
        )


def test_formal_outputs_and_expected_read_after_compute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay import describe_bundle, readout, run_suite

    bundle = tmp_path / "bundle"
    make_readout_bundle(bundle)
    description = describe_bundle(bundle)
    assert description["suites"] == ["readout"]
    assert description["analyses"][0]["kind"] == "bootstrap"
    retained = bundle / "paper/data/reviewer_supplement/readout/interactions.json"
    retained.parent.mkdir(parents=True)
    retained.write_text("invalid until computation finishes")
    original = readout.interaction_statistics
    results: list[Any] = []

    def record(*args: Any, **kwargs: Any) -> Any:
        values = original(*args, **kwargs)
        model = ("model_a", "model_b")[len(results)]
        results.append(
            [dict(v, model=model, pairs=[f"pair-{i:02d}" for i in range(19)]) for v in values]
        )
        if len(results) == 2:
            retained.write_text(json.dumps(results[0] + results[1]))
        return values

    monkeypatch.setattr(readout, "interaction_statistics", record)
    output = tmp_path / "output"
    receipt = run_suite(bundle, "readout", output)
    assert receipt["status"] == "PASS"
    assert receipt["draws"] == 20000
    assert receipt["correction_family"] == 22
    assert receipt["primary_intervals_replayed"] == 4
    assert all((output / name).is_file() for name in receipt["files"].values())


def test_npz_schema_is_validated_before_coercion(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay import run_suite

    make_readout_bundle(tmp_path / "bundle")
    path = tmp_path / "bundle/bootstrap_replay/inputs/readout_model_a.npz"
    with np.load(path, allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    arrays["labels"] = np.full((19, 400), 0.25)
    np.savez(path, **arrays)
    with pytest.raises(ValueError, match="binary"):
        run_suite(tmp_path / "bundle", "readout", tmp_path / "output")


def independent_rows() -> list[dict[str, Any]]:
    from promptcontrollab.diagnostics.research_replay.independent import CONDITIONS

    rows = []
    for model in ("model_a", "model_b", "model_c"):
        for parser, budget in CONDITIONS:
            for pair in range(3):
                for item in range(8):
                    risk = item % 2
                    rows.append(
                        {
                            "model": model,
                            "pair": f"pair-{pair}",
                            "item_id": f"item-{item}",
                            "item_index": item,
                            "parser": parser,
                            "budget": budget,
                            "risk_source": 0,
                            "risk_target": risk,
                            "parse_source": True,
                            "parse_target": True,
                            "correct_source": True,
                            "correct_target": not bool(risk),
                            "first_legal_source": True,
                            "first_legal_target": True,
                            "y": risk,
                            "channel": "correctness" if risk else "stable",
                            "primary": float(item),
                            "norm": float(item % 3),
                            "loss": float(7 - item),
                        }
                    )
    return rows


def test_independent_complete_matrix_and_coverage_gates() -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay.independent import analyze_rows, validate_rows

    rows = independent_rows()
    result = analyze_rows(rows, strict_contract=False, bootstrap_draws=32)
    assert not result["production_analysis"]
    assert result["primary"]["family_comparisons"] == 18
    assert len(result["secondary"]["models"]["model_a"]) == 18
    families = result["primary"]["models"]["model_a"]["families"]
    for family in families.values():
        assert not family["inferential"]
        assert "fewer_than_12_common_pairs" in family["ineligibility_reasons"]
        assert len(family["leave_one_pair_out"]) == 3
    with pytest.raises(ValueError, match="Missing row/cell"):
        validate_rows(rows[:-1], strict_contract=False)
    with pytest.raises(ValueError, match="differing endpoint risks"):
        validate_rows([dict(rows[0], y=1)], strict_contract=False)
    with pytest.raises(ValueError, match="production contract"):
        validate_rows(rows)


def crossed_panels(*, production: bool = False) -> dict[str, Any]:
    np = pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay.crossed import Panel

    rng = np.random.default_rng(918)
    result: dict[str, Any] = {}
    for model in ("model_a", "model_b"):
        result[model] = {}
        for cohort, count in (("old", 3), ("new", 16 if production else 4)):
            result[model][cohort] = {}
            for split in ("old", "new", "fresh"):
                item_count = (400 if split == "new" else 200) if production else 10
                result[model][cohort][split] = Panel(
                    tuple(f"{cohort}-{i}" for i in range(count)),
                    tuple(f"{split}-item-{i}" for i in range(item_count)),
                    rng.normal(size=(3, count, item_count)),
                    np.tile([0, 1] * (item_count // 2), (18, count, 1)),
                )
    return result


def test_cross_and_confirmation_use_fixed_references_and_frozen_predictions() -> None:
    import copy

    np = pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay.crossed import (
        Panel,
        analyze_confirm,
        analyze_cross,
        make_predictions,
    )

    panels = crossed_panels()
    source = analyze_cross(panels, draws=32)
    predictions = make_predictions(panels)
    locked = copy.deepcopy(predictions)
    fresh = analyze_confirm(panels, predictions, draws=32)
    assert predictions == locked
    assert source["primary"]["family_comparisons"] == 24
    assert fresh["primary"]["family_comparisons"] == 24
    assert fresh["predictions_and_uniform_baseline_fixed"]
    assert source["validation"]["old_reference_count"] == 3
    for model in panels:
        for cohort in panels[model]:
            panel = panels[model][cohort]["fresh"]
            panels[model][cohort]["fresh"] = Panel(
                panel.pair_ids, panel.item_ids, panel.scores, np.zeros_like(panel.labels)
            )
    undefined = analyze_confirm(panels, predictions, draws=32)
    assert predictions == locked
    assert (
        undefined["primary"]["models"]["model_a"]["families"]["primary"]["estimands"]["mean_T"][
            "interval"
        ]
        is None
    )
    bad = dict(predictions, content_sha256="0" * 64)
    with pytest.raises(ValueError, match="integrity digest"):
        analyze_confirm(panels, bad, draws=32)


def test_readout_resamples_new_pairs_and_keeps_family_22() -> None:
    np = pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay.readout import interaction_statistics

    labels = np.tile([0, 1] * 10, (19, 1))
    scores = np.random.default_rng(702).normal(size=(19, 3, 20))
    result = interaction_statistics(labels, scores, draws=32)
    assert len(result) == 2
    for row in result:
        assert row["bonferroni_family"] == 22
        assert row["common_new_pairs"] == 16
        assert row["old_reference_complete"]
        assert row["bootstrap_draws"] == 32
        assert len(row["leave_one_new_pair_out"]) == 16
    labels[0] = 0
    assert all(row["ci"] is None for row in interaction_statistics(labels, scores, draws=32))


def test_npz_rejects_object_arrays_and_claimed_large_headers(tmp_path: Path) -> None:
    import io
    import zipfile

    np = pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay import run_suite

    root = tmp_path / "bundle"
    make_readout_bundle(root)
    path = root / "bootstrap_replay/inputs/readout_model_a.npz"
    with np.load(path, allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    arrays["scores"] = np.empty((19, 3, 400), dtype=object)
    np.savez(path, **arrays)
    with pytest.raises(ValueError, match="dtype"):
        run_suite(root, "readout", tmp_path / "output")
    with zipfile.ZipFile(path) as archive:
        members = {item.filename: archive.read(item) for item in archive.infolist()}
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(
        header,
        {
            "descr": "<f8",
            "fortran_order": False,
            "shape": (2**40, 3, 400),
        },
    )
    members["scores.npy"] = header.getvalue()
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    with pytest.raises(ValueError, match="shape"):
        run_suite(root, "readout", tmp_path / "output")


def test_missing_numpy_gives_actionable_error_without_loading_kernels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    from promptcontrollab.diagnostics.research_replay import _numpy

    original = builtins.__import__

    def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "numpy":
            raise ImportError("synthetic optional dependency absent")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    with pytest.raises(RuntimeError, match=r"promptcontrollab\[research\]"):
        _numpy()


def test_unverified_output_ignores_uploaded_source_and_refuses_overwrite(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay import run_suite

    root = tmp_path / "bundle"
    make_readout_bundle(root)
    marker = tmp_path / "executed.txt"
    (root / "bootstrap_replay/run.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
    )
    output = tmp_path / "output"
    receipt = run_suite(root, "readout", output)
    assert receipt["status"] == "COMPUTED"
    assert not receipt["retained_expected_checked"]
    assert receipt["primary_intervals_defined"] == 0
    assert not marker.exists()
    with pytest.raises(FileExistsError):
        run_suite(root, "readout", output)
    with pytest.raises(ValueError, match="outside"):
        run_suite(root, "readout", root / "output")


def test_readout_json_snapshot_mismatch_is_not_a_pass(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay import run_suite

    root = tmp_path / "bundle"
    make_readout_bundle(root)
    expected = root / "paper/data/reviewer_supplement/readout/interactions.json"
    expected.parent.mkdir(parents=True)
    expected.write_text("[]")
    receipt = run_suite(root, "readout", tmp_path / "output")
    assert receipt["status"] == "FAIL"
    assert receipt["retained_expected_checked"]
    assert receipt["mismatches"]


def test_fingerprints_enforce_size_limit_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    from promptcontrollab.diagnostics import research_replay

    path = tmp_path / "input.json"
    path.write_bytes(b"synthetic")
    assert research_replay._file_sha256(path) == hashlib.sha256(b"synthetic").hexdigest()
    monkeypatch.setattr(research_replay, "_MAX_DATA_BYTES", 4)
    with pytest.raises(ValueError, match="size limit"):
        research_replay._file_sha256(path)


@pytest.mark.parametrize(
    "mutation", ["short_old", "short_new", "overlap", "false_flag", "string_flag"]
)
def test_confirmation_rejects_forged_source_layout(mutation: str) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay.crossed import (
        _digest,
        _validate,
        _validate_predictions,
        make_predictions,
    )

    panels = crossed_panels(production=True)
    predictions = make_predictions(panels)
    fresh = _validate(panels, ("fresh",))
    _validate_predictions(predictions, fresh)
    source = predictions["validation"]["item_ids_by_split"]
    if mutation == "short_old":
        source["old"] = ["synthetic-short-old"]
    elif mutation == "short_new":
        source["new"] = ["synthetic-short-new"]
    elif mutation == "overlap":
        source["new"][0] = source["old"][0]
    elif mutation == "false_flag":
        predictions["production_source_layout"] = False
    else:
        predictions["production_source_layout"] = "yes"
    predictions["content_sha256"] = _digest(
        {k: v for k, v in predictions.items() if k != "content_sha256"}
    )
    with pytest.raises(ValueError, match=r"source.*(layout|disjoint)"):
        _validate_predictions(predictions, fresh)


def test_small_confirmation_fixture_still_requires_disjoint_source_items() -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay.crossed import (
        _digest,
        _validate,
        _validate_predictions,
        make_predictions,
    )

    panels = crossed_panels()
    predictions = make_predictions(panels)
    fresh = _validate(panels, ("fresh",))
    assert predictions["production_source_layout"] is False
    _validate_predictions(predictions, fresh)
    source = predictions["validation"]["item_ids_by_split"]
    source["new"][0] = source["old"][0]
    predictions["content_sha256"] = _digest(
        {k: v for k, v in predictions.items() if k != "content_sha256"}
    )
    with pytest.raises(ValueError, match=r"source.*disjoint"):
        _validate_predictions(predictions, fresh)


def test_gsm_json_rejects_lossy_integer_scores(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_replay import _gsm_inputs

    pairs = [
        {
            "pair_id": f"pair-{i:02d}",
            "pairing_type": "adjacent_seed" if i < 8 else "selection_loss",
            "item_ids": [f"item-{j:03d}" for j in range(200)],
            "scores": {name: [2**53, 2**53 + 1] * 100 for name in ("primary", "norm", "loss")},
            "behavior": {"risk_change": [0, 1] * 100},
            "predictions": {
                family: {predictor: 0.0 for predictor in ("full", "cheap", "uniform_mean", "zero")}
                for family in ("primary", "norm")
            },
        }
        for i in range(16)
    ]
    path = tmp_path / "paper/data/gsm8k/compact_case.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"pairs": pairs}))
    with pytest.raises(ValueError, match="exactly representable"):
        _gsm_inputs(tmp_path)
    for row in pairs:
        row["scores"] = {name: [2**53 - 1, 2**53] * 100 for name in ("primary", "norm", "loss")}
    path.write_text(json.dumps({"pairs": pairs}))
    assert _gsm_inputs(tmp_path)["score_arrays"]["primary"].shape == (16, 200)


@pytest.mark.parametrize(
    "target",
    ["readout.json", "readout_report.json", "readout_primary_intervals.csv", "readout_check.json"],
)
def test_result_created_during_computation_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics import research_replay

    root, output = tmp_path / "bundle", tmp_path / "output"
    make_readout_bundle(root)
    original = research_replay._compute

    def race(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        output.mkdir(exist_ok=True)
        (output / target).write_bytes(b"concurrently-created-content")
        return result

    monkeypatch.setattr(research_replay, "_compute", race)
    with pytest.raises(FileExistsError):
        research_replay.run_suite(root, "readout", output)
    assert (output / target).read_bytes() == b"concurrently-created-content"


def test_same_suite_admission_blocks_competing_compute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics import research_replay

    root, output = tmp_path / "bundle", tmp_path / "output"
    make_readout_bundle(root)
    original = research_replay._compute
    calls = 0

    def competing(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            with pytest.raises(FileExistsError):
                research_replay.run_suite(root, "readout", output)
        return original(*args, **kwargs)

    monkeypatch.setattr(research_replay, "_compute", competing)
    receipt = research_replay.run_suite(root, "readout", output)
    assert calls == 1
    assert receipt["status"] == "COMPUTED"
    assert not list(output.glob("*.lock"))


def test_failed_compute_releases_admission_for_whole_suite_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics import research_replay

    root, output = tmp_path / "bundle", tmp_path / "output"
    make_readout_bundle(root)
    original = research_replay._compute

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("synthetic computation failure")

    monkeypatch.setattr(research_replay, "_compute", broken)
    with pytest.raises(ValueError, match="synthetic computation failure"):
        research_replay.run_suite(root, "readout", output)
    assert not list(output.glob("*.lock"))
    monkeypatch.setattr(research_replay, "_compute", original)
    assert research_replay.run_suite(root, "readout", output)["status"] == "COMPUTED"


def test_changed_original_input_cannot_publish_misbound_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics import research_replay

    root, output = tmp_path / "bundle", tmp_path / "output"
    make_readout_bundle(root)
    original = research_replay._compute
    snapshot_roots = []

    def change_original(bundle: Path, *args: Any, **kwargs: Any) -> Any:
        snapshot_roots.append(bundle)
        source = root / "bootstrap_replay/inputs/readout_model_b.npz"
        with source.open("ab") as handle:
            handle.write(b"concurrent input mutation")
        return original(bundle, *args, **kwargs)

    monkeypatch.setattr(research_replay, "_compute", change_original)
    with pytest.raises(ValueError, match="input changed"):
        research_replay.run_suite(root, "readout", output)
    assert snapshot_roots[0] != root
    assert not snapshot_roots[0].exists()
    assert not (output / "readout_check.json").exists()


def test_computation_hashes_match_private_snapshot_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics import research_replay

    root, output = tmp_path / "bundle", tmp_path / "output"
    make_readout_bundle(root)
    original = research_replay._compute
    captured: dict[str, str] = {}
    snapshots = []

    def observe(bundle: Path, suite: str, settings: dict[str, Any]) -> Any:
        snapshots.append(bundle)
        for relative in research_replay._required(settings, suite):
            captured[relative] = hashlib.sha256((bundle / relative).read_bytes()).hexdigest()
        assert json.loads((bundle / "bootstrap_replay/profile.json").read_text()) == settings
        return original(bundle, suite, settings)

    monkeypatch.setattr(research_replay, "_compute", observe)
    receipt = research_replay.run_suite(root, "readout", output)
    assert all(receipt["input_sha256"][key] == value for key, value in captured.items())
    assert snapshots[0] != root
    assert not snapshots[0].exists()


def test_retained_expected_hash_matches_the_single_compared_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics import research_replay

    root, output = tmp_path / "bundle", tmp_path / "output"
    make_readout_bundle(root)
    expected = root / research_replay.EXPECTED["readout"]
    expected.parent.mkdir(parents=True)
    result = research_replay._compute(root, "readout", research_replay._profile(root))
    expected_bytes = json.dumps(result).encode()
    expected.write_bytes(expected_bytes)
    read_bytes = research_replay._read_bytes
    reads = 0

    def change_after_read(path: Path) -> bytes:
        nonlocal reads
        contents = read_bytes(path)
        if path.samefile(expected):
            reads += 1
            expected.write_bytes(b"[]")
        return contents

    monkeypatch.setattr(research_replay, "_read_bytes", change_after_read)
    receipt = research_replay.run_suite(root, "readout", output)
    assert receipt["status"] == "PASS"
    assert receipt["retained_expected_sha256"] == hashlib.sha256(expected_bytes).hexdigest()
    assert reads == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows extended path regression")
def test_long_windows_snapshot_preserves_containment_and_cleanup(tmp_path: Path) -> None:
    from promptcontrollab.diagnostics import research_replay

    parent = tmp_path / ("workspace-" + "a" * 80) / ("research-" + "b" * 80)
    bundle, output = parent / "bundle", parent / "nested" / "results"
    extended_bundle = research_replay._absolute_path(bundle)
    make_readout_bundle(extended_bundle)
    assert len(str(bundle / "bootstrap_replay/inputs/readout_model_a.npz")) > 260
    receipt = research_replay.run_suite(bundle, "readout", output)
    extended_output = research_replay._absolute_path(output)
    assert receipt["status"] == "COMPUTED"
    assert all((extended_output / name).is_file() for name in receipt["files"].values())
    assert not list(extended_output.glob(".*-inputs-*"))
    assert not (extended_output / ".readout.running.lock").exists()
    with pytest.raises(ValueError, match="outside"):
        research_replay.run_suite(bundle, "readout", bundle / "output")


def test_suite_admission_preserves_foreign_lease_and_allows_other_suites(tmp_path: Path) -> None:
    from promptcontrollab.diagnostics.research_replay import _suite_admission

    lock = tmp_path / ".readout.running.lock"
    lock.write_bytes(b"another invocation owns this lease")
    with pytest.raises(FileExistsError), _suite_admission(tmp_path, "readout", {}):
        pytest.fail("A competing readout must not be admitted")
    assert lock.read_bytes() == b"another invocation owns this lease"
    with _suite_admission(tmp_path, "gsm8k", {}):
        assert (tmp_path / ".gsm8k.running.lock").is_file()
    assert lock.read_bytes() == b"another invocation owns this lease"
    assert not (tmp_path / ".gsm8k.running.lock").exists()


def test_original_profile_change_prevents_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    from promptcontrollab.diagnostics import research_replay

    root, output = tmp_path / "bundle", tmp_path / "output"
    make_readout_bundle(root)
    original = research_replay._compute

    def change_profile(*args: Any, **kwargs: Any) -> Any:
        (root / "bootstrap_replay/profile.json").write_text(
            json.dumps({"readout_models": ["another_a", "another_b"]})
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(research_replay, "_compute", change_profile)
    with pytest.raises(ValueError, match="input changed"):
        research_replay.run_suite(root, "readout", output)
    assert not (output / "readout_check.json").exists()
