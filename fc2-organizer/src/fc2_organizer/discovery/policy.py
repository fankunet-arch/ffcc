"""``DiscoveryPolicy`` -- the single, centralized place that controls which
file extensions ``discover_media`` treats as media (contract section 9).

No extension list is ever hard-coded a second time anywhere else in this
package.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from fc2_organizer.discovery.errors import DiscoveryConfigError

__all__ = ["DiscoveryPolicy", "DEFAULT_SUPPORTED_EXTENSIONS"]

# Common, reasonably safe default video container extensions. Chosen for
# breadth over precision (better to include a rare container than to make a
# user's real media invisible to discovery); see
# ``docs/specifications/PHASE4_DISCOVERY_CONTRACT.md`` section 5 for the
# rationale and how to override it via ``DiscoveryPolicy``.
DEFAULT_SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".ts",
)


def _normalize_extensions(raw: Iterable[str]) -> frozenset[str]:
    if isinstance(raw, (str, bytes)):
        raise DiscoveryConfigError(
            "DiscoveryPolicy.supported_extensions must be an iterable of "
            f"extension strings, not a bare {type(raw).__name__}"
        )
    normalized: set[str] = set()
    for entry in raw:
        if not isinstance(entry, str):
            raise DiscoveryConfigError(
                f"DiscoveryPolicy.supported_extensions entry must be str, got {type(entry).__name__}"
            )
        candidate = entry.strip().lower()
        if len(candidate) < 2 or not candidate.startswith("."):
            raise DiscoveryConfigError(
                f"DiscoveryPolicy.supported_extensions entry must look like '.ext', got {entry!r}"
            )
        normalized.add(candidate)
    return frozenset(normalized)


@dataclass(frozen=True, slots=True)
class DiscoveryPolicy:
    """Immutable, validated configuration for ``discover_media``.

    ``supported_extensions`` is matched case-insensitively (``VIDEO.MP4`` and
    ``video.mp4`` are equivalent) -- entries are normalized to lowercase,
    dot-prefixed strings at construction time. Symlink/junction traversal
    safety (section 11) is a fixed, non-configurable invariant of this
    package's v1.0 contract, not a policy knob: it is not exposed here.
    """

    supported_extensions: frozenset[str] = field(default_factory=lambda: frozenset(DEFAULT_SUPPORTED_EXTENSIONS))

    def __post_init__(self) -> None:
        normalized = _normalize_extensions(self.supported_extensions)
        if not normalized:
            raise DiscoveryConfigError("DiscoveryPolicy.supported_extensions must not be empty")
        object.__setattr__(self, "supported_extensions", normalized)

    def is_supported_extension(self, extension: str) -> bool:
        """``extension`` must already be lowercase and dot-prefixed (the
        shape ``scanner.py`` derives from a filename); this does not
        re-normalize its argument."""
        return extension in self.supported_extensions
