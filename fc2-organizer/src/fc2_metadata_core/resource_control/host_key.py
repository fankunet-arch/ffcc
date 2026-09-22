"""Canonical host identity for the shared host limiter (Phase 3 C5).

A :class:`HostKey` is derived **only** from a configured, validated ``base_url`` -- never from a response
URL, redirect target, error text, trace, title or request body. Rules (frozen in
``docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md`` §3):

* host lower-cased, one trailing dot stripped; IP literals canonicalised by :mod:`ipaddress`;
* effective port = explicit port, else 80 (http) / 443 (https);
* the URL path is ignored, so two sources on one host share one key;
* userinfo, query, fragment and IPv6 zone ids are rejected.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from fc2_metadata_core.resource_control.errors import ResourceControlConfigError

__all__ = ["HostKey", "host_key_for_base_url"]

_DEFAULT_PORTS: Mapping[str, int] = MappingProxyType({"http": 80, "https": 443})
_MAX_HOST_CHARS = 253
_LABEL_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def _canonical_host(raw: object) -> str:
    if not isinstance(raw, str) or not raw:
        raise ResourceControlConfigError("host must be a non-empty str")
    if "%" in raw:
        raise ResourceControlConfigError("host must not carry an IPv6 zone id")
    host = raw.lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        host = host[:-1] if host.endswith(".") else host
        if (
            not host
            or len(host) > _MAX_HOST_CHARS
            or not all(_LABEL_RE.fullmatch(label) for label in host.split("."))
        ):
            raise ResourceControlConfigError("host is not a valid DNS name or IP literal") from None
        return host
    return str(address)


def _checked_port(port: object) -> int:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ResourceControlConfigError("port must be an int in 1..65535")
    return port


@dataclass(frozen=True, slots=True, order=True)
class HostKey:
    """A canonical ``(host, effective port)`` pair.

    Build it with :meth:`parse` or :func:`host_key_for_base_url`; direct construction insists on an
    already-canonical host (it never silently rewrites what it was given).
    """

    host: str
    port: int

    def __post_init__(self) -> None:
        if _canonical_host(self.host) != self.host:
            raise ResourceControlConfigError(f"host {self.host!r} is not in canonical form")
        _checked_port(self.port)

    def __str__(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{host}:{self.port}"

    @classmethod
    def parse(cls, text: object) -> "HostKey":
        """``"Example.COM:443"`` / ``"[::1]:8080"`` -> canonical key. The port is mandatory."""
        if not isinstance(text, str) or not text:
            raise ResourceControlConfigError("host key must be a non-empty 'host:port' str")
        if text.startswith("["):
            close = text.find("]")
            if close < 0 or text[close + 1 : close + 2] != ":":
                raise ResourceControlConfigError("an IPv6 host key must look like '[addr]:port'")
            host_text, port_text = text[1:close], text[close + 2 :]
            if ":" not in host_text:
                raise ResourceControlConfigError("brackets are only for IPv6 literals")
        else:
            host_text, sep, port_text = text.rpartition(":")
            if not sep or ":" in host_text:
                raise ResourceControlConfigError("host key must look like 'host:port' (IPv6 in brackets)")
        if not port_text.isascii() or not port_text.isdigit():
            raise ResourceControlConfigError("host key port must be decimal digits")
        return cls(_canonical_host(host_text), _checked_port(int(port_text)))


def host_key_for_base_url(base_url: object) -> HostKey:
    """The :class:`HostKey` of a configured ``http(s)`` base URL. Pure, offline."""
    if not isinstance(base_url, str) or not base_url:
        raise ResourceControlConfigError("base_url must be a non-empty str")
    try:
        parts = urlsplit(base_url)
        port = parts.port
        hostname = parts.hostname
    except ValueError as exc:
        raise ResourceControlConfigError(f"base_url is not a valid URL: {exc}") from None
    if parts.scheme not in _DEFAULT_PORTS:
        raise ResourceControlConfigError("base_url must be an absolute http:// or https:// URL")
    if not parts.netloc or not hostname:
        raise ResourceControlConfigError("base_url has no host")
    if "@" in parts.netloc:
        raise ResourceControlConfigError("base_url must not contain userinfo")
    if parts.query or parts.fragment or "?" in base_url or "#" in base_url:
        raise ResourceControlConfigError("base_url must not contain a query or fragment")
    return HostKey(_canonical_host(hostname), _checked_port(port if port is not None else _DEFAULT_PORTS[parts.scheme]))
