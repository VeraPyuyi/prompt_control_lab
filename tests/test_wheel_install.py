"""Installed-package diagnostics and an opt-in clean-wheel acceptance test.

Set PCL_TEST_WHEEL to a built wheel to run the offline clean-venv test. Its child
processes run outside the checkout with PYTHONPATH removed and isolated Python.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.integrations import doctor


def test_doctor_uses_packaged_policy_and_hook_without_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1] / "src"))
    monkeypatch.chdir(tmp_path)
    policy = doctor._check_guard_policy(tmp_path)
    hook = doctor._check_claude_hook(tmp_path)
    assert policy["status"] == "pass"
    assert hook["status"] == "pass"
    assert "Packaged" in policy["message"]
    assert "Packaged" in hook["message"]
    assert not (tmp_path / "examples").exists()
    assert not (tmp_path / "plugins").exists()


def test_missing_cursor_server_is_skipped_separately_from_packaged_rule(tmp_path: Path) -> None:
    server = doctor._check_cursor_mcp(tmp_path)
    assert server["status"] == "skipped"
    assert "not run" in server["message"]
    template = doctor._check_cursor_rule()
    assert template["status"] == "pass"
    assert template["name"] == "cursor_rule_template"


def test_doctor_does_not_hide_invalid_checkout_policy_with_packaged_fallback(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "examples" / "guard.policy.yaml"
    policy.parent.mkdir()
    policy.write_text("block_at: impossible\n", encoding="utf-8")
    assert doctor._check_guard_policy(tmp_path)["status"] == "fail"


def test_missing_packaged_template_is_a_distribution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(package: str) -> Any:
        raise ModuleNotFoundError(package)

    monkeypatch.setattr("promptcontrollab.integrations.doctor.resources.files", unavailable)
    assert doctor._check_cursor_rule()["status"] == "fail"
    assert doctor._run_packaged_claude_hook()["status"] == "fail"


@pytest.mark.parametrize("legacy", [False, True])
def test_ui_install_hint_uses_published_extra_for_both_frontends(
    legacy: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    assert main(["ui", "--no-browser", *(["--legacy-streamlit"] if legacy else [])]) == 2
    message = capsys.readouterr().err
    assert "promptcontrollab[ui]" in message
    assert "pip install -e" not in message
    assert "streamlit" in message if legacy else "fastapi" in message


def test_wheel_install_in_clean_venv_outside_source(tmp_path: Path) -> None:
    selected = os.environ.get("PCL_TEST_WHEEL")
    if not selected:
        pytest.skip("Set PCL_TEST_WHEEL to run the built-wheel acceptance test")
    wheel = Path(selected).resolve(strict=True)
    assert wheel.suffix == ".whl"
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        for path in (
            "promptcontrollab/integrations/web_static/index.html",
            "promptcontrollab/template_data/claude_code/prompt_guard.py",
            "promptcontrollab/template_data/cursor_rule/prompt_control_lab.mdc",
            "promptcontrollab/evaluation/experiments/optimization.py",
        ):
            assert path in names, f"Missing wheel resource: {path}"
        assert any(
            name.startswith("promptcontrollab/integrations/web_static/assets/")
            and name.endswith(".js")
            for name in names
        )
        index = archive.read("promptcontrollab/integrations/web_static/index.html").decode("utf-8")
        references = re.findall(r"""(?:src|href)=["'](/assets/[^"']+)["']""", index)
        assert references, "Bundled React HTML does not reference built assets"
        for reference in references:
            assert "promptcontrollab/integrations/web_static" + reference in names
        assert not any(
            "node_modules/" in name or "__pycache__/" in name or name.endswith(".pyc")
            for name in names
        )
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "OPENAI_API_KEY"):
        environment.pop(key, None)
    isolated = tmp_path / "installed"
    outside = tmp_path / "outside-source"
    outside.mkdir()

    def run(command: list[str], *, expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command, cwd=outside, env=environment, text=True, capture_output=True, timeout=60
        )
        assert result.returncode == expected, result.stderr or result.stdout
        return result

    run([sys.executable, "-m", "venv", str(isolated)])
    python = isolated / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(python), "-I", "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)])
    probe = run(
        [str(python), "-I", "-c", "import promptcontrollab; print(promptcontrollab.__file__)"]
    )
    assert isolated.resolve() in Path(probe.stdout.strip()).resolve().parents
    run([str(python), "-I", "-m", "promptcontrollab", "--help"])
    response = run([str(python), "-I", "-m", "promptcontrollab", "doctor", "--json"])
    checks = {row["name"]: row for row in json.loads(response.stdout)["checks"]}
    for name in ("guard_policy", "claude_code_hook", "cursor_rule_template", "demo_report"):
        assert checks[name]["status"] == "pass", checks[name]
    assert checks["cursor_mcp_server"]["status"] == "skipped"
    assert "not run" in checks["cursor_mcp_server"]["message"]
    ui = run([str(python), "-I", "-m", "promptcontrollab", "ui", "--no-browser"], expected=2)
    assert "promptcontrollab[ui]" in ui.stderr
    templates = outside / "installed-templates"
    run(
        [
            str(python),
            "-I",
            "-m",
            "promptcontrollab",
            "install-plugin",
            "all",
            "--target",
            str(templates),
        ]
    )
    assert (templates / "cursor" / "prompt_control_lab.mdc").is_file()
    assert (templates / "claude-code" / "prompt_guard.py").is_file()
    assert not list(templates.rglob("*.pyc"))
    assert not (outside / "examples").exists()
    assert not (outside / "plugins").exists()
    destination = os.environ.get("PCL_WHEEL_EVIDENCE")
    if destination:
        evidence = Path(destination).resolve()
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(
            json.dumps(
                {
                    "schema_version": "wheel-install-validation/v1",
                    "wheel": str(wheel),
                    "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    "status": "passed",
                    "installed_package": probe.stdout.strip(),
                    "isolated_environment": str(isolated),
                    "working_directory": str(outside),
                    "doctor_checks": checks,
                    "react_asset_references": references,
                    "ui_dependencies": "not installed; actionable published-extra hint verified",
                    "live_provider_calls": 0,
                    "cursor_mcp_initialization": "skipped; server absent",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
