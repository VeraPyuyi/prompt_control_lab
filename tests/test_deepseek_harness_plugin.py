from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "deepseek-harness"
TEMPLATE = ROOT / "src" / "promptcontrollab" / "template_data" / "deepseek_harness"


INSTALLABLE_FILES = {
    "package-lock.json",
    "package.json",
    "tsconfig.json",
    "cordis.patch.yml",
    "compatibility.json",
    "COMPATIBILITY.md",
    "README.md",
    "README.zh.md",
    "src/bridge.ts",
    "src/config.ts",
    "src/decisions.ts",
    "src/index.ts",
    "src/observation-queue.ts",
    "src/privacy.ts",
    "src/protocol.ts",
    "src/run-lifecycle.ts",
}


def _read(relative: str) -> str:
    return (PLUGIN / relative).read_text(encoding="utf-8")


def test_plugin_contract_pins_the_verified_harness_surface() -> None:
    contract = json.loads(_read("compatibility.json"))

    assert contract["schema"] == "prompt_control_lab.deepseek_harness.compatibility.v1"
    assert contract["deepseek_harness"]["version"] == "0.1.1-rc.2"
    assert contract["deepseek_harness"]["commit"] == (
        "b150a551b8d465e31e418e1b2eaf5e79bbb7d28e"
    )
    assert contract["bridge"]["protocol"] == "prompt_control_lab.bridge.v1"
    assert set(contract["bridge"]["methods"]) == {
        "harness_session_start",
        "harness_pre_step",
        "harness_tool_pre_execute",
        "harness_event",
        "harness_turn_end",
        "harness_status",
        "harness_finalize",
    }
    assert contract["privacy"]["raw_prompt_transport_only"] is True
    assert contract["privacy"]["persist_hidden_reasoning"] is False
    assert contract["privacy"]["persist_api_keys"] is False


def test_plugin_is_native_cordis_and_maps_required_events() -> None:
    source = _read("src/index.ts")
    decisions = _read("src/decisions.ts")
    privacy = _read("src/privacy.ts")

    for event in (
        "agent/session-start",
        "agent/pre-step",
        "agent/request",
        "agent/request-error",
        "tools/pre-execute",
        "tools/post-execute",
        "tools/result",
        "session/event",
        "agent/turn-stopping",
    ):
        assert f"ctx.on('{event}'" in source
    assert "event.type === 'turn/end'" in source
    assert "return { kind: 'reject' }" in decisions
    assert "return { kind: 'deny', reason:" in source
    assert "autoRecover" in source
    assert "repeat-tool-reminder" in privacy
    assert "timeout" in privacy
    assert "execSync" not in source
    assert "spawnSync" not in source


def test_pre_step_gates_the_final_downstream_batch_once() -> None:
    source = _read("src/index.ts")

    assert "gateFinalPreStep({" in source
    assert "inspect: async (prompt, gateSignal)" in source
    assert "next," in source
    assert "extractPromptText(messages)" not in source


def test_bridge_is_persistent_and_observations_are_bounded() -> None:
    bridge = _read("src/bridge.ts")
    queue = _read("src/observation-queue.ts")

    assert "spawn(" in bridge
    assert "pcl" in bridge
    assert "bridge" in bridge
    assert "serve" in bridge
    assert "--transport" in bridge
    assert "stdio" in bridge
    assert "harnessPreStep" in bridge
    assert "harnessToolPreExecute" in bridge
    assert "harnessEvent" in bridge
    assert "harnessTurnEnd" in bridge
    assert "harnessStatus" in bridge
    assert "harnessFinalize" in bridge
    assert "class BoundedObservationQueue" in queue
    assert "dropped" in queue


def test_session_observations_filter_chunks_and_protect_critical_calls() -> None:
    source = _read("src/index.ts")

    assert "if (!shouldObserveSessionEvent(event.type)) return" in source
    assert "observations.enqueueCritical(() => bridge.harnessTurnEnd" in source
    assert "observations.enqueueCritical(() => bridge.harnessFinalize" in source


def test_disposal_serializes_finalization_before_fresh_resume() -> None:
    source = _read("src/index.ts")

    assert "new SessionRunLifecycle<Agent, RunState>" in source
    assert "void lifecycle.dispose(agent)" in source
    assert "const runs = new Map" not in source
    assert "const starts = new Map" not in source


def test_bridge_diagnostics_never_include_raw_child_or_rpc_text() -> None:
    source = _read("src/index.ts")
    bridge = _read("src/bridge.ts")

    assert "bridgeFailureCategory(error)" in source
    assert "error.message" not in source
    assert "String(error)" not in source
    assert "stderrTail" not in bridge
    assert "response.error.message" not in bridge
    assert "String(chunk)" not in bridge


def test_request_observations_include_deterministic_retry_attempts() -> None:
    source = _read("src/index.ts")

    assert "retryAttempts: new RetryAttemptTracker()" in source
    assert "state.retryAttempts.next('agent/request', turn, step)" in source
    assert "state.retryAttempts.next('agent/request-error', turn, step)" in source
    assert source.count("attempt,") >= 4


def test_async_gates_forward_the_harness_abort_signal() -> None:
    source = _read("src/index.ts")

    assert "await settleWithAbort(ensureRun(agent), gateSignal)" in source
    assert "}, gateSignal)" in source
    assert "await settleWithAbort(ensureRun(exec.agent), exec.signal)" in source
    assert "}, exec.signal)" in source


def test_config_defaults_are_safe_and_feedback_is_bounded() -> None:
    source = _read("src/config.ts")
    plugin = _read("src/index.ts")

    assert "mode: 'suggest'" in source
    assert "capture: 'redacted'" in source
    assert "feedback: 'summary'" in source
    assert "autoRecover: false" in source
    assert "bridgeFailure: 'warn'" in source
    assert "exposeStatusTool: false" in source
    assert "feedbackMaxChars" in source
    assert "observationQueueSize" in source
    assert "auto_recover: config.autoRecover" in plugin
    assert "max_auto_recoveries: config.maxAutoRecoveries" in plugin
    assert "state.recoveryCount >= config.maxAutoRecoveries" in plugin


def test_install_template_matches_plugin_runtime_files() -> None:
    for relative in INSTALLABLE_FILES:
        plugin_file = PLUGIN / relative
        template_file = TEMPLATE / relative
        assert plugin_file.is_file(), relative
        assert template_file.is_file(), relative
        assert template_file.read_bytes() == plugin_file.read_bytes(), relative


def test_package_metadata_is_native_plugin_package() -> None:
    package = json.loads(_read("package.json"))
    lock = json.loads(_read("package-lock.json"))

    assert package["type"] == "module"
    assert package["version"] == "0.1.0"
    assert package["peerDependencies"]["@deepseek-ai/cordis"] == "4.0.1"
    assert package["peerDependencies"]["@deepseek-ai/dsh-agent"] == "0.1.1-rc.2"
    assert package["peerDependencies"]["@deepseek-ai/dsh-tools"] == "0.1.1-rc.2"
    assert package["scripts"]["test"] == "node --test tests/*.test.mjs"
    assert lock["lockfileVersion"] == 3
    assert lock["packages"]["node_modules/typescript"]["version"] == "5.9.3"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_node_contract_suite() -> None:
    tests = [str(path) for path in sorted((PLUGIN / "tests").glob("*.test.mjs"))]
    completed = subprocess.run(
        ["node", "--test", *tests],
        cwd=PLUGIN,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
