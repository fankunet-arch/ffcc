# Phase 4 / P4-C5 Handoff -- Image Acquisition

```text
Phase        = 4
Package      = P4-C5
Role         = Developer
Branch       = claude/phase4-c5-image-acquisition
```

## 1. Coordinates

```text
Frozen Base                  = 97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6
Substep 1 Head               = a961dda486bc8377bd2cec8ae9dd107f5379eba4   foundation: models / policy / URL safety
Substep 2 Head               = d7c1bd9173cb88be399368a4a7a9083f52f73e72   binary HTTP transport
Substep 3 Head               = 4c780a88dd97613e97fe6a0f139deddcbfb40066   JPEG-only content validation
Substep 4 Head               = 9fff05ec1e8dbec3fce65dd9453fa41b8a4b786e   acquire_images orchestration
P4-C5 Code Review Candidate  = 3ef881b416439accf634ce792723b49d01db0d64   synthetic gate + frozen contract
P4-C5 Docs Head              = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C5_HANDOFF.md`>
Remote Head                  = <== Docs Head after push of this commit>

Code Review Range: 97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6..3ef881b416439accf634ce792723b49d01db0d64
Docs Review Range: 3ef881b416439accf634ce792723b49d01db0d64..<Docs Head>
```

History is linear: `97f6aeb -> a961dda -> d7c1bd9 -> 4c780a8 -> 9fff05e -> 3ef881b -> Docs Head`.
Every substep started from a verified `HEAD == origin/claude/phase4-c5-image-acquisition == <parent>`
with a clean working tree (only the untracked harness `.claude/`). No rebase, amend, squash or
force push. The Code Review Candidate contains code, tests and the frozen contract
(`PHASE4_IMAGE_ACQUISITION_CONTRACT.md`); the Docs Head commit contains only this file.

## 2. Type

**NEW PACKAGE** (`fc2_organizer.images`) + four one-line package-set scope-guard updates
(`{"discovery", "planning", "publication", "nfo"}` -> `+ "images"`). No production file outside
`fc2_organizer/images/` was touched; `fc2_organizer/__init__.py` is unchanged. Substep 5 changed no
production code (gate test + contract only).

## 3. Changed files (Code Review Range, 22 files, +5890 / -4)

New (18):
```text
fc2-organizer/docs/specifications/PHASE4_IMAGE_ACQUISITION_CONTRACT.md
fc2-organizer/src/fc2_organizer/images/__init__.py
fc2-organizer/src/fc2_organizer/images/errors.py
fc2-organizer/src/fc2_organizer/images/models.py
fc2-organizer/src/fc2_organizer/images/policy.py
fc2-organizer/src/fc2_organizer/images/urls.py
fc2-organizer/src/fc2_organizer/images/transport.py
fc2-organizer/src/fc2_organizer/images/jpeg.py
fc2-organizer/src/fc2_organizer/images/acquisition.py
fc2-organizer/tests/contract/test_images_architecture.py
fc2-organizer/tests/unit/images/__init__.py
fc2-organizer/tests/unit/images/test_image_models.py
fc2-organizer/tests/unit/images/test_image_policy.py
fc2-organizer/tests/unit/images/test_image_urls.py
fc2-organizer/tests/unit/images/test_image_transport.py
fc2-organizer/tests/unit/images/test_image_jpeg.py
fc2-organizer/tests/unit/images/test_image_acquisition.py
fc2-organizer/tests/unit/images/test_image_synthetic_gate.py
```

Modified (4, one line each -- package set only; no forbidden-import guard, runtime blocker,
allow-list or reverse-dependency guard changed):
```text
fc2-organizer/tests/contract/test_discovery_architecture.py
fc2-organizer/tests/contract/test_planning_architecture.py
fc2-organizer/tests/contract/test_publication_architecture.py
fc2-organizer/tests/contract/test_nfo_architecture.py
```

## 4. Public API

```python
# stdlib-only, from fc2_organizer.images
validate_image_url(url) -> str
validate_image_content_type(content_type) -> ContentTypeVerdict
inspect_jpeg(content) -> JpegInfo
validate_acquired_image(content, content_type) -> JpegInfo
ImageRole, ImageFailureKind, AcquiredImage, ImageCandidateFailure, ImageAcquisitionResult,
ImageAcquisitionPolicy, JpegInfo, error classes / reason enums, MAX_* constants

