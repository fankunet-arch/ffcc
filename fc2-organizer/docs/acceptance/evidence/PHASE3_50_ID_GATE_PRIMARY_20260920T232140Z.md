# Phase 3 C3 - 50-ID coverage gate (PRIMARY run)

- Run kind: **primary** (the formal acceptance result)
- Started / finished (UTC): 2026-09-20T23:21:40+00:00 / 2026-09-20T23:25:41+00:00
- Code head: `bb05b46e8ed896843d6f501bac09e892c676d031` (working tree clean: True)
- Set file: `docs/acceptance/PHASE3_50_ID_SET.json` sha256 `dc6f4af58b3af3df0fe84c6e704be38ae048ecb286333df929fbcd484a78c9a8`; last commit touching it `bb05b46e8ed896843d6f501bac09e892c676d031`
- Config: order ['fc2db_net', 'javdb', 'av123'], max_concurrency 3, deadline 20.0s/source, RetryPolicy {'max_attempts': 2, 'initial_backoff_seconds': 1.0, 'backoff_multiplier': 2.0, 'max_backoff_seconds': 5.0, 'retryable_error_kinds': ['connection_error', 'decode_error', 'http_server_error', 'network_error', 'timeout']}, 4.0s between IDs (sequential)

## Result

**covered 49 / 50 = 98.0%** (threshold >= 45/50 = 90.0%) -> **NUMERIC THRESHOLD MET**

Aggregate statuses: {'failed': 1, 'success': 49}
Covered but only PARTIAL (a source failed operationally): none
Live retries observed: **0**; M1 violations (BLOCKED after >1 attempt): **0**

## Source-level statistics (final results)

| source | ids | success | not_found | blocked | rate_limited | network_error | parse_error | invalid_response | attempts | ids retried | mean engine ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| av123 | 50 | 44 | 6 | 0 | 0 | 0 | 0 | 0 | 50 | 0 | 207 |
| fc2db_net | 50 | 27 | 23 | 0 | 0 | 0 | 0 | 0 | 50 | 0 | 895 |
| javdb | 50 | 40 | 10 | 0 | 0 | 0 | 0 | 0 | 50 | 0 | 284 |

## Uncovered IDs

| number | aggregate | per-source [status, error_kind, attempts] |
|---|---|---|
| FC2-4493606 | failed | {'fc2db_net': ['not_found', 'not_found', 1], 'javdb': ['not_found', 'not_found', 1], 'av123': ['not_found', 'not_found', 1]} |

## Retry events

0 live retries observed.

## Per-ID results

