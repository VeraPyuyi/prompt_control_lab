from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from promptcontrollab.integrations.hf_space import build_space_bundle
from promptcontrollab.integrations.ui.app import HF_DEMO_TEXT
from promptcontrollab.integrations.ui.data import load_run_detail

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_hugging_face_space_layout_is_safe_and_complete() -> None:
    space = PROJECT_ROOT / "deploy" / "huggingface"
    required = {
        "Dockerfile",
        "app.py",
        "README.md",
        "space_manifest.json",
    }

    assert required <= {path.name for path in space.iterdir() if path.is_file()}
    assert (space / "demo_runs" / "quick" / "manifest.json").is_file()
    assert (space / "demo_runs" / "checkpoint" / "posttrain_gate.json").is_file()
    assert (space / "demo_runs" / "agent" / "audit_result.json").is_file()

    dockerfile = (space / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12" in dockerfile
    assert "PCL_DEPLOYMENT_MODE=hf_demo" in dockerfile
    assert "7860" in dockerfile
    assert "--server.maxUploadSize=5" in dockerfile
    assert "HF_TOKEN" not in dockerfile
    assert "DEEPSEEK_API_KEY" not in dockerfile

    readme = (space / "README.md").read_text(encoding="utf-8")
    assert "sdk: docker" in readme
    assert "app_port: 7860" in readme
    assert "https://github.com/VeraPyuyi/prompt_control_lab" in readme

    quick = load_run_detail(space / "demo_runs" / "quick")
    checkpoint = load_run_detail(space / "demo_runs" / "checkpoint")
    agent = load_run_detail(space / "demo_runs" / "agent")
    assert quick["candidate_score"] == 0.875
    assert quick["first_comparison"]["mean_delta"] == 0.25
    assert set(checkpoint["diagnostics"]) == {
        "green_certificate",
        "posterior_certificate",
        "terminal_sensitivity",
    }
    assert checkpoint["posttrain_gate"]["decision"] == "needs_review"
    assert agent["audit"]["tests_passed"] is True
    assert agent["control_run"]["run_id"] == "hf-demo-agent-run"


def test_build_space_bundle_copies_only_curated_assets_and_records_source(tmp_path: Path) -> None:
    wheel = _write_fixture_wheel(tmp_path / "promptcontrollab-0.2.0a1-py3-none-any.whl")
    output = tmp_path / "space"

    manifest = build_space_bundle(
        project_root=PROJECT_ROOT,
        output_dir=output,
        wheel_path=wheel,
        source_commit="abc123",
    )

    assert manifest["source_commit"] == "abc123"
    assert manifest["package_version"] == "0.2.0a1"
    assert manifest["demo_data_version"] == "1"
    assert (output / "wheels" / wheel.name).is_file()
    assert (output / "README.zh.md").is_file()
    written = json.loads((output / "space_manifest.json").read_text(encoding="utf-8"))
    assert written == manifest
    assert not (output / "tests").exists()
    assert not (output / "plugins").exists()
    assert not list(output.rglob("*.mp4"))
    assert not list(output.rglob("*.pt"))
    assert not list(output.rglob("*.npz"))


def test_hugging_face_deploy_workflow_is_manual_or_release_only() -> None:
    workflow = PROJECT_ROOT / ".github" / "workflows" / "deploy-huggingface-space.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "release:" in text
    assert "push:" not in text
    assert "HF_TOKEN" in text
    assert "HF_SPACE_ID" in text
    assert "build_hf_space_bundle.py" in text
    assert "get_space_runtime" in text
    assert "\n    env:\n      HF_TOKEN:" not in text
    assert 'private=False' in text
    assert 'space_hardware="cpu-basic"' in text
    assert 'request_space_hardware(space_id, "cpu-basic")' in text
    assert 'runtime.hardware' in text
    assert text.index("docker build") < text.index("api.upload_folder")


def test_bilingual_readmes_link_the_space_and_explain_demo_boundaries() -> None:
    english = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (PROJECT_ROOT / "README.zh.md").read_text(encoding="utf-8")

    assert "Try on Hugging Face" in english
    assert "在 Hugging Face 体验" in chinese
    assert "docs/assets/hf_space.en.png" in english
    assert "docs/assets/hf_space.zh.png" in chinese
    assert "deploy/huggingface/README.md" in english
    assert "deploy/huggingface/README.md" in chinese
    assert (PROJECT_ROOT / "docs" / "huggingface_space.en.md").is_file()
    assert (PROJECT_ROOT / "docs" / "huggingface_space.zh.md").is_file()


def test_public_demo_privacy_copy_describes_temporary_server_uploads() -> None:
    assert "temporary" in HF_DEMO_TEXT["en"]["subtitle"].lower()
    assert "server" in HF_DEMO_TEXT["en"]["subtitle"].lower()
    assert "临时" in HF_DEMO_TEXT["zh"]["subtitle"]
    assert "服务器" in HF_DEMO_TEXT["zh"]["subtitle"]


def test_space_bundle_rejects_files_not_declared_by_the_source_manifest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    source = root / "deploy" / "huggingface"
    source.mkdir(parents=True)
    for name in ("Dockerfile", "app.py", "README.md", "README.zh.md"):
        (source / name).write_text(name, encoding="utf-8")
    (source / "demo_runs").mkdir()
    (source / "demo_runs" / "expected.json").write_text('{"value":1}', encoding="utf-8")
    (source / "demo_runs" / "private.json").write_text('{"secret":"value"}', encoding="utf-8")
    (source / "space_manifest.json").write_text(
        json.dumps(
            {
                "demo_data_version": "1",
                "demo_files": ["demo_runs/expected.json"],
            }
        ),
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text('version = "0.2.0a1"\n', encoding="utf-8")
    wheel = _write_fixture_wheel(tmp_path / "promptcontrollab-0.2.0a1-py3-none-any.whl")

    with pytest.raises(ValueError, match="not declared"):
        build_space_bundle(
            project_root=root,
            output_dir=tmp_path / "space",
            wheel_path=wheel,
            source_commit="abc123",
        )


def test_space_bundle_strips_plugin_templates_from_deployment_wheel(tmp_path: Path) -> None:
    wheel = _write_fixture_wheel(tmp_path / "promptcontrollab-0.2.0a1-py3-none-any.whl")
    output = tmp_path / "space"

    build_space_bundle(
        project_root=PROJECT_ROOT,
        output_dir=output,
        wheel_path=wheel,
        source_commit="abc123",
    )

    deployed_wheel = output / "wheels" / wheel.name
    with ZipFile(deployed_wheel) as archive:
        names = set(archive.namelist())
        record = archive.read("promptcontrollab-0.2.0a1.dist-info/RECORD").decode("utf-8")
    assert "promptcontrollab/__init__.py" in names
    assert not any("promptcontrollab/template_data/" in name for name in names)
    assert "template_data" not in record


def _write_fixture_wheel(path: Path) -> Path:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("promptcontrollab/__init__.py", '__version__ = "0.2.0a1"\n')
        archive.writestr("promptcontrollab/template_data/cursor_rule/rule.mdc", "fixture")
        archive.writestr(
            "promptcontrollab-0.2.0a1.dist-info/METADATA",
            "Metadata-Version: 2.3\nName: promptcontrollab\nVersion: 0.2.0a1\n",
        )
        archive.writestr(
            "promptcontrollab-0.2.0a1.dist-info/WHEEL",
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr("promptcontrollab-0.2.0a1.dist-info/RECORD", "")
    return path