# explicit imports (depend on httpx / publication; not loaded by `import fc2_organizer.images`)
from fc2_organizer.images.transport import ImageHttpClient, ImageHttpResponse, HttpxImageClient
from fc2_organizer.images.acquisition import acquire_images

async def acquire_images(record: PublicationRecord, client: ImageHttpClient, *,
                         policy: ImageAcquisitionPolicy | None = None) -> ImageAcquisitionResult
```

No `write`, `save`, `materialize`, `download_to`, path or file API exists.

## 5. Models (contract 3-6)

All `@dataclass(frozen=True, slots=True)`, exact-type validated (`bool` never an `int`, no
subclass passes). `AcquiredImage(role, candidate_index, content, width, height, size_bytes,
sha256)`: exact `bytes` (excluded from `repr`), `size_bytes == len(content)`, `sha256` = lowercase
hex digest **of `content`**. `ImageCandidateFailure(role, candidate_index, kind, http_status)`:
`http_status` exact `int` 100..599 iff `kind is HTTP_STATUS`. `ImageAcquisitionResult(poster,
fanart, thumb, extrafanart, failures)`: role-matched slots, exact tuples, pure `total_bytes`.
No model has a URL / header / cookie / body / exception / free-text field.

## 6. Policy (contract 7)

`ImageAcquisitionPolicy`: `request_deadline_seconds=15.0`, `max_redirects=5`,
`max_image_bytes=16 MiB`, `max_total_bytes=64 MiB`, `max_candidates_per_role=16`,
`max_extrafanart=12`; exact types, finite / `> 0`, `max_image_bytes <= max_total_bytes`
(`ImagePolicyError`). Enforced at runtime by the transport (deadline, redirects, per-image bytes)
and `acquire_images` (total bytes, candidates, extrafanart).

## 7. URL safety (contract 8)

`validate_image_url`: `type(url) is str` first (hostile `str` subclass: 0 hooks run); returns the
same object, never normalizes / strips / re-quotes. Only `http` / `https`; rejects relative,
`file:` / `data:` / `ftp:` / `javascript:`, userinfo, `localhost` / `*.localhost`, whitespace /
controls, backslash, `%` / non-ASCII / malformed hosts, non-canonical numeric hosts (`2130706433`,
`0x7f.1`, `127.1`, `0177.0.0.1`), and non-global IPs (private, loopback, link-local incl.
`169.254.169.254`, multicast, reserved, unspecified, shared, IPv4-mapped / 6to4 / NAT64 / Teredo
embedding). Reason-only `ImageUrlError`. **No DNS resolution; DNS rebinding is explicitly not
addressed** (8.5, 12.11).

## 8. Transport (contract 12)

`HttpxImageClient`: one `AsyncClient` per instance (created in `__init__`, never per request or at
import), `follow_redirects=False`, `trust_env=False`, fixed `Accept` / `Accept-Encoding: identity` /
`User-Agent` only, no auth / cookies / caller headers, server cookies never replayed, host
cross-check between httpx and the validator's parse. One send per hop (no retry). Lifecycle:
async context manager / idempotent `aclose()`; use after close -> `ImageClientClosedError`.
`ImageHttpResponse(status_code, content_type, content)`: builtin values only; body `b""` unless 200.

## 9. Redirects (contract 12.4)

301 / 302 / 303 / 307 / 308 handled manually. A response hook stops httpx before it parses
`Location` itself; the target is `urljoin`-resolved and re-validated with `validate_image_url`
**before** the next hop -- an unsafe target is never requested (tests assert the request list).
`max_redirects = N` follows N redirects; the (N+1)-th -> `ImageRedirectLimitError` without
requesting it (boundaries 0 / 1 / 5 / 6). Missing / blank `Location` -> `ImageRedirectError`.
Redirect bodies are never read.

## 10. Streaming bounds (contract 12.5-12.7)

Only a final 200 is streamed; other statuses return with the body unread (0 chunks pulled).
`Content-Encoding` must be identity. Chunks are counted before appending; exactly `max_bytes` is
accepted, `max_bytes + 1` stops immediately (no further chunk pulled). A well-formed
`Content-Length > max_bytes` rejects before reading (compared by length, never `int()` on huge
strings); malformed / lying values are ignored and the stream counter still applies. One
`asyncio.timeout` covers all hops + headers + body (not reset per hop); every timeout ->
`ImageTimeoutError`.

## 11. JPEG validation and dimensions (contract 13)

JPEG only (no Pillow, no transcoding). Content-Type: `image/jpeg|jpg|pjpeg` accepted;
`None` / `application/octet-stream` defer to bytes; any other explicit type ->
`CONTENT_TYPE_MISMATCH` even with a valid JPEG body. `inspect_jpeg`: single bounded pass -- SOI,
fill bytes, TEM / RSTn, length-checked segments, only the 13 real SOF markers (never DHT / JPG /
DAC), SOF / SOS header shapes, EOI at the very end; entropy data not scanned. Structural only: no
promise every decoder can decode. Dimensions from SOF: `0 < w, h <= 20000`, `w*h <= 100_000_000`
(`INVALID_DIMENSIONS`), judged after structure. Exact `bytes` / `str` boundary, 0 hostile hooks;
no internal exception escapes (all prefixes + 3000-case fuzz).

## 12. Orchestration and failure isolation (contract 14)

Roles `POSTER <- poster_urls`, `FANART <- fanart_urls`, `THUMB <- thumb_urls`,
`EXTRAFANART <- extrafanart`; no cross-role fallback. Strictly sequential in the order
poster -> fanart -> thumb -> extrafanart, candidates in tuple order, max one request in flight, each
candidate requested at most once. Per candidate: URL gate -> `get` -> 200 -> Content-Type -> JPEG ->
dimensions -> total cap -> `AcquiredImage`. Any failure is recorded as
`(role, candidate_index, kind[, http_status])` and the next candidate of the same role is tried;
a role failure never clears another role's success. Failure mapping is by exception type
(URL / redirect -> `INVALID_URL` / `UNSAFE_URL`; timeout, connection, redirect limit, too large;
other transport / client errors -> `TRANSPORT_ERROR`; non-200 -> `HTTP_STATUS` with the status;
Content-Type / JPEG / dimension failures keep their own kinds). Candidate shapes (exact tuple of
exact str, all four roles) are checked before any request -> `ImageInputError` naming only the
field. No deduplication.

## 13. Memory caps (contract 14.7-14.9)

* Per image: `max_image_bytes` (transport stream cap).
* Total: an image is accepted iff `current_total + new_size <= max_total_bytes` (exact boundary
  accepted); otherwise `TOTAL_BYTES_LIMIT` is recorded, the payload is dropped, and **no further
  request of any role** is made. Transient memory <= `current_total + max_image_bytes`.
* Candidates: `len > max_candidates_per_role` -> the role sends 0 requests, one
  `CANDIDATE_LIMIT` at `candidate_index = max_candidates_per_role`; no silent truncation.
* Extrafanart: after `max_extrafanart` successes processing completes normally (nothing further
  requested or recorded).

## 14. Sensitive data (contract 12.9, 14.12, 15)

Results hold only builtin values / images models: no URL, query token, `ImageHttpResponse`,
httpx object, exception, traceback, header, cookie, dict or list anywhere in the object graph.
All error messages are fixed text + reason enum; never a URL, Content-Type value, payload byte,
library message or exception `repr`; transport errors are never chained. Verified with
`?token=SUPERSECRET`, `SECRET_RESPONSE_BODY`, `SECRET_EXCEPTION_TEXT` sentinels.

## 15. Cancellation

`asyncio.CancelledError` (caller or client) propagates unchanged from both the transport and
`acquire_images`: never mapped, never recorded, no further candidate. `KeyboardInterrupt`,
`SystemExit`, `GeneratorExit` and other non-`Exception` `BaseException`s propagate. Only ordinary
`Exception`s are mapped.

## 16. Architecture (contract 10)

```text
fc2_organizer.images  foundation (__init__, errors, models, policy, urls, jpeg): stdlib only
fc2_organizer.images.transport   : + httpx            (the ONLY httpx importer)
fc2_organizer.images.acquisition : + images modules, transport Protocol / response, fc2_organizer.publication
```

Never: `fc2_metadata_core` (directly), `amane`, filesystem modules, `asyncio` fan-out in
acquisition. No reverse dependency (core, discovery, planning, publication, nfo never import
images). `import fc2_organizer` loads no images module; `import fc2_organizer.images` loads neither
`transport`, `acquisition`, `publication` nor httpx. Top-level subpackages are exactly
`{"discovery", "planning", "publication", "nfo", "images"}`. Enforced by
`tests/contract/test_images_architecture.py` (19 tests: module set, per-module allow-lists, AST
call bans, client construction site / flags, runtime import with network / core / amane blocked).

## 17. Synthetic gate (contract 15)

`tests/unit/images/test_image_synthetic_gate.py` (18 tests):

* 400 records (200 SUCCESS / 200 PARTIAL), 13 scenario families, 19 failure variants; every
  `ImageFailureKind` produced; extrafanart 0..6 candidates.
* Expected request order, roles, indices, kinds, statuses, bytes, width / height, SHA-256
  (hashlib over the fixture bytes), extrafanart order and `total_bytes` come from the case
  definitions -- not from production output. All 400 match.
* Determinism: every case re-run -> equal result and request order (fixed response script only;
  no claim about live responses).
* Sensitive-data graph walk over all 400 results: 0 secret / URL / live-object hits.
* Filesystem traps (`open`, `io.open`, `os`, `os.path`, `pathlib.Path`, `shutil`, `getcwd`) with a
  positive control: **0 hits**. No real network (fake client; reproduction B uses
  `httpx.MockTransport`).
* Cancellation / fatal regression.
* Mutation: 8 / 9 substep-4 acquisition mutants killed by the gate alone (the 9th, accepting
  `tuple` subclasses, cannot arise from valid records and is killed by
  `test_image_acquisition.py`). Earlier substeps were mutation-checked the same way (transport 3/3,
  JPEG 6/6, acquisition 9/9 in their own test files; URL exact-type 1/1).

## 18. Direct reproductions (all in the gate file, all pass)

```text
A  poster 404 -> second candidate valid           => second wins, failure (HTTP_STATUS, 404)
B  public URL 302 -> http://10.1.2.3/...           => private target never requested (real HttpxImageClient
                                                      over MockTransport); UNSAFE_URL; next candidate wins
