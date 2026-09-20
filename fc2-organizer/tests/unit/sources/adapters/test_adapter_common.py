"""Provider-agnostic helpers shared by every real-site adapter."""

from __future__ import annotations

import pytest

from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters._common import (
    classify_page_response,
    clean_text,
    duration_to_minutes,
    unique_in_order,
    with_field_sources,
)

from support.fake_http_client import make_response
from support.source_fixtures import load_fixture


@pytest.mark.parametrize(
    "text, expected",
    [
        ("55:23", 55),
        ("39:05", 39),
        ("1:02:03", 62),
        ("0:59", 0),
        (" 48:05 ", 48),
        ("", None),
        (None, None),
        ("abc", None),
        ("12", None),
        ("12:5", None),
    ],
)
def test_duration_to_minutes(text, expected):
    assert duration_to_minutes(text) == expected


def test_clean_text_strips_tags_decodes_entities_collapses_whitespace():
    assert clean_text("  <b>A&amp;B</b>\n  &#039;x&#039;  ") == "A&B 'x'"


def test_unique_in_order_drops_blanks_and_dupes():
    assert unique_in_order(["a", "", "b", "a", "c"]) == ("a", "b", "c")


def test_with_field_sources_only_attributes_populated_fields():
    md = with_field_sources("src", number="FC2-1234567", title="T", release=None, actors=(), tags=("x",))
    assert set(md.field_sources) == {"number", "title", "tags"}
    assert md.field_sources["tags"] == ("src",)
    assert md.meets_minimum_success()


def _classify(**kw):
    return classify_page_response("s", "FC2-1234567", make_response(**kw))


def test_normal_200_page_is_not_a_failure():
    assert _classify(status_code=200, text="<html><title>Real</title></html>") is None


@pytest.mark.parametrize(
    "status, expected",
    [
        (404, SourceStatus.NOT_FOUND),
        (403, SourceStatus.BLOCKED),
        (429, SourceStatus.RATE_LIMITED),
        (500, SourceStatus.INVALID_RESPONSE),
        (503, SourceStatus.INVALID_RESPONSE),
        (301, SourceStatus.INVALID_RESPONSE),
    ],
)
def test_status_mapping(status, expected):
    result = _classify(status_code=status)
    assert result is not None and result.status is expected
    assert result.metadata is None and result.error_detail


def test_cf_mitigated_header_is_blocked_even_with_200():
    result = _classify(status_code=200, headers={"CF-Mitigated": "challenge"}, text="x")
    assert result is not None and result.status is SourceStatus.BLOCKED


def test_real_cloudflare_challenge_body_is_blocked():
    result = _classify(status_code=200, text=load_fixture("common/cloudflare_challenge.html"))
    assert result is not None and result.status is SourceStatus.BLOCKED


def test_challenge_phrase_deep_in_body_is_not_misread_as_blocked():
    body = "<html><head><title>Real work</title></head><body>" + ("x" * 5000) + "Just a moment...</body></html>"
    assert _classify(status_code=200, text=body) is None


def test_blocked_url_marker_wins_over_200():
    response = make_response(status_code=200, url="https://example.invalid/login?next=/x", text="ok")
    result = classify_page_response("s", "FC2-1234567", response, blocked_url_markers=("/login",))
    assert result is not None and result.status is SourceStatus.BLOCKED
