"""P4-C4: XML 1.0 character boundary, injection safety, hostile ``str`` subclasses,
forged shapes and the error taxonomy (contract sections 10-12, test matrix 43-70).
"""

from __future__ import annotations

from xml.dom import minidom

import pytest

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.nfo import (
    NfoError,
    NfoInputError,
    NfoMetadataError,
    NfoReleaseDateError,
    NfoXmlCharacterError,
    render_movie_nfo,
)
from fc2_organizer.publication import PublicationRecord

from ._builders import N, actors_of, child_texts, forge, make_plan, make_record, parse

# ---- 43-55: XML 1.0 character boundary ---------------------------------------------------------------------------------

ALLOWED = {
    "TAB": "\t",
    "LF": "\n",
    "CR": "\r",
    "U+0020": " ",
    "CJK": "日本語",
    "emoji": "🎬",
    "U+D7FF": "퟿",
    "U+E000": "",
    "U+FFFD": "�",
    "U+10000": "\U00010000",
    "U+10FFFF": "\U0010ffff",
}

ILLEGAL = {
    "U+0000": "\x00",
    "U+0001": "\x01",
    "U+0008": "\x08",
    "U+000B": "\x0b",
    "U+000C": "\x0c",
    "U+001F": "\x1f",
    "U+D800": "\ud800",
    "U+DFFF": "\udfff",
    "U+FFFE": "￾",
    "U+FFFF": "￿",
}


@pytest.mark.parametrize("label", list(ALLOWED))
def test_43_48_allowed_xml_characters_render_and_round_trip(label):
    title = f"a{ALLOWED[label]}b"
    xml = render_movie_nfo(make_record(title=title))
    xml.encode("utf-8", errors="strict")
    assert parse(xml).findtext("title") == title


@pytest.mark.parametrize("label", list(ILLEGAL))
def test_49_55_illegal_xml_characters_in_title_are_rejected_with_field_and_code_point(label):
    with pytest.raises(NfoXmlCharacterError) as info:
        render_movie_nfo(make_record(title=f"Secret title text {ILLEGAL[label]} tail"))
    message = str(info.value)
    assert "metadata.title" in message and label in message
    assert "Secret title text" not in message


def _field_with(field: str, value: str) -> dict:
    return {"actors": {"actors": ("ok", value)}, "tags": {"tags": ("ok", value)}}.get(field, {field: value})


@pytest.mark.parametrize("field, expected_name", [
    ("title", "metadata.title"),
    ("plot", "metadata.plot"),
    ("studio", "metadata.studio"),
    ("actors", "metadata.actors[1]"),
    ("tags", "metadata.tags[1]"),
])
@pytest.mark.parametrize("label", ["U+0000", "U+000B", "U+D800", "U+FFFF"])
def test_illegal_character_propagates_from_every_rendered_text_field(field, expected_name, label):
    with pytest.raises(NfoXmlCharacterError) as info:
        render_movie_nfo(make_record(**_field_with(field, f"x{ILLEGAL[label]}y")))
    assert expected_name in str(info.value) and label in str(info.value)


def test_illegal_character_in_release_is_rejected_not_rendered():
    with pytest.raises(NfoMetadataError):
        render_movie_nfo(make_record(release="2026-09-19\x00"))


def test_illegal_character_in_forged_number_is_rejected():
    record = make_record()
    object.__setattr__(record.plan, "canonical_number", "FC2-1\x00")
    with pytest.raises(NfoXmlCharacterError) as info:
        render_movie_nfo(record)
    assert "record.number" in str(info.value)


def test_illegal_character_is_never_dropped_or_replaced():
    with pytest.raises(NfoXmlCharacterError):
        render_movie_nfo(make_record(title="ok", plot="a\x00b"))


# ---- 66-70: injection ------------------------------------------------------------------------------------------------------

INJECTIONS = [
    "</title><evil>true</evil><title>",
    'A </title><evil>true</evil>',
    '<!DOCTYPE movie [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>',
    "&xxe;",
    "A & B < C > D",
    "]]>",
    "<![CDATA[<evil/>]]>",
    '<?xml version="1.0"?><movie>',
    "<!-- comment -->",
    '" type="evil" x="',
]


@pytest.mark.parametrize("payload", INJECTIONS)
@pytest.mark.parametrize("field", ["title", "plot", "studio", "actors", "tags"])
def test_66_70_injection_payloads_stay_plain_text_in_every_field(payload, field):
    fields = {"actors": {"actors": (payload,)}, "tags": {"tags": (payload,)}}.get(field, {field: payload})
    xml = render_movie_nfo(make_record(**fields))
    root = parse(xml)
    assert root.tag == "movie"
    assert root.find(".//evil") is None and root.find(".//title/title") is None
    assert len(root.findall("title")) == 1 and len(root.findall("uniqueid")) == 1
    # structure: only the frozen element names, and attributes only on uniqueid (constants)
    assert {el.tag for el in root.iter()} <= {"movie", "title", "uniqueid", "plot", "studio", "actor", "name",
                                              "order", "tag"}
    for el in root.iter():
        assert el.attrib == ({"type": "fc2", "default": "true"} if el.tag == "uniqueid" else {})
    recovered = {
        "title": root.findtext("title"),
        "plot": root.findtext("plot"),
        "studio": root.findtext("studio"),
        "actors": actors_of(root)[0][0] if actors_of(root) else None,
        "tags": child_texts(root, "tag")[0] if child_texts(root, "tag") else None,
    }[field]
    assert recovered == payload
    assert "<!DOCTYPE" not in xml and "<!ENTITY" not in xml and "<![CDATA[" not in xml and "<!--" not in xml
    assert xml.count("<?xml") == 1


