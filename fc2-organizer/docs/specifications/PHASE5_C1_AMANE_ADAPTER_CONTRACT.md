# PHASE 5 / P5-C1 合同（Contract）—— Amane Adapter End-to-End

```text
文档性质              : P5-C1 Contract（Design Candidate；只设计，不实现）
Package               : P5-C1 —— Amane Adapter End-to-End
Branch                : claude/phase5-c1-amane-adapter
Package Frozen Base   : 98ad8eb67bfd3e09701a730487e049f3fc348789（Phase 5 Entry Closure Head；F3 / F5 / XD-B11 CLOSED，Entry Gate PASS）
Planning Parent       : 98ad8eb67bfd3e09701a730487e049f3fc348789
Governance Authority  : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d（ACCELERATED v2）
Amane 正式基线        : v0.15.0；commit 45dff2159369883e028a296d775a4598836c1ddd（tag 对象 3292c957a092f85ddde1ba7462ffe9813827f4f1，annotated）
Risk Class            : B（带强制升级门 U-1..U-8；第 5 节）
配套施工计划          : docs/P5_C1_CONSTRUCTION_PLAN.md
```

## 当前状态（CURRENT）

```text
P5-C1 Design                : CANDIDATE —— INDEPENDENT DESIGN REVIEW REQUIRED
P5-C1 Contract（本文件）    : CANDIDATE
P5-C1 Construction Plan     : CANDIDATE
P5-C1 Implementation        : NOT STARTED
Phase 5                     : ENTRY AUTHORIZED
```

本文件**不是**冻结合同。只有独立 Design / Authority Review 给出 PASS 之后，才由该 Review 建立 Frozen Contract、Frozen Construction Plan 与 Design Accepted Head。
在此之前不得开始 S1。本文件不声明 Contract FROZEN、Design PASS 或 P5-C1 STARTED。

坐标说明：`8f12bb69…`（Phase 4 Final Closure Docs Head）**不是**本 package 的 Frozen Base——它遗漏了已经独立 Review 的 F3 / F5 test-only closure；
本 package 的 Frozen Base 是包含该 closure 的 `98ad8eb…`。

---

## 1. 目的、范围与非范围

### 1.1 P5-C1 回答的问题

给定 Amane v0.15.0 的公开插件契约，**一个 FC2 影片查询**能否经过

```text
Amane host
   ↓  SearchQuery
薄 adapter（本 package）
   ↓  canonical FC2 number
fc2_metadata_core（Phase 1-3，不修改）
   ↓  AggregationResult
薄 adapter（本 package）
   ↓  MediaMetadata | None | SourceError
Amane host
```

完成一个**完整、确定性、离线可验证、安全失败**的功能闭环。

### 1.2 Scope（做）

* 插件发现合规的 adapter 目录（`plugin.py` + 支撑模块）、descriptor、配置模型；
* `SearchQuery` → canonical FC2 number 的边界校验（委托 Core 的 normalization）；
* 宿主 `WebClient` → Core `SourceHttpClient` 的传输桥（Transport Bridge）；
* 单个 `MultiSourceEngine` + `SourceResourceGovernor` 的构造、复用与调用；
* `AggregationResult` → `MediaMetadata` / `None` / `SourceError` 的映射（含逐字段表、复数 → 单数窄化、失败优先级）；
* 取消传播、缺失 Core 的失败行为、来源归属、诊断与敏感信息边界；
* 对真实 Amane v0.15.0 公开 API 的**真实宿主见证**（subprocess，脚本化传输，无真实网络）；
* 打包骨架（确定性 zip 构建脚本）与安装 skeleton 说明。

### 1.3 Non-Scope（不做；任何一项出现 = 越权）

* 修改 `src/**`（Core / Organizer 任何生产代码）、修改已 CLOSED package 的行为；
* 真实宿主安装 / 热重载 / 配置 UI 往返验收、真实网络冒烟、v0.15.0 与当前发布版本的兼容矩阵、最终可分发包、Core 的最终供给方式（P5-C2）；
* 批量编排、重试调度、取消 UI（Amane 宿主已有）；
* 图片下载、NFO、移动 / 重命名 / 整理（Amane 宿主与后续 Phase）；
* 持久化、数据库、磁盘缓存、cookie / 凭据存储；
* 新的 diagnostics 子系统；
* 把 Core 的每个内部 source 暴露为独立 Amane 插件，或绕过 Core 改用 Amane 自带聚合（架构已在 Phase 1-3 冻结，本合同不重新投票）；
* 绕过反爬 / 验证码 / Cloudflare challenge（含使用较新 Amane 的浏览器渲染回退；Core 已冻结“不绕过”）。

---

## 2. Authority 与坐标

Authority 优先级（冻结）：Frozen Contract > Frozen Construction Plan > Project Governance > Task Prompt。

本合同直接读取并服从下列 authority（均取自 `98ad8eb…`；Amane 部分取自 exact v0.15.0 源码）：

| Authority | 路径 / 坐标 | 本合同使用方式 |
|---|---|---|
| Phase 0 Amane 勘察 | `docs/PHASE0_AMANE_INTEGRATION_REPORT.md` | 背景；其结论逐条被第 6 节**重新核对**，不照抄 |
| Phase 1 Core 合同 | `docs/specifications/FC2_METADATA_CORE_CONTRACT.md` | normalization、`NormalizedMetadata`、`SourceResult` 不变量 |
| Phase 2 Source / HTTP | `src/fc2_metadata_core/{sources,http}/**`、`docs/review/PHASE2_HANDOFF.md`、`docs/SOURCE_STATUS_MATRIX.md` | `SourceHttpClient` Protocol、每次 fetch 恰好一个请求（Phase 2 已冻结事实） |
| Phase 3 聚合 / 韧性 / 资源控制 | `PHASE3_AGGREGATION_CONTRACT.md`、`PHASE3_RESILIENCE_CONTRACT.md`、`PHASE3_RESOURCE_CONTROL_CONTRACT.md` | 状态语义、重试矩阵、取消语义、governor / breaker |
| Phase 4 Final Acceptance | `docs/specifications/PHASE4_FINAL_ACCEPTANCE_CONTRACT.md` §12.7 / §18 | Phase 5 输入边界；测试隔离；XD-B16（见 §5.3） |
| Phase 5 Entry Authority | `docs/review/PHASE5_ENTRY_AUTHORITY.md` | F3 / F5 闭合背景；XD-B11 |
| 治理 | `docs/PROJECT_GOVERNANCE_ACCELERATION.md` | 四问、风险分级、Evidence Gate |
| Amane v0.15.0 | 第 7 节表 A 列出的 exact 文件与行号 | 公开插件契约 |

Amane exact 坐标（已在本机只读克隆核对，克隆位于仓库之外，**不提交**）：

```text
upstream               : https://github.com/sqzw-x/amane.git
tag                    : v0.15.0（annotated；tag 对象 3292c957a092f85ddde1ba7462ffe9813827f4f1）
commit                 : 45dff2159369883e028a296d775a4598836c1ddd
pyproject              : name = amane, version = 0.15.0, requires-python = ">=3.14"
```

Phase 0 报告写作 “tag SHA 45dff2159369883e028a296d775a4598836c1ddd”：`45dff21…` 是 **commit** SHA，tag 对象是 `3292c957…`。本合同以 commit SHA 为准。

---

## 3. 冻结架构与依赖方向

```text
Amane host（Python >= 3.14）
    ↓ 公开插件 API（amane.plugin）
adapters/amane/fc2_amane_adapter/        ← 本 package（唯一允许 import amane 的新代码）
    ↓ fc2_metadata_core 公开 API（只读使用）
fc2_metadata_core                        ← 不修改
    ↓
可插拔 FC2 sources（fc2db_net / javdb / av123）
```

硬规则：

* `fc2_metadata_core` **不得** import `amane`（既有守卫：`tests/contract/test_core_independent_of_amane.py`）；
* `fc2_organizer` **不得** import `amane`；
* 只有 `adapters/amane/fc2_amane_adapter/plugin.py` 允许 import `amane.plugin` 与 `pydantic`；其余 adapter 模块**必须**既不 import `amane` 也不 import `pydantic`（保证主测试进程可在没有 Amane 的环境里完整测试纯逻辑，第 25 节）；
* adapter **不得** import `fc2_organizer`（P5-C1 不向 Phase 4 链路提供任何 `NormalizedMetadata` / `OrganizePlan`；XD-B16 因此 N/A，见 §5.3）；
* adapter **不得**重新实现 FC2 正则 / 文件名 parser / 聚合 / 重试 / 熔断 / HTTP 客户端。

---

## 4. 治理四问（治理文档第 15 节；记录的是真实判断，不是照抄示例）

### Q1 为什么 P5-C1 不与已完成的 Phase 5 Entry Closure 合并？

Entry Closure（`98ad8eb…`）是**历史 blocker 的关闭**：F3 / F5 的 test-only 改动，其 authority 是 Owner Ratification，其交付物是对既有测试的修正，生产代码零改动。
P5-C1 是**新的用户能力**（Amane 插件），其 authority 是本合同，交付物是新代码与新证据。二者的 authority、能力与实现边界都不同；合并会让一次 Review 同时审计“已关闭的 blocker 修正”与“全新 adapter”，且会使已通过 Review 的 closure 证据失效。
同时，Entry Closure 已经 CLOSED（Review PASS），治理文档第 5 节不追溯修改。

### Q2 为什么 P5-C1 与 P5-C2 分开？（必须给出真实风险理由）

下列理由均来自本次设计中的**直接观测**，不是推测：

1. **宿主漂移是真实的。** 设计期核对发现，当前 Amane `origin/main`（`e1a43d1da689c6985d38b1bd37488b41cdcc44ba`，`app-1.0.1-12-ge1a43d1`）与 v0.15.0 之间，插件与网络层已有实质差异（第 29 节）：`SourceDescriptor.multi_language` 被 `traits` 取代、`SearchQuery.raw_results` 被移除、`WebClient.request` 新增 `max_attempts`、`HttpClient` 增加浏览器回退。
   Phase 0 曾记录“插件目录逐字节相同”，那只对当时的 `v0.16.1` 成立，对今天的 main 已不成立。把“针对冻结的 v0.15.0 API 做出确定性闭环”和“对一个仍在移动的发布线做兼容验收”放进同一次 Review，会让 Reviewer 无法区分“映射错误”与“宿主变化”。
2. **真实宿主验收不是离线、确定性的。** P5-C1 的证据是 subprocess 中真实 Amane 公开 API + 脚本化传输（无网络、可重复）；P5-C2 的证据是真实运行的 Amane 应用上的安装 / 重载 / 配置往返 / 路由接入 / 跨版本 / 实网冒烟，天然带环境依赖。
3. **Core 的供给方式是独立的 authority 决策。** Amane 文档明确写明插件“不能声明自己的 pip 依赖”（`docs/dev/plugins.md`），而 adapter 必须使用独立的 `fc2_metadata_core`。P5-C1 只冻结“Core 必须能在宿主解释器中被 import”（第 8.3 节）；“如何供给”（预装 / 随 zip 打包）属于 P5-C2 并带升级门 U-2。

### Q3 单独的 P5-C2 是否真的降低兼容与发布风险？

是，但带条件：它降低的是**兼容与发布**风险，而不是 adapter 逻辑风险。具体地，它把“当前发布线兼容性”的未知量隔离在 P5-C1 Frozen Contract 之外：若 P5-C2 发现需要改变 P5-C1 的映射语义，必须走 Contract amendment（治理文档第 11.2 节），而不是被悄悄吸收。
条件是：P5-C1 必须把对宿主 API 的使用**限制在 v0.15.0 与当前 main 的公共子集内**（不使用 `max_attempts`、`traits`、`multi_language`、`raw_results`、`partial_result`，也不依赖仅存在于单一版本的行为），否则 P5-C2 不是在做验收而是在做重写。该限制是本合同的不变量 I26。

### Q4 如果取消 P5-C1 / P5-C2 边界，是否影响 correctness / safety / auditability？

* **correctness / safety：不影响。** 两个 package 的映射与安全不变量完全相同；合并不会使任何一条映射更正确或更安全。
* **auditability：影响。** 合并后，一次 Review 必须同时审计“确定性映射 + 有界重试证据”和“环境依赖的兼容 / 安装 / 实网证据”，且后者的任何失败都会反向使前者的 closure 失效。

