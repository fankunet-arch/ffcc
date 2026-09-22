"""P4-C5 substep 1: pure candidate-image URL safety gate (contract section 8)."""

from __future__ import annotations

import pytest

from fc2_organizer.images import (
    MAX_IMAGE_URL_LENGTH,
    ImageError,
    ImageFailureKind,
    ImageUrlError,
    UrlRejectionReason,
    validate_image_url,
)

R = UrlRejectionReason


def _reason(url: object) -> UrlRejectionReason:
    with pytest.raises(ImageUrlError) as info:
        validate_image_url(url)
    assert info.value.__cause__ is None
    return info.value.reason


# --- accepted ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.jpg",
        "https://example.com/a.jpg",
        "HTTPS://Example.COM/Path/A.JPG?x=1&y=%20#frag",
        "https://cdn.example.co.jp:8443/img/poster.jpg",
        "https://example.com./a.jpg",
        "https://img_cdn.example.com/a.jpg",
        "https://8.8.8.8/a.jpg",
        "https://1.1.1.1:443/a.jpg",
        "https://[2606:4700:4700::1111]/a.jpg",
        "https://example.com/%E6%B5%B7.jpg",
        "https://example.com/海.jpg",
    ],
)
def test_safe_http_and_https_urls_are_returned_as_the_same_object(url):
    assert validate_image_url(url) is url


def test_validator_does_not_normalize_or_strip_or_touch_query():
    url = "https://Example.com/A.jpg?Token=AbC&b=%2F"
    out = validate_image_url(url)
    assert out is url and out == "https://Example.com/A.jpg?Token=AbC&b=%2F"


# --- rejected: shape -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("", R.EMPTY),
        ("a.jpg", R.RELATIVE),
        ("/img/a.jpg", R.RELATIVE),
        ("//example.com/a.jpg", R.RELATIVE),
        ("example.com/a.jpg", R.RELATIVE),
        ("http:///a.jpg", R.MISSING_HOST),
        ("http:a.jpg", R.MISSING_HOST),
        ("https://:443/a.jpg", R.MISSING_HOST),
        (" https://example.com/a.jpg", R.WHITESPACE_OR_CONTROL),
        ("https://example.com/a.jpg ", R.WHITESPACE_OR_CONTROL),
        ("https://example.com/a b.jpg", R.WHITESPACE_OR_CONTROL),
        ("https://exam\tple.com/a.jpg", R.WHITESPACE_OR_CONTROL),
        ("https://example.com/a.jpg\n", R.WHITESPACE_OR_CONTROL),
        ("https://example.com/\x00.jpg", R.WHITESPACE_OR_CONTROL),
        ("https://example.com/\x7f.jpg", R.WHITESPACE_OR_CONTROL),
        ("https://example.com/\u3000.jpg", R.WHITESPACE_OR_CONTROL),
        ("https://example.com:99999/a.jpg", R.INVALID_PORT),
        ("https://example.com:0/a.jpg", R.INVALID_PORT),
        ("https://example.com:abc/a.jpg", R.INVALID_PORT),
        ("https://[not-an-ip]/a.jpg", R.MALFORMED),
        ("https://exa%6dple.com/a.jpg", R.INVALID_HOST),
        ("https://ex..ample.com/a.jpg", R.INVALID_HOST),
        ("https://例え.jp/a.jpg", R.INVALID_HOST),
        ("https://１２７.０.０.１/a.jpg", R.INVALID_HOST),
        ("https://" + "a" * MAX_IMAGE_URL_LENGTH + ".com/", R.TOO_LONG),
    ],
)
def test_invalid_urls_rejected_with_reason(url, reason):
    assert _reason(url) is reason


@pytest.mark.parametrize("value", [None, b"https://example.com/a.jpg", 1, ["https://example.com/a.jpg"]])
def test_non_str_rejected(value):
    assert _reason(value) is R.NOT_EXACT_STR


# --- rejected: unsafe ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "file://C:/Windows/win.ini",
        "data:image/jpeg;base64,/9j/4AAQ",
        "ftp://example.com/a.jpg",
        "javascript:alert(1)",
        "gopher://example.com/",
        "ws://example.com/a.jpg",
    ],
)
def test_non_http_schemes_rejected(url):
    assert _reason(url) is R.UNSUPPORTED_SCHEME


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pass@example.com/a.jpg",
        "https://user@example.com/a.jpg",
        "https://:pass@example.com/a.jpg",
        "https://example.com@127.0.0.1/a.jpg",
    ],
)
def test_userinfo_rejected(url):
    assert _reason(url) is R.USERINFO


def test_backslash_rejected():
    assert _reason("https://example.com\\@127.0.0.1/a.jpg") is R.BACKSLASH
    assert _reason("https://127.0.0.1\\.example.com/a.jpg") is R.BACKSLASH


@pytest.mark.parametrize(
    "url",
    ["http://localhost/a.jpg", "http://LOCALHOST:8080/a.jpg", "http://localhost./a.jpg", "http://a.localhost/a.jpg",
     "http://x.y.localhost/a.jpg"],
)
def test_localhost_rejected(url):
    assert _reason(url) is R.LOCALHOST