C  valid JPEG declared image/png                   => CONTENT_TYPE_MISMATCH
D  malformed JPEG                                  => INVALID_JPEG
E  fanart would exceed max_total_bytes             => TOTAL_BYTES_LIMIT; thumb / extrafanart never requested
F  fanart timeout                                  => poster and thumb successes remain
G  ?token=SUPERSECRET failing (+ forged shape)     => no secret in result repr / str / failures / error
H  CancelledError from the client                  => the same exception object propagates; no next request
```

## 19. Tests

Targeted (`-p no:cacheprovider --basetemp=<job temp>`):

```text
tests/unit/images/test_image_models.py           59
tests/unit/images/test_image_policy.py           63
tests/unit/images/test_image_urls.py            102
tests/unit/images/test_image_transport.py       125
tests/unit/images/test_image_jpeg.py            119
tests/unit/images/test_image_acquisition.py      86
tests/unit/images/test_image_synthetic_gate.py   18
tests/contract/test_images_architecture.py       19
tests/contract/test_discovery_architecture.py    12
tests/contract/test_planning_architecture.py     13
tests/contract/test_publication_architecture.py  19
tests/contract/test_nfo_architecture.py          17
-------------------------------------------------
652 passed, 0 failed, 0 skipped
```

Full suite (`python -m pytest -q -p no:cacheprovider --basetemp=<job temp>`, PYTHONPATH=src):
**3811 passed, 14 skipped, 0 failed**. The skip count was 14 on every P4-C5 substep run
(3454 / 3583 / 3704 / 3793 / 3811 passed); no P4-C5 test is skipped. No P4-C1 / P4-C2 / P4-C3 /
P4-C4 / Phase 3 regression.

Observation (not a P4-C5 change): one earlier full-suite run on a loaded machine (96 s instead of
~50-60 s) failed `tests/unit/aggregation/test_agg_retry_execution.py::test_17_total_deadline_covers_attempt_backoff_and_retry_not_deadline_times_attempts`
(a wall-clock timing assertion in frozen Phase 3 code); that file passes in isolation (56 passed)
and in the subsequent full run. The same run exposed a test-order bug in the new gate file
(a function-local import after the architecture tests' `sys.modules` purge); fixed in the gate
test before the candidate commit.

## 20. Known limitations (documented in the contract, non-blocking)

* No DNS resolution / connection-time address check: a public hostname resolving to a private
  address is still connected to; DNS rebinding not addressed (8.5, 12.11).
* JPEG validation is structural only; entropy data / table contents are not decoded (13.3).
* `record.metadata` is trusted as far as `PublicationRecord` guarantees (`isinstance`); a hostile
  `NormalizedMetadata` subclass is the carried P4-C4-R-01 class of finding (14.2).
* Explicit non-scope (contract 16): filesystem writing / materialization, overwrite / collision,
  resize / crop / transcode, NFO modification, CLI / UI, persistence, Amane.

## 21. Blocking known issues

None.

## 22. Carried findings (unchanged by P4-C5)

```text
P4-C4-R-01 -- LOW
P4-C3-R-01 -- LOW
P4-C3-R-02 -- LOW
P4-C2-R1-02 -- LOW
OrganizePlan operation-graph hardening
overwrite executor semantics = NEVER
extended Windows reserved names
P4-C1-R-02..R-05
P2-R-05
P2-R-06
P2-R-07
C3-N1..N4
C4-N1
C4-R1-N1..N3
F3
F5
C5-R1-L1
fc2db_net release normalization = un-numbered upstream observation
```

Closed earlier, not re-carried: P4-C2 metadata identity gap, C2-L2, P2-R-10.

## 23. Hygiene

`git diff --check` clean over the Code Review Range and the Docs Review Range; working tree clean
after push; Remote Head == Docs Head.

## 24. Status

```text
Independent Review = REQUIRED
P4-C5              = NOT CLOSED
Phase 4            = NOT CLOSED
```

The developer does not declare P4-C5 or Phase 4 closed.


---

# R1 Remediation -- P4-C5-R-01 (HIGH), P4-C5-R-02 (MEDIUM)

Sections above are the unchanged original handoff. This section records R1 only:
no new feature, no other package touched.

```text
Branch                       = claude/phase4-c5-image-acquisition
R1 Base                      = d8831d255e7a509fe24544ef5e1652d6c2fdb513
Previous Reviewed Code Head  = 3ef881b416439accf634ce792723b49d01db0d64
R1 Code Review Candidate     = 65036e3857f87d821b5b282d7162ddbdabd42773
R1 Docs Head                 = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C5_HANDOFF.md`>
Remote Head                  = <== R1 Docs Head after push>

R1 Code Review Range: d8831d255e7a509fe24544ef5e1652d6c2fdb513..65036e3857f87d821b5b282d7162ddbdabd42773
R1 Docs Review Range: 65036e3857f87d821b5b282d7162ddbdabd42773..<R1 Docs Head>
```

