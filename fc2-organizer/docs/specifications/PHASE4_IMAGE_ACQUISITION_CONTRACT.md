# FC2 Organizer -- Phase 4 / P4-C5 Image Acquisition Contract

Status: **draft, substeps 1-3 of P4-C5** (foundation + binary transport + JPEG validation frozen; independent review pending).
Package: `fc2_organizer.images` (`__init__.py`, `errors.py`, `models.py`, `policy.py`, `urls.py`, `transport.py`, `jpeg.py`).
Frozen Base: `97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6`
Substep 1 Head: `a961dda486bc8377bd2cec8ae9dd107f5379eba4`
Substep 2 Head: `d7c1bd9173cb88be399368a4a7a9083f52f73e72`
Branch: `claude/phase4-c5-image-acquisition`

Sections marked **IMPLEMENTED IN SUBSTEP 2** describe the binary HTTP transport
(section 12); **IMPLEMENTED IN SUBSTEP 3** marks the JPEG-only content policy,
structural validation and dimension caps (section 13). Sections marked
**PENDING IN LATER P4-C5 SUBSTEP** describe work that is *not* implemented.
Nothing in this document claims acquisition orchestration exists yet.

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

**Substep 2 delivers only** (section 12, IMPLEMENTED IN SUBSTEP 2): the binary
HTTP transport -- `ImageHttpClient` protocol, production `HttpxImageClient`,
`ImageHttpResponse`, manual redirect handling with per-hop URL re-validation,
streamed per-response `max_bytes` bound, per-request total deadline, transport
error mapping and client lifecycle.

**Substep 3 delivers only** (section 13, IMPLEMENTED IN SUBSTEP 3): the
JPEG-only rule, the Content-Type policy, bounded JPEG structural validation,
dimension extraction from the SOF header, the dimension caps, the exact-bytes /
exact-str boundary and hostile-input semantics, plus the pure
`validate_acquired_image` helper.

**Not yet implemented** (section 11): `acquire_images`, HTTP-status ->
failure-kind mapping in the acquisition result, candidate fallback and
orchestration, role isolation, candidate-count / extrafanart / total-bytes
runtime enforcement, synthetic gate, final handoff, filesystem writes of any kind.

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

The model checks shape only. The JPEG validator and dimension caps exist
(section 13, IMPLEMENTED IN SUBSTEP 3); building every `AcquiredImage` from a
`validate_acquired_image` result (so `width` / `height` always come from the
SOF header) is the acquisition layer's job -- **PENDING IN LATER P4-C5 SUBSTEP**.

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
* **This gate does not solve DNS rebinding.** The substep-2 transport does not
  add connection-time (resolved-address) checks either; see section 12.11.
  DNS rebinding and "public name resolving to a private address" remain
  **explicitly unaddressed** in P4-C5 so far.
* Redirect targets are re-validated by the transport with this same function
  before every further hop -- **IMPLEMENTED IN SUBSTEP 2** (section 12.4).

### 8.6 Error shape

`ImageUrlError(reason)` carries only `.reason: UrlRejectionReason` and
`.failure_kind` (derived). Message: `image URL rejected: <reason.value>`. The
URL (whole or any part: host, path, query, token, userinfo) is never stored on
the exception or included in its message, and the error is never chained
(`__cause__ is None`; any context is suppressed).

## 9. Errors

