"""Contract tests for ``fc2_organizer.planning.policy.OutputPolicy``."""

from __future__ import annotations

import dataclasses

import pytest

from fc2_organizer.planning.errors import InvalidOutputPolicyError
from fc2_organizer.planning.policy import (
    DEFAULT_EXTRAFANART_DIRNAME,
    DEFAULT_FANART_FILENAME,
    DEFAULT_NFO_EXTENSION,
    DEFAULT_POSTER_FILENAME,
    DEFAULT_THUMB_FILENAME,
    OutputPolicy,
)


def test_default_policy_matches_frozen_v1_layout():
    policy = OutputPolicy()
    assert policy.nfo_extension == DEFAULT_NFO_EXTENSION == ".nfo"
    assert policy.poster_filename == DEFAULT_POSTER_FILENAME == "poster.jpg"
    assert policy.fanart_filename == DEFAULT_FANART_FILENAME == "fanart.jpg"
    assert policy.thumb_filename == DEFAULT_THUMB_FILENAME == "thumb.jpg"
    assert policy.extrafanart_dirname == DEFAULT_EXTRAFANART_DIRNAME == "extrafanart"


def test_custom_artifact_filenames_accepted():
    policy = OutputPolicy(poster_filename="cover.jpg", fanart_filename="backdrop.jpg")
    assert policy.poster_filename == "cover.jpg"
    assert policy.fanart_filename == "backdrop.jpg"


@pytest.mark.parametrize(
    "field_name",
    ["nfo_extension", "poster_filename", "fanart_filename", "thumb_filename", "extrafanart_dirname"],
)
def test_empty_field_rejected(field_name):
    with pytest.raises(InvalidOutputPolicyError):
        OutputPolicy(**{field_name: ""})


@pytest.mark.parametrize(
    "field_name",
    ["nfo_extension", "poster_filename", "fanart_filename", "thumb_filename", "extrafanart_dirname"],
)
def test_non_str_field_rejected(field_name):
    with pytest.raises(InvalidOutputPolicyError):
        OutputPolicy(**{field_name: 123})


def test_nfo_extension_without_leading_dot_rejected():
    with pytest.raises(InvalidOutputPolicyError):
        OutputPolicy(nfo_extension="nfo")


def test_policy_is_frozen():
    policy = OutputPolicy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.poster_filename = "x.jpg"  # type: ignore[misc]


def test_policy_equality_is_value_based():
    assert OutputPolicy() == OutputPolicy()
    assert OutputPolicy(poster_filename="a.jpg") != OutputPolicy(poster_filename="b.jpg")
