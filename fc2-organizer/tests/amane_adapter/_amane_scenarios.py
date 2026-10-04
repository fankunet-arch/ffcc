"""P5-C1 测试共享的场景构造器（非测试模块：下划线前缀，不被 pytest 收集；不 import amane）。

所有响应都来自 ``tests/fixtures/sources/**`` 中的真实站点 HTML 摘录（只读）；URL 模板与
Phase 4 验收测试（``test_p4_acceptance_real_adapters``）一致。预期值是作者根据 fixture HTML 写下的常量。
"""

from __future__ import annotations

import asyncio

from fc2_amane_adapter._runtime import AdapterRuntime
from fc2_amane_adapter._settings import parse_settings
from support.amane_host_fakes import FakeWebClient, FakeResponse
from support.source_fixtures import load_fixture

FC2DB = "https://fc2db.net/work/{digits}/"
JAVDB = "https://javdb.com/search?q=FC2-PPV-{digits}"
AV123 = "https://123av.com/en/v/fc2-ppv-{digits}"
TEMPLATES = {"fc2db_net": FC2DB, "javdb": JAVDB, "av123": AV123}

TITLE_4825061 = "【顔出し】ハーフ美人妻 最初で最後の顔出し未公開動画×2本 ※SNS認証者限定"
TITLE_4979299 = "夢は小学校の先生。天使のような笑顔と色白美巨乳♡ほのぼの系美女のおじさま２人への体当たり性指導映像。"


def url_for(source_id: str, digits: str) -> str:
    return TEMPLATES[source_id].format(digits=digits)


def serve(client: FakeWebClient, source_id: str, digits: str, fixture: str, status: int = 200) -> str:
    url = url_for(source_id, digits)
    client.add(url, FakeResponse.html(load_fixture(fixture), status=status, url=url))
    return url


def client_4825061() -> FakeWebClient:
    """av123 命中、fc2db_net 404、javdb 命中 -> Core SUCCESS。"""
    client = FakeWebClient()
    serve(client, "av123", "4825061", "av123/detail_4825061.html")
    serve(client, "fc2db_net", "4825061", "fc2db_net/work_404_4825061.html", status=404)
    serve(client, "javdb", "4825061", "javdb/search_hit_4825061.html")
    return client


def client_4979299() -> FakeWebClient:
    """三个来源全部命中。"""
    client = FakeWebClient()
    serve(client, "av123", "4979299", "av123/detail_4979299.html")
    serve(client, "fc2db_net", "4979299", "fc2db_net/work_4979299.html")
    serve(client, "javdb", "4979299", "javdb/search_hit_4979299.html")
    return client


def client_4824605_not_found_everywhere() -> FakeWebClient:
    """fc2db_net 命中被替换为 404；av123 404；javdb 仅有模糊号码 -> 三个来源都 NOT_FOUND。"""
    client = FakeWebClient()
    serve(client, "fc2db_net", "4824605", "fc2db_net/work_404_4825061.html", status=404)
    serve(client, "av123", "4824605", "av123/detail_404_4824605.html", status=404)
    serve(client, "javdb", "4824605", "javdb/search_no_exact_4824605.html")
    return client


def runtime_for(client: object, raw_settings: dict | None = None, **kwargs) -> AdapterRuntime:
    return AdapterRuntime(parse_settings(raw_settings or {}), client, **kwargs)


def lookup(runtime: AdapterRuntime, number: str = "FC2-PPV-4825061", content_type: object = "fc2"):
    return asyncio.run(runtime.lookup(number, content_type))
