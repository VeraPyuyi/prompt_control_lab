"""Evidence command parser registration."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.cli.handlers.evidence import (
    _cmd_evidence_audit,
    _cmd_evidence_card,
    _cmd_evidence_from,
    _cmd_evidence_gate,
    _cmd_evidence_import,
    _cmd_evidence_merge,
    _cmd_evidence_scan,
    _cmd_ingest_auto,
    _cmd_ingest_deepeval,
    _cmd_ingest_langfuse,
    _cmd_ingest_langsmith,
    _cmd_ingest_prompt_optimizer,
    _cmd_ingest_promptfoo,
    _cmd_posttrain_gate,
    _cmd_posttrain_model_provenance,
    _cmd_posttrain_pilot,
    _cmd_posttrain_pilot_export,
    _cmd_posttrain_pilot_prepare,
    _cmd_research_import_peoc,
    _cmd_source_verify,
)
from promptcontrollab.evidence.posttrain_pilot_data import (
    GSM8K_DATASET_ID,
    GSM8K_DATASET_REVISION,
    PILOT_SELECTION_SEED,
)


def _register_ingest(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``ingest`` command parser."""
    ingest_parser = subcommands.add_parser(
        "ingest",
        aliases=["import"],
        help="Import external eval-tool results or prompt assets into PromptControlLab artifacts.",
    )
    ingest_subcommands = ingest_parser.add_subparsers(dest="ingest_command", required=True)
    auto_ingest = ingest_subcommands.add_parser(
        "auto",
        help=(
            "Auto-detect Promptfoo/DeepEval/Langfuse/LangSmith scored exports or "
            "prompt-optimizer prompt assets and import them."
        ),
    )
    auto_ingest.add_argument("--input", type=Path, required=True, help="External export file.")
    auto_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    auto_ingest.add_argument("--prompt-id", default=None, help="Promptfoo prompt filter.")
    auto_ingest.add_argument("--name", default=None, help="Langfuse observation name filter.")
    auto_ingest.add_argument("--experiment", default=None, help="LangSmith experiment filter.")
    auto_ingest.add_argument(
        "--score-name",
        default=None,
        help="Langfuse/LangSmith/DeepEval score or metric filter.",
    )
    auto_ingest.add_argument("--model", default=None, help="Model id filter.")
    auto_ingest.add_argument("--provider", default=None, help="Provider filter.")
    auto_ingest.add_argument("--method", default=None, help="Method name written to predictions.")
    auto_ingest.add_argument(
        "--asset-id",
        default=None,
        help="prompt-optimizer asset id/title filter when importing prompt assets.",
    )
    auto_ingest.set_defaults(func=_cmd_ingest_auto)
    promptfoo_ingest = ingest_subcommands.add_parser(
        "promptfoo",
        help="Import `promptfoo eval --output results.json` output.",
    )
    promptfoo_ingest.add_argument("--input", type=Path, required=True, help="Promptfoo JSON file.")
    promptfoo_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    promptfoo_ingest.add_argument(
        "--prompt-id",
        default=None,
        help="Promptfoo prompt id/label to import when the file contains multiple prompts.",
    )
    promptfoo_ingest.add_argument(
        "--provider",
        default=None,
        help="Promptfoo provider id to import when the file contains multiple providers.",
    )
    promptfoo_ingest.add_argument(
        "--method",
        default=None,
        help="Method name written to PCL predictions. Defaults to the prompt id.",
    )
    promptfoo_ingest.set_defaults(func=_cmd_ingest_promptfoo)
    langfuse_ingest = ingest_subcommands.add_parser(
        "langfuse",
        help="Import Langfuse observations/traces JSON export.",
    )
    langfuse_ingest.add_argument("--input", type=Path, required=True, help="Langfuse JSON file.")
    langfuse_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    langfuse_ingest.add_argument(
        "--name",
        default=None,
        help="Langfuse observation/generation name to import when multiple names exist.",
    )
    langfuse_ingest.add_argument(
        "--score-name",
        default=None,
        help="Langfuse score name to import when multiple score names exist.",
    )
    langfuse_ingest.add_argument(
        "--model",
        default=None,
        help="Model id filter to import when the file contains multiple models.",
    )
    langfuse_ingest.add_argument(
        "--provider",
        default=None,
        help="Provider filter to import when the file contains multiple providers.",
    )
    langfuse_ingest.add_argument(
        "--method",
        default=None,
        help="Method name written to PCL predictions. Defaults to the Langfuse name.",
    )
    langfuse_ingest.set_defaults(func=_cmd_ingest_langfuse)
    langsmith_ingest = ingest_subcommands.add_parser(
        "langsmith",
        help="Import LangSmith experiment JSON/CSV export.",
    )
    langsmith_ingest.add_argument(
        "--input",
        type=Path,
        required=True,
        help="LangSmith export file.",
    )
    langsmith_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    langsmith_ingest.add_argument(
        "--experiment",
        default=None,
        help="LangSmith experiment/session name to import when multiple experiments exist.",
    )
    langsmith_ingest.add_argument(
        "--score-name",
        default=None,
        help="LangSmith score column/key to import when multiple scores exist.",
    )
    langsmith_ingest.add_argument(
        "--model",
        default=None,
        help="Model id filter to import when the file contains multiple models.",
    )
    langsmith_ingest.add_argument(
        "--provider",
        default=None,
        help="Provider filter to import when the file contains multiple providers.",
    )
    langsmith_ingest.add_argument(
        "--method",
        default=None,
        help="Method name written to PCL predictions. Defaults to the experiment name.",
    )
    langsmith_ingest.set_defaults(func=_cmd_ingest_langsmith)
    deepeval_ingest = ingest_subcommands.add_parser(
        "deepeval",
        help="Import DeepEval local TestRun JSON output.",
    )
    deepeval_ingest.add_argument("--input", type=Path, required=True, help="DeepEval JSON file.")
    deepeval_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    deepeval_ingest.add_argument(
        "--score-name",
        default=None,
        help="DeepEval metric name to import when multiple metrics exist.",
    )
    deepeval_ingest.add_argument(
        "--model",
        default=None,
        help="Model id filter or override.",
    )
    deepeval_ingest.add_argument(
        "--provider",
        default=None,
        help="Provider filter or override.",
    )
    deepeval_ingest.add_argument(
        "--method",
        default=None,
        help="Method name written to PCL predictions. Defaults to the run name.",
    )
    deepeval_ingest.set_defaults(func=_cmd_ingest_deepeval)
    prompt_optimizer_ingest = ingest_subcommands.add_parser(
        "prompt-optimizer",
        help="Import prompt-optimizer favorites/templates as prompt assets, not scored evidence.",
    )
    prompt_optimizer_ingest.add_argument(
        "--input",
        type=Path,
        required=True,
        help="prompt-optimizer JSON export, such as favorites or template export.",
    )
    prompt_optimizer_ingest.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for prompt_assets.json and gap plan artifacts.",
    )
    prompt_optimizer_ingest.add_argument(
        "--asset-id",
        default=None,
        help="Optional asset id or title to import from a multi-asset export.",
    )
    prompt_optimizer_ingest.set_defaults(func=_cmd_ingest_prompt_optimizer)


