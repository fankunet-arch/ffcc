# FC2 Organizer -- Phase 4 / P4-C5 Image Acquisition Contract

Status: **draft, substep 1 of P4-C5** (foundation frozen; independent review pending).
Package: `fc2_organizer.images` (`__init__.py`, `errors.py`, `models.py`, `policy.py`, `urls.py`).
Frozen Base: `97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6`
Branch: `claude/phase4-c5-image-acquisition`

Sections marked **PENDING IN LATER P4-C5 SUBSTEP** describe work that is *not*
implemented. Nothing in this document claims transport, download, redirect,
streaming, JPEG or orchestration behaviour exists yet.

## 1. Scope

P4-C5 as a whole: acquire, in memory, the poster / fanart / thumb / extrafanart
images for one film from the candidate image URLs of its metadata, with bounded
time, redirects and memory, and report every per-candidate failure in a
structured, secret-free form.

**Substep 1 (this substep) delivers only:**

1. the `fc2_organizer.images` package skeleton;
2. immutable value models (section 3-6);
3. the failure vocabulary (section 5);
4. the immutable acquisition policy (section 7);
5. a pure candidate-URL safety gate (section 8);
6. the error hierarchy (section 9) and the architecture boundary with its
   contract test (section 10).

**Not in substep 1** (section 11): HTTP transport, real or mock download,
redirect handling, status classification, streaming / memory enforcement,
Content-Type handling, JPEG validation, dimension extraction, candidate
fallback, role orchestration, `acquire_images`, synthetic gate, filesystem
writes of any kind.

## 2. Roles

```python
class ImageRole(Enum):
    POSTER = "poster"
    FANART = "fanart"
    THUMB = "thumb"
    EXTRAFANART = "extrafanart"
```

Exactly the four artwork roles of the frozen v1.0 organize layout
(`poster.jpg` / `fanart.jpg` / `thumb.jpg` / `extrafanart/`,
PHASE4_ORGANIZE_PLAN_CONTRACT). The mapping from role to metadata URL list
(`poster_urls` / `fanart_urls` / `thumb_urls` / `extrafanart`) and to plan paths
is **PENDING IN LATER P4-C5 SUBSTEP**.

## 3. Model rules (all models)

* `@dataclass(frozen=True, slots=True)`; no `__dict__`.
* Every field is validated in `__post_init__` with **exact** type checks
  (`type(x) is T`): `bool` never passes as `int`; a `bytes` / `str` / `tuple` /
  model subclass never passes as the base type.
* Violations raise `ImageModelError`. Messages carry only field names, Python
  type names and fixed wording.
* No model has a `url`, `headers`, `cookies`, `body`, `exception`,
  `traceback` or free-text `error_detail` field.

## 4. `AcquiredImage`

