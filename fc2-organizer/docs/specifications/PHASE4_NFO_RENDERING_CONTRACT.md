# FC2 Organizer -- Phase 4 / P4-C4 Pure NFO Rendering Contract

Status: **frozen at P4-C4** (candidate; independent review pending).
Package: `fc2_organizer.nfo` (`__init__.py`, `errors.py`, `renderer.py`).

**Scope (frozen for this package):** `PublicationRecord -> str`. A pure,
deterministic renderer of a Kodi-compatible Movie NFO XML *text value*. It writes
no file, chooses no path, creates no directory, decides no overwrite, downloads /
validates / selects no image, and performs no HTTP, database, CLI, UI or Amane
work. See section 17.

## 1. Architecture and dependency direction

```text
fc2_organizer.nfo
    '-- fc2_organizer.publication   (public package only: PublicationRecord)
```

* Standard library: only `__future__`, `re`, `datetime` (`datetime.date.fromisoformat`,
  a pure parser; no clock is read). `errors.py` is stdlib-only (`__future__`).
* No direct dependency on `fc2_metadata_core` (any module), `fc2_organizer.planning`,
  `fc2_organizer.discovery`, `amane`, any XML/HTML library, or any filesystem /
  network / clock / randomness / environment / locale module. The record's
  metadata is read by attribute only; `PublicationRecord` is already the P4-C3
  frozen content boundary.
* No reverse dependency: nothing in `fc2_metadata_core`, `planning`, `discovery`
  or `publication` imports `fc2_organizer.nfo`.
* `fc2_organizer/__init__.py` does **not** eagerly import `nfo` (unchanged file).
  A bare `import fc2_organizer` loads neither `nfo`, `publication` nor any
  `fc2_metadata_core` module. Import explicitly:
  `from fc2_organizer.nfo import render_movie_nfo`.
* Top-level `fc2_organizer` subpackages are now exactly
  `{"discovery", "planning", "publication", "nfo"}`. The P4-C1 / P4-C2 / P4-C3
  scope-guard assertions were updated by one line each (package-set growth only);
  none of their forbidden-import guards, runtime blockers, allow-lists or
  reverse-dependency guards changed.

Enforced by `tests/contract/test_nfo_architecture.py`.

## 2. Public API

```python
from fc2_organizer.nfo import render_movie_nfo

render_movie_nfo(record: PublicationRecord) -> str
```

Also exported: the error classes of section 12. Nothing else (no `write`, `save`,
`download`, `execute`, `materialize`).

* Input: an **exact** `PublicationRecord` (`type(record) is PublicationRecord`).
  A subclass is rejected (`NfoInputError`): it could override `number` /
  `metadata` and run code inside the renderer.
* Output: an exact `str` that always satisfies
  `xml_text.encode("utf-8", errors="strict")`. Never `bytes`, an `ElementTree`,
  a DOM or a file object.

## 3. XML envelope (frozen)

```text
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  ...
</movie>
```

| property | value |
|---|---|
| XML version | `1.0` |
| declared encoding | `UTF-8` |
| standalone | `yes` |
| line ending | `\n` only (never `\r\n`; a `\r` inside a value is emitted as `&#13;`) |
| final newline | exactly one |
| indentation | 2 spaces per level (`movie` children 2, `actor` children 4) |
| root | `movie`, no attributes |
| empty elements | never emitted (an absent optional field is omitted, not `<x/>`) |
| DOCTYPE / entity declaration / comment / CDATA / processing instruction | never emitted (only the declaration line) |

The text is built by a small centralized serializer, not an XML library, so no
library formatting choice (attribute order, quoting, empty-tag style) can vary.
The exact text is frozen by golden tests.

## 4. Element order (frozen)

```text
1. title        mandatory, exactly one
2. uniqueid     mandatory, exactly one
3. plot         optional
4. runtime      optional
5. premiered    optional
6. studio       optional
7. actor        0..N
8. tag          0..N
```

Order never depends on dict / hash / set order.

## 5. Field mapping (frozen)

