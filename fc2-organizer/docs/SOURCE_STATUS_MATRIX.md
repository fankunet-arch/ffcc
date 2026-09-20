# SOURCE_STATUS_MATRIX.md

Status: **POPULATED** - every row comes from live probes recorded in
`docs/source-probes/PHASE2_PROBE_20260920.json` and detailed in `docs/sources/SOURCE_VIABILITY_<id>.md`.
Nothing here was filled from a search snippet, a remembered name, or an assumption that a site named in the spec is still live.

## Columns

| Column | Meaning |
|---|---|
| Source ID | Stable logical id (`SourceAdapter.source_id`); never changes with mirror domain. |
| Provider | Human-readable provider/site. |
| Status | `VERIFIED`, `PARTIAL`, `BLOCKED`, `RATE_LIMITED`, `DEAD`, `REJECTED`, `EXPERIMENTAL`. |
| Verified IDs | Probe-set numbers that returned `SourceStatus.SUCCESS` (number + non-empty title) through the real adapter in the Gate run. `-` = no adapter. |
| Cookie | Whether a private cookie/login is required for lookup. |
| CF | Whether a Cloudflare/anti-bot challenge was observed on the lookup path. |
| Adopted | Whether a real `SourceAdapter` exists. |

## Status matrix

| Source ID | Provider | Status | Verified IDs | Cookie | CF | Adopted |
|---|---|---|---|---|---|---|
| `fc2db_net` | FC2DB (fc2db.net) | **VERIFIED** | 4824605, 4979299, 4976588, 1042815, 4978035, 4972767 | not required | no | yes |
| `javdb` | JavDB (javdb.com) - public search listing only | **VERIFIED** | 4825061, 4979299, 4976588, 1042815, 4978035, 4972767 | not required (search listing) | no | yes |
| `av123` | 123AV (123av.com) | **VERIFIED** | 4825061, 4979299, 4978035 | not required | no | yes |
| `fc2_official` | FC2 Content Market (adult.contents.fc2.com) | **BLOCKED** | - | **login required** | no | no |
| `fd2ppv` | FD2 (fd2ppv.cc) | **BLOCKED** | - | unknown | **yes** (work pages) | no |
| `fc2db_com` | FC2DB (fc2db.com - `.com` sibling) | **BLOCKED** | - | unknown | **yes** | no |
| `javten` | JavTen (javten.com) | **BLOCKED** | - | unknown | **yes** | no |
| `supjav_missav` | SupJav (supjav.com) and MissAV (missav.ws) | **BLOCKED** | - | unknown | **yes** | no |
| `fc2ppvdb` | FC2PPVDB (fc2ppvdb.com) | **BLOCKED** | - | unknown | n/a (IP-blocked here) | no |
| `onejav` | OneJAV (onejav.com) | **BLOCKED** | - | unknown | n/a (IP-blocked here) | no |
| `fc2cm` | FC2CM (fc2cm.com; spec name 'FC2CMADB') | **PARTIAL** | - | not required | no | no |
| `javbus` | JavBus (www.javbus.com) | **BLOCKED** | - | age-gate cookie | no (age gate) | no |
| `netflav` | Netflav (netflav.com) | **EXPERIMENTAL** | - | not required | no | no |
| `jav_guru` | Jav Guru (jav.guru) | **REJECTED** | - | not required | no | no |
| `sukebei_nyaa` | Sukebei (sukebei.nyaa.si) | **REJECTED** | - | not required | no | no |

## Gate summary

- Provider entries investigated: **15** (fc2db.com is a sibling of fc2db.net; supjav/missav share one row). The >=5 floor is met; >=3 VERIFIED was reached.
- **VERIFIED: 3** (`fc2db_net`, `javdb`, `av123`): independent operators and hosts, different page formats. The Phase 2 Gate needs >=2; the strong target of 3 is met.
- FC2 Official was actually investigated and is **BLOCKED (login wall)**; several aggregator/index candidates were investigated beyond the three adopted.
- Two candidates (`fc2ppvdb`, `onejav`) could not be evaluated because of an ISP-level IP block on this network; they are *unverified*, not dead. Re-probe from another network before Phase 3 fixes its source list.
- Independence caveat: all three ultimately mirror FC2 Content Market data and all three sit behind Cloudflare's CDN. They are independent *services*, not independent *origins*; a Cloudflare-wide incident or an FC2 takedown wave would hit all three. Keep FC2 Official (login-gated) and the other documented reserves in mind for Phase 3.

## Per-ID coverage in the Gate run (7-ID probe set)

| ID | fc2db_net | javdb | av123 |
|---|---|---|---|
| FC2-4825061 | NOT_FOUND | SUCCESS | SUCCESS |
| FC2-4824605 | SUCCESS | NOT_FOUND | NOT_FOUND |
| FC2-4979299 | SUCCESS | SUCCESS | SUCCESS |
| FC2-4976588 | SUCCESS | SUCCESS | NOT_FOUND |
| FC2-1042815 | SUCCESS | SUCCESS | NOT_FOUND |
| FC2-4978035 | SUCCESS | SUCCESS | SUCCESS |
| FC2-4972767 | SUCCESS | SUCCESS | NOT_FOUND |

`NOT_FOUND` here is each site's own answer (a real 404 or no exact hit), never a transport failure.
