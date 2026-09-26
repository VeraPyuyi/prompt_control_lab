"""Data-only research imports and portable evidence boundaries."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from promptcontrollab.diagnostics.research_jobs.bundles import (
    bundle_directory,
    import_bundle,
    verify_bundle,
)


def _zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            info.filename = name
            archive.writestr(info, data)
    return path


def _sample() -> bytes:
    return (Path(__file__).parents[1] / "examples/research-tools/readout.json").read_bytes()


def test_json_import_copies_inputs_and_identifies_recomputation(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(_sample())
    bundle = import_bundle(tmp_path / "workspace", source)
    assert bundle["schema_version"] == "pcl.research-bundle/v1"
    assert bundle["synthetic"] is True
    assert bundle["analyses"] == [{"kind": "readout", "input": "source.json"}]
    assert "source_path" not in bundle
    source.unlink()
    verify_bundle(tmp_path / "workspace", bundle["id"])


@pytest.mark.parametrize(
    "name", ["../escape.json", "/abs.json", "a\\b.json", "C:/x.json", "NUL.json", "a/../b.json"]
)
def test_unsafe_archive_paths_rejected_even_for_ignored_files(tmp_path: Path, name: str) -> None:
    source = _zip(tmp_path / "bad.zip", {name: b"{}"})
    with pytest.raises(ValueError, match="path"):
        import_bundle(tmp_path / "workspace", source)


def test_uploaded_python_never_copied_or_executed(tmp_path: Path) -> None:
    source = _zip(
        tmp_path / "input.zip",
        {"readout.json": _sample(), "evil.py": b"raise RuntimeError('executed')"},
    )
    bundle = import_bundle(tmp_path / "workspace", source)
    assert [row["path"] for row in bundle["files"]] == ["readout.json"]
    assert not (bundle_directory(tmp_path / "workspace", bundle["id"]) / "data/evil.py").exists()


def test_duplicate_casefold_and_symlink_members_rejected(tmp_path: Path) -> None:
    source = _zip(tmp_path / "duplicate.zip", {"A.json": b"{}", "a.json": b"{}"})
    with pytest.raises(ValueError, match="Duplicate"):
        import_bundle(tmp_path, source)
    source = tmp_path / "link.zip"
    with zipfile.ZipFile(source, "w") as archive:
        member = zipfile.ZipInfo("link.json")
        member.create_system = 3
        member.external_attr = 0o120777 << 16
        archive.writestr(member, "../outside")
    with pytest.raises(ValueError, match="link"):
        import_bundle(tmp_path, source)


def test_nonfinite_json_credentials_and_pickle_npz_rejected(tmp_path: Path) -> None:
    for body in (
        b'{"x":NaN}',
        b'{"x":1e400}',
        b'{"api_key":"private-value"}',
        b'{"api_key":"private-value","api_key":""}',
    ):
        source = tmp_path / "input.json"
        source.write_bytes(body)
        with pytest.raises(ValueError):
            import_bundle(tmp_path, source)
    np = pytest.importorskip("numpy")
    stream = io.BytesIO()
    np.savez(stream, payload=np.array([{}], dtype=object))
    source = tmp_path / "input.npz"
    source.write_bytes(stream.getvalue())
    with pytest.raises(ValueError, match=r"Object|pickle"):
        import_bundle(tmp_path, source)


def test_corruption_detected_before_analysis(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_bytes(_sample())
    bundle = import_bundle(tmp_path, source)
    directory = bundle_directory(tmp_path, bundle["id"]) / "data"
    (directory / "input.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        verify_bundle(tmp_path, bundle["id"])


def test_csv_summary_does_not_invent_paired_statistics(tmp_path: Path) -> None:
    source = tmp_path / "summary.csv"
    source.write_text("model,mean\na,0.5\nb,0.8\n", encoding="utf-8")
    bundle = import_bundle(tmp_path, source)
    assert bundle["analyses"] == [{"kind": "inventory"}]
    assert bundle["capabilities"][0]["level"] == "summary_only"


def test_supplied_portable_manifest_hash_must_match(tmp_path: Path) -> None:
    manifest = {
        "schema_version": "pcl.research-bundle/v1",
        "files": [{"path": "data.json", "sha256": "0" * 64}],
    }
    source = _zip(
        tmp_path / "bad.zip",
        {"research-bundle.json": json.dumps(manifest).encode(), "data.json": _sample()},
    )
    with pytest.raises(ValueError, match="manifest"):
        import_bundle(tmp_path, source)


def test_missing_historical_receipts_are_not_silently_certified(tmp_path: Path) -> None:
    document = json.loads(_sample())
    document["evidence_status"] = "independent_confirmation"
    document.pop("evidence_receipts", None)
    source = tmp_path / "assertion.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    bundle = import_bundle(tmp_path, source)
    assert bundle["analyses"] == [{"kind": "inventory"}]
    assert bundle["capabilities"][0]["level"] == "provenance_missing"


def test_nested_npz_arrays_share_one_expansion_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    np = pytest.importorskip("numpy")
    from promptcontrollab.diagnostics.research_jobs import bundles

    payload = io.BytesIO()
    np.savez_compressed(payload, values=np.zeros(6000, dtype=np.uint8))
    source = _zip(
        tmp_path / "arrays.zip", {"one.npz": payload.getvalue(), "two.npz": payload.getvalue()}
    )
    monkeypatch.setattr(bundles, "MAX_EXPANDED", 10_000)
    with pytest.raises(ValueError, match=r"expanded|expansion"):
        import_bundle(tmp_path, source)


def test_csv_and_array_credential_fields_are_not_exportable(tmp_path: Path) -> None:
    source = tmp_path / "credentials.csv"
    source.write_text("api_key,score\nprivate-test-credential,0.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="credentials"):
        import_bundle(tmp_path, source)
    np = pytest.importorskip("numpy")
    array = tmp_path / "credentials.npz"
    np.savez(array, api_key=np.array(["private-test-credential"]))
    with pytest.raises(ValueError, match="credentials"):
        import_bundle(tmp_path, array)
