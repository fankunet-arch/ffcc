"""Pure candidate-image URL safety gate (P4-C5 contract section 8).

``validate_image_url(url)`` either returns the **same** exact ``str`` object it
was given, or raises :class:`~fc2_organizer.images.errors.ImageUrlError` carrying
only a :class:`~fc2_organizer.images.errors.UrlRejectionReason`.

URL safety judgement is **not** URL normalization: the validator never strips,
lower-cases, re-quotes, re-encodes, drops userinfo from, or otherwise rewrites
the URL, and it returns no ``urllib`` parse object for later code to carry
around. A URL that would need rewriting to be safe is rejected instead.

The very first operation is ``type(url) is str``. A ``str`` subclass (which could
override ``strip`` / ``encode`` / ``__eq__`` / ``__hash__`` / ``__repr__`` /
``__format__`` / ``__iter__`` / ...) is rejected before any of its methods can
run, and the rejection message never formats the value.

Scope limits (frozen): no DNS resolution is performed, so a public hostname
that resolves to a private / loopback address is **not** caught here. This
module does not claim to defend against DNS rebinding; the later transport
substep owns connection-time address policy.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from fc2_organizer.images.errors import ImageUrlError, UrlRejectionReason

__all__ = ["MAX_IMAGE_URL_LENGTH", "validate_image_url"]

MAX_IMAGE_URL_LENGTH = 4096

_ALLOWED_SCHEMES = frozenset({"http", "https"})
# A registered-name host after urlsplit's lower-casing: ASCII letters, digits,
# '-' and '_' in non-empty dot-separated labels, optionally one trailing dot.
# Rejects '%' (percent-encoded hosts are decoded by WHATWG parsers), non-ASCII
# (IDNA / NFKC mapping could turn e.g. full-width digits into an IP) and empty labels.
_REG_NAME = re.compile(r"[a-z0-9_-]+(?:\.[a-z0-9_-]+)*\.?", re.ASCII)
# A final label that a WHATWG / inet_aton parser would read as an IPv4 number
# ("127.1", "2130706433", "0x7f.1", "017.0.0.1"): only a strict dotted quad is accepted.
_NUMERIC_LABEL = re.compile(r"(?:0x[0-9a-f]*|[0-9]+)", re.ASCII)


def _is_global_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.is_site_local:
            return False
        embedded = [address.ipv4_mapped, address.sixtofour]
        if address.teredo is not None:
            embedded.extend(address.teredo)
        for inner in embedded:
            if inner is not None and not _is_global_address(inner):
                return False
    return True


def validate_image_url(url: object) -> str:
    """Return ``url`` unchanged if it is a safe absolute ``http``/``https`` image
    URL, else raise :class:`ImageUrlError` (reason only; never the URL)."""
    if type(url) is not str:
        raise ImageUrlError(UrlRejectionReason.NOT_EXACT_STR)
    if not url:
        raise ImageUrlError(UrlRejectionReason.EMPTY)
    if len(url) > MAX_IMAGE_URL_LENGTH:
        raise ImageUrlError(UrlRejectionReason.TOO_LONG)
    # urlsplit silently drops leading C0/space and embedded tab/CR/LF; reject
    # instead so the validated string is exactly the string later requested.
    for char in url:
        if char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F:
            raise ImageUrlError(UrlRejectionReason.WHITESPACE_OR_CONTROL)
    if "\\" in url:
        # WHATWG parsers treat '\' as '/' in http(s) URLs; urlsplit does not.
        raise ImageUrlError(UrlRejectionReason.BACKSLASH)

    try:
        parts = urlsplit(url)
    except ValueError:
        raise ImageUrlError(UrlRejectionReason.MALFORMED) from None

    if not parts.scheme:
        raise ImageUrlError(UrlRejectionReason.RELATIVE)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise ImageUrlError(UrlRejectionReason.UNSUPPORTED_SCHEME)
    if not parts.netloc:
        raise ImageUrlError(UrlRejectionReason.MISSING_HOST)
    if "@" in parts.netloc:
        raise ImageUrlError(UrlRejectionReason.USERINFO)
    try:
        port = parts.port
    except ValueError:
        raise ImageUrlError(UrlRejectionReason.INVALID_PORT) from None
    if port == 0:
        raise ImageUrlError(UrlRejectionReason.INVALID_PORT)
    host = parts.hostname
    if not host:
        raise ImageUrlError(UrlRejectionReason.MISSING_HOST)

    if "[" in parts.netloc or "]" in parts.netloc:
        # Bracketed IPv6 literal. Zone ids ('%') are link-local by definition.
        if "%" in host:
            raise ImageUrlError(UrlRejectionReason.NON_GLOBAL_IP)
        try:
            address = ipaddress.IPv6Address(host)
        except ValueError:
            raise ImageUrlError(UrlRejectionReason.INVALID_HOST) from None
        if not _is_global_address(address):
            raise ImageUrlError(UrlRejectionReason.NON_GLOBAL_IP)
        return url

    if _REG_NAME.fullmatch(host) is None:
        raise ImageUrlError(UrlRejectionReason.INVALID_HOST)
    bare = host[:-1] if host.endswith(".") else host
    if bare == "localhost" or bare.endswith(".localhost"):
        raise ImageUrlError(UrlRejectionReason.LOCALHOST)
    if _NUMERIC_LABEL.fullmatch(bare.rsplit(".", 1)[-1]) is not None:
        try:
            address4 = ipaddress.IPv4Address(bare)
        except ValueError:
            raise ImageUrlError(UrlRejectionReason.NUMERIC_HOST) from None
        if not _is_global_address(address4):
            raise ImageUrlError(UrlRejectionReason.NON_GLOBAL_IP)
    return url