def _register_evidence_from(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``evidence-from`` command parser."""
    evidence_from_parser = subcommands.add_parser(
        "evidence-from",
        help=(
            "Import baseline/candidate exports from Promptfoo, Langfuse, LangSmith, or DeepEval "
            "and generate a PCL evidence card."
        ),
    )
    evidence_from_parser.add_argument(
        "--tool",
        choices=["auto", "promptfoo", "langfuse", "langsmith", "deepeval"],
        default="auto",
        help="External export type. Use auto to detect each input file.",
    )
    evidence_from_parser.add_argument(
        "--baseline-input",
        type=Path,
        required=True,
        help="Baseline external export file.",
    )
    evidence_from_parser.add_argument(
        "--candidate-input",
        type=Path,
        required=True,
        help="Candidate external export file.",
    )
    evidence_from_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Evidence bundle output directory.",
    )
    evidence_from_parser.add_argument(
        "--score-name",
        default=None,
        help="Langfuse/LangSmith/DeepEval score or metric name to import.",
    )
    evidence_from_parser.add_argument(
        "--provider",
        default=None,
        help="Provider filter shared by baseline and candidate.",
    )
    evidence_from_parser.add_argument("--baseline-provider", default=None)
    evidence_from_parser.add_argument("--candidate-provider", default=None)
    evidence_from_parser.add_argument(
        "--model",
        default=None,
        help="Model filter shared by baseline and candidate.",
    )
    evidence_from_parser.add_argument("--baseline-model", default=None)
    evidence_from_parser.add_argument("--candidate-model", default=None)
    evidence_from_parser.add_argument(
        "--baseline-prompt-id",
        default=None,
        help="Baseline Promptfoo prompt id, or prompt identity to record.",
    )
    evidence_from_parser.add_argument(
        "--candidate-prompt-id",
        default=None,
        help="Candidate Promptfoo prompt id, or prompt identity to record.",
    )
    evidence_from_parser.add_argument(
        "--baseline-name",
        default=None,
        help="Baseline Langfuse observation/name filter.",
    )
    evidence_from_parser.add_argument(
        "--candidate-name",
        default=None,
        help="Candidate Langfuse observation/name filter.",
    )
    evidence_from_parser.add_argument(
        "--baseline-experiment",
        default=None,
        help="Baseline LangSmith experiment filter.",
    )
    evidence_from_parser.add_argument(
        "--candidate-experiment",
        default=None,
        help="Candidate LangSmith experiment filter.",
    )
    evidence_from_parser.add_argument(
        "--split-hash",
        default=None,
        help="Optional shared split hash to record on both imported runs.",
    )
    evidence_from_parser.add_argument("--baseline-method", default="baseline")
    evidence_from_parser.add_argument("--candidate-method", default="candidate")
    evidence_from_parser.add_argument("--title", default="PromptControlLab External Evidence")
    evidence_from_parser.add_argument("--seed", type=int, default=0)
    evidence_from_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    evidence_from_parser.add_argument("--permutation-samples", type=int, default=1000)
    evidence_from_parser.set_defaults(func=_cmd_evidence_from)


def _register_evidence_audit(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``evidence-audit`` command parser."""
    evidence_audit_parser = subcommands.add_parser(
        "evidence-audit",
        help=(
            "Import external baseline/candidate exports, add PCL evidence, run gap-status, "
            "and verify the research bundle."
        ),
    )
    evidence_audit_parser.add_argument(
        "--tool",
        choices=["auto", "promptfoo", "langfuse", "langsmith", "deepeval"],
        default="auto",
        help="External export type. Use auto to detect each input file.",
    )
    evidence_audit_parser.add_argument(
        "--baseline-input",
        type=Path,
        required=True,
        help="Baseline external export file.",
    )
    evidence_audit_parser.add_argument(
        "--candidate-input",
        type=Path,
        required=True,
        help="Candidate external export file.",
    )
    evidence_audit_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Evidence audit output directory.",
    )
    evidence_audit_parser.add_argument(
        "--score-name",
        default=None,
        help="Langfuse/LangSmith/DeepEval score or metric name to import.",
    )
    evidence_audit_parser.add_argument(
        "--provider",
        default=None,
        help="Provider filter shared by baseline and candidate.",
    )
    evidence_audit_parser.add_argument("--baseline-provider", default=None)
    evidence_audit_parser.add_argument("--candidate-provider", default=None)
    evidence_audit_parser.add_argument(
        "--model",
        default=None,
        help="Model filter shared by baseline and candidate.",
    )
    evidence_audit_parser.add_argument("--baseline-model", default=None)
    evidence_audit_parser.add_argument("--candidate-model", default=None)
    evidence_audit_parser.add_argument(
        "--baseline-prompt-id",
        default=None,
        help="Baseline Promptfoo prompt id, or prompt identity to record.",
    )
    evidence_audit_parser.add_argument(
        "--candidate-prompt-id",
        default=None,
        help="Candidate Promptfoo prompt id, or prompt identity to record.",
    )
    evidence_audit_parser.add_argument(
        "--baseline-name",
        default=None,
        help="Baseline Langfuse observation/name filter.",
    )
    evidence_audit_parser.add_argument(
        "--candidate-name",
        default=None,
        help="Candidate Langfuse observation/name filter.",
    )
    evidence_audit_parser.add_argument(
        "--baseline-experiment",
        default=None,
        help="Baseline LangSmith experiment filter.",
    )
    evidence_audit_parser.add_argument(
        "--candidate-experiment",
        default=None,
        help="Candidate LangSmith experiment filter.",
    )
    evidence_audit_parser.add_argument(
        "--split-hash",
        default=None,
        help="Optional shared split hash to record on both imported runs.",
    )
    evidence_audit_parser.add_argument("--baseline-method", default="baseline")
    evidence_audit_parser.add_argument("--candidate-method", default="candidate")
    evidence_audit_parser.add_argument(
        "--title",
        default="PromptControlLab External Evidence Audit",
    )
    evidence_audit_parser.add_argument("--seed", type=int, default=0)
    evidence_audit_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    evidence_audit_parser.add_argument("--permutation-samples", type=int, default=1000)
    evidence_audit_parser.set_defaults(func=_cmd_evidence_audit)


