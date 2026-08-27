"""Paper concept mappings used by research diagnostic reports."""

from __future__ import annotations

from promptcontrollab.core.files import JsonDict

PAPER_MAPPING: list[JsonDict] = [
    {
        "concept": "tri-split withheld protocol",
        "commands": ["pcl split", "pcl analyze"],
        "artifact": "splits.json",
        "meaning": "Checks train/validation/withheld separation and split reproducibility.",
    },
    {
        "concept": "paired statistical comparison",
        "commands": ["pcl stats"],
        "artifact": "stats.json",
        "meaning": (
            "Reports paired mean delta, bootstrap CI, permutation p-value, and Holm correction."
        ),
    },
    {
        "concept": "soft-to-hard projection gap",
        "commands": ["pcl soft-hard"],
        "artifact": "diagnostics/soft_hard.json",
        "meaning": (
            "Measures whether learned soft vectors are close to deployable token embeddings."
        ),
    },
    {
        "concept": "HuggingFace hidden-state extraction",
        "commands": ["pcl extract-hidden"],
        "artifact": "inputs/hidden_states.npz",
        "meaning": (
            "Prepares trajectory-ready hidden states from an open/local model, or records "
            "the provided hidden-state source."
        ),
    },
    {
        "concept": "hidden-state trajectory",
        "commands": ["pcl trajectory"],
        "artifact": "diagnostics/trajectory.json",
        "meaning": "Reports drift, log-decay slope, fit quality, and turnpike-like signal.",
    },
    {
        "concept": "Riccati surrogate",
        "commands": ["pcl riccati"],
        "artifact": "diagnostics/riccati.json",
        "meaning": "Checks stability on a fitted finite-dimensional surrogate only.",
    },
    {
        "concept": "time-varying soft-control lane",
        "commands": ["pcl tv-soft"],
        "artifact": "diagnostics/tv_soft.json",
        "meaning": "Compares static, time-varying, shuffled, and random soft-control lanes.",
    },
    {
        "concept": "terminal sensitivity decay",
        "commands": ["pcl terminal-sensitivity", "pcl diagnose"],
        "artifact": "diagnostics/terminal_sensitivity.json",
        "meaning": "Measures how terminal-objective changes influence early controls by horizon.",
    },
    {
        "concept": "Green boundary certificate",
        "commands": ["pcl green-certificate", "pcl diagnose"],
        "artifact": "diagnostics/green_certificate.json",
        "meaning": (
            "Checks hyperbolicity and scaled boundary transversality on a named low-dimensional "
            "surrogate."
        ),
    },
    {
        "concept": "posterior local certificate",
        "commands": ["pcl posterior-certificate", "pcl diagnose"],
        "artifact": "diagnostics/posterior_certificate.json",
        "meaning": "Checks local existence conditions from residual and derivative bounds.",
    },
    {
        "concept": "prompt optimization evidence card",
        "commands": ["pcl evidence-card"],
        "artifact": "evidence_card.json",
        "meaning": "Summarizes the recorded research evidence into one reviewer-facing card.",
    },
]

PAPER_REMEDIATION: dict[str, JsonDict] = {
    "soft-to-hard projection gap": {
        "required_inputs": ["inputs/soft_prompt.npz", "inputs/vocab_embeddings.npz"],
        "command": (
            "pcl soft-hard --soft inputs/soft_prompt.npz "
            "--vocab inputs/vocab_embeddings.npz --out diagnostics"
        ),
        "artifact": "diagnostics/soft_hard.json",
        "explains": (
            "Whether the optimized soft vectors remain close enough to deployable hard tokens."
        ),
    },
    "HuggingFace hidden-state extraction": {
        "required_inputs": ["inputs/prompts.jsonl", "HuggingFace model id or local model path"],
        "command": (
            "pcl extract-hidden --model <model-id-or-path> "
            "--prompts inputs/prompts.jsonl --out inputs/hidden_states.npz"
        ),
        "artifact": "inputs/hidden_states.npz",
        "explains": (
            "Creates the hidden-state artifact needed by trajectory and Riccati diagnostics."
        ),
    },
    "hidden-state trajectory": {
        "required_inputs": ["inputs/hidden_states.npz"],
        "command": "pcl trajectory --states inputs/hidden_states.npz --out diagnostics",
        "artifact": "diagnostics/trajectory.json",
        "explains": (
            "Whether internal hidden-state traces show drift, decay, or turnpike-like behavior."
        ),
    },
    "Riccati surrogate": {
        "required_inputs": [
            "inputs/surrogate_mats.npz or inputs/hidden_states.npz",
        ],
        "command": "pcl riccati --trajectory inputs/hidden_states.npz --out diagnostics",
        "artifact": "diagnostics/riccati.json",
        "explains": (
            "Whether a fitted finite-dimensional control surrogate is self-consistent and stable."
        ),
    },
    "time-varying soft-control lane": {
        "required_inputs": [
            "inputs/method_predictions.jsonl with static/tv/shuffled/random methods",
        ],
        "command": (
            "pcl tv-soft --predictions inputs/method_predictions.jsonl "
            "--out diagnostics --baseline-method static"
        ),
        "artifact": "diagnostics/tv_soft.json",
        "explains": (
            "Whether time-varying gains look tied to temporal structure rather than capacity."
        ),
    },
}
