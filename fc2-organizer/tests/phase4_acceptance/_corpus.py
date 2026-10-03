"""P4-C10 acceptance corpus: FX-1..FX-6 and the G-500 definition (contract sections 7.1, 7.4), with every expected value
*derived from the definitions* (never read back from the output under test).

Pure data and pure functions: no filesystem access, no import of any package under acceptance, no ``tests/unit/**``.
The derivation helpers (``merge_expected``, ``expected_images``, ``expected_nfo_text``, ``expected_library``,
``mixed_expectations``) re-state the frozen rules of the cited contracts (Phase 3 aggregation merge, P4-C5 acquisition,
P4-C4 NFO, P4-C2 layout, P4-C8 generations) independently of the production code.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

__all__ = [
    "SOURCE_IDS",
    "IMAGE_HOST",
    "PRIVATE_REDIRECT_TARGET",
    "OPERATIONAL_FAILURES",
    "RETRYABLE_SOURCE_STATUSES",
    "Outcome",
    "Film",
    "ok_outcome",
    "fail_outcome",
    "jpeg_bytes",
    "media_bytes",
    "image_url",
    "unsafe_url",
    "image_behavior",
    "image_payload",
    "standard_scripts",
    "merge_expected",
    "expected_images",
    "expected_warnings",
    "expected_nfo_text",
    "expected_library",
    "expected_request_urls",
    "with_outcomes",
    "expectation",
    "FX1_FILMS",
    "FX5_CANARIES",
    "FX5_ALWAYS_FORBIDDEN",
    "fx5_films",
    "MixedPlan",
    "MixedCorpus",
    "mixed_expectations",
    "G500_PLAN",
    "G500_FROZEN",
    "FX2_PLAN",
]

# Phase 3 default priority order (highest first): fc2db_net, javdb, av123 -- also the order of the three scripted sources.
SOURCE_IDS = ("fc2db_net", "javdb", "av123")
IMAGE_HOST = "https://img.c10.example"
PRIVATE_REDIRECT_TARGET = "http://10.1.2.3/hidden.jpg"
OPERATIONAL_FAILURES = frozenset({"BLOCKED", "RATE_LIMITED", "NETWORK_ERROR", "PARSE_ERROR", "INVALID_RESPONSE"})
# the engine repeats a fetch whose result is one of these (default RetryPolicy): such an outcome must be the only one
# of its script, otherwise the "n-th aggregate call" indexing of scripts would be disturbed by source-local retries.
RETRYABLE_SOURCE_STATUSES = frozenset({"NETWORK_ERROR"})


# --------------------------------------------------------------------------- bytes / URLs


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def jpeg_bytes(tag: bytes, width: int = 16, height: int = 16) -> bytes:
    """A structurally valid baseline JPEG, different for every ``tag`` (the tag's digest sits in a COM segment)."""
    digest = hashlib.sha256(tag).digest()
    frame = bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00"
    scan = b"\x01\x01\x00\x00\x3f\x00"
    return (b"\xff\xd8" + _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00") + _segment(0xFE, digest)
            + _segment(0xDB, b"\x00" + bytes(range(1, 65))) + _segment(0xC0, frame) + _segment(0xDA, scan)
            + b"\x12\xff\x00\x34" + b"\xff\xd9")


def media_bytes(key: str, size: int) -> bytes:
    """Deterministic synthetic media content of exactly ``size`` bytes (0 allowed)."""
    block = hashlib.sha256(key.encode("utf-8")).digest()
    repeats = size // len(block) + 1
    return (block * repeats)[:size]


def image_url(key: str, role: str, n: int, behavior: str = "ok") -> str:
    """A candidate image URL whose last ``-<behavior>`` token selects the MockTransport route (``_harness``)."""
    return f"{IMAGE_HOST}/{key}/{role}{n}-{behavior}.jpg"


def unsafe_url(key: str, role: str, n: int) -> str:
    """A candidate that the P4-C5 URL gate rejects before any request (private address literal)."""
    return f"http://10.0.0.5/{key}/{role}{n}-unsafe.jpg"


_KNOWN_BEHAVIORS = ("ok", "404", "redir", "unsafe", "png", "bad")


def image_behavior(url: str) -> str:
    """The route token of a candidate URL (``...-<token>.jpg``); a URL without a known token (the real adapters' image
    URLs of S-20) is served as a valid JPEG (``ok``)."""
    stem = urlsplit(url).path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    token = stem.rsplit("-", 1)[-1]
    return token if token in _KNOWN_BEHAVIORS else "ok"


def image_payload(url: str) -> bytes:
    """The bytes the transport serves for a successful candidate URL (and the bytes the library must then hold)."""
    return jpeg_bytes(url.encode("utf-8"))


# --------------------------------------------------------------------------- film definitions


@dataclass(frozen=True)
class Outcome:
    """One scripted fetch outcome of one source: ``SUCCESS`` with ``fields`` or a failure status name."""

    status: str
    fields: tuple[tuple[str, object], ...] = ()

    def field(self, name: str):
        return dict(self.fields).get(name)


def ok_outcome(**fields) -> Outcome:
    assert "title" in fields, "a SUCCESS needs a non-empty title (Phase 3 minimum success)"
    frozen = tuple((name, tuple(value) if isinstance(value, list) else value) for name, value in fields.items())
    return Outcome("SUCCESS", frozen)


def fail_outcome(status: str) -> Outcome:
    assert status != "SUCCESS"
    return Outcome(status)


@dataclass(frozen=True)
class Film:
    """One synthetic media file plus the scripted behaviour of the three sources for its number.

    ``scripts[source_id]`` is the sequence of outcomes by fetch count (the last one repeats). A missing source answers
    ``NOT_FOUND``. ``number is None`` means the file name carries no FC2 number by construction.
    """

    key: str
    filename: str
    number: str | None
    directory: str = ""
    size: int = 64
    scripts: tuple[tuple[str, tuple[Outcome, ...]], ...] = ()
    group: str = ""

    def __post_init__(self) -> None:
        for source_id, outcomes in self.scripts:
            assert source_id in SOURCE_IDS
            if len(outcomes) > 1:
                assert not any(o.status in RETRYABLE_SOURCE_STATUSES for o in outcomes)

    @property
    def relative_source(self) -> str:
        return f"{self.directory}/{self.filename}" if self.directory else self.filename

    @property
    def extension(self) -> str:
        return "." + self.filename.rsplit(".", 1)[1].lower()

    @property
    def content(self) -> bytes:
        return media_bytes(self.key, self.size)

    def outcomes_at(self, call: int) -> dict[str, Outcome]:
        """What each source answers on its ``call``-th (0-based) fetch of this number."""
        table = dict(self.scripts)
        return {sid: (table[sid][min(call, len(table[sid]) - 1)] if sid in table else fail_outcome("NOT_FOUND"))
                for sid in SOURCE_IDS}


def standard_scripts(key: str, *, poster: tuple[str, ...] = (), fanart: tuple[str, ...] = (),
                     thumb: tuple[str, ...] = (), extra: tuple[str, ...] = (),
                     title: str | None = None, release: str = "2024-05-06", studio: str = "Studio C10",
                     plot: str = "A plot for acceptance.", actors: tuple[str, ...] = ("Actor One", "Actor Two"),
                     ) -> dict[str, tuple[Outcome, ...]]:
    """The field-level layout of S-04, used by every standard film: each source answers with its own title; the
    highest-priority title wins. A supplies poster, the first half of the extrafanart and tags (alpha, beta); B supplies
    release, studio, fanart and the second half of the extrafanart; C supplies plot, thumb, actors and tags
    (beta, delta). No tag or image URL is supplied by more than the sources named here."""
    half = (len(extra) + 1) // 2
    return {
        "fc2db_net": (ok_outcome(title=title if title is not None else f"Title A {key}", tags=("alpha", "beta"),
                                 poster_urls=poster, extrafanart=extra[:half]),),
        "javdb": (ok_outcome(title=f"Title B {key}", release=release, studio=studio, fanart_urls=fanart,
                             extrafanart=extra[half:]),),
        "av123": (ok_outcome(title=f"Title C {key}", plot=plot, actors=actors, thumb_urls=thumb,
                             tags=("beta", "delta")),),
    }


def _film(key, filename, number, *, directory="", size=64, scripts=None, group="") -> Film:
    return Film(key, filename, number, directory, size,
                tuple(sorted((scripts or {}).items(), key=lambda pair: SOURCE_IDS.index(pair[0]))), group)


def with_outcomes(film: Film, scripts: Mapping[str, tuple[Outcome, ...]], **changes) -> Film:
    """A copy of ``film`` whose per-source scripts are updated by ``scripts`` (other fields via ``changes``)."""
    table = dict(film.scripts)
    table.update(scripts)
    values = dict(key=film.key, filename=film.filename, number=film.number, directory=film.directory, size=film.size,
                  group=film.group)
    values.update(changes)
    return Film(values["key"], values["filename"], values["number"], values["directory"], values["size"],
                tuple(sorted(table.items(), key=lambda pair: SOURCE_IDS.index(pair[0]))), values["group"])


def full_images(key: str, extra: int = 2) -> dict[str, tuple[str, ...]]:
    return dict(poster=(image_url(key, "poster", 0),), fanart=(image_url(key, "fanart", 0),),
                thumb=(image_url(key, "thumb", 0),),
                extra=tuple(image_url(key, "extra", i) for i in range(extra)))


def success_film(key: str, filename: str, number: str, *, directory: str = "", size: int = 64, group: str = "",
                 images: dict | None = None, **overrides) -> Film:
    scripts = standard_scripts(key, **(images if images is not None else full_images(key)), **overrides)
    return _film(key, filename, number, directory=directory, size=size, scripts=scripts, group=group)


# --------------------------------------------------------------------------- independent derivations

_SCALARS = ("title", "studio", "release", "plot")
_COLLECTIONS = ("actors", "tags", "poster_urls", "thumb_urls", "fanart_urls", "extrafanart")


def _present(value) -> bool:
    return value is not None and not (isinstance(value, str) and value.strip() == "")


def merge_expected(outcomes: Mapping[str, Outcome]) -> dict | None:
    """Phase 3 field-level aggregation, re-stated from the aggregation contract: only SUCCESS contributes; scalars take
    the first non-empty value in priority order; collections are the ordered-unique union of non-blank items;
    provenance of a scalar = the contributing sources whose value equals the selected one, of a collection = every
    source that supplied at least one non-blank item. Status = ``partial`` iff some source failed operationally
    (``NOT_FOUND`` is not a failure), ``failed`` (returns ``None``) when nobody succeeded."""
    successes = {sid: o for sid, o in outcomes.items() if o.status == "SUCCESS"}
    if not successes:
        return None
    merged: dict = {"status": "partial" if any(o.status in OPERATIONAL_FAILURES for o in outcomes.values())
                    else "success"}
    provenance: dict[str, tuple[str, ...]] = {"number": tuple(sid for sid in SOURCE_IDS if sid in successes)}
    for name in _SCALARS:
        selected = None
        for sid in SOURCE_IDS:
            value = successes[sid].field(name) if sid in successes else None
            if _present(value):
                selected = value
                break
        merged[name] = selected
        if selected is not None:
            provenance[name] = tuple(sid for sid in SOURCE_IDS
                                     if sid in successes and successes[sid].field(name) == selected)
    for name in _COLLECTIONS:
        items: list[str] = []
        contributors = []
        for sid in SOURCE_IDS:
            if sid not in successes:
                continue
            supplied = False
            for item in successes[sid].field(name) or ():
                if not _present(item):
                    continue
                supplied = True
                if item not in items:
                    items.append(item)
            if supplied:
                contributors.append(sid)
        merged[name] = tuple(items)
        if contributors:
            provenance[name] = tuple(contributors)
    merged["provenance"] = provenance
    return merged


# candidate behavior -> (failure kind value, http status) or None for a success
_BEHAVIOR_FAILURE = {
    "ok": None,
    "404": ("http_status", 404),
    "redir": ("unsafe_url", None),
    "unsafe": ("unsafe_url", None),
    "png": ("content_type_mismatch", None),
    "bad": ("invalid_jpeg", None),
}
_MAX_EXTRAFANART = 12  # P4-C5 default policy


def expected_images(merged: dict | None) -> dict:
    """P4-C5 acquisition re-stated: per role in the order poster, fanart, thumb, extrafanart; the first successful
    candidate wins for the single-image roles; every successful extrafanart candidate (up to 12) is kept; every failed
    candidate attempted is one failure ``(ROLE, candidate_index, kind, http_status)``."""
    result = {"poster": None, "fanart": None, "thumb": None, "extrafanart": [], "failures": []}
    if merged is None:
        return result
    for role, field_name in (("POSTER", "poster_urls"), ("FANART", "fanart_urls"), ("THUMB", "thumb_urls")):
        for index, url in enumerate(merged[field_name]):
            failure = _BEHAVIOR_FAILURE[image_behavior(url)]
            if failure is None:
                result[role.lower()] = (index, url)
                break
            result["failures"].append((role, index, failure[0], failure[1]))
    for index, url in enumerate(merged["extrafanart"]):
        failure = _BEHAVIOR_FAILURE[image_behavior(url)]
        if failure is None:
            if len(result["extrafanart"]) < _MAX_EXTRAFANART:
                result["extrafanart"].append((index, url))
        else:
            result["failures"].append(("EXTRAFANART", index, failure[0], failure[1]))
    return result


def expected_warnings(merged: dict, images: dict) -> tuple[str, ...]:
    """P4-C8 section 22.3, in ``ItemWarning`` declaration order (leftover temporaries are execution-time)."""
    found = []
    if merged["status"] == "partial":
        found.append("metadata_partial")
    for role, name in (("poster", "poster_absent"), ("fanart", "fanart_absent"), ("thumb", "thumb_absent")):
        if images[role] is None:
            found.append(name)
    if not images["extrafanart"]:
        found.append("no_extrafanart")
    if images["failures"]:
        found.append("image_candidate_failures")
    return tuple(found)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")


def expected_nfo_text(number: str, merged: dict) -> str:
    """The frozen NFO shape (P4-C4 sections 3-5, 9, 10) for the fields a standard film defines."""
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<movie>",
             f"  <title>{_escape(merged['title'])}</title>",
             f'  <uniqueid type="fc2" default="true">{_escape(number)}</uniqueid>']
    if merged.get("plot") is not None:
        lines.append(f"  <plot>{_escape(merged['plot'])}</plot>")
    if merged.get("release") is not None:
        lines.append(f"  <premiered>{_escape(merged['release'])}</premiered>")
    if merged.get("studio") is not None:
        lines.append(f"  <studio>{_escape(merged['studio'])}</studio>")
    for order, actor in enumerate(merged["actors"]):
        lines += ["  <actor>", f"    <name>{_escape(actor)}</name>", f"    <order>{order}</order>", "  </actor>"]
    for tag in merged["tags"]:
        lines.append(f"  <tag>{_escape(tag)}</tag>")
    lines.append("</movie>")
    return "\n".join(lines) + "\n"


