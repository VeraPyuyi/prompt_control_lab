"""Bilingual plain-language presentation metadata for control diagnostics."""

# ruff: noqa: RUF001

from __future__ import annotations

from promptcontrollab.core.files import JsonDict

_CATALOG: dict[str, dict[str, JsonDict]] = {
    "en": {
        "terminal_sensitivity": {
            "label": "Long-horizon goal influence",
            "technical_name": "Terminal sensitivity",
            "purpose": (
                "Checks how much a change to the final reward, readout, or objective affects "
                "earlier decisions as the task gets longer."
            ),
            "question": (
                "Does a terminal change have progressively less influence on early decisions?"
            ),
            "meaning": (
                "A repeatable decay trend suggests that early decisions are less sensitive to "
                "distant terminal perturbations on this measured setup."
            ),
            "claim_boundary": (
                "This observed trend does not prove global stability of the full model or agent."
            ),
            "next_action": (
                "Repeat the intervention across seeds, task slices, and longer horizons."
            ),
        },
        "green_certificate": {
            "label": "Local stability boundary",
            "technical_name": "Green certificate",
            "purpose": (
                "Checks whether stable and unstable directions are separated in a reduced model "
                "and whether its boundary constraints remain well conditioned."
            ),
            "question": (
                "Does the reduced system have a clear local stability split and robust boundaries?"
            ),
            "meaning": (
                "Passing margins support the recorded reduced system and horizon family under its "
                "declared premises."
            ),
            "claim_boundary": (
                "This does not mathematically certify the full Transformer, agent, or deployment."
            ),
            "next_action": (
                "Inspect the smallest boundary margin and repeat the check on matched horizons."
            ),
        },
        "posterior_certificate": {
            "label": "Local solution confidence range",
            "technical_name": "Posterior certificate",
            "purpose": (
                "Uses the recorded residual and local derivative bounds to estimate whether a "
                "solution is supported near the numerical result and how large that region is."
            ),
            "question": "Is there a checkable solution near this result, and how local is it?",
            "meaning": (
                "A passed check supports a solution only inside the recorded local neighborhood "
                "and under the supplied bounds."
            ),
            "claim_boundary": (
                "It does not prove global optimality or behavior outside the verified neighborhood."
            ),
            "next_action": (
                "Tighten the residual or derivative bounds, then recompute the local radius."
            ),
        },
    },
    "zh": {
        "terminal_sensitivity": {
            "label": "最终目标影响",
            "technical_name": "终端敏感性（Terminal sensitivity）",
            "purpose": (
                "检查最终奖励、读出方式或目标发生变化时，前面几步的决策会受到多大影响，"
                "以及这种影响是否会随任务变长而减弱。"
            ),
            "question": "最终目标改变后，对前期决策的影响会不会越来越小？",
            "meaning": (
                "如果多个长度和重复实验都呈现稳定衰减，说明在当前实验条件下，前期决策"
                "对较远的最终目标扰动更不敏感。"
            ),
            "claim_boundary": "这只说明当前实验中的变化趋势，不能证明完整模型或 Agent 全局稳定。",
            "next_action": "在更多 seed、任务切片和更长序列上重复同一种目标干预。",
        },
        "green_certificate": {
            "label": "局部稳定边界",
            "technical_name": "Green 证书（Green certificate）",
            "purpose": (
                "检查低维近似系统中的稳定方向与不稳定方向是否清楚分离，并判断任务两端"
                "的约束是否足够稳健。"
            ),
            "question": "当前低维近似是否具有清楚的局部稳定结构和稳健边界？",
            "meaning": (
                "通过时只说明记录的低维系统、长度范围和前提彼此一致，适合继续作为稳定性"
                "线索使用。"
            ),
            "claim_boundary": "它不等于完整 Transformer、Agent 或生产系统已经得到数学安全证明。",
            "next_action": "先检查最小边界余量，再在相同长度和前提下重复验证。",
        },
        "posterior_certificate": {
            "label": "局部解可信范围",
            "technical_name": "后验证书（Posterior certificate）",
            "purpose": (
                "根据当前残差和局部变化上界，估计数值结果附近是否存在一个可验证的解，"
                "以及这个可信范围有多大。"
            ),
            "question": "当前结果附近是否有可检查的解，它的可信范围有多大？",
            "meaning": "通过时只支持给定前提和局部邻域内的结果，不自动延伸到更远区域。",
            "claim_boundary": "它不能证明全局最优，也不能说明可信邻域之外的模型行为。",
            "next_action": "收紧残差或局部变化上界，然后重新计算可信邻域半径。",
        },
    },
}

_STATUS_LABELS = {
    "en": {
        "certificate_verified": "Premises verified for the stated scope",
        "surrogate_consistent": "Reduced-model result is consistent",
        "empirical_only": "Experimental trend only",
        "not_applicable": "Not applicable to this run",
        "insufficient_evidence": "Insufficient evidence",
        "passed": "Check passed",
        "conditions_not_met": "Conditions not met; non-existence is not established",
        "missing": "Required input is missing",
        "invalid": "Input is invalid",
        "unknown": "Unknown",
    },
    "zh": {
        "certificate_verified": "限定条件已核验",
        "surrogate_consistent": "低维近似结果一致",
        "empirical_only": "仅观察到实验趋势",
        "not_applicable": "当前场景不适用",
        "insufficient_evidence": "现有证据不足",
        "passed": "检查通过",
        "conditions_not_met": "条件未满足，不代表解不存在",
        "missing": "缺少必要输入",
        "invalid": "输入无效",
        "unknown": "未知",
    },
}

_METRIC_LABELS = {
    "en": {
        "decay_rate": "Influence decay rate",
        "r_squared": "Trend fit",
        "hyperbolicity_margin": "Stable-direction separation margin",
        "boundary_sigma_min": "Boundary robustness margin",
        "h": "Local condition indicator",
        "existence_radius": "Confidence neighborhood radius",
        "neighborhood_margin": "Remaining neighborhood margin",
    },
    "zh": {
        "decay_rate": "影响衰减速度",
        "r_squared": "趋势拟合度",
        "hyperbolicity_margin": "稳定方向分离余量",
        "boundary_sigma_min": "边界稳健余量",
        "h": "局部条件指标",
        "existence_radius": "可信邻域半径",
        "neighborhood_margin": "剩余邻域余量",
    },
}


def diagnostic_catalog(language: str = "en") -> dict[str, JsonDict]:
    """Return a defensive copy of the plain-language diagnostic catalog."""

    lang = _language(language)
    return {key: dict(value) for key, value in _CATALOG[lang].items()}


def get_diagnostic_presentation(name: str, language: str = "en") -> JsonDict:
    """Return presentation metadata for one stable diagnostic identifier."""

    catalog = diagnostic_catalog(language)
    if name not in catalog:
        raise ValueError(f"Unknown diagnostic presentation id: {name}")
    return catalog[name]


def diagnostic_status_label(status: object, language: str = "en") -> str:
    """Translate a stable certificate or check status for display only."""

    value = str(status or "unknown")
    return _STATUS_LABELS[_language(language)].get(value, value)


def diagnostic_metric_label(metric: str, language: str = "en") -> str:
    """Translate a stable diagnostic metric key for display only."""

    return _METRIC_LABELS[_language(language)].get(metric, metric)


def _language(language: str) -> str:
    return "zh" if language == "zh" else "en"
