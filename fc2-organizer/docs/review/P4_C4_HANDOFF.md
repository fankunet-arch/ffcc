# Phase 4 / P4-C4 Handoff -- Pure NFO Rendering

```text
Phase        = 4
Package      = P4-C4
Role         = Developer
Branch       = claude/phase4-c4-nfo-rendering
```

## 1. Coordinates

```text
Frozen Base                  = 8439da97f4e23e475a20619b4adb6bfd4ae30b6a
P4-C4 Code Review Candidate  = 526177b7c4279057633a2fb893fab79804c97835
P4-C4 Docs Head              = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C4_HANDOFF.md`>
Remote Head                  = <== Docs Head after push of this commit>

Code Review Range: 8439da97f4e23e475a20619b4adb6bfd4ae30b6a..526177b7c4279057633a2fb893fab79804c97835
Docs Review Range: 526177b7c4279057633a2fb893fab79804c97835..<Docs Head>
```

Verified before any change: `git fetch --all --tags`;
`origin/claude/phase4-c3-publication-boundary` == `8439da97f4e23e475a20619b4adb6bfd4ae30b6a`;
working tree clean (only the untracked harness `.claude/`); new branch
`claude/phase4-c4-nfo-rendering` created from that exact commit in an isolated
worktree. No rebase / amend / squash / force push.

The Code Review Candidate contains code, tests and the frozen contract
(`PHASE4_NFO_RENDERING_CONTRACT.md`). The Docs Head commit contains only this file.

## 2. Type

**NEW PACKAGE** (`fc2_organizer.nfo`) + three one-line package-set scope-guard
updates. No production file outside `fc2_organizer/nfo/` was touched.

## 3. Changed files (Code Review Candidate `526177b`, 15 files, +2204 / -3)

New (12):
```text
fc2-organizer/docs/specifications/PHASE4_NFO_RENDERING_CONTRACT.md
fc2-organizer/src/fc2_organizer/nfo/__init__.py
fc2-organizer/src/fc2_organizer/nfo/errors.py
fc2-organizer/src/fc2_organizer/nfo/renderer.py
fc2-organizer/tests/contract/test_nfo_architecture.py
fc2-organizer/tests/unit/nfo/__init__.py
fc2-organizer/tests/unit/nfo/_builders.py
fc2-organizer/tests/unit/nfo/_guards.py
fc2-organizer/tests/unit/nfo/test_nfo_no_side_effects.py
fc2-organizer/tests/unit/nfo/test_nfo_render.py
fc2-organizer/tests/unit/nfo/test_nfo_synthetic_gate.py
fc2-organizer/tests/unit/nfo/test_nfo_xml_safety.py
```

Modified (3, package-set growth only):
```text
fc2-organizer/tests/contract/test_discovery_architecture.py    +1 -1
fc2-organizer/tests/contract/test_planning_architecture.py     +1 -1
fc2-organizer/tests/contract/test_publication_architecture.py  +1 -1
```

Not touched: `fc2_organizer/__init__.py`, discovery / planning / publication
production code, `NormalizedMetadata`, `PublicationRecord`, all of
`fc2_metadata_core`, P4-C3 test names / trap coverage, Amane.

## 4. Public API

```python
from fc2_organizer.nfo import render_movie_nfo
render_movie_nfo(record: PublicationRecord) -> str
```

Input must be an exact `PublicationRecord` (subclass -> `NfoInputError`). Output is
an exact `str` that always strict-encodes as UTF-8. Also exported: `NfoError`,
`NfoInputError`, `NfoMetadataError`, `NfoReleaseDateError`, `NfoXmlCharacterError`.

## 5. Frozen XML shape

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>A &amp; B</title>
  <uniqueid type="fc2" default="true">FC2-1234567</uniqueid>
  <plot>Example &lt;plot&gt;</plot>
  <runtime>61</runtime>
  <premiered>2026-09-19</premiered>
  <studio>Example Studio</studio>
  <actor>
    <name>Alice</name>
    <order>0</order>
  </actor>
  <actor>
    <name>Bob</name>
    <order>1</order>
  </actor>
  <tag>Tag A</tag>
  <tag>Tag B</tag>
</movie>
```