def _register_source_verify(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``source-verify`` command parser."""
    source_verify_parser = subcommands.add_parser(
        "source-verify",
        help="Verify original external export files against recorded source-input hashes.",
    )
    source_verify_parser.add_argument(
        "--run",
        type=Path,
        required=True,
        help="Run directory containing source_inputs provenance.",
    )
    source_verify_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path. Markdown/HTML siblings are written next to it.",
    )
    source_verify_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when source verification does not pass.",
    )
    source_verify_parser.set_defaults(func=_cmd_source_verify)


def _register_evidence_gate(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``evidence-gate`` command parser."""
    evidence_gate_parser = subcommands.add_parser(
        "evidence-gate",
        help="Run a CI/reviewer gate over source and research-bundle evidence.",
    )
    evidence_gate_parser.add_argument(
        "--run",
        type=Path,
        required=True,
        help="Run directory containing PCL evidence artifacts.",
    )
    evidence_gate_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path. Markdown/HTML siblings are written next to it.",
    )
    evidence_gate_parser.add_argument(
        "--require-source",
        action="store_true",
        help="Fail when source input provenance is absent or not pass.",
    )
    evidence_gate_parser.add_argument(
        "--allow-missing-bundle",
        action="store_true",
        help="Return needs_review instead of fail when research_bundle.json is absent.",
    )
    evidence_gate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when the evidence gate status is not pass.",
    )
    evidence_gate_parser.set_defaults(func=_cmd_evidence_gate)


