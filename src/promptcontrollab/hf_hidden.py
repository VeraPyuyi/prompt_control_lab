"""Backward-compatible facade for :mod:`promptcontrollab.diagnostics.hf_hidden`."""

from promptcontrollab.diagnostics.hf_hidden import extract_hidden_states, load_prompt_texts

__all__ = ["extract_hidden_states", "load_prompt_texts"]
