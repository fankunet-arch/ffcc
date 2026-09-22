"""Host identity (contract §3): canonical, derived only from the configured base URL."""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.resource_control import HostKey, ResourceControlConfigError, host_key_for_base_url


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.com", ("example.com", 443)),
        ("https://example.com/", ("example.com", 443)),
        ("https://example.com:8443", ("example.com", 8443)),
        ("http://example.com", ("example.com", 80)),
        ("http://example.com:8080/prefix/x", ("example.com", 8080)),
        ("https://example.com:443", ("example.com", 443)),  # explicit default port == implicit
        ("http://example.com:80", ("example.com", 80)),
        ("https://EXAMPLE.Com", ("example.com", 443)),  # case-insensitive
        ("https://example.com.", ("example.com", 443)),  # one trailing dot
        ("https://sub.example.co.jp/a/b/c", ("sub.example.co.jp", 443)),
        ("https://xn--bcher-kva.example", ("xn--bcher-kva.example", 443)),
        ("http://127.0.0.1:8080", ("127.0.0.1", 8080)),
        ("https://[::1]", ("::1", 443)),
        ("https://[0:0:0:0:0:0:0:1]:8443", ("::1", 8443)),
        ("https://[2001:DB8::1]/x", ("2001:db8::1", 443)),
    ],
)
def test_canonical_host_and_effective_port(url, expected):
    key = host_key_for_base_url(url)
    assert (key.host, key.port) == expected


def test_different_paths_share_one_key():
    assert host_key_for_base_url("https://same.example/a") == host_key_for_base_url("https://same.example/b")
    assert hash(host_key_for_base_url("https://same.example/a")) == hash(host_key_for_base_url("https://same.example/b/c"))


def test_scheme_or_port_or_host_changes_the_key():
    base = host_key_for_base_url("https://example.com")
    assert host_key_for_base_url("http://example.com") != base
    assert host_key_for_base_url("https://example.com:8443") != base
    assert host_key_for_base_url("https://example.org") != base
    assert host_key_for_base_url("https://www.example.com") != base  # no implicit "www." folding


def test_ipv6_is_deterministic_and_printed_in_brackets():
    a = host_key_for_base_url("https://[2001:db8:0:0:0:0:0:1]:9443")
    b = host_key_for_base_url("https://[2001:DB8::1]:9443")
    assert a == b
    assert str(a) == "[2001:db8::1]:9443"
    assert str(host_key_for_base_url("https://example.com")) == "example.com:443"


@pytest.mark.parametrize(
    "bad",
    [
        None,
        42,
        b"https://x.example",
        "",
        "example.com",  # no scheme
        "//example.com",
        "https://",
        "ftp://example.com",
        "https://user:pw@example.com",
        "https://example.com?x=1",
        "https://example.com#frag",
        "https://example.com:0",
        "https://example.com:65536",
        "https://example.com:abc",
        "https://[fe80::1%25eth0]",  # zone id
        "https://exa mple.com",
        "https://-bad.example",
        "https://bad_.example",
        "https://a..b.example",
    ],
)
def test_malformed_base_urls_fail_before_any_network(bad):
    with pytest.raises(ResourceControlConfigError):
        host_key_for_base_url(bad)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Example.COM:443", ("example.com", 443)),
        ("example.com:8443", ("example.com", 8443)),
        ("[::1]:8080", ("::1", 8080)),
        ("[2001:DB8:0:0:0:0:0:1]:443", ("2001:db8::1", 443)),
        ("127.0.0.1:80", ("127.0.0.1", 80)),
        ("example.com.:443", ("example.com", 443)),
    ],
)
def test_parse_round_trips_to_the_same_key(text, expected):
    key = HostKey.parse(text)
    assert (key.host, key.port) == expected
    assert HostKey.parse(str(key)) == key


@pytest.mark.parametrize(
    "bad",
    ["", None, 5, "example.com", "example.com:", ":443", "example.com:44x", "example.com:0", "example.com:99999",
     "::1:443", "[::1]", "[::1]443", "[example.com]:443", "[::1:443", "a:b:443", "example.com:٤٤٣", "example.com:+443"],
)
def test_parse_rejects_malformed_keys(bad):
    with pytest.raises(ResourceControlConfigError):
        HostKey.parse(bad)


def test_direct_construction_demands_canonical_form_and_never_rewrites():
    assert HostKey("example.com", 443).host == "example.com"
    for host in ("Example.com", "example.com.", "0:0:0:0:0:0:0:1", ""):
        with pytest.raises(ResourceControlConfigError):
            HostKey(host, 443)
    for port in (0, 65536, True, "443", None):
        with pytest.raises(ResourceControlConfigError):
            HostKey("example.com", port)  # type: ignore[arg-type]


def test_host_key_is_immutable_hashable_and_ordered():
    key = HostKey("a.example", 443)
    with pytest.raises(dataclasses.FrozenInstanceError):
        key.host = "b.example"  # type: ignore[misc]
    assert {key: 1}[HostKey("a.example", 443)] == 1
    assert sorted([HostKey("b.example", 80), HostKey("a.example", 443), HostKey("a.example", 80)]) == [
        HostKey("a.example", 80),
        HostKey("a.example", 443),
        HostKey("b.example", 80),
    ]