def _register_evidence(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``evidence`` command parser."""
    evidence_parser = subcommands.add_parser(
        "evidence",
        help="Scan or import dispersed local diagnostic evidence.",
    )
    evidence_subcommands = evidence_parser.add_subparsers(
        dest="evidence_command",
        required=True,
    )
    evidence_scan = evidence_subcommands.add_parser(
        "scan",
        help="Read-only scan of a known evidence layout.",
    )
    evidence_scan.add_argument("--root", type=Path, required=True, help="Evidence root.")
    evidence_scan.add_argument("--profile", default="peoc-server", help="Scanner profile.")
    evidence_scan.add_argument("--out", type=Path, required=True, help="Manifest JSON path.")
    evidence_scan.set_defaults(func=_cmd_evidence_scan)
    evidence_import = evidence_subcommands.add_parser(
        "import",
        help="Verify and normalize a scanned evidence manifest.",
    )
    evidence_import.add_argument("--manifest", type=Path, required=True)
    evidence_import.add_argument("--out", type=Path, required=True, help="Output run directory.")
    evidence_import.add_argument(
        "--portable",
        action="store_true",
        help="Write a path-free bundle of derived reports; raw sources are never copied.",
    )
    evidence_import.add_argument("--overwrite", action="store_true")
    evidence_import.set_defaults(func=_cmd_evidence_import)
    evidence_merge = evidence_subcommands.add_parser(
        "merge",
        help="Reconcile two compatible evidence manifests by canonical identity.",
    )
    evidence_merge.add_argument("--primary", type=Path, required=True)
    evidence_merge.add_argument("--secondary", type=Path, required=True)
    evidence_merge.add_argument("--out", type=Path, required=True)
    evidence_merge.add_argument("--portable", action="store_true")
    evidence_merge.add_argument("--overwrite", action="store_true")
    evidence_merge.set_defaults(func=_cmd_evidence_merge)


def _register_posttrain_gate(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``posttrain-gate`` command parser."""
    posttrain_parser = subcommands.add_parser(
        "posttrain-gate",
        help="Compare baseline and candidate checkpoint evidence.",
    )
    posttrain_parser.add_argument("--baseline", type=Path, required=True)
    posttrain_parser.add_argument("--candidate", type=Path, required=True)
    posttrain_parser.add_argument(
        "--policy",
        type=Path,
        help="Policy path. Uses the packaged bounded default when omitted.",
    )
    posttrain_parser.add_argument(
        "--capability",
        choices=["auto", "full-open-model", "black-box"],
        default="auto",
        help="Evidence capability profile. Auto detects open-model diagnostics.",
    )
    posttrain_parser.add_argument("--out", type=Path, required=True)
    posttrain_parser.set_defaults(func=_cmd_posttrain_gate)


def _register_posttrain_pilot(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``posttrain-pilot`` command parser."""
    pilot_parser = subcommands.add_parser(
        "posttrain-pilot",
        help="Plan or execute the guarded three-stage local LoRA checkpoint pilot.",
    )
    pilot_parser.add_argument("--model", type=Path, required=True, help="Cached local model path.")
    pilot_parser.add_argument(
        "--model-provenance",
        type=Path,
        help="External model snapshot provenance manifest. Defaults beside the model directory.",
    )
    pilot_parser.add_argument("--train", type=Path, required=True)
    pilot_parser.add_argument("--validation", type=Path, required=True)
    pilot_parser.add_argument("--withheld", type=Path, required=True)
    pilot_parser.add_argument("--format-fixture", type=Path, required=True)
    pilot_parser.add_argument("--out", type=Path, required=True)
    pilot_parser.add_argument(
        "--runtime-root",
        type=Path,
        default=Path(os.environ.get("PCL_RUNTIME_ROOT", "/root/prompt_control_lab_runtime")),
        help="Isolated root that must contain every resource used by --execute.",
    )
    pilot_parser.add_argument("--seed", type=int, action="append", dest="seeds")
    pilot_parser.add_argument("--max-steps", type=int, default=60)
    pilot_parser.add_argument("--execute", action="store_true")
    pilot_parser.add_argument("--approval", type=Path)
    pilot_parser.add_argument("--gpu", type=int, default=0)
    pilot_parser.add_argument(
        "--lock-file",
        type=Path,
        help="Global pilot lock. Defaults to <runtime-root>/locks/sft-pilot.lock.",
    )
    pilot_parser.set_defaults(func=_cmd_posttrain_pilot)


def _register_posttrain_pilot_export(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``posttrain-pilot-export`` command parser."""
    pilot_export_parser = subcommands.add_parser(
        "posttrain-pilot-export",
        help="Export a completed pilot as a portable aggregate-only evidence case.",
    )
    pilot_export_parser.add_argument("--run", type=Path, required=True)
    pilot_export_parser.add_argument("--out", type=Path, required=True)
    pilot_export_parser.set_defaults(func=_cmd_posttrain_pilot_export)


def _register_posttrain_model_provenance(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``posttrain-model-provenance`` command parser."""
    model_provenance_parser = subcommands.add_parser(
        "posttrain-model-provenance",
        help="Hash a pinned local model snapshot without modifying the model cache.",
    )
    model_provenance_parser.add_argument("--model", type=Path, required=True)
    model_provenance_parser.add_argument("--model-id", required=True)
    model_provenance_parser.add_argument("--revision", required=True)
    model_provenance_parser.add_argument("--out", type=Path, required=True)
    model_provenance_parser.set_defaults(func=_cmd_posttrain_model_provenance)


def _register_posttrain_pilot_prepare(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``posttrain-pilot-prepare`` command parser."""
    pilot_prepare_parser = subcommands.add_parser(
        "posttrain-pilot-prepare",
        help="Prepare the fixed, provenance-bound GSM8K and format pilot splits.",
    )
    pilot_prepare_parser.add_argument("--out", type=Path, required=True)
    pilot_prepare_parser.add_argument("--dataset-id", default=GSM8K_DATASET_ID)
    pilot_prepare_parser.add_argument("--dataset-revision", default=GSM8K_DATASET_REVISION)
    pilot_prepare_parser.add_argument("--selection-seed", type=int, default=PILOT_SELECTION_SEED)
    pilot_prepare_parser.add_argument("--gsm8k-train-jsonl", type=Path, default=None)
    pilot_prepare_parser.add_argument("--gsm8k-test-jsonl", type=Path, default=None)
    pilot_prepare_parser.set_defaults(func=_cmd_posttrain_pilot_prepare)


def _register_research_import(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``research-import`` command parser."""
    research_import_parser = subcommands.add_parser(
        "research-import",
        help="Import real research evidence through a named adapter.",
    )
    research_import_subcommands = research_import_parser.add_subparsers(
        dest="research_import_adapter",
        metavar="adapter",
        required=True,
    )
    peoc_import_parser = research_import_subcommands.add_parser(
        "peoc",
        help="Import a real PEOC NMI replication bundle.",
    )
    peoc_import_parser.add_argument(
        "--bundle",
        type=Path,
        required=True,
        help="PEOC NMI replication bundle directory.",
    )
    peoc_import_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output run directory.",
    )
    peoc_import_parser.add_argument(
        "--hard-summary",
        type=Path,
        default=None,
        help="Override the hard-test summary path within the bundle.",
    )
    peoc_import_parser.add_argument(
        "--trajectory-file",
        type=Path,
        action="append",
        default=[],
        help="Override a trajectory JSON source; repeat for each source.",
    )
    peoc_import_parser.add_argument(
        "--heterogeneity-summary",
        type=Path,
        default=None,
        help="Override the stage-heterogeneity summary path within the bundle.",
    )
    peoc_import_parser.add_argument(
        "--portable",
        action="store_true",
        help="Copy eligible small JSON/CSV sources; NPZ files remain references.",
    )
    peoc_import_parser.add_argument("--language", choices=["en", "zh"], default="en")
    peoc_import_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace previously generated PEOC import artifacts.",
    )
    peoc_import_parser.set_defaults(func=_cmd_research_import_peoc)


def _register_evidence_card(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``evidence-card`` command parser."""
    evidence_parser = subcommands.add_parser(
        "evidence-card",
        help="Generate a prompt optimization evidence card from run artifacts.",
    )
    evidence_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    evidence_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Markdown output path. A sibling HTML file is also written.",
    )
    evidence_parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="JSON output path. Defaults to RUN/evidence_card.json.",
    )
    evidence_parser.set_defaults(func=_cmd_evidence_card)


_REGISTRARS = {
    "ingest": _register_ingest,
    "evidence-from": _register_evidence_from,
    "evidence-audit": _register_evidence_audit,
    "source-verify": _register_source_verify,
    "evidence-gate": _register_evidence_gate,
    "evidence": _register_evidence,
    "posttrain-gate": _register_posttrain_gate,
    "posttrain-pilot": _register_posttrain_pilot,
    "posttrain-pilot-export": _register_posttrain_pilot_export,
    "posttrain-model-provenance": _register_posttrain_model_provenance,
    "posttrain-pilot-prepare": _register_posttrain_pilot_prepare,
    "research-import": _register_research_import,
    "evidence-card": _register_evidence_card,
}


def register_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    names: Sequence[str] | None = None,
) -> None:
    """Register selected evidence commands in the requested order."""

    selected = tuple(_REGISTRARS) if names is None else tuple(names)
    for name in selected:
        _REGISTRARS[name](subcommands)
