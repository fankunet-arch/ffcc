"""Aggregation configuration boundary (Phase 3 C1).

Everything a caller may configure is validated here, **before any network
request**, and rejected with :class:`AggregationConfigError` -- never with a
bare exception surfacing later from ``httpx`` (closes Phase 2 review finding
P2-R-08 on the normal Phase 3 config path).

``SourceConfig``
    one configured source: ``source_id``, ``enabled``, optional ``base_url``
    override, per-source wall-clock ``deadline_seconds``.
``AggregationConfig``
    the ordered tuple of ``SourceConfig`` (**that order is the default field
    priority**), ``max_concurrency`` and optional per-field priority overrides.

Both are frozen dataclasses of immutable members; validation happens in
``__post_init__`` and never mutates the instance.
"""

from __future__ import annotations

import ipaddress
import math
import re
from dataclasses import dataclass
from typing import Iterable, Mapping
from urllib.parse import urlsplit

from fc2_metadata_core.aggregation.policy import AggregationConfigError, AggregationPolicy
from fc2_metadata_core.aggregation.retry import RetryPolicy

__all__ = [
    "SourceConfig",
    "AggregationConfig",
    "validate_base_url",
    "DEFAULT_SOURCE_DEADLINE_SECONDS",
    "MAX_SOURCE_DEADLINE_SECONDS",
    "DEFAULT_MAX_CONCURRENCY",
    "MAX_CONCURRENCY_LIMIT",
]

DEFAULT_SOURCE_DEADLINE_SECONDS = 20.0
MAX_SOURCE_DEADLINE_SECONDS = 600.0
DEFAULT_MAX_CONCURRENCY = 3
MAX_CONCURRENCY_LIMIT = 64
_MAX_URL_CHARS = 2048

_HOST_LABEL_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
# Characters that may never appear anywhere in a base URL: ASCII controls
# (CR/LF/NUL/TAB/...), DEL, space, and the ones that make a URL ambiguous.
_FORBIDDEN_URL_CHARS = frozenset('\\<>"`{}|^ ')


def validate_base_url(value: object) -> str:
    """Return ``value`` if it is a safe absolute ``http(s)`` base URL, else raise.

    Accepts e.g. ``https://mirror.example``, ``http://127.0.0.1:8080/prefix``.
    Rejects (all with :class:`AggregationConfigError`, no network involved):
    non-``str``; empty; ``mirror.example`` (no scheme); ``http://`` / ``https://``
    (no host); any scheme other than http/https; embedded userinfo
    (``user:pw@host`` -- credentials must never ride in a URL); a query or
    fragment (adapters append their own path); a bad port; a host that is
    neither a valid DNS name nor an IP literal; and **any** control
    character (CR, LF, NUL, TAB ...), space, backslash, non-ASCII character or
    length over 2048 -- the injection / smuggling vectors that would otherwise
    only fail (or worse, succeed) inside the HTTP client.
    """
    if not isinstance(value, str):
        raise AggregationConfigError(f"base_url must be a str, got {type(value).__name__}")
    if not value:
        raise AggregationConfigError("base_url must not be empty")
    if len(value) > _MAX_URL_CHARS:
        raise AggregationConfigError(f"base_url is longer than {_MAX_URL_CHARS} characters")
    for char in value:
        if ord(char) < 0x21 or ord(char) == 0x7F or ord(char) > 0x7E or char in _FORBIDDEN_URL_CHARS:
            raise AggregationConfigError(
                f"base_url contains a forbidden character (U+{ord(char):04X}); "
                "control characters, spaces, backslashes and non-ASCII are not allowed"
            )
    try:
        parts = urlsplit(value)
        port = parts.port  # raises ValueError for a non-numeric / out-of-range port
        hostname = parts.hostname
    except ValueError as exc:
        raise AggregationConfigError(f"base_url is not a valid URL: {exc}") from None
    if parts.scheme not in ("http", "https"):
        raise AggregationConfigError("base_url must be an absolute http:// or https:// URL")
    if not parts.netloc or not hostname:
        raise AggregationConfigError("base_url has no host")
    if "@" in parts.netloc:
        raise AggregationConfigError("base_url must not contain userinfo (credentials)")
    if parts.query or parts.fragment or "?" in value or "#" in value:
        raise AggregationConfigError("base_url must not contain a query or fragment")
    if port is not None and not 1 <= port <= 65535:
        raise AggregationConfigError("base_url port is out of range")
    if not _is_valid_host(hostname):
        raise AggregationConfigError(f"base_url host {hostname!r} is not a valid DNS name or IP address")
    return value