def expected_library(film: Film, merged: dict, images: dict) -> tuple[list[str], list[str]]:
    """(files, directories) the library holds for one successfully organized film, relative and ``/``-separated
    (P4-C2 section 7 default layout; P4-C6 mapping names). The ``extrafanart`` directory always exists: P4-C7 section
    14 step U7 creates it "even when there is no extrafanart image"."""
    base = film.number
    files = [f"{base}/{base}{film.extension}", f"{base}/{base}.nfo"]
    for role in ("poster", "fanart", "thumb"):
        if images[role] is not None:
            files.append(f"{base}/{role}.jpg")
    directories = [base, f"{base}/extrafanart"]
    files += [f"{base}/extrafanart/extrafanart-{n:03d}.jpg" for n in range(1, len(images["extrafanart"]) + 1)]
    return files, directories


def expected_request_urls(merged: dict | None) -> list[str]:
    """Every candidate URL the transport must see (a candidate that the URL gate rejects is never requested; after
    the first success of a single-image role no further candidate of that role is requested)."""
    if merged is None:
        return []
    urls: list[str] = []
    for field_name in ("poster_urls", "fanart_urls", "thumb_urls"):
        for url in merged[field_name]:
            if image_behavior(url) != "unsafe":
                urls.append(url)
            if _BEHAVIOR_FAILURE[image_behavior(url)] is None:
                break
    urls += [url for url in merged["extrafanart"] if image_behavior(url) != "unsafe"]
    return urls


