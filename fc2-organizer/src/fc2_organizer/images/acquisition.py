"""Image acquisition orchestration (P4-C5 substep 4, contract section 14).

::

    acquire_images(record, client, policy=None) -> ImageAcquisitionResult

    roles, in this fixed order, each from exactly one metadata field (no cross-role fallback):
        POSTER <- metadata.poster_urls      first valid JPEG wins
        FANART <- metadata.fanart_urls      first valid JPEG wins
        THUMB  <- metadata.thumb_urls       first valid JPEG wins
        EXTRAFANART <- metadata.extrafanart every valid JPEG, up to policy.max_extrafanart

    per candidate (strictly sequential -- at most one request in flight, no gather):
        validate_image_url -> client.get -> status == 200 -> Content-Type policy
        -> JPEG structure -> dimensions -> total-result cap -> AcquiredImage
    any step failing -> ImageCandidateFailure(role, index, kind[, http_status]) -> next candidate
    (never the same URL twice).

Memory only: no file is opened, written, stat-ed or resolved. The HTTP client is
injected (never constructed here). The result keeps only builtin values and images
models: no URL, Content-Type, status of a success, header, response, exception or
traceback.
"""

from __future__ import annotations

import hashlib

from fc2_organizer.images.errors import (
    ImageConnectionError,
    ImageContentTypeError,
    ImageDimensionError,
    ImageFailureKind,
    ImageInputError,
    ImageJpegError,
    ImageRedirectError,
    ImageRedirectLimitError,
    ImageResponseTooLargeError,
    ImageTimeoutError,
    ImageUrlError,
)
from fc2_organizer.images.jpeg import validate_acquired_image
from fc2_organizer.images.models import (
    AcquiredImage,
    ImageAcquisitionResult,
    ImageCandidateFailure,
    ImageRole,
)
from fc2_organizer.images.policy import ImageAcquisitionPolicy
from fc2_organizer.images.transport import ImageHttpClient, ImageHttpResponse
from fc2_organizer.images.urls import validate_image_url
from fc2_organizer.publication import PublicationRecord

__all__ = ["ROLE_ORDER", "ROLE_METADATA_FIELDS", "acquire_images"]

# Frozen request order and the one metadata field each role reads.
ROLE_ORDER: tuple[ImageRole, ...] = (ImageRole.POSTER, ImageRole.FANART, ImageRole.THUMB, ImageRole.EXTRAFANART)
ROLE_METADATA_FIELDS: dict[ImageRole, str] = {
    ImageRole.POSTER: "poster_urls",
    ImageRole.FANART: "fanart_urls",
    ImageRole.THUMB: "thumb_urls",
    ImageRole.EXTRAFANART: "extrafanart",
}


def _candidates_by_role(record: PublicationRecord) -> dict[ImageRole, tuple[str, ...]]:
    """Every candidate collection must be an exact ``tuple`` of exact ``str`` -- checked for
    all four roles before any request. The message names only the field, never a value.

    ``record.metadata`` itself is trusted as far as ``PublicationRecord`` guarantees it (an
    ``isinstance`` ``NormalizedMetadata``); a hostile metadata *subclass* is the carried
    P4-C4-R-01 class of finding and is deliberately not re-litigated here."""
    metadata = record.metadata
    result: dict[ImageRole, tuple[str, ...]] = {}
    for role in ROLE_ORDER:
        name = ROLE_METADATA_FIELDS[role]
        value = getattr(metadata, name)
        if type(value) is not tuple:
            raise ImageInputError(f"metadata.{name} must be an exact tuple of exact str")
        for item in value:
            if type(item) is not str:
                raise ImageInputError(f"metadata.{name} must be an exact tuple of exact str")
        result[role] = value
    return result


def _request_failure_kind(exc: Exception) -> ImageFailureKind:
    """Structured mapping by exception *type* (never by message text)."""
    if isinstance(exc, (ImageUrlError, ImageRedirectError)):
        return exc.failure_kind  # INVALID_URL / UNSAFE_URL (or TRANSPORT_ERROR: redirect w/o Location)
    if isinstance(exc, ImageTimeoutError):
        return ImageFailureKind.TIMEOUT
    if isinstance(exc, ImageConnectionError):
        return ImageFailureKind.CONNECTION_ERROR
    if isinstance(exc, ImageRedirectLimitError):
        return ImageFailureKind.REDIRECT_LIMIT
    if isinstance(exc, ImageResponseTooLargeError):
        return ImageFailureKind.TOO_LARGE
    # Any other ImageTransportError / ImageError, or an ordinary Exception from an injected
    # client that breaks the ImageHttpClient contract.
    return ImageFailureKind.TRANSPORT_ERROR


