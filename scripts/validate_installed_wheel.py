"""Validate an installed UI wheel from isolated Python outside the source directory.

Install the selected wheel with its ui extra into a clean virtual environment,
then run this script using that environment's Python with -I. The script performs
only deterministic local checks and never sends a model request.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from importlib.resources import files
from pathlib import Path
from typing import Any, cast


def _installed_files(wheel: Path) -> tuple[Path, int]:
    import promptcontrollab

    package = Path(promptcontrollab.__file__).resolve().parent
    assert Path(sys.prefix).resolve() in package.parents, "Package is outside the clean environment"
    count = 0
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith("promptcontrollab/") and not name.endswith("/"):
                installed = package.parent / name
                assert installed.is_file(), f"Missing installed wheel file: {name}"
                assert installed.read_bytes() == archive.read(name), f"Stale installed file: {name}"
                count += 1
    assert count > 100
    return package, count


def _library_checks(root: Path) -> dict[str, Any]:
    from promptcontrollab.evaluation.experiments import (
        create_experiment,
        export_experiment,
        run_experiment,
    )

    examples = files("promptcontrollab").joinpath("example_data")
    fixture = examples.joinpath("experiments").joinpath("synthetic-import.json")
    spec = json.loads(fixture.read_text(encoding="utf-8"))
    research = examples.joinpath("research")
    sample_names = ["readout", "response", "measurement-value", "transfer", "replay"]
    for name in sample_names:
        assert isinstance(json.loads(research.joinpath(f"{name}.json").read_text()), dict)
    imported = run_experiment(root, create_experiment(root, spec)["id"])
    assert imported["status"] == "completed"
    assert imported["assessment"]["coverage"]["matched"] == 4
    calls = 0

    def provider(**kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "output_text": "yes" if kwargs["prompt"].startswith("candidate") else "no",
            "model_id": "wheel-synthetic-stub",
            "usage": {"input_tokens": 2, "output_tokens": 1},
        }

    spec.update(
        name="Synthetic wheel acceptance: deterministic callable",
        operation="run",
        data=[
            {"id": str(index), "input": f"item {index}", "expected": "yes"} for index in range(4)
        ],
        baseline={
            "provider": "openai",
            "model": "wheel-synthetic-stub",
            "prompt": "baseline",
            "max_output_tokens": 10,
        },
        candidate={
            "provider": "openai",
            "model": "wheel-synthetic-stub",
            "prompt": "candidate",
            "max_output_tokens": 10,
        },
        budget={"max_calls": 8, "max_output_tokens": 80, "max_seconds": 30},
    )
    spec.pop("predictions")
    ran = run_experiment(root, create_experiment(root, spec)["id"], provider)
    assert ran["status"] == "completed"
    assert ran["assessment"]["coverage"]["matched"] == 4
    assert calls == ran["budget"]["calls"] == 8
    archives = []
    for job in (imported, ran):
        archive = export_experiment(root, job["id"])
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            assert any(name.endswith("report.en.html") for name in names)
            assert any(name.endswith("records.json") for name in names)
            assert all(name.startswith(job["id"] + "/") and ".." not in name for name in names)
        archives.append(str(archive))
    return {
        "import_job": imported["id"],
        "run_job": ran["id"],
        "synthetic_calls": calls,
        "packaged_research_examples": sample_names,
        "exports": archives,
    }


def _http_checks(root: Path, stage: str) -> dict[str, Any]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    environment = os.environ.copy()
    environment["PCL_UI_RUNS"] = str(root)
    environment["PCL_DEPLOYMENT_MODE"] = "local"
    command = [
        sys.executable,
        "-I",
        "-m",
        "uvicorn",
        "promptcontrollab.integrations.web_api:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    base = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path: str, headers: dict[str, str] | None = None) -> bytes:
        with opener.open(
            urllib.request.Request(base + path, headers=headers or {}), timeout=5
        ) as response:
            return cast(bytes, response.read())

    with (root / "ui-server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    health = json.loads(request("/api/health"))
                    assert health["status"] == "ok"
                    if stage == "final":
                        assert health["mode"] == "local_session"
                    break
                except (urllib.error.URLError, ConnectionError):
                    assert server.poll() is None, "Installed UI exited before readiness"
                    assert time.monotonic() < deadline, "Installed UI did not become ready"
                    time.sleep(0.1)
            html = request("/").decode("utf-8")
            assets = re.findall(r"""(?:src|href)=["'](/assets/[^"']+)["']""", html)
            assert assets
            for asset in assets:
                assert request(asset)
            assert json.loads(request("/api/session"))["enabled"] is True
            assert len(json.loads(request("/api/experiments"))["experiments"]) == 2
            assert isinstance(json.loads(request("/api/research-examples/readout")), dict)
            try:
                request("/api/runs", {"Host": "attacker.example"})
            except urllib.error.HTTPError as exc:
                assert exc.code == 403
            else:
                raise AssertionError("Host guard did not reject the hostile Host")
            return {
                "status": "passed",
                "assets": assets,
                "node_available": False,
                "server": "installed uvicorn factory",
                "host_guard": "passed",
                "health": health,
            }
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


def _research_checks(root: Path, library: dict[str, Any]) -> dict[str, Any]:
    """Run all packaged CLI examples and replay an exported bundle after relocation."""
    dependencies = {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "gepa")}
    assert dependencies["gepa"] == "0.1.4"
    examples = files("promptcontrollab").joinpath("example_data").joinpath("research")
    results = {}
    inputs = root / "research-inputs"
    inputs.mkdir()
    for kind in ("readout", "response", "measurement-value", "transfer", "replay"):
        source = inputs / f"{kind}.json"
        source.write_text(examples.joinpath(f"{kind}.json").read_text(), encoding="utf-8")
        destination = root / "research-results" / kind
        command = [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            "-m",
            "promptcontrollab",
            "research",
            kind,
            "--input",
            str(source),
            "--out",
            str(destination),
        ]
        completed = subprocess.run(command, encoding="utf-8", capture_output=True, timeout=120)
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        assert result["kind"] == kind
        for filename in ("report.json", "metrics.csv", "report.en.html", "report.zh.html"):
            assert (destination / filename).is_file(), f"Missing {kind} artifact {filename}"
        if kind == "replay":
            assert result["integrity"]["status"] == "passed"
        results[kind] = {"status": "passed", "directory": str(destination)}
    relocated = root / "relocated"
    relocated.mkdir()
    replay_results = []
    for index, exported in enumerate(library["exports"]):
        source = relocated / f"experiment-{index}.zip"
        shutil.copyfile(exported, source)
        destination = relocated / f"recomputed-{index}"
        command = [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            "-m",
            "promptcontrollab",
            "experiment",
            "replay",
            "--bundle",
            str(source),
            "--out",
            str(destination),
        ]
        completed = subprocess.run(command, encoding="utf-8", capture_output=True, timeout=60)
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        assert result["integrity"]["status"] == "passed", result["integrity"]
        assert result["numerical_replay"]["status"] == "passed", result["numerical_replay"]
        replay_results.append(
            {
                "archive": str(source),
                "directory": str(destination),
                "integrity": "passed",
                "numerical_replay": "passed",
                "premise_checks": result["premise_checks"]["status"],
            }
        )
    return {"dependencies": dependencies, "examples": results, "relocated_replay": replay_results}


def main() -> None:
    """Verify exact installed bytes and write stage-specific installation evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--stage", choices=["provisional", "final"], required=True)
    parser.add_argument(
        "--research",
        action="store_true",
        help="Also validate research/optimize extras and relocated offline replay",
    )
    args = parser.parse_args()
    assert sys.flags.isolated, "Run with Python -I"
    assert sys.prefix != sys.base_prefix, "Run in a clean virtual environment"
    assert not (Path.cwd() / "pyproject.toml").exists(), "Run outside the source root"
    os.environ["PATH"] = str(Path(sys.executable).parent)
    for key in list(os.environ):
        if (
            key in {"PYTHONPATH", "PYTHONHOME"}
            or key.endswith("API_KEY")
            or key.startswith("PCL_SESSION_")
        ):
            os.environ.pop(key, None)
    assert shutil.which("node") is None
    wheel = args.wheel.resolve(strict=True)
    package, matched = _installed_files(wheel)
    root = args.runs.resolve()
    root.mkdir(parents=True, exist_ok=False)
    dependencies = {
        name: importlib.metadata.version(name)
        for name in ("fastapi", "uvicorn", "streamlit", "plotly")
    }
    library = _library_checks(root)
    doctor = subprocess.run(
        [sys.executable, "-I", "-m", "promptcontrollab", "doctor", "--json"],
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
    )
    checks = {row["name"]: row for row in json.loads(doctor.stdout)["checks"]}
    for name in ("guard_policy", "claude_code_hook", "cursor_rule_template", "demo_report"):
        assert checks[name]["status"] == "pass", checks[name]
    assert checks["cursor_mcp_server"]["status"] == "skipped"
    evidence = {
        "schema_version": "wheel-ui-validation/v1",
        "stage": args.stage,
        "wheel": str(wheel),
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "status": "passed",
        "installed_package": str(package),
        "matching_files": matched,
        "working_directory": str(Path.cwd()),
        "python": sys.executable,
        "ui_dependencies": dependencies,
        "library": library,
        "http": _http_checks(root, args.stage),
        "doctor_checks": checks,
        "live_provider_calls": 0,
        "evidence_scope": "synthetic installation; no live model or editor acceptance",
    }
    if args.research:
        evidence["research"] = _research_checks(root, library)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "passed",
                "stage": args.stage,
                "sha256": evidence["sha256"],
                "evidence": str(args.output.resolve()),
            }
        )
    )


if __name__ == "__main__":
    main()