def expectation(film: Film, call: int = 0):
    """``(merged, images)`` for the ``call``-th aggregation of ``film`` (``(None, ...)`` when every source failed)."""
    merged = merge_expected(film.outcomes_at(call))
    return merged, expected_images(merged)


# --------------------------------------------------------------------------- FX-1 small deterministic corpus (12 files)

FX1_FILMS: tuple[Film, ...] = (
    success_film("fx1-01", "FC2-PPV-1000001.mp4", "FC2-1000001", size=1024),
    success_film("fx1-02", "FC2PPV1000002.MP4", "FC2-1000002", size=2048),
    success_film("fx1-03", "fc2-ppv-1000003.mkv", "FC2-1000003", size=0),
    success_film("fx1-04", "FC2-PPV-1000004 日本語タイトル.mp4", "FC2-1000004", size=4096),
    success_film("fx1-05", "FC2-PPV-1000005_\U0001F3AC.mp4", "FC2-1000005", size=33),
    success_film("fx1-06", "FC2-PPV-1000006 café.mp4", "FC2-1000006", size=128),  # NFC
    success_film("fx1-07", "FC2-PPV-1000007 café.mp4", "FC2-1000007", size=129),  # NFD
    success_film("fx1-08", "FC2_PPV_1000008.MKV", "FC2-1000008", size=300),
    success_film("fx1-09", "FC2-PPV-1000009.mp4", "FC2-1000009", size=(1 << 20) + 1),  # streamed cross-volume case
    success_film("fx1-10", "FC2-PPV-1000010.mp4", "FC2-1000010", directory="a", size=17),
    success_film("fx1-11", "FC2-PPV-1000011.mp4", "FC2-1000011", directory="b c", size=18),
    success_film("fx1-12", "FC2-PPV-1000012.mp4", "FC2-1000012", directory="deep/er", size=19),
)
assert len(FX1_FILMS) == 12


