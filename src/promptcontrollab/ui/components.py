"""Reusable Streamlit component helpers."""

from __future__ import annotations

import difflib
import html
from typing import Any


def dashboard_css() -> str:
    """Return the local dashboard design-token stylesheet."""

    return """
<style>
:root {
  --pcl-bg: #f8fafc;
  --pcl-surface: #ffffff;
  --pcl-surface-muted: #f1f5f9;
  --pcl-border: #dbe3ef;
  --pcl-ink: #0f172a;
  --pcl-muted: #64748b;
  --pcl-accent: #2563eb;
  --pcl-accent-soft: #dbeafe;
  --pcl-good: #059669;
  --pcl-warn: #d97706;
  --pcl-risk: #dc2626;
}
.block-container {
  padding-top: 1.4rem;
  padding-bottom: 2.6rem;
}
.pcl-hero {
  border: 1px solid var(--pcl-border);
  border-radius: 8px;
  padding: 22px 24px;
  background:
    linear-gradient(135deg, rgba(37,99,235,.09), rgba(5,150,105,.08)),
    var(--pcl-surface);
  margin-bottom: 16px;
}
.pcl-hero h1 {
  margin: 0 0 8px 0;
  color: var(--pcl-ink);
  font-size: 2rem;
  letter-spacing: 0;
}
.pcl-hero p {
  margin: 0;
  color: var(--pcl-muted);
  font-size: 1rem;
  line-height: 1.55;
}
.pcl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin: 14px 0 18px 0;
}
.pcl-stat-card, .pcl-paper-card {
  border: 1px solid var(--pcl-border);
  border-radius: 8px;
  background: var(--pcl-surface);
  padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(15,23,42,.04);
}
.pcl-stat-label {
  color: var(--pcl-muted);
  font-size: .78rem;
  text-transform: uppercase;
  letter-spacing: .06em;
}
.pcl-stat-value {
  color: var(--pcl-ink);
  font-weight: 700;
  font-size: 1.35rem;
  margin-top: 4px;
}
.pcl-stat-caption, .pcl-paper-card p {
  color: var(--pcl-muted);
  font-size: .9rem;
  line-height: 1.45;
  margin: 6px 0 0 0;
}
.pcl-pipeline {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin: 12px 0 18px 0;
}
.pcl-pipeline-step {
  border: 1px solid var(--pcl-border);
  border-radius: 8px;
  padding: 12px;
  background: var(--pcl-surface-muted);
}
.pcl-pipeline-step strong {
  display: block;
  color: var(--pcl-ink);
}
.pcl-pipeline-step span {
  display: block;
  color: var(--pcl-muted);
  font-size: .86rem;
  line-height: 1.35;
  margin-top: 4px;
}
.pcl-section-title {
  margin-top: 10px;
  margin-bottom: 4px;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--pcl-ink);
}
</style>
"""


def stat_card_html(label: str, value: object, caption: str = "") -> str:
    """Return a compact dashboard card."""

    return (
        '<div class="pcl-stat-card">'
        f'<div class="pcl-stat-label">{html.escape(label)}</div>'
        f'<div class="pcl-stat-value">{html.escape("-" if value is None else str(value))}</div>'
        f'<div class="pcl-stat-caption">{html.escape(caption)}</div>'
        "</div>"
    )


def paper_card_html(title: str, body: str) -> str:
    """Return a paper-concept explanation card."""

    return (
        '<div class="pcl-paper-card">'
        f"<strong>{html.escape(title)}</strong>"
        f"<p>{html.escape(body)}</p>"
        "</div>"
    )


def badge(label: str, value: object) -> str:
    """Return a compact badge-like Markdown string."""

    return f"**{label}:** `{value}`"


def prompt_diff(original: str, improved: str) -> str:
    """Return a readable unified diff for two prompt strings."""

    lines = difflib.unified_diff(
        original.splitlines(),
        improved.splitlines(),
        fromfile="original",
        tofile="guarded",
        lineterm="",
    )
    return "\n".join(lines)


def metric_cards(st: Any, cards: list[tuple[str, object]]) -> None:
    """Render metric cards in a stable column layout."""

    columns = st.columns(max(1, len(cards)))
    for column, (label, value) in zip(columns, cards, strict=False):
        column.metric(label, "-" if value is None else str(value))


def empty_state(st: Any, message: str, command: str | None = None) -> None:
    """Render an empty-state warning with an optional command."""

    st.warning(message)
    if command:
        st.code(command, language="bash")