据此：治理文档第 15 节第 4 问的答案是“影响 auditability”，因此**保留**边界；同时**不**把 P5-C1 内部再拆（不拆 models / config / mapping / error / tests / packaging，见计划第 1 节）。
**P5-C2 并非无条件必需**：若 P5-C1 Final Closure 后，宿主漂移评估（第 29 节）与真实宿主验收均无新增工作，治理上允许 P5-C2 缩减为单纯的兼容与发布验收；不得因此跳过它。**不规划 P5-C3。**

---

## 5. Risk Class 与升级门

### 5.1 裁决：Risk Class = B

依据治理文档第 8.2 节：新 adapter、service / client glue、compatibility bridge。设计调查**没有**发现需要改变风险类别的因素：

* 不修改任何 CLOSED package 的生产语义（`src/**` 零改动）；
* 不引入 persistence、不写文件系统、不存 cookie / 凭据；
* 不引入新的安全边界：adapter 在宿主进程内运行，所有网络请求仍经宿主 `WebClient`；adapter 处理的不可信输入（远端 HTML 派生的字符串）只经由 Core 已有的解析边界进入，输出侧新增一层 URL 卫生过滤（I22）；
* 重试 / 限速的**有界性已被直接证明**（第 15 节，含对真实 v0.15.0 `WebClient` 的实测），不需要修改 CLOSED 的 Core 合同。

### 5.2 强制升级门（任一触发即 STOP，按 C 类重新治理；不得自行按 B 类继续）

```text
U-1 任何 src/** 改动（含 Core 公共 API / 行为）
U-2 需要把 Core 源码复制 / vendor / 打包进 plugin.py 或 plugin 树（Core 供给方式变更；属 P5-C2 决策）
U-3 任何持久化 / 文件写入 / 磁盘缓存（含 data_dir 写入）
U-4 无法在不修改 CLOSED Core 合同的前提下证明重试 / 物理请求数有界（DESIGN BLOCKED）
U-5 需要绕过宿主 HTTP 生命周期（自建 httpx / requests / curl / socket 客户端）
U-6 Core 在 Python 3.14 上出现需要生产修改才能修复的缺陷（第 6 节 W-04：目前只有一个与 adapter 无关的测试假设差异）
U-7 需要修改 ≥ 1 个已 CLOSED package 的既有测试语义（P5-C1 只允许新增测试文件）
U-8 出现新的 security boundary（例如接受凭据 / cookie 配置、引入网络监听、读取宿主数据库）
```

### 5.3 与既有 Debt 的关系

* XD-B11（F3 / F5）：已 CLOSED（Entry Closure Review PASS）。本合同**不重开**。
* P5-ENTRY-CLOSURE-OBS-01（`sys.modules` 缓存命中使 `meta_path` blocker 失效、可能造成 order-dependent）：非阻塞 observation。本合同在第 25 节规定 P5-C1 **不得加重**它。
* XD-B16（P4-C4-R-01，adapter 向 Phase 4 链路提供自构造 `NormalizedMetadata` / `OrganizePlan` 须先裁决容器信任）：**N/A**。P5-C1 adapter 只**消费** Core 产出的 `NormalizedMetadata`、产出 Amane `MediaMetadata`；不构造 `NormalizedMetadata`，不 import `fc2_organizer`。若将来改变，须先裁决 XD-B16。

---

## 6. 设计期实证（Design-time Witness）

本节记录设计者直接执行的核对。它们是**设计期观测**，不是 P5-C1 的施工证据；施工证据由计划第 10 节的 E1..E28 提供。复现脚本见附录 A / B。

| ID | 观测 | 方法 / 结果 |
|---|---|---|
| W-01 | Amane v0.15.0 exact 坐标 | 只读克隆 `sqzw-x/amane`，`git checkout v0.15.0`：`HEAD = 45dff2159369883e028a296d775a4598836c1ddd`；`git rev-parse v0.15.0 = 3292c957…`（tag 对象） |
| W-02 | Amane 要求 Python ≥ 3.14 | `pyproject.toml: requires-python = ">=3.14"`；`src/amane/net/http.py` 使用 PEP 758 语法 `except ValueError, TypeError:`（3.14 才合法）。**宿主解释器 = 3.14+，而 Core 的正式证据环境是 3.11 / 3.12** |
| W-03 | Core 公共 API 的 import 不需要 `httpx` 等第三方包 | 阻断 `httpx / httpcore / requests / aiohttp / curl_cffi / pydantic / amane` 后，在 3.12.10 与 3.14.7 上均可 import `fc2_metadata_core` 及 `aggregation / sources.adapters / normalize / resource_control / http`（附录 B）。`httpx_client` 与 `fc2_organizer.images.transport` 才依赖 `httpx`；adapter 不 import 它们 |
| W-04 | Core 在 3.14 上的基本可用性 | 在 3.14.7 上运行 `tests/unit/{core,sources,aggregation,batch,resource_control,http}` + `tests/contract/test_core_independent_of_amane.py`：**2398 passed / 1 failed**。唯一失败：`tests/unit/http/test_httpx_transport_decode_c3.py::…[punycode]`（3.14 上 `punycode` codec 的行为与该测试假设不同；仅涉及 `HttpxTransport`，adapter 不使用）。另：`tests/unit/execution/test_execution_manifest.py` 在 3.14 / Windows 收集期失败（`'/x'` 在 3.13+ 的 Windows 上不再是绝对路径），属 Phase 4 organizer，**与 P5-C1 无关**，记入 L-07 |
| W-05 | 真实 v0.15.0 `WebClient.request` 的重试 / 状态行为 | 把 `WebClient._session` 换成脚本化会话，调用真实 `request`，统计物理请求数（见下表；脚本见附录 A） |
| W-06 | 真实 v0.15.0 `PluginManager.discover` / `install_plugin_path` 在 Core 缺失时的行为 | 见下方 W-06 记录（脚本见附录 B） |
| W-07 | 宿主漂移（v0.15.0 → 当前） | 见第 29 节 |

**W-05 记录（Amane v0.15.0；`max_retries = 3`，脚本化会话；`ok` = `ok_statuses=frozenset(range(300,600))`）：**

| 场景 | 物理请求数 | 结果 |
|---|---|---|
| 429，不传 `ok_statuses` | 3（退避 ≈1.3 s、4.0 s） | `RequestError(reason=rate_limited, http_status=429)` |
| 429，`ok` | **1** | 返回 `status_code = 429` 的响应 |
| 503，不传 `ok_statuses` | 3 | `RequestError(reason=server_error, http_status=503)` |
| 503，`ok` | **1** | 返回响应 |
| 404，不传 | 1 | `RequestError(reason=not_found, http_status=404)` |
| 404 / 403，`ok` | 1 | 返回响应（Core 可自行分类） |
| `CurlError` × 3，`ok` | 3（退避 ≈1.2 s、5.1 s） | `RequestError(reason=network, http_status=None)` |
| `CurlError, CurlError, 200`，`ok` | 3 | 返回 200 |
| `TimeoutError` × 3，`ok` | 3 | `RequestError(reason=timeout)` |
| 其它 `Exception` | 1（不重试） | `RequestError(reason=unexpected)` |
| `CurlError` × 10，`max_retries = 10` | 10（退避累计 > 120 s） | `RequestError(reason=network)` |
| `max_retries = 0` | **0**（宿主缺陷：一次请求都不发） | `RequestError(reason=network)` |
| 调用方 `asyncio.timeout` 在请求挂起期间到期 | 1 | 调用方得到 `TimeoutError`（取消干净传播） |

**W-06 记录：** `plugin.py` 在顶层 `import fc2_metadata_core` 失败时：`PluginManager.discover()` → `plugin_ids == []`，`failures == [(目录名, 异常消息)]`（**无部分注册**）；`install_plugin_path()` → `ValueError("插件导入失败: <消息>")`；Core 可 import 时，同一目录被正常注册，`descriptor.api_version == "1"`、`capabilities == {film_metadata}`、`content_types == {fc2}`。

---

## 7. 表 A —— Amane Public API Surface（exact v0.15.0，commit `45dff21…`）

文件均相对 Amane 仓库根；行号取自该 commit。**P5-C1 只允许使用本表列出的名字**（由 API manifest 守护，计划 E3）。

### 7.1 导入面与发现

| 项 | 事实 | 坐标 |
|---|---|---|
| 作者导入面 | 插件**只**从 `amane.plugin` 导入；宿主实现在 `amane.plugins.*`，不得被插件依赖 | `src/amane/plugin/__init__.py` 1-78 |
| `amane.plugin.__all__`（与本 package 相关的子集） | `PLUGIN_API_VERSION`、`ContentType`、`FailureReason`、`FetchOptions`、`FilmActor`、`FilmSourcePlugin`、`FilmSourceProvider`、`HttpClient`、`MediaMetadata`、`PluginContext`、`RequestError`、`SearchQuery`、`SourceCapability`、`SourceDescriptor`、`SourceError`、`WebClient` | 同上 |
| `PLUGIN_API_VERSION` | `"1"` | `src/amane/plugins/models.py:14` |
| 发现 | `PluginManager.discover(data_dir)` 扫描 `{data_dir}/plugins/sources/<dir>/`；需 `plugin.py` 中名为 `Plugin` 的 `FilmSourcePlugin` 子类；校验 `api_version`、能力、`descriptor.id == 目录名`、id 不重复；单个失败只记 `failures` | `src/amane/plugins/manager.py:51-141`（`_instantiate_dropin` 51、`_require_matching_capabilities` 64、`discover` 100） |
| 模块加载 | `load_plugin_module`：模块名 `amane_ext_<编码后的 id>`，`spec_from_file_location(..., submodule_search_locations=[目录])`——**目录即包，同目录 `.py` 可相对导入**；`discover()` 先 `purge_imported_plugin_modules()` 清 `amane_ext_*` | `src/amane/plugins/packaging.py:31-62` |
| 安装 | `install_plugin_zip`：zip ≤ 20 MiB，解压后 ≤ 50 MiB，拒绝绝对路径 / `..`；根目录或**单一顶层文件夹**含 `plugin.py`；`inspect_plugin_id` 会真实 import 插件，ImportError → `ValueError("插件导入失败: …")`；落盘目录名取自 `descriptor.id` | `src/amane/plugins/packaging.py:65-135` |
| 内容路由 | 声明 `content_types` 非空时，`validate_hot_settings` 要求被路由的 `ContentType` ∈ `content_types`；声明 `metadata_fields` 非空时，`field_priority` / `field_blacklist` 中的字段须 ∈ `metadata_fields` | `src/amane/plugins/manager.py:235-280` |

### 7.2 类型与签名