| number | aggregate | covered | title | fc2db_net | javdb | av123 | ms |
|---|---|---|---|---|---|---|---|
| FC2-1042815 | success | yes | yes | successx1 | successx1 | not_foundx1 | 3063 |
| FC2-1097500 | success | yes | yes | not_foundx1 | successx1 | successx1 | 844 |
| FC2-1261799 | success | yes | yes | successx1 | successx1 | successx1 | 656 |
| FC2-1395953 | success | yes | yes | not_foundx1 | successx1 | successx1 | 765 |
| FC2-1528279 | success | yes | yes | successx1 | successx1 | successx1 | 1094 |
| FC2-1692217 | success | yes | yes | not_foundx1 | successx1 | successx1 | 719 |
| FC2-1713543 | success | yes | yes | successx1 | successx1 | successx1 | 1094 |
| FC2-1737461 | success | yes | yes | not_foundx1 | successx1 | successx1 | 718 |
| FC2-1782986 | success | yes | yes | successx1 | successx1 | successx1 | 1156 |
| FC2-1817510 | success | yes | yes | not_foundx1 | successx1 | successx1 | 687 |
| FC2-1841311 | success | yes | yes | not_foundx1 | successx1 | successx1 | 703 |
| FC2-1858921 | success | yes | yes | successx1 | successx1 | successx1 | 1078 |
| FC2-1879883 | success | yes | yes | not_foundx1 | successx1 | successx1 | 735 |
| FC2-1940353 | success | yes | yes | successx1 | successx1 | successx1 | 1125 |
| FC2-1977836 | success | yes | yes | successx1 | successx1 | successx1 | 1218 |
| FC2-2050468 | success | yes | yes | successx1 | successx1 | successx1 | 657 |
| FC2-2086710 | success | yes | yes | successx1 | successx1 | successx1 | 1203 |
| FC2-2172250 | success | yes | yes | not_foundx1 | successx1 | successx1 | 813 |
| FC2-2278260 | success | yes | yes | not_foundx1 | successx1 | successx1 | 860 |
| FC2-2570996 | success | yes | yes | not_foundx1 | successx1 | successx1 | 906 |
| FC2-2629560 | success | yes | yes | not_foundx1 | successx1 | successx1 | 781 |
| FC2-2733270 | success | yes | yes | not_foundx1 | successx1 | successx1 | 812 |
| FC2-2807093 | success | yes | yes | not_foundx1 | successx1 | successx1 | 734 |
| FC2-2865991 | success | yes | yes | not_foundx1 | successx1 | successx1 | 829 |
| FC2-2909140 | success | yes | yes | not_foundx1 | successx1 | successx1 | 719 |
| FC2-2954603 | success | yes | yes | not_foundx1 | successx1 | successx1 | 750 |
| FC2-3078940 | success | yes | yes | not_foundx1 | successx1 | successx1 | 781 |
| FC2-3084171 | success | yes | yes | not_foundx1 | successx1 | successx1 | 828 |
| FC2-3119265 | success | yes | yes | not_foundx1 | successx1 | successx1 | 719 |
| FC2-3178581 | success | yes | yes | successx1 | successx1 | successx1 | 1219 |
| FC2-4070093 | success | yes | yes | not_foundx1 | not_foundx1 | successx1 | 781 |
| FC2-4134556 | success | yes | yes | successx1 | successx1 | successx1 | 1203 |
| FC2-4174411 | success | yes | yes | successx1 | successx1 | successx1 | 1078 |
| FC2-4266906 | success | yes | yes | successx1 | not_foundx1 | successx1 | 656 |
| FC2-4336025 | success | yes | yes | not_foundx1 | not_foundx1 | successx1 | 718 |
| FC2-4385140 | success | yes | yes | successx1 | not_foundx1 | successx1 | 1125 |
| FC2-4493606 | failed | **NO** | no | not_foundx1 | not_foundx1 | not_foundx1 | 781 |
| FC2-4499275 | success | yes | yes | successx1 | not_foundx1 | successx1 | 1078 |
| FC2-4547366 | success | yes | yes | successx1 | successx1 | successx1 | 1219 |
| FC2-4548410 | success | yes | yes | successx1 | not_foundx1 | successx1 | 1110 |
| FC2-4655045 | success | yes | yes | successx1 | not_foundx1 | not_foundx1 | 828 |
| FC2-4699133 | success | yes | yes | successx1 | successx1 | successx1 | 656 |
| FC2-4791899 | success | yes | yes | successx1 | successx1 | successx1 | 640 |
| FC2-4824605 | success | yes | yes | successx1 | not_foundx1 | not_foundx1 | 656 |
| FC2-4825061 | success | yes | yes | not_foundx1 | successx1 | successx1 | 688 |
| FC2-4835063 | success | yes | yes | successx1 | not_foundx1 | successx1 | 657 |
| FC2-4972767 | success | yes | yes | successx1 | successx1 | not_foundx1 | 640 |
| FC2-4976588 | success | yes | yes | successx1 | successx1 | not_foundx1 | 657 |
| FC2-4978035 | success | yes | yes | successx1 | successx1 | successx1 | 656 |
| FC2-4979299 | success | yes | yes | successx1 | successx1 | successx1 | 657 |
