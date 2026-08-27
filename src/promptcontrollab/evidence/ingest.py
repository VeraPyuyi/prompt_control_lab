"""Import artifacts from external eval tools into PromptControlLab runs."""

from __future__ import annotations

import hashlib
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json, write_jsonl
from promptcontrollab.core.version import __version__
from promptcontrollab.evaluation.metrics import summarize_predictions
from promptcontrollab.evidence.importers.prompt_optimizer import (
    _prompt_optimizer_assets,
    _prompt_optimizer_gap_plan,
    _prompt_optimizer_next_actions,
    _write_prompt_optimizer_eval_scaffold,
)
from promptcontrollab.evidence.importers.prompt_optimizer import (
    render_prompt_assets_html as render_prompt_assets_html,
)
from promptcontrollab.evidence.importers.prompt_optimizer import (
    render_prompt_assets_markdown as render_prompt_assets_markdown,
)
from promptcontrollab.evidence.importers.prompt_optimizer import (
    render_prompt_optimizer_eval_scaffold_markdown as _render_eval_scaffold_markdown,
)
from promptcontrollab.evidence.importers.prompt_optimizer import (
    render_prompt_optimizer_gap_plan_html as render_prompt_optimizer_gap_plan_html,
)
from promptcontrollab.evidence.importers.prompt_optimizer import (
    render_prompt_optimizer_gap_plan_markdown as render_prompt_optimizer_gap_plan_markdown,
)
from promptcontrollab.evidence.importers.structured import (
    _deepeval_rows,
    _filter_deepeval_rows,
    _filter_langfuse_rows,
    _filter_langsmith_rows,
    _filter_rows,
    _langfuse_rows,
    _langsmith_rows,
    _optional_str,
    _prediction_from_deepeval_row,
    _prediction_from_langfuse_row,
    _prediction_from_langsmith_row,
    _prediction_from_promptfoo_row,
    _prompt_identity,
    _row_from_v3_result,
    _rows_from_table_row,
    _single_value,
    _split_provider_model,
    _string_list,
)
from promptcontrollab.provenance.model_identity import detect_model_identity

render_prompt_optimizer_eval_scaffold_markdown = _render_eval_scaffold_markdown