| 项 | 事实 | 坐标 |
|---|---|---|
| `FilmSourcePlugin` | 抽象基类；`descriptor()` 为 `classmethod`；`configuration_model()` 返回 `config_model`（缺省 `EmptyPluginConfig`）；`build(self, context: PluginContext, config: BaseModel) -> FilmSourceProvider` 同步抽象方法；插件在 discover 时以**无参**构造 | `src/amane/plugins/api.py:311-345` |
| `FilmSourceProvider` | `async def fetch(self, query: SearchQuery, options: FetchOptions \| None = None) -> MediaMetadata \| None`（抽象、异步） | `src/amane/plugins/api.py:35-42` |
| `PluginContext` | `@dataclass(frozen=True, slots=True)`：`source_id: str`、`http_client: HttpClient`、`web_client: WebClient`、`data_dir: Path` | `src/amane/plugins/api.py:297-308` |
| `SearchQuery` | `@dataclass`（非 Pydantic，**无运行时校验**）：`number: str`、`file_path: str \| None`、`file_hash: str \| None`、`content_type: ContentType \| None`、`partial_result`、`raw_results` | `src/amane/crawlers/models.py:16-25` |
| `FetchOptions` | `@dataclass`：`language: Language \| None` | `src/amane/crawlers/models.py:27-30` |
| `ContentType` | `StrEnum`：`censored / uncensored / chinese / western / fc2 / amateur / hentai` | `src/amane/parsing/file_info.py:26-33` |
| `MediaMetadata` | Pydantic：`number: str`、`title`、`actors: list[FilmActor]`、`studio`、`publisher`、`release`、`runtime: int \| None`、`tags: list[str]`、`series`、`plot`、`poster_urls`、`thumb_urls`、`trailer_urls`、`score`、`external_id: str \| None`、`source_url: str \| None`、`directors: list[str]`、`extrafanart: list[str]`；`release` 经 `normalize_calendar_date`（无法解析 → `None`）；**没有** `fanart_urls` | `src/amane/crawlers/models.py:44-87` |
| `FilmActor` | Pydantic：`name: str`、`gender: ActorGender = UNKNOWN`；`film_actors()` 缺省性别为 **FEMALE**（本 package 禁用） | `src/amane/crawlers/models.py:32-41` |
| `SourceDescriptor` | Pydantic（`extra="forbid"`，frozen）：`id`、`name`、`version = "builtin"`、`api_version = PLUGIN_API_VERSION`、`capabilities = {film_metadata}`、`content_types`、`metadata_fields`、`languages`、`urls`、`multi_language`、`rate_limit (0.1..100)`；`id` 须匹配 `^[a-z0-9][a-z0-9._-]*$` | `src/amane/plugins/models.py:56-92` |
| `SourceCapability` | `StrEnum`：`film_metadata / actor_profile / actor_image / playback` | `src/amane/plugins/models.py:47-53` |
| 第三方 id 规则 | `namespace.local`，各段 `^[a-z0-9][a-z0-9_-]*$`；namespace ∉ `{amane, plugin, official, builtin}` ∪ 内置 `SiteName` | `src/amane/plugins/models.py:18-44` |
| `FailureReason` | `StrEnum`：`http_error / not_found / rate_limited / server_error / timeout / network / cloudflare_challenge / cloudflare_blocked / ip_banned / geo_restricted / age_verification / empty_response / no_usable_metadata / parse_error / crawler_unavailable / unexpected` | `src/amane/net/errors.py:35-58` |
| `SourceError` | `Exception`：`__init__(self, reason: FailureReason, *, http_status: int \| None = None, detail: str \| None = None, url: str \| None = None)`；`RequestError(SourceError)` 增加 `failure` / `message` | `src/amane/net/errors.py:62-97` |
| `WebClient.request` | `async def request(self, method, url, *, headers=None, cookies=None, data=None, json=None, use_proxy=True, timeout=None, allow_redirects=True, ok_statuses=None) -> Response`；`ok_statuses` 内的状态码**视为成功、不重试、不当失败** | `src/amane/net/http.py:139-171`（`WebClient` 139、`request` 161） |
| `HttpClient.web_client` | 属性，“暴露给受信任来源插件的共享低层客户端”；`PluginContext.web_client` 与它是同一实例（`CrawlerFactory._get_plugin` 装配） | `src/amane/crawlers/http.py:15-24`；`src/amane/crawlers/factory.py:94-120` |
| `invoke_source` | 一次来源调用边界：`SourceError` → 记 `FAILED`（原因 / `http_status` / `detail`）；其它 `Exception` → 记 `unexpected`；**返回 `None` → 记 `no_usable_metadata`**；`CancelledError`（`BaseException`）不被捕获 | `src/amane/observability/source.py:10-34` |
| 结果校验 | 工厂的 `_PluginProviderAdapter.fetch` 只在返回值不是 `MediaMetadata` 时 `model_validate` | `src/amane/crawlers/factory.py:32-42` |
| 聚合器对插件结果的使用 | 以 `node.cache_key`（来源 id）为键写入 `external_ids[id] = external_id`、`source_urls[id] = source_url`、`extrafanart_urls[id]`；`fanart` 不是 metadata 字段（整理时取 `thumb`） | `src/amane/aggregate/engine.py:480-525`；`src/amane/media/pipeline.py:37` |
| 来源文档契约 | 未命中返回 `None`；网络 / 拦截 / 可分类业务失败抛 `SourceError`；**不得** `except RequestError: return None`，也不得裸 `except Exception` 吞异常；`SourceError.detail` 不得写入上游 URL / 密钥 | `docs/dev/plugins.md`（“网络和运行时”、“播放源”节） |

---

## 8. 包布局、Core 供给与插件发现（Package Boundary）

### 8.1 仓库布局（冻结）

```text
fc2-organizer/
  adapters/
    amane/                                    ← adapter 工作区根（NOT under src/；不属于 fc2-metadata-core 的发行内容）
      README.md                               ← 安装骨架说明（中文）
      api_manifest/
        amane_v0.15.0_api_manifest.json       ← 由工具从 exact v0.15.0 生成的 API 清单（E3）
      fc2_amane_adapter/                      ← 插件树 = zip 的唯一顶层文件夹的内容；无 __init__.py
        plugin.py                             ← 宿主侧：Plugin / descriptor / config 模型 / provider / 向 Amane 类型的转换
        _core_gate.py                         ← 纯：Core 缺失 / 不兼容时的 ImportError 翻译（冻结的消息模板，第 22 节）
        _settings.py                          ← 纯：配置校验与 Core 配置构造
        _number.py                            ← 纯：SearchQuery → canonical 边界
        _bridge.py                            ← 纯：Amane web client → SourceHttpClient 桥
        _runtime.py                           ← 纯：一次构造、多次复用的 Core 调用封装
        _outcome.py                           ← 纯：AggregationResult → 中立结果（含错误映射与窄化）
  tools/
    amane_api_manifest.py                     ← 清单生成器
    build_amane_plugin_zip.py                 ← 确定性 zip 构建
    run_amane_host_witness.py                 ← 真实宿主见证运行器（subprocess；不是 pytest 测试）
  tests/
    amane_adapter/                            ← 全部新测试（pytest 文件名一律 test_amane_*.py：既有 tests 目录没有 __init__.py，基名必须全局唯一）
      host_scripts/                           ← 只在真实宿主 subprocess 内被执行的场景脚本；pytest 从不导入
    support/amane_host_fakes.py               ← 纯逻辑测试用的“宿主 web client”替身（duck-typed；不 import amane）
  docs/acceptance/evidence/P5_C1_HOST_WITNESS.json   ← 宿主见证日志（S3 产出并提交；E4 / E7 / E9 / E13 …）
```

* `plugin.py` 之外的模块（“纯模块”）**不得** import `amane`、`pydantic`、`httpx`、`requests`、`aiohttp`、`curl_cffi`、`urllib.request`、`socket`、`http.client`、`subprocess`、`sqlite3`；**不得**调用 `open(`、`Path.write_*`、`os.makedirs` 等任何文件系统写入（I14、I18 的 AST 守护）。
* 树内模块互相引用**只许相对导入**（`from ._number import …`）；绝对导入只许标准库、`fc2_metadata_core.*`（第 8.4 节白名单）以及（仅 `plugin.py`）`amane.plugin` / `pydantic`。
* 所有 `fc2_*` 名字**只许模块顶层导入**；禁止函数体内导入（第 25 节，既有测试守卫会清理 `sys.modules`，函数内导入会得到“另一代”模块对象）。
* 语法兼容：树内代码**必须**同时满足 Python 3.11-3.14 的语法（主测试进程在 3.12 上执行纯模块；宿主在 3.14+）。
* 测试通过 `pyproject.toml` 中 `[tool.pytest.ini_options] pythonpath` 增加 `"adapters/amane"` 导入树（唯一允许的 `pyproject.toml` 改动，计划第 4 节）。生产中 Amane 把同一目录作为包 `amane_ext_ffcc_d_fc2_h_metadata` 加载，相对导入两种方式下均成立。
* **打包形态**：zip 的单一顶层文件夹名为插件 id（`ffcc.fc2-metadata/`），其下为 `fc2_amane_adapter/` 的**全部**文件（`plugin.py` 在该文件夹根）；不含 `__pycache__`、测试、文档。确定性构建（排序、固定时间戳、固定权限）。Amane 落盘目录名取自 `descriptor.id`，与 zip 内文件夹名无关；手动放置目录时必须命名为 `ffcc.fc2-metadata`。

### 8.2 入口与发现合规（Plugin Discovery Contract）

| 项 | 冻结值 |
|---|---|
| 入口 | `plugin.py` 顶层导出名为 `Plugin` 的类，继承 `FilmSourcePlugin`；无参构造 |
| `descriptor()` | `classmethod`；每次调用返回等价的 `SourceDescriptor`；**不做 I/O**；除 `amane.plugin` / Core 公共常量外不依赖运行时状态 |
| `descriptor.id` | `ffcc.fc2-metadata`（第 9 节） |
| `descriptor.api_version` | 不显式传参，使用 `PLUGIN_API_VERSION`（默认值）；**不得**硬编码 `"1"` |
| `capabilities` | 仅 `{"film_metadata"}`（以 `SourceCapability.FILM_METADATA.value` 构造） |
| `config_model` | Pydantic 模型（`extra="forbid"`），第 11 节 |
| 加载失败行为 | 任何 import / descriptor 失败 → Amane 记入 `failures`，不注册；第 22 节 |
| `build()` | 同步；只做一次性的校验与构造，**不做网络 I/O**；返回的 provider 是 `FilmSourceProvider` 实例 |

P5-C1 验证“发现合规的 skeleton”（在真实 v0.15.0 `PluginManager.discover` 上，subprocess 中，E4）；**真实运行中的 Amane 应用的安装 / 重载验收属 P5-C2**（第 26 节）。

### 8.3 Core 供给（P5-C1 冻结的最小要求）

```text
P5-C1 供给模式 A（唯一授权）：
  fc2_metadata_core 必须能在 Amane 所在的同一 Python 解释器中被 import
  （即安装到 Amane 的 Python 环境，或位于其 sys.path 上）。
```

* **要求**：Core 以其发行名 `fc2-metadata-core` 安装到宿主解释器（Python ≥ 3.14 for v0.15.0）。adapter 只使用 §8.4 列出的公共名字。
* **缺失行为**：第 22 节。
* **P5-C2 职责**：最终供给方式（pip 安装 / 受控的随包分发）、安装指南、升级流程。若 P5-C2 选择“把未经修改的 Core 包目录随 zip 分发”，必须走 Contract amendment（U-2）并满足：字节一致的构建产物、哈希校验、不得编辑、不得复制进 `plugin.py`、不得新增逻辑。**P5-C1 不授权该模式。**
* **与宿主文档的关系（如实记录）**：Amane 文档写明插件“只使用主机已提供的 API，不能声明自己的 pip 依赖”；因为插件与宿主共享解释器，安装到同一环境的 Core 技术上可 import，但这超出宿主文档承诺的支持范围。该风险记入 L-08，并作为 P5-C2 的显式输入。
* **依赖面**：adapter 不 import `httpx`（W-03）。`pip install fc2-metadata-core` 会带入它声明的 `httpx` 依赖，但 adapter 运行不需要它。

### 8.4 Core 公共 API 白名单（adapter 允许使用的 Core 名字；AST 守护，E17 / E18）

```text
fc2_metadata_core.normalize            : normalize_fc2_number, FC2RecognitionStatus
fc2_metadata_core.aggregation          : AggregationConfig, SourceConfig, RetryPolicy, MultiSourceEngine,
                                         AggregateStatus, AggregationResult, AggregationConfigError,
                                         DEFAULT_MAX_CONCURRENCY, DEFAULT_SOURCE_DEADLINE_SECONDS,
                                         DEFAULT_SOURCE_ORDER, validate_base_url
fc2_metadata_core.sources              : SourceRegistry
fc2_metadata_core.sources.adapters     : build_default_registry, ALL_ADAPTER_CLASSES
fc2_metadata_core.resource_control     : SourceResourceGovernor
fc2_metadata_core.http                 : HttpResponse, HttpTransportError, HttpTimeoutError,
                                         HttpConnectionError, HttpResponseTooLargeError
fc2_metadata_core.http.client          : HttpDecodingError      ← 包 __init__ 未再导出它；从 http.client 导入（既有观察，不改 Core）
fc2_metadata_core.models               : NormalizedMetadata, SourceResult, SourceStatus, SourceErrorKind
```

任何白名单之外的 Core 名字 = 违反本合同（需 Contract amendment）。**禁止**导入 `fc2_metadata_core.http.httpx_client`。

---

## 9. 插件身份与能力