`\n` only, exactly one final newline, 2-space indentation, order
title, uniqueid, plot, runtime, premiered, studio, actor*, tag*. Frozen by golden
tests (`GOLDEN_FULL`, `GOLDEN_MINIMAL`) and by parser round-trip tests.

## 6. Field mapping

| element | source | rule |
|---|---|---|
| title | `metadata.title` | exact `str`, non-blank, verbatim, XML-escaped only |
| uniqueid `type="fc2" default="true"` | `record.number` | exact `str`, non-blank; constants for attributes; not re-parsed |
| plot | `metadata.plot` | None / blank -> omitted |
| runtime | `metadata.runtime` | None -> omitted; exact `int` >= 0, whole minutes; `0` rendered |
| premiered | `metadata.release` | None / blank -> omitted; else exact real `YYYY-MM-DD` |
| studio | `metadata.studio` | None / blank -> omitted |
| actor(name, order) | `metadata.actors` | tuple order, blank omitted, order contiguous from 0, no dedupe |
| tag | `metadata.tags` | tuple order, blank omitted, no dedupe / sort, never `<genre>` |

## 7. Explicit non-mapping

Never read: `publisher` (no studio fallback, no `<publisher>`), `poster_urls`,
`thumb_urls`, `fanart_urls`, `extrafanart` (no `<thumb>` / `<fanart>` / URLs),
`source_urls`, `external_ids` (exactly one `<uniqueid>`), `field_sources`,
`aggregate_status`. No comments, no custom tags, no attributes other than the two
`uniqueid` constants. Sentinel tests (`SECRET-PUBLISHER`, `SECRET-SOURCE-URL`,
`SECRET-FIELD-SOURCE`, external-ID and image-URL sentinels, `error_detail` cookie /
bearer text) confirm none reaches the XML; adding all of them leaves the output
byte-identical to the golden text.

## 8. XML character safety

Allowed: U+0009, U+000A, U+000D, U+0020..U+D7FF, U+E000..U+FFFD,
U+10000..U+10FFFF. Anything else in a rendered value -> `NfoXmlCharacterError`
with field name + code point only (e.g. `metadata.tags[1] contains U+000B ...`);
never dropped / replaced / ignored. Tested for title, plot, studio, actor, tag
(and forged number) with U+0000, U+0001, U+0008, U+000B, U+000C, U+001F,
U+D800, U+DFFF, U+FFFE, U+FFFF; allowed boundary characters round-trip. CR is
emitted as `&#13;` so it survives parsing and never introduces a raw `\r`.
Blank-first rule: a whitespace-only optional value (by `str.strip()`, which
includes U+000B / U+000C / U+001C..U+001F) is omitted before the character check
(contract section 10).

## 9. Injection safety

One centralized `_escape_text` (`&`, `<`, `>`, `\r`) feeds every text node via
`_text_element`; tags / attributes / declaration are constants; no CDATA; no
`html.escape` / `html.unescape`. 10 payloads (`</title><evil>...`, DOCTYPE with
external entity, `&xxe;`, `A & B < C > D`, `]]>`, CDATA, XML declaration,
comment, attribute-breaking quotes) x 5 fields: parsed document has only the
frozen element names, attributes only on `uniqueid`, no `<evil>`, no DTD
(`minidom ... doctype is None`), and the payload is recovered verbatim as text.
`A &amp; B` renders as `A &amp;amp; B` (no HTML double-processing).

## 10. Hostile text boundary

`type(value) is str` for title, number, plot, release, studio and every actor /
tag item; `type(value) is int` for runtime; `type(...) is tuple` for actors /
tags. The check precedes any method call, so a `str` subclass overriding 29 hooks
(`__str__`, `__repr__`, `__format__`, `__eq__`, `__hash__`, `strip`, `replace`,
`encode`, `translate`, ...) yields `NfoMetadataError` with **0** hook calls, for
each of title / plot / release / studio / actors / tags and the canonical number
(positive control proves the hooks are armed). Forged shapes (`runtime=True/-1/
"60"/60.0/IntSubclass`, list actors / tags, non-str / `None` items, frozenset,
non-str plot / release / studio, blank / non-str title, unset slots, a
non-plan plan, a raising metadata property, `10**5000` runtime) all raise typed
`NfoMetadataError`, `from None`, never a bare exception.