def test_localhost_lookalikes_are_ordinary_hostnames():
    assert validate_image_url("https://localhost.example.com/a.jpg")
    assert validate_image_url("https://notlocalhost/a.jpg")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/a.jpg",  # loopback
        "http://127.8.9.10/a.jpg",
        "http://[::1]/a.jpg",
        "http://10.0.0.1/a.jpg",  # private
        "http://172.16.0.1/a.jpg",
        "http://192.168.1.1/a.jpg",
        "http://[fd00::1]/a.jpg",
        "http://169.254.169.254/latest/meta-data",  # link-local / cloud metadata
        "http://[fe80::1]/a.jpg",
        "http://224.0.0.1/a.jpg",  # multicast (is_global is True on 3.12; still refused)
        "http://[ff02::1]/a.jpg",
        "http://240.0.0.1/a.jpg",  # reserved
        "http://255.255.255.255/a.jpg",
        "http://0.0.0.0/a.jpg",  # unspecified
        "http://[::]/a.jpg",
        "http://100.64.0.1/a.jpg",  # shared address space
        "http://192.0.2.1/a.jpg",  # documentation
        "http://[::ffff:127.0.0.1]/a.jpg",  # IPv4-mapped loopback
        "http://[::ffff:169.254.169.254]/a.jpg",
        "http://[2002:7f00:1::]/a.jpg",  # 6to4 wrapping 127.0.0.1
        "http://[64:ff9b::7f00:1]/a.jpg",  # NAT64 wrapping 127.0.0.1
        "http://127.0.0.1./a.jpg",  # trailing dot
    ],
)
def test_non_global_ip_literals_rejected(url):
    assert _reason(url) is R.NON_GLOBAL_IP


def test_ipv6_zone_id_rejected():
    assert _reason("http://[fe80::1%25eth0]/a.jpg") in (R.NON_GLOBAL_IP, R.MALFORMED)


@pytest.mark.parametrize(
    "url",
    [
        "http://2130706433/a.jpg",  # decimal 127.0.0.1
        "http://0x7f000001/a.jpg",
        "http://0x7f.0.0.1/a.jpg",
        "http://127.1/a.jpg",
        "http://017700000001/a.jpg",
        "http://0177.0.0.1/a.jpg",  # leading-zero (octal) quad
        "http://8.8.8.08/a.jpg",
        "http://example.123/a.jpg",
        "http://0/a.jpg",
    ],
)
def test_non_canonical_numeric_hosts_rejected(url):
    assert _reason(url) is R.NUMERIC_HOST


def test_failure_kind_mapping():
    assert ImageUrlError(R.RELATIVE).failure_kind is ImageFailureKind.INVALID_URL
    assert ImageUrlError(R.NOT_EXACT_STR).failure_kind is ImageFailureKind.INVALID_URL
    for reason in (R.UNSUPPORTED_SCHEME, R.USERINFO, R.LOCALHOST, R.NON_GLOBAL_IP, R.NUMERIC_HOST, R.BACKSLASH):
        assert ImageUrlError(reason).failure_kind is ImageFailureKind.UNSAFE_URL
    assert {ImageUrlError(r).failure_kind for r in R} == {ImageFailureKind.INVALID_URL, ImageFailureKind.UNSAFE_URL}


def test_url_error_is_typed_image_error():
    with pytest.raises(ImageError):
        validate_image_url("file:///x")
    assert issubclass(ImageUrlError, ValueError)


# --- error message leaks nothing -----------------------------------------------------------------

_SECRET = "SECRETTOKEN-7f3a9c"


@pytest.mark.parametrize(
    "url",
    [
        f"https://user:{_SECRET}@example.com/a.jpg?token={_SECRET}",
        f"http://127.0.0.1/a.jpg?sig={_SECRET}",
        f"http://localhost/{_SECRET}.jpg",
        f"ftp://example.com/a.jpg?token={_SECRET}",
        f"https://example.com/a.jpg?token={_SECRET} ",
        f"/relative/a.jpg?token={_SECRET}",
        f"https://example.com:99999/?token={_SECRET}",
        f"https://[zz]/?token={_SECRET}",
    ],
)
def test_url_error_message_contains_only_the_reason(url):
    with pytest.raises(ImageUrlError) as info:
        validate_image_url(url)
    error = info.value
    rendered = " ".join([str(error), repr(error), repr(error.args)])
    assert _SECRET not in rendered
    assert "example.com" not in rendered and "127.0.0.1" not in rendered and "token" not in rendered
    assert error.args == (f"image URL rejected: {error.reason.value}",)
    assert error.__cause__ is None
    assert error.__context__ is None or error.__suppress_context__
    assert not hasattr(error, "url")


# --- hostile str subclass ------------------------------------------------------------------------


class _Hostile(str):
    calls: list[str] = []

    def _hook(name):  # noqa: N805 - class-body helper
        def method(self, *args, **kwargs):
            _Hostile.calls.append(name)
            raise AssertionError(f"hostile hook {name} executed")

        return method

    for _name in (
        "strip", "lstrip", "rstrip", "lower", "upper", "casefold", "encode", "startswith", "endswith", "split",
        "rsplit", "partition", "find", "index", "replace", "isascii", "isspace", "__repr__", "__str__",
        "__format__", "__hash__", "__eq__", "__ne__", "__len__", "__iter__", "__getitem__", "__contains__",
        "__bool__", "__add__", "__mod__", "__fspath__", "__reduce__", "__reduce_ex__",
    ):
        locals()[_name] = _hook(_name)
    del _name, _hook


def test_hostile_str_subclass_rejected_before_any_hook_runs():
    hostile = _Hostile("https://example.com/a.jpg")
    _Hostile.calls.clear()
    with pytest.raises(ImageUrlError) as info:
        validate_image_url(hostile)
    assert info.value.reason is R.NOT_EXACT_STR
    assert info.value.failure_kind is ImageFailureKind.INVALID_URL
    assert _Hostile.calls == []
    str(info.value)
    assert _Hostile.calls == []