| 项 | 冻结值 | 理由 |
|---|---|---|
| `descriptor.id` | `ffcc.fc2-metadata` | `namespace.local`；`ffcc` 是仓库 / 项目标识（不是个人或品牌名），不在保留命名空间与内置 `SiteName` 中；**该 id 一经真实安装即成为持久化键（raw / source_urls / field_sources），不可再改**。目前没有任何安装，变更成本为零；Design Reviewer 可否决（记入 C-12） |
| `descriptor.name` | `FC2 Metadata (ffcc)` | 人类可读展示名 |
| `descriptor.version` | `0.1.0` | adapter 版本（展示用；与 Core 版本独立） |
| `descriptor.api_version` | `PLUGIN_API_VERSION`（= `"1"`） | 取宿主常量 |
| `capabilities` | `frozenset({"film_metadata"})` | 只声称影片元数据；**不**声称 `playback` / `actor_profile` / `actor_image`；不声称 organize / NFO / 图片下载 / 批量调度（这些不是插件能力） |
| `content_types` | `frozenset({"fc2"})`（= `ContentType.FC2.value`） | 路由校验使该来源只能被挂到 FC2 路由 |
| `metadata_fields` | `frozenset({"title","plot","actors","tags","release","runtime","publisher","studio","poster_urls","thumb_urls","extrafanart"})` | 与表 H 一致；不声称 `directors / series / trailer_urls / score` |
| `languages` | 空 | 不声明语言 |
| `urls` | 由 Core `ALL_ADAPTER_CLASSES` 的 `default_base_url` 按 `DEFAULT_SOURCE_ORDER` 派生 | 单一事实来源；仅用于宿主限速映射与展示 |
| `rate_limit` | 不设置（`None`） | 速率由宿主 `network.rate_limits` / `default_rate_limit` 掌控（第 15 节） |
| `multi_language` / `traits` | **不传** | 跨版本最小公共子集（I26）：v0.15.0 有 `multi_language`，当前 main 改为 `traits`；两者缺省值都表示“不声明” |

---

## 10. 表 B —— `SearchQuery` → canonical FC2 输入

`fetch(query, options=None)` 在**任何网络活动之前**按下列顺序执行；每一行的输出是中立结果（第 16 节）：

| # | 条件 | 处理 | 网络 | 对 Amane 的结果 |
|---|---|---|---|---|
| B1 | `query` 没有 `number` 属性，或 `query.number` 不是 `str`（外来对象 / 宿主缺陷；`SearchQuery` 无运行时校验） | `Failed(unexpected, "invalid search query")` | 无 | `SourceError(UNEXPECTED, detail=固定文本)` |
| B2 | `query.content_type` 既不是 `None` 也不等于 `"fc2"`（`StrEnum` 与 `str` 都按值比较；读取失败视同 B1） | `NoMatch("content_type")` | 无 | 返回 `None` |
| B3 | `len(query.number) > 256`（有界输入） | `NoMatch("number_too_long")` | 无 | `None` |
| B4 | `normalize_fc2_number(query.number)`（Core Phase 1 公开合同）：`NOT_FC2`（含空白 / 缺失号） | `NoMatch("not_fc2")` | 无 | `None` |
| B5 | `RECOGNIZED` | `canonical = result.canonical`（`FC2-<5..8 位 ASCII 数字>`） | 继续 | — |

* **dirty 输入被接受**：`FC2PPV-1234567`、`[广告]FC2-PPV-1234567`、`xxx@FC2PPV-1234567` 等均由 Core 语法规范化；**canonicalization 只在 Core 完成**，adapter 不含任何 FC2 正则 / 前缀剥离 / 数字提取（AST 守护：`_number.py` 不含 `re` 的 FC2 相关用法，不含 `FC2` 字面量解析）。
* **宿主的 canonical 保证不被盲信**：即使宿主已经规范化，B1-B5 仍全部执行。Amane 的号码正则是 `FC2-\d{5,}`（无上界、含 Unicode 数字），Core 是 ASCII `[0-9]{5,8}` 且整串边界；二者不一致时**以 Core 为准**（例如 9 位数字 → `NOT_FC2` → `None`）。
* `file_path`、`file_hash`、`partial_result`、`raw_results`、`FetchOptions.language`：**一律不读取、不记录**（I26：`raw_results` 在较新 main 中已被移除；`file_path` 是宿主本机路径，隐私）。
* “非 FC2 / 缺号 / 号码无效”返回 `None` 是 Amane 文档的约定（“番号不匹配 = 没有找到”），不是吞错：它们没有发生任何请求。外来对象（B1）才是错误。
* 一次 `SearchQuery` → **恰好一个** canonical → **一次** Core 聚合 → **一个** Amane 结果。无批量编排。

---

## 11. 表 C —— Plugin 配置 → Core 配置

### 11.1 用户可配置项（冻结；只暴露有真实用户价值且安全的项）

Pydantic 模型 `Fc2MetadataConfig`（`extra="forbid"`），字段：

| 配置字段 | 类型 / 缺省 | 含义 | Core 目标 |
|---|---|---|---|
| `sources` | `list[SourceEntry] \| None`，缺省 `None` | `None` = 使用 Core 默认来源集合与顺序（`DEFAULT_SOURCE_ORDER`，全部启用，默认 base URL）。非 `None` = **权威列表**：列表顺序即字段优先级；只有列出的来源被配置，未列出的已注册来源不被使用 | `AggregationConfig.sources`（`SourceConfig` 序列；顺序 = 默认字段优先级） |
| `SourceEntry.id` | `str` | 必须是 Core 默认 registry 中已注册的 `source_id` | `SourceConfig.source_id` |
| `SourceEntry.enabled` | `bool = True` | 是否启用 | `SourceConfig.enabled` |
| `SourceEntry.base_url` | `str \| None = None` | 站点镜像 / 迁移域名（Core 设计上“域名迁移是配置变更，不是代码变更”） | `SourceConfig.base_url`（经 Core `validate_base_url`） |
| `source_deadline_seconds` | `float = 20.0`（= `DEFAULT_SOURCE_DEADLINE_SECONDS`），范围 `(0, 600]` | 每个来源的**总**墙钟预算（含宿主重试与退避，第 15 节） | 每个 `SourceConfig.deadline_seconds` |

校验规则（纯模块 `_settings.parse_settings` 全权负责；Pydantic 只声明形状，`model_validator(mode="after")` 调用它）：

* `sources` 为空列表 → 拒绝（用 `None` 表示默认）；未知 `id` → 拒绝并列出已注册 id；`id` 重复 → 拒绝；全部 `enabled = false` → 拒绝；
* `base_url`：必须通过 Core `validate_base_url`（拒绝 userinfo、query / fragment、控制字符、非 http(s)、非法 host 等）——**凭据不得经 URL 进入配置**；
* `source_deadline_seconds`：有限数值，`bool` 不被当作数字，`(0, 600]`——范围**由 Core `SourceConfig` 的校验强制**（adapter 不复制上界常量；该常量没有从 `fc2_metadata_core.aggregation` 包导出，不在 §8.4 白名单内）；
* 所有违规以**确定性、不回显配置值**的消息（只含字段名与允许集合）拒绝；Pydantic 层与 `build()` 各执行一次，**都在任何网络活动之前**；
* 配置**没有任何密钥字段**：字段名不含 `token / secret / password / api_key / cookie / credential / dsn`（宿主脱敏按名字子串匹配）；任何值不得进入日志或 `SourceError.detail`。

### 11.2 冻结的内部默认（**不**暴露给用户）

| 项 | 冻结值 | 理由 |
|---|---|---|
| 每来源 `RetryPolicy` 与聚合级默认 | `RetryPolicy.no_retry()`（`max_attempts = 1`） | 第 15 节：传输重试归宿主，Core 层重试被关闭以避免乘法重试 |
| `max_concurrency` | Core 默认 3 | 与默认来源数一致；`1..64` 范围内 |
| `field_priority` | 不设置（= 来源顺序） | 简化；不暴露 |
| `SourceResourceGovernor` | 默认：`HostLimitPolicy(4)`、`CircuitBreakerPolicy(3, 30.0 s, 1)` | Core 已冻结并经验收的默认；不暴露 |
| 桥的响应体上限 | 5 MiB（与 Core `HttpxTransport` 默认一致） | 第 13 节 |
| 单请求超时 | **不传**（`timeout=None` → 宿主 `network.timeout`） | 宿主拥有请求级超时 |
| 代理 / 限速 / 重试次数 / TLS 策略 | 宿主 | 第 15 节 |

---

## 12. Core 调用与生命周期

`Plugin.build(context, config)` 同步地、**一次性**构造并持有（每个 provider 实例一份，随宿主 `CrawlerFactory` 重建而重建）：

```text
settings  = parse_settings(config)                                     # 纯；失败 → 构造失败（见下）
registry  = build_default_registry()
agg_cfg   = AggregationConfig.create(
                sources=[SourceConfig(id, enabled, base_url, deadline_seconds=D, retry_policy=RetryPolicy.no_retry()) …],
                max_concurrency=DEFAULT_MAX_CONCURRENCY,
                retry_policy=RetryPolicy.no_retry())
governor  = SourceResourceGovernor()                                   # 默认策略
bridge    = AmaneHttpBridge(context.web_client)                        # 第 13 节
engine    = MultiSourceEngine(agg_cfg, registry, bridge, governor=governor)
```

* **复用**：每次 `fetch` 只调用 `engine.aggregate(canonical)`。**禁止**每次 fetch 重建 engine / registry / governor / bridge（测试以构造计数证明，E-mutant M-10）。adapter 是无状态的，governor / breaker 状态是内存态，随 provider 生命周期；宿主 rebuild 时重置（L-09）。
* **没有需要关闭的资源**：bridge 只持有宿主 client 的引用；Core 的 `HttpxTransport` 不被使用，故无 `aclose`。
* **配置校验时机**：Amane 在写配置 / rebuild 时经 Pydantic 校验（`configuration_model().model_validate`），`build()` 再次 `parse_settings`（总是在网络活动之前）。`build()` 抛出的异常由宿主工厂记录并使该来源本次不可用；因为校验已前置，`build()` 在合法配置下**不得抛出**（W2 见证）。
* **单事件循环**：Core 的 resource_control 不是线程安全的、假设单事件循环——与 Amane 宿主一致（L-12）。
* `engine.aggregate` 的调用与 Core 合同一致：非 canonical 输入抛 `InvalidCanonicalNumberInputError`（B 系列已保证不会发生，若发生视为 adapter 缺陷 → `Failed(unexpected)`）。

---

## 13. 表 D —— Amane HTTP → `SourceHttpClient`（Transport Bridge）

### 13.1 直接比较

| | Core `SourceHttpClient`（`fc2_metadata_core.http.client`） | Amane `PluginContext.web_client` |
|---|---|---|
| 调用 | `async get(url, *, headers=None, timeout=None) -> HttpResponse` | `async request(method, url, *, headers=…, timeout=…, ok_statuses=…, …) -> curl_cffi.Response` |
| 非 2xx | **不是错误**：返回带 `status_code` 的 `HttpResponse`，由 adapter 分类 | 默认**抛** `RequestError`（并对 408/429/503/504 重试 `max_retries` 次）；传 `ok_statuses` 的状态码则作为响应返回、不重试 |
| 失败 | 抛 `HttpTransportError` 子类 | 抛 `RequestError(reason, …)` |
| 响应 | `status_code / url / headers / text / elapsed_ms` | `Response`：`status_code / url / headers / content / text` |

二者**不能**直接兼容 → 设计一个薄的 `AmaneHttpBridge`（adapter 本地、纯模块 `_bridge.py`）。

### 13.2 桥的行为（冻结）

```python
class AmaneHttpBridge:                       # 满足 SourceHttpClient Protocol（async get；keyword-only headers / timeout）
    def __init__(self, web_client, *, clock=time.monotonic): ...
    async def get(self, url, *, headers=None, timeout=None) -> HttpResponse: ...
```

