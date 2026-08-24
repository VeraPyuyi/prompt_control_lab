from __future__ import annotations

import json
from pathlib import Path

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
    assert diagnostic["support_status"] == "requires_reanalysis"
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