def ingest_auto_results(
    *,
    source_path: Path,
    out_dir: Path,
    prompt_id: str | None = None,
    name: str | None = None,
    experiment: str | None = None,
    score_name: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    method: str | None = None,
    asset_id: str | None = None,
) -> JsonDict:
    """Auto-detect external eval/trace exports and import them."""

    source_tool = detect_ingest_source(source_path)
    if source_tool == "promptfoo":
        payload = ingest_promptfoo_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=prompt_id,
            provider=provider,
            method=method,
        )
    elif source_tool == "langfuse":
        payload = ingest_langfuse_results(
            source_path=source_path,
            out_dir=out_dir,
            name=name,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    elif source_tool == "langsmith":
        payload = ingest_langsmith_results(
            source_path=source_path,
            out_dir=out_dir,
            experiment=experiment,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    elif source_tool == "deepeval":
        payload = ingest_deepeval_results(
            source_path=source_path,
            out_dir=out_dir,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    elif source_tool == "prompt-optimizer":
        payload = ingest_prompt_optimizer_assets(
            source_path=source_path,
            out_dir=out_dir,
            asset_id=asset_id,
        )
    else:
        msg = f"Unsupported ingest source `{source_tool}`"
        raise ValueError(msg)
    return {"source_tool": source_tool, **payload}


def detect_ingest_source(source_path: Path) -> str:
    """Detect which external eval/trace tool produced an export file."""

    if source_path.suffix.lower() == ".csv":
        return "langsmith"
    payload = read_json(source_path)
    if _looks_like_promptfoo(payload):
        return "promptfoo"
    if _looks_like_langfuse(payload):
        return "langfuse"
    if _looks_like_langsmith(payload):
        return "langsmith"
    if _looks_like_deepeval(payload):
        return "deepeval"
    if _looks_like_prompt_optimizer(payload):
        return "prompt-optimizer"
    msg = (
        "Could not detect export source. Use `pcl ingest promptfoo`, "
        "`pcl ingest langfuse`, `pcl ingest langsmith`, `pcl ingest deepeval`, "
        "or `pcl ingest prompt-optimizer` explicitly."
    )
    raise ValueError(msg)


def ingest_promptfoo_results(
    *,
    source_path: Path,
    out_dir: Path,
    prompt_id: str | None = None,
    provider: str | None = None,
    method: str | None = None,
) -> JsonDict:
    """Convert Promptfoo JSON eval output into one PromptControlLab scored run."""

    payload = read_json(source_path)
    rows = _promptfoo_rows(payload)
    if not rows:
        msg = f"No Promptfoo result rows found in {source_path}"
        raise ValueError(msg)
    selected = _filter_rows(rows, prompt_id=prompt_id, provider=provider)
    if not selected:
        msg = "No Promptfoo rows matched the requested prompt/provider filter"
        raise ValueError(msg)
    selected_prompt_id = prompt_id or _single_value(selected, "prompt_id", "Promptfoo prompt ids")
    selected_provider = provider or _single_value(selected, "provider", "Promptfoo providers")
    method_name = method or selected_prompt_id or "promptfoo"
    predictions = [
        _prediction_from_promptfoo_row(row, index=index, method=method_name)
        for index, row in enumerate(selected)
    ]
    summary = summarize_predictions(predictions)
    ensure_dir(out_dir)
    write_jsonl(out_dir / "predictions.jsonl", [prediction.to_json() for prediction in predictions])
    write_json(out_dir / "metrics.json", summary.to_json())
    provider_name, model_id = _split_provider_model(selected_provider)
    model_identity = detect_model_identity(provider=provider_name, model_id=model_id)
    prompt_identity = _prompt_identity(payload, selected_prompt_id)
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "promptfoo_ingest",
        "method": method_name,
        "metric": "promptfoo_score",
        "source_tool": "promptfoo",
        "source_path": str(source_path),
        "promptfoo_filter": {
            "prompt_id": selected_prompt_id,
            "provider": selected_provider,
        },
        "model": model_identity.to_json(),
    }
    if prompt_identity:
        manifest["prompt"] = prompt_identity
    write_json(out_dir / "manifest.json", manifest)
    return {
        "out_dir": str(out_dir),
        "count": len(predictions),
        "mean_score": summary.mean_score,
        "prompt_id": selected_prompt_id,
        "provider": selected_provider,
    }


def ingest_langfuse_results(
    *,
    source_path: Path,
    out_dir: Path,
    name: str | None = None,
    score_name: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    method: str | None = None,
) -> JsonDict:
    """Convert Langfuse observations/traces JSON export into one scored PCL run.

    This intentionally avoids the Langfuse SDK. The bridge is for local exported
    artifacts so teams can keep using Langfuse while adding PCL's protocol and
    research diagnostics on top.
    """

    payload = read_json(source_path)
    rows = _langfuse_rows(payload, score_name=score_name)
    if not rows:
        msg = f"No Langfuse observations with scores found in {source_path}"
        raise ValueError(msg)
    selected = _filter_langfuse_rows(rows, name=name, model=model, provider=provider)
    if not selected:
        msg = "No Langfuse rows matched the requested name/model/provider filter"
        raise ValueError(msg)
    selected_name = name or _single_value(
        selected,
        "name",
        "Langfuse observation names",
    )
    selected_model = model or _single_value(selected, "model_id", "Langfuse model ids")
    selected_provider = provider or _single_value(
        selected,
        "provider",
        "Langfuse providers",
    )
    method_name = method or selected_name or "langfuse"
    predictions = [
        _prediction_from_langfuse_row(row, index=index, method=method_name)
        for index, row in enumerate(selected)
    ]
    summary = summarize_predictions(predictions)
    ensure_dir(out_dir)
    write_jsonl(out_dir / "predictions.jsonl", [prediction.to_json() for prediction in predictions])
    write_json(out_dir / "metrics.json", summary.to_json())
    model_identity = detect_model_identity(provider=selected_provider, model_id=selected_model)
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "langfuse_ingest",
        "method": method_name,
        "metric": f"langfuse_score:{score_name or 'auto'}",
        "source_tool": "langfuse",
        "source_path": str(source_path),
        "langfuse_filter": {
            "name": selected_name,
            "score_name": score_name or "auto",
            "model": selected_model,
            "provider": selected_provider,
        },
        "model": model_identity.to_json(),
    }
    write_json(out_dir / "manifest.json", manifest)
    return {
        "out_dir": str(out_dir),
        "count": len(predictions),
        "mean_score": summary.mean_score,
        "name": selected_name,
        "model": selected_model,
        "provider": selected_provider,
    }


def ingest_langsmith_results(
    *,
    source_path: Path,
    out_dir: Path,
    experiment: str | None = None,
    score_name: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    method: str | None = None,
) -> JsonDict:
    """Convert LangSmith experiment JSON/CSV export into one scored PCL run."""

    rows = _langsmith_rows(source_path, score_name=score_name)
    if not rows:
        msg = f"No LangSmith runs with scores found in {source_path}"
        raise ValueError(msg)
    selected = _filter_langsmith_rows(
        rows,
        experiment=experiment,
        model=model,
        provider=provider,
    )
    if not selected:
        msg = "No LangSmith rows matched the requested experiment/model/provider filter"
        raise ValueError(msg)
    selected_experiment = experiment or _single_value(
        selected,
        "experiment",
        "LangSmith experiments",
    )
    selected_model = model or _single_value(selected, "model_id", "LangSmith model ids")
    selected_provider = provider or _single_value(selected, "provider", "LangSmith providers")
    method_name = method or selected_experiment or "langsmith"
    predictions = [
        _prediction_from_langsmith_row(row, index=index, method=method_name)
        for index, row in enumerate(selected)
    ]
    summary = summarize_predictions(predictions)
    ensure_dir(out_dir)
    write_jsonl(out_dir / "predictions.jsonl", [prediction.to_json() for prediction in predictions])
    write_json(out_dir / "metrics.json", summary.to_json())
    model_identity = detect_model_identity(provider=selected_provider, model_id=selected_model)
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "langsmith_ingest",
        "method": method_name,
        "metric": f"langsmith_score:{score_name or 'auto'}",
        "source_tool": "langsmith",
        "source_path": str(source_path),
        "langsmith_filter": {
            "experiment": selected_experiment,
            "score_name": score_name or "auto",
            "model": selected_model,
            "provider": selected_provider,
        },
        "model": model_identity.to_json(),
    }
    write_json(out_dir / "manifest.json", manifest)
    return {
        "out_dir": str(out_dir),
        "count": len(predictions),
        "mean_score": summary.mean_score,
        "experiment": selected_experiment,
        "model": selected_model,
        "provider": selected_provider,
    }