Verified before any change: `git fetch --all --tags`; HEAD ==
`origin/claude/phase4-c5-image-acquisition` == `d8831d2`; working tree clean. No
rebase / amend / squash / force push.

## R1.1 Changed files (R1 Code Review Candidate, 3 files, +407 / -17)

```text
fc2-organizer/src/fc2_organizer/images/transport.py                  (fix)
fc2-organizer/tests/unit/images/test_image_transport.py              (+47 regression tests, appended)
fc2-organizer/docs/specifications/PHASE4_IMAGE_ACQUISITION_CONTRACT.md (12.7 note, new 12.9a)
```

Not touched: `errors.py` (no new error class needed), `urls.py`, `jpeg.py`,
`acquisition.py`, `models.py`, `policy.py`, every other Phase 4 package.

## R1.2 P4-C5-R-01 -- cleanup exception boundary: FIXED

Root cause: `_follow` closed the response in a bare `finally: await
response.aclose()`, and `_read_body` closed its byte iterator the same way. An
ordinary exception raised by cleanup therefore (a) replaced an already-returned
value (non-200 / `TOO_LARGE` path), and so escaped `_map_exception` as a raw
httpx exception carrying the message, `httpx.Request` and URL/token; and (b)
replaced a propagating `CancelledError`. After (b), `asyncio.timeout` never
turned the deadline into `ImageTimeoutError`, and caller cancellation was lost.

