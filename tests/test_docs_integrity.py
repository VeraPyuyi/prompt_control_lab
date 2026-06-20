import re
from pathlib import Path

LOCAL_LINK_RE = re.compile(r"(?<!\!)\[[^\]\n]+\]\(([^)]+)\)|!\[[^\]\n]*\]\(([^)]+)\)")


def test_readmes_stay_concise() -> None:
    """Keep the repository front page from drifting back into a long manual."""

    assert _line_count(Path("README.md")) <= 90
    assert _line_count(Path("README.zh.md")) <= 75


def test_beginner_guide_is_visible_from_readmes_and_tutorials() -> None:
    """Keep the goal-based beginner path visible at the public entry points."""

    for path in [
        Path("README.md"),
        Path("README.zh.md"),
        Path("docs/tutorial.en.md"),
        Path("docs/tutorial.zh.md"),
    ]:
        assert "pcl start --guide" in path.read_text(encoding="utf-8")


def test_public_markdown_local_links_resolve() -> None:
    """Ensure public README/docs links and image references point to existing files."""

    missing: list[str] = []
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        for lineno, raw_link in _markdown_links(text):
            target = _local_target(raw_link)
            if target is None:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{path}:{lineno}: {raw_link} -> {resolved}")

    assert not missing, "\n".join(missing)


def _public_markdown_files() -> list[Path]:
    return [
        Path("README.md"),
        Path("README.zh.md"),
        *sorted(Path("docs").rglob("*.md")),
    ]


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _markdown_links(text: str) -> list[tuple[int, str]]:
    links: list[tuple[int, str]] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LOCAL_LINK_RE.finditer(line):
            raw = (match.group(1) or match.group(2) or "").strip()
            if raw:
                links.append((lineno, raw))
    return links


def _local_target(raw: str) -> str | None:
    if raw.startswith(("#", "http://", "https://", "mailto:", "file:", "app://")):
        return None
    target = raw.split("#", 1)[0].strip()
    if not target:
        return None
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target
