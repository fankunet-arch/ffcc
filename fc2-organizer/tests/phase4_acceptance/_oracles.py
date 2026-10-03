"""P4-C10 shared acceptance gates (independent oracles; contract sections 6, 7.3, 11, 12.4).

Every gate is implemented here, independently of the packages under acceptance and of ``tests/unit/**``: expected
values come from ``_corpus`` definitions and from the frozen rules of the cited contracts, never from the output under
test. A gate that sees a violation raises ``AcceptanceGateViolation`` (an ``AssertionError``), which is what the
mutation tests (contract section 11) expect to catch.

Gates only read the model objects through their public attributes and compare enum *values* (strings), so they share no
classification code with production. They never write anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import xml.dom.minidom
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from . import _corpus

__all__ = [
    "AcceptanceGateViolation",
    "sha256_file",
    "snapshot_tree",
    "gate_snapshots_equal",
    "gate_entries_unchanged",
    "gate_source_not_lost",
    "gate_path_within",
    "gate_write_paths_contained",
    "gate_no_unreported_temporaries",
    "gate_layout_exact",
    "gate_nfo_matches",
    "gate_file_bytes",
    "expected_retry_kind",
    "gate_retry_kinds",
    "gate_result_accounting",
    "gate_indices_exactly_once",
    "gate_diagnostics_canaries",
    "gate_diagnostics_structure",
    "gate_deterministic_equal",
    "gate_peak",
    "gate_no_network",
    "parse_nfo",
    "TEMP_NAME",
    "gate_film_organized",
    "gate_library_exact",
    "repository_digest",
    "gate_repository_unmodified",
    "gate_phase_a_conflicts",
    "gate_resume_converges",
    "gate_merge_composition",
    "gate_default_output_clean",
    "gate_metadata_isolation",
]

TEMP_NAME = re.compile(r"\.fc2tmp-[0-9a-f]{32}\.part\Z")


class AcceptanceGateViolation(AssertionError):
    """A P4-C10 acceptance gate observed a violation of a frozen invariant."""


def _violation(message: str) -> None:
    raise AcceptanceGateViolation(message)


# --------------------------------------------------------------------------- snapshots


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_tree(root: str) -> dict[str, tuple]:
    """relative path (``/``-separated on every platform) -> (kind, size, mtime_ns, sha256 | None, inode); links are never
    followed, nothing is read twice."""
    result: dict[str, tuple] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in sorted(dirnames + filenames):
            path = os.path.join(dirpath, name)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode):
                kind, digest = "link", None
            elif stat.S_ISREG(st.st_mode):
                kind, digest = "file", sha256_file(path)
            elif stat.S_ISDIR(st.st_mode):
                kind, digest = "dir", None
            else:
                kind, digest = "other", None
            result[os.path.relpath(path, root).replace(os.sep, "/")] = (kind, st.st_size if kind == "file" else None, st.st_mtime_ns,
                                                   digest, st.st_ino)
    return result


def gate_snapshots_equal(before: Mapping[str, tuple], after: Mapping[str, tuple], what: str) -> None:
    """Whole-tree equality (SI-21 preview zero mutation, diagnostics read-only)."""
    if before == after:
        return
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
    _violation(f"{what}: the tree changed (added={added[:5]}, removed={removed[:5]}, changed={changed[:5]})")


def gate_entries_unchanged(before: Mapping[str, tuple], after: Mapping[str, tuple], relative_paths: Iterable[str],
                           what: str) -> None:
    """Pre-existing user entries keep their bytes, size, mtime and inode (SI-02, SI-14)."""
    for relative in relative_paths:
        if relative not in before:
            _violation(f"{what}: test bug, {relative!r} was not part of the earlier snapshot")
        if relative not in after:
            _violation(f"{what}: user entry {relative!r} disappeared")
        if before[relative] != after[relative]:
            _violation(f"{what}: user entry {relative!r} was modified")


def gate_source_not_lost(source_path: str, final_path: str | None, original_sha256: str, what: str = "SI-01") -> None:
    """SI-01: the source path or the final path (or both) holds a regular, non-link file with the original bytes."""

    def holds(path: str | None) -> bool:
        if path is None:
            return False
        try:
            st = os.lstat(path)
        except OSError:
            return False
        return stat.S_ISREG(st.st_mode) and sha256_file(path) == original_sha256

    if not (holds(source_path) or holds(final_path)):
        _violation(f"{what}: the source media was lost ({os.path.basename(source_path)})")


# --------------------------------------------------------------------------- containment (SI-15 / SI-19)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def gate_path_within(path: str, root: str, what: str) -> None:
    candidate, base = _norm(path), _norm(root)
    if candidate != base and not candidate.startswith(base + os.sep):
        _violation(f"{what}: {path!r} is outside {root!r}")


def gate_write_paths_contained(records: Sequence[tuple[str, tuple[str, ...]]], *, sandbox_root: str,
                               allowed_directories: Iterable[str], allowed_files: Iterable[str],
                               what: str = "SI-15") -> None:
    """Every mutating path is inside the disposable root, and inside either an allowed target directory (library
    writes) or is exactly an allowed source file (source removal). ``records`` come from the write observer."""
    directories = [_norm(path) for path in allowed_directories]
    files = {_norm(path) for path in allowed_files}
    for operation, paths in records:
        for path in paths:
            gate_path_within(path, sandbox_root, f"{what} ({operation})")
            candidate = _norm(path)
            inside = any(candidate == directory or candidate.startswith(directory + os.sep)
                         for directory in directories)
            if not inside and candidate not in files:
                _violation(f"{what}: {operation} touched {path!r}, which is neither an allowed target directory "
                           f"nor a source file of this batch")


def gate_no_unreported_temporaries(root: str, reported: Iterable[tuple[str, str]], preexisting: Iterable[str] = (),
                                   what: str = "SI-14") -> None:
    """No ``.fc2tmp-<32hex>.part`` remains unless P4-C7 reported it (``(directory, name)`` pairs); user-owned
    look-alikes that were part of the fixture are listed in ``preexisting`` (relative paths)."""
    allowed = {(_norm(directory), name) for directory, name in reported}
    known = {_norm(os.path.join(root, relative)) for relative in preexisting}
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            if TEMP_NAME.match(name) is None:
                continue
            full = _norm(os.path.join(dirpath, name))
            if full in known or (_norm(dirpath), name) in allowed:
                continue
            _violation(f"{what}: an unreported temporary file was left behind: {name}")


# --------------------------------------------------------------------------- layout / content


def gate_layout_exact(library_root: str, expected_files: Iterable[str], expected_directories: Iterable[str],
                      what: str = "layout") -> None:
    """The library holds exactly the expected files and directories (relative, ``/``-separated), nothing else."""
    actual_files, actual_dirs = set(), set()
    for dirpath, dirnames, filenames in os.walk(library_root, followlinks=False):
        for name in dirnames:
            actual_dirs.add(os.path.relpath(os.path.join(dirpath, name), library_root).replace(os.sep, "/"))
        for name in filenames:
            actual_files.add(os.path.relpath(os.path.join(dirpath, name), library_root).replace(os.sep, "/"))
    expected_files, expected_directories = set(expected_files), set(expected_directories)
    if actual_files != expected_files:
        _violation(f"{what}: files differ (unexpected={sorted(actual_files - expected_files)[:5]}, "
                   f"missing={sorted(expected_files - actual_files)[:5]})")
    if actual_dirs != expected_directories:
        _violation(f"{what}: directories differ (unexpected={sorted(actual_dirs - expected_directories)[:5]}, "
                   f"missing={sorted(expected_directories - actual_dirs)[:5]})")


def gate_file_bytes(path: str, expected: bytes, what: str) -> None:
    try:
        with open(path, "rb") as handle:
            actual = handle.read()
    except OSError:
        _violation(f"{what}: {path!r} cannot be read")
    if actual != expected:
        _violation(f"{what}: {os.path.basename(path)} has other bytes than expected "
                   f"({hashlib.sha256(actual).hexdigest()[:12]} != {hashlib.sha256(expected).hexdigest()[:12]})")


def parse_nfo(data: bytes) -> list[tuple[str, dict[str, str], str, list[tuple[str, str]]]]:
    """Parse an NFO with ``xml.dom.minidom`` and return the ordered children of ``<movie>``:
    ``(tag, attributes, text, [(child_tag, child_text), ...])``. Fails the gate on malformed XML, a DOCTYPE, a
    comment, a CDATA section or a wrong root."""
    try:
        document = xml.dom.minidom.parseString(data)
    except Exception as exc:  # noqa: BLE001 - any parser failure is a gate violation
        _violation(f"NFO is not well-formed XML ({type(exc).__name__})")
    if document.doctype is not None:
        _violation("NFO carries a DOCTYPE")
    root = document.documentElement
    if root.tagName != "movie" or root.attributes.length != 0:
        _violation("NFO root must be a bare <movie>")
    children = []
    for node in root.childNodes:
        if node.nodeType == node.TEXT_NODE:
            if node.data.strip():
                _violation("NFO <movie> carries stray text")
            continue
        if node.nodeType != node.ELEMENT_NODE:
            _violation("NFO carries a comment / CDATA / processing instruction")
        attributes = {name: node.attributes[name].value for name in node.attributes.keys()}
        grand = []
        text = ""
        for child in node.childNodes:
            if child.nodeType == child.TEXT_NODE:
                text += child.data
            elif child.nodeType == child.ELEMENT_NODE:
                grand.append((child.tagName, "".join(c.data for c in child.childNodes if c.nodeType == c.TEXT_NODE)))
            else:
                _violation("NFO carries a comment / CDATA / processing instruction")
        children.append((node.tagName, attributes, text, grand))
    return children


def gate_nfo_matches(data: bytes, *, number: str, expected_text: str, title: str, tags: Sequence[str],
                     premiered: str | None, what: str = "NFO") -> None:
    """Exact bytes (independent serializer, ``_corpus.expected_nfo_text``) *and* a structural check by an XML parser:
    element order, title / uniqueid / premiered / tag values, no injected element, attribute or DTD."""
    if data != expected_text.encode("utf-8"):
        _violation(f"{what}: the NFO text differs from the independently serialized expectation")
    children = parse_nfo(data)
    names = [child[0] for child in children]
    if names[:2] != ["title", "uniqueid"] or names.count("title") != 1 or names.count("uniqueid") != 1:
        _violation(f"{what}: element order / mandatory elements violated: {names}")
    if children[0][2] != title or children[0][1]:
        _violation(f"{what}: <title> does not round-trip")
    uniqueid = children[1]
    if uniqueid[2] != number or uniqueid[1] != {"type": "fc2", "default": "true"}:
        _violation(f"{what}: <uniqueid> is wrong")
    allowed = {"title", "uniqueid", "plot", "runtime", "premiered", "studio", "actor", "tag"}
    if not set(names) <= allowed:
        _violation(f"{what}: unexpected NFO element(s): {sorted(set(names) - allowed)}")
    actual_tags = [child[2] for child in children if child[0] == "tag"]
    if actual_tags != list(tags):
        _violation(f"{what}: <tag> values differ: {actual_tags} != {list(tags)}")
    actual_premiered = [child[2] for child in children if child[0] == "premiered"]
    if actual_premiered != ([] if premiered is None else [premiered]):
        _violation(f"{what}: <premiered> differs: {actual_premiered}")


# --------------------------------------------------------------------------- retry / accounting oracles

_RETRYABLE = frozenset({"metadata_refetch", "preflight_recheck", "fresh_reexecute", "resume"})


def expected_retry_kind(item) -> str:
    """The frozen retry-kind table of P4-C8 section 25.1, re-stated from the contract (values as strings)."""
    disposition = item.disposition.value
    if disposition == "executed":
        status = item.execution.status.value
        return {"partial": "resume", "failed": "fresh_reexecute", "success": "none"}[status]
    if disposition == "not_ready":
        if item.issue.stage.value == "metadata":
            return "metadata_refetch"
        if item.issue.reason.value == "preflight_blocked":
            return "preflight_recheck"
        return "none"
    if disposition in ("not_selected", "cancelled"):
        return "deferred"
    return "none"  # rejected / aborted


def gate_retry_kinds(result, what: str = "SI-12") -> None:
    for item in result.items:
        expected = expected_retry_kind(item)
        if item.retry_kind.value != expected:
            _violation(f"{what}: item {item.index} has retry_kind {item.retry_kind.value}, the frozen table says "
                       f"{expected}")


def gate_indices_exactly_once(result, batch_size: int, what: str = "SI-22") -> None:
    indices = [item.index for item in result.items]
    if indices != list(range(batch_size)):
        _violation(f"{what}: result items do not cover indices 0..{batch_size - 1} exactly once "
                   f"(got {len(indices)} items)")


def _expected_counts(result) -> dict[str, int]:
    """Recompute every ExecutionSummary count from the items (P4-C8 sections 11.5 and 28.2)."""
    items = result.items
    counts: Counter = Counter()
    counts["total"] = len(items)
    for item in items:
        disposition = item.disposition.value
        state = item.preview_state.value
        if state == "ready":
            counts["ready"] += 1
        if disposition == "executed":
            counts["executed"] += 1
            counts[item.execution.status.value] += 1
        elif disposition == "not_ready":
            counts[state] += 1
        else:
            counts[disposition] += 1
        kind = expected_retry_kind(item)
        is_success = disposition == "executed" and item.execution.status.value == "success"
        if kind in _RETRYABLE:
            counts["retryable"] += 1
        elif kind == "deferred":
            counts["deferred"] += 1
        elif not is_success:
            counts["non_retryable"] += 1
    return counts


def gate_result_accounting(result, what: str = "SI-22") -> dict[str, int]:
    """Summary identities and the outcome truth table, recomputed independently from ``result.items`` and compared
    with ``result.summary`` / ``result.outcome``. Returns the recomputed counts."""
    counts = _expected_counts(result)
    summary = result.summary
    for name in ("total", "ready", "blocked", "unprepared", "executed", "success", "partial", "failed",
                 "not_selected", "cancelled", "rejected", "aborted", "retryable", "deferred", "non_retryable"):
        if getattr(summary, name) != counts.get(name, 0):
            _violation(f"{what}: summary.{name} = {getattr(summary, name)}, recomputed {counts.get(name, 0)}")
    unexecuted = counts["not_selected"] + counts["cancelled"] + counts["rejected"] + counts["aborted"]
    if counts["executed"] != counts["success"] + counts["partial"] + counts["failed"]:
        _violation(f"{what}: executed != success + partial + failed")
    if counts["ready"] != counts["executed"] + unexecuted:
        _violation(f"{what}: ready != executed + unexecuted")
    if counts["total"] != counts["executed"] + counts["blocked"] + counts["unprepared"] + unexecuted:
        _violation(f"{what}: total != every disposition")
    if counts["total"] != counts["success"] + counts["retryable"] + counts["deferred"] + counts["non_retryable"]:
        _violation(f"{what}: total != success + retryable + deferred + non_retryable")
    success, partial = counts["success"], counts["partial"]
    expected_outcome = "success" if success == counts["total"] else ("partial" if success + partial >= 1 else "failed")
    if result.outcome.value != expected_outcome:
        _violation(f"{what}: outcome {result.outcome.value}, the truth table says {expected_outcome}")
    gate_retry_kinds(result)
    return dict(counts)


# --------------------------------------------------------------------------- diagnostics


def gate_diagnostics_canaries(rendered: bytes, *, forbidden: Iterable[str], what: str = "SI-18") -> None:
    """None of the (class A) canaries may appear in the rendered JSON, as plain text or as a JSON-escaped string."""
    text = rendered.decode("ascii")
    decoded = json.dumps(json.loads(rendered), ensure_ascii=False)
    for canary in forbidden:
        if canary in text or canary in decoded:
            _violation(f"{what}: the canary {canary!r} leaked into the rendered diagnostics")


def gate_diagnostics_structure(rendered: bytes, *, schema: str, schema_version: str, kind: str,
                               items_expected: int | None = None, indices: Sequence[int] | None = None,
                               what: str = "SI-18") -> dict:
    """The JSON parses, is compact / key-sorted ASCII (deterministic form), carries the schema constants and one
    entry per input index in ascending order (``items_expected`` = the indices 0..n-1 of a complete batch; ``indices`` =
    the exact index list of a retry round, which covers only its scope)."""
    try:
        text = rendered.decode("ascii")
    except UnicodeDecodeError:
        _violation(f"{what}: the diagnostics JSON is not ASCII")
    tree = json.loads(text)
    canonical = json.dumps(tree, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if canonical != text:
        _violation(f"{what}: the diagnostics JSON is not compact, key-sorted ASCII")
    if tree.get("schema") != schema or tree.get("schema_version") != schema_version or tree.get("kind") != kind:
        _violation(f"{what}: schema / schema_version / kind differ from the frozen constants")
    found = [entry["index"] for entry in tree["items"]]
    wanted = list(indices) if indices is not None else list(range(items_expected))
    if found != wanted:
        _violation(f"{what}: diagnostics items do not cover the indices {wanted[:3]}..{wanted[-1:]} exactly once, "
                   f"in ascending order")
    return tree


# --------------------------------------------------------------------------- determinism / concurrency / network


def gate_deterministic_equal(first, second, what: str = "SI-07") -> None:
    if first != second:
        _violation(f"{what}: two runs over equal inputs produced different results")


def gate_peak(observed_peak: int, *, limit: int, expect_reached: bool, what: str = "SI-06") -> None:
    """The observed concurrency never exceeded ``limit``; when the scenario holds calls in flight, it reached it."""
    if observed_peak > limit:
        _violation(f"{what}: observed concurrency {observed_peak} exceeds the budget {limit}")
    if expect_reached and observed_peak != limit:
        _violation(f"{what}: the gated scenario never reached the budget (peak {observed_peak}, budget {limit})")


def gate_no_network(trap_hits: Sequence[str], what: str = "SI-20") -> None:
    if trap_hits:
        _violation(f"{what}: network primitives were used: {sorted(set(trap_hits))}")


# --------------------------------------------------------------------------- composite library oracles (S2)


def gate_film_organized(library_root: str, film, merged: dict, images: dict, what: str = "layout") -> None:
    """One organized film: media bytes == the synthetic source bytes, NFO == the independent serialization (and parses),
    every acquired image == the bytes the transport served for its URL, extrafanart names / order."""
    base = film.number
    directory = os.path.join(library_root, base)
    gate_file_bytes(os.path.join(directory, f"{base}{film.extension}"), film.content, f"{what}: media bytes of {base}")
    with open(os.path.join(directory, f"{base}.nfo"), "rb") as handle:
        nfo = handle.read()
    gate_nfo_matches(nfo, number=base, expected_text=_corpus.expected_nfo_text(base, merged), title=merged["title"],
                     tags=merged["tags"], premiered=merged["release"], what=f"{what}: NFO of {base}")
    for role in ("poster", "fanart", "thumb"):
        if images[role] is not None:
            gate_file_bytes(os.path.join(directory, f"{role}.jpg"), _corpus.image_payload(images[role][1]),
                            f"{what}: {role} of {base}")
    for ordinal, (_index, url) in enumerate(images["extrafanart"], start=1):
        gate_file_bytes(os.path.join(directory, "extrafanart", f"extrafanart-{ordinal:03d}.jpg"),
                        _corpus.image_payload(url), f"{what}: extrafanart {ordinal} of {base}")


def gate_library_exact(library_root: str, organized: Iterable[tuple], *, user_files: Mapping[str, bytes] | None = None,
                       empty_directories: Iterable[str] = (), user_directories: Iterable[str] = (),
                       what: str = "layout") -> None:
    """The whole library: exactly the organized films (``(film, merged, images)``), the user's files (relative path ->
    bytes, must be unchanged) and directories, and the empty target directories of ABORTED entries -- nothing else."""
    organized = list(organized)
    files, directories = [], []
    for film, merged, images in organized:
        film_files, film_dirs = _corpus.expected_library(film, merged, images)
        files += film_files
        directories += film_dirs
    user_files = dict(user_files or {})
    files += list(user_files)
    directories += list(empty_directories) + list(user_directories)
    for relative in list(user_files):  # parents of the user's files are directories too
        parent = relative.rsplit("/", 1)[0] if "/" in relative else None
        while parent:
            directories.append(parent)
            parent = parent.rsplit("/", 1)[0] if "/" in parent else None
    gate_layout_exact(library_root, files, sorted(set(directories)), what)
    for film, merged, images in organized:
        gate_film_organized(library_root, film, merged, images, what)
    for relative, data in user_files.items():
        gate_file_bytes(os.path.join(library_root, *relative.split("/")), data, f"{what}: user file {relative}")


# --------------------------------------------------------------------------- repository read-only evidence (SI-19, 3.4.1)

_REPOSITORY = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DIGEST_ROOTS = ("src", os.path.join("tests", "support"), os.path.join("tests", "fixtures"), "pyproject.toml")


def repository_digest() -> dict[str, str]:
    """sha256 of every file the acceptance may only read (``src``, ``tests/support``, ``tests/fixtures``,
    ``pyproject.toml``); byte-code caches are ignored."""
    digest: dict[str, str] = {}
    for entry in _DIGEST_ROOTS:
        base = os.path.join(_REPOSITORY, entry)
        if os.path.isfile(base):
            digest[entry] = sha256_file(base)
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [name for name in dirnames if name != "__pycache__"]
            for name in filenames:
                path = os.path.join(dirpath, name)
                digest[os.path.relpath(path, _REPOSITORY).replace(os.sep, "/")] = sha256_file(path)
    return digest


def gate_repository_unmodified(before: Mapping[str, str], after: Mapping[str, str], what: str = "SI-19") -> None:
    if before != after:
        changed = sorted(set(before) ^ set(after)) or sorted(k for k in before if before[k] != after.get(k))
        _violation(f"{what}: repository files the acceptance may only read changed: {changed[:5]}")


# --------------------------------------------------------------------------- cross-package gates added for the mutation matrix


def gate_phase_a_conflicts(preview, numbers_called: Mapping[str, int], groups: Iterable[Iterable[int]],
                           what: str = "SI-10") -> None:
    """P4-C8 section 14.2: the members of every Phase A conflict group are all BLOCKED with a ``duplicate_*_in_batch``
    reason, carry no metadata and no preflight, know exactly their peers, and the engine was never asked for their
    numbers (no winner is selected, nothing is fetched for a conflicted entry)."""
    for group in groups:
        members = sorted(group)
        for index in members:
            item = preview.items[index]
            if (item.state.value != "blocked" or item.issue is None
                    or item.issue.reason.value not in ("duplicate_source_in_batch", "duplicate_target_in_batch")):
                _violation(f"{what}: Phase A member {index} is not blocked by a batch conflict")
            if item.metadata is not None or item.preflight is not None:
                _violation(f"{what}: Phase A member {index} was processed past the conflict check")
            if sorted(item.conflict_with) != [peer for peer in members if peer != index]:
                _violation(f"{what}: conflict_with of member {index} is not its exact peer set")
            if item.canonical_number is not None and numbers_called.get(item.canonical_number, 0):
                _violation(f"{what}: the engine was asked for the conflicted number {item.canonical_number}")


def gate_resume_converges(previous, retry_preview, what: str = "SI-13") -> None:
    """P4-C7 section 14 / P4-C8 section 25: a RESUME retry item is READY, its preflight is a RESUME preflight and carries
    the very checkpoint the previous result holds -- a checkpoint of another entry (or none) does not converge."""
    for item in retry_preview.items:
        if item.retry_origin is None or item.retry_origin.value != "resume":
            continue
        issued = previous.items[item.index].execution.checkpoint
        if (item.state.value != "ready" or item.preflight is None or item.preflight.mode.value != "resume"
                or item.preflight.checkpoint is not issued):
            _violation(f"{what}: the RESUME retry of item {item.index} does not converge on its own checkpoint")


def gate_merge_composition(previous, retry, merged, what: str = "SI-22") -> None:
    """P4-C8 section 26: every index of the merged result holds the retry round's item (when it was retried) or the
    previous result's item (the very objects), exactly once, in index order."""
    replacements = {item.index: item for item in retry.items}
    if [item.index for item in merged.items] != [item.index for item in previous.items]:
        _violation(f"{what}: the merged result does not cover the previous indices in order")
    for old, new in zip(previous.items, merged.items):
        expected = replacements.get(old.index, old)
        if new is not expected:
            _violation(f"{what}: merged item {old.index} is not the {'retry' if old.index in replacements else 'previous'} item")


def gate_default_output_clean(rendered: bytes, what: str = "SI-18") -> None:
    """The default (``PathPolicy.NONE``) diagnostics contain no canary text at all (file names included)."""
    if b"C10CANARY" in rendered:
        _violation(f"{what}: the default diagnostics output contains canary text")


def gate_metadata_isolation(items, films_by_number: Mapping[str, object], call: int = 0, what: str = "SI-04") -> None:
    """Source isolation (SI-04): the metadata status of every fetched item is the one the independent merge definition
    gives for its scripted source outcomes -- one failing source never turns a film FAILED."""
    for item in items:
        if item.metadata is None or item.canonical_number is None:
            continue
        film = films_by_number.get(item.canonical_number)
        if film is None:
            continue
        merged = _corpus.merge_expected(film.outcomes_at(call))
        expected = "failed" if merged is None else merged["status"]
        if item.metadata.status.value != expected:
            _violation(f"{what}: {item.canonical_number} has metadata status {item.metadata.status.value}, "
                       f"the source outcomes give {expected}")