Fix (`transport.py`):

* `_cleanup(close)` runs one cleanup step. An ordinary `Exception` becomes a
  fresh error value through the existing type-based `_map_exception` (httpx
  `NetworkError` incl. `CloseError` / `ProtocolError` / `ProxyError` ->
  `ImageConnectionError`; timeout family -> `ImageTimeoutError`; anything else ->
  `ImageTransportError`). It is created, never raised, so it has no cause,
  context or traceback. A `BaseException` raised by the cleanup itself
  propagates.
* The response-handling body moved into `_response_outcome`, which returns every
  ordinary failure as a value. `_follow` then either (a) closes normally, or (b)
  on `BaseException` closes via `_cleanup` and re-raises the **original object**
  (bare `raise`).
* Precedence: an existing error value wins over a cleanup error. A cleanup
  error replaces only a successful `ImageHttpResponse` (fail closed). A
  propagating cancellation / fatal always wins over an ordinary cleanup error.
* `_read_body` uses the same pattern for the byte iterator (`too_large` flag
  instead of returning from inside the `try`).

## R1.3 Cancellation / fatal preservation

* Primary `CancelledError`, custom `BaseException`, `KeyboardInterrupt`,
  `SystemExit` and `GeneratorExit` combined with a failing cleanup (httpx
  `CloseError` or `RuntimeError`): the raised object `is` the primary. That is
  10 parametrized cases, captured in the same task for identity.
