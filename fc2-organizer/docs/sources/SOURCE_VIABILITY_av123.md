# SOURCE_VIABILITY - av123

- **Provider:** 123AV (123av.com)
- **Status:** `VERIFIED`
- **Decision:** ADOPT
- **Adapter:** `fc2_metadata_core.sources.adapters.av123.Av123Adapter`
- **Login/cookie needed:** not required
- **Cloudflare/anti-bot:** Cloudflare CDN present, no challenge observed; a challenge would map to `BLOCKED`
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

Server-rendered detail page per work at `/en/v/fc2-ppv-<digits>`; missing works are a clean HTTP 404. Complementary to FC2DB rather than a mirror: it carried works FC2DB did not and vice versa.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:57:55 | `https://123av.com/en/v/fc2-ppv-4825061` | 200 | `FC2-PPV-4825061 — [Face Revealed] Half-Japanese Beautiful Wi` | - | same |  |
| 12:57:57 | `https://123av.com/en/v/fc2-ppv-4824605` | 404 | `404 — 123AV` | - | same |  |

## Findings

- Fields: number+title from `<h1 class="watch__title">FC2-PPV-N — Title</h1>`; release date, duration and genres from the Details `<dl>`.
- Titles are the site's **English** rendering (machine-translated), not the Japanese original; recorded so Phase 3 can weight it below JP sources for `title`. Maker is always the generic `FC2`, so it is intentionally not mapped to `studio`/`publisher`. No cover or actors on the page (`og:image` is the site logo).
- The `<title>` tag double-encodes entities (`&amp;#039;`); the adapter reads the `<h1>` instead, which decodes correctly.
- Coverage on the 7-ID probe set: 3/7 (`4825061`, `4979299`, `4978035`). The weakest coverage of the three: a supplementary source, not a primary one.

## Adapter verification (Phase 2 Gate run, `tools/probe_sources.py adapter --source av123`, code `3a21c4b`)

Real HTTP through `HttpxTransport`, one request per lookup, about 2.5 s between lookups, no cookies. `SUCCESS` means the adapter's `SourceResult` met minimum success (canonical number + non-empty title).

| UTC | Number | HTTP | SourceStatus | Title (excerpt) | Fields populated |
|---|---|---|---|---|---|
| 13:02:47 | FC2-4825061 | 200 | **success** | [Face Revealed] Half-Japanese Beautiful Wife's F | number, title, release, runtime, tags, source_urls |
| 13:02:50 | FC2-4824605 | 404 | **not_found** |  |  |
| 13:02:53 | FC2-4979299 | 200 | **success** | Her dream is to be an elementary school teacher. | number, title, release, runtime, tags, source_urls |
| 13:02:56 | FC2-4976588 | 404 | **not_found** |  |  |
| 13:02:58 | FC2-1042815 | 404 | **not_found** |  |  |
| 13:03:01 | FC2-4978035 | 200 | **success** | [Discontinued] A beautiful woman from a very fam | number, title, release, tags, source_urls |
| 13:03:04 | FC2-4972767 | 404 | **not_found** |  |  |

An earlier identical run at code `45be2b7` (13:00:30-13:01:38) gave the same outcomes.

**Gate result:** 3 known-valid IDs returned `SUCCESS` (FC2-4825061, FC2-4979299, FC2-4978035); requirement is >=2.

## Requirement checklist

| Requirement (spec section 11 / Phase 2) | Met |
|---|---|
| Real HTTP request (not mocked) | yes |
| Formal adapter actually executed | yes |
| >=2 distinct known-valid IDs return `SUCCESS` with number + non-empty title | yes (3) |
| No private login / cookie | yes |
| No CAPTCHA / Cloudflare bypass | yes (none attempted; a challenge maps to `BLOCKED`) |
| Offline parser + contract tests | yes (`tests/unit/sources/adapters/test_adapter_av123.py`, real-response fixtures under `tests/fixtures/sources/`) |

## Risks / re-check trigger

Streaming-site operator; domain churn is likely (configurable `base_url`). Low coverage of small/older works.
