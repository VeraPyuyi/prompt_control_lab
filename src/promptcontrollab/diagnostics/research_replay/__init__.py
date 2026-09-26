"""Data-only replay of the frozen, 20,000-draw statistical protocol.

The optional NumPy dependency is loaded only when a suite runs. Uploaded scripts
are never imported. This protocol is separate from the legacy descriptive
``research_tools.bootstrap`` diagnostic.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import tempfile
import time
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

PROTOCOL = "pcl.research_replay.frozen_shared_bootstrap.v1"
SUITES = ("independent", "cross", "confirmation", "gsm8k", "readout")
DRAWS = 20_000
SEEDS = dict.fromkeys(SUITES[:3], 20260908) | {"gsm8k": 20260911, "readout": 2026091201}
FAMILIES = {"independent": 18, "cross": 24, "confirmation": 24, "gsm8k": 22, "readout": 22}
EXPECTED = {
    "independent": "paper/data/analysis.json",
    "cross": "paper/data/cross_analysis.json",
    "confirmation": "paper/data/confirm_analysis.json",
    "gsm8k": "paper/data/gsm8k/analysis/statistics_512.json",
    "readout": "paper/data/reviewer_supplement/readout/interactions.json",
}
# Public model identifiers describe the historical layout, never scientific data.
# A data-only profile can replace identifiers; it cannot change the protocol.
DEFAULT_PROFILE: dict[str, Any] = {
    "independent_models": ["ministral", "granite", "qwen35"],
    "cross_models": ["granite", "ministral"],
    "readout_models": ["ministral", "granite"],
    "gsm8k_model": "ministral",
}
_PROFILE_PATH = "bootstrap_replay/profile.json"
_INPUTS = "bootstrap_replay/inputs/"
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_MAX_DATA_BYTES = 64 * 1024 * 1024


def _absolute_path(path: Path) -> Path:
    """Keep long Windows snapshots usable without changing containment semantics."""
    resolved = path.resolve()
    value = str(resolved)
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return resolved
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def _safe_path(root: Path, relative: str) -> Path:
    root = _absolute_path(root)
    path = root / relative
    if path.resolve() != root and root not in path.resolve().parents:
        raise ValueError("Replay data must remain inside the bundle")
    current = path
    while current != root:
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("Replay data cannot use symbolic links or junctions")
        current = current.parent
    return path


def _read_bytes(path: Path) -> bytes:
    if path.stat().st_size > _MAX_DATA_BYTES:
        raise ValueError("Replay file exceeds the data size limit")
    with path.open("rb") as handle:
        contents = handle.read(_MAX_DATA_BYTES + 1)
    if len(contents) > _MAX_DATA_BYTES:
        raise ValueError("Replay file exceeds the data size limit")
    return contents


def _decode_json(contents: bytes) -> Any:

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value: str) -> Any:
        raise ValueError("JSON numbers must be finite or explicit null")

    return json.loads(contents.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)


def _load_json(path: Path) -> Any:
    return _decode_json(_read_bytes(path))


def _profile(root: Path, supplied: dict[str, Any] | None = None) -> dict[str, Any]:
    saved = _safe_path(root, _PROFILE_PATH)
    settings = supplied if supplied is not None else (_load_json(saved) if saved.is_file() else {})
    if not isinstance(settings, dict) or set(settings) - set(DEFAULT_PROFILE):
        raise ValueError("Profile permits model identities only; statistical settings are frozen")
    result = dict(DEFAULT_PROFILE) | settings
    for key, count in (("independent_models", 3), ("cross_models", 2), ("readout_models", 2)):
        values = result[key]
        if (
            not isinstance(values, list)
            or len(values) != count
            or any(not isinstance(value, str) or not _MODEL.fullmatch(value) for value in values)
            or len(set(values)) != count
        ):
            raise ValueError(f"{key} requires {count} distinct safe model identities")
    if not isinstance(result["gsm8k_model"], str) or not _MODEL.fullmatch(result["gsm8k_model"]):
        raise ValueError("gsm8k_model requires a safe model identity")
    return {key: list(value) if isinstance(value, list) else value for key, value in result.items()}


def _required(profile: dict[str, Any], suite: str) -> list[str]:
    if suite == "independent":
        return [f"{_INPUTS}independent_{model}.npz" for model in profile["independent_models"]]
    if suite in ("cross", "confirmation"):
        splits = ("old", "new") if suite == "cross" else ("fresh",)
        names = [
            f"{_INPUTS}crossed_{model}_{cohort}_{split}.npz"
            for model in profile["cross_models"]
            for cohort in ("old", "new")
            for split in splits
        ]
        return names + ([f"{_INPUTS}crossed_predictions.json"] if suite == "confirmation" else [])
    if suite == "gsm8k":
        return ["paper/data/gsm8k/compact_case.json"]
    return [f"{_INPUTS}readout_{model}.npz" for model in profile["readout_models"]]


def describe_bundle(root: Path) -> dict[str, Any]:
    """Recognize exact safe data paths without NumPy or executing bundle code.

    Presence is discovery, not scientific validation. Full dimensions, dtypes,
    identities and endpoint consistency are checked before each computation.
    """
    root = Path(root)
    profile = _profile(root)
    analyses, missing = [], {}
    for suite in SUITES:
        required = _required(profile, suite)
        absent = [name for name in required if not _safe_path(root, name).is_file()]
        if absent:
            missing[suite] = absent
        else:
            analyses.append(
                {
                    "kind": "bootstrap",
                    "suite": suite,
                    "protocol": PROTOCOL,
                    "draws": DRAWS,
                    "correction_family": FAMILIES[suite],
                    "required_inputs": required,
                    "retained_expected_available": _safe_path(root, EXPECTED[suite]).is_file(),
                }
            )
    return {
        "protocol": PROTOCOL,
        "suites": [record["suite"] for record in analyses],
        "analyses": analyses,
        "missing_inputs": missing,
        "capabilities": {
            "statistical_replay": bool(analyses),
            "requires_numpy": True,
            "executes_uploaded_code": False,
            "refits_forecasts": False,
            "input_validation": "before_computation",
            "resume_unit": "whole_suite_from_seed",
            "historical_prediction_lock_certified": False,
        },
    }


def _numpy() -> Any:
    try:
        import numpy
    except ImportError as error:
        raise RuntimeError(
            "Statistical replay requires the optional promptcontrollab[research] extra"
        ) from error
    return numpy


def _npz(root: Path, name: str, shapes: dict[str, tuple[int, ...]]) -> dict[str, Any]:
    """Bound decompression and inspect NPY headers before array allocation."""
    np = _numpy()
    path = _safe_path(root, name)
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        expected_names = {f"{key}.npy" for key in shapes}
        if len(members) != len(shapes) or {item.filename for item in members} != expected_names:
            raise ValueError("NPZ array schema does not match the registered suite")
        if sum(item.file_size for item in members) > _MAX_DATA_BYTES:
            raise ValueError("Expanded NPZ exceeds the data size limit")
        for item in members:
            key = item.filename[:-4]
            with archive.open(item) as handle:
                version = np.lib.format.read_magic(handle)
                if version == (1, 0):
                    shape, _, dtype = np.lib.format.read_array_header_1_0(handle)
                elif version == (2, 0):
                    shape, _, dtype = np.lib.format.read_array_header_2_0(handle)
                else:
                    raise ValueError("Unsupported NPY header version")
                if shape != shapes[key] or dtype.hasobject or dtype.kind not in "biufUS":
                    raise ValueError(f"NPZ shape or dtype invalid for {key}")
                if dtype.itemsize > 4096 or math.prod(shape) * dtype.itemsize > _MAX_DATA_BYTES:
                    raise ValueError("NPZ array allocation exceeds the data size limit")
                if math.prod(shape) * dtype.itemsize != item.file_size - handle.tell():
                    raise ValueError("NPZ array byte length does not match its header")
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in shapes}
    for key in ("pair_ids", "item_ids"):
        values = arrays[key].tolist()
        if any(not isinstance(value, str) or not value for value in values) or len(
            set(values)
        ) != len(values):
            raise ValueError(f"{key} must contain unique nonempty string identities")
    for key, values in arrays.items():
        if key in ("pair_ids", "item_ids"):
            continue
        if values.dtype.kind not in "biuf" or not np.isfinite(values).all():
            raise ValueError(f"{key} must contain finite numerical values")
        if key == "scores":
            if values.dtype.kind in "iu" and any(
                int(a) != int(b)
                for a, b in zip(values.flat, values.astype(float).flat, strict=True)
            ):
                raise ValueError("Integer scores must be exactly representable as float64")
        elif key == "channel":
            if not np.isin(values, (0, 1, 2)).all():
                raise ValueError("channel must contain registered channel codes")
        elif not np.isin(values, (0, 1)).all():
            raise ValueError(f"{key} must contain binary values")
    return arrays


def _independent_rows(root: Path, profile: dict[str, Any]) -> Iterator[dict[str, Any]]:
    from .independent import CONDITIONS, SCORES

    shapes = {"pair_ids": (16,), "item_ids": (400,), "scores": (16, 400, 3)}
    shapes.update(
        dict.fromkeys(
            ("y", "channel", "parse_source", "parse_target", "risk_source", "risk_target"),
            (18, 16, 400),
        )
    )
    shapes.update(dict.fromkeys(("first_legal_source", "first_legal_target"), (16, 400)))
    for model in profile["independent_models"]:
        data = _npz(root, f"{_INPUTS}independent_{model}.npz", shapes)
        for cell, (parser, budget) in enumerate(CONDITIONS):
            for p, pair in enumerate(data["pair_ids"].tolist()):
                for i, item in enumerate(data["item_ids"].tolist()):
                    row = {
                        "model": model,
                        "pair": pair,
                        "item_id": item,
                        "item_index": i,
                        "parser": parser,
                        "budget": budget,
                        "y": int(data["y"][cell, p, i]),
                        "channel": ("stable", "parse", "correctness")[
                            int(data["channel"][cell, p, i])
                        ],
                    }
                    for side in ("source", "target"):
                        parsed = bool(data[f"parse_{side}"][cell, p, i])
                        risk = int(data[f"risk_{side}"][cell, p, i])
                        row.update(
                            {
                                f"parse_{side}": parsed,
                                f"risk_{side}": risk,
                                f"correct_{side}": bool(not risk) if parsed else None,
                                f"first_legal_{side}": bool(data[f"first_legal_{side}"][p, i]),
                            }
                        )
                    row.update(
                        {name: float(data["scores"][p, i, k]) for k, name in enumerate(SCORES)}
                    )
                    yield row


def _panels(root: Path, profile: dict[str, Any], suite: str) -> dict[str, Any]:
    from .crossed import Panel

    result: dict[str, Any] = {}
    for model in profile["cross_models"]:
        result[model] = {}
        for cohort, pairs in (("old", 3), ("new", 16)):
            result[model][cohort] = {}
            for split in ("fresh",) if suite == "confirmation" else ("old", "new"):
                items = 400 if split == "new" else 200
                data = _npz(
                    root,
                    f"{_INPUTS}crossed_{model}_{cohort}_{split}.npz",
                    {
                        "pair_ids": (pairs,),
                        "item_ids": (items,),
                        "scores": (3, pairs, items),
                        "labels": (18, pairs, items),
                    },
                )
                result[model][cohort][split] = Panel(
                    tuple(data["pair_ids"].tolist()),
                    tuple(data["item_ids"].tolist()),
                    data["scores"],
                    data["labels"],
                )
    return result


def _gsm_inputs(root: Path) -> dict[str, Any]:
    """Validate frozen confirmation inputs and their linked prediction coordinates."""
    from .gsm8k import FAMILIES, PAIR_TYPES, PREDICTORS

    np = _numpy()
    document = _load_json(_safe_path(root, "paper/data/gsm8k/compact_case.json"))
    try:
        rows = document["pairs"]
        if not isinstance(rows, list) or len(rows) != 16:
            raise ValueError("The frozen GSM suite requires 16 pairs")
        ids = rows[0]["item_ids"]
        if (
            not isinstance(ids, list)
            or len(ids) != 200
            or len(set(ids)) != 200
            or any(not isinstance(value, str) or not value for value in ids)
        ):
            raise ValueError("The frozen GSM suite requires 200 unique shared item identities")
        if any(row["item_ids"] != ids for row in rows):
            raise ValueError("GSM shared item coordinates changed")
        if any(row["pairing_type"] not in PAIR_TYPES for row in rows):
            raise ValueError("Unknown GSM pairing type")
        for row in rows:
            labels = row["behavior"]["risk_change"]
            if len(labels) != 200 or any(type(v) is not int or v not in (0, 1) for v in labels):
                raise ValueError("GSM labels must be aligned binary integers")
            for key in ("primary", "norm", "loss"):
                values = row["scores"][key]
                if len(values) != 200 or any(
                    type(v) not in (int, float) or not math.isfinite(v) for v in values
                ):
                    raise ValueError("GSM scores must be aligned finite numeric values")
                if any(type(v) is int and int(float(v)) != v for v in values):
                    raise ValueError("Integer scores must be exactly representable as float64")
            for family in FAMILIES:
                for predictor in PREDICTORS:
                    value = row["predictions"][family][predictor]
                    if value is not None and (
                        type(value) not in (int, float) or not math.isfinite(value)
                    ):
                        raise ValueError("Fixed predictions must be finite numbers or null")
        return {
            "score_arrays": {
                key: np.asarray([row["scores"][key] for row in rows])
                for key in ("primary", "norm", "loss")
            },
            "risk_change_labels": np.asarray([row["behavior"]["risk_change"] for row in rows]),
            "pair_ids": [row["pair_id"] for row in rows],
            "pairing_types": [row["pairing_type"] for row in rows],
            "fixed_predictions": {
                family: {
                    predictor: np.asarray(
                        [row["predictions"][family][predictor] for row in rows], dtype=float
                    )
                    for predictor in PREDICTORS
                }
                for family in FAMILIES
            },
        }
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed GSM saved-score case") from error


def _compute(root: Path, suite: str, profile: dict[str, Any]) -> Any:
    if suite == "independent":
        from .independent import analyze_rows

        return analyze_rows(
            _independent_rows(root, profile), model_keys=tuple(profile["independent_models"])
        )
    if suite == "cross":
        from .crossed import analyze_cross

        return analyze_cross(_panels(root, profile, suite))
    if suite == "confirmation":
        from .crossed import analyze_confirm

        return analyze_confirm(
            _panels(root, profile, suite),
            _load_json(_safe_path(root, f"{_INPUTS}crossed_predictions.json")),
        )
    if suite == "gsm8k":
        from .gsm8k import forecast_mae_statistics

        return forecast_mae_statistics(**_gsm_inputs(root))
    from .readout import interaction_statistics

    result: list[dict[str, Any]] = []
    shared_items = None
    for model in profile["readout_models"]:
        data = _npz(
            root,
            f"{_INPUTS}readout_{model}.npz",
            {
                "pair_ids": (19,),
                "item_ids": (400,),
                "labels": (19, 400),
                "scores": (19, 3, 400),
            },
        )
        items = data["item_ids"].tolist()
        if shared_items is not None and items != shared_items:
            raise ValueError("Readout shared item coordinates changed")
        shared_items = items
        values = interaction_statistics(data["labels"], data["scores"])
        for value in values:
            value.update(model=model, pairs=data["pair_ids"].tolist())
        result.extend(values)
    return result


def scientific_view(value: Any) -> Any:
    """Exclude only software/schema and derivative prediction-container metadata."""
    if isinstance(value, dict):
        return {
            key: scientific_view(item)
            for key, item in value.items()
            if key not in {"schema", "numpy_version", "frozen_prediction_sha256"}
        }
    if isinstance(value, list):
        return [scientific_view(item) for item in value]
    return value


def compare(actual: Any, expected: Any, path: str = "") -> list[str]:
    """Compare every scientific field, retaining RNG hashes and coverage gates."""
    errors = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            errors.append(path + ": keys differ")
        else:
            for key in expected:
                errors.extend(compare(actual[key], expected[key], path + "/" + str(key)))
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            errors.append(path + ": length differs")
        else:
            for i, (left, right) in enumerate(zip(actual, expected, strict=True)):
                errors.extend(compare(left, right, path + "/" + str(i)))
    elif type(expected) in (float, int):
        if type(actual) not in (float, int) or not math.isclose(
            actual, expected, rel_tol=1e-12, abs_tol=1e-12
        ):
            errors.append(path + ": numerical value differs")
    elif type(actual) is not type(expected) or actual != expected:
        errors.append(path + ": value differs")
    return errors


def primary_rows(suite: str, result: Any, *, gsm8k_model: str = "model") -> list[dict[str, Any]]:
    """Project the primary endpoints without dropping null or descriptive rows."""
    rows = []

    def add(model: str, score: str, estimand: str, point: Any, interval: Any, valid: Any) -> None:
        rows.append(
            {
                "study": suite,
                "model": model,
                "score": score,
                "estimand": estimand,
                "estimate": point,
                "lower": None if interval is None else interval[0],
                "upper": None if interval is None else interval[1],
                "valid_draws": valid,
                "requested_draws": DRAWS,
                "correction_family": FAMILIES[suite],
            }
        )

    if suite in ("independent", "cross", "confirmation"):
        selected = {
            "independent": ("native_gap", "stopped_gap", "gap_change"),
            "cross": ("P", "Q", "H"),
            "confirmation": ("mean_T", "improvement_over_zero", "improvement_over_constant"),
        }[suite]
        for model, record in result["primary"]["models"].items():
            for score, family in record["families"].items():
                for name in selected:
                    value = family["estimands"][name]
                    add(model, score, name, value["point"], value["interval"], value["valid_draws"])
    elif suite == "gsm8k":
        for score, comparisons in result["comparisons"].items():
            for baseline, value in comparisons.items():
                add(
                    gsm8k_model,
                    score,
                    "MAE improvement over " + baseline,
                    value["mae_improvement"],
                    value["interval"],
                    value["valid_bootstrap_draws"],
                )
    else:
        for value in result:
            fraction = value["valid_bootstrap_fraction"]
            add(
                value["model"],
                value["alternative"],
                "readout group interaction",
                value["estimate"],
                value["ci"],
                None if fraction is None else round(DRAWS * fraction),
            )
    return rows


def _write_json(path: Path, value: Any) -> None:
    contents = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(contents)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(_read_bytes(path)).hexdigest()


@contextmanager
def _suite_admission(output: Path, suite: str, files: dict[str, str]) -> Iterator[None]:
    """Admit one writer per suite; never reclaim another process's lease."""
    output.mkdir(parents=True, exist_ok=True)
    lock = _safe_path(output, f".{suite}.running.lock")
    identity = None
    try:
        with lock.open("x", encoding="utf-8") as handle:
            identity = os.fstat(handle.fileno())
            handle.write(json.dumps({"suite": suite, "pid": os.getpid()}))
            handle.flush()
            if any(_safe_path(output, name).exists() for name in files.values()):
                raise FileExistsError("Suite output already exists; use a new output directory")
            yield
    finally:
        # A killed process leaves its lease in its abandoned attempt directory.
        # On ordinary exits, remove only the exact lease this call created.
        if identity is not None and lock.exists() and os.path.samestat(identity, lock.stat()):
            lock.unlink()


