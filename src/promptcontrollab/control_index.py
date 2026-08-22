"""Rebuildable SQLite index for local control-run artifacts."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from promptcontrollab.control_protocol import ControlRun
from promptcontrollab.files import JsonDict, ensure_dir, read_json

_COLUMNS = (
    "run_id",
    "run_dir",
    "created_at",
    "status",
    "authorization",
    "prompt_hash",
    "provider",
    "model",
    "agent",
    "risk_level",
    "stability_state",
    "decision",
    "event_count",
)


class RunIndex:
    """Query cache that can always be recreated from JSON artifacts."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def rebuild(self, runs_root: Path) -> int:
        ensure_dir(self.path.parent)
        records = [
            self._record(path.parent) for path in sorted(runs_root.rglob("control_run.json"))
        ]
        with closing(self._connect()) as connection, connection:
            self._create_schema(connection)
            connection.execute("DELETE FROM runs")
            connection.executemany(
                """
                INSERT INTO runs (
                    run_id, run_dir, created_at, status, authorization, prompt_hash,
                    provider, model, agent, risk_level, stability_state, decision, event_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [tuple(record[column] for column in _COLUMNS) for record in records],
            )
        return len(records)

    def index_run(self, run_dir: Path) -> JsonDict:
        """Refresh one locator row from its JSON artifacts."""

        ensure_dir(self.path.parent)
        record = self._record(run_dir)
        values = tuple(record[column] for column in _COLUMNS)
        with closing(self._connect()) as connection, connection:
            self._create_schema(connection)
            existing = connection.execute(
                "SELECT run_dir FROM runs WHERE run_id = ?", (record["run_id"],)
            ).fetchone()
            if existing is not None and Path(str(existing[0])).resolve() != Path(
                str(record["run_dir"])
            ).resolve():
                msg = (
                    f"Run id `{record['run_id']}` is already registered at "
                    f"{Path(str(existing[0])).resolve()}"
                )
                raise ValueError(msg)
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, run_dir, created_at, status, authorization, prompt_hash,
                    provider, model, agent, risk_level, stability_state, decision, event_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    run_dir=excluded.run_dir,
                    created_at=excluded.created_at,
                    status=excluded.status,
                    authorization=excluded.authorization,
                    prompt_hash=excluded.prompt_hash,
                    provider=excluded.provider,
                    model=excluded.model,
                    agent=excluded.agent,
                    risk_level=excluded.risk_level,
                    stability_state=excluded.stability_state,
                    decision=excluded.decision,
                    event_count=excluded.event_count
                """,
                values,
            )
        return record

    def get(self, run_id: str) -> JsonDict | None:
        if not self.path.exists():
            return None
        with closing(self._connect()) as connection, connection:
            self._create_schema(connection)
            row = connection.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(zip(_COLUMNS, row, strict=True))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                run_dir TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                authorization TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                provider TEXT,
                model TEXT,
                agent TEXT,
                risk_level TEXT,
                stability_state TEXT,
                decision TEXT,
                event_count INTEGER NOT NULL
            )
            """
        )

    @staticmethod
    def _record(run_dir: Path) -> JsonDict:
        run = ControlRun.from_json(read_json(run_dir / "control_run.json"))
        preflight = _read_optional(run_dir / "preflight.json")
        stability = _read_optional(run_dir / "stability.json")
        decision = _read_optional(run_dir / "decision.json")
        return {
            "run_id": run.run_id,
            "run_dir": str(run_dir.resolve()),
            "created_at": run.created_at,
            "status": run.status,
            "authorization": run.authorization,
            "prompt_hash": run.prompt_hash,
            "provider": run.provider,
            "model": run.model,
            "agent": run.agent,
            "risk_level": _optional_value(preflight, "risk_level"),
            "stability_state": _optional_value(stability, "state"),
            "decision": _optional_value(decision, "decision"),
            "event_count": _event_count(run_dir / "events.jsonl"),
        }


def _read_optional(path: Path) -> JsonDict:
    return read_json(path) if path.exists() else {}


def _optional_value(value: JsonDict, key: str) -> Any:
    return value.get(key)


def _event_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip())
