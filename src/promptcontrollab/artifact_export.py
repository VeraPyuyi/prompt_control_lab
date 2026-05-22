"""Export PromptControlLab artifacts."""

from __future__ import annotations

import zipfile
from pathlib import Path

from promptcontrollab.files import JsonDict, ensure_dir
from promptcontrollab.report_model import ReportModel


def export_report_zip(*, run_dir: Path, zip_path: Path) -> JsonDict:
    """Write a zip archive containing recognized artifacts from one run."""

    model = ReportModel.from_run(run_dir)
    ensure_dir(zip_path.parent)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in model.artifacts:
            path = run_dir / relative
            if path.exists() and path.is_file():
                archive.write(path, arcname=relative.replace("\\", "/"))
    return {
        "run_dir": str(run_dir),
        "zip_path": str(zip_path),
        "artifacts": model.artifacts,
        "artifact_count": len(model.artifacts),
    }