def run_suite(
    bundle_dir: Path, suite: str, out_dir: Path, *, profile: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Compute a complete suite, then read retained outputs for comparison.

    Output must be outside the bundle and suite filenames must be unused. A
    parent process can cancel this CPU-only call and restart the entire suite
    with the same seed. No resumable partial draw state is claimed.
    """
    root, output = _absolute_path(Path(bundle_dir)), _absolute_path(Path(out_dir))
    if suite not in SUITES:
        raise ValueError("Unknown statistical replay suite")
    saved_profile = _safe_path(root, _PROFILE_PATH)
    profile_bytes = (
        _read_bytes(saved_profile) if profile is None and saved_profile.is_file() else None
    )
    settings = _profile(
        root,
        _decode_json(profile_bytes)
        if profile_bytes is not None
        else (profile if profile is not None else {}),
    )
    if output == root or root in output.parents:
        raise ValueError("Replay output must be outside the input bundle")
    required = _required(settings, suite)
    if any(not _safe_path(root, name).is_file() for name in required):
        raise ValueError(f"Incomplete saved-score input layout for {suite}")
    files = {
        "scientific": f"{suite}.json",
        "check": f"{suite}_check.json",
        "report": f"{suite}_report.json",
        "primary_intervals": f"{suite}_primary_intervals.csv",
    }
    with _suite_admission(output, suite, files):
        return _run_admitted(
            root, suite, output, settings, required, files, profile_bytes, profile is None
        )


def _run_admitted(
    root: Path,
    suite: str,
    output: Path,
    settings: dict[str, Any],
    required: list[str],
    files: dict[str, str],
    profile_bytes: bytes | None,
    uses_saved_profile: bool,
) -> dict[str, Any]:
    """Compute a frozen suite before reading expected results and publishing verification."""
    np = _numpy()
    started = time.perf_counter()
    input_hashes = {}
    # Only required data and the normalized settings enter this owned snapshot.
    # In particular, retained expectations and uploaded source are never copied.
    with tempfile.TemporaryDirectory(prefix=f".{suite}-inputs-", dir=output) as temporary:
        snapshot = _absolute_path(Path(temporary))
        if snapshot.parent != output or root == snapshot or root in snapshot.parents:
            raise ValueError("Replay snapshot must remain in the external output directory")
        for relative in required:
            contents = _read_bytes(_safe_path(root, relative))
            target = _safe_path(snapshot, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(contents)
            input_hashes[relative] = hashlib.sha256(contents).hexdigest()
        settings_path = _safe_path(snapshot, _PROFILE_PATH)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(settings_path, settings)
        profile_sha256 = _file_sha256(settings_path)
        result = _compute(snapshot, suite, settings)
    if profile_bytes is not None:
        input_hashes[_PROFILE_PATH] = hashlib.sha256(profile_bytes).hexdigest()
    # This is deliberately the first read of retained expected results.
    expected_path = _safe_path(root, EXPECTED[suite])
    checked = expected_path.is_file()
    expected_bytes = _read_bytes(expected_path) if checked else None
    mismatches = (
        compare(scientific_view(result), scientific_view(_decode_json(expected_bytes)))
        if expected_bytes is not None
        else []
    )
    rows = primary_rows(suite, result, gsm8k_model=settings["gsm8k_model"])
    receipt = {
        "protocol": PROTOCOL,
        "suite": suite,
        "status": ("FAIL" if mismatches else "PASS") if checked else "COMPUTED",
        "draws": DRAWS,
        "seed": SEEDS[suite],
        "correction_family": FAMILIES[suite],
        "seconds": time.perf_counter() - started,
        "numpy_version": np.__version__,
        "comparison_tolerance": 1e-12,
        "retained_expected_checked": checked,
        "retained_expected_sha256": hashlib.sha256(expected_bytes).hexdigest()
        if expected_bytes is not None
        else None,
        "mismatches": mismatches,
        "primary_intervals_replayed": len(rows),
        "primary_intervals_defined": sum(row["lower"] is not None for row in rows),
        "input_sha256": input_hashes,
        "profile": settings,
        "profile_sha256": profile_sha256,
        "files": files,
        "anonymous_input_integrity_is_not_a_historical_prediction_lock": True,
    }
    report = {
        "protocol": PROTOCOL,
        "suite": suite,
        "status": receipt["status"],
        "primary_intervals": rows,
        "scope": "Statistical replay from saved scores and labels with frozen forecasts.",
        "limits": [
            "Does not reconstruct scores from raw tensors or labels from tokens.",
            "Input integrity does not certify historical prediction-lock chronology.",
            "Coverage gates and descriptive/undefined results remain in the scientific output.",
            "The retained correction family of 22 is not reduced to the implemented comparisons.",
        ],
    }
    for relative, digest in input_hashes.items():
        if _file_sha256(_safe_path(root, relative)) != digest:
            raise ValueError("Replay input changed during computation; no results were published")
    if uses_saved_profile and profile_bytes is None and _safe_path(root, _PROFILE_PATH).exists():
        raise ValueError("Replay input changed during computation; a profile appeared")
    _write_json(_safe_path(output, files["scientific"]), result)
    _write_json(_safe_path(output, files["report"]), report)
    with _safe_path(output, files["primary_intervals"]).open(
        "x", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _write_json(_safe_path(output, files["check"]), receipt)
    return receipt
