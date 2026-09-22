# Phase 3 / C5-R1 Handoff — Docs-Only Closure

**Type:** DOCS-ONLY CLOSURE (no source, no test, no tool changes)

**C5 Code Head:** `fb4dddaf4ef00ed201c94d9a7e29d1e86a20f17d` (unchanged / frozen by this round)
**Reviewed C5 Docs Head / C5-R1 Base:** `caf1655336b96a02a64cfdd515932c594d86da0a`

**Independent Level 2 review result (prior round):** PASS WITH NON-BLOCKING NOTES

## 1. Finding closed this round

**C5-R-01** — Severity: MEDIUM — Scope: documentation / frozen contract wording

**Root cause:** The contract and handoff promoted a true, narrower guarantee (host-permit *capacity*
independence per `HostKey`) into an unqualified, absolute claim about scheduler-level *latency*
independence ("different hosts ... never block each other"; "a saturated host never delays a different
host"). The independent Level 2 reviewer reproduced a case where `AggregationConfig.max_concurrency = 2`
with targets `A1 -> host-a`, `A2 -> host-a`, `B1 -> host-b` (each host limit 1) leaves `B1` unable to obtain
an aggregate source slot while `A1`/`A2` occupy both of the only two `max_concurrency` slots contending for
`host-a` — even though `host-b`'s own permit capacity is completely idle throughout.

**Code behavior:** UNCHANGED. This is expected, pre-existing C1 (`AggregationConfig.max_concurrency`)
architecture, not a C5 defect: host permit capacities *are* independent per `HostKey` exactly as claimed;
what was missing was the explicit acknowledgement that aggregate-local source-slot admission (C1, unchanged)
sits *outside* that guarantee and can still serialize sources across hosts.

**Source/test changes:** NONE.

## 2. Correct frozen semantics (now recorded in the contract and handoff)

- Host permit budgets are independent per `HostKey`.
- Saturation of one host cannot consume or reduce another host's permit capacity.
- Different hosts may execute concurrently up to their own respective limits whenever an aggregate source
  slot is available to use them.
- `AggregationConfig.max_concurrency` (C1) remains the outer, unchanged per-`aggregate()` scheduling budget.
- A source waiting for a host permit continues to occupy its aggregate-local source slot for the duration of
  that wait.
- Therefore, when `max_concurrency` is smaller than the number of runnable sources in one lookup, contention
  on one host can indirectly delay the admission of a later source targeting a *different*, otherwise-idle
  host.
- This is **not** a host-permit leak and **not** cross-host budget coupling — it is ordinary aggregate-level
  head-of-line scheduling under the unchanged C1 semaphore, orthogonal to the host limiter's own accounting.
- **C5 provides capacity isolation across hosts. C5 does not provide cross-host latency isolation.**

## 3. Files changed this round

```
docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md   (amended: §2, §5 — capacity- vs latency-isolation wording)
docs/review/PHASE3_C5_HANDOFF.md                            (amended: §9 — two-hosts claim re-worded, 2+3 peak result preserved)
docs/review/PHASE3_C5_R1_HANDOFF.md                          (new: this file)
```

No `src/`, `tests/`, `tools/`, or `pyproject.toml` file touched. No other specification file touched.

## 4. Finding closure claim

**C5-R-01: CLOSED** (docs amended to state the precise capacity-isolation vs. latency-isolation semantics;
no remaining unqualified scheduler-level latency guarantee found in `PHASE3_RESOURCE_CONTROL_CONTRACT.md` or
`PHASE3_C5_HANDOFF.md` — verified by search for "never block each other" / "never delays a different host" /
"no cross-host delay" / "cannot delay another host").

This is a documentation-correctness claim only. It does not re-run or re-assert the prior round's code
evidence beyond restating it for record-keeping (§5).

## 5. Independent Level 2 code evidence (preserved from the prior round, not re-verified this round)

This round is docs-only and did not re-run the full product test suite (per instruction, since no code
changed). For the record, the prior independent Level 2 review found:

- Full offline suite: **2361/2361** passed, 0 failed, 0 skipped (both `tests/contract` ↔
  `tests/unit/resource_control` import orderings green).
- Independent 200-item mixed stress gate (author's own construction, separate from
  `test_rc_stage_gate_200.py`): **PASS**.
- Independent 10,000-item large-N gate (single scheduler M=16 host limit 3, and two schedulers × 5,000
  sharing one governor): **PASS**.
- 6 targeted mutation probes (epoch-check removal, host-wait revalidation removal, permit-held-across-backoff,
  `NOT_FOUND` reclassified as failure, `CIRCUIT_OPEN` made retryable, grant+cancel handback removal): all 6
  caught by the test suite.
- No BLOCKER / HIGH findings. C5-R-01 (MEDIUM, docs) was the only open item, now closed by this round.

## 6. Backlog (unchanged, carried forward)

- **C2-L2** — LOW / OPEN, unchanged: C5 reads no trace fields (contract §10 / handoff §8, unaffected by this
  docs round).
- All other C4-N1, C4-R1-N1/N2/N3, C3-N1…N4, P2-R-05/06/07/10, F3/F5 items: unchanged, carried forward as
  before this round.

## 7. Status

**C5 code:** UNCHANGED / FROZEN at `fb4dddaf4ef00ed201c94d9a7e29d1e86a20f17d`.
**Next phase:** NOT STARTED.

READY FOR C5-R1 DOCS-ONLY INDEPENDENT CLOSURE REVIEW