def ingest_deepeval_results(
    *,
    source_path: Path,
    out_dir: Path,
    score_name: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    method: str | None = None,
) -> JsonDict:
    """Convert DeepEval local TestRun JSON into one scored PCL run."""

    payload = read_json(source_path)
    rows = _deepeval_rows(payload, score_name=score_name)
    if not rows:
        msg = f"No DeepEval test cases with scores found in {source_path}"
        raise ValueError(msg)
    selected = _filter_deepeval_rows(rows, model=model, provider=provider)
    if not selected:
        msg = "No DeepEval rows matched the requested model/provider filter"
        raise ValueError(msg)
    selected_model = model or _single_value(selected, "model_id", "DeepEval model ids")
    selected_provider = provider or _single_value(selected, "provider", "DeepEval providers")
    method_name = method or _optional_str(payload.get("run_name")) or "deepeval"
    predictions = [
        _prediction_from_deepeval_row(row, index=index, method=method_name)
        for index, row in enumerate(selected)
    ]
    summary = summarize_predictions(predictions)
    ensure_dir(out_dir)
    write_jsonl(out_dir / "predictions.jsonl", [prediction.to_json() for prediction in predictions])
    write_json(out_dir / "metrics.json", summary.to_json())
    model_identity = detect_model_identity(provider=selected_provider, model_id=selected_model)
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "deepeval_ingest",
        "method": method_name,
        "metric": f"deepeval_metric:{score_name or 'auto'}",
        "source_tool": "deepeval",
        "source_path": str(source_path),
        "deepeval_filter": {
            "score_name": score_name or "auto",
            "model": selected_model,
            "provider": selected_provider,
        },
        "model": model_identity.to_json(),
    }
    write_json(out_dir / "manifest.json", manifest)
    return {
        "out_dir": str(out_dir),
        "count": len(predictions),
        "mean_score": summary.mean_score,
        "score_name": score_name or "auto",
        "model": selected_model,
        "provider": selected_provider,
    }


