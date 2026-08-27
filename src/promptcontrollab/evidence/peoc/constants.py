"""Canonical PEOC source locations and transactional import limits."""

from __future__ import annotations

import re
from pathlib import Path

HARD_SUMMARY = Path(
    "experiments/redesign_v2/results_server_pull_20260524/"
    "strong_main_grid/summary_acc_hard_test.json"
)
SOFT_SUMMARY = Path(
    "experiments/redesign_v2/results_server_pull_20260524/"
    "strong_main_grid/summary_soft_segmented.json"
)
HETEROGENEITY_SUMMARY = Path("experiments/redesign_v2/stage_heterogeneity/shi_r27_summary.json")
TRAJECTORY_ROOT = Path("experiments/turnpike_trace/results_a800")

MAX_PORTABLE_FILE_BYTES = 10 * 1024 * 1024
MAX_PORTABLE_TOTAL_BYTES = 50 * 1024 * 1024

MANIFEST = Path("README_MANIFEST.md")
CHUNK_SIZE = 1024 * 1024
SEED_PATTERN = re.compile(r"_s(-?\d+)\.json$")
GENERATED_ARTIFACTS = (
    "manifest.json",
    "source_manifest.json",
    "peoc_evidence.json",
    "research_case_study.json",
    "research_case_study.md",
    "research_case_study.html",
)
PORTABLE_EXTENSIONS = {".csv", ".json"}
REQUIRED_SOURCE_ROLES = {"bundle_manifest", "hard_test_summary"}
