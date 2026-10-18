"""Generate versioned offline fixture evidence and replay the public protocol example."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from promptcontrollab.evaluation.experiments import (
    create_experiment,
    export_experiment,
    run_experiment,
)
from promptcontrollab.evaluation.experiments.protocol import replay_protocol


def main() -> None:
    """Build a local data-only bundle; never issue model requests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    examples = Path(__file__).resolve().parents[1] / "examples/experiments"
    spec = json.loads((examples / "synthetic-import.json").read_text(encoding="utf-8"))
    declaration = json.loads(
        (examples / "public-benchmark-protocol.json").read_text(encoding="utf-8")
    )
    job = run_experiment(args.out, create_experiment(args.out, spec)["id"])
    bundle = export_experiment(args.out, job["id"])
    (args.out / "experiment.zip").write_bytes(bundle.read_bytes())
    (args.out / "protocol.json").write_text(json.dumps(declaration, indent=2), encoding="utf-8")
    result = replay_protocol(declaration, base_dir=args.out, out_dir=args.out / "replay")
    print(
        json.dumps(
            {
                "protocol_status": result["protocol_status"],
                "integrity": result["replay"]["integrity"]["status"],
                "numerical_replay": result["replay"]["numerical_replay"]["status"],
                "model_calls": job["budget"]["calls"],
            },
            indent=2,
        )
    )
    if any(
        result["replay"][key]["status"] != "passed" for key in ("integrity", "numerical_replay")
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