# --------------------------------------------------------------------------- FX-5 diagnostics canaries

FX5_CANARIES = {
    "auth": "C10CANARY-AUTH",
    "cookie": "C10CANARY-COOKIE",
    "text": "C10CANARY-TEXT",
    "url": "C10CANARY-URL",
    "exc": "C10CANARY-EXC",
    "dir": "C10CANARYDIR",
    "root": "C10CANARYROOT",
}
# class A canaries: never in any rendered output, under any path policy
FX5_ALWAYS_FORBIDDEN = tuple(FX5_CANARIES.values())
FX5_SECRETLIKE_NAMES = ("Authorization-C10CANARY.mp4", "Cookie-C10CANARY.mp4", "token-C10CANARY.mp4")


def fx5_films() -> tuple[Film, ...]:
    """Class A canaries planted in every source-controlled text channel (the failure ``error_detail`` strings are
    attached by ``_harness.ScriptedSources`` through ``Outcome`` status only; the scripted adapter adds the
    ``Authorization`` / ``Cookie`` text to the failure detail, see ``FAIL_DETAIL``)."""
    films = []
    for n, name in enumerate(FX5_SECRETLIKE_NAMES):
        key = f"fx5-{n}"
        number = f"FC2-{1500001 + n}"
        filename = f"FC2-PPV-{1500001 + n}-{name}"
        scripts = standard_scripts(key, title=f"{FX5_CANARIES['text']} {key}", plot=f"{FX5_CANARIES['text']} plot",
                                   **{**full_images(key), "poster": (
                                       f"{IMAGE_HOST}/{key}/poster0-ok.jpg?token={FX5_CANARIES['url']}",)})
        if n == 0:  # one operational failure carries the Authorization / Cookie canaries in its error detail
            scripts["javdb"] = (fail_outcome("BLOCKED"),)
        films.append(_film(key, filename, number, directory=FX5_CANARIES["dir"], size=40 + n, scripts=scripts,
                           group="fx5"))
    return tuple(films)