| 项 | 规则 |
|---|---|
| 请求 | `await web_client.request("GET", url, headers=dict(headers) if headers else None, timeout=timeout, ok_statuses=frozenset(range(300, 600)))`。**不传** `cookies / data / json / use_proxy / allow_redirects / max_attempts`（取宿主缺省；`max_attempts` 仅存在于较新版本，I26） |
| 为什么传 `ok_statuses` | 实测（W-05）：不传时 429 / 503 被宿主**重试 3 次**并抛 `RequestError`，既违反 Core “`RATE_LIMITED` 永不自动重试”的冻结语义，又使 Core 看不到状态码与响应体（无法做 Cloudflare challenge 检测与 `NOT_FOUND` 分类）。传入后所有 HTTP 状态码以**普通响应**返回，单次物理请求 |
| `status_code` | `resp.status_code`（必须是 `int` 且非 `bool`，否则 `HttpTransportError`） |
| `url` | `str(resp.url)`（最终 URL；缺失或为空则回退为请求 URL） |
| `headers` | 键**统一小写**；同名多值以 `, ` 按宿主迭代顺序连接（确定性）；Core adapter 只读取 `cf-mitigated` |
| `text` | 由 `resp.content`（必须是 `bytes`，否则 `HttpTransportError`）解码：charset 取自 `content-type` 的 `charset=` 参数，缺省 `utf-8`；**未知 charset 名 → 回退 `utf-8`**（与 Core `HttpxTransport` 一致）；`errors="replace"`；`LookupError` / `ValueError`（非文本 codec、`idna`/`undefined`、内嵌 NUL）→ `HttpDecodingError`（Core C3-E02 同一语义）。**主动避免依赖 `punycode`**（W-04：该 codec 行为随解释器版本变化） |
| `elapsed_ms` | 桥用注入的单调时钟包住整个 `request()`（含宿主限速等待与宿主重试）测得 |
| 超大响应 | `len(content) > 5 MiB` → `HttpResponseTooLargeError`（**事后**检查；宿主缓冲整个响应，桥无法流式截断——L-02）。异常消息只含上限数字，不含 URL |
| 外来响应 | 缺属性 / 类型不符 → `HttpTransportError("invalid host response")`，绝不抛裸 `AttributeError` |
| 代理 / 限速 / HTTP 记录 / 指纹 | **继续由宿主生效**：桥只调用 `request`，不创建任何客户端 |
| 禁止 | 在 adapter 内创建 `httpx.Client` / `requests.Session` / curl / socket / `urllib.request`（I3、I4；AST 守护） |

---

## 14. 表 E —— 传输异常映射（Amane → Core）

分类**只**使用公共的结构化属性（`RequestError.reason`，`FailureReason`），**绝不**解析异常消息字符串（I8）。

| 宿主事件 | 宿主侧证据（W-05） | 桥抛出的 Core 异常 | 由此得到的 `SourceErrorKind`（Core `transport_failure_result`） |
|---|---|---|---|
| `RequestError`，`reason == TIMEOUT` | `TimeoutError` × H → `timeout` | `HttpTimeoutError` | `TIMEOUT` |
| `RequestError`，`reason == NETWORK` | `CurlError` × H → `network`；`max_retries = 0` → `network` | `HttpConnectionError` | `CONNECTION_ERROR` |
| DNS / TCP 连接 / TLS 失败 | **NOT DISTINGUISHABLE**（均为 `CurlError`） | 并入上一行（`HttpConnectionError`） | `CONNECTION_ERROR` |
| 重定向超限（宿主 `max_redirects = 20`，不可配） | **NOT DISTINGUISHABLE**（`CurlError`） | 并入 `HttpConnectionError`；桥**从不**抛 `HttpRedirectLimitError` | `CONNECTION_ERROR` |
| 响应体解压失败（`Content-Encoding`） | **NOT DISTINGUISHABLE**（`CurlError`） | 并入 `HttpConnectionError` | `CONNECTION_ERROR` |
| 桥自身的 charset 解码失败 | — | `HttpDecodingError` | `DECODE_ERROR` |
| 响应体超过 5 MiB | — | `HttpResponseTooLargeError` | `RESPONSE_TOO_LARGE` |
| `RequestError`，其它任意 `reason`（含 `unexpected`、`http_error` 等；在 v0.15.0 + `ok_statuses` 下，HTTP 状态类 reason 不可达） | `unexpected` 单次、不重试 | `HttpTransportError`（通用） | `NETWORK_ERROR`（通用 kind） |
| 非 `RequestError` 的 `SourceError` | — | `HttpTransportError`（通用） | `NETWORK_ERROR`（通用） |
| `asyncio.CancelledError` | 取消干净传播 | **原样传播**（桥不捕获） | —（第 18 节） |
| 其它 `Exception`（编程错误） | — | **不捕获**，交由 Core 执行边界：`INVALID_RESPONSE / ADAPTER_EXCEPTION`（消息仅含异常类型名） | `ADAPTER_EXCEPTION` |

桥抛出的所有异常消息都是**固定的、不含 URL / 响应体 / 头 / 宿主异常消息**的短文本（I12）。**fail-closed**：凡是无法区分的，都归入更保守的类别，且不据异常文本猜测。

---

## 15. 重试 / 限速 / 资源控制的所有权与有界性（冻结；这是 P5-C1 必须解决的设计点）

### 15.1 所有权

| 关注点 | 所有者 | 具体规则 |
|---|---|---|
| 传输层重试（`CurlError` / 超时） | **宿主 `WebClient`** | 每次 `request()` 至多 `H` 次物理请求（`H = network.max_retries`，宿主配置 `0..10`，默认 3），退避 `attempt·3 + 2 ± 1` s。插件**无法**在单次调用上关闭它（v0.15.0 没有该参数） |
| HTTP 状态码重试（408 / 429 / 503 / 504） | **无人**（被桥的 `ok_statuses` 关闭） | 所有状态码单次请求；429 / 403 / 404 / 5xx 均不被自动重试，与 Core 冻结矩阵一致 |
| 语义 / 来源级重试 | **无人** | Core 层重试关闭：`RetryPolicy.no_retry()`。放弃的只有“5xx 的 Core 单次重试”；5xx 在一次 fetch 内不重试，由 Amane 的任务级 `RETRY`（仅 `FAILED` 任务）或后续 Phase 6 批量重试承担 |
| 单来源总时限 | **Core** | `source_deadline_seconds`（默认 20 s）覆盖该来源的全部宿主重试与退避，由 `asyncio.timeout` 强制，取消传播进宿主 `request()`（W-05 末行证明干净取消） |
| 站点级限速（Host 限速器） | **宿主 `RateLimiters`** | 在 `request()` 开头**获取一次**（不是每次物理重试一次）；优先级 `network.rate_limits` > descriptor `rate_limit`（本插件为 `None`）> `default_rate_limit`（默认 5 req/s） |
| 每 host 并发上限 | **Core governor** | `HostLimitPolicy` 默认 4；FIFO；等待时间不计入来源 deadline（Core 合同 §5.1） |
| 来源熔断 | **Core governor** | 默认：连续 3 次**最终**失败 → 打开 30 s → 半开 1 次探测；`CIRCUIT_OPEN` 不发请求 |
| 并发的任务数 | **宿主 Worker** | `worker.concurrency`（默认 10）个任务可同时调用 `fetch` |

### 15.2 有界性（冻结的公式）

令：

```text
S = 启用的来源数（≤ Core 默认 registry 的来源数；98ad8eb 时为 3；每个 id 唯一）
H = 宿主 network.max_retries（有效范围 1..10；v0.15.0 中 0 = 一次请求都不发，见 L-04）
D = source_deadline_seconds（默认 20 s，≤ 600 s）
```

* Core 层 attempt 数 **A = 1**（`no_retry`）；Phase 2 已冻结“每次 adapter fetch 恰好一个 `client.get`”。因此每个来源对桥恰好发起 **1 次** `get`，每次 `get` 至多 **H** 次物理请求：

```text
每次 fetch 的桥调用数        = S                       （无熔断打开时；熔断打开的来源 = 0）
每次 fetch 的最大物理请求数  = S × H                   （默认 3 × 3 = 9；v0.15.0 配置空间内上限 3 × 10 = 30）
每来源最大物理请求数         = H
每来源墙钟上限               = D（permit 排队时间不计入，Core 合同 §5.1）
```

* **不存在乘法重试**：A = 1 使 Core 层不再重复宿主重试；`ok_statuses` 使状态码路径恒为 1 次。若设计留下 `A = 2`，上限会变成 `S × 2 × H`，这正是本合同禁止的（M-02 mutant 检验）。
* **没有“两层都会 retry，大概没事”的模糊合同**：以上公式由 E9 的测试在真实 v0.15.0 `WebClient` 上以脚本化会话逐项验证（状态码路径、`CurlError` 路径、超时路径、混合路径、熔断路径、`max_retries ∈ {1, 3, 10}`）。

### 15.3 备选方案及其被拒原因（审计记录）

| 备选 | 被拒原因 |
|---|---|
| Core `max_attempts = 2`（保留 5xx 重试） | `A = 2` 与宿主 `H` 相乘（`S × 2 × H`），且混合路径（先 `CurlError` 再 5xx）会使上界不再可由公式简单表达 |
| 不传 `ok_statuses`，让宿主处理状态码 | 429 被宿主重试 3 次（违反 Core 冻结语义）；Core 看不到响应体（无法识别 challenge / 分类 NOT_FOUND）；`RequestError` 中的失败正文是**截断的**且不含头 / 最终 URL |
| 使用 `HttpClient.get_html` / `get_text` | 丢失状态码 / 头 / 最终 URL；`get_html` 在较新版本会触发浏览器回退（等价于绕过反爬，Core 已冻结“不绕过”） |
| 自建 httpx 客户端以获得完整控制 | 违反 I3 / I4：绕过宿主代理、限速、记录与生命周期 |
| 关闭 governor / breaker | 失去 Core 已验收的 host 并发上限与熔断，对批量刮削不利；它们是内存态、无持久化 |

---

## 16. 表 F —— `AggregateStatus` → 插件结果

Core `AggregationResult` 的冻结语义：`SUCCESS` / `PARTIAL` 都带满足最低成功标准（canonical 号 + 非空标题）的 metadata；`FAILED` 的 `metadata is None`。

adapter 内部的中立结果类型（纯模块 `_outcome.py`，冻结的形状）：

```text
AdapterFound    (record: AdapterRecord, degraded: tuple[(source_id, error_kind_value), ...])
AdapterNoMatch  (why: "content_type" | "number_too_long" | "not_fc2" | "all_not_found")
AdapterFailure  (reason: FailureReason 的字符串值, detail: str)          # reason 属于第 17 节的 7 个值之一
```

| Core 结果 | 中立结果 | 对 Amane |
|---|---|---|
| `SUCCESS` | `AdapterFound(degraded=())` | 返回 `MediaMetadata` |
| `PARTIAL` | `AdapterFound(degraded=<运行性失败的 (来源, kind)，按配置顺序>)` | 返回**可用的** `MediaMetadata`（不是错误）；另记**一条** `WARNING` 日志（第 21 节） |
| `FAILED`，且**没有**任何来源的最终结果是运行性失败（即全部 `NOT_FOUND`） | `AdapterNoMatch("all_not_found")` | 返回 `None`（宿主记 `no_usable_metadata`；这是“未命中”的文档约定） |
| `FAILED`，且**至少一个**来源最终为运行性失败（`BLOCKED / RATE_LIMITED / NETWORK_ERROR / PARSE_ERROR / INVALID_RESPONSE`） | `AdapterFailure(reason, detail)`（第 17 节） | 抛 `SourceError(FailureReason(reason), detail=detail)` |
| 表 B 的 `NoMatch` / `Failed` | 见表 B | `None` / `SourceError(UNEXPECTED)` |
| `engine.aggregate` 抛出非取消的 `Exception`（Core 合同违例等） | `AdapterFailure("unexpected", "internal adapter error: <异常类型名>")` | `SourceError(UNEXPECTED)`（`raise … from exc`；detail 仅含类型名） |

* `PARTIAL → 成功` 的理由：Core 已保证其 metadata 满足最低成功标准；Amane 对插件只有“一个结果”的概念，没有“部分成功”的表示。把 PARTIAL 当作错误会丢弃一份可用且可信的数据。代价（L-05）：被降级的来源在 Amane 的 outcome 里不可见，仅有那一条日志。
* “混合：NOT_FOUND + 运行性失败 → FAILED”选择**报错而不是返回 `None`**：只要有一个来源没有真正回答，就不能声称“没有找到”（该来源可能有这部影片）。
* **永不**抛通用 `Exception`；**永不** `except RequestError: return None`；`SourceError.url` 恒为 `None`，`http_status` 恒为 `None`（`SourceResult` 不携带状态码，不猜测）。

---

## 17. 表 G —— Core 失败 → Amane `SourceError` / `FailureReason`

### 17.1 逐 kind 映射（冻结；对 `SourceErrorKind` 的**全部**成员穷尽，由测试枚举验证；未知新 kind 默认 `unexpected`）

