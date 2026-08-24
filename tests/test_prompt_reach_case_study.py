from __future__ import annotations

import hashlib
import json
from pathlib import Path

CASE_ROOT = Path("docs/case_studies/prompt_reach_v2")
PUBLIC_ROOT = CASE_ROOT / "public"


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_prompt_reach_public_case_is_portable_and_bounded() -> None:
    source_manifest = _read_json(PUBLIC_ROOT / "public_source_manifest.json")
    matrix = _read_json(PUBLIC_ROOT / "evidence_matrix.json")
    reconciliation = _read_json(PUBLIC_ROOT / "source_reconciliation.json")
    claims = _read_json(PUBLIC_ROOT / "claim_check.json")
    run_manifest = _read_json(PUBLIC_ROOT / "manifest.json")

    assert source_manifest["profile"] == "prompt-reach-v2"
    assert len(source_manifest["sources"]) == 371  # type: ignore[arg-type]
    assert reconciliation["status_counts"] == {
        "canonical_equivalent": 198,
        "secondary_only": 173,
    }
    assert matrix["status_counts"] == {"observed": 4, "requires_reanalysis": 1}
    assert claims["universal_improvement_supported"] is False
    assert claims["observed_diagnostic_count"] == 4
    assert claims["requires_reanalysis_count"] == 1
    artifacts = run_manifest["artifacts"]
    artifact_sha256 = run_manifest["artifact_sha256"]
    assert isinstance(artifacts, list)
    assert isinstance(artifact_sha256, dict)
    for name in artifacts:
        assert isinstance(name, str)
        content = (PUBLIC_ROOT / name).read_bytes()
        assert b"\r\n" not in content
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        assert artifact_sha256[name] == digest

    rendered = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(PUBLIC_ROOT.glob("*"))
        if path.is_file()
    )
    assert "D:\\" not in rendered
    assert "/root/" not in rendered
    for sensitive_field in ("prompt_text", '"gold"', '"prediction"', '"generation"'):
        assert sensitive_field not in rendered


def test_prompt_reach_case_has_bilingual_explanation_and_visual() -> None:
    english = (CASE_ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (CASE_ROOT / "README.zh.md").read_text(encoding="utf-8")
    visual = (CASE_ROOT / "evidence_overview.svg").read_text(encoding="utf-8")

    for text in (english, chinese):
        assert "371" in text
        assert "198" in text
        assert "173" in text
        assert "requires_reanalysis" in text
        assert "strict causal" in text or "严格因果" in text
    assert "prompt_control_lab" in visual
    assert "371" in visual
