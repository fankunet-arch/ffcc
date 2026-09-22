# Phase 3 C5 resource control contract

Status: implementation contract for independent review.

## Resource domain and identity

Each `SourceResourceGovernor` is an explicit resource domain. Engines sharing one
governor share host permits and per-source circuit state across all aggregate
calls and batch schedulers. Separate governors are independent. No process-wide
singleton exists. A source is registered from its validated configured base URL
at engine construction. A host key is `(canonical hostname, effective port)`:
DNS names are lowercase without a terminal dot; IP literals use compressed
canonical form; omitted ports mean 443 for HTTPS and 80 for HTTP. Paths do not
contribute. Userinfo, query, and fragment are forbidden by base URL validation.

## Host permits and deadlines

Every adapter fetch attempt acquires one host permit and releases it in `finally`.
Retry backoff does not hold a permit. The per-source deadline includes attempts
and backoff, but excludes time in the host permit queue. Cancellation while
queued removes the waiter; cancellation inside fetch releases the permit.
Different hosts have independent budgets. Limits are immutable configuration.

## Circuit state machine

Circuits are keyed by `source_id`. The immutable policy defaults to threshold 3,
open duration 30 seconds, and one half-open probe. The injected monotonic clock
controls cooldown. CLOSED counts consecutive final source failures; SUCCESS and
NOT_FOUND reset that count. BLOCKED, RATE_LIMITED, NETWORK_ERROR, PARSE_ERROR,
and INVALID_RESPONSE count once each, after all retries. Reaching threshold
opens the circuit. At cooldown expiry the circuit becomes HALF_OPEN; at most the
configured number of source executions are admitted as probes. Other calls
short-circuit immediately to NETWORK_ERROR / CIRCUIT_OPEN. A healthy probe
closes the circuit; a failing probe opens it for a fresh cooldown.

Each admission has an opaque governor-owned token and epoch. A completion from
an older epoch cannot reverse OPEN or HALF_OPEN. A caller cancelled, a fatal
BaseException, or a source rejected after host queueing abandons its token and
does not change circuit health. OPEN short-circuits before using a host permit;
after a queued call gets a permit, its token is revalidated before fetch.
Already running attempts may finish when another call opens the circuit.

Public snapshots are immutable copies; internal mutable maps and tokens are
never exposed. The governor retains state only per configured host and source,
never per item. Decisions read only final `SourceResult.status` and
`SourceResult.error_kind`, configured source and host identity, and monotonic
time. They do not read execution traces or error text. `CIRCUIT_OPEN` is not
retryable.

## Test matrix

Unit tests cover policy validation, canonical host keys, threshold and reset,
NOT_FOUND health, half-open admission and recovery, stale completion, concurrent
threshold updates, cancellation and fatal cleanup, 100 cancelled host waiters,
retry permit release, shared and separate governor scope, same and different
hosts, aggregation merge behavior, a 200-item offline gate, and 10,000-item
bounded-state stress. AST guards forbid trace and error-text dependencies.