```text
ImageError(Exception)
 +-- ImageInputError(ImageError, TypeError)   illegal argument (e.g. HttpxImageClient.get(max_bytes=True))
 +-- ImagePolicyError(ImageError, ValueError)
 +-- ImageModelError(ImageError, ValueError)
 +-- ImageUrlError(ImageError, ValueError)    .reason, .failure_kind
 +-- ImageTransportError(ImageError)          substep 2; failure_kind TRANSPORT_ERROR
      +-- ImageTimeoutError                   TIMEOUT
      +-- ImageConnectionError                CONNECTION_ERROR
      +-- ImageRedirectLimitError             REDIRECT_LIMIT
      +-- ImageRedirectError                  .reason (None | UrlRejectionReason);
      |                                       TRANSPORT_ERROR if None, else INVALID_URL / UNSAFE_URL
      +-- ImageResponseTooLargeError          TOO_LARGE
      +-- ImageClientClosedError              TRANSPORT_ERROR
 +-- ImageContentTypeError(ImageError, ValueError)   substep 3; CONTENT_TYPE_MISMATCH
 +-- ImageJpegError(ImageError, ValueError)          INVALID_JPEG, .reason: JpegRejectionReason
 +-- ImageDimensionError(ImageError, ValueError)     INVALID_DIMENSIONS, .reason: DimensionRejectionReason
```

Transport errors take **no constructor argument** (except `ImageRedirectError`'s
optional reason enum): each message is a fixed string, so no URL, header, body,
library message or exception `repr` can be passed in. `ImageUrlError.failure_kind`
semantics are unchanged from substep 1 (the mapping was only moved into a shared
helper so `ImageRedirectError` reuses it).

No bare `ValueError` is raised by the package.

## 10. Architecture boundary

```text
fc2_organizer.images    foundation: __init__, errors, models, policy, urls, jpeg (substep 3)
    '-- standard library only:
        __future__, dataclasses, enum, hashlib, math, re, ipaddress, urllib.parse
    '-- jpeg.py specifically: __future__, dataclasses, enum, fc2_organizer.images.errors
        (never transport.py, httpx, an image library, struct, or any I/O module)

fc2_organizer.images.transport    (substep 2 -- the single httpx exception)
    '-- httpx
    '-- fc2_organizer.images.errors, fc2_organizer.images.urls
    '-- __future__, asyncio, dataclasses, math, re, types, typing, urllib.parse
```

* Foundation modules: no import of `fc2_metadata_core` (any module, incl. `sources`, aggregation,
  batch, resource control), `amane`, `httpx`, `requests`, `socket`, `ssl`,
  `http`, `urllib.request`, `asyncio`, `os`, `pathlib`, `io`, `shutil`, `time`,
  `random`, or any other `fc2_organizer` package. `errors.py` imports only
  `__future__` and `enum`.
* No reverse dependency: `fc2_metadata_core`, `discovery`, `planning`,
  `publication` and `nfo` never import `images`.
* `transport.py` is the **only** images module that imports `httpx`. It never
  imports `fc2_metadata_core` (it does not reuse the text-oriented
  `SourceHttpClient` / `HttpResponse.text`), `amane`, a filesystem module or any
  other `fc2_organizer` package, and makes no filesystem call.
* `fc2_organizer/images/__init__.py` does **not** import `transport`; a bare
  `import fc2_organizer.images` never loads `httpx`. Import the transport
  explicitly: `from fc2_organizer.images.transport import HttpxImageClient`.
* `fc2_organizer/__init__.py` is unchanged and does **not** eagerly import
  `images`; import explicitly: `from fc2_organizer.images import ...`.
* Top-level `fc2_organizer` subpackages are now exactly
  `{"discovery", "planning", "publication", "nfo", "images"}`. The four existing
  scope-guard assertions (P4-C1..P4-C4 architecture tests) were updated by one
  line each (package-set growth only); none of their forbidden-import guards,
  runtime blockers, allow-lists or reverse-dependency guards changed.
Enforced by `tests/contract/test_images_architecture.py` (module set is exactly
the five foundation modules plus `transport.py`; only `transport.py` imports
`httpx`; transport allow-list, no filesystem call, no `.aread` / `.text` /
`decode` / non-`self` `.content`, `AsyncClient` created once in `__init__` with
`follow_redirects=False` and `trust_env=False` and no auth / cookies / headers /
proxies; foundation import allow-list; forbidden calls; reverse
dependency; runtime import with `amane` / `httpx` / `requests` / `socket` /
`ssl` / `fc2_metadata_core` / `urllib.request` / `http.client` blocked at the
meta-path level; public API contains no deferred entry point).