## 11. Release validation

ASCII `[0-9]{4}-[0-9]{2}-[0-9]{2}` fullmatch + `date.fromisoformat`. Accepted:
`2026-09-19`, `2026-02-28`, `2024-02-29`, `2000-02-29`, `0001-01-01`, `9999-12-31`.
Rejected (`NfoReleaseDateError`): `2026-02-30`, `2023-02-29`, `2026-13-01`,
`2026-00-10`, `2026-04-31`, `0000-01-01`, `26-01-01`, `20260101`, `2026/09/19`,
`2026-9-19`, datetime form, leading / trailing space or newline, full-width and
Arabic-Indic digits, ISO week / ordinal, `+2026-09-19`, `Sep 19, 2026`. No clock
read.

## 12. Actor / tag ordering

`("Alice", "   ", "", "Bob", "\t")` -> Alice 0, Bob 1. `("Alice", "Bob", "Alice")`
keeps all three (0, 1, 2). Tags keep tuple order, duplicates and never become
`<genre>`.

## 13. Status isolation

`aggregate_status` is never read. Same plan + metadata, SUCCESS vs PARTIAL ->
byte-identical (model-built records, real `prepare_publication` records over real
aggregates with traces + `error_detail`, and every one of the 400 gate records
re-rendered with the flipped status). No `success` / `partial` / `status` /
comment text appears in any output.

## 14. Determinism

Same record x100 -> one distinct string; equal records -> equal strings; the record
is unchanged (`==` twin and identical `repr`) after rendering.

## 15. No filesystem / network / clock / random

