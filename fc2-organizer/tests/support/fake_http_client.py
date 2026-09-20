"""A fully offline ``SourceHttpClient`` test double.

Adapters must be usable with a production transport or a fake offline
transport interchangeably, with zero monkeypatching (Phase 2 requirement).
This is that fake: register a canned response (or an exception to raise)
per exact URL, then hand an instance to an adapter's ``fetch`` exactly as
production code would hand it a real transport.
"""

from __future__ import annotations

from typing import Mapping

from fc2_metadata_core.http.client import HttpResponse

__all__ = ["FakeHttpClient", "make_response"]


def make_response(
    *,
    status_code: int = 200,
    url: str = "https://example.invalid/",
    text: str = "",
    headers: Mapping[str, str] | None = None,
    elapsed_ms: float = 1.0,
) -> HttpResponse:
    """Convenience constructor for a minimal ``HttpResponse`` in tests."""
    return HttpResponse(
        status_code=status_code,
        url=url,
        headers=dict(headers) if headers else {},
        text=text,
        elapsed_ms=elapsed_ms,
    )


class FakeHttpClient:
    """Programmable ``SourceHttpClient`` double: exact-URL response/error map.

    ``requested_urls`` records every URL asked for, in call order, so a
    test can assert an adapter built the request it meant to (e.g. the
    right ``base_url`` + path for a given canonical number) without any
    real network access.
    """

    def __init__(self) -> None:
        self._responses: dict[str, HttpResponse] = {}
        self._errors: dict[str, Exception] = {}
        self._sequences: dict[str, list] = {}
        self.requested_urls: list[str] = []

    def add_response(self, url: str, response: HttpResponse) -> None:
        self._responses[url] = response

    def add_error(self, url: str, error: Exception) -> None:
        self._errors[url] = error

    def add_sequence(self, url: str, outcomes: list) -> None:
        """Successive requests for ``url`` get successive outcomes (an ``HttpResponse`` is
        returned, an ``Exception`` is raised); the **last** outcome repeats forever.
        Used to script "500 first, then 200" without any real network."""
        assert outcomes, "need at least one outcome"
        self._sequences[url] = list(outcomes)

    def request_count(self, url: str) -> int:
        return self.requested_urls.count(url)

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        self.requested_urls.append(url)
        if url in self._sequences:
            queue = self._sequences[url]
            outcome = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        if url in self._errors:
            raise self._errors[url]
        if url in self._responses:
            return self._responses[url]
        raise AssertionError(f"FakeHttpClient: no response registered for {url!r}")