## 11. Implementation status

| area | status |
|---|---|
| HTTP client abstraction / httpx transport | IMPLEMENTED IN SUBSTEP 2 (12.1-12.2) |
| redirect handling and per-hop URL re-validation | IMPLEMENTED IN SUBSTEP 2 (12.4) |
| streaming body and per-response `max_bytes` bound | IMPLEMENTED IN SUBSTEP 2 (12.5-12.6) |
| per-request total deadline | IMPLEMENTED IN SUBSTEP 2 (12.7) |
| Content-Type extraction (no policy) | IMPLEMENTED IN SUBSTEP 2 (12.8) |
| transport error mapping, cancellation, lifecycle | IMPLEMENTED IN SUBSTEP 2 (12.9-12.10) |
| HTTP status -> `HTTP_STATUS` failure mapping in the acquisition result | PENDING IN LATER P4-C5 SUBSTEP |
| JPEG-only rule, Content-Type accept / reject policy | IMPLEMENTED IN SUBSTEP 3 (13.1-13.2) |
| JPEG structural validation, dimension extraction, dimension caps | IMPLEMENTED IN SUBSTEP 3 (13.3-13.4) |
| exact-bytes / exact-str boundary, hostile input semantics | IMPLEMENTED IN SUBSTEP 3 (13.6) |
| total 64 MiB result cap, candidate-count and extrafanart runtime enforcement | PENDING IN LATER P4-C5 SUBSTEP |
| connection-time resolved-address check / DNS rebinding | NOT ADDRESSED (see 8.5, 12.11) |
| `acquire_images`, candidate fallback / orchestration, candidate limit, role isolation | PENDING IN LATER P4-C5 SUBSTEP |
| synthetic acquisition gate | PENDING IN LATER P4-C5 SUBSTEP |
| final P4-C5 handoff | PENDING IN LATER P4-C5 SUBSTEP |

## 12. Binary HTTP transport -- IMPLEMENTED IN SUBSTEP 2

Module: `fc2_organizer.images.transport`. Tests:
`tests/unit/images/test_image_transport.py` (fully offline, section 12.12).

### 12.1 `ImageHttpClient` (protocol) and `ImageHttpResponse`

```python
class ImageHttpClient(Protocol):
    async def get(self, url: str, *, deadline_seconds: float, max_redirects: int,
                  max_bytes: int) -> ImageHttpResponse: ...
    async def aclose(self) -> None: ...

@dataclass(frozen=True, slots=True)
class ImageHttpResponse:
    status_code: int          # exact int, 100..599, never a redirect status
    content_type: str | None  # exact str media type or None (12.8)
    content: bytes            # exact bytes; b"" unless status_code == 200
```

`ImageHttpResponse` violations raise `ImageModelError` (`bytearray`,
`memoryview`, `str`, `bytes` / `str` subclasses, `bool` status, non-200 with a
body). The body is snapshotted into builtin `bytes`. The response holds **no**
URL, redirect history, header mapping, cookie, `httpx.Request` / `httpx.Response`
or exception (its `gc` referents are only `int` / `str` / `bytes` / `None`).

`get` argument rules (else `ImageInputError`, before any request):
`deadline_seconds` exact `int` / `float`, finite, `> 0`; `max_redirects` exact
`int >= 0`; `max_bytes` exact `int > 0`. There is no `headers`, `cookies`,
`auth` or credentials parameter.

### 12.2 `HttpxImageClient`

* One `httpx.AsyncClient` per instance, created in `__init__` (never per request,
  never at import time). Construction sends no request.