def ingest_prompt_optimizer_assets(
    *,
    source_path: Path,
    out_dir: Path,
    asset_id: str | None = None,
) -> JsonDict:
    """Convert prompt-optimizer exports into auditable prompt asset artifacts.

    prompt-optimizer exports are prompt candidates/favorites/templates. They do
    not normally include per-example scores, so this bridge intentionally writes
    prompt asset artifacts and a gap plan instead of fake predictions/metrics.
    """

    payload = read_json(source_path)
    assets = _prompt_optimizer_assets(payload, source_path=source_path)
    if asset_id is not None:
        assets = [
            asset
            for asset in assets
            if asset.get("id") == asset_id or asset.get("title") == asset_id
        ]
    if not assets:
        msg = "No prompt-optimizer prompt assets found in the input file"
        if asset_id is not None:
            msg = f"No prompt-optimizer prompt assets matched --asset-id {asset_id!r}"
        raise ValueError(msg)

    ensure_dir(out_dir)
    source_sha256 = f"sha256:{hashlib.sha256(source_path.read_bytes()).hexdigest()}"
    asset_bundle: JsonDict = {
        "schema": "prompt_control_lab.prompt_assets.v1",
        "source_tool": "prompt-optimizer",
        "artifact_type": "prompt_assets",
        "source_path": str(source_path),
        "source_sha256": source_sha256,
        "evaluation_status": "not_scored",
        "asset_count": len(assets),
        "asset_ids": [str(asset.get("id", "")) for asset in assets],
        "assets": assets,
        "boundary": (
            "prompt-optimizer exports are prompt candidates and prompt assets. "
            "This import does not prove that any prompt improved."
        ),
        "next_actions": _prompt_optimizer_next_actions(out_dir),
    }
    scaffold = _write_prompt_optimizer_eval_scaffold(
        out_dir=out_dir,
        asset_bundle=asset_bundle,
    )
    asset_bundle["eval_scaffold"] = scaffold
    asset_bundle["next_actions"] = [
        *_string_list(asset_bundle.get("next_actions")),
        f"Edit `{scaffold['readme_path']}` to turn imported assets into paired evidence.",
    ]
    gap_plan = _prompt_optimizer_gap_plan(asset_bundle)
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "prompt_optimizer_asset_import",
        "source_tool": "prompt-optimizer",
        "artifact_type": "prompt_assets",
        "source_path": str(source_path),
        "source_sha256": source_sha256,
        "evaluation_status": "not_scored",
        "asset_count": len(assets),
    }
    if asset_id is not None:
        manifest["asset_filter"] = asset_id
    write_json(out_dir / "prompt_assets.json", asset_bundle)
    write_json(out_dir / "prompt_optimizer_gap_plan.json", gap_plan)
    write_json(out_dir / "manifest.json", manifest)
    (out_dir / "prompt_assets.md").write_text(
        render_prompt_assets_markdown(asset_bundle),
        encoding="utf-8",
    )
    (out_dir / "prompt_assets.html").write_text(
        render_prompt_assets_html(asset_bundle),
        encoding="utf-8",
    )
    (out_dir / "prompt_optimizer_gap_plan.md").write_text(
        render_prompt_optimizer_gap_plan_markdown(gap_plan),
        encoding="utf-8",
    )
    (out_dir / "prompt_optimizer_gap_plan.html").write_text(
        render_prompt_optimizer_gap_plan_html(gap_plan),
        encoding="utf-8",
    )
    return {
        "out_dir": str(out_dir),
        "artifact_type": "prompt_assets",
        "asset_count": len(assets),
        "asset_ids": asset_bundle["asset_ids"],
        "evaluation_status": "not_scored",
        "prompt_assets_path": str(out_dir / "prompt_assets.json"),
        "prompt_assets_html_path": str(out_dir / "prompt_assets.html"),
        "gap_plan_path": str(out_dir / "prompt_optimizer_gap_plan.json"),
        "eval_scaffold_path": str(
            out_dir / "eval_scaffold" / "prompt_optimizer_eval_scaffold.json"
        ),
        "boundary": asset_bundle["boundary"],
        "next_actions": asset_bundle["next_actions"],
    }


