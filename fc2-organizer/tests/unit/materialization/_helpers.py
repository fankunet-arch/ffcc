"""Shared helpers for the P4-C6 materialization tests (failure injection, links, snapshots)."""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest

from fc2_organizer.materialization import atomic

TEMP_PREFIX = atomic._TEMP_PREFIX
TEMP_SUFFIX = atomic._TEMP_SUFFIX


def inject(monkeypatch: pytest.MonkeyPatch, **ops) -> None:
    """Replace selected private filesystem ops for this test only."""
    monkeypatch.setattr(atomic, "_FS", dataclasses.replace(atomic._FS, **ops))


def use_hardlink_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the POSIX publish strategy (link + unlink temp) on any OS that supports hard links."""
    monkeypatch.setattr(atomic, "_PUBLISH_LEAVES_TEMP", True)
    inject(monkeypatch, publish=os.link)


STRATEGIES = ["native", "hardlink"]


def apply_strategy(monkeypatch: pytest.MonkeyPatch, strategy: str) -> None:
    if strategy == "hardlink":
        use_hardlink_strategy(monkeypatch)


class TempRecorder:
    """Wraps the ``open`` op to record every temporary path this call created."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.created: list[str] = []
        real_open = atomic._FS.open

        def recording_open(path, flags, mode):
            fd = real_open(path, flags, mode)
            self.created.append(path)
            return fd

        inject(monkeypatch, open=recording_open)


def entries(directory: Path) -> set[str]:
    return set(os.listdir(directory))


def temp_entries(directory: Path) -> set[str]:
    return {n for n in entries(directory) if n.startswith(TEMP_PREFIX)}


def try_symlink(link: Path, target: Path, *, target_is_directory: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")


def try_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("junctions are Windows-only")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


def failing(exc: BaseException):
    def op(*_args, **_kwargs):
        raise exc

    return op