# the failure detail every scripted failure carries (class A channel; must never be rendered)
FAIL_DETAIL = (f"Authorization: Bearer {FX5_CANARIES['auth']}; Cookie: session={FX5_CANARIES['cookie']}")


# --------------------------------------------------------------------------- mixed corpora (G-500 and FX-2)


@dataclass(frozen=True)
class MixedPlan:
    """Group sizes of a mixed batch (contract section 7.4 table). ``c_recover`` of the GC films recover on the second
    aggregation; ``g_removed`` of the GG blocking directories are removed by the user before generation 2; the GH films are
    split half NFO publish faults / half poster publish faults."""

    a: int
    b: int
    c: int
    c_recover: int
    d: int
    e: int
    f_pairs: int
    g: int
    g_removed: int
    h: int
    i: int
    j: int
    k: int

    def __post_init__(self) -> None:
        assert self.c_recover <= self.c and self.g_removed <= self.g and self.h % 2 == 0

    @property
    def total(self) -> int:
        return self.a + self.b + self.c + self.d + self.e + 2 * self.f_pairs + self.g + self.h + self.i + self.j + self.k


# G-500 (frozen): 260 + 60 + 30 + 30 + 20 + 20 + 20 + 20 + 20 + 10 + 10 = 500
G500_PLAN = MixedPlan(a=260, b=60, c=30, c_recover=20, d=30, e=20, f_pairs=10, g=20, g_removed=15, h=20, i=20, j=10,
                      k=10)
