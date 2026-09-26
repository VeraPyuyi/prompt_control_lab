"""Internal typed subprocess entry; uploaded code is never imported."""

from __future__ import annotations

import csv
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from promptcontrollab.evaluation.experiments.storage import active_job, alive, read_json, write_json

from .bundles import bundle_directory, data_path, json_value, verify_bundle


def saved_summary_preview(data: Path, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bounded display of supplied values, with no inferred statistical meaning."""
    previews = []
    for row in files[:50]:
        path = data_path(data, row["path"])
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                values = []
                for index, cells in enumerate(csv.reader(stream)):
                    if index >= 101:
                        break
                    values.append([cell[:512] for cell in cells[:100]])
            preview: Any = values
            limit = "First 100 rows, 100 columns and 512 characters per cell."
        elif path.suffix.lower() == ".json":
            text = json.dumps(json_value(path), ensure_ascii=False, allow_nan=False)
            preview = text[:65536]
            limit = "First 65,536 characters; longer saved records remain in the replay bundle."
        else:
            preview = row.get("arrays", [])
            limit = "Array metadata only; raw reconstruction needs a supported analysis protocol."
        previews.append({"input": row["path"], "saved_values": preview, "display_limit": limit})
    return previews


def main() -> None:
    """Run one allowlisted CPU analysis while monitoring its parent execution lease."""
    root, identifier, temporary_arg = sys.argv[1:]
    workspace = Path(root).resolve()
    from .engine import job_directory

    directory = job_directory(workspace, identifier)
    temporary = Path(temporary_arg).resolve()
    if temporary.parent != (directory / "attempts").resolve():
        raise ValueError("Invalid worker attempt path")
    request = read_json(temporary / "request.json")

    def watch_parent() -> None:
        while True:
            owner = active_job(workspace)
            if (
                not alive(request["parent_pid"])
                or not owner
                or owner.get("token") != request["lease_token"]
            ):
                os._exit(75)
            time.sleep(0.5)

    threading.Thread(target=watch_parent, daemon=True).start()
    output = temporary / "output"
    output.mkdir()
    try:
        bundle = verify_bundle(workspace, request["bundle_id"])
        data = bundle_directory(workspace, bundle["id"]) / "data"
        analysis = request["analysis"]
        if analysis not in bundle["analyses"]:
            raise ValueError("Unsupported research operation")
        if analysis["kind"] == "bootstrap":
            from promptcontrollab.diagnostics.research_replay import run_suite

            result = run_suite(data, analysis["suite"], output)
        elif analysis["kind"] == "saved-summary":
            from .summaries import write_saved_tables

            selected = [row for row in bundle["files"] if row["path"] in analysis["inputs"]]
            result = write_saved_tables(
                analysis["tool"], saved_summary_preview(data, selected), output
            )
        elif analysis["kind"] == "inventory":
            from promptcontrollab.diagnostics.research_tools.common import write_reports

            result = write_reports(
                {
                    "kind": "inventory",
                    "synthetic": bundle["synthetic"],
                    "capabilities": bundle["capabilities"],
                    "files": bundle["files"],
                    "saved_summaries": saved_summary_preview(data, bundle["files"]),
                    "statistical_support": "not_evaluated",
                    "scope": "Saved summaries only; no paired statistics are inferred.",
                },
                output,
            )
        else:
            from promptcontrollab.diagnostics.research_tools import analyze_research

            result = analyze_research(
                analysis["kind"], json_value(data_path(data, analysis["input"])), output
            )
        write_json(temporary / "receipt.json", result)
    except BaseException as error:
        message = str(error).replace(str(workspace), "[workspace]")
        write_json(
            temporary / "failure.json",
            {"error_type": type(error).__name__, "error": message[:1000]},
        )
        raise


if __name__ == "__main__":
    main()