| NFO element | source | rule |
|---|---|---|
| `<title>` | `record.metadata.title` | exact `str`, non-blank; content kept verbatim (no strip, case-fold, Unicode normalization, HTML- or XML-unescape); XML-escaped only |
| `<uniqueid type="fc2" default="true">` | `record.number` | exact `str`, non-blank; never re-derived from a file name, never re-parsed; `type` / `default` are constants |
| `<plot>` | `metadata.plot` | `None` or `plot.strip() == ""` -> omitted; else verbatim (no summary, truncation or newline rewriting) |
| `<runtime>` | `metadata.runtime` | `None` -> omitted; exact `int` (not `bool`, not an `int` subclass), `>= 0`, whole minutes, decimal digits; `0` is rendered |
| `<premiered>` | `metadata.release` | `None` / whitespace-only -> omitted; else section 8 |
| `<studio>` | `metadata.studio` | `None` / whitespace-only -> omitted; else verbatim |
| `<actor><name/><order/></actor>` | `metadata.actors` | section 9 |
| `<tag>` | `metadata.tags` | section 9 |

Exactly one `<uniqueid>` is emitted.

## 6. Explicit non-mapping (frozen)

Never read, never rendered in any form (element, attribute, comment, custom tag):

```text
metadata.publisher          (not a studio fallback; no <publisher>)
metadata.poster_urls / thumb_urls / fanart_urls / extrafanart   (no <thumb>/<fanart>, no URL)
metadata.source_urls
metadata.external_ids       (no extra <uniqueid>; source-ID -> Kodi-ID mapping is not frozen here)
metadata.field_sources
record.aggregate_status
```

Artwork: the NFO carries no image reference. The OrganizePlan already targets
`poster.jpg` / `fanart.jpg` / `thumb.jpg` / `extrafanart/`; image selection and
content are a later package's concern.

## 7. Status isolation (frozen)

`SUCCESS` and `PARTIAL` records are both rendered. `aggregate_status` is never
read, so two records with the same plan and metadata that differ only in status
render **byte-identical** text. No `<status>`, no comment, no operational
diagnostics (`SourceResult`, traces, attempts, `error_detail` / `error_kind`,
retry or P2-R-07 timing, HTTP URL / body / headers / cookie) can reach the XML.

## 8. Release validation (frozen)

A non-blank `release` must be an exact `str` that fully matches ASCII
`[0-9]{4}-[0-9]{2}-[0-9]{2}` **and** is accepted by `datetime.date.fromisoformat`
(a real proleptic-Gregorian date, year 1..9999). It is rendered unchanged.

| input | result |
|---|---|
| `2026-09-19`, `2026-02-28`, `2024-02-29`, `2000-02-29` | rendered |
| `None`, `""`, `"   "` | omitted |
| `2026-02-30`, `2023-02-29`, `2026-13-01`, `2026-00-10`, `0000-01-01` | `NfoReleaseDateError` |
| `26-01-01`, `20260101`, `2026/09/19`, `2026-9-19`, `2026-09-19T00:00:00`, `" 2026-09-19"`, `"2026-09-19\n"`, full-width / Arabic-Indic digits, ISO week / ordinal forms | `NfoReleaseDateError` |

No guessing, no repair, no silent omission of a non-blank invalid value. No clock
is read.

## 9. Actor / tag ordering (frozen)

* `actors` / `tags` must be an exact `tuple`; each item an exact `str`
  (`None` or any other type is an error, never skipped).
* Items with `item.strip() == ""` are omitted; all others are kept in tuple
  order. No dedupe, no sort.
* Actor `<order>` is `0, 1, 2, ...` over the **emitted** actors (contiguous after
  omissions): `("Alice", "   ", "Bob")` -> Alice `0`, Bob `1`.
* Each actor is exactly `<actor>`, `<name>`, `<order>`, `</actor>` on four lines.
* Tags are `<tag>`, never `<genre>`.

## 10. XML character safety and escaping (frozen)

Allowed characters in any rendered value (XML 1.0 `Char`):

```text
U+0009  U+000A  U+000D  U+0020..U+D7FF  U+E000..U+FFFD  U+10000..U+10FFFF
```

Anything else (e.g. `U+0000`, `U+0001`, `U+0008`, `U+000B`, `U+000C`, `U+001F`,
surrogates `U+D800..U+DFFF`, `U+FFFE`, `U+FFFF`) in a value that would be
rendered raises `NfoXmlCharacterError` naming the field and the code point only
(`metadata.plot contains U+0000 ...`). Characters are never dropped, replaced or
ignored. Checked fields: title, number, plot, studio, each emitted actor / tag
(release is covered by its ASCII shape rule).

Blank-first rule: an optional value / collection item that is whitespace-only by
`str.strip()` is omitted *before* the character check (it is not rendered).
`str.strip()` treats `U+000B`, `U+000C` and `U+001C..U+001F` as whitespace, so an
optional value consisting only of such characters is omitted, not rejected; any
such character inside a rendered value is rejected.

