# PHASE2_HANDOFF.md

```text
Phase: Phase 2 — Source adapter framework + live source verification

Review Base:
e6472f948f885c52e6f4c62cf29383e9dcd3d4e3
(docs(review): add Phase 1 R2 handoff)

Phase 2 WIP checkpoint (already pushed; not amended/squashed/reset):
948fc23b672da454e14a577ad7eb7b833d378310

Code Review Candidate (FINAL_PHASE2_CODE_HEAD):
3a23e6fa9a351b5c3bc6d2159028177616f98371

Review range:
e6472f948f885c52e6f4c62cf29383e9dcd3d4e3..3a23e6fa9a351b5c3bc6d2159028177616f98371

Phase 2 Reviewed Docs Head:
4e7883e87bd6195080d1eb5afcefda0a8897600d

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**这是一个复查候选，而不是 PASS 声明。** Phase 3（聚合）尚未开始。

> **在 Phase 3 Entry C0-05 中做的更正**（只更正事实，是在独立 Phase 2 复查给出
> PASS WITH NON-BLOCKING NOTES 之后进行的；本文其余内容没有改写）：
> 1. 头部不再写 Docs Head 为 "reported externally"（一个自我引用的占位符）— 现在记录的是经过复查的 Docs Head；
> 2. “我的所有提交都在本地 / 没有推送”这一行在 Phase 2 推送之后就不对了，已被替换（见 *本地工作区说明*）；
> 3. `FC2-4824605` 的线上近似未命中项是 `FC2-1824605` 和
>    `FC2-4724605`（早先的草稿写成了 `FC2-1825061`，那是 `FC2-4825061` 的近似未命中项）；
> 4. 测试数量记录为 309 collected / 309 passed，`45be2b7` 提交信息中
>    “80 new offline tests” 的说法被注明为一种粗略的历史描述（历史不做 amend）。

## Phase 2 交付的内容

| 层 | 内容 | 位置 |
|---|---|---|
| 框架（在 WIP `948fc23` 中） | `SourceAdapter` 合同、`SourceRegistry`、与 transport 无关的 `SourceHttpClient` Protocol + `HttpxTransport`、`tools/probe_sources.py` | `src/fc2_metadata_core/{sources,http}`、`tools/` |
| 线上调研 | 线上探测了 15 个候选条目；采用 3 个 | `docs/sources/SOURCE_VIABILITY_*.md`、`docs/SOURCE_STATUS_MATRIX.md` |
| 探测集合 | 7 个已知有效的 ID，每个都经过独立佐证 | `docs/PHASE2_PROBE_SET.md` |
| 证据 | 机器生成的 JSON（原始探测 + adapter 探测）以及人工观察记录 | `docs/source-probes/` |
| Adapter | `fc2db_net`、`javdb`、`av123` + 共享的 `_common.py` | `src/fc2_metadata_core/sources/adapters/` |
| 离线测试 | 基于逐字摘录的真实响应 fixture 的解析器测试 + `fetch` 合同测试 | `tests/unit/sources/adapters/`、`tests/fixtures/sources/` |

WIP checkpoint 之后的提交，从旧到新：

```text
ee14d0b chore: ignore .pytest_cache and *.egg-info local artifacts
45be2b7 feat(source): add fc2db_net, av123 and javdb adapters with offline parser tests
3a21c4b fix(source): name the exception type in transport-error details
3a23e6f docs(source): Phase 2 live source viability research, evidence and probe set
```

## 门槛结果（规格 §11 / Phase 2）

| 要求 | 结果 | 证据 |
|---|---|---|
| 普通的公网 HTTPS 不是沙箱合成的 403 | 满足 — 从 example.com / wikipedia.org / fc2.com 得到了真实的 200s；出口是西班牙的网络（`cf-ray …-MAD`） | 人工观察记录 §1 |
| 在编写任何 adapter 之前，用 `probe_sources.py raw` 做真实的候选调研 | 满足 — 每个 adapter 之前都先有原始探测；最后一轮原始探测在 12:57–12:58 UTC | `PHASE2_PROBE_20260920.json` |
| >=5 个 provider 家族，包括 FC2 Official 和若干聚合站 | 满足 — 15 个条目（见矩阵） | `SOURCE_STATUS_MATRIX.md` |
| 实际调查了 FC2 Official | 满足 — **BLOCKED：登录墙**（302 跳转链指向 `fc2.com/ja/login.php`） | `SOURCE_VIABILITY_fc2_official.md`、人工观察 §2 |
| >=5 个已知有效的 ID | 满足 — 7 个 | `PHASE2_PROBE_SET.md` |
| 每个候选都有一份 SOURCE_VIABILITY 文档 | 满足 — 15 份文档 | `docs/sources/` |
| 只为线上可用且合格的来源编写 adapter | 满足 — 3 个 adapter，全部针对先通过了原始探测的来源 | — |
| 每个 VERIFIED 来源：真实运行 adapter、>=2 个 ID 为 `SUCCESS`、番号 + 非空标题、无需登录、不绕过 CAPTCHA/CF、有离线测试 | 3 个来源全部满足 | 见下表 |
| >=2 个独立的 VERIFIED 来源（门槛）；3 = 更强的目标 | **3 VERIFIED** | 见下表 |
| 没有 Phase 3 聚合 | 满足 — adapter 之间从不相互调用（有测试断言） | `test_adapter_registration.py` |

VERIFIED 来源（门槛运行于 2026-09-20 13:02:27–13:03:21 UTC，代码 `3a21c4b`；
adapter 运行经过真实的 `HttpxTransport`，每次查找一个请求，间隔约 ~2.5 s，不带 cookie）：

| Source ID | Provider | `SUCCESS` 的 ID（共 7） | 番号 / 标题之外的字段 |
|---|---|---|---|
| `fc2db_net` | fc2db.net | 6（`4824605 4979299 4976588 1042815 4978035 4972767`） | release、runtime、actors、publisher(seller)、tags、thumb |
| `javdb` | javdb.com 公开搜索列表 | 6（`4825061 4979299 4976588 1042815 4978035 4972767`） | release、thumb、external id |
| `av123` | 123av.com | 3（`4825061 4979299 4978035`） | release、runtime、tags |

每个来源对于*其他*来源所收录的 ID 也都返回了 `NOT_FOUND`（真实的 404，或“没有精确命中”），这正是需要三个来源的原因：
见 `SOURCE_STATUS_MATRIX.md` 中按 ID 列出的表格。

**同样如实记录：** 出现过一次瞬时超时（`fc2db_net`、
`FC2-4978035`、13:01，在 `45be2b7` 上的第一轮门槛运行）。它暴露出一个只有 `transport error: ` 的
`error_detail`（httpx 的超时异常字符串化后为 `""`）；已在 `3a21c4b` 中修复（`transport error: HttpTimeoutError`），
整个门槛在 `3a21c4b` 上重新运行并通过。两轮结果都记录在 JSON 中。

## 复查者应当质疑的决定

1. **`javdb` 只使用搜索列表。** 它的详情页会重定向到 `/login`（人工观察 §3），因此 adapter 从不请求详情页，
   也无法提供 actors/tags/runtime。它仍然满足门槛（番号 + 日文标题 + 发行日期 + 封面），而且不需要任何私人会话。
   如果你认为字段贫乏的来源不能算 “VERIFIED”，仅凭 `fc2db_net` + `av123`（2 个来源）门槛依然成立，
   只是届时只有一个提供日文标题的来源。
2. **`javdb` 的搜索是模糊的。** adapter 只接受番号与请求完全相等的命中项；近似未命中项（对于
   `4824605` 的 `FC2-1824605`、`FC2-4724605`）会得到 `NOT_FOUND`。已针对真实的模糊搜索页面做了离线测试，
   也做了线上验证（`FC2-4824605` → `NOT_FOUND`）。
3. **`NormalizedMetadata.runtime` 的单位。** Core 合同只规定了 `int >= 0`。adapter 输出的是**整分钟**
   （`"55:23"` → 55，`"1:02:03"` → 62；秒数丢弃）。这是我的选择，写在 `_common.duration_to_minutes` 中；
   Phase 1 的合同没有确定这一点，Phase 5 的 NFO writer 必须与之一致。
4. **`123av` 的标题是英文机器翻译**，它的 “Maker” 是一个固定的桶值 `FC2`，刻意*没有*映射到
   `studio`/`publisher`。Phase 3 在选取 `title` 时应当让它的权重低于提供日文标题的来源。
5. **`fc2db_net.thumb_urls` 与 `poster_urls`。** 它的封面是一个标注为缩略图的 600×600 裁切图，因此放入
   `thumb_urls`；这里没有任何来源提供 poster/fanart。
6. **WIP checkpoint 之后对 Phase-2 框架代码只有一处改动：**
   `sources/base.py::transport_error_result` 现在会在 `error_detail` 中写出异常类型（在
   `tests/unit/sources/test_base.py` 中 +1 个测试）。框架 / WIP 中的其他内容都没有被触碰。
7. **探测工具的改动：** `tools/probe_sources.py raw` 现在还会记录页面的 `<title>`、`server` 和
   `cf-mitigated`（仍然不记录响应体 / cookie），这样证据文件就能说明它看到的是哪一种 200/403/404。
   在此之前写入的记录缺少这三个字段（已在人工观察记录文件中注明）。

## 独立性 — 在依赖“3 个来源”之前请先读这一节

这三个 VERIFIED 来源是彼此独立的*服务*（不同的运营者、host、页面格式，而且每一个都收录了其他来源没有的作品）。
它们**不是**彼此独立的*源头*：它们都复制 FC2 Content Market 的数据，而且三者都位于 Cloudflare 的 CDN 之后。
一次 FC2 下架潮或一次 Cloudflare 全局故障会同时波及这三者。FC2 Official 本身是唯一的源头，而且需要登录。

## 影响调研的环境事实

- **西班牙 ISP 层面的 IP 封锁。** `fc2ppvdb.com` 和 `onejav.com` 解析到
  `188.114.96.5`/`188.114.97.5`；从这个网络访问时，HTTPS 以 `self-signed certificate` 失败，
  而普通 HTTP 返回一则引用巴塞罗那商事法院判决的通知（18 Dec 2024，LaLiga/Telefónica）。
  因此这两者都是**未评估，而不是已失效**（人工观察 §4）。没有关闭证书校验，也没有使用其他路由。
  在 Phase 3 确定其来源列表之前，应当从另一个网络重新探测它们。
- 遇到 Cloudflare challenge（403，`cf-mitigated: challenge`）且**没有绕过**的：
  `fd2ppv.cc` 作品页、`javten.com`、`supjav.com`、`missav.ws`、`fc2db.com`。
- `fc2cm.com` 数据陈旧（最新作品为 4699535），不稳定（响应体中出现 `sql error`），并且对缺失的作品返回
  HTTP 200 — 已拒绝。

## 测试

离线测试套件（无网络）：

```text
cd fc2-organizer
python -m pytest -q
309 collected / 309 passed
```

相对于 WIP checkpoint 时 228 个测试的变化明细：`tests/unit/sources/adapters/` 中新增 **+76** 个测试
（common 24、fc2db_net 17、javdb 17、av123 15、registration 3），`tests/unit/sources/test_base.py` 中 **+1**，
以及 **+4** 个：因为 `tests/contract/test_core_independent_of_amane.py` 对 package 中的每个模块做参数化，
因此自动覆盖了四个新模块（`_common`、`fc2db_net`、`av123`、`javdb`）— 所以它们都没有 import Amane。
（`45be2b7` 的提交信息写的是 “80 new offline tests”；那只是一条历史提交信息中的粗略描述，刻意不做 amend。
以上数字才是正式记录：309 collected / 309 passed。）

adapter 测试使用 `tests/fixtures/sources/` 下的 fixture，每一个都是*真实响应的逐字摘录*
（每个文件顶部有出处注释）；只删除了广告 / 脚本 / 导航。每个 adapter 覆盖：在两个真实页面上的精确字段提取、
真实的 404 页面、每一种失败状态（403/429/5xx/Cloudflare-challenge-under-200/登录重定向）、transport 错误、
番号不符的页面（`INVALID_RESPONSE`，绝不会悄悄成功）、缺失 / 空白的标题（`PARSE_ERROR`）、在任何请求之前
拒绝非规范输入，以及 `base_url` 覆盖。

线上检查**不**属于离线测试套件（它们依赖网络和第三方站点）。如需重复运行：

```text
python tools/probe_sources.py adapter --source fc2db_net FC2-4824605 FC2-4979299
python tools/probe_sources.py adapter --source javdb     FC2-4825061 FC2-4979299
python tools/probe_sources.py adapter --source av123     FC2-4825061 FC2-4979299
```

（默认每次请求间隔 2.0 s；除非使用 `--no-record`，否则每次运行都会追加写入
`docs/source-probes/PHASE2_PROBE_<date>.json`。）

## 已知局限 / 刻意延后

- 没有节流、重试、退避、按 host 的并发限制或熔断：属于 Phase 3。每次 `fetch` 恰好发出一个请求。
  `javdb` 最有可能触发限流；`429` 映射为 `RATE_LIMITED`。
- 解析器基于正则 / JSON-LD，针对的是今天的页面标记。页面布局变化会表现为 `PARSE_ERROR`/`INVALID_RESPONSE`，
  而不会产生错误的数据（番号总是与页面交叉核对）；fixture 固定了当前的页面标记。
- 默认 15 s 的 transport 超时在线上使用中产生过一次瞬时失败；重试策略属于 Phase 3 的范畴。
- 服务条款：这些都是第三方成人索引站点。adapter 每次查找只以较低的频率读取一个公开页面，不是批量爬虫；
  是否默认启用它们发布，是后续阶段的产品决策。
- 覆盖不均衡（见按 ID 列出的表格）：没有任何单一来源收录全部 7 个 ID；
  `av123` 覆盖 3/7。Phase 3 必须把某一个来源返回的 `NOT_FOUND` 视为正常情况。

## 本地工作区说明

- `.gitignore` 现在会忽略 `.pytest_cache/` 和 `*.egg-info/`（`ee14d0b`）；
  多余的 `src/fc2_metadata_core.egg-info/` 已被删除。
- `fc2-organizer/.pytest_cache/` **无法**删除：当前（非提权、中等完整性级别的）用户无法读取它 —
  `Get-ChildItem`、`icacls`、`Get-Acl` 都返回 *Access denied*；`dir /q` 显示一个无法解析的所有者（`...`）；
  父目录授予了 `Ctg` 完全控制权限。旁边的 `.venv` 归 `BUILTIN\Administrators` 所有，说明它们是早先一次
  提权运行创建的。它现在已被 git 忽略，只会产生一条 `PytestCacheWarning`；所有测试都通过。最小修复方式
  （提权的 PowerShell，只针对这个目录）：
  `takeown /f .pytest_cache /r /d y; icacls .pytest_cache /reset /t; Remove-Item -Recurse -Force .pytest_cache`。
- 推送状态：Phase 2（截至 Docs Head `4e7883e87bd6195080d1eb5afcefda0a8897600d`）
  已推送到 `origin/claude/phase-0-amane-integration-fnvhpq`，并已通过独立复查（PASS WITH NON-BLOCKING NOTES）。

## Phase 3 尚未开始（NOT started）

没有做任何聚合、跨来源调度、字段级合并、重试策略或 Amane adapter 工作。