`tests/unit/nfo/_guards.py::traps()` (scoped `MonkeyPatch.context`) traps builtins /
`io.open`, `os` fs calls incl. `getcwd` / `chdir`, `os.path` (`exists`, `realpath`,
`abspath`, ...), `pathlib.Path` (incl. `resolve`, `absolute`, `cwd`), `shutil`,
`socket`, `urllib.request.urlopen`, `httpx.Client/AsyncClient.send/request`,
`requests` (if present), `time.*`, `datetime.date.today`,
`datetime.datetime.now/today/utcnow` (and the renderer's own `date` binding),
`random.*`, `uuid.uuid1/uuid4`, `os.urandom`, `secrets.token_bytes`, `os.environ`,
`os.getenv`, `locale.*`. 36 parametrized positive controls (14 filesystem,
4 network, 13 clock / random, 5 environment) + 1 real `httpx.Client` control prove
each trap fires. `date.fromisoformat` is proven to still work under the traps. Rendered
under all traps: full, minimum, invalid date, invalid char, invalid input, forged
shape, and the whole synthetic gate; output equals the un-trapped output.

## 16. Architecture boundary

`fc2_organizer.nfo -> fc2_organizer.publication` (public package) + `__future__`,
`re`, `datetime`. `tests/contract/test_nfo_architecture.py` (17 tests): allowed
imports only; no direct `fc2_metadata_core` / sources / aggregation / batch /
resource_control / http / discovery / planning / Amane / XML / HTML / I/O import;
no I/O, clock, env, `escape` / `unescape` / CDATA call; stdlib-only `errors.py`; no
reverse dependency from core / planning / discovery / publication; no eager import
in `fc2_organizer/__init__.py`; bare `import fc2_organizer` loads no nfo /
publication / `fc2_metadata_core` module; explicit import renders with `amane`
blocked; exact public API; exact package set.

Architecture exact-set edits: the P4-C1 / P4-C2 / P4-C3 scope guards changed from
`{"discovery", "planning", "publication"}` to
`{"discovery", "planning", "publication", "nfo"}` -- one line each, nothing else
(`git diff 8439da9..526177b -- fc2-organizer/tests/contract/test_{discovery,planning,publication}_architecture.py`).

## 17. Synthetic gate

`test_nfo_synthetic_gate.py`: 400 model-built records + 20 real
`prepare_publication` records (420). Variation: SUCCESS / PARTIAL, 5-8 digit
numbers, 12 title families (Unicode, XML-special, injection, CR / tab / newline,
DOCTYPE + entity), 6 plots, runtime None / 0 / N, 6 releases, 5 studios, 6 actor
sets (0..4, blanks, duplicates), 5 tag sets, sentinel provenance / image / URL
fields on every third. Each rendered twice under all traps (identical), UTF-8
strict, parsed (`root == movie`, title, uniqueid, every optional element, actor
order, tags vs the record's metadata), no sentinel / status leak; flipped-status
re-render byte-identical. PASS.

## 18. Tests

Targeted:
```text
python -m pytest tests/unit/nfo tests/contract/test_nfo_architecture.py \
  tests/contract/test_discovery_architecture.py tests/contract/test_planning_architecture.py \
  tests/contract/test_publication_architecture.py tests/unit/publication \
  -q -p no:cacheprovider --basetemp=<job-owned tmp>
433 passed, 0 failed, 0 skipped
  unit/nfo: render 88, xml_safety 142, no_side_effects 46, synthetic_gate 3 (= 279)
  contract: nfo 17, discovery 12, planning 13, publication 19
  unit/publication: 93
```

Full suite (run from `fc2-organizer/`):
```text
python -m pytest -q -p no:cacheprovider --basetemp=<job-owned tmp>
3220 passed, 14 skipped, 0 failed
```

The 14 skips are pre-existing host / platform skips, none in P4-C4 code:
4 discovery symlink tests (Windows symlink privilege not held on this host) and
10 POSIX-only planning path forms. `--basetemp` / `-p no:cacheprovider` are used
because of the known local pytest temp-dir permission quirk. P4-C1, P4-C2, P4-C3
and Phase 3 suites: no regression.

Direct reproductions (plain `python` script outside pytest, importing the worktree
`src`):
```text
A exact minimal : '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<movie>\n  <title>Example</title>\n  <uniqueid type="fc2" default="true">FC2-1234567</uniqueid>\n</movie>\n'
B injection     : evil found = False | title = 'A </title><evil>true</evil>'
C U+0000        : NfoXmlCharacterError: metadata.title contains U+0000, which is not a legal XML 1.0 character
D status        : SUCCESS vs PARTIAL identical = True
E hostile       : title / plot -> NfoMetadataError ("must be an exact str, got H"), hooks called = []
F release       : 2024-02-29 -> rendered; 2026-02-30 -> NfoReleaseDateError
G provenance    : leaked sentinels = []
```

## 19. Known limitations

* `fc2db_net` stores schema.org `uploadDate` into `release` without shape
  validation; an ISO datetime value there makes that film's NFO render fail closed
  (`NfoReleaseDateError`). By design no repair here; adapter-side normalization
  would be a separate contracted change.
* The canonical number is checked as exact `str`, non-blank, XML-safe; its FC2
  shape is guaranteed upstream (planning / P4-C3) and not re-validated.
* Blank-first rule: whitespace-only optional values made of `str.strip()`
  whitespace control characters (U+000B, U+000C, U+001C..U+001F) are omitted
  rather than rejected, because they are not rendered (contract section 10).
* During development one real defect was caught by the forged-shape tests before
  commit: a `None` item inside a forged `actors` tuple was being treated as blank
  and skipped; items are now type-checked before blank omission.

## 20. Carried debts

Still carried, unchanged: P4-C3-R-01 (LOW), P4-C3-R-02 (LOW); P4-C2-R1-02 (LOW),
OrganizePlan operation-graph hardening, overwrite executor semantics (frozen
`NEVER`), extended Windows reserved names; P4-C1-R-02..R-05; P2-R-05, P2-R-06,
P2-R-07 (LOW / CARRIED -- no `elapsed_ms` is consumed); C3-N1..N4; C4-N1;
C4-R1-N1..N3; F3; F5; C5-R1-L1.

Closed earlier, not re-carried: P4-C2 metadata identity gap, C2-L2, P2-R-10.

## 21. Hygiene

```text
git diff --check (code candidate, staged)  -> clean (exit 0)
git status --porcelain after push           -> clean (empty)
```

## 22. Status

```text
Independent Review : REQUIRED
P4-C4              : NOT CLOSED
Phase 4            : NOT CLOSED
```

The developer does not declare P4-C4 PASS / CLOSED. No later package was started.
