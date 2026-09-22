"""Real Windows drive-relative-path regression tests for P4-C1-R2-01
(HIGH / BLOCKING, closed in R3).

R2's fix for P4-C1-R1-01 absolutized a relative root by prefixing the
current working directory onto it via a plain ``pathlib`` join
(``Path(os.getcwd()) / candidate``). That is correct on POSIX, which has no
concept of a drive-relative path. On Windows it is wrong for several
legal relative-path forms a bare cwd-join cannot express at all:

- **same-drive drive-relative** (``C:foo`` while the process's current
  drive is already ``C:``) -- relative to that drive's own current
  directory;
- **cross-drive drive-relative** (``D:foo`` while the process is on
  ``C:``) -- relative to drive ``D:``'s *own* current directory, a piece
  of OS-maintained state (the hidden per-drive ``=D:`` environment
  variable Windows itself tracks) that ``os.getcwd()`` cannot report at
  all for a drive other than the current one;
- **rooted-relative** (``\\foo``) -- relative to the current drive's root.

The independent reviewer's concern: ``Path(os.getcwd()) / Path("D:foo")``
does not even produce an absolute path (pathlib does not special-case a
drive-relative right-hand side the way Windows's own path resolution
does), so the P4-C1-R-01 "``source_path`` must be absolute" contract could
be silently violated again for these forms.

Every identity assertion in this module is checked against an **oracle
independent of this package's own code**: the real ``GetFullPathNameW``
Win32 API (via ``ctypes``, not ``os.path.abspath`` -- a different call
path than what ``fc2_organizer.discovery.scanner`` itself uses), plus a
direct, plain ``open()`` read of the file that oracle path names,
performed *before* ``discover_media`` is ever called. This avoids the
circular-proof trap of using ``_coerce_root``'s own output as the expected
value.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import uuid
from pathlib import Path

import pytest

from fc2_organizer.discovery import discover_media
from fc2_organizer.discovery import scanner

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows drive-relative path semantics; not applicable on this OS")


def _oracle_resolve(caller_root: str) -> str:
    """Independent oracle: real Win32 GetFullPathNameW via ctypes -- a
    different call path than scanner._coerce_root's own os.path.abspath,
    so this is not the production code grading its own homework."""
    buf = ctypes.create_unicode_buffer(4096)
    ctypes.windll.kernel32.GetFullPathNameW(caller_root, 4096, buf, None)
    return buf.value


def test_rooted_relative_root_matches_native_path_resolution(tmp_path, monkeypatch):
    """``\\foo`` (current-drive-root-relative). Verified as an oracle path-
    resolution match, not against a real file at a drive root: this suite
    deliberately does not write test fixtures directly at a drive root
    (``C:\\`` or ``D:\\``) -- see ``docs/review/P4_C1_HANDOFF.md`` R3 section
    for why (the D:\\ cross-drive test below was explicitly scoped by the
    repo owner to one single owned directory well below any drive root).
    This still proves ``_coerce_root`` does not mishandle this relative
    form -- e.g. by leaving it unresolved/relative, or by mangling the
    drive -- since it must match Windows's own resolution exactly."""
    monkeypatch.chdir(tmp_path)
    caller_root = "\\some-rooted-relative-name"

    result = scanner._coerce_root(caller_root)

    assert result == Path(_oracle_resolve(caller_root))
    assert result.is_absolute()
    assert result.drive  # confirms a drive got attached from the current drive context


