"""Builders for the P4-C7 execution tests: real plans / manifests and forgeries."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.execution import _fs
from fc2_organizer.execution.directories import create_extrafanart_directory, create_target_directory
from fc2_organizer.execution.models import CompletedEffect, EffectKind, LeftoverTemporary, PathRole, TransferMode
from fc2_organizer.execution.seal import issue_checkpoint, manifest_fingerprint, plan_fingerprint
from fc2_organizer.execution.validation import expected_effects
from fc2_organizer.images import AcquiredImage, ImageAcquisitionResult, ImageRole
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteRequest, materialize_artifact
from fc2_organizer.materialization.mapping import build_artifact_requests
from fc2_organizer.planning import OrganizePlan, OutputPolicy, PlannedOperation, PlannedPath, build_organize_plan

NUMBER = "FC2-1234567"
NFO_TEXT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    "<movie>\n  <title>Example Title</title>\n</movie>\n"
)

# All 8 poster / fanart / thumb presence combinations.
MAIN_COMBOS = [(p, f, t) for p in (False, True) for f in (False, True) for t in (False, True)]


def make_plan(library_root: str, source_path: str | None = None, *, number: str = NUMBER,
              extension: str = ".mp4", size: int = 123, policy: OutputPolicy | None = None) -> OrganizePlan:
    if source_path is None:
        source_path = os.path.join(os.path.dirname(library_root), "downloads", "random-name" + extension.upper())
    item = DiscoveredMediaItem(index=0, source_path=source_path, relative_path=os.path.basename(source_path),
                               extension=extension.lower(), size=size)
    metadata = NormalizedMetadata(number=number, title="Example Title")
    return build_organize_plan(item, number, metadata, library_root, policy)


def jpeg(tag: bytes) -> bytes:
    return b"\xff\xd8\xff\xe0" + tag + b"\x00\x01\x02\xff" + b"\xff\xd9"


def image(role: ImageRole, content: bytes, candidate_index: int = 0) -> AcquiredImage:
    return AcquiredImage(role=role, candidate_index=candidate_index, content=content, width=10, height=20,
                         size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())


def make_images(poster: bool = True, fanart: bool = True, thumb: bool = True,
                extra: int = 0) -> ImageAcquisitionResult:
    return ImageAcquisitionResult(
        poster=image(ImageRole.POSTER, jpeg(b"poster")) if poster else None,
        fanart=image(ImageRole.FANART, jpeg(b"fanart")) if fanart else None,
        thumb=image(ImageRole.THUMB, jpeg(b"thumb")) if thumb else None,
        extrafanart=tuple(image(ImageRole.EXTRAFANART, jpeg(b"extra-%d" % i), i) for i in range(extra)),
    )


def make_manifest(plan: OrganizePlan, poster: bool = True, fanart: bool = True, thumb: bool = True,
                  extra: int = 0, nfo_text: str = NFO_TEXT) -> tuple[ArtifactWriteRequest, ...]:
    return build_artifact_requests(plan, nfo_text, make_images(poster, fanart, thumb, extra))


def tampered(obj, **changes):
    """A shallow copy of a frozen dataclass with fields rewritten via ``object.__setattr__``."""
    clone = copy.copy(obj)
    for name, value in changes.items():
        object.__setattr__(clone, name, value)
    return clone


def replace_op(plan: OrganizePlan, index: int, op) -> OrganizePlan:
    ops = list(plan.operations)
    ops[index] = op
    return tampered(plan, operations=tuple(ops))


def op(kind, target: str, source: str | None = None) -> PlannedOperation:
    """A PlannedOperation built without its own invariant checks (for forgeries)."""
    built = object.__new__(PlannedOperation)
    object.__setattr__(built, "kind", kind)
    object.__setattr__(built, "target", PlannedPath(target))
    object.__setattr__(built, "source", None if source is None else PlannedPath(source))
    return built


def request(kind: ArtifactKind, target: str, content: bytes = b"x", ordinal: int | None = None,
            ) -> ArtifactWriteRequest:
    return ArtifactWriteRequest(kind, target, content, ordinal)


@dataclass
class Scene:
    """A real, on-disk fresh-execution scene under ``tmp_path``."""

    root: Path
    library_root: str
    source_path: str
    content: bytes
    plan: OrganizePlan
    artifacts: tuple[ArtifactWriteRequest, ...]


def scene(tmp_path: Path, *, content: bytes = b"media-bytes" * 7, number: str = NUMBER,
          source_name: str = "random-name.MP4", library_name: str = "library", make_library: bool = True,
          make_source: bool = True, **manifest_options) -> Scene:
    library_root = tmp_path / library_name
    downloads = tmp_path / "downloads"
    downloads.mkdir(exist_ok=True)
    if make_library:
        library_root.mkdir()
    source = downloads / source_name
    if make_source:
        source.write_bytes(content)
    plan = make_plan(str(library_root), str(source), number=number, extension=os.path.splitext(source_name)[1],
                     size=len(content))
    return Scene(tmp_path, str(library_root), str(source), content, plan, make_manifest(plan, **manifest_options))


# --------------------------------------------------------------------------- S2: tests-only partial states

TEMP_NAME = ".fc2tmp-" + "ab" * 16 + ".part"


def advance(s: Scene, count: int, *, leftovers=(), transfer_mode=None):
    """TESTS-ONLY orchestration (construction plan S2 item 4): perform the first ``count`` effects of
    E(plan, manifest) for real -- the production directory helpers, a hard-link "publish" of the media
    (``os.link``) and ``os.unlink`` of the source standing in for S3, P4-C6 ``materialize_artifact`` for
    artifacts -- then issue a real sealed checkpoint. ``leftovers`` = ``[(PathRole, name), ...]`` files
    planted as recorded leftover temporaries. Not an executor: S5 owns production orchestration."""
    plan, artifacts = s.plan, s.artifacts
    slots = expected_effects(plan, artifacts)
    assert 1 <= count <= len(slots)
    library_identity = _fs.snapshot(s.library_root)
    source_identity = _fs.snapshot(s.source_path)
    requests = {(r.kind, r.ordinal): r for r in artifacts}
    effects, target_identity, extrafanart_identity = [], None, None
    for slot in slots[:count]:
        kind = slot.kind
        if kind is EffectKind.TARGET_DIRECTORY_CREATED:
            target_identity, failure = create_target_directory(plan, library_identity)
            assert failure is None
            effects.append(CompletedEffect(kind, slot.role, slot.path, target_identity, None, None, None, None))
        elif kind is EffectKind.MEDIA_PUBLISHED:
            os.link(s.source_path, slot.path)
            effects.append(CompletedEffect(kind, slot.role, slot.path, _fs.snapshot(slot.path), len(s.content),
                                           None, None, None))
        elif kind is EffectKind.SOURCE_REMOVED:
            os.unlink(s.source_path)
            effects.append(CompletedEffect(kind, slot.role, slot.path, None, None, None, None, None))
        elif kind is EffectKind.EXTRAFANART_DIRECTORY_CREATED:
            extrafanart_identity, failure = create_extrafanart_directory(plan, target_identity)
            assert failure is None
            effects.append(CompletedEffect(kind, slot.role, slot.path, extrafanart_identity, None, None, None,
                                           None))
        else:
            request_ = requests[(slot.artifact_kind, slot.ordinal)]
            materialize_artifact(request_)
            effects.append(CompletedEffect(kind, slot.role, slot.path, _fs.snapshot(slot.path),
                                           len(request_.content), hashlib.sha256(request_.content).hexdigest(),
                                           slot.artifact_kind, slot.ordinal))
    recorded = []
    for role, name in leftovers:
        directory = (plan.target_directory if role is PathRole.TARGET_DIRECTORY
                     else plan.extrafanart_directory).absolute_path
        with open(os.path.join(directory, name), "wb") as handle:
            handle.write(b"leftover")
        recorded.append(LeftoverTemporary(role, name))
    return issue_checkpoint(
        plan_fingerprint=plan_fingerprint(plan), manifest_fingerprint=manifest_fingerprint(artifacts),
        library_root_identity=library_identity, source_identity=source_identity,
        transfer_mode=transfer_mode or TransferMode.SAME_VOLUME, target_directory_identity=target_identity,
        extrafanart_directory_identity=extrafanart_identity, completed_effects=tuple(effects),
        leftover_temporaries=tuple(recorded),
    )


def checkpoint_fields(checkpoint) -> dict:
    """All fields but ``seal`` (to re-issue a modified, properly sealed checkpoint in tests)."""
    return {f.name: getattr(checkpoint, f.name) for f in dataclasses.fields(checkpoint) if f.name != "seal"}