* Real caller `task.cancel()` during the body plus a failing cleanup:
  `CancelledError` propagates.
* Deadline expiry during the body plus a failing cleanup (httpx or ordinary):
  `ImageTimeoutError`.
* Cancellation / fatal raised *by cleanup itself* (`_R1Fatal`,
  `KeyboardInterrupt`, `CancelledError`) propagates as the same object: never
  swallowed, never mapped.

## R1.4 P4-C5-R-02 -- huge deadline: FIXED

The accepted domain is unchanged: `ImageAcquisitionPolicy(request_deadline_seconds=10**400)`
is still valid, and `get()` still accepts any exact positive `int`.
`_deadline_delay` converts the deadline to a float once, by exception type
(`OverflowError` of the conversion, no message sniffing). If it cannot be
represented (`10**400`, `10**309`, `2**1024`), `get()` sends **nothing** and
raises a fresh fixed-message `ImageTransportError` (`TRANSPORT_ERROR`) with cause
and context `None`. Before R1 these cases leaked `OverflowError` from
`asyncio.timeout`. The acquisition layer already records any `Exception` from
`get()` as a per-candidate failure, so it now records `TRANSPORT_ERROR` for
such a policy. Representable deadlines are unchanged: `15.0`, `1`, `5`, `3600`,
`10**300`, `10**308`, `1e300` and `sys.float_info.max` all succeed with exactly
one request.

## R1.5 New regression tests (`test_image_transport.py`, 47 cases)

Secrets used: the exception message `SECRET_EXCEPTION_TEXT`, plus
`https://example.com/x.jpg?token=SUPERSECRET` as both the message URL and the
exception's `httpx.Request`. `assert_r1_clean` checks:
* `str` / `repr` / `args` contain no secret, token, host, httpx name or
  `<Request` / `<Response`;
* `__cause__` and `__context__` are `None`;
* an object-graph walk (args, cause, context, `__dict__`, notes, reason) holds no
  `httpx.Request` / `httpx.Response` / `httpx.HTTPError` and no exception other
  than itself;
* the traceback holds no worker / cleanup frame and no frame local of those
  types.

