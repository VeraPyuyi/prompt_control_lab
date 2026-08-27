from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS_SRC = ROOT / "plugins" / "deepseek-harness" / "src"

INTEGRATION_DIRECTORIES = (
    ROOT / "plugins",
    ROOT / "plugins" / "claude-code",
    ROOT / "plugins" / "cursor",
    ROOT / "plugins" / "codex",
    ROOT / "plugins" / "deepseek-harness",
    ROOT / "deploy" / "huggingface",
)

KEY_HARNESS_EVENTS = (
    "agent/session-start",
    "agent/pre-step",
    "agent/request",
    "agent/request-error",
    "tools/pre-execute",
    "tools/post-execute",
    "tools/result",
    "session/event",
    "agent/turn-stopping",
    "agent/disposed",
)


def _has_leading_tsdoc(source: str, declaration_start: int) -> bool:
    """Return whether a declaration is immediately preceded by a TSDoc block."""

    prefix = source[:declaration_start].rstrip()
    if not prefix.endswith("*/"):
        return False
    opening = prefix.rfind("/**")
    closing = prefix.rfind("*/")
    return opening >= 0 and opening < closing


def test_user_facing_integrations_have_paired_readmes() -> None:
    """Require English and Chinese documentation for each shipped integration."""

    for directory in INTEGRATION_DIRECTORIES:
        english = directory / "README.md"
        chinese = directory / "README.zh.md"
        assert english.is_file(), f"missing English integration guide: {english}"
        assert chinese.is_file(), f"missing Chinese integration guide: {chinese}"
        assert english.read_text(encoding="utf-8").strip()
        assert chinese.read_text(encoding="utf-8").strip()


def test_exported_harness_functions_and_classes_have_tsdoc() -> None:
    """Require TSDoc on hand-written exported Harness functions and classes."""

    declaration = re.compile(r"^export\s+(?:async\s+)?(?:function|class)\s+", re.MULTILINE)
    missing: list[str] = []
    for path in sorted(HARNESS_SRC.glob("*.ts")):
        source = path.read_text(encoding="utf-8")
        for match in declaration.finditer(source):
            if not _has_leading_tsdoc(source, match.start()):
                line = source.count("\n", 0, match.start()) + 1
                missing.append(f"{path.relative_to(ROOT)}:{line}")
    assert not missing, "missing TSDoc:\n" + "\n".join(missing)


def test_key_harness_event_handlers_have_tsdoc() -> None:
    """Require concise intent comments on the plugin's lifecycle event handlers."""

    path = HARNESS_SRC / "index.ts"
    source = path.read_text(encoding="utf-8")
    missing: list[str] = []
    for event_name in KEY_HARNESS_EVENTS:
        match = re.search(rf"ctx\.on\('{re.escape(event_name)}'", source)
        assert match is not None, f"missing expected Harness event handler: {event_name}"
        if not _has_leading_tsdoc(source, match.start()):
            missing.append(event_name)
    assert not missing, "missing event-handler TSDoc: " + ", ".join(missing)


def test_harness_doc_check_scans_only_hand_written_source() -> None:
    """Keep generated, dependency, template, and test trees outside this contract."""

    scanned = {path.relative_to(ROOT).as_posix() for path in HARNESS_SRC.glob("*.ts")}
    assert scanned
    assert all("/lib/" not in f"/{path}/" for path in scanned)
    assert all("/tests/" not in f"/{path}/" for path in scanned)
    assert all("/node_modules/" not in f"/{path}/" for path in scanned)
    assert all("/template_data/" not in f"/{path}/" for path in scanned)
