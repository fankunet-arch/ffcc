# Phase 3 C5 handoff

Status: **READY FOR PHASE 3 C5 INDEPENDENT REVIEW**. This is implementation evidence, not an independent PASS verdict.

## Heads and environment

- C5 Base: `83d7d6ff6e9ac21bcb3417cc7d814e9b91a814d0`
- C5 Code Head: `5ccd5feb3111bd7c465c65389677d9f02f6e77aa`
- Python: 3.12.14
- Baseline: 1927 collected, 1927 passed, 0 failed, 0 skipped.
- C5: 1956 collected, 1956 passed, 0 failed, 0 skipped (`pytest -v` and `pytest -q`).
- Focused: resource control 16 passed; batch 324 passed; aggregation 761 passed; F4 contract 46 passed.

## Resource domain and host semantics

`SourceResourceGovernor` is an explicitly injected domain. Two engines and two
batch schedulers sharing one governor share host and breaker state. A second
governor has independent capacity. Host keys are `(canonical hostname,
effective port)`, from validated adapter base URLs: lowercase DNS without a
terminal dot or compressed IP literal, and explicit/default HTTP 80 or HTTPS
443 port. Paths do not affect the key. `HostPolicy` is frozen; default limit 3,
range 1..64, with immutable canonical per-host overrides. A permit wraps each
adapter fetch attempt and is released before retry backoff. Host queue time is
excluded from the source execution deadline; attempts and backoff remain in it.

The two-scheduler shared-governor test observed a global host peak of 3,
while two separate governors observed process peak 6. Two different sources
on one host shared peak 2 but had independent circuits. Different hosts
reached 2 + 3 simultaneous fetches. Cancellation of 60 of 100 host waiters
left full capacity; cancellation inside fetch released permit and probe slot.

## Circuit state machine

Breaker domain is `source_id`. `BreakerPolicy` is frozen: failure threshold 3,
open duration 30 seconds, half-open maximum one probe by default. States are
CLOSED, OPEN, HALF_OPEN. Final SUCCESS and NOT_FOUND are healthy. Final BLOCKED,
RATE_LIMITED, NETWORK_ERROR, PARSE_ERROR, and INVALID_RESPONSE count once as
failures after retries. Cancellation and fatal BaseException abandon admission
without a health observation. OPEN returns NETWORK_ERROR / CIRCUIT_OPEN with
zero adapter attempts; CIRCUIT_OPEN is outside the retry-eligible set. The
existing aggregation merge maps open plus success to PARTIAL, and all-open
to FAILED.

Admission tokens carry an epoch. A completion admitted in an earlier epoch
cannot close a newly opened circuit. After cooldown, 100 simultaneous calls
with `half_open_max_calls=1` produced one probe and 99 structured short
circuits. A failed probe restarts cooldown; a healthy probe closes. OPEN while
host queued is revalidated after the permit is acquired, before fetch.

The governor observes only final `SourceResult.status` and `error_kind`,
configured source/host identity, and monotonic time. It reads no
`SourceExecutionTrace` fields, error detail, response text, or fatal metadata.
Snapshots are immutable. State maps scale with configured hosts and sources;
active tokens exist only for live source executions.

## Offline gates

- 200 items, two BatchSchedulers, three sources, two hosts: PASS. Mixed SUCCESS,
  NOT_FOUND, NETWORK_ERROR then retry recovery, BLOCKED, RATE_LIMITED, and
  PARSE_ERROR. All items accounted for, host peaks within 2 and 3, OPEN
  suppresses network fetch, resource state remains two hosts/three sources.
  Separate deterministic tests cover cooldown, half-open recovery, stale
  completion, cancellation, and fatal cleanup.
- 10,000 items, shared governor, combined batch M=16, host limit=3: PASS.
  Observed host peak 3; scheduler item peak <=16; all accounted; governor
  retained one host and one source state, with zero in-flight at completion.

## Carry-forward and exclusions

- C2-L2: LOW / OPEN. C5 has no trace dependency.
- C4-N1: carried; BatchLineage is not durable provenance and is unused by C5.
- C4-R1-N1/N2/N3: carried.
- C3-N1..N4; P2-R-05/06/07/10; F3/F5: carried.
- Persistence, NFO writer, image downloader, filesystem rename/move, Amane
  adapter, GUI, Retry-After parsing, CAPTCHA bypass, proxy rotation: not started.
- Final 500-item acceptance and live large-batch scraping: not run.

READY FOR PHASE 3 C5 INDEPENDENT REVIEW

