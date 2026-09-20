"""Scriptable fake source adapters for the aggregation tests (fully offline).

``scripted_adapter_class(source_id, script)`` returns a real ``SourceAdapter``
subclass whose ``fetch`` runs ``script(number, client)`` -- so the engine,
registry and execution boundary are exercised with genuine ``SourceAdapter``
objects, never mocks. ``ok`` / ``failed`` build the ``SourceResult``s a script
returns.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.sources.base import SourceAdapter

Script = Callable[[str, object], Awaitable[SourceResult]]


def ok(
    source_id: str,
    number: str,
    title: str | None = "A title",
    *,
    elapsed_ms: float = 1.0,
    field_sources: dict | None = None,
    **fields,
) -> SourceResult:
    """A SUCCESS result. ``field_sources`` (default: honest) is what the adapter *claims*."""
    if title is not None:
        fields["title"] = title
    honest = {name: (source_id,) for name in ("number", *fields)}
    metadata = NormalizedMetadata(
        number=number, field_sources=honest if field_sources is None else field_sources, **fields
    )
    return SourceResult(source_id=source_id, status=SourceStatus.SUCCESS, metadata=metadata, elapsed_ms=elapsed_ms)


def failed(source_id: str, status: SourceStatus, *, elapsed_ms: float = 1.0, detail: str | None = None) -> SourceResult:
    assert status is not SourceStatus.SUCCESS
    return SourceResult(
        source_id=source_id,
        status=status,
        metadata=None,
        elapsed_ms=elapsed_ms,
        error_kind=SourceErrorKind(status.value),
        error_detail=detail or f"{source_id}: scripted {status.value}",
    )


def scripted_adapter_class(source_id: str, script: Script) -> type[SourceAdapter]:
    """A real ``SourceAdapter`` subclass whose fetch is ``script``."""

    class _Scripted(SourceAdapter):
        display_name = f"Scripted {source_id}"
        default_base_url = f"https://{source_id.replace('_', '-')}.invalid"

        def __init__(self, *, base_url: str | None = None) -> None:
            super().__init__(base_url=base_url)
            self.calls: list[str] = []

        async def fetch(self, number, client):
            self.calls.append(number)
            return await script(number, client)

    _Scripted.source_id = source_id
    _Scripted.__name__ = f"Scripted_{source_id}"
    return _Scripted
