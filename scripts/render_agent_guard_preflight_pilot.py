"""Regenerate the local preflight-only guard pilot CSV."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

CSV_PATH = REPO_ROOT / "docs" / "case_studies" / "agent_guard_pilot.csv"
POLICY_PATH = REPO_ROOT / "examples" / "guard.policy.yaml"

JsonDict = dict[str, Any]


def main() -> int:
    from promptcontrollab.prompt_context import empty_prompt_context
    from promptcontrollab.prompt_guard import guard_prompt
    from promptcontrollab.prompt_improver import estimate_tokens

    rows = list(csv.DictReader(CSV_PATH.read_text(encoding="utf-8").splitlines()))
    output: list[JsonDict] = []
    for row in rows:
        prompt = str(row["raw_prompt_summary"])
        result = guard_prompt(
            prompt,
            context=empty_prompt_context(),
            mode="suggest",
            profile="coding",
            token_mode="balanced",
            max_tokens=None,
            language="en",
            policy_path=POLICY_PATH,
        ).to_json()
        output.append(
            {
                **row,
                "guarded_prompt_summary": _compact(str(result["improved_prompt"])),
                "raw_prompt_tokens": estimate_tokens(prompt),
                "guarded_prompt_tokens": estimate_tokens(str(result["improved_prompt"])),
                "notes": (
                    "preflight-only paired prompt; "
                    f"action={result['action']}; risk={result['risk_level']}; "
                    f"categories={','.join(result['risk_categories'])}; "
                    f"policy_violations={len(result['policy_violations'])}"
                ),
            }
        )
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(f"wrote {CSV_PATH}")
    return 0


def _compact(text: str, limit: int = 180) -> str:
    cleaned = " ".join(text.split())
    return cleaned[:limit]


if __name__ == "__main__":
    raise SystemExit(main())
