"""NormalizedMetadata: the FC2 Metadata Core's own metadata model.

This is a deliberately independent contract, not a copy of Amane's
``MediaMetadata`` (``src/amane/crawlers/models.py``). Phase 0 found that
Amane's model uses singular ``external_id`` / ``source_url``, while this
project's spec calls for plural, multi-source ``external_ids`` /
``source_urls`` so that Phase 3's field-level aggregation can track more
than one contributing source per film. Narrowing that shape down to
Amane's singular fields is explicitly deferred to the Phase 5 adapter; this
module must not be shaped around Amane's current fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fc2_metadata_core.errors import MetadataContractError
from fc2_metadata_core.normalize.fc2_number import is_valid_fc2_number

__all__ = ["NormalizedMetadata"]


@dataclass(slots=True)
class NormalizedMetadata:
    """Partial-safe, source-agnostic FC2 film metadata.

    Every field except ``number``/``title`` may be absent (``None`` for
    scalars, empty for collections) -- ``NormalizedMetadata()`` with no
    arguments at all is a valid, fully partial instance. The only frozen
    rule (see :meth:`meets_minimum_success`) is:

        minimum success = a valid canonical FC2 number + a non-empty title

    List/mapping fields all use ``default_factory`` so that two independent
    instances never share the same underlying list/dict.
    """

    number: str | None = None
    title: str | None = None
    studio: str | None = None
    publisher: str | None = None
    release: str | None = None
    runtime: int | None = None
    actors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    plot: str | None = None

    poster_urls: list[str] = field(default_factory=list)
    thumb_urls: list[str] = field(default_factory=list)
    fanart_urls: list[str] = field(default_factory=list)
    extrafanart: list[str] = field(default_factory=list)

    source_urls: list[str] = field(default_factory=list)
    external_ids: dict[str, str] = field(default_factory=dict)
    field_sources: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.runtime is not None:
            if not isinstance(self.runtime, int) or isinstance(self.runtime, bool):
                raise MetadataContractError("runtime must be an int or None")
            if self.runtime < 0:
                raise MetadataContractError("runtime must not be negative")

    def has_valid_canonical_number(self) -> bool:
        """True iff ``number`` is a well-formed canonical FC2 number."""
        return self.number is not None and is_valid_fc2_number(self.number)

    def has_non_empty_title(self) -> bool:
        """True iff ``title`` is set and not just whitespace."""
        return self.title is not None and self.title.strip() != ""

    def meets_minimum_success(self) -> bool:
        """The one frozen success condition for this Phase.

        ``minimum success = canonical FC2 number + non-empty title``.
        Every other field may be missing/partial without affecting this.
        """
        return self.has_valid_canonical_number() and self.has_non_empty_title()
