"""Run portable deterministic examples without provider calls or model downloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from promptcontrollab.diagnostics.research_tools import analyze_research  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--historical",
        action="store_true",
        help="Also replay the published completed historical measurement case",
    )
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Use a new output directory to preserve earlier reports")
    fixtures = Path(__file__).resolve().parent
    for kind in ("readout", "response", "measurement-value", "transfer", "replay"):
        source = fixtures / f"{kind}.json"
        analyze_research(kind, json.loads(source.read_text(encoding="utf-8")), args.out / kind)
    if args.historical:
        source = ROOT / "docs/case_studies/measurement_value/source_records.json"
        analyze_research(
            "measurement-value",
            json.loads(source.read_text(encoding="utf-8")),
            args.out / "historical-measurement-value",
        )
    print(json.dumps({"status": "completed", "kinds": 5, "historical": args.historical}))


if __name__ == "__main__":
    main()