Escaping: every text node goes through the single `_escape_text` helper:
`&` -> `&amp;`, `<` -> `&lt;`, `>` -> `&gt;`, `\r` -> `&#13;`. Quotes and
apostrophes are left literal (legal in text nodes). No `html.escape` /
`html.unescape` is ever called: `A &amp; B` in metadata is the literal string
`A &amp; B` and is rendered `A &amp;amp; B` (P2-R-10 separation of HTML and XML).
No CDATA.

## 11. Injection safety and hostile-text boundary (frozen)

* Metadata only ever becomes a text node. Tag names, attribute names and values,
  the declaration, DOCTYPE and entity declarations are module constants; no raw
  interpolation of unescaped data exists.
* Payloads such as `</title><evil>true</evil><title>`,
  `<!DOCTYPE movie [...]>`, `&xxe;`, `]]>`, `<![CDATA[...]]>`, `<!-- -->`,
  `" type="evil"` are rendered as text: the parsed document has no extra
  element, attribute, DTD or entity.
* Every textual value that could reach the XML (title, number, plot, release,
  studio, every actor / tag item) must satisfy `type(value) is str`. A `str`
  subclass raises `NfoMetadataError` **before** any method is invoked on it:
  none of its `__str__`, `__repr__`, `__format__`, `__eq__`, `__hash__`, `strip`,
  `replace`, `encode`, `translate`, ... hooks is called. `runtime` must satisfy
  `type(value) is int`.
* Defensive shape validation (forged records via `object.__new__` /
  `object.__setattr__`): every attribute the renderer reads is read inside a
  guard; any failure becomes an `NfoMetadataError` (never a bare
  `AttributeError` / `TypeError` / `UnicodeEncodeError` / `ValueError`), raised
  `from None`. `NormalizedMetadata` and `PublicationRecord` are unchanged.

## 12. Error taxonomy (`errors.py`)

| error | base | raised when |
|---|---|---|
| `NfoError` | `Exception` | base of all below |
| `NfoInputError` | `NfoError`, `TypeError` | input is not an exact `PublicationRecord` |
| `NfoMetadataError` | `NfoError`, `ValueError` | a used field has an unrenderable shape (wrong / subclass type, list instead of tuple, negative or non-`int` runtime, unreadable attribute, blank title / number) |
| `NfoReleaseDateError` | `NfoMetadataError` | non-blank release not an exact real `YYYY-MM-DD` date |
| `NfoXmlCharacterError` | `NfoMetadataError` | a rendered value contains a non-XML-1.0 character |

Messages contain only field names (`metadata.actors[2]`), Python type names and
code points. They never contain a title, plot, actor, tag, studio or release
value. No NFO error is chained (`__cause__ is None`).

## 13. Purity and determinism (frozen)

`render_movie_nfo` does not mutate the record, keeps no global mutable state, and
reads no environment variable, locale, timezone, cwd, filesystem, network, clock,
`random`, `uuid` or `os.urandom`. The same record rendered 100 times gives 100
identical strings; equal records give equal strings. Proven by rendering (success,
minimum, invalid date, invalid character, invalid input, forged shape, and the
whole synthetic gate) with all of these trapped; each trap category has a positive
control proving it fires. `date.fromisoformat` is intentionally not trapped.

## 14. Synthetic gate

