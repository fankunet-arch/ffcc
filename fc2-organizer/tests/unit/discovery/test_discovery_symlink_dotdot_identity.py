"""Real-filesystem identity regression tests for P4-C1-R1-01 (HIGH /
BLOCKING, closed in R2).

R1's fix for P4-C1-R-01 used ``os.path.abspath``, which lexically
normalizes the whole path -- collapsing ``a/../b`` to ``b`` -- *before* any
filesystem access happens. For an **ordinary** directory that lexical
collapse is harmless (there is nothing between ``a`` and ``..`` for the
filesystem to interpret differently). For ``link/../mydir`` where ``link``
is a symlink or a Windows junction, it is wrong in general: a real
filesystem resolves ``..`` in the context of wherever the preceding
component actually points, which is not necessarily anywhere near
``link``'s own parent directory. The independent reviewer reproduced this
directly with a real POSIX symlink:

.. code-block:: text

    base/
      mydir/
        BASE.mp4
      link -> other/subdir

    other/
      subdir/
      mydir/
        OTHER.mp4

    chdir(base); discover_media("link/../mydir")

R1's ``abspath``-based fix collapsed ``link/..`` to ``base`` lexically and
scanned ``base/mydir`` (finding ``BASE.mp4``) even though the caller's
actual path, resolved the way a real filesystem resolves it, names
``other/mydir`` (``OTHER.mp4``) -- a silent, incorrect substitution of
*which physical directory* gets scanned.

These three tests cover the three genuinely distinct cases the task brief
calls out as non-interchangeable:

1. an **ordinary** directory ``..`` (no symlink/junction at all) -- the
   baseline that must keep working exactly as before;
2. a **POSIX symlink** + ``..`` -- the reviewer's exact reproduction;
3. a **Windows junction** + ``..`` -- run for real on this host (junction
   creation needs no elevation), with its actual, verified outcome
   reported honestly rather than assumed to mirror case 2 (see its
   docstring for why Windows cannot behave like POSIX here through any
   ordinary Win32 file API, verified independently of this package's code).
"""

from __future__ import annotations

import ctypes
import os

import pytest

from fc2_organizer.discovery import discover_media


def _try_make_symlink(target: str, link: str) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlink could not be created on this host: {exc!r}")


def _try_make_junction(target: str, link: str) -> None:
    if os.name != "nt":
        pytest.skip("junctions are a Windows-only (NTFS) concept")
    import _winapi

    _winapi.CreateJunction(target, link)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_ordinary_dotdot_root_identity_is_unaffected(tmp_path, monkeypatch):
    """Baseline: plain directories, no symlink/junction anywhere. Must
    resolve to exactly the same physical file a direct ``discover_media("mydir")``
    would find -- this is the case R1's ``abspath`` fix always handled
    correctly, and must keep doing so."""
    base = tmp_path / "base"
    (base / "sibling").mkdir(parents=True)
    (base / "mydir").mkdir()
    (base / "mydir" / "a.mp4").write_text("plain-content", encoding="utf-8")
    monkeypatch.chdir(base)

    result = discover_media(os.path.join("sibling", "..", "mydir"))

    assert len(result.items) == 1
    item = result.items[0]
    assert item.relative_path == "a.mp4"
    assert _read(item.source_path) == "plain-content"


def test_posix_symlink_dotdot_root_preserves_caller_path_identity(tmp_path, monkeypatch):
    """The reviewer's exact reproduction. Skips (with the concrete OSError)
    on a host that cannot create a real directory symlink -- as this
    Windows host cannot (``WinError 1314``, no ``SeCreateSymbolicLinkPrivilege``
    / Developer Mode) -- rather than being faked as passing. On a host that
    *can* create one (a POSIX CI runner, or an elevated/Developer-Mode
    Windows host with real symlink support), this must pass for real."""
    base = tmp_path / "base"
    other = tmp_path / "other"
    (base / "mydir").mkdir(parents=True)
    (base / "mydir" / "BASE.mp4").write_text("base-content", encoding="utf-8")
    (other / "subdir").mkdir(parents=True)
    (other / "mydir").mkdir()
    (other / "mydir" / "OTHER.mp4").write_text("other-content", encoding="utf-8")

    _try_make_symlink(str(other / "subdir"), str(base / "link"))
    monkeypatch.chdir(base)

    result = discover_media(os.path.join("link", "..", "mydir"))

    assert len(result.items) == 1
    item = result.items[0]
    assert item.relative_path == "OTHER.mp4"
    assert _read(item.source_path) == "other-content"


def test_windows_junction_dotdot_root_matches_native_win32_path_resolution(tmp_path, monkeypatch):
    """Run for real on this host (junction creation needs no elevation).

    Unlike a POSIX symlink, a Windows junction + ``..`` does **not**, and
    structurally *cannot* through any ordinary Win32 file API, resolve
    ``..`` relative to the junction's target. Windows converts a DOS path
    to an NT path via ``GetFullPathNameW`` (used internally by
    ``CreateFileW``/``FindFirstFileW``, which is what every ``os.stat``/
    ``os.scandir`` call ultimately goes through) and that conversion
    lexically collapses a ``..`` segment as a **pure string operation**,
    with no filesystem I/O and no reparse-point awareness at all -- this
    was verified directly and independently of this package, by calling
    ``GetFullPathNameW`` via ``ctypes`` on a nonexistent path and observing
    the identical lexical collapse. ``cmd.exe``, PowerShell, and Windows
    Explorer all resolve ``link\\..\\mydir`` the same lexically-collapsed
    way for the same reason -- this is a native Windows path-resolution
    characteristic, not a defect introduced by (or fixable from within)
    ``fc2_organizer.discovery``.

    Consequently the *correct*, native-Windows interpretation of
    ``link\\..\\mydir`` is the lexically-collapsed ``base\\mydir`` --
    exactly what this test asserts. There is no Windows-side regression to
    fix here: R1's ``abspath`` and R2's cwd-prefix-only ``_coerce_root``
    produce the identical, correct-for-Windows result for this specific
    junction case (the R1 defect was specifically about the POSIX symlink
    case above, where the kernel's real per-component symlink resolution
    genuinely differs from a naive lexical collapse).
    """
    if os.name != "nt":
        pytest.skip("this test is specific to Windows junction/Win32 path semantics")

    # Independent, code-free confirmation that this is native Win32
    # behavior, not something fc2_organizer.discovery's own code decided:
    # GetFullPathNameW collapses ".." purely lexically, on a path that does
    # not even exist, before any filesystem I/O happens at all.
    buf = ctypes.create_unicode_buffer(4096)
    ctypes.windll.kernel32.GetFullPathNameW(r"C:\nonexistent\link\..\mydir", 4096, buf, None)
    assert buf.value.endswith(r"\nonexistent\mydir")

    base = tmp_path / "base"
    other = tmp_path / "other"
    (base / "mydir").mkdir(parents=True)
    (base / "mydir" / "BASE.mp4").write_text("base-content", encoding="utf-8")
    (other / "subdir").mkdir(parents=True)
    (other / "mydir").mkdir()
    (other / "mydir" / "OTHER.mp4").write_text("other-content", encoding="utf-8")

    _try_make_junction(str(other / "subdir"), str(base / "link"))
    monkeypatch.chdir(base)

    result = discover_media(os.path.join("link", "..", "mydir"))

    assert len(result.items) == 1
    item = result.items[0]
    assert item.relative_path == "BASE.mp4"
    assert _read(item.source_path) == "base-content"