| # | scenario | expected |
|---|---|---|
| 1 | non-200 (404/500/204) + httpx `CloseError` on close | `ImageConnectionError`, 0 body chunks read |
| 1b | non-200 + `RuntimeError` on close | `ImageTransportError` |
| 2 | 200 success + `CloseError` / `ValueError` on close | `ImageConnectionError` / `ImageTransportError` |
| 3 | `TOO_LARGE` (streamed and declared) + `CloseError` | `ImageResponseTooLargeError` (primary kept) |
| 3b | mid-stream `ReadError` + cleanup `RuntimeError` | `ImageConnectionError` (primary kept) |
| 4 | deadline during body + `CloseError` / `RuntimeError` | `ImageTimeoutError` |
| 5 | caller cancel + `CloseError`; primary `CancelledError` + cleanup error | `CancelledError`, same object |
| 6 | primary custom fatal / `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` + cleanup error | same object |
| 7 | cleanup itself raises fatal / `KeyboardInterrupt` / `CancelledError` | same object, not mapped |
| 8 | `_cleanup` maps by type (misleading messages) and returns values with no cause / context / traceback | type decides |
| 9 | successful cleanup | response unchanged |
| R2 | `10**400`, `10**309`, `2**1024` | `ImageTransportError`, no request, no `OverflowError` |
| R2 | policy still accepts `10**400`; `_deadline_delay` is type-based | domain unchanged |
| R2 | `15.0`, `1`, `5`, `3600`, `10**300`, `10**308`, `1e300`, `float max` | success, one request |

Mutation check: the 47 cases were run against the `d8831d2` `transport.py`.
**26 fail** with a raw `httpx.CloseError` (secret message), `RuntimeError`,
`OverflowError` or a missing helper. The 21 that pass there are the expected
controls: 200-path close (httpx closes inside iteration and was already
mapped), fatal-from-cleanup, representable deadlines, policy domain and
successful cleanup.

## R1.6 Tests

```text
New regression only : python -m pytest tests/unit/images/test_image_transport.py -k "r1 or r2" -q
                      47 passed
Targeted            : python -m pytest tests/unit/images tests/contract/test_images_architecture.py -q
                      632 passed, 0 failed, 0 skipped
Full suite          : python -m pytest -q
                      3852 passed, 14 skipped, 0 failed
```

All runs were from `fc2-organizer/` with `-p no:cacheprovider
--basetemp=<job-owned tmp>` (known local pytest temp-permission quirk). The 14
skips are the same count as before R1: the pre-existing Windows-symlink-privilege
and POSIX-only path-form skips. No images test is skipped.

## R1.7 Carried / unchanged

No finding other than P4-C5-R-01 / R-02 was addressed. Every carried debt listed
above is unchanged, and so is the un-numbered fc2db_net release observation.

## R1.8 Hygiene

```text
git diff --check (R1 code range, R1 docs range) -> clean
git status --porcelain after push             -> clean
```

## R1.9 Status

```text
P4-C5-R-01          = FIXED (pending independent re-review)
P4-C5-R-02          = FIXED (pending independent re-review)
Independent Re-review = REQUIRED
P4-C5               = NOT CLOSED
Phase 4             = NOT CLOSED
```


---

# Final Closure -- P4-C5 Image Acquisition

Sections above are unchanged. This section is append-only and docs-only: it records
the final closure of P4-C5. No code, test or contract file is touched, and no later
package is started.

## F.1 Closure record

```text
Phase                        = 4
Package                      = P4-C5 Image Acquisition
Branch                       = claude/phase4-c5-image-acquisition
Status                       = CLOSED
Final Review                 = Incremental Level 1 PASS
Final Reviewed Code Head     = 65036e3857f87d821b5b282d7162ddbdabd42773
Previous Docs Head           = b0ee039a83228dc42d900b6423e2a4f0274a7926
Closure Docs Head            = <this commit; its parent is the Previous Docs Head>
```

Verified before this change: `git fetch --all --tags`; HEAD ==
`origin/claude/phase4-c5-image-acquisition` == `b0ee039`; working tree clean. No
rebase / amend / squash / force push.

