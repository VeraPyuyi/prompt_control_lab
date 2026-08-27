"""Local posterior existence checks for bounded nonlinear surrogate systems."""

from __future__ import annotations

import html
import math
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json


def analyze_posterior_certificate(*, input_path: Path, out_dir: Path) -> JsonDict:
    """Evaluate a scalar Newton-Kantorovich-style posterior bound record."""

    source = read_json(input_path)
    epsilon = _nonnegative_finite(source, "residual_norm_upper")
    beta = _positive_finite(source, "jacobian_inverse_norm_upper")
    lipschitz = _nonnegative_finite(source, "jacobian_lipschitz_upper")
    radius = _positive_finite(source, "neighborhood_radius")

    eta = beta * epsilon
    contraction = beta * lipschitz
    h_value = eta * contraction
    if not all(math.isfinite(value) for value in (eta, contraction, h_value)):
        raise ValueError("The derived posterior bounds eta, K, and h must be finite")
    h_passed = h_value <= 0.5
    if contraction == 0.0:
        existence_radius = eta
        linear_case = True
    elif h_passed:
        discriminant_root = math.sqrt(max(0.0, 1.0 - 2.0 * h_value))
        existence_radius = 2.0 * eta / (1.0 + discriminant_root)
        linear_case = False
    else:
        existence_radius = None
        linear_case = False
    radius_passed = existence_radius is not None and existence_radius <= radius

    unmet: list[str] = []
    if not h_passed:
        unmet.append("kantorovich_h")
    if h_passed and not radius_passed:
        unmet.append("neighborhood_radius")
    check_state = "passed" if not unmet else "conditions_not_met"
    provenance = source.get("bound_provenance")
    provenance_dict = provenance if isinstance(provenance, dict) else {}
    provenance_complete = _complete_conservative_provenance(provenance_dict)
    if not provenance_dict:
        certificate_level = "insufficient_evidence"
    elif check_state == "passed" and provenance_complete:
        certificate_level = "certificate_verified"
    else:
        certificate_level = "surrogate_consistent"

    payload: JsonDict = {
        "schema": "prompt_control_lab.posterior_certificate.v1",
        "kind": "posterior_certificate",
        "source": str(input_path),
        "certificate_level": certificate_level,
        "check_state": check_state,
        "residual_norm_upper": epsilon,
        "jacobian_inverse_norm_upper": beta,
        "jacobian_lipschitz_upper": lipschitz,
        "neighborhood_radius": radius,
        "eta": eta,
        "K": contraction,
        "h": h_value,
        "existence_radius": existence_radius,
        "h_margin": 0.5 - h_value,
        "neighborhood_margin": (
            radius - existence_radius if existence_radius is not None else None
        ),
        "linear_case": linear_case,
        "conditions_not_met": unmet,
        "inequalities": {
            "h_at_most_one_half": {
                "observed": h_value,
                "threshold": 0.5,
                "passed": h_passed,
            },
            "existence_radius_within_neighborhood": {
                "observed": existence_radius,
                "threshold": radius,
                "passed": radius_passed,
            },
        },
        "bound_provenance": provenance_dict,
        "provenance_complete": provenance_complete,
        "observation": _observation(check_state, h_value, existence_radius, radius),
        "explanation": (
            "The recorded residual, inverse-Jacobian, and local Lipschitz bounds satisfy the "
            "stated local posterior check."
            if check_state == "passed"
            else "At least one stated local posterior certificate condition was not met."
        ),
        "scope": str(provenance_dict.get("scope") or "the supplied local surrogate bounds"),
        "claim_boundary": (
            "This local posterior check does not prove global optimality, a Transformer-wide "
            "mechanism, or nonexistence when conditions are not met."
        ),
        "next_action": (
            "Retain the bound provenance and validate the named local branch."
            if check_state == "passed"
            else "Tighten the residual or derivative bounds, or enlarge the justified local "
            "neighborhood before relying on this certificate."
        ),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "posterior_certificate.json", payload)
    (out_dir / "posterior_certificate.html").write_text(
        _render_html(payload),
        encoding="utf-8",
    )
    return payload


def _nonnegative_finite(payload: JsonDict, key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"`{key}` must be a finite non-negative number")
    converted = float(value)
    if not math.isfinite(converted) or converted < 0.0:
        raise ValueError(f"`{key}` must be a finite non-negative number")
    return converted


def _positive_finite(payload: JsonDict, key: str) -> float:
    converted = _nonnegative_finite(payload, key)
    if converted <= 0.0:
        raise ValueError(f"`{key}` must be a finite positive number")
    return converted


def _complete_conservative_provenance(provenance: JsonDict) -> bool:
    return (
        provenance.get("kind") == "certified_bounds"
        and provenance.get("conservative") is True
        and bool(str(provenance.get("scope") or "").strip())
        and bool(str(provenance.get("source") or "").strip())
    )


def _observation(
    check_state: str,
    h_value: float,
    existence_radius: float | None,
    neighborhood_radius: float,
) -> str:
    if check_state == "passed":
        return (
            f"h={h_value:.6g} and local radius={existence_radius:.6g} fit within "
            f"R={neighborhood_radius:.6g}."
        )
    radius_text = "undefined" if existence_radius is None else f"{existence_radius:.6g}"
    return (
        f"h={h_value:.6g}, local radius={radius_text}, and R={neighborhood_radius:.6g}; "
        "the supplied conditions were not all met."
    )


def _render_html(payload: JsonDict) -> str:
    rows = [
        ("Certificate level", payload["certificate_level"]),
        ("Check state", payload["check_state"]),
        ("h", payload["h"]),
        ("Existence radius", payload["existence_radius"]),
        ("Neighborhood margin", payload["neighborhood_margin"]),
    ]
    cards = "".join(
        f"<div><b>{html.escape(str(label))}</b><br>{html.escape(str(value))}</div>"
        for label, value in rows
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Posterior certificate</title>
<style>body{{font-family:Arial,sans-serif;background:#f7f9fc;color:#172b4d;margin:0}}
main{{max-width:980px;margin:auto;padding:32px}}.grid{{display:grid;grid-template-columns:
repeat(auto-fit,minmax(180px,1fr));gap:12px}}.grid div,section{{background:white;border:
1px solid #d9e2ec;border-radius:8px;padding:16px}}p{{line-height:1.55}}</style></head>
<body><main><h1>Posterior certificate</h1><div class="grid">{cards}</div>
<section><h2>Interpretation</h2><p>{html.escape(str(payload['observation']))}</p>
<p><b>Boundary:</b> {html.escape(str(payload['claim_boundary']))}</p>
<p><b>Next:</b> {html.escape(str(payload['next_action']))}</p></section></main></body></html>"""