| field | rule |
|---|---|
| `role` | exact `ImageRole` |
| `candidate_index` | exact `int`, `>= 0` (position in the role's candidate list) |
| `content` | exact `bytes`; excluded from `repr` |
| `width`, `height` | exact `int`, `> 0` (carried, **not measured** in substep 1) |
| `size_bytes` | exact `int`, `== len(content)` |
| `sha256` | exact `str`, 64 lowercase hex chars, **equal to** `hashlib.sha256(content).hexdigest()` |

The model checks shape only; whether `content` is a real JPEG and whether
`width` / `height` match it is **PENDING IN LATER P4-C5 SUBSTEP**.

## 5. Failure vocabulary: `ImageFailureKind` and `ImageCandidateFailure`

```text
INVALID_URL  UNSAFE_URL  CANDIDATE_LIMIT
TIMEOUT  CONNECTION_ERROR  REDIRECT_LIMIT  TRANSPORT_ERROR
HTTP_STATUS  TOO_LARGE  TOTAL_BYTES_LIMIT
CONTENT_TYPE_MISMATCH  INVALID_JPEG  INVALID_DIMENSIONS
```

The words are frozen. In substep 1 only `INVALID_URL` / `UNSAFE_URL` are
reachable (via `ImageUrlError.failure_kind`); the rest are reserved vocabulary.

`ImageCandidateFailure(role, candidate_index, kind, http_status=None)`:

| field | rule |
|---|---|
| `role` | exact `ImageRole` |
| `candidate_index` | exact `int`, `>= 0` |
| `kind` | exact `ImageFailureKind` |
| `http_status` | exact `int` in `100..599` **iff** `kind is HTTP_STATUS`; otherwise `None` |

Nothing else is stored: no URL, query, header, cookie, `Authorization`, body,
exception or traceback.

## 6. `ImageAcquisitionResult`

| field | rule |
|---|---|
| `poster` | `None` or exact `AcquiredImage` with `role is POSTER` |
| `fanart` | `None` or exact `AcquiredImage` with `role is FANART` |
| `thumb` | `None` or exact `AcquiredImage` with `role is THUMB` |
| `extrafanart` | exact `tuple` of exact `AcquiredImage`, each `role is EXTRAFANART` |
| `failures` | exact `tuple` of exact `ImageCandidateFailure` |

All-empty (`ImageAcquisitionResult()`) is legal. `total_bytes` is a pure
property: the sum of `size_bytes` over every acquired image. Enforcing that it
stays within `max_total_bytes`, and that `len(extrafanart) <= max_extrafanart`,
is **PENDING IN LATER P4-C5 SUBSTEP** (orchestration).

## 7. `ImageAcquisitionPolicy`

| field | default | rule |
|---|---|---|
| `request_deadline_seconds` | `15.0` | exact `int` or `float` (not `bool`), finite, `> 0` |
| `max_redirects` | `5` | exact `int` (not `bool`), `> 0` |
| `max_image_bytes` | `16 * 1024 * 1024` | exact `int`, `> 0` |
| `max_total_bytes` | `64 * 1024 * 1024` | exact `int`, `> 0` |
| `max_candidates_per_role` | `16` | exact `int`, `> 0` |
| `max_extrafanart` | `12` | exact `int`, `> 0` |

Cross-field: `max_image_bytes <= max_total_bytes`. Violations raise
`ImagePolicyError`. `frozen=True, slots=True`.

Substep 1 validates values only. **Runtime enforcement of every cap is
PENDING IN LATER P4-C5 SUBSTEP.**

## 8. URL safety gate: `validate_image_url(url) -> str`

Pure function; no DNS, socket, filesystem, clock or environment access.

### 8.1 Exact-type boundary

The first operation is `type(url) is str`. Anything else -- including any `str`
subclass -- raises `ImageUrlError(NOT_EXACT_STR)` **before** any method of the
value (`strip`, `encode`, `__eq__`, `__hash__`, `__repr__`, `__format__`,
`__iter__`, `__len__`, `__bool__`, ...) can run. Enforced by a hostile-subclass
test whose every hook records and raises; the recorded hook count must be 0.

### 8.2 Output: safety judgement is not normalization (frozen)

* A safe URL is returned as **the same `str` object** (`result is url`).
* The validator never strips, case-folds, re-quotes, re-encodes, removes
  userinfo from, reorders or otherwise rewrites the URL or its query.
* No `urllib` `SplitResult` / `ParseResult` is returned or retained.
* A URL that would need rewriting to be safe is rejected, not repaired.

### 8.3 Rules (checked in this order)

| # | rule | reason | kind |
|---|---|---|---|
| 1 | exact `str` | `NOT_EXACT_STR` | `INVALID_URL` |
| 2 | non-empty | `EMPTY` | `INVALID_URL` |
| 3 | `len <= 4096` (`MAX_IMAGE_URL_LENGTH`) | `TOO_LONG` | `INVALID_URL` |
| 4 | no Unicode whitespace, C0 control or DEL anywhere (so `urlsplit`'s silent stripping never applies) | `WHITESPACE_OR_CONTROL` | `INVALID_URL` |
| 5 | no `\` anywhere (WHATWG treats it as `/`, `urlsplit` does not) | `BACKSLASH` | `UNSAFE_URL` |
| 6 | `urlsplit` succeeds | `MALFORMED` | `INVALID_URL` |
| 7 | has a scheme (else relative, incl. `//host/x`) | `RELATIVE` | `INVALID_URL` |
| 8 | scheme is `http` or `https` (case-insensitive); `file:` `data:` `ftp:` `javascript:` etc. refused | `UNSUPPORTED_SCHEME` | `UNSAFE_URL` |
| 9 | non-empty authority | `MISSING_HOST` | `INVALID_URL` |
| 10 | no userinfo (`@` in authority) | `USERINFO` | `UNSAFE_URL` |
| 11 | port absent or `1..65535` | `INVALID_PORT` | `INVALID_URL` |
| 12 | non-empty hostname | `MISSING_HOST` | `INVALID_URL` |
| 13 | bracketed host: valid IPv6, no zone id, global (8.4) | `INVALID_HOST` / `NON_GLOBAL_IP` | `INVALID_URL` / `UNSAFE_URL` |
| 14 | reg-name host: ASCII `[a-z0-9_-]` labels, no empty label, optional single trailing dot; no `%`, no non-ASCII (IDNA / NFKC could map e.g. full-width digits to an IP) | `INVALID_HOST` | `INVALID_URL` |
| 15 | host (trailing dot ignored) is not `localhost` and does not end in `.localhost` | `LOCALHOST` | `UNSAFE_URL` |
| 16 | if the last label is numeric (`[0-9]+` or `0x[0-9a-f]*`), the host must be a strict dotted-quad IPv4 (rejects `2130706433`, `0x7f.1`, `127.1`, `0177.0.0.1`) | `NUMERIC_HOST` | `UNSAFE_URL` |
| 17 | IPv4 literal is global (8.4) | `NON_GLOBAL_IP` | `UNSAFE_URL` |

### 8.4 Global-address rule

Using stdlib `ipaddress`, an IP literal is accepted only if it is `is_global`
**and** not private, loopback, link-local, multicast, reserved or unspecified
(multicast is checked explicitly: `is_global` is `True` for it on Python 3.12),
not IPv6 site-local, and every embedded IPv4 address (IPv4-mapped, 6to4,
Teredo) is itself global. Examples refused: `127.0.0.1`, `::1`, `10.0.0.1`,
`192.168.1.1`, `169.254.169.254`, `224.0.0.1`, `240.0.0.1`, `0.0.0.0`,
`100.64.0.1`, `::ffff:127.0.0.1`, `64:ff9b::7f00:1`. Public literals such as
`8.8.8.8` and `2606:4700:4700::1111` are accepted.

### 8.5 Explicit non-claims (frozen)

* **No DNS resolution.** A public-looking hostname that resolves to a private
  or loopback address is **not** caught by this gate.
* **This gate does not solve DNS rebinding.** Connection-time address policy is
  **PENDING IN LATER P4-C5 SUBSTEP** (transport), and may still not fully
  close it.
* Redirect targets must be re-validated by the transport -- **PENDING IN LATER
  P4-C5 SUBSTEP**.

### 8.6 Error shape

`ImageUrlError(reason)` carries only `.reason: UrlRejectionReason` and
`.failure_kind` (derived). Message: `image URL rejected: <reason.value>`. The
URL (whole or any part: host, path, query, token, userinfo) is never stored on
the exception or included in its message, and the error is never chained
(`__cause__ is None`; any context is suppressed).

## 9. Errors

```text
ImageError(Exception)
 +-- ImageInputError(ImageError, TypeError)   reserved for the later acquisition entry point
 +-- ImagePolicyError(ImageError, ValueError)
 +-- ImageModelError(ImageError, ValueError)
 +-- ImageUrlError(ImageError, ValueError)    .reason, .failure_kind
```

No bare `ValueError` is raised by the package.

## 10. Architecture boundary

```text
fc2_organizer.images    (substep 1)
    '-- standard library only:
        __future__, dataclasses, enum, hashlib, math, re, ipaddress, urllib.parse
```

* No import of `fc2_metadata_core` (any module, incl. `sources`, aggregation,
  batch, resource control), `amane`, `httpx`, `requests`, `socket`, `ssl`,
  `http`, `urllib.request`, `asyncio`, `os`, `pathlib`, `io`, `shutil`, `time`,
  `random`, or any other `fc2_organizer` package. `errors.py` imports only
  `__future__` and `enum`.
* No reverse dependency: `fc2_metadata_core`, `discovery`, `planning`,
  `publication` and `nfo` never import `images`.
* `fc2_organizer/__init__.py` is unchanged and does **not** eagerly import
  `images`; import explicitly: `from fc2_organizer.images import ...`.
* Top-level `fc2_organizer` subpackages are now exactly
  `{"discovery", "planning", "publication", "nfo", "images"}`. The four existing
  scope-guard assertions (P4-C1..P4-C4 architecture tests) were updated by one
  line each (package-set growth only); none of their forbidden-import guards,
  runtime blockers, allow-lists or reverse-dependency guards changed.
* Whether the later transport substep may depend on `httpx` directly or must go
  through a local abstraction is **PENDING IN LATER P4-C5 SUBSTEP**.

Enforced by `tests/contract/test_images_architecture.py` (module set is exactly
the five foundation modules; import allow-list; forbidden calls; reverse
dependency; runtime import with `amane` / `httpx` / `requests` / `socket` /
`ssl` / `fc2_metadata_core` / `urllib.request` / `http.client` blocked at the
meta-path level; public API contains no deferred entry point).

## 11. Deferred sections -- PENDING IN LATER P4-C5 SUBSTEP

| area | status |
|---|---|
| HTTP client abstraction / httpx transport | PENDING IN LATER P4-C5 SUBSTEP |
| redirect handling and per-hop URL re-validation | PENDING IN LATER P4-C5 SUBSTEP |
| HTTP status classification | PENDING IN LATER P4-C5 SUBSTEP |
| streaming body, per-image and total memory bounds at runtime | PENDING IN LATER P4-C5 SUBSTEP |
| deadline enforcement | PENDING IN LATER P4-C5 SUBSTEP |
| Content-Type handling | PENDING IN LATER P4-C5 SUBSTEP |
| JPEG validation and width / height extraction | PENDING IN LATER P4-C5 SUBSTEP |
| candidate fallback, candidate limit, role orchestration, `acquire_images` | PENDING IN LATER P4-C5 SUBSTEP |
| synthetic acquisition gate | PENDING IN LATER P4-C5 SUBSTEP |
| final P4-C5 handoff | PENDING IN LATER P4-C5 SUBSTEP |

P4-C5: **NOT CLOSED**. Phase 4: **NOT CLOSED**.