`tests/unit/nfo/test_nfo_synthetic_gate.py`: 400 varied records (SUCCESS / PARTIAL,
5-8 digit numbers, Unicode / XML-special / injection titles, plot / no plot,
runtime None / 0 / N, release / none, studio / none, 0..4 actors with blanks and
duplicates, 0..3 tags, provenance / image / source-URL sentinels on every third)
plus 20 records produced by the real `prepare_publication` over real merged
aggregates carrying traces and `error_detail`. Each is rendered twice under all
traps (identical), strictly UTF-8 encoded, parsed (`root == movie`,
`title == metadata.title`, `uniqueid == record.number`, every optional element,
actor order and tag list checked against the record's metadata), and checked for
the absence of every sentinel and status literal. Every gate record re-rendered
with the opposite status is byte-identical.

## 15. Architecture test

`tests/contract/test_nfo_architecture.py`: allowed-import AST scan (publication +
`__future__` / `re` / `datetime`), no direct core / sources / aggregation / batch /
resource-control / http / discovery / planning / Amane / XML / I/O import, no I/O,
clock, `escape` / `unescape` / CDATA-style call, stdlib-only `errors.py`, no
reverse dependency, no eager import in `fc2_organizer/__init__.py`, bare
`import fc2_organizer` loads no nfo / publication / core module, explicit import
renders end to end with `amane` blocked, exact public API, exact package set.

## 16. Test matrix

| # | requirement | test (`tests/unit/nfo/`) |
|---|---|---|
| 1 | minimum record | `test_nfo_render.py::test_01_*` |
| 2 | full metadata exact + parsed | `test_02_*` (golden + parser) |
| 3-7 | Unicode, `&`, `<>`, quotes, non-BMP | `test_03_*` .. `test_07_*` |
| 8-10 | final newline, no CR, root / envelope | `test_08_*` .. `test_10_*` |
| 11-24 | optional fields | `test_11_12_*` .. `test_24_*`, `test_optional_elements_keep_frozen_relative_order_*` |
| 25-33 | actors / tags | `test_25_26_*` .. `test_33_*` |
| 34-38 | non-mapping | `test_34_*` .. `test_38_*`, `test_publisher_is_never_used_as_studio_fallback`, `test_no_sentinel_of_any_kind_leaks` |
| 39-42 | status isolation | `test_39_40_*`, `test_41_*` (model + real `prepare_publication`), `test_42_*` |
| 43-55 | XML character boundary | `test_nfo_xml_safety.py::test_43_48_*`, `test_49_55_*`, `test_illegal_character_propagates_from_every_rendered_text_field` (title / plot / studio / actor / tag) |
| hostile | `str` subclass, zero hook calls | `test_hostile_str_subclass_is_rejected_without_calling_any_hook` (title / plot / release / studio / actors / tags), `..._as_canonical_number_...`, positive control `test_hostile_hooks_really_are_armed` |
| 56-65 | forged shapes | `test_56_65_*`, `test_huge_runtime_*`, `test_metadata_missing_attribute_*`, `test_record_with_unset_slots_*`, `test_forged_*` |
| 66-70 | injection | `test_66_70_*` (10 payloads x 5 fields), `test_66_repro_b_*`, `test_67_70_*`, `test_69_*` |
| input / taxonomy | | `test_non_publication_record_input_*`, `test_publication_record_subclass_*`, `test_error_taxonomy_*`, `test_each_failure_category_*`, `test_error_messages_never_echo_*` |
| purity | no I/O / clock / random / env | `test_nfo_no_side_effects.py` (positive controls + 6 scenarios) |
| determinism | | `test_same_record_rendered_100_times_*`, `test_rendering_does_not_modify_the_record` |
| gate | | `test_nfo_synthetic_gate.py` |
| architecture | | `tests/contract/test_nfo_architecture.py` |

## 17. Out of scope for P4-C4

File path choice, file creation / writing, directory creation, overwrite
decisions, OrganizePlan execution, image download / validation / selection,
`<thumb>` / `<fanart>` / artwork, extra `<uniqueid>` mappings, `<genre>`,
`<publisher>`, HTTP, database, CLI, UI, JSON / diagnostics export, Amane. No
placeholder (`writer.py`, `filesystem.py`, `downloader.py`, `executor.py`) exists.

## 18. Known limitations

* `fc2db_net` passes schema.org `uploadDate` into `release` without shape
  validation; if a live page supplies an ISO datetime (`2026-09-19T...`), the
  renderer fails closed with `NfoReleaseDateError` for that film (by design:
  no repair here). Normalizing release at the adapter is a separate, not-yet-
  contracted change.
* The canonical number is checked for exact `str`, non-blank and XML-safe only;
  its canonical FC2 shape is guaranteed upstream (planning / P4-C3) and is not
  re-validated or re-parsed here.

## 19. Carried debts

Unchanged and still carried: P4-C3-R-01 (LOW), P4-C3-R-02 (LOW); P4-C2-R1-02
(LOW), OrganizePlan operation-graph hardening, overwrite executor semantics
(frozen `NEVER`), extended Windows reserved names; P4-C1-R-02..R-05; P2-R-05,
P2-R-06, P2-R-07 (not consumed: the renderer reads no `elapsed_ms`); C3-N1..N4;
C4-N1; C4-R1-N1..N3; F3; F5; C5-R1-L1.

Already closed and not re-carried: P4-C2 metadata identity gap, C2-L2, P2-R-10.
