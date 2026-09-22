"""P4-C5 substep 5: synthetic image acquisition gate (contract section 15).

400 synthetic ``PublicationRecord``s (SUCCESS and PARTIAL) are acquired through a scripted
in-memory ``ImageHttpClient``. Every expectation -- request order, roles, candidate indices,
failure kinds, HTTP statuses, artifact bytes, dimensions, SHA-256, total bytes and extrafanart
order -- comes from the synthetic *case definition*, never from the production result.

The gate runs under filesystem traps (0 hits required) and never touches a real network:
the fake client is pure memory; the one redirect reproduction uses ``httpx.MockTransport``.
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import dataclasses
import gc
import hashlib
import io
import os
import os.path
import pathlib
import shutil
from collections import Counter
from collections.abc import Callable, Iterator

import httpx
import pytest

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.images import (
    AcquiredImage,
    ImageAcquisitionPolicy,
    ImageAcquisitionResult,
    ImageCandidateFailure,
    ImageConnectionError,
    ImageInputError,
    ImageRedirectError,
    ImageRedirectLimitError,
    ImageResponseTooLargeError,
    ImageRole,
    ImageTimeoutError,
    UrlRejectionReason,
)
from fc2_organizer.images import ImageFailureKind as K
from fc2_organizer.images.acquisition import acquire_images
from fc2_organizer.images.transport import HttpxImageClient, ImageHttpResponse
from fc2_organizer.planning import build_organize_plan
from fc2_organizer.publication import PublicationRecord

P, F, T, E = ImageRole.POSTER, ImageRole.FANART, ImageRole.THUMB, ImageRole.EXTRAFANART
GATE_SIZE = 400
SECRET_TOKEN = "SUPERSECRET"
SECRET_RESPONSE_BODY = "SECRET_RESPONSE_BODY"
SECRET_EXCEPTION_TEXT = "SECRET_EXCEPTION_TEXT"
SECRETS = (SECRET_TOKEN, SECRET_RESPONSE_BODY, SECRET_EXCEPTION_TEXT)


# --- fixtures ---------------------------------------------------------------------------------------------


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def jpeg(width: int, height: int, *, seed: int = 0, pad: int = 0) -> bytes:
    """Structurally valid baseline JPEG, built segment by segment; ``seed`` / ``pad`` vary the bytes."""
    frame = bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00"
    comment = _segment(0xFE, seed.to_bytes(4, "big") + bytes([seed % 251]) * pad) if pad or seed else b""
    return (b"\xff\xd8" + _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00") + comment
            + _segment(0xDB, b"\x00" + bytes(range(1, 65))) + _segment(0xC0, frame)
            + _segment(0xDA, b"\x01\x01\x00\x00\x3f\x00") + bytes([seed % 256, 0x5A, 0xFF, 0x00]) + b"\xff\xd9")


def ok(content: bytes, content_type: str | None = "image/jpeg") -> ImageHttpResponse:
    return ImageHttpResponse(status_code=200, content_type=content_type, content=content)


def status(code: int) -> ImageHttpResponse:
    return ImageHttpResponse(status_code=code, content_type="text/html; charset=utf-8", content=b"")


MALFORMED = b"\xff\xd8" + SECRET_RESPONSE_BODY.encode() + b"\xff\xd9"
HTML_BODY = ("<html>" + SECRET_RESPONSE_BODY + "</html>").encode()


class ScriptedClient:
    """Pure in-memory ImageHttpClient. Outcomes: an ImageHttpResponse, or a zero-arg callable that
    returns one / raises. Records every request and the max number in flight."""

    def __init__(self, script: dict[str, object]) -> None:
        self.script = script
        self.calls: list[str] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def get(self, url: str, *, deadline_seconds: float, max_redirects: int, max_bytes: int):
        self.calls.append(url)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0)
            outcome = self.script[url]
            return outcome() if callable(outcome) else outcome
        finally:
            self.in_flight -= 1

    async def aclose(self) -> None:
        return None


def raises(factory: Callable[[], BaseException]) -> Callable[[], ImageHttpResponse]:
    def outcome() -> ImageHttpResponse:
        raise factory()

    return outcome


# --- case definition ------------------------------------------------------------------------------------------


@dataclasses.dataclass
class Expected:
    role: ImageRole
    index: int
    content: bytes
    width: int
    height: int


@dataclasses.dataclass
class Case:
    number: int
    scenario: str
    status: AggregateStatus
    urls: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    script: dict[str, object] = dataclasses.field(default_factory=dict)
    policy: ImageAcquisitionPolicy = dataclasses.field(default_factory=ImageAcquisitionPolicy)
    calls: list[str] = dataclasses.field(default_factory=list)
    singles: dict[ImageRole, Expected] = dataclasses.field(default_factory=dict)
    extras: list[Expected] = dataclasses.field(default_factory=list)
    failures: list[tuple[ImageRole, int, K, int | None]] = dataclasses.field(default_factory=list)
    tags: set[str] = dataclasses.field(default_factory=set)

    def url(self, role: ImageRole, k: int, *, secret: bool = False) -> str:
        query = f"?token={SECRET_TOKEN}" if secret else f"?v={k}"
        return f"https://cdn{self.number}.example.test/{role.value}/{k}.jpg{query}"

    def add(self, role: ImageRole, url: str) -> int:
        field = {P: "poster_urls", F: "fanart_urls", T: "thumb_urls", E: "extrafanart"}[role]
        self.urls[field] = self.urls.get(field, ()) + (url,)
        return len(self.urls[field]) - 1

    def success(self, role: ImageRole, url: str, content: bytes, width: int, height: int,
                content_type: str | None = "image/jpeg") -> None:
        index = self.add(role, url)
        self.script[url] = ok(content, content_type)
        self.calls.append(url)
        expected = Expected(role, index, content, width, height)
        if role is E:
            self.extras.append(expected)
        else:
            self.singles[role] = expected

    def failure(self, role: ImageRole, url: str, outcome: object | None, kind: K, http: int | None = None,
                *, requested: bool = True) -> None:
        index = self.add(role, url)
        if requested:
            self.script[url] = outcome
            self.calls.append(url)
        self.failures.append((role, index, kind, http))
        self.tags.add(kind.name)

    def unrequested(self, role: ImageRole, url: str) -> None:
        self.add(role, url)


# Every per-candidate failure variant: (tag, outcome factory(case, k), kind, http status, requested?)
def _fail_variants(case: Case, role: ImageRole, k: int):
    n = case.number
    return [
        ("404", case.url(role, k), status(404), K.HTTP_STATUS, 404, True),
        ("403", case.url(role, k), status(403), K.HTTP_STATUS, 403, True),
        ("429", case.url(role, k), status(429), K.HTTP_STATUS, 429, True),
        ("500", case.url(role, k), status(500), K.HTTP_STATUS, 500, True),
        ("timeout", case.url(role, k), raises(ImageTimeoutError), K.TIMEOUT, None, True),
        ("connection", case.url(role, k), raises(ImageConnectionError), K.CONNECTION_ERROR, None, True),
        ("redirect-limit", case.url(role, k), raises(ImageRedirectLimitError), K.REDIRECT_LIMIT, None, True),
        ("unsafe-redirect", case.url(role, k),
         raises(lambda: ImageRedirectError(UrlRejectionReason.NON_GLOBAL_IP)), K.UNSAFE_URL, None, True),
        ("too-large", case.url(role, k), raises(ImageResponseTooLargeError), K.TOO_LARGE, None, True),
        ("png-mime", case.url(role, k), ok(jpeg(10, 10, seed=n), "image/png"), K.CONTENT_TYPE_MISMATCH, None, True),
        ("html-mime", case.url(role, k), ok(HTML_BODY, "text/html"), K.CONTENT_TYPE_MISMATCH, None, True),
        ("malformed", case.url(role, k), ok(MALFORMED, "application/octet-stream"), K.INVALID_JPEG, None, True),
        ("bad-dims", case.url(role, k), ok(jpeg(20_001, 5, seed=n)), K.INVALID_DIMENSIONS, None, True),
        ("zero-dims", case.url(role, k), ok(jpeg(8, 0, seed=n)), K.INVALID_DIMENSIONS, None, True),
        ("buggy-client", case.url(role, k), raises(lambda: RuntimeError(SECRET_EXCEPTION_TEXT)),
         K.TRANSPORT_ERROR, None, True),
        ("unsafe-url", f"http://10.0.{n % 250}.{k + 1}/p.jpg?token={SECRET_TOKEN}", None, K.UNSAFE_URL, None, False),
        ("localhost", f"http://img{n}.localhost/p.jpg", None, K.UNSAFE_URL, None, False),
        ("invalid-url", f"relative/{n}/{k}.jpg", None, K.INVALID_URL, None, False),
        ("secret-timeout", case.url(role, k, secret=True), raises(ImageTimeoutError), K.TIMEOUT, None, True),
    ]


def _fail(case: Case, role: ImageRole, k: int, variant: int) -> str:
    variants = _fail_variants(case, role, k)
    tag, url, outcome, kind, http, requested = variants[variant % len(variants)]
    case.failure(role, url, outcome, kind, http, requested=requested)
    case.tags.add(tag)
    return tag


def _dims(n: int, salt: int) -> tuple[int, int]:
    return 100 + (n * 7 + salt * 13) % 1900, 60 + (n * 11 + salt * 5) % 1100


def _img(case: Case, role: ImageRole, k: int, salt: int, *, pad: int = 0, content_type: str | None = "image/jpeg"):
    w, h = _dims(case.number, salt)
    case.success(role, case.url(role, k), jpeg(w, h, seed=case.number * 16 + salt, pad=pad), w, h, content_type)


# --- scenarios -----------------------------------------------------------------------------------------------


def sc_empty(case: Case) -> None:
    case.tags.add("empty")


def sc_poster_first(case: Case) -> None:
    _img(case, P, 0, 1)
    case.unrequested(P, case.url(P, 1))  # never requested after the first success
    case.tags.add("poster-first")


def sc_poster_fallback(case: Case) -> None:
    fails = 1 + case.number % 3
    for k in range(fails):
        _fail(case, P, k, case.number + k * 5)
    _img(case, P, fails, 2, content_type=[None, "image/jpeg", "Image/JPEG; charset=binary",
                                          "application/octet-stream", "image/pjpeg"][case.number % 5])
    case.tags.add("poster-fallback")


def sc_poster_all_fail(case: Case) -> None:
    for k in range(2):
        _fail(case, P, k, case.number + k)
    case.tags.add("poster-all-fail")


def sc_fanart_thumb(case: Case) -> None:
    _fail(case, F, 0, case.number)
    _img(case, F, 1, 3)
    _img(case, T, 0, 4)
    case.tags.add("fanart-thumb")


def sc_extrafanart(case: Case) -> None:
    count = case.number % 7  # 0..6 candidates
    for k in range(count):
        if (case.number + k) % 3 == 1:
            _fail(case, E, k, case.number + k)
        else:
            _img(case, E, k, 10 + k)
    case.tags.add(f"extrafanart-{count}")


def sc_role_isolation(case: Case) -> None:
    _fail(case, P, 0, 0)  # 404
    _img(case, P, 1, 1)
    _fail(case, F, 0, 4)  # timeout
    _img(case, T, 0, 2)
    _img(case, E, 0, 3)
    _fail(case, E, 1, 11)  # malformed
    _img(case, E, 2, 5)
    case.tags.add("role-isolation")


def sc_candidate_limit(case: Case) -> None:
    limit = 3
    case.policy = ImageAcquisitionPolicy(max_candidates_per_role=limit)
    for k in range(limit + 1 + case.number % 3):
        case.unrequested(P, case.url(P, k))
    case.failures.append((P, limit, K.CANDIDATE_LIMIT, None))
    _img(case, F, 0, 1)
    for k in range(limit):  # exactly at the limit: processed normally
        _img(case, E, k, 20 + k)
    case.tags.update({"candidate-limit", "CANDIDATE_LIMIT"})


def sc_extrafanart_limit(case: Case) -> None:
    cap = 2 + case.number % 2
    case.policy = ImageAcquisitionPolicy(max_extrafanart=cap)
    successes = 0
    for k in range(7):
        if successes >= cap:
            case.unrequested(E, case.url(E, k))  # neither requested nor recorded
        elif k == 1:
            _fail(case, E, k, 0)
        else:
            _img(case, E, k, 30 + k)
            successes += 1
    case.tags.add("extrafanart-limit")


def sc_total_cap(case: Case) -> None:
    w1, h1 = _dims(case.number, 40)
    w2, h2 = _dims(case.number, 41)
    a = jpeg(w1, h1, seed=case.number * 16 + 40, pad=300 + case.number)
    b = jpeg(w2, h2, seed=case.number * 16 + 41, pad=500)
    exact = case.number % 2 == 0
    cap = len(a) + len(b) if exact else len(a) + len(b) - 1
    case.policy = ImageAcquisitionPolicy(max_image_bytes=cap, max_total_bytes=cap)
    case.success(P, case.url(P, 0), a, w1, h1)
    if exact:
        case.success(F, case.url(F, 0), b, w2, h2)
        case.tags.add("total-cap-exact")
    else:
        index = case.add(F, case.url(F, 0))
        case.script[case.url(F, 0)] = ok(b)
        case.calls.append(case.url(F, 0))
        case.failures.append((F, index, K.TOTAL_BYTES_LIMIT, None))
        case.unrequested(F, case.url(F, 1))  # nothing after TOTAL_BYTES_LIMIT
        case.unrequested(T, case.url(T, 0))
        case.unrequested(E, case.url(E, 0))
        case.tags.update({"total-cap-exceeded", "TOTAL_BYTES_LIMIT"})


def sc_duplicates(case: Case) -> None:
    w, h = _dims(case.number, 50)
    same = jpeg(w, h, seed=case.number * 16 + 50)
    for role in (P, F, T, E, E):
        url = case.url(role, len(case.urls.get({P: "poster_urls", F: "fanart_urls", T: "thumb_urls",
                                                    E: "extrafanart"}[role], ())))
        case.success(role, url, same, w, h)
    case.tags.add("duplicates")


def sc_secrets(case: Case) -> None:
    case.failure(P, case.url(P, 0, secret=True), status(403), K.HTTP_STATUS, 403)
    case.failure(P, f"https://example.com/x.jpg?token={SECRET_TOKEN}&n={case.number}", ok(HTML_BODY, "text/html"),
                 K.CONTENT_TYPE_MISMATCH)
    case.failure(P, f"https://example.com/y.jpg?token={SECRET_TOKEN}&n={case.number}",
                 raises(lambda: RuntimeError(SECRET_EXCEPTION_TEXT)), K.TRANSPORT_ERROR)
    case.failure(F, f"https://example.com/z.jpg?token={SECRET_TOKEN}&n={case.number}",
                 ok(MALFORMED, None), K.INVALID_JPEG)
    _img(case, T, 0, 60)
    case.tags.add("secrets")


def sc_full_mix(case: Case) -> None:
    _fail(case, P, 0, case.number)
    _img(case, P, 1, 70)
    _img(case, F, 0, 71)
    _fail(case, T, 0, case.number + 3)
    _fail(case, T, 1, case.number + 6)
    for k in range(3):
        _img(case, E, k, 72 + k)
    case.tags.add("full-mix")


SCENARIOS = [sc_empty, sc_poster_first, sc_poster_fallback, sc_poster_all_fail, sc_fanart_thumb, sc_extrafanart,
             sc_role_isolation, sc_candidate_limit, sc_extrafanart_limit, sc_total_cap, sc_duplicates, sc_secrets,
             sc_full_mix]


def build_case(n: int) -> Case:
    scenario = SCENARIOS[n % len(SCENARIOS)]
    case = Case(n, scenario.__name__, AggregateStatus.SUCCESS if n % 2 == 0 else AggregateStatus.PARTIAL)
    scenario(case)
    return case


def make_record(case: Case) -> PublicationRecord:
    number = f"FC2-{1_000_000 + case.number}"
    item = DiscoveredMediaItem(index=case.number, source_path=rf"C:\downloads\m{case.number}.mp4",
                               relative_path=f"m{case.number}.mp4", extension=".mp4", size=case.number + 1)
    metadata = NormalizedMetadata(number=number, title=f"Film {case.number}", **case.urls)
    plan = build_organize_plan(item, number, NormalizedMetadata(number=number, title="plan"), r"C:\library")
    return PublicationRecord(plan=plan, metadata=metadata, aggregate_status=case.status)


# --- filesystem trap -------------------------------------------------------------------------------------------


class FilesystemTouched(AssertionError):
    pass


_FS_TARGETS: list[tuple[object, str]] = [
    (builtins, "open"), (io, "open"), (os, "open"), (os, "stat"), (os, "lstat"), (os, "listdir"), (os, "scandir"),
    (os, "mkdir"), (os, "makedirs"), (os, "remove"), (os, "unlink"), (os, "rename"), (os, "replace"), (os, "rmdir"),
    (os, "getcwd"), (os, "walk"), (os.path, "exists"), (os.path, "isfile"), (os.path, "isdir"),
    (os.path, "getsize"), (os.path, "realpath"), (pathlib.Path, "open"), (pathlib.Path, "exists"),
    (pathlib.Path, "stat"), (pathlib.Path, "mkdir"), (pathlib.Path, "resolve"), (pathlib.Path, "read_bytes"),
    (pathlib.Path, "read_text"), (pathlib.Path, "write_bytes"), (pathlib.Path, "write_text"),
    (pathlib.Path, "touch"), (pathlib.Path, "unlink"), (pathlib.Path, "rename"), (pathlib.Path, "iterdir"),
    (pathlib.Path, "cwd"), (shutil, "copy"), (shutil, "copy2"), (shutil, "copyfile"), (shutil, "copytree"),
    (shutil, "move"), (shutil, "rmtree"),
]


@contextlib.contextmanager
def filesystem_trap() -> Iterator[list[str]]:
    hits: list[str] = []

    def make(name: str):
        def trapped(*args, **kwargs):
            hits.append(name)
            raise FilesystemTouched(name)

        return trapped

    with pytest.MonkeyPatch.context() as mp:
        for owner, attr in _FS_TARGETS:
            name = f"{getattr(owner, '__name__', owner)}.{attr}"
            replacement = make(name)
            if owner is pathlib.Path and attr == "cwd":
                replacement = classmethod(lambda cls, _n=name: make(_n)())
            mp.setattr(owner, attr, replacement)
        yield hits


def test_filesystem_trap_positive_control():
    with filesystem_trap() as hits:
        for probe in (lambda: open("x"), lambda: os.stat("."), lambda: pathlib.Path("x").exists(),
                      lambda: shutil.copy("a", "b"), lambda: os.getcwd(), lambda: io.open("x")):
            with pytest.raises(FilesystemTouched):
                probe()
    assert len(hits) == 6


# --- running --------------------------------------------------------------------------------------------------


def run_case(runner: asyncio.Runner, case: Case) -> tuple[ImageAcquisitionResult, ScriptedClient]:
    client = ScriptedClient(case.script)
    result = runner.run(acquire_images(make_record(case), client, policy=case.policy))
    return result, client


@pytest.fixture(scope="module")
def gate():
    cases = [build_case(n) for n in range(GATE_SIZE)]
    outcomes = []
    with asyncio.Runner() as runner:
        runner.get_loop()  # event loop created before the trap (it may touch the OS)
        with filesystem_trap() as hits:
            for case in cases:
                outcomes.append((case, *run_case(runner, case)))
    return outcomes, hits


def test_gate_size_and_coverage(gate):
    outcomes, _ = gate
    assert len(outcomes) == GATE_SIZE
    cases = [case for case, _, _ in outcomes]
    assert Counter(c.status for c in cases) == {AggregateStatus.SUCCESS: 200, AggregateStatus.PARTIAL: 200}
    tags = set().union(*(c.tags for c in cases))
    required = {
        "empty", "poster-first", "poster-fallback", "poster-all-fail", "fanart-thumb", "role-isolation",
        "404", "403", "429", "500", "timeout", "connection", "redirect-limit", "unsafe-redirect", "unsafe-url",
        "localhost", "invalid-url", "too-large", "png-mime", "html-mime", "malformed", "bad-dims", "zero-dims",
        "buggy-client", "candidate-limit", "extrafanart-limit", "total-cap-exact", "total-cap-exceeded",
        "duplicates", "secrets", "secret-timeout", "full-mix",
        *(f"extrafanart-{k}" for k in range(7)),
        *(kind.name for kind in K),  # every failure kind is produced somewhere in the gate
    }
    assert required <= tags, sorted(required - tags)


def test_gate_matches_case_definitions_exactly(gate):
    outcomes, _ = gate
    for case, result, client in outcomes:
        where = f"case {case.number} ({case.scenario})"
        assert client.calls == case.calls, where
        assert client.max_in_flight <= 1, where
        assert [(f.role, f.candidate_index, f.kind, f.http_status) for f in result.failures] == case.failures, where
        for role, slot in ((P, result.poster), (F, result.fanart), (T, result.thumb)):
            _assert_image(slot, case.singles.get(role), where)
        assert len(result.extrafanart) == len(case.extras), where
        for got, want in zip(result.extrafanart, case.extras):
            _assert_image(got, want, where)
        expected_total = sum(len(e.content) for e in [*case.singles.values(), *case.extras])
        assert result.total_bytes == expected_total, where
        assert expected_total <= case.policy.max_total_bytes, where


def _assert_image(got: AcquiredImage | None, want: Expected | None, where: str) -> None:
    if want is None:
        assert got is None, where
        return
    assert type(got) is AcquiredImage, where
    assert got.role is want.role and got.candidate_index == want.index, where
    assert got.content == want.content and type(got.content) is bytes, where
    assert (got.width, got.height) == (want.width, want.height), where
    assert got.size_bytes == len(want.content), where
    assert got.sha256 == hashlib.sha256(want.content).hexdigest(), where


def test_gate_touched_no_filesystem(gate):
    _, hits = gate
    assert hits == []


def test_gate_is_deterministic(gate):
    outcomes, _ = gate
    with asyncio.Runner() as runner:
        for case, first, first_client in outcomes:
            second, second_client = run_case(runner, case)
            assert second == first and second_client.calls == first_client.calls, case.number


def _walk(obj, seen):
    if id(obj) in seen:
        return
    seen.add(id(obj))
    yield obj
    if isinstance(obj, (type, str, bytes, int, float, bool)) or obj is None:
        return
    for child in gc.get_referents(obj):
        if not isinstance(child, type):
            yield from _walk(child, seen)


def test_gate_results_hold_no_sensitive_or_live_objects(gate):
    outcomes, _ = gate
    for case, result, _ in outcomes:
        for text in (repr(result), str(result), repr(result.failures)):
            for secret in SECRETS:
                assert secret not in text, (case.number, secret)
            assert "://" not in text and "example" not in text, case.number
        for node in _walk(result, set()):
            assert not isinstance(node, (BaseException, ImageHttpResponse, httpx.Response, httpx.Request,
                                         httpx.Headers, httpx.Cookies, dict, list)), (case.number, type(node))
            assert type(node).__name__ != "traceback", case.number
            if type(node) is str:
                assert "://" not in node and not any(s in node for s in SECRETS), (case.number, node)
            if type(node) is bytes:
                assert not any(s.encode() in node for s in SECRETS), case.number
        for failure in result.failures:
            assert type(failure) is ImageCandidateFailure
            assert {f.name for f in dataclasses.fields(failure)} == {"role", "candidate_index", "kind",
                                                                     "http_status"}


# --- cancellation regression --------------------------------------------------------------------------------------


def test_cancellation_mid_acquisition_propagates_without_failure_or_next_request():
    case = Case(9_999, "cancel", AggregateStatus.SUCCESS)
    _img(case, P, 0, 1)
    fanart_0, fanart_1 = case.url(F, 0), case.url(F, 1)
    case.add(F, fanart_0)
    case.add(F, fanart_1)
    case.script[fanart_0] = raises(asyncio.CancelledError)
    case.script[fanart_1] = ok(jpeg(5, 5))
    client = ScriptedClient(case.script)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(acquire_images(make_record(case), client))
    assert client.calls == [case.url(P, 0), fanart_0]  # the next candidate was never requested


@pytest.mark.parametrize("fatal", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_fatal_base_exceptions_still_propagate(fatal):
    case = Case(9_998, "fatal", AggregateStatus.PARTIAL)
    url = case.url(P, 0)
    case.add(P, url)
    case.add(P, case.url(P, 1))
    client = ScriptedClient({url: raises(fatal), case.url(P, 1): ok(jpeg(5, 5))})
    with pytest.raises(fatal):
        asyncio.run(acquire_images(make_record(case), client))
    assert client.calls == [url]


# --- direct reproductions A-H ---------------------------------------------------------------------------------------


def _single(urls: dict[str, tuple[str, ...]], script: dict[str, object], policy=None):
    case = Case(5_000, "repro", AggregateStatus.SUCCESS, urls=urls)
    client = ScriptedClient(script)
    return asyncio.run(acquire_images(make_record(case), client, policy=policy)), client


def test_repro_a_poster_404_then_second_candidate_wins():
    good = jpeg(300, 450, seed=1)
    result, client = _single({"poster_urls": ("https://a.example.test/1.jpg", "https://a.example.test/2.jpg")},
                             {"https://a.example.test/1.jpg": status(404), "https://a.example.test/2.jpg": ok(good)})
    assert result.poster.candidate_index == 1 and result.poster.content == good
    assert [(f.kind, f.http_status) for f in result.failures] == [(K.HTTP_STATUS, 404)]
    assert client.calls == ["https://a.example.test/1.jpg", "https://a.example.test/2.jpg"]


def test_repro_b_public_redirect_to_private_ip_never_requested():
    requested: list[str] = []
    good = jpeg(20, 30, seed=2)

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "public.example.test":
            return httpx.Response(302, headers={"Location": "http://10.1.2.3/internal.jpg"})
        return httpx.Response(200, headers={"Content-Type": "image/jpeg"}, content=good)

    async def scenario():
        case = Case(5_001, "redirect", AggregateStatus.SUCCESS,
                    urls={"poster_urls": ("https://public.example.test/p.jpg", "https://cdn.example.test/ok.jpg")})
        async with HttpxImageClient(transport=httpx.MockTransport(handler)) as client:
            return await acquire_images(make_record(case), client)

    result = asyncio.run(scenario())
    assert requested == ["https://public.example.test/p.jpg", "https://cdn.example.test/ok.jpg"]
    assert not any("10.1.2.3" in url for url in requested)
    assert [(f.candidate_index, f.kind) for f in result.failures] == [(0, K.UNSAFE_URL)]
    assert result.poster.content == good and result.poster.candidate_index == 1


def test_repro_c_valid_jpeg_declared_png_is_content_type_mismatch():
    result, _ = _single({"thumb_urls": ("https://c.example.test/t.jpg",)},
                        {"https://c.example.test/t.jpg": ok(jpeg(10, 10), "image/png")})
    assert result.thumb is None and [f.kind for f in result.failures] == [K.CONTENT_TYPE_MISMATCH]


def test_repro_d_malformed_jpeg_is_invalid_jpeg():
    result, _ = _single({"fanart_urls": ("https://d.example.test/f.jpg",)},
                        {"https://d.example.test/f.jpg": ok(MALFORMED)})
    assert result.fanart is None and [f.kind for f in result.failures] == [K.INVALID_JPEG]


def test_repro_e_total_cap_exceeded_stops_all_later_requests():
    a, b = jpeg(10, 10, seed=3, pad=100), jpeg(10, 10, seed=4, pad=100)
    policy = ImageAcquisitionPolicy(max_image_bytes=len(a) + len(b) - 1, max_total_bytes=len(a) + len(b) - 1)
    urls = {"poster_urls": ("https://e.example.test/p.jpg",), "fanart_urls": ("https://e.example.test/f.jpg",),
            "thumb_urls": ("https://e.example.test/t.jpg",), "extrafanart": ("https://e.example.test/x.jpg",)}
    script = {"https://e.example.test/p.jpg": ok(a), "https://e.example.test/f.jpg": ok(b),
              "https://e.example.test/t.jpg": ok(a), "https://e.example.test/x.jpg": ok(a)}
    result, client = _single(urls, script, policy)
    assert client.calls == ["https://e.example.test/p.jpg", "https://e.example.test/f.jpg"]
    assert result.poster.content == a and result.fanart is None and result.thumb is None and result.extrafanart == ()
    assert [(f.role, f.kind) for f in result.failures] == [(F, K.TOTAL_BYTES_LIMIT)]


def test_repro_f_fanart_failure_keeps_poster_and_thumb():
    p, t = jpeg(1, 2, seed=5), jpeg(3, 4, seed=6)
    result, _ = _single(
        {"poster_urls": ("https://f.example.test/p.jpg",), "fanart_urls": ("https://f.example.test/f.jpg",),
         "thumb_urls": ("https://f.example.test/t.jpg",)},
        {"https://f.example.test/p.jpg": ok(p), "https://f.example.test/f.jpg": raises(ImageTimeoutError),
         "https://f.example.test/t.jpg": ok(t)})
    assert result.poster.content == p and result.fanart is None and result.thumb.content == t


def test_repro_g_secret_token_never_in_result_or_errors():
    url = f"https://example.com/x.jpg?token={SECRET_TOKEN}"
    result, _ = _single({"poster_urls": (url,)}, {url: raises(lambda: RuntimeError(SECRET_EXCEPTION_TEXT))})
    assert [f.kind for f in result.failures] == [K.TRANSPORT_ERROR]
    for text in (repr(result), str(result), repr(result.failures)):
        assert SECRET_TOKEN not in text and SECRET_EXCEPTION_TEXT not in text
    # forged candidate shape -> typed input error, still no secret
    case = Case(5_002, "forged", AggregateStatus.SUCCESS, urls={"poster_urls": (url,)})
    record = make_record(case)
    object.__setattr__(record.metadata, "poster_urls", [url])
    with pytest.raises(ImageInputError) as info:
        asyncio.run(acquire_images(record, ScriptedClient({})))
    assert SECRET_TOKEN not in str(info.value) and SECRET_TOKEN not in repr(info.value)


def test_repro_h_cancelled_error_propagates_unchanged():
    url = "https://h.example.test/p.jpg"
    original = asyncio.CancelledError("caller cancelled")
    client = ScriptedClient({url: raises(lambda: original), "https://h.example.test/q.jpg": ok(jpeg(2, 2))})
    case = Case(5_003, "cancel", AggregateStatus.SUCCESS,
                urls={"poster_urls": (url, "https://h.example.test/q.jpg")})
    with pytest.raises(asyncio.CancelledError) as info:
        asyncio.run(acquire_images(make_record(case), client))
    assert info.value is original
    assert client.calls == [url]
