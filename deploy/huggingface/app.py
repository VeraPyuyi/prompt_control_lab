"""Hugging Face Space entry point for the restricted public demo."""

from __future__ import annotations

import os

os.environ.setdefault("PCL_DEPLOYMENT_MODE", "hf_demo")
os.environ.setdefault("PCL_UI_LANGUAGE", "zh")
os.environ.setdefault("PCL_UI_RUNS", "/tmp/prompt_control_lab")
os.environ.setdefault("PCL_UI_DEFAULT_VIEW", "before")
os.environ.setdefault("PCL_HF_DEMO_SOURCE", "/app/demo_runs")

from promptcontrollab.ui.app import main

main()