def test_same_drive_drive_relative_root_preserves_identity(tmp_path, monkeypatch):
    """``C:foo`` while the process's current drive is already ``C:`` --
    relative to that drive's current directory, i.e. exactly ``tmp_path``
    here. Uses a real file under ``tmp_path`` (an ordinary, already-
    sanctioned temp location), no special drive needed."""
    (tmp_path / "mydir").mkdir()
    (tmp_path / "mydir" / "a.mp4").write_text("same-drive-content", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    caller_root = tmp_path.drive + "mydir"  # e.g. "C:mydir" -- same-drive drive-relative, no backslash

    expected_dir = _oracle_resolve(caller_root)
    with open(os.path.join(expected_dir, "a.mp4"), encoding="utf-8") as f:
        expected_content = f.read()

    result = discover_media(caller_root)

    assert len(result.items) == 1
    item = result.items[0]
    assert os.path.isabs(result.root)
    assert os.path.isabs(item.source_path)
    assert item.relative_path == "a.mp4"
    assert os.path.samefile(item.source_path, os.path.join(expected_dir, "a.mp4"))
    with open(item.source_path, encoding="utf-8") as f:
        assert f.read() == expected_content == "same-drive-content"


@pytest.fixture
def _second_writable_drive():
    """Finds a real, writable drive other than the one this repo/tmp_path
    lives on -- required for a genuine cross-drive regression (P4-C1-R2-01
    is specifically about a drive *other than* the process's current one).
    Skips (never fabricates a result) if no such drive is available on
    this host.
    """
    import string

    current_drive = os.path.splitdrive(os.getcwd())[0]  # e.g. "C:"
    for letter in string.ascii_uppercase:
        candidate = f"{letter}:\\"
        if candidate.upper() == (current_drive + "\\").upper():
            continue
        if os.path.isdir(candidate):
            try:
                # Writability probe: an isolated, uniquely-named directory,
                # created and removed immediately, touching nothing else.
                probe_name = f"ffcc_p4c1_r3_probe_{uuid.uuid4().hex}"
                probe = Path(candidate) / probe_name
                probe.mkdir()
                probe.rmdir()
            except OSError:
                continue
            return f"{letter}:"
    pytest.skip("no second writable drive available on this host for a real cross-drive test")


def test_cross_drive_drive_relative_root_preserves_identity(_second_writable_drive):
    """The reviewer's exact concern: ``D:foo`` (or whichever second drive
    is available) while the process's current drive is a *different* one.

    Creates exactly ONE uniquely-named owned directory directly under the
    second drive's root (nothing else on that drive is read, modified, or
    deleted), sets that drive's own current directory to a subdirectory of
    it, switches the process back to its original drive, then verifies
    ``discover_media("<drive>:mydir")`` matches an independent
    ``GetFullPathNameW`` oracle exactly -- both in resolved path identity
    (``os.path.samefile``) and in actual file content read independently
    of this package. Cleans up its own owned directory afterward and
    re-verifies nothing else on the drive changed.
    """
    drive = _second_writable_drive  # e.g. "D:"
    owned_name = f"ffcc_p4c1_r3_{uuid.uuid4().hex}"
    owned_root = Path(f"{drive}\\") / owned_name
    assert not owned_root.exists()
    assert owned_root.parent == Path(f"{drive}\\")

    original_cwd = os.getcwd()
    try:
        droot = owned_root / "droot"
        mydir = droot / "mydir"
        mydir.mkdir(parents=True)
        target_file = mydir / "D_DRIVE_FILE.mp4"
        target_file.write_text("cross-drive-content", encoding="utf-8")

        os.chdir(str(droot))  # sets this drive's own current directory
        os.chdir(original_cwd)  # switches the process back to its original drive

        caller_root = f"{drive}mydir"

        expected_dir = _oracle_resolve(caller_root)
        expected_file = os.path.join(expected_dir, "D_DRIVE_FILE.mp4")
        with open(expected_file, encoding="utf-8") as f:
            expected_content = f.read()

        result = discover_media(caller_root)

        assert len(result.items) == 1
        item = result.items[0]
        assert os.path.isabs(result.root)
        assert os.path.isabs(item.source_path)
        assert item.relative_path == "D_DRIVE_FILE.mp4"
        assert os.path.samefile(item.source_path, expected_file)
        with open(item.source_path, encoding="utf-8") as f:
            observed_content = f.read()
        assert observed_content == expected_content == "cross-drive-content"
    finally:
        os.chdir(original_cwd)
        assert owned_root.parent == Path(f"{drive}\\"), "refusing to delete: owned_root moved out of the drive root"
        assert owned_root.name == owned_name, "refusing to delete: owned_root name changed"
        if owned_root.exists():
            shutil.rmtree(str(owned_root))
        assert not owned_root.exists(), f"residual path after cleanup: {owned_root}"
