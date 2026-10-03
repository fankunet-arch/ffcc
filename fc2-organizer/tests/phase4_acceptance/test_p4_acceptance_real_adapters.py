"""P4-C10 S2: S-20, the real adapter chain (contract sections 5.2 L-05, 7.1 FX-6, 7.2).

``build_default_registry()`` + ``default_aggregation_config()`` with ``MultiSourceEngine`` over the offline
``support.fake_http_client.FakeHttpClient``, answering with the verbatim fixture HTML of ``tests/fixtures/sources/**``
(read-only, loaded into memory; nothing is written to or created in the repository). The expected titles / dates /
numbers below are constants written by the test author from the fixture HTML (the same practice as the Phase 2
adapter tests); they are not read back from the parsers under acceptance.
"""

from __future__ import annotations

import os

from . import _corpus as corpus
from ._corpus import Film
from ._harness import CONFIG_4, Chain, diagnostics_bytes, diagnostics_model
from ._oracles import gate_diagnostics_canaries, gate_file_bytes, parse_nfo, sha256_file
from support.fake_http_client import FakeHttpClient, make_response
from support.source_fixtures import load_fixture

# ---- the author's constants (read from the fixture HTML; see the module docstring)
TITLE_4979299 = "夢は小学校の先生。天使のような笑顔と色白美巨乳♡ほのぼの系美女のおじさま２人への体当たり性指導映像。"
# the javdb exact hit; the Phase 2 text cleaner collapses the HTML's U+3000 to one ASCII space (whitespace rule)
TITLE_4825061 = "【顔出し】ハーフ美人妻 最初で最後の顔出し未公開動画×2本 ※SNS認証者限定"
TITLE_4824605 = "※1/11まで初回限定90％OFF※【ハメ撮り】スレンダー美人の人妻に種付け中出し調教"
RELEASE_4979299 = "2026-09-19"
RELEASE_4825061 = "2026-01-02"
RELEASE_4824605 = "2026-01-04"

FC2DB = "https://fc2db.net/work/{digits}/"
JAVDB = "https://javdb.com/search?q=FC2-PPV-{digits}"
AV123 = "https://123av.com/en/v/fc2-ppv-{digits}"


def _serve(client: FakeHttpClient, template: str, digits: str, fixture: str, status: int = 200, **extra) -> str:
    url = template.format(digits=digits)
    client.add_response(url, make_response(status_code=status, url=url, text=load_fixture(fixture), **extra))
    return url


def _films() -> list[Film]:
    names = {"4825061": "FC2-PPV-4825061.mp4", "4979299": "FC2-PPV-4979299.mp4", "4824605": "FC2-PPV-4824605.mp4"}
    return [Film(f"s20-{digits}", name, f"FC2-{digits}", "", 40 + n, (), "s20")
            for n, (digits, name) in enumerate(names.items())]


def _client_for_three_numbers() -> tuple[FakeHttpClient, list[str]]:
    client = FakeHttpClient()
    urls = [
        # FC2-4825061: av123 hit, fc2db_net 404, javdb hit (its page also lists the fuzzy FC2-1825061)
        _serve(client, AV123, "4825061", "av123/detail_4825061.html"),
        _serve(client, FC2DB, "4825061", "fc2db_net/work_404_4825061.html", status=404),
        _serve(client, JAVDB, "4825061", "javdb/search_hit_4825061.html"),
        # FC2-4979299: every source hits
        _serve(client, AV123, "4979299", "av123/detail_4979299.html"),
        _serve(client, FC2DB, "4979299", "fc2db_net/work_4979299.html"),
        _serve(client, JAVDB, "4979299", "javdb/search_hit_4979299.html"),
        # FC2-4824605: fc2db_net hit, av123 404, javdb lists only fuzzy numbers (no exact match -> NOT_FOUND)
        _serve(client, AV123, "4824605", "av123/detail_404_4824605.html", status=404),
        _serve(client, FC2DB, "4824605", "fc2db_net/work_4824605.html"),
        _serve(client, JAVDB, "4824605", "javdb/search_no_exact_4824605.html"),
    ]
    return client, urls


def _states(diagnostic_item):
    return {s.source_id: (s.status.value, s.operational_failure, s.contributed) for s in diagnostic_item.metadata.sources}


