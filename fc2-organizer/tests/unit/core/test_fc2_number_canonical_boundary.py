"""C0-01: the canonical FC2 grammar is strictly ASCII and fully anchored.

Phase 2 independent review (P2-R-01): the old ``^FC2-\\d{5,8}$`` accepted a
trailing newline (``$`` also matches just before one) and every Unicode
decimal digit (``\\d`` in a ``str`` pattern). ``"FC2-1234567\\n"`` then passed
``require_canonical_number`` and reached the request layer, where httpx raised
a bare ``InvalidURL``. The frozen grammar is ``FC2-[0-9]{5,8}``, full-string.

Escapes below are spelled out (``\\n``, ``\\uff11`` ...) so no invisible or
look-alike character is hidden in this file.
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.normalize import is_valid_fc2_number, normalize_fc2_number

FULLWIDTH = "１２３４５６７"  # fullwidth 1234567
ARABIC_INDIC = "٤٨٢٤٦٠٥"  # 4824605

NOT_CANONICAL = [
    "FC2-1234567\n",  # trailing newline: ``$`` used to allow it
    "FC2-1234567\r\n",
    "\nFC2-1234567",
    "FC2-1234567\x00",
    "FC2-" + FULLWIDTH,
    "FC2-" + ARABIC_INDIC,
    "FC2-1234٥",  # ASCII digits plus one non-ASCII digit
    "FC2-1234567XYZ",
    "XFC2-1234567",
    "FC2-1234567 ",
    " FC2-1234567",
]


@pytest.mark.parametrize("value", NOT_CANONICAL, ids=[ascii(v) for v in NOT_CANONICAL])
def test_is_valid_fc2_number_rejects_non_canonical(value):
    assert is_valid_fc2_number(value) is False


@pytest.mark.parametrize("value", NOT_CANONICAL, ids=[ascii(v) for v in NOT_CANONICAL])
def test_normalize_never_returns_a_non_canonical_canonical(value):
    result = normalize_fc2_number(value)
    if result.recognized:
        # e.g. "FC2-1234567\n" *contains* a clean token; whatever comes back
        # must itself satisfy the canonical grammar (ASCII, anchored).
        assert is_valid_fc2_number(result.canonical) is True
        assert result.canonical.isascii()


@pytest.mark.parametrize(
    "value",
    ["FC2-" + FULLWIDTH, "FC2-" + ARABIC_INDIC, "FC2PPV-1234567１", "１FC2-1234567"],
)
def test_normalize_does_not_recognize_unicode_digit_runs(value):
    result = normalize_fc2_number(value)
    assert result.recognized is False and result.canonical is None


def test_is_valid_and_normalize_agree_on_ascii_digit_semantics():
    for digits in ("12345", "1234567", "12345678"):
        canonical = f"FC2-{digits}"
        assert is_valid_fc2_number(canonical) is True
        assert normalize_fc2_number(canonical).canonical == canonical
    for digits in ("1234", "123456789"):
        canonical = f"FC2-{digits}"
        assert is_valid_fc2_number(canonical) is False
        assert normalize_fc2_number(canonical).recognized is False


def test_glued_cjk_noise_is_still_a_valid_token():
    # dirty filenames routinely glue CJK text to the number; that must keep working
    raw = "[广告]FC2PPV-1234567高画質.mp4"
    assert normalize_fc2_number(raw).canonical == "FC2-1234567"


@pytest.mark.parametrize("value", NOT_CANONICAL[:7])
def test_metadata_does_not_accept_non_canonical_number_as_minimum_success(value):
    metadata = NormalizedMetadata(number=value, title="A title")
    assert metadata.has_valid_canonical_number() is False
    assert metadata.meets_minimum_success() is False


def test_valid_canonical_still_passes():
    assert is_valid_fc2_number("FC2-4825061") is True
    assert NormalizedMetadata(number="FC2-4825061", title="t").meets_minimum_success() is True