def test_66_repro_b_title_injection_creates_no_element():
    title = "A </title><evil>true</evil>"
    root = parse(render_movie_nfo(make_record(title=title)))
    assert root.find(".//evil") is None and root.findtext("title") == title


def test_67_70_no_dtd_or_entity_is_present_in_the_document_structure():
    xml = render_movie_nfo(make_record(title='<!DOCTYPE movie [<!ENTITY xxe "boom">]>', plot="&xxe; &amp;xxe;"))
    dom = minidom.parseString(xml.encode("utf-8"))
    assert dom.doctype is None
    assert dom.documentElement.tagName == "movie"
    root = parse(xml)
    assert root.findtext("plot") == "&xxe; &amp;xxe;" and "boom" not in root.findtext("plot")


def test_69_metadata_cannot_create_or_alter_attributes():
    xml = render_movie_nfo(make_record(title='x" evil="1', tags=("' onload='x",)))
    for el in parse(xml).iter():
        assert set(el.attrib) <= {"type", "default"}
    assert parse(xml).find("uniqueid").attrib == {"type": "fc2", "default": "true"}


# ---- hostile str subclass ------------------------------------------------------------------------------------------------------

CALLS: list[str] = []


def _hook(name):
    def _record_and_raise(self, *args, **kwargs):
        CALLS.append(name)
        raise AssertionError(f"hostile hook {name} was called")

    return _record_and_raise


HOOKS = [
    "__str__", "__repr__", "__format__", "__eq__", "__ne__", "__hash__", "__len__", "__iter__", "__getitem__",
    "__contains__", "__add__", "__mod__", "__bool__", "replace", "strip", "lstrip", "rstrip", "encode", "translate",
    "split", "join", "format", "startswith", "endswith", "find", "isspace", "isdigit", "casefold", "lower",
]
HostileStr = type("HostileStr", (str,), {name: _hook(name) for name in HOOKS})


@pytest.fixture(autouse=True)
def _reset_calls():
    CALLS.clear()
    yield
    CALLS.clear()


@pytest.mark.parametrize("field", ["title", "plot", "release", "studio", "actors", "tags"])
def test_hostile_str_subclass_is_rejected_without_calling_any_hook(field):
    hostile = HostileStr("2026-09-19" if field == "release" else "Innocent looking text")
    value = (hostile,) if field in ("actors", "tags") else hostile
    record = forge(**{field: value})
    CALLS.clear()  # any hook run while *building* the fixture is irrelevant; only rendering counts
    with pytest.raises(NfoMetadataError) as info:
        render_movie_nfo(record)
    assert CALLS == []
    assert "HostileStr" in str(info.value) and "Innocent" not in str(info.value)
    assert type(info.value) is NfoMetadataError  # shape error, not a date/char error


def test_hostile_str_subclass_as_canonical_number_is_rejected_without_hooks():
    record = make_record()
    object.__setattr__(record.plan, "canonical_number", HostileStr(N))
    CALLS.clear()
    with pytest.raises(NfoMetadataError):
        render_movie_nfo(record)
    assert CALLS == []


def test_hostile_hooks_really_are_armed():
    """Positive control: the hostile class does trap the ordinary str operations."""
    hostile = HostileStr("x")
    for op in (lambda: hostile.strip(), lambda: hostile.translate({}), lambda: f"{hostile}",
               lambda: hostile.encode("utf-8"), lambda: hostile == "x", lambda: hash(hostile)):
        with pytest.raises(AssertionError):
            op()
    assert {"strip", "translate", "__format__", "encode", "__eq__", "__hash__"} <= set(CALLS)


# ---- 56-65: forged shapes ---------------------------------------------------------------------------------------------------------


class IntSubclass(int):
    pass


FORGED = [
    ("runtime", True),        # 56
    ("runtime", False),
    ("runtime", -1),          # 57
    ("runtime", "60"),        # 58
    ("runtime", 60.0),
    ("runtime", IntSubclass(60)),
    ("actors", ["Alice"]),    # 59
    ("actors", ("Alice", 1)),  # 60
    ("actors", ("Alice", None)),
    ("actors", None),
    ("actors", "Alice"),
    ("tags", ["t"]),          # 61
    ("tags", ("t", b"x")),    # 62
    ("tags", frozenset({"t"})),
    ("tags", ("t", None)),
    ("plot", 123),            # 63
    ("plot", b"bytes"),
    ("release", 20260919),    # 64
    ("studio", ["S"]),        # 65
    ("title", None),
    ("title", 1),
    ("title", "   "),
]


