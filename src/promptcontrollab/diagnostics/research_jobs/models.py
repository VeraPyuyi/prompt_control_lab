"""Versioned public contracts for research input, execution and results."""

from __future__ import annotations

from typing import Any, TypedDict


class ResearchBundle(TypedDict):
    """Describe a versioned data inventory and its supported analysis capabilities."""
    schema_version: str
    id: str
    created_at: float
    title: str
    synthetic: bool
    files: list[dict[str, Any]]
    capabilities: list[dict[str, Any]]
    analyses: list[dict[str, Any]]
    integrity: dict[str, Any]


class ResearchAnalysisSpec(TypedDict):
    """Freeze the bundle identity and selected analysis operations."""
    schema_version: str
    bundle_id: str
    analyses: list[dict[str, Any]]


class ResearchJob(TypedDict):
    """Track durable job status, suite progress, attempts and committed outputs."""
    schema_version: str
    id: str
    status: str
    created_at: float
    updated_at: float
    spec: ResearchAnalysisSpec
    completed: dict[str, Any]
    progress: dict[str, Any]
    attempts: list[dict[str, Any]]
    error: str | None
    queue_owner_pid: int