class _Run:
    """Mutable bookkeeping of one acquire_images call (never escapes it)."""

    def __init__(self, client: ImageHttpClient, policy: ImageAcquisitionPolicy) -> None:
        self.client = client
        self.policy = policy
        self.total_bytes = 0
        self.stopped = False  # set once TOTAL_BYTES_LIMIT is hit: no further request of any role
        self.failures: list[ImageCandidateFailure] = []

    def fail(self, role: ImageRole, index: int, kind: ImageFailureKind, http_status: int | None = None) -> None:
        self.failures.append(ImageCandidateFailure(role, index, kind, http_status))

    async def try_candidate(self, role: ImageRole, index: int, url: str) -> AcquiredImage | None:
        """One candidate, one request at most. Returns the image or records exactly one failure."""
        try:
            validate_image_url(url)
        except ImageUrlError as exc:
            self.fail(role, index, exc.failure_kind)
            return None

        policy = self.policy
        try:
            response = await self.client.get(
                url,
                deadline_seconds=policy.request_deadline_seconds,
                max_redirects=policy.max_redirects,
                max_bytes=policy.max_image_bytes,
            )
        except Exception as exc:  # BaseException (CancelledError, KeyboardInterrupt ...) propagates
            self.fail(role, index, _request_failure_kind(exc))
            return None

        if type(response) is not ImageHttpResponse:
            self.fail(role, index, ImageFailureKind.TRANSPORT_ERROR)
            return None
        if response.status_code != 200:
            self.fail(role, index, ImageFailureKind.HTTP_STATUS, response.status_code)
            return None

        content = response.content
        try:
            info = validate_acquired_image(content, response.content_type)
        except ImageContentTypeError:
            self.fail(role, index, ImageFailureKind.CONTENT_TYPE_MISMATCH)
            return None
        except ImageJpegError:
            self.fail(role, index, ImageFailureKind.INVALID_JPEG)
            return None
        except ImageDimensionError:
            self.fail(role, index, ImageFailureKind.INVALID_DIMENSIONS)
            return None

        size = len(content)
        if self.total_bytes + size > policy.max_total_bytes:
            # The payload that would overflow never enters the result; everything stops.
            self.fail(role, index, ImageFailureKind.TOTAL_BYTES_LIMIT)
            self.stopped = True
            return None
        self.total_bytes += size
        return AcquiredImage(
            role=role,
            candidate_index=index,
            content=content,
            width=info.width,
            height=info.height,
            size_bytes=size,
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def over_candidate_limit(self, role: ImageRole, candidates: tuple[str, ...]) -> bool:
        limit = self.policy.max_candidates_per_role
        if len(candidates) > limit:
            # No silent truncation: the role sends nothing; the index is the first disallowed one.
            self.fail(role, limit, ImageFailureKind.CANDIDATE_LIMIT)
            return True
        return False

    async def single(self, role: ImageRole, candidates: tuple[str, ...]) -> AcquiredImage | None:
        if self.stopped or self.over_candidate_limit(role, candidates):
            return None
        for index, url in enumerate(candidates):
            image = await self.try_candidate(role, index, url)
            if image is not None:
                return image
            if self.stopped:
                return None
        return None

    async def extrafanart(self, candidates: tuple[str, ...]) -> tuple[AcquiredImage, ...]:
        acquired: list[AcquiredImage] = []
        if self.stopped or self.over_candidate_limit(ImageRole.EXTRAFANART, candidates):
            return ()
        for index, url in enumerate(candidates):
            if len(acquired) >= self.policy.max_extrafanart:
                break  # normal completion: later candidates are neither requested nor recorded
            image = await self.try_candidate(ImageRole.EXTRAFANART, index, url)
            if image is not None:
                acquired.append(image)
            elif self.stopped:
                break
        return tuple(acquired)


async def acquire_images(
    record: PublicationRecord,
    client: ImageHttpClient,
    *,
    policy: ImageAcquisitionPolicy | None = None,
) -> ImageAcquisitionResult:
    """Acquire poster / fanart / thumb / extrafanart JPEGs for one publication record.

    Input errors (``ImageInputError``, before any request): ``record`` not an exact
    ``PublicationRecord``; any of the four candidate collections not an exact ``tuple`` of exact ``str``; ``policy`` not ``None`` or
    an exact ``ImageAcquisitionPolicy``; ``client`` without a callable ``get``.

    Every per-candidate problem becomes an ``ImageCandidateFailure``; no candidate failure
    raises. ``asyncio.CancelledError`` and other ``BaseException`` propagate unchanged.
    """
    if type(record) is not PublicationRecord:
        raise ImageInputError("record must be an exact PublicationRecord")
    if policy is None:
        policy = ImageAcquisitionPolicy()
    elif type(policy) is not ImageAcquisitionPolicy:
        raise ImageInputError("policy must be None or an exact ImageAcquisitionPolicy")
    if client is None or not callable(getattr(client, "get", None)):
        raise ImageInputError("client must provide an async get(...) (ImageHttpClient)")
    candidates = _candidates_by_role(record)

    run = _Run(client, policy)
    poster = await run.single(ImageRole.POSTER, candidates[ImageRole.POSTER])
    fanart = await run.single(ImageRole.FANART, candidates[ImageRole.FANART])
    thumb = await run.single(ImageRole.THUMB, candidates[ImageRole.THUMB])
    extrafanart = await run.extrafanart(candidates[ImageRole.EXTRAFANART])
    return ImageAcquisitionResult(
        poster=poster,
        fanart=fanart,
        thumb=thumb,
        extrafanart=extrafanart,
        failures=tuple(run.failures),
    )
