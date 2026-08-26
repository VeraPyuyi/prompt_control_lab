"""Build the allowlisted Hugging Face Space upload directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from promptcontrollab.hf_space import build_space_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    manifest = build_space_bundle(
        project_root=args.project_root,
        output_dir=args.output,
        wheel_path=args.wheel,
        source_commit=args.source_commit,
        force=args.force,
    )
    print(
        f"Built Hugging Face Space bundle for {manifest['package_version']} "
        f"from {manifest['source_commit']} at {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