def _promptfoo_rows(payload: JsonDict) -> list[JsonDict]:
    results = payload.get("results")
    if isinstance(results, list):
        return [_row_from_v3_result(item) for item in results if isinstance(item, dict)]
    table = payload.get("table")
    if isinstance(table, dict):
        body = table.get("body")
        if isinstance(body, list):
            rows: list[JsonDict] = []
            for row in body:
                if isinstance(row, dict):
                    rows.extend(_rows_from_table_row(row))
            return rows
    return []


def _looks_like_promptfoo(payload: JsonDict) -> bool:
    if isinstance(payload.get("table"), dict):
        return True
    results = payload.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and (
                "promptId" in item or "testCase" in item or "gradingResult" in item
            ):
                return True
    return False


def _looks_like_langfuse(payload: JsonDict) -> bool:
    for key in ["observations", "generations"]:
        if isinstance(payload.get(key), list):
            return True
    for key in ["traces", "data"]:
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and isinstance(item.get("observations"), list):
                    return True
    return False


def _looks_like_langsmith(payload: JsonDict) -> bool:
    for key in ["runs", "examples"]:
        if isinstance(payload.get(key), list):
            return True
    for key in ["results", "data"]:
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and (
                    "experiment_name" in item
                    or "reference_outputs" in item
                    or "feedback_stats" in item
                ):
                    return True
    return False


def _looks_like_deepeval(payload: JsonDict) -> bool:
    tool = payload.get("tool") or payload.get("source_tool") or payload.get("framework")
    if isinstance(tool, str) and "deepeval" in tool.lower():
        return True
    for key in ["test_cases", "testCases", "test_results", "testResults"]:
        if isinstance(payload.get(key), list):
            return True
    for key in ["test_run", "testRun", "run"]:
        value = payload.get(key)
        if isinstance(value, dict):
            for nested_key in ["test_cases", "testCases", "test_results", "testResults"]:
                if isinstance(value.get(nested_key), list):
                    return True
    return False


def _looks_like_prompt_optimizer(payload: JsonDict) -> bool:
    favorites = payload.get("favorites")
    if isinstance(favorites, list):
        return any(
            isinstance(item, dict)
            and isinstance(item.get("content"), str)
            and ("functionMode" in item or "useCount" in item or "tags" in item)
            for item in favorites
        )
    export_info = payload.get("export_info")
    template = payload.get("template")
    if isinstance(export_info, dict) and export_info.get("format") == "template":
        return isinstance(template, dict)
    return False