@pytest.mark.parametrize("field, value", FORGED, ids=[f"{f}={v!r}" for f, v in FORGED])
def test_56_65_forged_shapes_raise_typed_nfo_error_never_a_bare_exception(field, value):
    record = forge(**{field: value})
    with pytest.raises(NfoMetadataError) as info:
        render_movie_nfo(record)
    assert f"metadata.{field}" in str(info.value)
    assert info.value.__cause__ is None


def test_huge_runtime_beyond_int_str_digit_limit_is_a_typed_error():
    with pytest.raises(NfoMetadataError):
        render_movie_nfo(forge(runtime=10 ** 5000))


def test_metadata_missing_attribute_on_forged_object_is_a_typed_error():
    metadata = object.__new__(NormalizedMetadata)  # no slot set at all
    record = make_record()
    object.__setattr__(record, "metadata", metadata)
    with pytest.raises(NfoMetadataError) as info:
        render_movie_nfo(record)
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_record_with_unset_slots_is_a_typed_error():
    record = object.__new__(PublicationRecord)
    with pytest.raises(NfoMetadataError):
        render_movie_nfo(record)


def test_forged_record_whose_plan_is_not_a_plan_is_a_typed_error():
    record = make_record()
    object.__setattr__(record, "plan", object())
    with pytest.raises(NfoMetadataError):
        render_movie_nfo(record)


def test_forged_metadata_property_that_raises_is_wrapped():
    class Exploding:
        @property
        def title(self):
            raise RuntimeError("secret internal detail")

    record = make_record()
    object.__setattr__(record, "metadata", Exploding())
    with pytest.raises(NfoMetadataError) as info:
        render_movie_nfo(record)
    assert "secret internal detail" not in str(info.value)


# ---- input type -------------------------------------------------------------------------------------------------------------------


class RecordSubclass(PublicationRecord):
    __slots__ = ()


@pytest.mark.parametrize(
    "value",
    [None, "FC2-1234567", {"title": "x"}, 1, make_plan(), NormalizedMetadata(number=N, title="x")],
    ids=["None", "str", "dict", "int", "plan", "metadata"],
)
def test_non_publication_record_input_is_nfo_input_error(value):
    with pytest.raises(NfoInputError) as info:
        render_movie_nfo(value)
    assert isinstance(info.value, TypeError) and isinstance(info.value, NfoError)


def test_publication_record_subclass_is_rejected_exact_type_only():
    sub = RecordSubclass(plan=make_plan(), metadata=NormalizedMetadata(number=N, title="x"),
                         aggregate_status=AggregateStatus.SUCCESS)
    with pytest.raises(NfoInputError):
        render_movie_nfo(sub)


# ---- error taxonomy ---------------------------------------------------------------------------------------------------------------


def test_error_taxonomy_is_distinct_and_rooted_at_nfo_error():
    assert issubclass(NfoInputError, NfoError) and issubclass(NfoInputError, TypeError)
    assert issubclass(NfoMetadataError, NfoError) and issubclass(NfoMetadataError, ValueError)
    assert issubclass(NfoReleaseDateError, NfoMetadataError)
    assert issubclass(NfoXmlCharacterError, NfoMetadataError)
    assert not issubclass(NfoReleaseDateError, NfoXmlCharacterError)
    assert not issubclass(NfoXmlCharacterError, NfoReleaseDateError)
    assert not issubclass(NfoInputError, NfoMetadataError)


def test_each_failure_category_raises_its_own_class():
    cases = [
        (lambda: render_movie_nfo(None), NfoInputError),
        (lambda: render_movie_nfo(forge(actors=["a"])), NfoMetadataError),
        (lambda: render_movie_nfo(make_record(release="2026-02-30")), NfoReleaseDateError),
        (lambda: render_movie_nfo(make_record(title="a\x00")), NfoXmlCharacterError),
    ]
    for call, cls in cases:
        with pytest.raises(NfoError) as info:
            call()
        assert type(info.value) is cls


def test_error_messages_never_echo_long_plot_or_other_content():
    plot = "PLOT-SENTINEL " * 200 + "\x00"
    with pytest.raises(NfoXmlCharacterError) as info:
        render_movie_nfo(make_record(plot=plot, actors=("ACTOR-SENTINEL",), tags=("TAG-SENTINEL",)))
    message = str(info.value)
    assert "PLOT-SENTINEL" not in message and len(message) < 200
    with pytest.raises(NfoXmlCharacterError) as info:
        render_movie_nfo(make_record(actors=("ACTOR-SENTINEL\x01",)))
    assert "ACTOR-SENTINEL" not in str(info.value)
    with pytest.raises(NfoXmlCharacterError) as info:
        render_movie_nfo(make_record(tags=("TAG-SENTINEL\x01",)))
    assert "TAG-SENTINEL" not in str(info.value)
    with pytest.raises(NfoReleaseDateError) as info:
        render_movie_nfo(make_record(release="DATE-SENTINEL"))
    assert "DATE-SENTINEL" not in str(info.value)
