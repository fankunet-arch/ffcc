"""Unit tests for FC2 number normalization (NORM-01).

Covers Phase 1 requirements:
- positive dirty-filename regression set (spec section 10), including the
  two forms Phase 0 reviewer note F-03 explicitly requires closed here:
  `[广告]FC2PPV-1234567` and `xxx@FC2PPV-1234567`.
- negative misidentification regression set (spec section 11): the parser
  must not treat arbitrary digits, other studios' codes, dates, resolutions,
  or "FC2" glued into an unrelated word as a valid FC2 number.
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.normalize import (
    FC2RecognitionStatus,
    is_valid_fc2_number,
    normalize_fc2_number,
)

POSITIVE_CASES = [
    ("FC2-PPV-1234567", "FC2-1234567"),
    ("FC2PPV-1234567", "FC2-1234567"),
    ("FC2PPV1234567", "FC2-1234567"),
    ("FC2-1234567", "FC2-1234567"),
    ("FC2_1234567", "FC2-1234567"),
    ("[广告]FC2PPV-1234567", "FC2-1234567"),
    ("xxx@FC2PPV-1234567", "FC2-1234567"),
    ("FC2-PPV-1234567.mp4", "FC2-1234567"),
    ("[中文字幕]FC2-PPV-1234567-CD1.mkv", "FC2-1234567"),
    ("some.download.site_FC2PPV-1234567_1080p.mp4", "FC2-1234567"),
    ("fc2-1234567", "FC2-1234567"),
    ("  FC2-1234567  ", "FC2-1234567"),
    ("(FC2--1234567)", "FC2-1234567"),
    ("FC2-4825061", "FC2-4825061"),
]


@pytest.mark.parametrize("raw, expected_canonical", POSITIVE_CASES)
def test_positive_dirty_filenames_normalize_to_canonical(raw, expected_canonical):
    result = normalize_fc2_number(raw)
    assert result.status is FC2RecognitionStatus.RECOGNIZED
    assert result.recognized is True
    assert result.canonical == expected_canonical
    assert result.raw_input == raw
    assert is_valid_fc2_number(result.canonical) is True


def test_f03_regression_ad_prefix_noise_closed():
    """Phase 0 reviewer F-03: `[广告]FC2PPV-1234567` must be closed by our
    own automated regression, not just documented as manually verified."""
    result = normalize_fc2_number("[广告]FC2PPV-1234567")
    assert result.recognized is True
    assert result.canonical == "FC2-1234567"


def test_f03_regression_xxx_at_prefix_noise_closed():
    """Phase 0 reviewer F-03: `xxx@FC2PPV-1234567` must be closed by our own
    automated regression, not just documented as manually verified."""
    result = normalize_fc2_number("xxx@FC2PPV-1234567")
    assert result.recognized is True
    assert result.canonical == "FC2-1234567"


NEGATIVE_CASES = [
    "1234567.mp4",  # pure numeric filename, no FC2 token at all
    "SSNI-999.mp4",  # another studio's code
    "2024-01-15.mp4",  # a date, not a number
    "1920x1080.mkv",  # a resolution
    "Movie.Title.CD1.mp4",  # CD marker with no FC2 anywhere
    "Movie.Title.CD2.mkv",
    "readme.txt",  # plain text, unrelated
    "FC2.mp4",  # "FC2" with no digits at all
    "FC2 configuration notes.txt",  # "FC2" keyword, no digits nearby
    "FC2-12.mp4",  # digit run too short (2 < 5)
    "FC2-1234.mp4",  # digit run too short (4 < 5)
    "FC2-123456789012345.mp4",  # digit run absurdly long (glued blob)
    "SUPERFC2-4825061.mp4",  # "FC2" glued to a preceding letter
    "PERFC2PPV1234567.mp4",  # "FC2" glued to a preceding letter, with PPV
    "FC2-1234567EXTRA.mp4",  # digits glued to a following letter
    "FC2-1234567890123.mp4",  # digits glued to more digits (too long overall)
    "20240115_1234567890123.mp4",  # long unrelated digit blob, no FC2 token
    "Amane-Release-v0.15.0-build.zip",  # contains version numbers, no FC2 token
    "",  # empty string
    "just a plain filename without any code.mkv",
]


@pytest.mark.parametrize("raw", NEGATIVE_CASES)
def test_negative_misidentification_regression(raw):
    result = normalize_fc2_number(raw)
    assert result.status is FC2RecognitionStatus.NOT_FC2
    assert result.recognized is False
    assert result.canonical is None
    assert result.raw_input == raw


def test_not_fc2_result_preserves_raw_input_verbatim():
    raw = "totally unrelated file name (not fc2 at all).mkv"
    result = normalize_fc2_number(raw)
    assert result.raw_input == raw


def test_normalize_fc2_number_rejects_non_string_input():
    with pytest.raises(TypeError):
        normalize_fc2_number(1234567)  # type: ignore[arg-type]


class TestIsValidFc2Number:
    def test_accepts_well_formed_canonical_numbers(self):
        assert is_valid_fc2_number("FC2-1234567") is True
        assert is_valid_fc2_number("FC2-12345") is True
        assert is_valid_fc2_number("FC2-12345678") is True

    def test_rejects_malformed_or_non_canonical_strings(self):
        assert is_valid_fc2_number("FC2-12") is False  # too short
        assert is_valid_fc2_number("FC2-123456789") is False  # too long
        assert is_valid_fc2_number("FC21234567") is False  # missing dash
        assert is_valid_fc2_number("fc2-1234567") is False  # wrong case
        assert is_valid_fc2_number("FC2-1234567 ") is False  # trailing noise
        assert is_valid_fc2_number(" FC2-1234567") is False  # leading noise
        assert is_valid_fc2_number("SSNI-999") is False

    def test_rejects_non_string_values(self):
        assert is_valid_fc2_number(1234567) is False
        assert is_valid_fc2_number(None) is False
