"""Phase 3 C3 (pre-selection amendment 1): candidate-pool builder v2.

Attempt 1 of the pool conflated "the reference said no" with "the reference could not be asked" (41 of 214
requests failed and were silently recorded as "not confirmed"). v2 records every lookup as exactly one of
``confirmed`` / ``negative`` / ``unavailable`` (never ``unavailable -> negative``), retries an ``unavailable`` lookup
once, and refuses to produce a pool at all when a prefix enumeration stays unavailable.

Fully offline: a scripted fake site behind ``httpx.MockTransport``. The builder never sees the aggregation engine.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import tempfile
from pathlib import Path

import httpx
import pytest

TOOL = Path(__file__).resolve().parents[3] / "tools" / "build_candidate_pool.py"
_spec = importlib.util.spec_from_file_location("build_candidate_pool_v2_under_test", TOOL)
pool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pool)

SECRET = "SECRET-COOKIE-abc123"


# ---- fake pages -------------------------------------------------------------------------------------------------------------------------------------


def sukebei_html(*digits_and_extra: str) -> str:
    rows = "".join(
        f'<tr class="default"><td><a href="/view/{i}" title="FC2-PPV-{d} title {SECRET}">x</a></td></tr>'
        for i, d in enumerate(digits_and_extra, start=100)
    )
    return f"<html><table><tbody>{rows}</tbody></table></html>" if rows else "<html><h3>No results found</h3></html>"


def netflav_html(*codes: str) -> str:
    payload = {"props": {"initialState": {"search": {"docs": [{"code": c, "title": SECRET} for c in codes]}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></html>'


CHALLENGE = "<html><head><title>Just a moment...</title></head><body>challenge</body></html>"


class FakeSite:
    """Scripted responses keyed by ``(host-kind, query key)``; a list is consumed one entry per request (last repeats)."""

    def __init__(self, prefixes=None, numbers=None, netflav=None, script=None):
        self.prefixes = prefixes or {}
        self.numbers = numbers or {}
        self.netflav = netflav or {}
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if "sukebei" in request.url.host:
            q = params["q"]
            key = ("sukebei", q[len("FC2-PPV-"):-1] if q.endswith("*") else q[len("FC2-PPV-"):])
            default = (self.prefixes if q.endswith("*") else self.numbers).get(key[1], sukebei_html())
        else:
            key = ("netflav", params["keyword"])
            default = netflav_html(*self.netflav.get(key[1], ()))
        self.calls.append(key)
        queue = self.script.get(key)
        if queue:
            outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        else:
            outcome = httpx.Response(200, text=default, headers={"Set-Cookie": f"sid={SECRET}"})
        if isinstance(outcome, BaseException):
            if isinstance(outcome, httpx.TransportError):
                outcome.request = request
            raise outcome
        return outcome


def run_build(site: FakeSite, *, prefixes=("10", "11"), per_prefix=2, frozen=("FC2-4825061",)):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(site), follow_redirects=True) as client:
            return await pool.build_pool(0.0, prefixes=prefixes, per_prefix=per_prefix, frozen=frozen, client=client)

    return asyncio.run(scenario())


def refs_for(site: FakeSite):
    client = httpx.AsyncClient(transport=httpx.MockTransport(site))
    return pool.References(client, 0.0), client


def netflav_check(site: FakeSite, digits="1000001"):
    async def scenario():
        refs, client = refs_for(site)
        try:
            return await refs.netflav(digits), refs
        finally:
            await client.aclose()

    return asyncio.run(scenario())


# ---- pure parsing -------------------------------------------------------------------------------------------------------------------------------


def test_sukebei_ids_come_from_torrent_names_only_and_are_counted():
    page = sukebei_html("2304688", "2304688", "2305735", "83654") + "FC2-PPV-2311111 outside a row title"
    counts = pool.sukebei_torrent_ids(page)
    assert counts == {"2304688": 2, "2305735": 1, "83654": 1}


def test_prefix_candidates_and_even_stride_are_deterministic():
    counts = {"2304688": 1, "2305735": 1, "83654": 1, "2400001": 1}
    assert pool.prefix_candidates(counts, "23") == ["2304688", "2305735"]
    ids = [str(2_000_000 + i) for i in range(10)]
    assert pool.pick_per_prefix(ids, 4) == [ids[1], ids[3], ids[6], ids[8]]
    assert pool.pick_per_prefix(ids[:3], 4) == ids[:3] and pool.pick_per_prefix([], 4) == []


def test_a_sukebei_page_is_valid_only_with_rows_or_an_explicit_no_results_marker():
    assert pool.sukebei_page_is_valid(sukebei_html("2304688")) is True
    assert pool.sukebei_page_is_valid(sukebei_html()) is True  # genuine empty result
    for junk in ("", CHALLENGE, "<html>oops</html>", "sql error"):
        assert pool.sukebei_page_is_valid(junk) is False


def test_netflav_codes_distinguish_an_empty_result_from_an_unusable_page():
    assert pool.netflav_result_codes(netflav_html()) == []
    assert pool.netflav_result_codes(netflav_html("fc2-ppv 4825061", "FC2-PPV-1825061", "abc")) == ["4825061", "1825061"]
    for junk in ("", CHALLENGE, '<script id="__NEXT_DATA__">{not json</script>', '<script id="__NEXT_DATA__">{"props":{}}</script>',
                 '<script id="__NEXT_DATA__">{"props":{"initialState":{"search":{"docs":"x"}}}}</script>'):
        assert pool.netflav_result_codes(junk) is None


# ---- tri-state + retry ------------------------------------------------------------------------------------------------------------------------------


def test_netflav_exact_hit_is_confirmed_after_one_attempt():
    check, refs = netflav_check(FakeSite(netflav={"1000001": ["fc2-ppv 1000001"]}))
    assert (check.state, check.attempts, check.detail) == (pool.CONFIRMED, 1, "exact_match") and refs.requests_made == 1 and refs.retry_requests == 0


@pytest.mark.parametrize("codes", [[], ["FC2-PPV-2000001"], ["fc2-ppv 1000002", "fc2-ppv 11000001"]], ids=["empty", "fuzzy-neighbour", "near-misses"])
def test_a_valid_page_without_the_exact_code_is_negative_and_is_never_retried(codes):
    check, refs = netflav_check(FakeSite(netflav={"1000001": codes}))
    assert (check.state, check.attempts, check.detail) == (pool.NEGATIVE, 1, "no_exact_match")
    assert refs.requests_made == 1 and refs.retry_requests == 0


@pytest.mark.parametrize(
    "outcome, detail",
    [
        (httpx.Response(503, text="down"), "http_503"),
        (httpx.Response(429, text="slow"), "http_429"),
        (httpx.Response(403, text="no"), "http_403"),
        (httpx.Response(404, text="nope"), "http_404"),
        (httpx.Response(200, text=CHALLENGE), "invalid_response"),
        (httpx.Response(200, text=""), "invalid_response"),
        (httpx.ReadTimeout("t"), "timeout"),
        (httpx.ConnectError("c"), "exception:ConnectError"),
    ],
)
def test_no_usable_response_twice_is_unavailable_never_negative(outcome, detail):
    site = FakeSite(script={("netflav", "1000001"): [outcome]})
    check, refs = netflav_check(site)
    assert (check.state, check.attempts, check.detail) == (pool.UNAVAILABLE, 2, detail)
    assert check.state != pool.NEGATIVE and site.calls == [("netflav", "1000001")] * 2
    assert refs.requests_made == 2 and refs.retry_requests == 1


def test_unavailable_then_confirmed_is_confirmed_with_two_attempts():
    site = FakeSite(script={("netflav", "1000001"): [httpx.Response(503), httpx.Response(200, text=netflav_html("fc2-ppv 1000001"))]})
    check, refs = netflav_check(site)
    assert (check.state, check.attempts) == (pool.CONFIRMED, 2) and refs.retry_requests == 1


def test_unavailable_then_negative_is_negative_with_two_attempts_and_no_third_request():
    site = FakeSite(script={("netflav", "1000001"): [httpx.ReadTimeout("t"), httpx.Response(200, text=netflav_html())]})
    check, refs = netflav_check(site)
    assert (check.state, check.attempts) == (pool.NEGATIVE, 2) and refs.requests_made == 2


def test_the_retry_waits_the_politeness_delay_like_any_other_request(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(pool.asyncio, "sleep", fake_sleep)
    site = FakeSite(script={("netflav", "1"): [httpx.Response(503)], ("netflav", "2"): [httpx.Response(200, text=netflav_html())]})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(site))
        try:
            refs = pool.References(client, 3.0)
            await refs.netflav("1")  # first request: no wait; retry: 3.0
            await refs.netflav("2")  # another request: 3.0
        finally:
            await client.aclose()

    asyncio.run(scenario())
    assert sleeps == [3.0, 3.0]


def test_direct_sukebei_number_lookup_is_tri_state():
    async def check(site, digits="4825061"):
        refs, client = refs_for(site)
        try:
            return await refs.sukebei_number(digits)
        finally:
            await client.aclose()

    found = asyncio.run(check(FakeSite(numbers={"4825061": sukebei_html("4825061", "4825061", "4825062")})))
    assert (found[0].state, found[0].attempts, found[1]) == (pool.CONFIRMED, 1, 2)
    none = asyncio.run(check(FakeSite(numbers={"4825061": sukebei_html("4825062")})))
    assert (none[0].state, none[0].attempts, none[1]) == (pool.NEGATIVE, 1, 0)
    empty = asyncio.run(check(FakeSite(numbers={"4825061": sukebei_html()})))
    assert empty[0].state == pool.NEGATIVE
    down = asyncio.run(check(FakeSite(script={("sukebei", "4825061"): [httpx.Response(503)]})))
    assert (down[0].state, down[0].attempts) == (pool.UNAVAILABLE, 2)


# ---- whole-pool behaviour -----------------------------------------------------------------------------------------------------------------------------


GOOD_SITE = dict(
    prefixes={"10": sukebei_html("1000001", "1000002", "1000003", "1000004", "1000005"), "11": sukebei_html("1100001", "1100002")},
    numbers={"4825061": sukebei_html("4825061")},
    netflav={"1000002": ["fc2-ppv 1000002"], "1100001": ["fc2-ppv 1100001"], "4825061": ["fc2-ppv 4825061"]},
)


def test_a_full_offline_build_has_the_v2_schema_and_fully_accounted_requests():
    site = FakeSite(**GOOD_SITE)
    doc = run_build(site)
    assert doc["schema_version"] == 2 and doc["engine_independent"] is True and doc["prefix_enumeration_complete"] is True
    numbers = [c["number"] for c in doc["candidates"]]
    assert numbers == sorted(numbers, key=lambda n: int(n.split("-")[1])) and len(set(numbers)) == len(numbers)
    assert {"FC2-4825061", "FC2-1100001", "FC2-1100002"} <= set(numbers) and len(numbers) == 5  # 2 kept of 5 in prefix 10, both of 11, + frozen
    assert doc["requests_made"] == len(site.calls) and doc["retry_requests"] == 0 and doc["initial_requests"] == doc["requests_made"]
    prefix_attempts = sum(r["attempts"] for r in doc["prefix_enumeration"])
    own_attempts = sum(
        check["attempts"]
        for c in doc["candidates"]
        for check in c["reference_checks"].values()
        if "shared_with_prefix_query" not in check
    )
    assert prefix_attempts + own_attempts == doc["requests_made"], "every request is accounted for by exactly one recorded check"
    assert doc["confirmed_checks"] + doc["negative_checks"] + doc["unavailable_checks"] == len(numbers) * 2 - len([c for c in doc["candidates"] if c["origin"] == "enumerated"])


def test_each_candidate_records_states_and_the_count_matches_the_confirmed_external_checks():
    doc = run_build(FakeSite(**GOOD_SITE))
    by = {c["number"]: c for c in doc["candidates"]}
    both = by["FC2-1100001"]
    assert both["external_reference_count"] == 2 and both["reference_checks"]["netflav"]["state"] == pool.CONFIRMED
    assert both["reference_checks"]["sukebei"]["shared_with_prefix_query"] == "11" and both["band"] == "older"
    only_r1 = by["FC2-1100002"]
    assert only_r1["external_reference_count"] == 1 and only_r1["reference_checks"]["netflav"]["state"] == pool.NEGATIVE
    assert "single-source validation" in only_r1["validity_note"] and only_r1["validity_sources"] == [pool.SUKEBEI_LABEL]
    for candidate in doc["candidates"]:
        confirmed = sum(1 for check in candidate["reference_checks"].values() if check["state"] == pool.CONFIRMED)
        assert candidate["external_reference_count"] == confirmed


def test_an_unavailable_corroboration_keeps_the_candidate_single_reference_and_is_not_hidden():
    site = FakeSite(**GOOD_SITE, script={("netflav", "1100001"): [httpx.Response(503)]})
    doc = run_build(site)
    candidate = next(c for c in doc["candidates"] if c["number"] == "FC2-1100001")
    assert candidate["external_reference_count"] == 1 and candidate["reference_checks"]["netflav"] == {"state": "unavailable", "attempts": 2, "detail": "http_503"}
    assert "UNAVAILABLE" in candidate["validity_note"] and "not a negative" in candidate["validity_note"]
    assert doc["unavailable_checks"] == 1 and doc["retry_requests"] == 1 and doc["requests_made"] == doc["initial_requests"] + 1 == len(site.calls)
    assert doc["prefix_enumeration_complete"] is True


def test_a_prefix_that_recovers_on_retry_keeps_the_pool_complete():
    site = FakeSite(**GOOD_SITE, script={("sukebei", "11"): [httpx.Response(429), httpx.Response(200, text=GOOD_SITE["prefixes"]["11"])]})
    doc = run_build(site)
    row = next(r for r in doc["prefix_enumeration"] if r["prefix"] == "11")
    assert (row["state"], row["attempts"]) == (pool.CONFIRMED, 2) and doc["retry_requests"] == 1 and doc["prefix_enumeration_complete"] is True


@pytest.mark.parametrize("outcome", [httpx.Response(503), httpx.Response(200, text=CHALLENGE), httpx.ReadTimeout("t")])
def test_a_prefix_unavailable_twice_fails_the_whole_build_instead_of_looking_like_zero_candidates(outcome):
    site = FakeSite(**GOOD_SITE, script={("sukebei", "11"): [outcome]})
    with pytest.raises(pool.PrefixEnumerationIncomplete, match="'11'"):
        run_build(site)


def test_a_prefix_with_a_genuine_empty_result_is_complete_with_zero_candidates():
    doc = run_build(FakeSite(**{**GOOD_SITE, "prefixes": {"10": sukebei_html("1000001"), "11": sukebei_html()}}))
    row = next(r for r in doc["prefix_enumeration"] if r["prefix"] == "11")
    assert (row["state"], row["candidates_found"], row["candidates_kept"]) == (pool.CONFIRMED, 0, 0) and doc["prefix_enumeration_complete"] is True


def test_phase2_provenance_is_never_counted_as_an_external_reference():
    site = FakeSite(**{**GOOD_SITE, "numbers": {"4825061": sukebei_html("4825062")}, "netflav": {}})
    doc = run_build(site)
    frozen = next(c for c in doc["candidates"] if c["number"] == "FC2-4825061")
    assert frozen["origin"] == "phase2_frozen" and frozen["external_reference_count"] == 0
    assert frozen["validity_sources"] == [pool.PHASE2_SOURCE_LABEL]
    assert {k: v["state"] for k, v in frozen["reference_checks"].items()} == {"sukebei": "negative", "netflav": "negative"}
    assert "provenance only" in frozen["validity_note"] and "no external reference confirmed" in frozen["validity_note"]


def test_an_unavailable_frozen_lookup_is_recorded_as_unavailable_and_the_id_is_kept():
    site = FakeSite(**GOOD_SITE, script={("sukebei", "4825061"): [httpx.ConnectError("c")], ("netflav", "4825061"): [httpx.Response(503)]})
    doc = run_build(site)
    frozen = next(c for c in doc["candidates"] if c["number"] == "FC2-4825061")
    assert {k: (v["state"], v["attempts"]) for k, v in frozen["reference_checks"].items()} == {"sukebei": ("unavailable", 2), "netflav": ("unavailable", 2)}
    assert frozen["external_reference_count"] == 0 and doc["unavailable_checks"] >= 2


def test_the_pool_document_never_contains_bodies_cookies_or_titles_from_the_references():
    doc = run_build(FakeSite(**GOOD_SITE, script={("netflav", "1100001"): [httpx.Response(503, text=SECRET, headers={"Set-Cookie": SECRET})]}))
    dumped = json.dumps(doc)
    for forbidden in (SECRET, "<html", "Set-Cookie", "set-cookie", "Authorization", "torrent title"):
        assert forbidden not in dumped
    allowed_detail = {"http_200", "http_503", "no_exact_match", "exact_match", "torrent_name_match_via_prefix_query", "valid_results_page"}
    for candidate in doc["candidates"]:
        for check in candidate["reference_checks"].values():
            assert set(check) <= {"state", "attempts", "detail", "shared_with_prefix_query"}
            assert check["detail"] in allowed_detail or check["detail"].startswith("exact_match_in_")


def test_the_pool_has_no_engine_derived_fields():
    doc = run_build(FakeSite(**GOOD_SITE))
    keys = set(doc) | {k for c in doc["candidates"] for k in c}
    for key in keys:
        assert not any(bad in key.lower() for bad in ("aggregate", "adapter", "coverage", "title", "engine_result", "source_status")), key


# ---- command line ------------------------------------------------------------------------------------------------------------------------------------


def test_main_writes_nothing_when_the_prefix_enumeration_is_incomplete(monkeypatch):
    async def boom(delay, **kwargs):
        raise pool.PrefixEnumerationIncomplete("prefix '11' enumeration stayed unavailable after 2 attempt(s) (http_503)")

    monkeypatch.setattr(pool, "build_pool", boom)
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory) / "pool.json"
        with pytest.raises(SystemExit, match="pool build FAILED, no output written"):
            pool.main(["--out", str(out)])
        assert not out.exists()


def test_main_enforces_the_politeness_floor_and_never_overwrites():
    with pytest.raises(SystemExit, match=">= 3"):
        pool.main(["--out", "x.json", "--delay-seconds", "2"])
    with tempfile.TemporaryDirectory() as directory:
        existing = Path(directory) / "pool.json"
        existing.write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit, match="refusing to overwrite"):
            pool.main(["--out", str(existing)])