| Core `SourceStatus` / `SourceErrorKind` | 来源 | `FailureReason` |
|---|---|---|
| `NOT_FOUND` / `NOT_FOUND` | 非运行性失败 | —（见表 F） |
| `BLOCKED` / `BLOCKED` | 403、Cloudflare challenge、登录 / 验证重定向（Core 不区分，**不据文本猜测**） | `http_error` |
| `RATE_LIMITED` / `RATE_LIMITED` | HTTP 429 | `rate_limited` |
| `NETWORK_ERROR` / `TIMEOUT` | 桥 `HttpTimeoutError` | `timeout` |
| `NETWORK_ERROR` / `SOURCE_DEADLINE` | 来源总预算耗尽 | `timeout` |
| `NETWORK_ERROR` / `CONNECTION_ERROR` | 桥 `HttpConnectionError` | `network` |
| `NETWORK_ERROR` / `NETWORK_ERROR`（通用） | 通用传输失败 | `network` |
| `NETWORK_ERROR` / `DECODE_ERROR` | 桥解码失败 | `network` |
| `NETWORK_ERROR` / `REDIRECT_ERROR` | （桥从不产生；Core 枚举完整性） | `network` |
| `NETWORK_ERROR` / `CIRCUIT_OPEN` | 熔断器打开，未发请求 | `network` |
| `PARSE_ERROR` / `PARSE_ERROR` | 页面布局漂移 | `parse_error` |
| `INVALID_RESPONSE` / `INVALID_RESPONSE`（通用） | 非 200 的其它状态、解析异常 | `parse_error` |
| `INVALID_RESPONSE` / `RESPONSE_TOO_LARGE` | 响应体 > 5 MiB | `parse_error` |
| `INVALID_RESPONSE` / `HTTP_SERVER_ERROR` | HTTP 5xx | `server_error` |
| `INVALID_RESPONSE` / `ADAPTER_EXCEPTION` | Core adapter 抛异常 | `unexpected` |
| `INVALID_RESPONSE` / `RESULT_CONTRACT_MISMATCH` | 结果合同违例 | `unexpected` |
| 任何未在表中的 `SourceErrorKind` | 将来的新 kind | `unexpected` |

`FailureReason` 的取值只可能是 `http_error / rate_limited / parse_error / server_error / timeout / network / unexpected` 这 7 个，全部存在于 v0.15.0 与当前 main（I26）。**不使用** `cloudflare_*` / `ip_banned` / `geo_restricted` / `age_verification`：Core 的 `BLOCKED` 无法区分它们，错误归因比通用归因更糟。

### 17.2 多来源同时失败的确定性优先级（冻结）

唯一上报的 `reason` = 在所有来源**最终结果**的运行性失败中，按下表**自上而下**第一个出现的 `FailureReason`：

```text
1 http_error   2 rate_limited   3 parse_error   4 server_error   5 timeout   6 network   7 unexpected
```

理由：从“需要运维 / 站点层面处理”到“多半是瞬时问题”由高到低排序，保证同一输入永远得到同一 reason；同级之间不需要再比较（同一 reason 只出现一次）。**排序与集合 / dict 迭代顺序无关**（来源顺序 = 配置顺序）。

### 17.3 `detail` 的冻结格式

```text
detail = "FC2 lookup failed: " + "; ".join(f"{source_id}={kind_value}" for each source, in configuration order)
```

* 列出**所有**参与来源的最终 `(source_id, error_kind 或 "not_found")`——包括 `NOT_FOUND` 的来源，让运维看到全貌；
* 只包含**封闭词汇**：Core 已注册的 `source_id` 与 `SourceErrorKind.value`。**绝不**包含 `SourceResult.error_detail`、异常消息、URL、响应体、头、cookie、配置值、文件路径（I12）；
* 长度有界（≤ 来源数 × 约 40 字符）；
* 另一类固定 detail：`"invalid search query"`（B1）、`"internal adapter error: <ExceptionTypeName>"`。

---

## 18. 取消（Cancellation）

```text
Amane host（invoke_source）
   → provider.fetch
   → runtime.lookup
   → engine.aggregate        （Core：TaskGroup + asyncio.timeout）
   → bridge.get
   → web_client.request      （宿主：可被取消，W-05 末行）
```

* adapter **不得**吞掉取消：整个 adapter 树**不得**出现 `except BaseException`、裸 `except:`、`except asyncio.CancelledError` 后不重抛的代码（AST 守护）；唯一允许的宽捕获是 `runtime` 中包住 `engine.aggregate` 的 `except Exception`（`CancelledError` 是 `BaseException`，不会被捕获），它只把非取消异常转成 `AdapterFailure("unexpected", …)`。
* 取消**不**转换成普通 source failure，**不**产生 `AdapterFailure`；`KeyboardInterrupt` / `SystemExit` 等致命异常同样原样传播。
* Core 已冻结的行为被继承：调用方取消 → `CancelledError` 原样传播，所有同级任务被取消，无遗留后台任务，governor 不泄漏 permit / ticket（E15 以 `GovernorSnapshot` 验证）；宿主 `invoke_source` 只捕获 `Exception`，因此 `CancelledError` 穿过它（W2 以真实 `invoke_source` 验证）。
* 若宿主内部在没有请求取消时自发抛 `CancelledError`：Core 既有规则把该来源记为 `INVALID_RESPONSE / ADAPTER_EXCEPTION`，其它来源继续（继承，不改变）。

---

## 19. 表 H —— `NormalizedMetadata` → `MediaMetadata`（逐字段；确定性；纯函数）

### 19.1 源字段（Core，16 个）→ 目标

| # | Core 字段 | 目标 `MediaMetadata` 字段 | 转换 | 缺失时 | 损失 / 窄化 |
|---|---|---|---|---|---|
| 1 | `number` | `number` | 原样（= 请求的 canonical 号） | 不可能缺失（最低成功标准） | 无 |
| 2 | `title` | `title` | 原样 | 不可能缺失 | 无 |
| 3 | `studio` | `studio` | 原样 | `None` | 无 |
| 4 | `publisher` | `publisher` | 原样 | `None` | 无 |
| 5 | `release` | `release` | **原样传递**；宿主 `normalize_calendar_date` 规范化为 `YYYY-MM-DD` | `None` | 宿主无法解析的值变为 `None`（宿主侧窄化；adapter 不预处理，L-11） |
| 6 | `runtime` | `runtime` | `int`（整分钟，Core 已冻结）；`0` 原样传递 | `None` | 无 |
| 7 | `actors`（`tuple[str]`） | `actors`（`list[FilmActor]`） | `[FilmActor(name=n) …]`，保持 Core 顺序，丢弃空白名；**性别一律 `unknown`**（不使用 `film_actors()` 的 FEMALE 缺省——那是捏造） | `[]` | Core 无性别信息，不伪造 |
| 8 | `tags` | `tags` | `list`，保持顺序 | `[]` | 无 |
| 9 | `plot` | `plot` | 原样 | `None` | 无 |
| 10 | `poster_urls` | `poster_urls` | `list`；**URL 卫生过滤**（I22：只留带 host 的绝对 `http` / `https`），保持顺序 | `[]` | 非 http(s) / 相对 URL 被丢弃 |
| 11 | `thumb_urls` | `thumb_urls` | 同上 | `[]` | 同上 |
| 12 | `fanart_urls` | **无对应字段（NOT REPRESENTABLE）** | 不映射、不并入其它字段 | — | **有意丢弃，已记录（L-06）。** v0.15.0 的 `MediaMetadata` 没有 `fanart_urls`；Amane 的 `fanart.jpg` 来自 `thumb`（`media/pipeline.py:37`：“fanart 不是 metadata 字段，整理时按 JAV 约定取 thumb”）。把“显式 fanart”塞进 `thumb_urls` 会改变 `thumb` 的语义；塞进 `extrafanart` 会把“主 fanart”降级为“额外 fanart”。二者都是把语义不同的东西硬塞进错误字段。当前 3 个已验收 adapter 都不产出 `fanart_urls`，所以实际损失为 0；测试对该字段的处置做完备性守护 |
| 13 | `extrafanart` | `extrafanart` | `list`；URL 卫生过滤 | `[]` | 同 10 |
| 14 | `source_urls`（有序 unique 并集） | `source_url`（单数） | **窄化规则 N-1**（19.2） | `None` | 其余 URL 被丢弃（L-06） |
| 15 | `external_ids`（来源内部 id 映射） | `external_id`（单数） | **窄化规则 N-2**（19.2）——**不使用** Core 的 `external_ids` 值 | 不会缺失 | Core 的内部 provider id 不被表达（L-06） |
| 16 | `field_sources`（Core 内部出处） | —（无对应字段） | 不映射 | — | 仅用于映射内部与诊断，不伪造到 Amane（表 I） |

### 19.2 目标字段反向核对（`MediaMetadata` 的每个字段）

| 目标字段 | 来源 | 缺失行为 |
|---|---|---|
| `number / title / studio / publisher / release / runtime / actors / tags / plot / poster_urls / thumb_urls / extrafanart / source_url / external_id` | 上表 1-11、13-15 | 如上 |
| `series` | Core 没有此字段 | `None` |
| `directors` | Core 没有此字段 | `[]` |
| `trailer_urls` | Core 没有此字段 | `[]` |
| `score` | Core 没有此字段 | `None` |

目标字段集合由 API manifest 固定；若 manifest 中出现本表未处置的目标字段，守护测试失败（E11）。**Core 字段集合也由守护测试穷举**：若 `NormalizedMetadata` 将来新增字段而本表没有处置，测试失败（E11）。

### 19.3 复数 → 单数窄化（确定性；不是 `dict.values()[0]`）

**N-1 `source_url`**：取 `NormalizedMetadata.source_urls` 中**第一个**满足 I22 的绝对 http(s) URL；没有则 `None`。
依据：Core 合并把 `source_urls` 构造为“按字段优先级（默认 = 配置顺序）排序的、精确字符串去重的有序并集”，因此下标 0 是**配置顺序中最靠前、且提供了 URL 的贡献来源**的第一个 URL。这个选择只取决于配置顺序与来源数据，与 dict / set 迭代顺序、完成顺序、时钟、随机数无关。

**N-2 `external_id`**：`canonical_number.split("-", 1)[1]`——即 canonical 号的**数字部分**（FC2 PPV 文章 id，如 `FC2-4825061` → `4825061`）。
依据：Amane 的 `external_id` 是“该影片在**本来源**（插件 id）中的标识”。本插件的“来源”就是 FC2 元数据 Core，其自然身份是 FC2 id——它出现在三个内部来源的 URL 中、与具体哪个内部来源作答无关，且总是可得（最低成功标准保证 canonical 号存在）。
**不**取 Core `external_ids` 中的值（例如 `javdb` 的详情页 id）：把某个内部站点的私有 id 当作“本插件的外部 id”是**伪造出处**（I11），且取哪个键会依赖来源顺序与是否有来源提供它。

两条规则的冲突测试（E12）：构造多个来源提供不同 URL / 不同 `external_ids`，改变配置顺序，断言结果**只**随配置顺序以规定方式变化、且对同一输入完全可复现；`PYTHONHASHSEED` 变化不影响。

### 19.4 空值与顺序

* 标量缺失 → `None`；列表缺失 → `[]`；所有列表保持 Core 的顺序；
* URL 卫生过滤只**删除**不合规项，**不**重排、**不**改写、**不**规范化大小写；
* 映射是 `NormalizedMetadata`（不可变值对象）的**纯函数**：不读取时钟、随机数、环境、文件；相同输入 ⇒ 字节相同的输出（I16）。

---

## 20. 表 I —— 来源归属（Provenance）

| 层 | 含义 | 在 Amane 可见处的表达 |
|---|---|---|
| **Amane 层来源身份** | 本插件的 descriptor id `ffcc.fc2-metadata`（宿主以它为 `cache_key`，写入 `source_urls[id]`、`external_ids[id]`、`extrafanart_urls[id]`、`field_sources`、outcome） | 由宿主按插件 id 自动记录；adapter 不需要、也**不得**自行伪造任何来源标记 |
| **Core 层内部出处** | `NormalizedMetadata.field_sources`、`AggregationResult.contributing_source_ids / source_results / conflicts / source_execution_traces` | **不**写入 `MediaMetadata`、`SourceError`、descriptor；仅用于：① 映射内部（N-1 的顺序）；② 失败 `detail` 中列出内部来源 id + kind（封闭词汇）；③ PARTIAL 的一条日志 |
| 可安全体现在 `source_url` | 最高优先级贡献来源的页面 URL（N-1） | 是（它本来就是一个来源页面链接，不是伪造的归属声明） |
| 可安全体现在 `external_id` | FC2 id（N-2） | 是 |
| **不得** | 把多个内部来源冒充成多个 Amane 插件；把内部 provider id 写进 `external_id`；把 `field_sources` 的内部 id 写进任何 Amane 字段 | — |

