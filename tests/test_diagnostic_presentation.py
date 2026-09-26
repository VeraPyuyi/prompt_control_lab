# ruff: noqa: RUF001

from __future__ import annotations

from promptcontrollab.diagnostics.presentation import (
    diagnostic_catalog,
    diagnostic_metric_label,
    diagnostic_status_label,
    get_diagnostic_presentation,
)
from promptcontrollab.integrations.ui.data import control_certificate_interpretation_rows
from promptcontrollab.integrations.ui.data.research import research_diagnostic_rows


def test_chinese_certificate_catalog_uses_plain_function_names() -> None:
    catalog = diagnostic_catalog("zh")

    assert catalog["terminal_sensitivity"]["label"] == "最终目标影响"
    assert catalog["green_certificate"]["label"] == "局部稳定边界"
    assert catalog["posterior_certificate"]["label"] == "局部解可信范围"
    for key in ("terminal_sensitivity", "green_certificate", "posterior_certificate"):
        item = catalog[key]
        assert all(
            item[field]
            for field in ("purpose", "question", "meaning", "claim_boundary", "next_action")
        )
        assert key not in str(item["label"])


def test_catalog_keeps_technical_names_secondary_and_localizes_statuses() -> None:
    item = get_diagnostic_presentation("green_certificate", "zh")

    assert item["technical_name"] == "Green 证书（Green certificate）"
    assert diagnostic_status_label("certificate_verified", "zh") == "限定条件已核验"
    assert diagnostic_status_label("conditions_not_met", "zh") == (
        "条件未满足，不代表解不存在"
    )
    assert diagnostic_metric_label("boundary_sigma_min", "zh") == "边界稳健余量"


def test_control_certificate_rows_use_localized_labels_and_explanations() -> None:
    detail = {
        "diagnostics": {
            "terminal_sensitivity": {
                "certificate_level": "empirical_only",
                "check_state": "passed",
                "decay_rate": 0.2,
                "r_squared": 0.8,
            },
            "green_certificate": {
                "certificate_level": "surrogate_consistent",
                "check_state": "conditions_not_met",
                "hyperbolicity_margin": 0.1,
                "boundary_sigma_min": 0.02,
            },
            "posterior_certificate": {
                "certificate_level": "certificate_verified",
                "check_state": "passed",
                "h": 0.1,
                "existence_radius": 0.03,
            },
        }
    }

    rows = control_certificate_interpretation_rows(detail, "zh")

    assert [row["diagnostic"] for row in rows] == [
        "最终目标影响",
        "局部稳定边界",
        "局部解可信范围",
    ]
    assert rows[0]["function"] == get_diagnostic_presentation(
        "terminal_sensitivity", "zh"
    )["purpose"]
    assert rows[1]["status_label"] == "条件未满足，不代表解不存在"
    assert "条件未满足" in str(rows[1]["explains"])
    assert "通过时" not in str(rows[1]["explains"])
    assert "影响衰减速度" in str(rows[0]["observed"])
    assert rows[2]["technical_name"] == "后验证书（Posterior certificate）"


def test_certificate_rows_preserve_artifact_specific_interpretation() -> None:
    detail = {
        "diagnostics": {
            "green_certificate": {
                "certificate_level": "insufficient_evidence",
                "check_state": "conditions_not_met",
                "observation": "The smallest recorded boundary margin is negative.",
                "explanation": "The supplied reduced system does not meet this local condition.",
                "claim_boundary": "This does not establish that a nearby solution is absent.",
                "next_action": "Recheck the boundary matrices and premise manifest.",
            }
        }
    }

    row = control_certificate_interpretation_rows(detail, "zh")[0]

    assert row["observed"] == "The smallest recorded boundary margin is negative."
    assert row["explains"] == (
        "The supplied reduced system does not meet this local condition."
    )
    assert row["does_not_prove"] == (
        "This does not establish that a nearby solution is absent."
    )
    assert row["next_action"] == "Recheck the boundary matrices and premise manifest."


def test_research_overview_uses_plain_chinese_names_for_advanced_evidence() -> None:
    rows = research_diagnostic_rows({"diagnostics": {}}, "zh")
    by_key = {str(row["key"]): row for row in rows}

    assert by_key["terminal_sensitivity"]["diagnostic"] == "最终目标影响"
    assert by_key["green_certificate"]["diagnostic"] == "局部稳定边界"
    assert by_key["posterior_certificate"]["diagnostic"] == "局部解可信范围"
    assert "检查" in str(by_key["terminal_sensitivity"]["meaning"])
