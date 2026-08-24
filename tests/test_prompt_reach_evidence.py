from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pytest import CaptureFixture

from promptcontrollab import server_evidence
from promptcontrollab.cli import main
from promptcontrollab.files import JsonDict, read_json

ADAPTERS = (
    "prompt_reachability",
    "readout_alignment",
    "prompt_routing",
    "prompt_projection",
    "prompt_stability",
)


def _write_json(path: Path, value: object, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    else:
        text = json.dumps(value, indent=2)
    path.write_text(text, encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_prompt_reach_fixture(root: Path) -> None:
    _write_json(
        root / "reachable/prompt_reachability.json",
        {
            "effective_rank": 4.25,
            "gramian_trace": 8.5,
            "sample_count": 12,
            "note": "raw prompt text must not be copied",
        },
    )
    _write_json(
        root / "controllability/readout_alignment.json",
        {
            "readout_share": 0.61,
            "cosine": 0.42,
            "exact_shift": 0.14,
        },
    )
    _write_json(
        root / "routing/prompt_routing.json",
        {
            "top_head_share": 0.37,
            "direct_share": 0.22,
            "indirect_share": 0.78,
        },
    )
    _write_json(
        root / "projection/prompt_projection.json",
        {
            "relative_gap": 0.18,
            "cosine_to_projection": 0.73,
            "magnitude_ratio": 0.81,
        },
    )
    _write_jsonl(
        root / "analysis/prompt_stability.jsonl",
        [
            {
                "prompt": "SENSITIVE_PROMPT_SENTINEL",
                "gold": "SENSITIVE_GOLD_SENTINEL",
                "prediction": "SENSITIVE_PREDICTION_SENTINEL",
                "generation": "SENSITIVE_GENERATION_SENTINEL",
                "metrics": {"repeat_score_gap": 0.04, "parameter_cosine": 0.91},
            },
            {
                "prompt": "SECOND_PRIVATE_PROMPT",
                "metrics": {"repeat_score_gap": 0.06, "parameter_cosine": 0.89},
            },
        ],
    )
    binary = root / "projection/unsafe_checkpoint.pt"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(b"not-a-pickle-and-must-never-be-deserialized")


def _scan_to(root: Path, manifest_path: Path) -> JsonDict:
    manifest = server_evidence.scan_evidence_root(root=root, profile="prompt-reach-v2")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_prompt_reach_profile_registry_exposes_five_independent_adapters() -> None:
    registry = server_evidence.evidence_profile_registry()

    assert "peoc-server" in registry
    assert "prompt-reach-v2" in registry
    assert tuple(registry["prompt-reach-v2"].adapter_names) == ADAPTERS
    assert len({type(adapter) for adapter in registry["prompt-reach-v2"].adapters}) == 5


def test_prompt_reach_scan_finds_evidence_below_an_archive_prefix_once(
    tmp_path: Path,
) -> None:
    root = tmp_path / "archive"
    evidence = (
        root
        / "_release"
        / "prompt-reach"
        / "results"
        / "reach_length"
        / "summary.json"
    )
    _write_json(
        evidence,
        {"effective_rank": 4.25, "gramian_trace": 8.5, "sample_count": 12},
    )

    manifest = server_evidence.scan_evidence_root(
        root=root,
        profile="prompt-reach-v2",
    )

    reachability = [
        row
        for row in manifest["sources"]
        if row["adapter"] == "prompt_reachability"
    ]
    assert len(reachability) == 1
    assert reachability[0]["relative_path"] == (
        "_release/prompt-reach/results/reach_length/summary.json"
    )
    assert manifest["adapter_counts"]["prompt_reachability"] == 1


def test_prompt_reach_scan_and_import_write_bounded_diagnostics(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _write_prompt_reach_fixture(root)
    manifest_path = tmp_path / "manifest.json"
    manifest = _scan_to(root, manifest_path)

    assert manifest["schema"] == "prompt_control_lab.evidence_manifest.v2"
    assert manifest["profile"] == "prompt-reach-v2"
    assert set(manifest["adapter_counts"]) == set(ADAPTERS)
    assert all("canonical_sha256" in row for row in manifest["sources"])
    pt_row = next(
        row
        for row in manifest["sources"]
        if row["media_type"] == "application/x-pytorch"
    )
    assert pt_row["load_policy"] == "metadata_only_never_deserialize"

    out_dir = tmp_path / "run"
    server_evidence.import_evidence_manifest(
        server_evidence.EvidenceImportOptions(
            manifest_path=manifest_path,
            out_dir=out_dir,
            portable=True,
        )
    )

    expected = {
        "source_gap_report.json",
        "source_reconciliation.json",
        "evidence_matrix.json",
        "interpretability_report.json",
        "interpretability_report.html",
        "claim_check.json",
        *(f"{adapter}.json" for adapter in ADAPTERS),
    }
    assert expected <= {path.name for path in out_dir.iterdir()}
    matrix = read_json(out_dir / "evidence_matrix.json")
    assert {row["adapter"] for row in matrix["diagnostics"]} == set(ADAPTERS)
    assert all(row["support_status"] == "observed" for row in matrix["diagnostics"])
    stability = read_json(out_dir / "prompt_stability.json")
    assert stability["metrics"]["repeat_score_gap"]["mean"] == 0.05
    assert stability["metrics"]["parameter_cosine"]["count"] == 2
    public_manifest = read_json(out_dir / "public_source_manifest.json")
    assert all("canonical_sha256" in row for row in public_manifest["sources"])

    rendered = "\n".join(
        path.read_text(encoding="utf-8")
        for path in out_dir.rglob("*")
        if path.is_file() and path.suffix in {".json", ".html"}
    )
    for secret in (
        "SENSITIVE_PROMPT_SENTINEL",
        "SENSITIVE_GOLD_SENTINEL",
        "SENSITIVE_PREDICTION_SENTINEL",
        "SENSITIVE_GENERATION_SENTINEL",
        "SECOND_PRIVATE_PROMPT",
    ):
        assert secret not in rendered
    assert "not-a-pickle" not in rendered


def test_prompt_reach_import_overwrite_refuses_an_unowned_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    _write_prompt_reach_fixture(root)
    manifest_path = tmp_path / "manifest.json"
    _scan_to(root, manifest_path)
    out_dir = tmp_path / "user-owned"
    out_dir.mkdir()
    marker = out_dir / "keep.txt"
    marker.write_text("do not delete", encoding="utf-8")

    with pytest.raises(ValueError, match="not a PromptControlLab evidence run"):
        server_evidence.import_evidence_manifest(
            server_evidence.EvidenceImportOptions(
                manifest_path=manifest_path,
                out_dir=out_dir,
                overwrite=True,
            )
        )

    assert marker.read_text(encoding="utf-8") == "do not delete"


def test_prompt_reach_import_parses_the_same_bytes_that_were_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    source = root / "reachable/prompt_reachability.json"
    _write_json(source, {"effective_rank": 4.0})
    manifest_path = tmp_path / "manifest.json"
    _scan_to(root, manifest_path)
    original_verify = server_evidence._verify_sources

    def verify_then_mutate(manifest: JsonDict) -> list[JsonDict]:
        rows = original_verify(manifest)
        _write_json(source, {"effective_rank": 99.0})
        return rows

    monkeypatch.setattr(server_evidence, "_verify_sources", verify_then_mutate)
    out_dir = tmp_path / "run"
    server_evidence.import_evidence_manifest(
        server_evidence.EvidenceImportOptions(
            manifest_path=manifest_path,
            out_dir=out_dir,
        )
    )

    metric = read_json(out_dir / "prompt_reachability.json")["metrics"][
        "effective_rank"
    ]
    assert metric["mean"] == 4.0


def test_prompt_reach_manifest_binds_the_canonical_digest(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _write_prompt_reach_fixture(root)
    manifest_path = tmp_path / "manifest.json"
    manifest = _scan_to(root, manifest_path)
    manifest["sources"][0]["canonical_sha256"] = "sha256:" + "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot_sha256"):
        server_evidence.import_evidence_manifest(
            server_evidence.EvidenceImportOptions(
                manifest_path=manifest_path,
                out_dir=tmp_path / "run",
            )
        )


def test_prompt_reach_unsupported_source_is_reported_without_guessing(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _write_json(
        root / "reachable/prompt_reachability.json",
        {"description": "unknown free-form schema", "prompt": "PRIVATE_TEXT"},
    )
    manifest_path = tmp_path / "manifest.json"
    _scan_to(root, manifest_path)

    out_dir = tmp_path / "run"
    server_evidence.import_evidence_manifest(
        server_evidence.EvidenceImportOptions(manifest_path=manifest_path, out_dir=out_dir)
    )

    diagnostic = read_json(out_dir / "prompt_reachability.json")
    gaps = read_json(out_dir / "source_gap_report.json")
    claims = read_json(out_dir / "claim_check.json")
    assert diagnostic["support_status"] == "requires_reanalysis"
    assert claims["status"] == "insufficient_evidence"
    assert claims["mechanism_interpretation_available"] is False
    assert "unsupported_source_format" in diagnostic["quality_flags"]
    assert any(row["adapter"] == "prompt_reachability" for row in gaps["gaps"])
    assert "PRIVATE_TEXT" not in json.dumps(gaps)


def test_evidence_merge_reconciles_canonical_json_and_marks_true_conflict(
    tmp_path: Path,
) -> None:
    primary_root = tmp_path / "primary"
    secondary_root = tmp_path / "secondary"
    value = {"effective_rank": 4.25, "gramian_trace": 8.5, "sample_count": 12}
    path = Path("reachable/prompt_reachability.json")
    _write_json(primary_root / path, value)
    _write_json(secondary_root / path, dict(reversed(list(value.items()))), compact=True)
    primary_manifest = tmp_path / "primary.json"
    secondary_manifest = tmp_path / "secondary.json"
    _scan_to(primary_root, primary_manifest)
    _scan_to(secondary_root, secondary_manifest)

    canonical_out = tmp_path / "canonical"
    server_evidence.merge_evidence_manifests(
        primary=primary_manifest,
        secondary=secondary_manifest,
        out_dir=canonical_out,
    )
    reconciliation = read_json(canonical_out / "source_reconciliation.json")
    assert reconciliation["status_counts"]["canonical_equivalent"] == 1
    assert read_json(canonical_out / "prompt_reachability.json")["support_status"] == "observed"

    _write_json(secondary_root / path, {**value, "effective_rank": 9.0})
    _scan_to(secondary_root, secondary_manifest)
    conflict_out = tmp_path / "conflict"
    server_evidence.merge_evidence_manifests(
        primary=primary_manifest,
        secondary=secondary_manifest,
        out_dir=conflict_out,
    )
    conflict = read_json(conflict_out / "source_reconciliation.json")
    assert conflict["status_counts"]["requires_reanalysis"] == 1
    diagnostic = read_json(conflict_out / "prompt_reachability.json")
    assert diagnostic["support_status"] == "requires_reanalysis"
    assert "source_conflict" in diagnostic["quality_flags"]


def test_evidence_merge_cli_writes_complete_run(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    primary_root = tmp_path / "primary"
    secondary_root = tmp_path / "secondary"
    _write_prompt_reach_fixture(primary_root)
    _write_prompt_reach_fixture(secondary_root)
    primary_manifest = tmp_path / "primary.json"
    secondary_manifest = tmp_path / "secondary.json"
    _scan_to(primary_root, primary_manifest)
    _scan_to(secondary_root, secondary_manifest)
    out_dir = tmp_path / "merged"

    assert (
        main(
            [
                "evidence",
                "merge",
                "--primary",
                str(primary_manifest),
                "--secondary",
                str(secondary_manifest),
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )
    assert (out_dir / "source_reconciliation.json").is_file()
    assert (out_dir / "interpretability_report.html").is_file()
    assert '"conflict_count": 0' in capsys.readouterr().out


def test_evidence_merge_accepts_verified_portable_runs_without_source_roots(
    tmp_path: Path,
) -> None:
    runs: list[Path] = []
    roots: list[Path] = []
    for name in ("local", "server"):
        root = tmp_path / f"{name}-source"
        roots.append(root)
        _write_prompt_reach_fixture(root)
        manifest_path = tmp_path / f"{name}-manifest.json"
        _scan_to(root, manifest_path)
        run = tmp_path / f"{name}-run"
        server_evidence.import_evidence_manifest(
            server_evidence.EvidenceImportOptions(
                manifest_path=manifest_path,
                out_dir=run,
                portable=True,
            )
        )
        runs.append(run / "portable")
    for root in roots:
        shutil.rmtree(root)

    result = server_evidence.merge_evidence_manifests(
        primary=runs[0],
        secondary=runs[1],
        out_dir=tmp_path / "portable-merged",
    )

    assert result["conflict_count"] == 0
    merged = read_json(tmp_path / "portable-merged/source_reconciliation.json")
    assert merged["status_counts"]["canonical_equivalent"] >= 1
    assert read_json(tmp_path / "portable-merged/prompt_stability.json")[
        "support_status"
    ] == "observed"


def test_portable_merge_rejects_a_tampered_derived_artifact(tmp_path: Path) -> None:
    portable_runs: list[Path] = []
    for name in ("primary", "secondary"):
        root = tmp_path / f"{name}-source"
        _write_prompt_reach_fixture(root)
        manifest_path = tmp_path / f"{name}.json"
        _scan_to(root, manifest_path)
        run = tmp_path / f"{name}-run"
        server_evidence.import_evidence_manifest(
            server_evidence.EvidenceImportOptions(
                manifest_path=manifest_path,
                out_dir=run,
                portable=True,
            )
        )
        portable_runs.append(run / "portable")
    tampered = portable_runs[1] / "prompt_reachability.json"
    payload = read_json(tampered)
    payload["metrics"]["effective_rank"]["mean"] = 999.0
    _write_json(tampered, payload)

    with pytest.raises(ValueError, match="digest mismatch"):
        server_evidence.merge_evidence_manifests(
            primary=portable_runs[0],
            secondary=portable_runs[1],
            out_dir=tmp_path / "merged",
        )


def test_portable_merge_pools_non_conflicting_numeric_summaries(tmp_path: Path) -> None:
    first_root = tmp_path / "first-source"
    second_root = tmp_path / "second-source"
    _write_json(first_root / "reachable/first.json", {"effective_rank": 1.0})
    _write_json(second_root / "reachable/second.json", {"effective_rank": 3.0})
    portable_runs: list[Path] = []
    for name, root in (("first", first_root), ("second", second_root)):
        manifest_path = tmp_path / f"{name}.json"
        _scan_to(root, manifest_path)
        run = tmp_path / f"{name}-run"
        server_evidence.import_evidence_manifest(
            server_evidence.EvidenceImportOptions(
                manifest_path=manifest_path,
                out_dir=run,
                portable=True,
            )
        )
        portable_runs.append(run / "portable")

    server_evidence.merge_evidence_manifests(
        primary=portable_runs[0],
        secondary=portable_runs[1],
        out_dir=tmp_path / "merged",
    )

    metric = read_json(tmp_path / "merged/prompt_reachability.json")["metrics"][
        "effective_rank"
    ]
    assert metric == {"count": 2, "max": 3.0, "mean": 2.0, "min": 1.0}
