"""Unit tests for the reparse-point detection seam
(``fc2_organizer.discovery._platform.is_reparse_point``), independent of
whether a real junction/symlink can be created on this host (contract
section 21 platform-abstraction requirement)."""

from __future__ import annotations

import stat as stat_module
from types import SimpleNamespace

from fc2_organizer.discovery import _platform


def test_non_windows_platform_always_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(_platform.os, "name", "posix")
    assert _platform.is_reparse_point(str(tmp_path)) is False


def test_windows_reparse_bit_set_returns_true(monkeypatch):
    monkeypatch.setattr(_platform.os, "name", "nt")
    fake_stat = SimpleNamespace(st_file_attributes=stat_module.FILE_ATTRIBUTE_REPARSE_POINT | stat_module.FILE_ATTRIBUTE_DIRECTORY)
    monkeypatch.setattr(_platform.os, "lstat", lambda path: fake_stat)
    assert _platform.is_reparse_point("C:\\fake\\path") is True


def test_windows_reparse_bit_clear_returns_false(monkeypatch):
    monkeypatch.setattr(_platform.os, "name", "nt")
    fake_stat = SimpleNamespace(st_file_attributes=stat_module.FILE_ATTRIBUTE_DIRECTORY)
    monkeypatch.setattr(_platform.os, "lstat", lambda path: fake_stat)
    assert _platform.is_reparse_point("C:\\fake\\path") is False


def test_missing_st_file_attributes_returns_false(monkeypatch):
    monkeypatch.setattr(_platform.os, "name", "nt")
    fake_stat = SimpleNamespace()  # no st_file_attributes at all (e.g. non-Windows stat_result shape)
    monkeypatch.setattr(_platform.os, "lstat", lambda path: fake_stat)
    assert _platform.is_reparse_point("C:\\fake\\path") is False


def test_lstat_failure_returns_false_not_raise(monkeypatch):
    monkeypatch.setattr(_platform.os, "name", "nt")

    def raising_lstat(path):
        raise FileNotFoundError("vanished")

    monkeypatch.setattr(_platform.os, "lstat", raising_lstat)
    assert _platform.is_reparse_point("C:\\fake\\path") is False