def test_s20_real_adapters_chain_crosses_every_boundary(tmp_path):
    """S-20 (L-05, SI-17): three real fixture numbers -> aggregate SUCCESS -> READY -> SUCCESS; NFO title / uniqueid ==
    the fixture constants; the real parsers' output is accepted by every boundary down to the filesystem."""
    films = _films()
    client, urls = _client_for_three_numbers()
    with Chain(tmp_path, films, config=CONFIG_4, real_http_client=client) as chain:
        preview = chain.preview()
        assert sorted(client.requested_urls) == sorted(urls)  # one request per adapter per number: nine in all
        assert chain.sources.numbers_called == {}  # the scripted engine was not involved
        assert preview.summary.ready == 3 and preview.summary.unprepared == 0
        by_number = {i.canonical_number: i for i in preview.items}
        for number in ("FC2-4825061", "FC2-4979299", "FC2-4824605"):
            item = by_number[number]
            assert item.state.value == "ready" and item.metadata.status.value == "success"
            assert item.metadata.aggregation_result.status.value == "success"  # NOT_FOUND is not an operational failure
        assert by_number["FC2-4825061"].metadata.aggregation_result.metadata.title == TITLE_4825061  # javdb outranks av123
        result = chain.execute(preview)
        assert result.outcome.value == "success" and result.summary.success == 3
        expected = {"FC2-4825061": (TITLE_4825061, RELEASE_4825061), "FC2-4979299": (TITLE_4979299, RELEASE_4979299),
                    "FC2-4824605": (TITLE_4824605, RELEASE_4824605)}
        for number, (title, release) in expected.items():
            nfo = parse_nfo(open(os.path.join(chain.library, number, f"{number}.nfo"), "rb").read())
            assert nfo[0][:3] == ("title", {}, title) and nfo[1][2] == number
            assert [c[2] for c in nfo if c[0] == "premiered"] == [release]
            assert nfo[1][1] == {"type": "fc2", "default": "true"}
            media = os.path.join(chain.library, number, f"{number}.mp4")
            assert sha256_file(media) == chain.original[chain.source_path(next(f for f in films if f.number == number))]
        # the images came from the fixtures' thumb URLs, served as valid JPEGs by the MockTransport
        thumb = os.path.join(chain.library, "FC2-4824605", "thumb.jpg")
        gate_file_bytes(thumb, corpus.image_payload(
            "https://img.fc2db.net/wp-content/uploads/2026/01/06134641/1767165768.52.webp"), "S-20 thumb bytes")
        # source states are those of the fixtures
        model = diagnostics_model(preview)
        assert _states(model.items[by_number["FC2-4825061"].index]) == {
            "fc2db_net": ("not_found", False, False), "javdb": ("success", False, True), "av123": ("success", False, True)}
        assert _states(model.items[by_number["FC2-4979299"].index]) == {
            "fc2db_net": ("success", False, True), "javdb": ("success", False, True), "av123": ("success", False, True)}
        assert _states(model.items[by_number["FC2-4824605"].index]) == {
            "fc2db_net": ("success", False, True), "javdb": ("not_found", False, False), "av123": ("not_found", False, False)}
        for built in (preview, result):
            gate_diagnostics_canaries(diagnostics_bytes(built), forbidden=corpus.FX5_ALWAYS_FORBIDDEN)


def test_s20_a_cloudflare_challenge_page_makes_the_aggregate_partial_not_failed(tmp_path):
    """S-20 (challenge group): one source answers with the verbatim Cloudflare interstitial (HTTP 403) -> BLOCKED, the
    aggregate is PARTIAL and the film is still organized from the other two sources."""
    film = Film("s20-challenge", "FC2-PPV-4979299.mp4", "FC2-4979299", "", 77, (), "s20")
    client = FakeHttpClient()
    _serve(client, FC2DB, "4979299", "common/cloudflare_challenge.html", status=403)
    _serve(client, JAVDB, "4979299", "javdb/search_hit_4979299.html")
    _serve(client, AV123, "4979299", "av123/detail_4979299.html")
    with Chain(tmp_path, [film], real_http_client=client) as chain:
        preview = chain.preview()
        item = preview.items[0]
        assert item.state.value == "ready" and item.metadata.status.value == "partial"
        assert item.metadata.aggregation_result.status.value == "partial"
        assert [w.value for w in item.warnings][0] == "metadata_partial"
        result = chain.execute(preview)
        assert result.items[0].execution.status.value == "success" and result.summary.partial == 0
        states = _states(diagnostics_model(preview).items[0])
        assert states == {"fc2db_net": ("blocked", True, False), "javdb": ("success", False, True),
                          "av123": ("success", False, True)}
        nfo = parse_nfo(open(os.path.join(chain.library, film.number, f"{film.number}.nfo"), "rb").read())
        assert nfo[0][2] == TITLE_4979299  # fc2db_net (BLOCKED) is absent; javdb's Japanese title outranks av123's English one
        assert [c[2] for c in nfo if c[0] == "premiered"] == [RELEASE_4979299]