宿主聚合器见证（计划 E13）：真实 `amane.aggregate` 对本插件结果的聚合只产生 `…[ffcc.fc2-metadata]` 这一个来源键。

---

## 21. 诊断与敏感信息

P5-C1 **不**建立新的 diagnostics 子系统。

* **绝不**进入 `MediaMetadata` / `SourceError` / descriptor / 日志的内容：`SourceExecutionTrace`、`SourceAttempt`、`SourceResult.error_detail`、原始异常对象与消息、HTTP 响应体、请求 / 响应头、cookie、凭据、配置值、`file_path`、URL（包括 `source_urls` 之外的所有 URL；`SourceError.url` 恒为 `None`）。
* **唯一**的日志：标准库 `logging.getLogger("ffcc.fc2_metadata")`，仅在 `PARTIAL` 时发一条 `WARNING`，消息 = `"partial FC2 result for %s: %s"`，参数为 canonical 号与 `"; ".join(f"{source_id}={kind_value}")`（仅运行性失败的来源，配置顺序）。无其它日志、无 `print`、无 `structlog`（宿主私有）。
* 错误消息：**有界、尽可能结构化、无密钥**（第 14、17 节的固定模板；有界性由测试断言）。

---

## 22. 缺失 Core（Missing Core）

* `plugin.py` 在**模块顶层**导入 adapter 纯模块；这些模块在**模块顶层**导入 Core。导入链失败时，`plugin.py` 捕获 `ImportError` 并交给纯模块 `_core_gate.translate_core_import_error(exc)`（`_core_gate` 自身不 import Core，因此在 Core 缺失时仍可加载）：当且仅当 `exc.name` 属于 `fc2_metadata_core`（即等于或以 `fc2_metadata_core.` 开头）时，返回新的 `ImportError`（`plugin.py` 以 `raise … from exc` 抛出），消息为**冻结的固定中文模板**：

```text
FC2 Metadata Core 未安装或版本不兼容：请在 Amane 所在的 Python 环境中安装 fc2-metadata-core（缺失模块：<exc.name>）
```

  其它 `ImportError`（例如支撑模块缺失）：`translate_core_import_error` 返回 `None`，`plugin.py` **原样重抛原异常**，**不**误报为 Core 缺失。`<exc.name>` 只会是 `fc2_metadata_core[.子模块]` 形式（有界；`exc.name` 为 `None` 或含其它字符时同样返回 `None`）。
* 效果（W-06 已用等价脚本在真实 v0.15.0 上证明）：`discover()` → 该插件进入 `failures`、**不注册**（无部分注册）；`install_plugin_*()` → `ValueError("插件导入失败: …")`（可读的 422 载荷错误）；**没有** `AttributeError` 之类的神秘异常。
* **不得**回退到 Amane 内置的 FC2 爬虫（那会绕过本项目能力）；**不得**注册一个“空壳”插件。
* “Core 已安装但缺少某个公共名字”（版本过旧）同属 `ImportError`，走同一模板。

---

## 23. 无持久化 / 无文件系统 / 无整理职责

* adapter：**无**数据库、**无**持久缓存、**无**文件写入、**无** cookie / 凭据存储；**不使用** `context.data_dir`（宿主工厂自己会 `mkdir plugins/<id>`，那是宿主行为，不是 adapter 的）。
* governor / breaker 状态是**内存态**，随 provider 生命周期（L-09）。
* adapter 只负责“影片元数据来源”能力；**不**负责图片下载、NFO、移动 / 重命名 / 整理、冲突 / 覆盖（Phase 0 已确认这些属于 Amane 宿主与后续 Phase）。
* 守护：纯模块的 AST 扫描禁止文件系统写入 API、`open(`、`subprocess`、`sqlite3`、`shelve`、`pickle` 落盘、`tempfile`、`os.environ` 写入；运行期以“文件系统快照前后相同”验证（E19）。

---

## 24. 确定性

相同的 `SearchQuery` + 插件配置 + Core 结果 ⇒ 相同的 `MediaMetadata`，或相同的结构化错误（reason + detail）。
不使用 `random` / 时钟 / 无序 `set` 或 `dict` 选择做窄化或优先级；所有“选择”都基于配置顺序或固定优先级表。验证：同一场景在 `PYTHONHASHSEED ∈ {0, 1, 2}` 的 subprocess 中输出逐字节相同（E20）；AST 守护 `_outcome.py` / `_runtime.py` 不对 `set` / `frozenset` 做迭代取值。

---

## 25. 测试隔离（P5-ENTRY-CLOSURE-OBS-01）与“真实宿主 vs 测试替身”边界

### 25.1 主进程隔离（冻结）

* **任何 import `amane` 的测试都必须在 subprocess 中运行**，主 pytest 进程**绝不** import `amane` / `amane.*`，因此 P5-C1 的新测试**不污染** `sys.modules`，也不会使已 CLOSED 的架构守卫变得依赖顺序。
* 新测试不使用 `sys.modules` 清理 / 替换 / 注入；不使用 stub `amane` 模块。
* 所有 `fc2_*` 与 `fc2_amane_adapter.*` 名字在测试模块**顶层**导入（P4-C10 合同 §12.7：既有守卫会清理 `fc2_metadata_core.*` 而不恢复，函数内导入会得到另一代模块对象）。
* 静态守护：`tests/**` 中除 `tests/amane_adapter/host_scripts/**`（只在 subprocess 内被执行、从不被 pytest 导入）之外，不得出现 `import amane` / `from amane` / `importlib.import_module("amane…")`。
* 顺序无关证据（E22）：完整套件在三种收集顺序下通过且计数一致——默认、`tests/amane_adapter` 最先、`tests/amane_adapter` 最后；并在 adapter 测试之后运行既有 `tests/contract` 与 `tests/phase4_acceptance`。

### 25.2 真实 Amane 与替身的边界（P5-C1 冻结）

| 测试类别 | 使用什么 | 运行位置 |
|---|---|---|
| 纯逻辑（设置 / 号码边界 / 桥 / 结果映射 / 错误映射 / 窄化 / 有界性 / 取消 / 确定性） | **仓库内替身**：duck-typed 的“宿主 web client”（`tests/support/amane_host_fakes.py`，**不** import amane）+ Core 既有的脚本化 source adapter / `tests/support` 工具 | 主 pytest 进程（Python 3.12） |
| API 形状 | **exact v0.15.0 源码的 AST 清单**（E3）：adapter 使用的每个 `amane.plugin` 名字、`MediaMetadata(...)` 的关键字、`SourceDescriptor(...)` 的关键字、`SourceError(...)` 的关键字、`web_client.request(...)` 的关键字都必须 ∈ 清单 | 主进程（静态，不 import amane） |
| `plugin.py`、发现、descriptor、配置模型、provider 构造、`MediaMetadata` / `SourceError` 的真实构造、`invoke_source`、`CrawlerFactory`、真实 `WebClient.request` 的重试 / `ok_statuses` 语义、`amane.aggregate` 对结果的使用 | **真实 Amane v0.15.0 公共 API**；传输层是**脚本化的 `WebClient._session`**（无真实网络）。由 `tools/run_amane_host_witness.py` 在 Python ≥ 3.14 且已安装 Amane v0.15.0 的解释器中执行 | **subprocess**；产出提交的日志 `P5_C1_HOST_WITNESS.json` |
| 见证日志的**新鲜度与一致性** | 主进程中恒执行的验证测试：日志中 Amane commit / 版本、adapter 树哈希、Core 树哈希与当前仓库一致，且全部场景 `passed` | 主进程（不 skip） |

* **禁止**只靠一个与真实 API 无关的自造 fake 就声称“真实 Amane 兼容”：上表第 3 行是“真实 Amane”的唯一来源。
* **禁止**把 P5-C2 提前塞进 P5-C1：P5-C1 的见证**不**启动 Amane 应用、**不**做真实网络、**不**覆盖当前发布线（第 26、29 节）。
* 见证运行器是**脚本**，不是 pytest 测试：主套件在没有 Python 3.14 + Amane 的环境里也**不会 skip**；独立 Reviewer 以文档化命令重跑见证（计划第 7 节）。
* **环境硬门槛**：S3 必须在真实 Amane v0.15.0 上完成见证。若无法提供 Python ≥ 3.14 + 已安装 Amane v0.15.0 的环境，S3 **STOP**（`needs input`），**不得**降级为“只做替身测试”。

---

## 26. 表 J —— P5-C1 / P5-C2 责任边界

| 能力 / 证据 | P5-C1 | P5-C2 |
|---|---|---|
| adapter 逻辑闭环（SearchQuery → Core → MediaMetadata / None / SourceError） | ✅ 冻结并验证 | 不改动（若需要改动 = Contract amendment） |
| 对 **v0.15.0** 公开 API 的使用（exact SHA） | ✅ API manifest + 真实宿主见证 | 复核仍成立 |
| 发现合规的 skeleton（`PluginManager.discover` / `install_plugin_zip` 的 API 级验证） | ✅ | — |
| **真实运行的 Amane 应用**中的安装 / 卸载 / 重载 / 启停 | ❌ | ✅ |
| 经宿主配置 API 与 TOML 持久化的**配置往返**、内容路由接入（`content_routes`）、UI 渲染 | ❌（仅验证 `model_json_schema()` 与校验） | ✅ |
| **当前发布线**（`v0.16.1` / `v0.17.0` / `app-1.0.x` / main）兼容矩阵与跨版本集成 | ❌（仅记录观察到的漂移，第 29 节） | ✅ |
| 真实网络冒烟（真实站点） | ❌（P5-C1 全离线、确定性） | ✅（或 Phase 6） |
| Core 的**最终供给方式**与最终可分发包（含安装指南、升级流程） | ❌（仅冻结“Core 必须可 import”与确定性 zip 构建骨架） | ✅（含 U-2 决策） |
| Python 3.14 上 adapter + Core 子集测试 | ✅（记录结果） | ✅（回归） |
| HANDOFF | P5-C1 HANDOFF | P5-C2 / Phase 5 Final HANDOFF |

P5-C1 的设计保证**没有阻止 P5-C2 的结构性死路**：adapter 只用 v0.15.0 与当前 main 的公共子集（I26）；Core 供给是单一、可替换的决策点；打包骨架可被 P5-C2 直接扩展。

---

## 27. 不变量

```text
I1  Core / Organizer 永不 import Amane
I2  adapter 只使用 Amane 公开插件 API（amane.plugin），且仅在 plugin.py 中
I3  adapter 使用宿主提供的 HTTP 生命周期（PluginContext.web_client）
I4  不存在独立的 adapter HTTP 客户端（无 httpx / requests / curl / socket / urllib.request）
I5  对本插件而言，Core 仍是唯一的 FC2 多源引擎；不使用 Amane 内置 FC2 爬虫 / 聚合替代
I6  SearchQuery 在任何网络活动之前被校验
I7  番号规范化完全委托给 Core（adapter 不含 FC2 正则 / parser）
I8  失败映射是结构化且确定的（不解析异常 / error_detail 文本）
I9  SUCCESS / PARTIAL 的 metadata 满足 Core 最低成功标准
I10 不存在静默的、任意的复数 → 单数选择（N-1 / N-2 是确定性规则，有冲突测试）
I11 不伪造出处（不把内部 provider id / 多个内部来源冒充成 Amane 来源或 external_id）
I12 诊断与秘密不泄漏到 MediaMetadata / SourceError / descriptor / 日志（封闭词汇）
I13 取消不被吞掉、不被转换
I14 无文件系统改动、无持久化
I15 重试 / 物理请求数有界（第 15 节公式；A = 1）
I16 映射确定性
I17 Phase 1-4 的生产语义不变（src/** 零 diff）
I18 既有架构测试保持顺序无关（主进程从不 import amane；无 sys.modules 操作）
I19 P5-C1 不做 P5-C2 的兼容性 closure
I20 Design Review PASS 之前不开始 P5-C1 实现
——（以下为设计中新增）——
I21 所有 fc2_* 名字只在模块顶层导入；树内只用相对导入；Core 名字限于 §8.4 白名单
I22 输出 URL 卫生：poster / thumb / extrafanart / source_url 只含带 host 的绝对 http(s) URL
I23 错误 / 日志的词汇封闭：只含 Core source_id、SourceErrorKind.value、FailureReason 值与固定模板
I24 插件树布局：plugin.py 在树根；无 __init__.py；纯模块不 import amane / pydantic
I25 树内语法兼容 Python 3.11-3.14
I26 对宿主 API 的使用限于 v0.15.0 与当前 main 的公共子集（不用 max_attempts / traits / multi_language / raw_results / partial_result / check_connectivity）
```