* `follow_redirects=False`, `trust_env=False` (no `HTTP_PROXY` / `HTTPS_PROXY`
  / `ALL_PROXY` / `.netrc`), no auth, no client cookies, no client headers.
* `transport=` accepts an `httpx.AsyncBaseTransport` (tests inject
  `httpx.MockTransport`); anything else -> `ImageInputError`.
* Each hop's `httpx.Request` is built directly with only the fixed headers
  `Accept: image/jpeg, image/*;q=0.8`, `Accept-Encoding: identity`,
  `User-Agent: fc2-organizer-image-fetch/0.1 (...)` (plus httpx's `Host`).
  Server cookies are cleared from the client jar after every hop and are
  never sent.
* Parse-differential guard: the built request's scheme and host must equal the
  `urlsplit` scheme / hostname the validator judged; otherwise nothing is sent
  (`ImageTransportError`).
* One send per hop -- **no retry, no backoff, no `Retry-After`**. A redirect is
  not a retry.

### 12.3 Initial URL

`validate_image_url(url)` (substep 1, not a copy) runs before any request is
built. An unsafe / invalid initial URL raises `ImageUrlError` and nothing is sent.

### 12.4 Manual redirects

* Redirect statuses: `301 302 303 307 308`. Each hop is a `GET`.
* httpx 0.27 `AsyncClient.send` parses `Location` itself (to build
  `next_request`) even with `follow_redirects=False`. To keep every redirect
  target under *our* validator, a response event hook runs right after the
  headers arrive and, for a redirect status, stops `send` with a private signal
  carrying only the raw `Location` string; httpx closes that response **unread**.
* Resolution: `urllib.parse.urljoin(current_url, location)` (relative
  `Location` allowed), then `validate_image_url(target)` **before** the next hop
  is sent. The validated string is exactly what is requested next.
* Missing / blank `Location` -> `ImageRedirectError(reason=None)`
  (`TRANSPORT_ERROR`). A target failing validation (localhost, `*.localhost`,
  private / link-local / loopback / non-canonical-numeric IP, `file:` / `data:`
  / `ftp:`, userinfo, whitespace, malformed ...) -> `ImageRedirectError(reason)`
  whose `failure_kind` is `INVALID_URL` / `UNSAFE_URL` exactly as for
  `ImageUrlError`. **The rejected target is never requested** (tests assert the
  recorded request list).
* A redirect body is never read and never treated as an image.

**Redirect limit (frozen):** `max_redirects` is the number of redirects that may
be *followed*. With `max_redirects = N`, a chain of N redirects succeeds (N+1
requests); when the (N+1)-th redirect response arrives, `ImageRedirectLimitError`
is raised **without** requesting its target (so at most N+1 requests are sent).
`max_redirects = 0` means the first redirect response fails. Boundary tests
cover N = 0, 1, 5, 6 on both sides.

### 12.5 Status handling

Only a final `200` enters body streaming. Every other final status (`204`,
`206`, `304`, `403`, `404`, `429`, `500`, `503`, ...) returns
`ImageHttpResponse(status_code, content_type, b"")` **without reading the
body**. Mapping a non-200 status to `HTTP_STATUS` is the acquisition layer's job
(PENDING). A status outside `100..599` -> `ImageTransportError`.

### 12.6 Streaming `max_bytes` bound and `Content-Length`

* `Content-Encoding` must be absent or `identity` (the request asks for
  `identity`); anything else -> `ImageTransportError` before reading, so no
  decompression (and no decompression bomb) ever happens and the byte counter
  equals the bytes held in memory.
* The body is consumed chunk by chunk (`aiter_bytes` under identity encoding)
  into a `bytearray`; before appending a chunk,
  `len(buffer) + len(chunk) > max_bytes` -> `ImageResponseTooLargeError`
  immediately; **no further chunk is pulled** and the response is closed without
  draining. Exactly `max_bytes` is accepted; `max_bytes + 1` is rejected. Never
  `aread()` / `.content` first.
* `Content-Length` early reject: if the header is a well-formed ASCII decimal
  (`[0-9]+` after trimming) and its value `> max_bytes`, `TOO_LARGE` is raised
  before reading any body byte. Very long digit strings are compared by length,
  never passed to `int()`. A malformed / signed / duplicated value is ignored.
  `Content-Length` is only a hint: the streamed counter applies regardless (a
  lying small value is still capped; a missing value is fine).

### 12.7 Total deadline

`deadline_seconds` is the whole wall-clock budget of one `get()`: first hop,
every redirect, headers and body streaming. One `asyncio.timeout(deadline)`
wraps the entire request / redirect / stream lifecycle; it is **not** reset per
hop. Each hop's httpx timeout extension is set to the *remaining* budget, and
any httpx timeout (`ConnectTimeout`, `ReadTimeout`, `WriteTimeout`,
`PoolTimeout`) or builtin `TimeoutError` maps to the same `ImageTimeoutError`.

### 12.8 Content-Type extraction (no policy)

`content_type` is the `Content-Type` media type: the text before the first `;`,
surrounding whitespace trimmed, case preserved. `None` when the header is
absent, empty, longer than 127 characters or contains anything but printable
ASCII. No `image/jpeg` / `image/png` / `application/octet-stream` judgement
happens in the transport; the policy is section 13.2 (IMPLEMENTED IN SUBSTEP 3),
applied by the acquisition layer (PENDING). The header mapping is never returned.

### 12.9 Error mapping and cancellation

| cause | raised |
|---|---|
| httpx `TimeoutException` family, builtin `TimeoutError`, deadline expiry | `ImageTimeoutError` |
| httpx `NetworkError` (`ConnectError` incl. DNS / TLS, `ReadError`, `WriteError`, `CloseError`), `ProtocolError` (`RemoteProtocolError`, `LocalProtocolError`), `ProxyError` | `ImageConnectionError` |
| any other ordinary `Exception` (e.g. `UnsupportedProtocol`, `RuntimeError`) | `ImageTransportError` |
| failure after `aclose()` | `ImageClientClosedError` |

Library exceptions are translated into a **fresh** error value inside the worker
coroutine and raised only from `get()` itself, outside any `except` block, so
`__cause__` and `__context__` are `None` and no httpx exception, request,
response, header mapping or redirect URL is reachable from the error. Messages
never contain a URL, query, body, library message or exception `repr`.

**Cancellation (frozen):** a caller's `asyncio.CancelledError` propagates
unchanged (it is never mapped). `KeyboardInterrupt`, `SystemExit`,
`GeneratorExit` and every other non-`Exception` `BaseException` propagate
untouched. Only ordinary `Exception`s are mapped.

### 12.10 Lifecycle

`async with HttpxImageClient() as client:` or `await client.aclose()`
(idempotent). After close, `get()` and `__aenter__` raise
`ImageClientClosedError` and send nothing.

### 12.11 Explicit non-claims

* No resolved-address (connection-time) check: a public hostname whose DNS
  answer is private / loopback is still connected to. DNS rebinding is **not**
  addressed.
* No retry / backoff / `Retry-After`, no HTTP/2, no caching.
* The transport itself makes no Content-Type or JPEG judgement (that is
  section 13, applied by the acquisition layer); no role / candidate
  orchestration, no result-level total-bytes cap (PENDING).

### 12.12 Offline tests

All transport tests use `httpx.MockTransport` plus a recording
`httpx.AsyncByteStream` -- no DNS, socket, listener or public network. Proof
strength: the recording stream counts chunks actually pulled (over-cap bodies
stop at exactly the first chunk crossing the cap; non-200 / redirect bodies
pull zero chunks), and the recorder lists every request actually sent (unsafe
redirect targets never appear). Mutation-checked during development: removing
redirect re-validation, reading the whole body before the size check, or
re-arming the deadline per hop each makes the corresponding tests fail.

## 13. JPEG-only content validation -- IMPLEMENTED IN SUBSTEP 3

Module: `fc2_organizer.images.jpeg` (standard library only; exported from
`fc2_organizer.images`). Tests: `tests/unit/images/test_image_jpeg.py`.

### 13.1 JPEG-only rule (frozen)

The P4-C5 output format is **JPEG only**. PNG, WEBP, GIF, AVIF, HTML, JSON or
anything else without a JPEG structure is refused (`INVALID_JPEG`). Nothing is
transcoded; no image library (Pillow or other) is added or imported.

### 13.2 Content-Type policy: `validate_image_content_type(content_type) -> ContentTypeVerdict`

`content_type` must be `None` or an exact `str` (`ImageInputError` otherwise,
before any method of the value runs). The media type is the text before the
first `;`, whitespace-trimmed, compared case-insensitively; parameters are ignored.

| declared media type | outcome |
|---|---|
| `image/jpeg`, `image/jpg`, `image/pjpeg` | `JPEG_DECLARED` |
| `None`, empty, `application/octet-stream` | `UNDECLARED` -- the bytes alone decide |
| anything else (`image/png`, `image/webp`, `image/gif`, `image/avif`, `text/html`, `application/json`, `text/plain`, `image/*`, `binary/octet-stream`, ...) | `ImageContentTypeError` -> `CONTENT_TYPE_MISMATCH` |

An explicit non-JPEG media type is rejected **even when the body is a valid
JPEG**. `JPEG_DECLARED` and `UNDECLARED` both still require the byte validation
of 13.3; a declaration never substitutes for it. The error message is fixed
(`image content type is not JPEG`) and never echoes the declared value.

### 13.3 Structural validation: `inspect_jpeg(content) -> JpegInfo`

`content` must be exact `bytes` (`bytearray`, `memoryview`, `str` and any
`bytes` subclass -> `ImageInputError`, before any hook of the value runs).
One forward pass, O(len(content)), every index bounds-checked before use:

1. `FF D8` (SOI) at offset 0, else `NOT_JPEG` (this is where PNG / WEBP / GIF /
   AVIF / HTML / JSON fail).
2. Up to and including the first SOS, markers and segments are parsed exactly:
   * a marker is `0xFF`, optionally repeated as fill bytes (T.81 B.1.1.2), then
     a code; a non-`FF` byte where a marker must start -> `INVALID_MARKER`. Fill
     bytes are never taken as segment data;
   * standalone markers `TEM` (`01`) and `RST0..7` (`D0..D7`) carry no length
     and are skipped;
   * `FF 00`, a repeated SOI and reserved codes `02..BF` -> `INVALID_MARKER`;
   * an EOI before any SOS -> `MISSING_SOF` / `MISSING_SOS`;
   * every other marker has a 2-byte big-endian length: a cut length field ->
     `TRUNCATED`, length `< 2` -> `INVALID_SEGMENT_LENGTH`, a segment running
     past the end -> `SEGMENT_OUT_OF_BOUNDS`. Such segments (APPn, DQT, DHT, DAC,
     DRI, COM, JPG, JPGn, DNL, DHP, EXP ...) are skipped by their declared length.
3. SOF: exactly the 13 frame markers `C0 C1 C2 C3 C5 C6 C7 C9 CA CB CD CE CF`.
   `C4` (DHT), `C8` (JPG) and `CC` (DAC) are **never** frames. Frame header:
   precision, height, width, component count `Nf >= 1`, and the segment length
   must be exactly `8 + 3*Nf`. Precision `8` or `12` (DCT) or `2..16`
   (lossless `C3 C7 CB CF`); otherwise `INVALID_SOF`. A second SOF ->
   `MULTIPLE_SOF`.
4. SOS: requires a prior SOF (`MISSING_SOF`); header `Ns` in `1..4` and length
   exactly `6 + 2*Ns` (`INVALID_SOS`).
5. After the SOS header the entropy-coded data is **not scanned**. The payload
   must end with `FF D9` (EOI), located after the SOS header; otherwise
   `MISSING_EOI` (this includes trailing bytes after EOI). Data ending before
   any SOS -> `TRUNCATED`.

A bare `FF D8 ... FF D9` without real segments is rejected; the check is never
just `startswith(FFD8)` / `endswith(FFD9)`.

**Scope of the promise (frozen):** bounded *structural* validation. Passing it
does **not** guarantee that every JPEG decoder can decode the image (entropy
data, Huffman / quantisation table content and component sampling are not
verified). No pixel is decoded.

All failures are `ImageJpegError(reason: JpegRejectionReason)`
(`INVALID_JPEG`). No `IndexError`, `struct.error`, `UnicodeError`,
`OverflowError` or other internal exception can escape (every prefix of a
valid fixture and a deterministic 3000-case mutation fuzz are tested).

### 13.4 Dimensions and caps

Width and height come from the SOF frame header (no decoding). They are judged
**after** the structure is accepted. `JpegInfo(width, height, sof_marker)` is
`frozen=True, slots=True` and enforces the caps at construction:

| rule | reason (`INVALID_DIMENSIONS`) |
|---|---|
| width / height exact `int` (not `bool`) | `NOT_EXACT_INT` |
| `width == 0` | `ZERO_WIDTH` |
| `height == 0` (DNL-defined height is not supported) | `ZERO_HEIGHT` |
| `width <= 20000` | `WIDTH_TOO_LARGE` |
| `height <= 20000` | `HEIGHT_TOO_LARGE` |
| `width * height <= 100_000_000` | `TOO_MANY_PIXELS` |

`20000 x 5000` (exactly `1e8`) is accepted; `20000 x 5001` is not. Violations
raise `ImageDimensionError(reason)`, never a bare `ValueError`. `sof_marker`
must be one of the 13 frame markers.

### 13.5 Integration helper: `validate_acquired_image(content, content_type) -> JpegInfo`

Frozen order: (0) exact types of both arguments, (1) Content-Type policy,
(2) JPEG structure, (3) dimension caps. Pure: no HTTP, role, candidate
iteration or I/O. Wiring it into acquisition is PENDING.

### 13.6 Hostile input semantics

`type(content) is bytes` and `content_type is None or type(content_type) is str`
are the first operations. A hostile `bytes` subclass (overriding `__bytes__`,
`__repr__`, `__str__`, `__getitem__`, `__len__`, `__iter__`, `__eq__`,
`__hash__`, `__buffer__`, `startswith`, `find`, `decode`, ...) or `str`
subclass (`strip`, `lower`, `split`, `__eq__`, `__hash__`, ...) is rejected
with `ImageInputError` and **zero** of its hooks run (tested with hooks that
record and raise).

### 13.7 Errors and side effects

`ImageContentTypeError` (`CONTENT_TYPE_MISMATCH`), `ImageJpegError`
(`INVALID_JPEG`, `.reason`), `ImageDimensionError` (`INVALID_DIMENSIONS`,
`.reason`) are `ImageError` + `ValueError`. Messages are fixed text plus the
reason value: never payload bytes, a declared Content-Type, a URL or internal
exception text; never chained. The module performs zero filesystem, network,
clock or randomness operations and imports only `__future__`, `dataclasses`,
`enum` and `fc2_organizer.images.errors`.

Mutation-checked during development: accepting `C4`/`C8`/`CC` as SOF, dropping
the EOI check, dropping the segment-length lower bound, dropping the bounds
check, dropping the pixel cap, or using `isinstance` instead of the exact-type
check each makes `test_image_jpeg.py` fail.

P4-C5: **NOT CLOSED**. Phase 4: **NOT CLOSED**.
