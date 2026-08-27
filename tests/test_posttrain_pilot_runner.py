from __future__ import annotations

import contextlib
import importlib
import os
from collections.abc import Iterator
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest

import promptcontrollab.evidence.posttrain_pilot_runner as posttrain_pilot_runner
from promptcontrollab.evidence.posttrain_pilot import PilotInputs
from promptcontrollab.evidence.posttrain_pilot_runner import (
    PosttrainPilotError,
    _posix_exclusive_lock,
    _validate_training_runtime_dependencies,
    execute_sft_pilot,
)


def _inputs(tmp_path: Path) -> PilotInputs:
    paths = {
        name: tmp_path / f"{name}.jsonl" for name in ("train", "validation", "withheld", "format")
    }
    for name, path in paths.items():
        path.write_text(
            f'{{"id":"{name}","prompt":"{name}?","answer":"4","slice":"math"}}\n',
            encoding="utf-8",
        )
    return PilotInputs(
        model_path=tmp_path / "model",
        train_path=paths["train"],
        validation_path=paths["validation"],
        withheld_path=paths["withheld"],
        format_fixture_path=paths["format"],
        out_dir=tmp_path / "pilot",
        runtime_root=tmp_path,
    )


def test_execute_pilot_acquires_output_lock_before_validation_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path)
    validation_called = False

    @contextlib.contextmanager
    def reject_lock(path: Path) -> Iterator[None]:
        assert path == tmp_path / ".pilot.pilot.lock"
        raise PosttrainPilotError("lock conflict")
        yield

    def unexpected_validation(*args: object, **kwargs: object) -> None:
        nonlocal validation_called
        validation_called = True

    monkeypatch.setattr(posttrain_pilot_runner, "_exclusive_lock", reject_lock)
    monkeypatch.setattr(
        posttrain_pilot_runner,
        "validate_model_provenance",
        unexpected_validation,
    )

    with pytest.raises(PosttrainPilotError, match="lock conflict"):
        execute_sft_pilot(
            inputs,
            approval_path=tmp_path / "approval.json",
            gpu=0,
            lock_file=tmp_path / "global.lock",
        )

    assert validation_called is False
    assert not inputs.out_dir.exists()


def test_lock_conflict_does_not_truncate_the_current_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "pilot.lock"
    lock.write_text("existing-owner\n", encoding="utf-8")

    class LockedFcntl:
        LOCK_EX = 1
        LOCK_NB = 2
        LOCK_UN = 4

        @staticmethod
        def flock(fd: int, operation: int) -> None:
            del fd
            if operation != LockedFcntl.LOCK_UN:
                raise BlockingIOError

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: LockedFcntl if name == "fcntl" else None,
    )

    with (
        pytest.raises(PosttrainPilotError, match="owns the lock"),
        _posix_exclusive_lock(lock),
    ):
        pass

    assert lock.read_text(encoding="utf-8") == "existing-owner\n"


def test_secure_lock_rejects_a_symbolic_link(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symbolic links are unavailable")
    target = tmp_path / "owner.txt"
    target.write_text("owner", encoding="utf-8")
    link = tmp_path / "pilot.lock"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symbolic link creation is not permitted")

    with (
        pytest.raises(PosttrainPilotError, match="symbolic link"),
        _posix_exclusive_lock(link),
    ):
        pass

    assert target.read_text(encoding="utf-8") == "owner"


def test_execute_pilot_rejects_paths_outside_the_runtime_before_locking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    inputs = _inputs(runtime)
    inputs = PilotInputs(
        model_path=inputs.model_path,
        train_path=inputs.train_path,
        validation_path=inputs.validation_path,
        withheld_path=inputs.withheld_path,
        format_fixture_path=inputs.format_fixture_path,
        out_dir=tmp_path / "outside" / "pilot",
        runtime_root=runtime,
    )
    lock_called = False

    @contextlib.contextmanager
    def unexpected_lock(path: Path) -> Iterator[None]:
        nonlocal lock_called
        del path
        lock_called = True
        yield

    monkeypatch.setattr(posttrain_pilot_runner, "_exclusive_lock", unexpected_lock)

    with pytest.raises(PosttrainPilotError, match="outside the pilot runtime"):
        execute_sft_pilot(
            inputs,
            approval_path=runtime / "approval.json",
            gpu=0,
            lock_file=runtime / "locks" / "pilot.lock",
        )

    assert lock_called is False
    assert not inputs.out_dir.exists()


def test_training_runtime_rejects_old_accelerate_before_writing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path)

    @contextlib.contextmanager
    def unlocked(path: Path) -> Iterator[None]:
        del path
        yield

    versions = {
        "accelerate": "0.34.2",
        "torch": "2.4.1",
        "peft": "0.17.1",
        "transformers": "4.55.4",
    }

    monkeypatch.setattr(posttrain_pilot_runner, "_exclusive_lock", unlocked)
    monkeypatch.setattr(
        importlib_metadata,
        "version",
        versions.__getitem__,
    )

    with pytest.raises(PosttrainPilotError, match=r"accelerate>=1\.1\.0"):
        execute_sft_pilot(
            inputs,
            approval_path=tmp_path / "approval.json",
            gpu=0,
            lock_file=tmp_path / "global.lock",
        )

    assert not inputs.out_dir.exists()


def test_training_runtime_accepts_supported_accelerate_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions = {
        "accelerate": "1.10.1",
        "torch": "2.4.1",
        "peft": "0.17.1",
        "transformers": "4.55.4",
    }
    monkeypatch.setattr(
        importlib_metadata,
        "version",
        versions.__getitem__,
    )

    runtime = _validate_training_runtime_dependencies()

    assert runtime["accelerate"] == "1.10.1"
