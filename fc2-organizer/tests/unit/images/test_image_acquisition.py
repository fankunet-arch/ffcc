"""P4-C5 substep 4: acquire_images orchestration (contract section 14).

Fully offline: a scripted in-memory ``ImageHttpClient`` returns ``ImageHttpResponse`` values
or raises the images transport errors. No httpx, socket or filesystem is involved.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import gc
import hashlib

import pytest

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.images import (
    AcquiredImage,
    ImageAcquisitionPolicy,
    ImageAcquisitionResult,
    ImageCandidateFailure,
    ImageClientClosedError,
    ImageConnectionError,
    ImageError,
    ImageInputError,
    ImageRedirectError,
    ImageRedirectLimitError,
    ImageResponseTooLargeError,
    ImageRole,
    ImageTimeoutError,
    ImageTransportError,
    ImageUrlError,
    UrlRejectionReason,
)
from fc2_organizer.images import ImageFailureKind as K
from fc2_organizer.images.acquisition import ROLE_METADATA_FIELDS, ROLE_ORDER, acquire_images
from fc2_organizer.images.transport import ImageHttpResponse
from fc2_organizer.planning import build_organize_plan
from fc2_organizer.publication import PublicationRecord

P, F, T, E = ImageRole.POSTER, ImageRole.FANART, ImageRole.THUMB, ImageRole.EXTRAFANART
N = "FC2-1234567"


# --- builders -------------------------------------------------------------------------------------------


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def jpeg(width: int = 640, height: int = 480, *, pad: int = 0, seed: int = 0) -> bytes:
    """A structurally valid baseline JPEG built segment by segment (``pad`` grows a COM segment)."""
    frame = bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00"
    scan = b"\x01\x01\x00\x00\x3f\x00"
    comments = b""
    remaining = pad
    while remaining > 0:
        chunk = min(remaining, 60_000)
        comments += _segment(0xFE, bytes([seed % 256]) * chunk)
        remaining -= chunk
    return (b"\xff\xd8" + _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00") + comments
            + _segment(0xDB, b"\x00" + bytes(range(1, 65))) + _segment(0xC0, frame)
            + _segment(0xDA, scan) + bytes([seed % 256, 0x12, 0xFF, 0x00, 0x34]) + b"\xff\xd9")


def ok(content: bytes | None = None, content_type: str | None = "image/jpeg") -> ImageHttpResponse:
    return ImageHttpResponse(status_code=200, content_type=content_type, content=jpeg() if content is None else content)


def status(code: int) -> ImageHttpResponse:
    return ImageHttpResponse(status_code=code, content_type="text/html", content=b"")


def make_record(**urls: tuple[str, ...]) -> PublicationRecord:
    item = DiscoveredMediaItem(index=0, source_path=r"C:\downloads\a.mp4", relative_path="a.mp4", extension=".mp4",
                               size=1)
    metadata = NormalizedMetadata(number=N, title="Example", **urls)
    plan = build_organize_plan(item, N, NormalizedMetadata(number=N, title="plan"), r"C:\library")
    return PublicationRecord(plan=plan, metadata=metadata, aggregate_status=AggregateStatus.SUCCESS)


def u(name: str) -> str:
    return f"https://img.example.test/{name}.jpg"


class ScriptedClient:
    """An ``ImageHttpClient`` whose every URL answer is scripted. Unscripted URLs fail the test."""

    def __init__(self, script: dict[str, object]) -> None:
        self.script = script
        self.calls: list[str] = []
        self.kwargs: list[dict[str, object]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def get(self, url: str, *, deadline_seconds: float, max_redirects: int, max_bytes: int):
        self.calls.append(url)
        self.kwargs.append(dict(deadline_seconds=deadline_seconds, max_redirects=max_redirects, max_bytes=max_bytes))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0)
            assert url in self.script, "unscripted request"
            outcome = self.script[url]
            if isinstance(outcome, type) and issubclass(outcome, BaseException):
                raise outcome()
            if isinstance(outcome, BaseException):
                raise outcome
            if callable(outcome):
                return await outcome()
            return outcome
        finally:
            self.in_flight -= 1

    async def aclose(self) -> None:
        return None


def acquire(record: PublicationRecord, script: dict[str, object], policy: ImageAcquisitionPolicy | None = None):
    client = ScriptedClient(script)
    result = asyncio.run(acquire_images(record, client, policy=policy))
    assert client.max_in_flight <= 1  # never more than one request in flight
    return result, client


def kinds(result: ImageAcquisitionResult) -> list[tuple[ImageRole, int, K, int | None]]:
    return [(f.role, f.candidate_index, f.kind, f.http_status) for f in result.failures]


# --- 1-7: basic role behaviour --------------------------------------------------------------------------


def test_no_candidates_is_an_empty_valid_result():
    result, client = acquire(make_record(), {})
    assert result == ImageAcquisitionResult()
    assert client.calls == []


def test_poster_first_success_stops_the_role():
    record = make_record(poster_urls=(u("p0"), u("p1"), u("p2")))
    result, client = acquire(record, {u("p0"): ok()})
    assert client.calls == [u("p0")]
    assert result.poster is not None and result.poster.candidate_index == 0 and result.poster.role is P
    assert result.failures == ()


def test_poster_fail_then_success():
    record = make_record(poster_urls=(u("p0"), u("p1"), u("p2")))
    result, client = acquire(record, {u("p0"): status(404), u("p1"): ok()})
    assert client.calls == [u("p0"), u("p1")]
    assert result.poster.candidate_index == 1
    assert kinds(result) == [(P, 0, K.HTTP_STATUS, 404)]


def test_poster_all_fail():
    record = make_record(poster_urls=(u("p0"), u("p1")))
    result, _ = acquire(record, {u("p0"): status(500), u("p1"): ImageTimeoutError})
    assert result.poster is None
    assert kinds(result) == [(P, 0, K.HTTP_STATUS, 500), (P, 1, K.TIMEOUT, None)]


def test_role_isolation_scenario():
    record = make_record(
        poster_urls=(u("p0"), u("p1")), fanart_urls=(u("f0"),), thumb_urls=(u("t0"),),
        extrafanart=(u("e0"), u("e1"), u("e2")),
    )
    script = {
        u("p0"): status(404), u("p1"): ok(jpeg(1, 2)),
        u("f0"): ImageTimeoutError,
        u("t0"): ok(jpeg(3, 4)),
        u("e0"): ok(jpeg(5, 6)), u("e1"): ok(b"\xff\xd8 not a jpeg \xff\xd9"), u("e2"): ok(jpeg(7, 8)),
    }
    result, client = acquire(record, script)
    assert client.calls == [u("p0"), u("p1"), u("f0"), u("t0"), u("e0"), u("e1"), u("e2")]
    assert (result.poster.width, result.poster.height) == (1, 2)
    assert result.fanart is None
    assert (result.thumb.width, result.thumb.height) == (3, 4)
    assert [(x.candidate_index, x.width) for x in result.extrafanart] == [(0, 5), (2, 7)]
    assert kinds(result) == [(P, 0, K.HTTP_STATUS, 404), (F, 0, K.TIMEOUT, None), (E, 1, K.INVALID_JPEG, None)]


def test_fanart_failure_does_not_remove_poster_and_thumb_is_independent():
    record = make_record(poster_urls=(u("p0"),), fanart_urls=(u("f0"), u("f1")), thumb_urls=(u("t0"),))
    result, _ = acquire(record, {u("p0"): ok(), u("f0"): status(403), u("f1"): ImageConnectionError,
                                 u("t0"): ok(jpeg(9, 9))})
    assert result.poster is not None and result.fanart is None and result.thumb.width == 9


def test_no_cross_role_fallback():
    # poster candidates all fail; fanart / thumb successes are never promoted to poster
    record = make_record(poster_urls=(u("p0"),), fanart_urls=(u("f0"),), thumb_urls=(u("t0"),))
    result, _ = acquire(record, {u("p0"): status(404), u("f0"): ok(), u("t0"): ok()})
    assert result.poster is None and result.fanart.role is F and result.thumb.role is T


# --- 7-8: extrafanart -----------------------------------------------------------------------------------


def test_extrafanart_mixed_success_and_failure_keeps_order():
    urls = tuple(u(f"e{i}") for i in range(5))
    script = {urls[0]: ok(jpeg(10, 10)), urls[1]: status(404), urls[2]: ok(jpeg(20, 20)),
              urls[3]: ok(content_type="image/png"), urls[4]: ok(jpeg(40, 40))}
    result, client = acquire(make_record(extrafanart=urls), script)
    assert [x.width for x in result.extrafanart] == [10, 20, 40]
    assert [x.candidate_index for x in result.extrafanart] == [0, 2, 4]
    assert kinds(result) == [(E, 1, K.HTTP_STATUS, 404), (E, 3, K.CONTENT_TYPE_MISMATCH, None)]
    assert client.calls == list(urls)


def test_extrafanart_success_limit_stops_requests_without_failures():
    urls = tuple(u(f"e{i}") for i in range(10))
    policy = ImageAcquisitionPolicy(max_extrafanart=3)
    script = {url: ok() for url in urls}
    script[urls[1]] = status(404)
    result, client = acquire(make_record(extrafanart=urls), script, policy)
    assert [x.candidate_index for x in result.extrafanart] == [0, 2, 3]
    assert client.calls == [urls[0], urls[1], urls[2], urls[3]]  # nothing after the 3rd success
    assert kinds(result) == [(E, 1, K.HTTP_STATUS, 404)]  # no CANDIDATE_LIMIT for normal completion


# --- 9-17: fallback after each failure kind ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("first_url", "first_outcome", "expected"),
    [
        ("not a url", None, (K.INVALID_URL, None)),
        ("/relative/p.jpg", None, (K.INVALID_URL, None)),
        ("http://127.0.0.1/p.jpg", None, (K.UNSAFE_URL, None)),
        ("http://localhost/p.jpg", None, (K.UNSAFE_URL, None)),
        ("file:///etc/passwd", None, (K.UNSAFE_URL, None)),
        (u("timeout"), ImageTimeoutError, (K.TIMEOUT, None)),
        (u("conn"), ImageConnectionError, (K.CONNECTION_ERROR, None)),
        (u("redir"), ImageRedirectLimitError, (K.REDIRECT_LIMIT, None)),
        (u("unsafe-redirect"), ImageRedirectError(UrlRejectionReason.NON_GLOBAL_IP), (K.UNSAFE_URL, None)),
        (u("bad-location"), ImageRedirectError(), (K.TRANSPORT_ERROR, None)),
        (u("big"), ImageResponseTooLargeError, (K.TOO_LARGE, None)),
        (u("transport"), ImageTransportError, (K.TRANSPORT_ERROR, None)),
        (u("closed"), ImageClientClosedError, (K.TRANSPORT_ERROR, None)),
        (u("url-from-client"), ImageUrlError(UrlRejectionReason.USERINFO), (K.UNSAFE_URL, None)),
        (u("buggy-client"), RuntimeError("client bug"), (K.TRANSPORT_ERROR, None)),
        (u("junk-response"), lambda: _junk(), (K.TRANSPORT_ERROR, None)),
        (u("404"), status(404), (K.HTTP_STATUS, 404)),
        (u("429"), status(429), (K.HTTP_STATUS, 429)),
        (u("204"), ImageHttpResponse(204, None, b""), (K.HTTP_STATUS, 204)),
        (u("png-mime"), ok(content_type="image/png"), (K.CONTENT_TYPE_MISMATCH, None)),
        (u("html-mime"), ok(content_type="text/html; charset=utf-8"), (K.CONTENT_TYPE_MISMATCH, None)),
        (u("bad-jpeg"), ok(b"\x89PNG\r\n\x1a\n" + b"\x00" * 30, "application/octet-stream"), (K.INVALID_JPEG, None)),
        (u("bad-dims"), ok(jpeg(30_000, 10)), (K.INVALID_DIMENSIONS, None)),
        (u("zero-dims"), ok(jpeg(0, 10)), (K.INVALID_DIMENSIONS, None)),
    ],
)
def test_each_failure_kind_then_valid_candidate(first_url, first_outcome, expected):
    record = make_record(poster_urls=(first_url, u("good")))
    script = {u("good"): ok(jpeg(11, 12))}
    if first_outcome is not None:
        script[first_url] = first_outcome
    result, client = acquire(record, script)
    assert result.poster is not None and result.poster.candidate_index == 1 and result.poster.width == 11
    assert kinds(result) == [(P, 0, *expected)]
    if first_outcome is None:  # rejected by validate_image_url: never requested
        assert client.calls == [u("good")]
    else:
        assert client.calls == [first_url, u("good")]  # each candidate requested exactly once


async def _junk():
    return {"status_code": 200, "content": b"\xff\xd8"}


# --- 18-19: candidate-count limit ---------------------------------------------------------------------------


def test_candidate_overflow_sends_zero_requests_for_that_role_and_others_still_run():
    policy = ImageAcquisitionPolicy(max_candidates_per_role=3)
    record = make_record(poster_urls=tuple(u(f"p{i}") for i in range(4)), fanart_urls=(u("f0"),),
                         thumb_urls=tuple(u(f"t{i}") for i in range(3)), extrafanart=tuple(u(f"e{i}") for i in range(9)))
    script = {u("f0"): ok(), u("t0"): ok()}
    result, client = acquire(record, script, policy)
    assert client.calls == [u("f0"), u("t0")]
    assert result.poster is None and result.fanart is not None and result.thumb is not None
    assert result.extrafanart == ()
    assert kinds(result) == [(P, 3, K.CANDIDATE_LIMIT, None), (E, 3, K.CANDIDATE_LIMIT, None)]


def test_candidate_count_exactly_at_limit_is_processed():
    policy = ImageAcquisitionPolicy(max_candidates_per_role=2)
    record = make_record(poster_urls=(u("p0"), u("p1")))
    result, client = acquire(record, {u("p0"): status(404), u("p1"): ok()}, policy)
    assert result.poster.candidate_index == 1 and len(client.calls) == 2


# --- 20-22: total-result cap -----------------------------------------------------------------------------------


def test_total_bytes_exact_boundary_accepted():
    a, b = jpeg(pad=1000, seed=1), jpeg(pad=2000, seed=2)
    policy = ImageAcquisitionPolicy(max_image_bytes=len(a) + len(b), max_total_bytes=len(a) + len(b))
    result, _ = acquire(make_record(poster_urls=(u("p"),), fanart_urls=(u("f"),)), {u("p"): ok(a), u("f"): ok(b)},
                        policy)
    assert result.total_bytes == len(a) + len(b) == policy.max_total_bytes
    assert result.failures == ()


def test_image_exceeding_total_cap_is_dropped_and_everything_stops():
    a, b = jpeg(pad=1000, seed=1), jpeg(pad=2000, seed=2)
    policy = ImageAcquisitionPolicy(max_image_bytes=len(a) + len(b) - 1, max_total_bytes=len(a) + len(b) - 1)
    record = make_record(poster_urls=(u("p"),), fanart_urls=(u("f0"), u("f1")), thumb_urls=(u("t"),),
                         extrafanart=(u("e0"), u("e1")))
    script = {u("p"): ok(a), u("f0"): ok(b), u("f1"): ok(), u("t"): ok(), u("e0"): ok(), u("e1"): ok()}
    result, client = acquire(record, script, policy)
    assert client.calls == [u("p"), u("f0")]  # no request after TOTAL_BYTES_LIMIT
    assert result.poster is not None and result.poster.content == a
    assert result.fanart is None and result.thumb is None and result.extrafanart == ()
    assert kinds(result) == [(F, 0, K.TOTAL_BYTES_LIMIT, None)]
    assert result.total_bytes == len(a) <= policy.max_total_bytes


def test_total_cap_hit_inside_extrafanart_stops_remaining_extrafanart():
    img = jpeg(pad=500)
    policy = ImageAcquisitionPolicy(max_image_bytes=len(img) * 2, max_total_bytes=len(img) * 2)
    urls = tuple(u(f"e{i}") for i in range(5))
    result, client = acquire(make_record(extrafanart=urls), {url: ok(img) for url in urls}, policy)
    assert len(result.extrafanart) == 2 and client.calls == list(urls[:3])
    assert kinds(result) == [(E, 2, K.TOTAL_BYTES_LIMIT, None)]


def test_invalid_payloads_do_not_count_towards_total():
    good = jpeg(pad=100)
    policy = ImageAcquisitionPolicy(max_image_bytes=len(good), max_total_bytes=len(good))
    record = make_record(poster_urls=(u("bad"), u("good")))
    result, _ = acquire(record, {u("bad"): ok(b"\xff\xd8" + b"\x00" * 5000), u("good"): ok(good)}, policy)
    assert result.poster.content == good and kinds(result) == [(P, 0, K.INVALID_JPEG, None)]


def test_policy_values_are_passed_to_the_client():
    policy = ImageAcquisitionPolicy(request_deadline_seconds=3.5, max_redirects=2, max_image_bytes=12345,
                                    max_total_bytes=99999)
    _, client = acquire(make_record(poster_urls=(u("p"),)), {u("p"): ok()}, policy)
    assert client.kwargs == [dict(deadline_seconds=3.5, max_redirects=2, max_bytes=12345)]


def test_default_policy_is_used_when_none():
    _, client = acquire(make_record(poster_urls=(u("p"),)), {u("p"): ok()}, None)
    assert client.kwargs == [dict(deadline_seconds=15.0, max_redirects=5, max_bytes=16 * 1024 * 1024)]


# --- 23-25: artifacts ------------------------------------------------------------------------------------------


def test_artifact_digest_size_and_dimensions():
    content = jpeg(1920, 1080, pad=77, seed=5)
    result, _ = acquire(make_record(thumb_urls=(u("t"),)), {u("t"): ok(content, None)})
    image = result.thumb
    assert type(image) is AcquiredImage
    assert image.sha256 == hashlib.sha256(content).hexdigest()
    assert (image.width, image.height) == (1920, 1080)  # copied from the SOF header via JpegInfo
    assert image.size_bytes == len(content) and image.content == content and type(image.content) is bytes
    assert {f.name for f in dataclasses.fields(AcquiredImage)} == {
        "role", "candidate_index", "content", "width", "height", "size_bytes", "sha256"}


def test_same_bytes_in_different_roles_and_duplicates_are_not_deduplicated():
    content = jpeg(pad=10)
    record = make_record(poster_urls=(u("x"),), fanart_urls=(u("x"),), thumb_urls=(u("y"),),
                         extrafanart=(u("x"), u("y"), u("x")))
    result, client = acquire(record, {u("x"): ok(content), u("y"): ok(content)})
    digests = [result.poster.sha256, result.fanart.sha256, result.thumb.sha256] + [e.sha256 for e in result.extrafanart]
    assert len(digests) == 6 and len(set(digests)) == 1
    assert client.calls == [u("x"), u("x"), u("y"), u("x"), u("y"), u("x")]
    assert result.total_bytes == 6 * len(content)


# --- 26-27: determinism and order -----------------------------------------------------------------------------


def _mixed():
    record = make_record(
        poster_urls=(u("p0"), "http://10.0.0.1/p.jpg", u("p2")), fanart_urls=(u("f0"), u("f1")),
        thumb_urls=(u("t0"),), extrafanart=tuple(u(f"e{i}") for i in range(6)),
    )
    script = {
        u("p0"): status(503), u("p2"): ok(jpeg(2, 2)), u("f0"): ImageConnectionError, u("f1"): ok(jpeg(3, 3)),
        u("t0"): ok(content_type="image/webp"), u("e0"): ok(jpeg(4, 4)), u("e1"): ImageTimeoutError,
        u("e2"): ok(jpeg(5, 5)), u("e3"): status(404), u("e4"): ok(jpeg(6, 6)), u("e5"): ok(jpeg(7, 7)),
    }
    return record, script


def test_request_order_is_exactly_poster_fanart_thumb_extrafanart():
    record, script = _mixed()
    _, client = acquire(record, script)
    assert client.calls == [u("p0"), u("p2"), u("f0"), u("f1"), u("t0")] + [u(f"e{i}") for i in range(6)]
    assert ROLE_ORDER == (P, F, T, E)
    assert ROLE_METADATA_FIELDS == {P: "poster_urls", F: "fanart_urls", T: "thumb_urls", E: "extrafanart"}


def test_failure_order_and_whole_result_are_deterministic():
    record, script = _mixed()
    first, c1 = acquire(record, script)
    second, c2 = acquire(record, script)
    assert first == second and c1.calls == c2.calls
    assert kinds(first) == [
        (P, 0, K.HTTP_STATUS, 503), (P, 1, K.UNSAFE_URL, None), (F, 0, K.CONNECTION_ERROR, None),
        (T, 0, K.CONTENT_TYPE_MISMATCH, None), (E, 1, K.TIMEOUT, None), (E, 3, K.HTTP_STATUS, 404),
    ]
    assert [(x.candidate_index, x.width) for x in first.extrafanart] == [(0, 4), (2, 5), (4, 6), (5, 7)]


# --- 28: cancellation and fatal exceptions ----------------------------------------------------------------------


def test_caller_cancellation_propagates_and_is_not_recorded():
    started = asyncio.Event()

    async def hang():
        started.set()
        await asyncio.sleep(3600)

    async def scenario():
        client = ScriptedClient({u("p0"): hang, u("p1"): ok()})
        task = asyncio.create_task(acquire_images(make_record(poster_urls=(u("p0"), u("p1"))), client))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client.calls == [u("p0")]  # no fallback after cancellation

    asyncio.run(scenario())


def test_cancelled_error_raised_by_client_propagates():
    with pytest.raises(asyncio.CancelledError):
        acquire(make_record(poster_urls=(u("p0"), u("p1"))), {u("p0"): asyncio.CancelledError, u("p1"): ok()})


class _Fatal(BaseException):
    pass


@pytest.mark.parametrize("fatal", [_Fatal, KeyboardInterrupt, SystemExit])
def test_fatal_base_exceptions_are_not_swallowed(fatal):
    with pytest.raises(fatal):
        acquire(make_record(poster_urls=(u("p0"), u("p1"))), {u("p0"): fatal, u("p1"): ok()})


# --- 29-30: candidate shape defence ---------------------------------------------------------------------------------


def _forge(record: PublicationRecord, field: str, value: object) -> PublicationRecord:
    object.__setattr__(record.metadata, field, value)
    return record


@pytest.mark.parametrize("field", ["poster_urls", "fanart_urls", "thumb_urls", "extrafanart"])
@pytest.mark.parametrize(
    "value",
    [[u("a")], {u("a")}, (x for x in [u("a")]), frozenset({u("a")}), None, u("a")],
    ids=["list", "set", "generator", "frozenset", "none", "bare-str"],
)
def test_non_tuple_candidate_collection_fails_typed_before_any_request(field, value):
    record = _forge(make_record(poster_urls=(u("p"),)), field, value)
    client = ScriptedClient({u("p"): ok()})
    with pytest.raises(ImageInputError) as info:
        asyncio.run(acquire_images(record, client))
    assert client.calls == []
    assert field in str(info.value) and "img.example.test" not in str(info.value)


class _StrSub(str):
    pass


@pytest.mark.parametrize("item", [b"https://img.example.test/a.jpg", 1, None, _StrSub(u("a"))])
def test_non_str_candidate_fails_typed_before_any_request(item):
    record = _forge(make_record(poster_urls=(u("p"),)), "extrafanart", (u("ok"), item))
    client = ScriptedClient({})
    with pytest.raises(ImageInputError):
        asyncio.run(acquire_images(record, client))
    assert client.calls == []


def test_tuple_subclass_collection_fails_typed():
    class TupleSub(tuple):
        pass

    record = _forge(make_record(), "thumb_urls", TupleSub((u("t"),)))
    with pytest.raises(ImageInputError):
        asyncio.run(acquire_images(record, ScriptedClient({})))


@pytest.mark.parametrize("bad", [None, "record", object()])
def test_record_must_be_exact_publication_record(bad):
    with pytest.raises(ImageInputError):
        asyncio.run(acquire_images(bad, ScriptedClient({})))  # type: ignore[arg-type]


def test_policy_and_client_are_validated():
    record = make_record()
    with pytest.raises(ImageInputError):
        asyncio.run(acquire_images(record, ScriptedClient({}), policy={"max_redirects": 1}))  # type: ignore[arg-type]
    with pytest.raises(ImageInputError):
        asyncio.run(acquire_images(record, None))  # type: ignore[arg-type]
    with pytest.raises(ImageInputError):
        asyncio.run(acquire_images(record, object()))  # type: ignore[arg-type]
    assert issubclass(ImageInputError, ImageError)


# --- 31, sensitive token: result graph ---------------------------------------------------------------------------

SECRET = "SUPERSECRET"


def _walk(obj, seen=None):
    seen = set() if seen is None else seen
    if id(obj) in seen:
        return
    seen.add(id(obj))
    yield obj
    if isinstance(obj, (type, str, bytes, int, float, bool)) or obj is None:
        return
    for child in gc.get_referents(obj):
        if isinstance(child, type):
            continue
        yield from _walk(child, seen)


def test_result_graph_holds_no_url_exception_or_http_object():
    record = make_record(
        poster_urls=(f"https://example.com/a.jpg?token={SECRET}", u("p1")),
        fanart_urls=(f"http://127.0.0.1/f.jpg?token={SECRET}",),
        thumb_urls=(f"https://example.com/t.jpg?token={SECRET}",),
        extrafanart=(f"https://example.com/e.jpg?token={SECRET}", u("e1")),
    )
    script = {
        f"https://example.com/a.jpg?token={SECRET}": ImageTimeoutError,
        u("p1"): ok(),
        f"https://example.com/t.jpg?token={SECRET}": status(403),
        f"https://example.com/e.jpg?token={SECRET}": ok(content_type="text/html"),
        u("e1"): ok(),
    }
    result, _ = acquire(record, script)
    assert len(result.failures) == 4
    for text in (repr(result), repr(result.failures), str(result)):
        assert SECRET not in text and "example.com" not in text and "img.example.test" not in text
    for node in _walk(result):
        assert not isinstance(node, (BaseException, ImageHttpResponse, dict, list)), type(node)
        if type(node) is str:
            assert SECRET not in node and "://" not in node, node
        assert type(node).__module__.split(".")[0] not in ("httpx", "httpcore"), type(node)
    for failure in result.failures:
        assert type(failure) is ImageCandidateFailure
        assert {f.name for f in dataclasses.fields(failure)} == {"role", "candidate_index", "kind", "http_status"}


def test_domain_errors_never_contain_the_secret():
    for field in ("poster_urls", "extrafanart"):
        record = _forge(make_record(), field, [f"https://example.com/a.jpg?token={SECRET}"])
        with pytest.raises(ImageInputError) as info:
            asyncio.run(acquire_images(record, ScriptedClient({})))
        rendered = " ".join([str(info.value), repr(info.value), repr(info.value.args)])
        assert SECRET not in rendered and "example.com" not in rendered


# --- 32: inputs unchanged -------------------------------------------------------------------------------------------


def test_record_and_metadata_unchanged_after_acquisition():
    record, script = _mixed()
    before_record = copy.copy(record)
    before_fields = {f.name: getattr(record.metadata, f.name) for f in dataclasses.fields(record.metadata)}
    policy = ImageAcquisitionPolicy()
    acquire(record, script, policy)
    assert record == before_record and record.metadata is before_record.metadata
    assert {f.name: getattr(record.metadata, f.name) for f in dataclasses.fields(record.metadata)} == before_fields
    assert policy == ImageAcquisitionPolicy()