assert G500_PLAN.total == 500
# FX-2: 24 entries covering every disposition / ExecutionStatus / RetryKind at least once
FX2_PLAN = MixedPlan(a=4, b=3, c=3, c_recover=2, d=2, e=1, f_pairs=1, g=2, g_removed=1, h=2, i=2, j=2, k=1)
assert FX2_PLAN.total == 24

_FAILING_BEHAVIORS = ("404", "redir", "png", "bad")  # GD rotation
_B_STATUSES = ("BLOCKED", "NETWORK_ERROR", "PARSE_ERROR")  # GB: 1/3 each
_C_STATUSES = ("BLOCKED", "NOT_FOUND", "PARSE_ERROR")  # GC: never retried by the engine


class MixedCorpus:
    """The films of a mixed batch, generated from a ``MixedPlan``. Numbers: GA 1_0xx_xxx ... GK 11_0xx_xxx."""

    BASE = {"A": 1_000_000, "B": 2_000_000, "C": 3_000_000, "D": 4_000_000, "F": 6_000_000, "G": 7_000_000,
            "H": 8_000_000, "I": 9_000_000, "J": 10_000_000, "K": 11_000_000}

    def __init__(self, plan: MixedPlan) -> None:
        self.plan = plan
        self.groups: dict[str, list[Film]] = {name: [] for name in "ABCDEFGHIJK"}
        combos = [(p, f, t) for p in (True, False) for f in (True, False) for t in (True, False)]  # 8 combinations
        for k in range(plan.a):  # GA normal: 8 poster / fanart / thumb combinations x extrafanart 0..3
            poster, fanart, thumb = combos[k % 8]
            self.groups["A"].append(self._ok("A", k, poster, fanart, thumb, (k // 8) % 4))
        for k in range(plan.b):  # GB: one operational failure, the failing source rotates, statuses 1/3 each
            status = _B_STATUSES[k % 3]
            source = SOURCE_IDS[(k // 3) % 3]
            film = self._ok("B", k, True, True, True, 2)
            scripts = dict(film.scripts)
            scripts[source] = (fail_outcome(status),)
            self.groups["B"].append(self._with(film, scripts))
        for k in range(plan.c):  # GC: everything fails; the first c_recover recover on the second aggregation
            film = self._ok("C", k, True, True, True, 1)
            status = _C_STATUSES[k % 3]
            scripts = {}
            for source, outcomes in film.scripts:
                scripts[source] = (fail_outcome(status), outcomes[0]) if k < plan.c_recover else (fail_outcome(status),)
            self.groups["C"].append(self._with(film, scripts))
        for k in range(plan.d):  # GD: poster = (failing candidate, good candidate); fanart = a failing candidate only
            behavior = _FAILING_BEHAVIORS[k % 4]
            key = self._key("D", k)
            images = dict(poster=(image_url(key, "poster", 0, behavior), image_url(key, "poster", 1)),
                          fanart=(image_url(key, "fanart", 0, behavior),),
                          thumb=(image_url(key, "thumb", 0),), extra=(image_url(key, "extra", 0, "bad"),
                                                                       image_url(key, "extra", 1)))
            self.groups["D"].append(self._ok("D", k, True, True, True, 0, images=images))
        for k in range(plan.e):  # GE: no FC2 number in the file name
            key = f"ge-{k:04d}"
            self.groups["E"].append(Film(key, f"holiday-clip-{k:03d}.mp4", None, "ge", 16 + k, (), "E"))
        for p in range(plan.f_pairs):  # GF: two different files, one number
            number = f"FC2-{self.BASE['F'] + p}"
            for side, name in (("a", f"FC2-PPV-{self.BASE['F'] + p}.mp4"), ("b", f"FC2PPV{self.BASE['F'] + p}.mkv")):
                key = f"gf-{p:04d}{side}"
                self.groups["F"].append(
                    self._with(self._ok("F", p, True, True, True, 0, key=key, filename=name, directory=f"gf-{side}"),
                               None, number=number))
        for name in "GHIJK":  # normal films with one or two extrafanart; GH always has a poster
            for k in range(getattr(plan, name.lower())):
                self.groups[name].append(self._ok(name, k, True, True, True, 1 if name == "G" else 2))
        assert sum(len(v) for v in self.groups.values()) == plan.total

    # ---- construction helpers

    def _key(self, group: str, k: int) -> str:
        return f"g{group.lower()}-{k:04d}"

    def _ok(self, group, k, poster, fanart, thumb, extra, *, images=None, key=None, filename=None,
            directory=None) -> Film:
        key = key or self._key(group, k)
        number = f"FC2-{self.BASE[group] + k}"
        if images is None:
            full = full_images(key, extra)
            images = dict(poster=full["poster"] if poster else (), fanart=full["fanart"] if fanart else (),
                          thumb=full["thumb"] if thumb else (), extra=full["extra"])
        scripts = standard_scripts(key, **images)
        filename = filename or f"FC2-PPV-{self.BASE[group] + k}.mp4"
        return _film(key, filename, number, directory=directory if directory is not None else f"g{group.lower()}",
                     size=16 + (k % 50), scripts=scripts, group=group)

    @staticmethod
    def _with(film: Film, scripts: dict | None, number: str | None = None) -> Film:
        table = dict(film.scripts) if scripts is None else scripts
        return Film(film.key, film.filename, film.number if number is None else number, film.directory, film.size,
                    tuple(sorted(table.items(), key=lambda pair: SOURCE_IDS.index(pair[0]))), film.group)

    # ---- views

    @property
    def films(self) -> list[Film]:
        """Every film in group order (the physical file order does not matter: discovery sorts)."""
        return [film for name in "ABCDEFGHIJK" for film in self.groups[name]]

    def by_group(self, name: str) -> list[Film]:
        return self.groups[name]

    @property
    def c_recovering(self) -> list[Film]:
        return self.groups["C"][:self.plan.c_recover]

    @property
    def g_removed(self) -> list[Film]:
        return self.groups["G"][:self.plan.g_removed]


def mixed_expectations(plan: MixedPlan) -> dict:
    """The frozen generation table of contract section 7.4 derived from the group sizes (never from outputs)."""
    p = plan
    c_left, g_left = p.c - p.c_recover, p.g - p.g_removed
    ready0 = p.a + p.b + p.d + p.h + p.i + p.j + p.k
    blocked0 = 2 * p.f_pairs + p.g
    unprepared0 = p.c + p.e
    success0 = p.a + p.b + p.d
    exp = {
        "g0_preview": dict(total=p.total, ready=ready0, blocked=blocked0, unprepared=unprepared0),
        "g0_result": dict(success=success0, partial=p.h, failed=p.i, aborted=p.k, not_selected=p.j,
                          not_ready=blocked0 + unprepared0, retryable=p.h + p.i + p.c + p.g, deferred=p.j,
                          non_retryable=p.e + 2 * p.f_pairs + p.k, outcome="partial",
                          kinds=dict(resume=p.h, fresh_reexecute=p.i, metadata_refetch=p.c, preflight_recheck=p.g)),
    }
    exp["g1"] = dict(scope=("resume",), items=p.h, ready=p.h, blocked=0, unprepared=0, success=p.h, outcome="success",
                     merged_success=success0 + p.h)
    g2_items = p.c + p.i + p.g
    g2_ready = p.c_recover + p.i + p.g_removed
    exp["g2"] = dict(scope=("metadata_refetch", "fresh_reexecute", "preflight_recheck"), items=g2_items, ready=g2_ready,
                     blocked=g_left, unprepared=c_left, success=g2_ready,
                     outcome="success" if g2_ready == g2_items else "partial",
                     merged_success=success0 + p.h + g2_ready)
    exp["g3"] = dict(scope=("deferred",), items=p.j, ready=p.j, blocked=0, unprepared=0, success=p.j, outcome="success",
                     merged_success=success0 + p.h + g2_ready + p.j)
    exp["g4"] = dict(scope=None, items=c_left + g_left, ready=0, blocked=g_left, unprepared=c_left, success=0,
                     outcome="failed", merged_success=success0 + p.h + g2_ready + p.j)
    exp["final"] = dict(success=success0 + p.h + g2_ready + p.j, blocked=2 * p.f_pairs + g_left,
                        unprepared=p.e + c_left, aborted=p.k, outcome="partial", retryable=c_left + g_left,
                        sources_in_place=p.e + 2 * p.f_pairs + g_left + c_left + p.k,
                        user_blocked_directories=g_left, empty_target_directories=p.k)
    return exp


# Contract section 7.4 "冻结计数", transcribed literally (checked against ``mixed_expectations`` by the harness tests)
G500_FROZEN = {
    "g0_preview": dict(total=500, ready=410, blocked=40, unprepared=50),
    "g0_result": dict(success=350, partial=20, failed=20, aborted=10, not_selected=10, not_ready=90, retryable=90,
                      deferred=10, kinds=dict(resume=20, fresh_reexecute=20, metadata_refetch=30,
                                              preflight_recheck=20)),
    "g1": dict(items=20, ready=20, success=20, merged_success=370),
    "g2": dict(items=70, ready=55, blocked=5, unprepared=10, success=55, merged_success=425),
    "g3": dict(items=10, ready=10, success=10, merged_success=435),
    "g4": dict(items=15, ready=0, success=0, outcome="failed"),
    "final": dict(success=435, blocked=25, unprepared=30, aborted=10, outcome="partial", retryable=15,
                  sources_in_place=65),
}