def _is_valid_host(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass
    labels = hostname.rstrip(".").split(".")
    if len(hostname) > 253 or not all(labels):
        return False
    return all(_HOST_LABEL_RE.fullmatch(label) for label in labels)


def _validate_source_id(source_id: object) -> str:
    if not isinstance(source_id, str) or not source_id.strip() or source_id != source_id.strip():
        raise AggregationConfigError(f"invalid source_id {source_id!r}: must be a non-empty str without surrounding whitespace")
    return source_id


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """One configured source. Immutable and validated at construction."""

    source_id: str
    enabled: bool = True
    base_url: str | None = None
    deadline_seconds: float = DEFAULT_SOURCE_DEADLINE_SECONDS
    retry_policy: RetryPolicy | None = None  # None = use the AggregationConfig default

    def __post_init__(self) -> None:
        _validate_source_id(self.source_id)
        if self.retry_policy is not None and not isinstance(self.retry_policy, RetryPolicy):
            raise AggregationConfigError(f"source {self.source_id!r}: retry_policy must be a RetryPolicy or None")
        if not isinstance(self.enabled, bool):
            raise AggregationConfigError(f"source {self.source_id!r}: enabled must be a bool")
        if self.base_url is not None:
            try:
                validate_base_url(self.base_url)
            except AggregationConfigError as exc:
                raise AggregationConfigError(f"source {self.source_id!r}: {exc}") from None
        deadline = self.deadline_seconds
        if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
            raise AggregationConfigError(f"source {self.source_id!r}: deadline_seconds must be a number")
        if not math.isfinite(deadline) or deadline <= 0 or deadline > MAX_SOURCE_DEADLINE_SECONDS:
            raise AggregationConfigError(
                f"source {self.source_id!r}: deadline_seconds must be > 0 and <= "
                f"{MAX_SOURCE_DEADLINE_SECONDS:g}, got {deadline!r}"
            )


@dataclass(frozen=True, slots=True)
class AggregationConfig:
    """The whole aggregation configuration.

    ``sources``: ordered; **the order is the default field priority**.
    ``field_priority``: per-field override table as ``((field, source_ids), ...)``
    (use :meth:`create` to pass a plain mapping). ``max_concurrency``: how many
    sources may execute at once (default 3).

    Rejected: empty source set, no *enabled* source, duplicate ``source_id``,
    a field-priority entry for an unknown field / unconfigured source /
    duplicate id, ``max_concurrency`` outside ``1..64`` (or not an int).
    Whether a ``source_id`` is *registered* is checked when the engine is
    built (the config alone does not know the registry).
    """

    sources: tuple[SourceConfig, ...]
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    field_priority: tuple[tuple[str, tuple[str, ...]], ...] = ()
    retry_policy: RetryPolicy = RetryPolicy()

    def __post_init__(self) -> None:
        # Direct construction must be as safe as create(): only immutable shapes are
        # accepted, so nothing the caller still holds can change this config later.
        _validate_field_priority_shape(self.field_priority)
        if not isinstance(self.retry_policy, RetryPolicy):
            raise AggregationConfigError("retry_policy must be a RetryPolicy")
        if not isinstance(self.sources, tuple) or not all(isinstance(s, SourceConfig) for s in self.sources):
            raise AggregationConfigError("sources must be a tuple of SourceConfig")
        if not self.sources:
            raise AggregationConfigError("at least one source must be configured")
        seen: set[str] = set()
        for source in self.sources:
            if source.source_id in seen:
                raise AggregationConfigError(f"duplicate source_id {source.source_id!r}")
            seen.add(source.source_id)
        if not any(source.enabled for source in self.sources):
            raise AggregationConfigError("no source is enabled")
        if (
            isinstance(self.max_concurrency, bool)
            or not isinstance(self.max_concurrency, int)
            or not 1 <= self.max_concurrency <= MAX_CONCURRENCY_LIMIT
        ):
            raise AggregationConfigError(f"max_concurrency must be an int in 1..{MAX_CONCURRENCY_LIMIT}")
        # Validates field names, source ids and duplicates; also proves the
        # stored tuple is internally consistent.
        self.policy()

    @classmethod
    def create(
        cls,
        sources: Iterable[SourceConfig],
        *,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        field_priority: Mapping[str, Iterable[str]] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> "AggregationConfig":
        """Friendly constructor: accepts any iterable of sources and a plain mapping.

        Everything is copied into immutable tuples; later changes to the objects the
        caller passed cannot reach the returned config.
        """
        source_tuple = tuple(sources)
        overrides = _normalize_overrides(field_priority)
        return cls(
            source_tuple,
            max_concurrency,
            overrides,
            retry_policy if retry_policy is not None else RetryPolicy(),
        )

    def retry_policy_for(self, source_id: str) -> RetryPolicy:
        """The retry policy for ``source_id``: its own override, else the default."""
        for source in self.sources:
            if source.source_id == source_id:
                return source.retry_policy if source.retry_policy is not None else self.retry_policy
        raise AggregationConfigError(f"source {source_id!r} is not configured")

    @property
    def enabled_sources(self) -> tuple[SourceConfig, ...]:
        return tuple(source for source in self.sources if source.enabled)

    @property
    def disabled_source_ids(self) -> tuple[str, ...]:
        return tuple(source.source_id for source in self.sources if not source.enabled)

    def policy(self) -> AggregationPolicy:
        """The priority table for the *enabled* sources.

        Validated first against **all configured** sources (unknown field,
        duplicate id, empty override, or a source that is not configured at all
        is an error), then reduced to the enabled ones. An override may
        therefore mention a configured-but-disabled source -- it is simply
        skipped -- so disabling a source never invalidates the rest of the
        config.
        """
        configured_ids = tuple(source.source_id for source in self.sources)
        _validate_field_priority_shape(self.field_priority)
        overrides: dict[str, tuple[str, ...]] = {}
        for entry in self.field_priority:
            field_name, listed = entry
            if field_name in overrides:
                raise AggregationConfigError(f"field_priority: duplicate field {field_name!r}")
            overrides[field_name] = listed
        over_all = AggregationPolicy.build(configured_ids, overrides)
        enabled = {source.source_id for source in self.sources if source.enabled}
        enabled_ids = tuple(sid for sid in configured_ids if sid in enabled)
        reduced = tuple(
            (field_name, tuple(sid for sid in full_order if sid in enabled))
            for field_name, full_order in over_all.field_priority
        )
        return AggregationPolicy(source_order=enabled_ids, field_priority=reduced)


def _validate_field_priority_shape(field_priority: object) -> None:
    """Strictly ``tuple[tuple[str, tuple[str, ...]], ...]`` -- no list, dict or nested list.

    Rejects with :class:`AggregationConfigError` (never ``TypeError`` /
    ``KeyError`` / ``AttributeError``): a non-tuple container, an entry that is not
    a 2-tuple, a field name that is not a non-empty ``str`` (``None``, ints and
    unhashable objects included), or source ids that are not a ``tuple`` of ``str``.
    """
    if not isinstance(field_priority, tuple):
        raise AggregationConfigError(
            f"field_priority must be a tuple of (field, source_ids) pairs, got {type(field_priority).__name__}"
        )
    for entry in field_priority:
        if not (isinstance(entry, tuple) and len(entry) == 2):
            raise AggregationConfigError("field_priority entries must be (field, source_ids) 2-tuples")
        field_name, listed = entry
        if not isinstance(field_name, str) or not field_name:
            raise AggregationConfigError(f"field_priority field name must be a non-empty str, got {field_name!r}")
        if not isinstance(listed, tuple) or not all(isinstance(sid, str) for sid in listed):
            raise AggregationConfigError(
                f"field_priority[{field_name!r}] must be a tuple of source id strings, got {type(listed).__name__}"
            )


def _normalize_overrides(field_priority: Mapping[str, Iterable[str]] | None) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if field_priority is None:
        return ()
    if not isinstance(field_priority, Mapping):
        raise AggregationConfigError("field_priority must be a mapping of field name to source ids")
    entries: list[tuple[str, tuple[str, ...]]] = []
    for field_name, listed in field_priority.items():
        if isinstance(listed, (str, bytes)) or not isinstance(listed, Iterable):
            raise AggregationConfigError(f"field_priority[{field_name!r}] must be a list of source ids")
        entries.append((field_name, tuple(listed)))
    entries.sort(key=lambda entry: str(entry[0]))
    return tuple(entries)