---

## 28. 已知局限（P5-C1 自身；如实记录）

| ID | 局限 |
|---|---|
| L-01 | 宿主传输**无法区分** DNS / 连接 / TLS / 重定向超限 / 内容编码失败（均为 `CurlError`），统一为 `CONNECTION_ERROR`；不据文本猜测 |
| L-02 | 响应体上限只能**事后**检查（宿主缓冲整个响应）；内存 / 流量上界由宿主决定 |
| L-03 | TLS 校验（宿主 `verify=False`）、浏览器指纹伪装、`max_redirects = 20`、代理，都是宿主策略，adapter 继承而不能改变；与 Core 的 `HttpxTransport` 行为（UA、5 次重定向上限）不同 |
| L-04 | v0.15.0 的宿主缺陷：`network.max_retries = 0` 时 `request()` 一次请求都不发 → 所有来源 `CONNECTION_ERROR` → `FAILED / network`（fail-closed、确定性）；较新版本已修复 |
| L-05 | `PARTIAL` 的降级在 Amane 的 outcome 里**不可见**（只有一条 `WARNING` 日志）；Amane 没有“部分成功”的表示 |
| L-06 | 有意不被表达的 Core 数据：`fanart_urls`；`source_urls` 的第 2 项起；全部 `external_ids`；`field_sources`；`conflicts`；演员性别（Core 没有） |
| L-07 | Python 3.14：Core 子集测试 2398 passed / 1 failed（`punycode` 解码假设，仅 `HttpxTransport`）；Phase 4 organizer 在 3.14 / Windows 上有一个收集期失败（`'/x'`）。均与 P5-C1 无关，记录为后续（Phase 6 / 7）平台输入 |
| L-08 | 宿主文档不承诺插件可依赖第三方包；Core 必须预装到宿主解释器（模式 A）；这是 P5-C2 的显式输入 |
| L-09 | governor / breaker 是 provider 级内存态，随宿主 rebuild 重置 |
| L-10 | P5-C1 不做任何真实网络请求；对真实站点的行为证据来自 Phase 2 / 3 的既有验收 |
| L-11 | `release` 由宿主规范化，无法解析 → `None`（宿主侧窄化） |
| L-12 | Core resource_control 非线程安全，要求单事件循环（与宿主一致） |
| L-13 | 较新 Amane 的浏览器回退（挑战页渲染）**不被使用**：Core 的 `BLOCKED` 永不绕过；桥直接使用 `WebClient.request`，不经 `HttpClient.get_html` |
| L-14 | 不规划多语言（`multi_language` / `languages`）；`FetchOptions.language` 被忽略 |

---

## 29. v0.15.0 之后观察到的宿主漂移（P5-C2 输入；**不是**本合同冻结的内容）

设计者在本机克隆中核对了相对 v0.15.0 的变化（`git diff --stat v0.15.0 <ref> -- src/amane/{plugin,plugins,crawlers/models.py,crawlers/http.py,net}`）：

| 参考 | commit | 变更规模（上述路径） |
|---|---|---|
| `v0.16.1` | `786849daa4ac13a5d480b43ea60b78f1e994741b` | 1 文件，+38 −7 |
| `v0.17.0` | `3c416618a9617be1c377694b1a150bf9821a7e6d` | 5 文件，+202 −14（含 `WebClient.request(max_attempts)`） |
| `app-1.0.1` | `5556b8a65835fb2e79ce70be9b324047bf21aba0` | 8 文件，+238 −43 |
| `origin/main`（本次核对时） | `e1a43d1da689c6985d38b1bd37488b41cdcc44ba`（`app-1.0.1-12-ge1a43d1`） | 10 文件，+1003 −131 |

对 main 的具体差异（已读 diff，**仅作 P5-C2 输入**）：

* `SourceDescriptor.multi_language` 被 `traits: frozenset[str]` 取代（P5-C1 不传任何一个，I26）；
* `SearchQuery.raw_results` 被移除（P5-C1 不读取）；
* `FilmSourceProvider.check_connectivity()` 新增（非抽象，缺省 `None`；P5-C1 不覆盖）；
* `WebClient.request` 新增 `max_attempts`，`max_retries` 被澄清为“总尝试次数”且 `0` 不再导致零请求（P5-C1 不传 `max_attempts`）；新增 `WebClient.acquire`；
* `HttpClient` 增加按来源的浏览器回退（`get_html` 在 Cloudflare challenge 时可渲染）；新增 `net/browser.py`、`net/connectivity.py`；`FailureReason` 新增 `api_error`，`RequestFailure.reason`；
* `PluginContext`、`FilmSourcePlugin`、`MediaMetadata`、`PLUGIN_API_VERSION`（仍为 `"1"`）**未变**。

这些漂移**不改变 P5-C1 的设计**，因为 adapter 只使用公共子集；但它们是 P5-C2 必须验收的真实输入。Phase 0 报告关于“插件目录在 v0.15.0 与 main 之间逐字节相同”的结论只对其当时的 `v0.16.1` 成立。

---

## 30. 状态

```text
P5-C1 Design                 : CANDIDATE —— INDEPENDENT DESIGN REVIEW REQUIRED
P5-C1 Contract               : CANDIDATE
P5-C1 Construction Plan      : CANDIDATE
P5-C1 Implementation         : NOT STARTED
Phase 5                      : ENTRY AUTHORIZED
Risk Class                   : B（升级门 U-1..U-8）
New Architecture Blocker     : NONE
Risk Escalation              : NONE（B → C 未触发）
```

唯一 authority transition：独立 Design / Authority Review PASS ⇒ 该 Review 建立 Frozen Contract / Frozen Construction Plan 与 Design Accepted Head ⇒ 才允许 S1。
Design PASS 之后，开发者只能**执行**本合同与计划：不得重新设计、不得调整 S 边界、不得把任何设计项推迟到“开发时再决定”。

### 设计者希望复查者重点质疑的决定（记录，供 Review 使用）

| ID | 决定 | 备选 / 风险 |
|---|---|---|
| C-01 | Core 层重试**关闭**（`no_retry`）；传输重试归宿主 | 失去 5xx 的 Core 单次重试；换来无乘法重试、可用公式证明的上界 |
| C-02 | 桥传 `ok_statuses=range(300,600)` 使用宿主低层 `WebClient.request` | 依赖较低层的公共方法；已有实测（W-05）与跨版本最小子集约束（I26） |
| C-03 | 供给模式 A（Core 预装到宿主解释器），与宿主“插件无第三方依赖”的文档承诺不一致 | 唯一不复制 Core 源码的选择；最终方式交 P5-C2（U-2） |
| C-04 | `external_id` = FC2 id 数字，丢弃 Core 内部 provider id | 避免伪造出处；损失内部 id |
| C-05 | `source_url` = 配置顺序中最靠前贡献来源的首个有效 URL | 其它来源 URL 被丢弃 |
| C-06 | `fanart_urls` NOT REPRESENTABLE（有意丢弃） | 当前 adapter 不产出该字段，实际损失 0 |
| C-07 | `PARTIAL` 返回可用 metadata，仅一条 WARNING 日志 | Amane 没有“部分成功”；降级不可见 |
| C-08 | 非 FC2 / 缺号 / 号码无效返回 `None`（不是 `SourceError`） | 符合 Amane 文档约定；外来对象才是错误 |
| C-09 | 启用 governor / breaker | 内存态；breaker 在网络全断时快速失败 |
| C-10 | 输出 URL 仅保留 http(s) | 对不可信远端字符串的卫生过滤；可能丢弃相对 URL |
| C-11 | 真实宿主见证是**脚本**而不是 pytest 测试，附“新鲜度”测试 | 避免 skip；独立 Reviewer 必须重跑 |
| C-12 | 插件 id 命名空间 `ffcc` | 一经安装即不可变；目前零成本可改 |
| C-13 | 不暴露重试 / 并发 / 熔断 / 字段优先级 | 减少用户 knob，与 Owner Question Gate 一致 |

---

## 附录 A —— 设计期探针脚本：真实 v0.15.0 `WebClient.request`（W-05）

在已安装 Amane v0.15.0 的 Python 3.14 解释器中运行；`_session` 被替换为脚本化会话，不访问网络；`asyncio.sleep` 被替换为记录等待值的假函数。

```python
import asyncio, json
from amane.net.http import WebClient, RateLimiters
from amane.net.errors import RequestError
from curl_cffi import CurlError

class FakeResp:
    def __init__(self, status, body=b"<html>x</html>", url="https://h.example/p"):
        self.status_code = status; self.content = body; self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.text = body.decode("utf-8", "replace")

class FakeSession:
    def __init__(self, script): self.script = list(script); self.calls = 0
    async def request(self, method, url, **kw):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, BaseException): raise item
        return item
    async def close(self): pass

async def run(label, script, ok=None, max_retries=3):
    waits = []; real_sleep = asyncio.sleep
    async def fake_sleep(s): waits.append(round(s, 1))
    asyncio.sleep = fake_sleep
    try:
        wc = WebClient(timeout=10, max_retries=max_retries, limiters=RateLimiters())
        wc._session = FakeSession(script)
        try:
            r = await wc.request("GET", "https://h.example/p", ok_statuses=ok)
            result = f"response status={r.status_code}"
        except RequestError as e:
            result = f"RequestError reason={e.reason.value} http_status={e.http_status}"
        print(label, json.dumps({"result": result, "physical_calls": wc._session.calls, "backoff_waits": waits}))
    finally:
        asyncio.sleep = real_sleep

async def main():
    OK = frozenset(range(300, 600))
    await run("429 no ok_statuses", [FakeResp(429)] * 3)
    await run("429 ok_statuses",    [FakeResp(429)], ok=OK)
    await run("503 no ok_statuses", [FakeResp(503)] * 3)
    await run("503 ok_statuses",    [FakeResp(503)], ok=OK)
    await run("404 no ok_statuses", [FakeResp(404)])
    await run("404 ok_statuses",    [FakeResp(404)], ok=OK)
    await run("403 ok_statuses",    [FakeResp(403)], ok=OK)
    await run("curl x3 ok",         [CurlError("boom")] * 3, ok=OK)
    await run("curl,curl,200",      [CurlError("boom"), CurlError("boom"), FakeResp(200)], ok=OK)
    await run("timeout x3",         [TimeoutError()] * 3, ok=OK)
    await run("unexpected",         [ValueError("zzz")], ok=OK)
    await run("curl x10 retries=10", [CurlError("b")] * 10, ok=OK, max_retries=10)
    await run("max_retries=0",      [FakeResp(200)], ok=OK, max_retries=0)

asyncio.run(main())
```

## 附录 B —— 设计期探针：Core 的 import 面与真实发现行为（W-03、W-06）

**B-1（W-03）**——在 3.12 与 3.14 上分别运行（工作目录 `fc2-organizer/`）：

```python
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("httpx", "httpcore", "amane", "requests", "aiohttp", "curl_cffi", "pydantic"):
            raise ImportError("BLOCKED " + name)
sys.meta_path.insert(0, Block())
sys.path.insert(0, "src")
import fc2_metadata_core
from fc2_metadata_core.aggregation import MultiSourceEngine, AggregationConfig, SourceConfig, RetryPolicy
from fc2_metadata_core.sources.adapters import build_default_registry
from fc2_metadata_core.normalize import normalize_fc2_number
from fc2_metadata_core.resource_control import SourceResourceGovernor
import fc2_metadata_core.http
print("OK", sorted(m for m in sys.modules if m.split(".")[0] in ("httpx", "fc2_organizer")))   # -> OK []
```

**B-2（W-06）**——在已安装 Amane v0.15.0 的 3.14 解释器中：在临时 `data_dir/plugins/sources/ffcc.fc2-metadata/plugin.py` 写入一个顶层 `import fc2_metadata_core`（失败时抛 `ImportError`）并继承 `FilmSourcePlugin` 的最小插件；分别在 Core 不可 import / 可 import 的情况下调用 `PluginManager.discover(data_dir)` 与 `install_plugin_path(...)`。观测结果见第 6 节 W-06。
