"""Shared schemas and adapter names for server evidence runs."""

MANIFEST_SCHEMA = "prompt_control_lab.server_evidence_manifest.v1"
MATRIX_SCHEMA = "prompt_control_lab.evidence_matrix.v1"
REPORT_SCHEMA = "prompt_control_lab.interpretability_report.v1"

ADAPTERS = (
    "agent_episode",
    "deployment_gate",
    "generation_aware",
    "riccati_ass_hyp",
    "selective_risk",
    "soft_hard_tv",
    "turnpike_a800",
)

CHUNK_SIZE = 1024 * 1024
