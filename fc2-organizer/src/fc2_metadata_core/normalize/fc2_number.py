"""FC2 canonical number grammar and validation (NORM-01).

Phase 0 finding F-02 / MEDIUM note: Amane's ``parse_file_info(path=...)`` is a
path-mode parser with a mandatory fallback (``_fallback()``) that always
returns a non-``None`` number for a real filesystem path, even when nothing
FC2-shaped was actually found (worst case: a sanitized copy of the original
text tagged ``ContentType.WESTERN``). That fallback exists to satisfy
Amane's own "every scanned file must become *some* library entry" contract,
which is a different job from ours.

**Hard invariant for this module:** the FC2 Metadata Core decides on its own,
from its own grammar, whether a string is a valid FC2 number. It never
delegates that decision to Amane's fallback, and it never fabricates a
canonical number to paper over an unrecognized input. Every call to
``normalize_fc2_number`` returns an explicit, inspectable verdict:
``FC2RecognitionStatus.RECOGNIZED`` with a canonical string, or
``FC2RecognitionStatus.NOT_FC2`` with ``canonical=None``. There is no third,
implicit "guessed" outcome.

Canonical FC2 number grammar
-----------------------------
Accepted input shape (case-insensitive, anywhere inside a larger dirty
string such as a filename)::

    FC2 [-_]* (PPV [-_]*)? DIGITS

- ``FC2`` and the optional ``PPV`` literal may be joined by zero or more
  ``-``/``_`` separators, or none at all. This covers ``FC2-PPV-1234567``,
  ``FC2PPV-1234567``, ``FC2PPV1234567``, ``FC2-1234567`` and
  ``FC2_1234567``.
- ``DIGITS`` must be a contiguous run of 5 to 8 **ASCII** digits ``[0-9]``
  (Unicode digits such as fullwidth or Arabic-Indic ones are not FC2 digits;
  C0-01) (``_MIN_DIGITS`` /
  ``_MAX_DIGITS`` below). FC2 PPV numbers in circulation today are 6-7
  digits; the 5-8 window gives headroom for growth while still rejecting
  implausible digit blobs (dates glued together, resolutions, hashes) that
  would otherwise be misread as a valid number. This window is a Phase 1
  design decision, not an upstream fact, and may be revisited by a later
  phase with evidence.
- The match must not be glued to surrounding word characters: the
  character immediately before ``FC2`` (if any) and the character
  immediately after the digit run (if any) must not be ``[A-Za-z0-9]``.
  This is what allows arbitrary noise (``[广告]``, ``xxx@``, brackets,
  whitespace, other studio-style prefixes, file extensions, ``-CD1``
  suffixes, ...) to surround the token while rejecting cases where "FC2"
  is merely a substring embedded inside an unrelated word or where the
  digit run bleeds into trailing letters/digits that are not part of the
  number.
- Everything else in the input string is ignored (prefix/suffix noise is
  not stripped explicitly; the grammar simply never matches it).

Anything that does not match this grammar is ``NOT_FC2`` /
``UNRECOGNIZED`` -- including bare "FC2" with no digits, digit runs outside
the 5-8 window, and "FC2" glued to other letters/digits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "FC2RecognitionStatus",
    "FC2NumberResult",
    "normalize_fc2_number",
    "is_valid_fc2_number",
    "MIN_FC2_DIGITS",
    "MAX_FC2_DIGITS",
    "CANONICAL_FC2_PATTERN",
]

MIN_FC2_DIGITS = 5
MAX_FC2_DIGITS = 8

# Digits are ASCII ``[0-9]`` everywhere in this module, deliberately *not*
# ``\d``: in Python 3 ``str`` patterns ``\d`` matches every Unicode decimal
# digit (fullwidth ``１２３``, Arabic-Indic ``٤٨٢``, ...). Those are not FC2
# numbers, and one that slipped through as "canonical" would be interpolated
# into a request URL by a source adapter. The ``(?<!\d)`` / ``(?!\d)``
# guards below are the one place ``\d`` is used on purpose: a digit run that
# is glued to a *non-ASCII* digit is not a clean token either, so it is
# refused rather than silently truncated at the ASCII part.
_FC2_TOKEN_PATTERN = (
    r"(?<![A-Za-z0-9])(?<!\d)"
    r"FC2[-_]*(?:PPV[-_]*)?"
    rf"([0-9]{{{MIN_FC2_DIGITS},{MAX_FC2_DIGITS}}})"
    r"(?![A-Za-z0-9])(?!\d)"
)
_FC2_TOKEN_RE = re.compile(_FC2_TOKEN_PATTERN, re.IGNORECASE)

# Anchored with ``\A``/``\Z``, never ``^``/``$``: ``$`` also matches just
# before a trailing newline, so ``"FC2-1234567"`` plus a newline used to
# count as canonical.
CANONICAL_FC2_PATTERN = rf"\AFC2-[0-9]{{{MIN_FC2_DIGITS},{MAX_FC2_DIGITS}}}\Z"
_CANONICAL_FC2_RE = re.compile(CANONICAL_FC2_PATTERN)


class FC2RecognitionStatus(Enum):
    """Explicit, non-fabricated recognition verdict for a raw input string."""

    RECOGNIZED = "recognized"
    NOT_FC2 = "not_fc2"


@dataclass(frozen=True, slots=True)
class FC2NumberResult:
    """Result of attempting to recognize an FC2 number inside a raw string.

    ``canonical`` is ``None`` if and only if ``status`` is ``NOT_FC2``: there
    is no fallback number, guessed or otherwise.
    """

    status: FC2RecognitionStatus
    canonical: str | None
    raw_input: str

    def __post_init__(self) -> None:
        is_recognized = self.status is FC2RecognitionStatus.RECOGNIZED
        has_canonical = self.canonical is not None
        if is_recognized != has_canonical:
            raise ValueError(
                "FC2NumberResult.canonical must be set if and only if "
                "status is RECOGNIZED"
            )
        if is_recognized and not is_valid_fc2_number(self.canonical):
            raise ValueError(
                f"FC2NumberResult.canonical={self.canonical!r} is not a "
                "well-formed canonical FC2 number"
            )

    @property
    def recognized(self) -> bool:
        return self.status is FC2RecognitionStatus.RECOGNIZED


def normalize_fc2_number(text: str) -> FC2NumberResult:
    """Attempt to recognize and canonicalize an FC2 number inside ``text``.

    This never raises for "unrecognizable" input and never fabricates a
    number: unrecognized input yields ``FC2RecognitionStatus.NOT_FC2`` with
    ``canonical=None``.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text)!r}")

    match = _FC2_TOKEN_RE.search(text)
    if match is None:
        return FC2NumberResult(
            status=FC2RecognitionStatus.NOT_FC2, canonical=None, raw_input=text
        )

    digits = match.group(1)
    canonical = f"FC2-{digits}"
    return FC2NumberResult(
        status=FC2RecognitionStatus.RECOGNIZED, canonical=canonical, raw_input=text
    )


def is_valid_fc2_number(value: object) -> bool:
    """Return True iff ``value`` is already a well-formed canonical FC2 number.

    A canonical number is exactly ``FC2-`` followed by 5 to 8 digits
    (``FC2-1234567``). This is the check ``NormalizedMetadata`` uses to
    decide whether its ``number`` field satisfies the minimum-success
    condition; it does not attempt to extract a number from noisy text (use
    ``normalize_fc2_number`` for that).
    """
    if not isinstance(value, str):
        return False
    return _CANONICAL_FC2_RE.fullmatch(value) is not None