## F.2 Review history

```text
Initial Level 1 review      (code 3ef881b, docs d8831d2)
  P4-C5-R-01 -- HIGH    response / stream cleanup raising an ordinary exception bypassed
                        the image transport error boundary: raw httpx exception,
                        httpx.Request and the token-bearing URL could escape.
  P4-C5-R-02 -- MEDIUM  a contract-accepted huge deadline (e.g. 10**400) leaked a bare
                        OverflowError.

R1 remediation
  R1 Code Review Candidate = 65036e3857f87d821b5b282d7162ddbdabd42773
  R1 Docs Head             = b0ee039a83228dc42d900b6423e2a4f0274a7926

Independent Incremental Level 1 re-review (d8831d2..65036e3, 65036e3..b0ee039)
  Verdict = PASS
  P4-C5-R-01 = CLOSED
  P4-C5-R-02 = CLOSED
```

Both findings are closed and are no longer carried.

## F.3 R1 independent evidence (reviewer's own results)

```text
Context Handshake                  = PASS
Diff Scope                         = PASS
P4-C5-R-01                         = CLOSED
Cleanup Error Mapping              = PASS
Sensitive-Data Boundary            = PASS
Cancellation / Fatal Preservation  = PASS
P4-C5-R-02                         = CLOSED
Huge Deadline Boundary             = PASS
Normal Deadline Regression         = PASS
Transport Regression               = PASS

Independent probes                 = 434 PASS / 0 FAIL
Targeted: test_image_transport.py  = 166 passed / 0 failed / 0 skipped
Targeted: images + architecture    = 632 passed / 0 failed / 0 skipped
Full Suite                         = 3852 passed / 14 skipped / 0 failed
git diff --check                   = clean on both R1 code and docs ranges

New Findings                       = NONE
Blocking Findings                  = NONE
```

## F.4 Final package state

```text
URL safety                  = CLOSED / accepted
Redirect safety             = CLOSED / accepted
Binary streaming bounds     = CLOSED / accepted
Deadline handling           = CLOSED / accepted
Transport error boundary    = CLOSED / accepted
JPEG / Content-Type         = CLOSED / accepted
Dimension validation        = CLOSED / accepted
Candidate ordering          = CLOSED / accepted
Role isolation              = CLOSED / accepted
Candidate limits            = CLOSED / accepted
Extrafanart limit           = CLOSED / accepted
Total-result memory cap     = CLOSED / accepted
Cancellation                = CLOSED / accepted
Sensitive-data exclusion    = CLOSED / accepted
Architecture boundary       = CLOSED / accepted
Synthetic gate              = CLOSED / accepted
```

## F.5 Documented non-blocking boundaries (not findings)

These are known boundaries recorded in the contract (see section 20). They are not
new findings and do not block P4-C5:

* DNS rebinding: not defended in P4-C5.
* JPEG validation: structural only, not a full decoder guarantee.
* Hostile `NormalizedMetadata` subclass: covered by the carried P4-C4-R-01 context.

## F.6 Carried findings

```text
P4-C4-R-01 -- LOW
P4-C3-R-01 -- LOW
P4-C3-R-02 -- LOW
P4-C2-R1-02 -- LOW
OrganizePlan operation-graph hardening
overwrite executor semantics = NEVER
extended Windows reserved names
P4-C1-R-02..R-05
P2-R-05
P2-R-06
P2-R-07
C3-N1..N4
C4-N1
C4-R1-N1..N3
F3
F5
C5-R1-L1
fc2db_net release normalization = un-numbered upstream observation
```

Not carried (CLOSED in P4-C5): P4-C5-R-01, P4-C5-R-02.
Closed earlier, not re-carried: P4-C2 metadata identity gap, C2-L2, P2-R-10.

## F.7 Final status

```text
P4-C5-R-01    = CLOSED
P4-C5-R-02    = CLOSED
New Findings  = NONE
Blocking      = NONE
Targeted      = 632 passed / 0 failed / 0 skipped
Full Suite    = 3852 passed / 14 skipped / 0 failed
P4-C5         = CLOSED
Phase 4       = NOT CLOSED
Next Package  = NOT STARTED
```
