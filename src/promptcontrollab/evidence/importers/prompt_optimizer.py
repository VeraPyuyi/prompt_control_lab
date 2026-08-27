"""Prompt Optimizer asset normalization and scaffold rendering."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, write_json, write_jsonl
from promptcontrollab.evidence.importers.structured import (
    _dict_or_empty,
    _html_text,
    _json_list,
    _markdown_cell,
    _optional_str,
    _string_list,
)


def _prompt_optimizer_assets(payload: JsonDict, *, source_path: Path) -> list[JsonDict]:
    assets: list[JsonDict] = []
    favorites = payload.get("favorites")
    if isinstance(favorites, list):
        for index, item in enumerate(favorites):
            if isinstance(item, dict):
                asset = _prompt_optimizer_favorite_asset(item, index=index)
                if asset is not None:
                    assets.append(asset)
    template = payload.get("template")
    if isinstance(template, dict):
        asset = _prompt_optimizer_template_asset(
            template,
            payload=payload,
            source_path=source_path,
        )
        if asset is not None:
            assets.append(asset)
    elif isinstance(payload.get("messages"), list):
        asset = _prompt_optimizer_template_asset(
            payload,
            payload=payload,
            source_path=source_path,
        )
        if asset is not None:
            assets.append(asset)
    return assets


def _prompt_optimizer_favorite_asset(item: JsonDict, *, index: int) -> JsonDict | None:
    content = _optional_str(item.get("content"))
    if content is None:
        return None
    metadata = _dict_or_empty(item.get("metadata"))
    prompt_asset = _dict_or_empty(metadata.get("promptAsset"))
    asset: JsonDict = {
        "id": _optional_str(item.get("id")) or f"favorite-{index}",
        "title": _optional_str(item.get("title")) or f"Favorite {index + 1}",
        "content": content,
        "content_hash": f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}",
        "source_type": "favorite",
        "description": _optional_str(item.get("description")),
        "tags": _string_list(item.get("tags")),
        "category": _optional_str(item.get("category")),
        "function_mode": _optional_str(item.get("functionMode")),
        "optimization_mode": _optional_str(item.get("optimizationMode")),
        "use_count": item.get("useCount") if isinstance(item.get("useCount"), int) else None,
        "created_at": _optional_str(item.get("createdAt")),
        "updated_at": _optional_str(item.get("updatedAt")),
        "metadata_summary": _prompt_optimizer_metadata_summary(metadata, prompt_asset),
    }
    model_payload: JsonDict = {}
    for source_key, target_key in [
        ("modelKey", "model_key"),
        ("modelName", "model_name"),
        ("templateId", "template_id"),
        ("sourceHistoryId", "source_history_id"),
    ]:
        value = _optional_str(metadata.get(source_key))
        if value is not None:
            model_payload[target_key] = value
    if model_payload:
        asset["model_or_source"] = model_payload
    original_content = _optional_str(metadata.get("originalContent"))
    if original_content is not None:
        asset["original_content_hash"] = (
            f"sha256:{hashlib.sha256(original_content.encode('utf-8')).hexdigest()}"
        )
        asset["has_original_content"] = True
    else:
        asset["has_original_content"] = False
    return {key: value for key, value in asset.items() if value is not None}


def _prompt_optimizer_template_asset(
    template: JsonDict,
    *,
    payload: JsonDict,
    source_path: Path,
) -> JsonDict | None:
    content = _prompt_optimizer_template_content(template)
    if not content:
        return None
    title = (
        _optional_str(template.get("title"))
        or _optional_str(template.get("name"))
        or _optional_str(template.get("id"))
        or source_path.stem
    )
    variables = payload.get("variables")
    messages = template.get("messages")
    asset: JsonDict = {
        "id": _optional_str(template.get("id")) or f"template:{source_path.stem}",
        "title": title,
        "content": content,
        "content_hash": f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}",
        "source_type": "template",
        "description": _optional_str(template.get("description")),
        "tags": _string_list(template.get("tags")),
        "variables": variables if isinstance(variables, dict) else {},
        "metadata_summary": {
            "message_count": len(messages) if isinstance(messages, list) else None,
            "export_format": _dict_or_empty(payload.get("export_info")).get("format"),
        },
    }
    return {key: value for key, value in asset.items() if value is not None}


def _prompt_optimizer_template_content(template: JsonDict) -> str:
    content = _optional_str(template.get("content")) or _optional_str(template.get("prompt"))
    if content is not None:
        return content
    messages = template.get("messages")
    if not isinstance(messages, list):
        return ""
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = _optional_str(message.get("role")) or "message"
        text = message.get("content")
        if not isinstance(text, str):
            text = json.dumps(text, sort_keys=True, ensure_ascii=False)
        parts.append(f"[{role}]\n{text}")
    return "\n\n".join(parts)


def _prompt_optimizer_metadata_summary(metadata: JsonDict, prompt_asset: JsonDict) -> JsonDict:
    versions = prompt_asset.get("versions")
    examples = prompt_asset.get("examples")
    summary: JsonDict = {
        "has_prompt_asset": bool(prompt_asset),
        "prompt_asset_schema_version": prompt_asset.get("schemaVersion")
        if isinstance(prompt_asset.get("schemaVersion"), str)
        else None,
        "current_version_id": _optional_str(prompt_asset.get("currentVersionId")),
        "version_count": len(versions) if isinstance(versions, list) else 0,
        "example_count": len(examples) if isinstance(examples, list) else 0,
    }
    media = metadata.get("media")
    if isinstance(media, list):
        summary["media_count"] = len(media)
    return {key: value for key, value in summary.items() if value is not None}


def _prompt_optimizer_next_actions(out_dir: Path) -> list[str]:
    return [
        "Choose one imported prompt asset as baseline or candidate.",
        "Create a paired task set and predictions with a fixed model/provider.",
        (
            "Edit the generated `eval_scaffold/` files, then run "
            "`pcl analyze --config eval_scaffold/promptcontrol.prompt_optimizer.example.yaml "
            "--out runs/quick` after scoring."
        ),
        f"Open `{out_dir / 'prompt_optimizer_gap_plan.html'}` before making an improvement claim.",
    ]


def _write_prompt_optimizer_eval_scaffold(*, out_dir: Path, asset_bundle: JsonDict) -> JsonDict:
    """Materialize a reproducible evaluation scaffold for imported prompt assets."""

    scaffold_dir = out_dir / "eval_scaffold"
    prompts_dir = scaffold_dir / "prompts"
    ensure_dir(scaffold_dir)
    ensure_dir(prompts_dir)
    asset_prompt_files: list[JsonDict] = []
    for index, asset in enumerate(_json_list(asset_bundle.get("assets"))):
        asset_id = str(asset.get("id") or f"asset-{index + 1}")
        filename = _safe_prompt_asset_filename(asset_id, fallback=f"asset-{index + 1}") + ".txt"
        prompt_path = prompts_dir / filename
        prompt_path.write_text(str(asset.get("content", "")), encoding="utf-8")
        asset_prompt_files.append(
            {
                "asset_id": asset_id,
                "title": asset.get("title"),
                "path": str(prompt_path),
                "content_hash": asset.get("content_hash"),
            }
        )

    tasks_path = scaffold_dir / "tasks.template.jsonl"
    baseline_path = scaffold_dir / "baseline_predictions.template.jsonl"
    candidate_path = scaffold_dir / "candidate_predictions.template.jsonl"
    config_path = scaffold_dir / "promptcontrol.prompt_optimizer.example.yaml"
    readme_path = scaffold_dir / "README.md"
    scaffold_path = scaffold_dir / "prompt_optimizer_eval_scaffold.json"

    write_jsonl(
        tasks_path,
        [
            {
                "id": "example-1",
                "input": "Replace with a real evaluation input.",
                "expected": "Replace with the expected answer.",
                "slice": "replace-me",
            },
            {
                "id": "example-2",
                "input": "Add another paired evaluation input.",
                "expected": "Add the expected answer for the same metric.",
                "slice": "replace-me",
            },
        ],
    )
    write_jsonl(
        baseline_path,
        [
            {
                "id": "example-1",
                "output": "TODO: run the baseline prompt on example-1.",
                "provider": "TODO",
                "model": "TODO",
            },
            {
                "id": "example-2",
                "output": "TODO: run the baseline prompt on example-2.",
                "provider": "TODO",
                "model": "TODO",
            },
        ],
    )
    candidate_asset_id = (
        str(asset_prompt_files[0]["asset_id"]) if asset_prompt_files else "imported-asset"
    )
    write_jsonl(
        candidate_path,
        [
            {
                "id": "example-1",
                "output": "TODO: run the imported candidate prompt on example-1.",
                "provider": "TODO",
                "model": "TODO",
                "prompt_asset_id": candidate_asset_id,
            },
            {
                "id": "example-2",
                "output": "TODO: run the imported candidate prompt on example-2.",
                "provider": "TODO",
                "model": "TODO",
                "prompt_asset_id": candidate_asset_id,
            },
        ],
    )
    config_path.write_text(
        "\n".join(
            [
                "# Fill the template JSONL files before running this config.",
                "mode: quick",
                "data: tasks.template.jsonl",
                "metric: exact_match",
                "baseline_predictions: baseline_predictions.template.jsonl",
                "candidate_predictions: candidate_predictions.template.jsonl",
                "out: ../runs/from-prompt-optimizer-scored",
                "explain_level: plain",
                "baseline_prompt_id: baseline",
                f"candidate_prompt_id: {candidate_asset_id}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    scaffold: JsonDict = {
        "kind": "prompt_optimizer_eval_scaffold",
        "schema": "prompt_control_lab.prompt_optimizer_eval_scaffold.v1",
        "source_tool": "prompt-optimizer",
        "status": "template_not_scored",
        "boundary": (
            "This scaffold is not evidence until tasks and predictions are filled "
            "with paired outputs from a fixed model/provider and `pcl analyze` is run."
        ),
        "asset_count": asset_bundle.get("asset_count", 0),
        "asset_prompt_files": asset_prompt_files,
        "tasks_template_path": str(tasks_path),
        "baseline_predictions_template_path": str(baseline_path),
        "candidate_predictions_template_path": str(candidate_path),
        "analyze_config_template_path": str(config_path),
        "readme_path": str(readme_path),
        "fields_to_fill": [
            "tasks.template.jsonl input/expected/slice",
            "baseline_predictions.template.jsonl output/provider/model",
            "candidate_predictions.template.jsonl output/provider/model",
            "promptcontrol.prompt_optimizer.example.yaml metric and prompt ids",
        ],
        "commands": [
            f"pcl analyze --config {config_path} --out runs/from-prompt-optimizer-scored",
            "pcl diagnose --run runs/from-prompt-optimizer-scored",
        ],
    }
    write_json(scaffold_path, scaffold)
    readme_path.write_text(
        render_prompt_optimizer_eval_scaffold_markdown(scaffold),
        encoding="utf-8",
    )
    return {**scaffold, "path": str(scaffold_path)}


def _safe_prompt_asset_filename(value: str, *, fallback: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "-" for char in value)
    safe = "-".join(part for part in safe.split("-") if part)
    return safe[:80] or fallback


def _prompt_optimizer_gap_plan(asset_bundle: JsonDict) -> JsonDict:
    scaffold = asset_bundle.get("eval_scaffold")
    scaffold_path = ""
    if isinstance(scaffold, dict):
        scaffold_path = str(scaffold.get("readme_path") or scaffold.get("path") or "")
    return {
        "kind": "prompt_optimizer_gap_plan",
        "source_tool": "prompt-optimizer",
        "status": "not_scored",
        "asset_count": asset_bundle.get("asset_count", 0),
        "boundary": asset_bundle.get("boundary", ""),
        "missing_evidence": [
            "No paired baseline/candidate prediction file was imported.",
            "No train/validation/withheld split hash is available yet.",
            "No paired bootstrap confidence interval or permutation p-value exists yet.",
            (
                "No prompt-only validity check can be made until model/provider/prompt "
                "identity is recorded."
            ),
            (
                "Paper diagnostics such as soft-hard, trajectory, Riccati, and tv-soft "
                "are not present yet."
            ),
        ],
        "recommended_commands": [
            f"Open {scaffold_path}" if scaffold_path else "Open eval_scaffold/README.md",
            (
                "pcl analyze --config "
                "eval_scaffold/promptcontrol.prompt_optimizer.example.yaml "
                "--out runs/from-prompt-optimizer-scored"
            ),
            (
                "pcl validity --baseline runs/baseline --candidate runs/candidate "
                "--out runs/validity.json"
            ),
            "pcl diagnose --run runs/from-prompt-optimizer-scored",
        ],
        "next_actions": asset_bundle.get("next_actions", []),
        "eval_scaffold": scaffold if isinstance(scaffold, dict) else {},
    }


def render_prompt_assets_markdown(bundle: JsonDict) -> str:
    """Render imported prompt assets as a bounded Markdown report."""

    lines = [
        "# Prompt Optimizer Asset Import",
        "",
        f"- Source tool: `{bundle.get('source_tool')}`",
        f"- Asset count: `{bundle.get('asset_count')}`",
        f"- Evaluation status: `{bundle.get('evaluation_status')}`",
        f"- Source SHA256: `{bundle.get('source_sha256')}`",
        "",
        "## Boundary",
        "",
        str(bundle.get("boundary", "")),
        "",
        "## Assets",
        "",
        "| ID | Title | Type | Hash | Tags |",
        "|---|---|---|---|---|",
    ]
    for asset in _json_list(bundle.get("assets")):
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(asset.get("id")),
                    _markdown_cell(asset.get("title")),
                    _markdown_cell(asset.get("source_type")),
                    _markdown_cell(asset.get("content_hash")),
                    _markdown_cell(", ".join(_string_list(asset.get("tags")))),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Next actions", ""])
    lines.extend(f"- {item}" for item in _string_list(bundle.get("next_actions")))
    lines.append("")
    return "\n".join(lines)


def render_prompt_optimizer_gap_plan_markdown(plan: JsonDict) -> str:
    """Render missing prompt-optimizer evidence and recommended actions as Markdown."""

    lines = [
        "# Prompt Optimizer Evidence Gap Plan",
        "",
        f"- Status: `{plan.get('status')}`",
        f"- Asset count: `{plan.get('asset_count')}`",
        "",
        "## Missing evidence",
        "",
    ]
    lines.extend(f"- {item}" for item in _string_list(plan.get("missing_evidence")))
    lines.extend(["", "## Recommended commands", ""])
    lines.extend(f"- `{item}`" for item in _string_list(plan.get("recommended_commands")))
    lines.append("")
    return "\n".join(lines)


def render_prompt_optimizer_eval_scaffold_markdown(scaffold: JsonDict) -> str:
    """Render the prompt-optimizer evaluation scaffold as Markdown."""

    lines = [
        "# Prompt Optimizer Eval Scaffold",
        "",
        "This folder turns imported prompt-optimizer assets into a concrete scoring checklist.",
        "",
        "## Boundary",
        "",
        str(scaffold.get("boundary", "")),
        "",
        "## Files",
        "",
        f"- Tasks template: `{scaffold.get('tasks_template_path')}`",
        f"- Baseline predictions template: `{scaffold.get('baseline_predictions_template_path')}`",
        (
            "- Candidate predictions template: "
            f"`{scaffold.get('candidate_predictions_template_path')}`"
        ),
        f"- Analyze config template: `{scaffold.get('analyze_config_template_path')}`",
        "",
        "## Imported prompt files",
        "",
    ]
    for item in _json_list(scaffold.get("asset_prompt_files")):
        lines.append(
            f"- `{item.get('asset_id')}`: `{item.get('path')}` ({item.get('content_hash')})"
        )
    lines.extend(["", "## Fill these fields", ""])
    lines.extend(f"- {item}" for item in _string_list(scaffold.get("fields_to_fill")))
    lines.extend(["", "## Commands after scoring", ""])
    lines.extend(f"- `{item}`" for item in _string_list(scaffold.get("commands")))
    lines.append("")
    return "\n".join(lines)


def render_prompt_assets_html(bundle: JsonDict) -> str:
    """Render imported prompt assets as a standalone HTML report."""

    rows = "\n".join(
        "<tr>"
        f"<td>{_html_text(asset.get('id'))}</td>"
        f"<td>{_html_text(asset.get('title'))}</td>"
        f"<td>{_html_text(asset.get('source_type'))}</td>"
        f"<td><code>{_html_text(asset.get('content_hash'))}</code></td>"
        f"<td>{_html_text(', '.join(_string_list(asset.get('tags'))))}</td>"
        "</tr>"
        for asset in _json_list(bundle.get("assets"))
    )
    actions = "\n".join(
        f"<li>{_html_text(item)}</li>" for item in _string_list(bundle.get("next_actions"))
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Prompt Optimizer Asset Import</title>
  <style>
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 32px; color: #172033; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{
      border: 1px solid #d8dee9;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #f5f7fb; }}
    .card {{ border: 1px solid #d8dee9; border-radius: 8px; padding: 16px; background: #fbfcff; }}
    code {{ background: #eef2f7; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Prompt Optimizer Asset Import</h1>
  <div class="card">
    <p><strong>Source tool:</strong> {_html_text(bundle.get("source_tool"))}</p>
    <p><strong>Asset count:</strong> {_html_text(bundle.get("asset_count"))}</p>
    <p><strong>Evaluation status:</strong> {_html_text(bundle.get("evaluation_status"))}</p>
    <p><strong>Boundary:</strong> {_html_text(bundle.get("boundary"))}</p>
  </div>
  <h2>Assets</h2>
  <table>
    <thead><tr><th>ID</th><th>Title</th><th>Type</th><th>Hash</th><th>Tags</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Next actions</h2>
  <ul>{actions}</ul>
</body>
</html>
"""


def render_prompt_optimizer_gap_plan_html(plan: JsonDict) -> str:
    """Render the prompt-optimizer evidence gap plan as HTML."""

    missing = "\n".join(
        f"<li>{_html_text(item)}</li>" for item in _string_list(plan.get("missing_evidence"))
    )
    commands = "\n".join(
        f"<li><code>{_html_text(item)}</code></li>"
        for item in _string_list(plan.get("recommended_commands"))
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Prompt Optimizer Evidence Gap Plan</title>
  <style>
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 32px; color: #172033; }}
    .status {{
      display: inline-block;
      border-radius: 999px;
      background: #fff4cc;
      padding: 4px 10px;
    }}
    code {{ background: #eef2f7; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Prompt Optimizer Evidence Gap Plan</h1>
  <p class="status">Status: {_html_text(plan.get("status"))}</p>
  <h2>Boundary</h2>
  <p>{_html_text(plan.get("boundary"))}</p>
  <h2>Missing evidence</h2>
  <ul>{missing}</ul>
  <h2>Recommended commands</h2>
  <ul>{commands}</ul>
</body>
</html>
"""
