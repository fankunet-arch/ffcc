# P5-C1 HANDOFF —— Amane Adapter End-to-End（实现候选）

```text
候选状态              : READY FOR LEVEL 1 REVIEW
Implementation        : COMPLETE CANDIDATE（不是 PASS / CLOSED / FROZEN；这些只能由独立 Review 建立）
Risk Class            : B（B -> C 未触发）
New Architecture Blocker : NONE
Risk Escalation       : NONE
Frozen Contract       : docs/specifications/PHASE5_C1_AMANE_ADAPTER_CONTRACT.md @ 10eba0b8e1d95a49f34becc5ed87301bc2e47320
Frozen Construction Plan : docs/P5_C1_CONSTRUCTION_PLAN.md @ 10eba0b8e1d95a49f34becc5ed87301bc2e47320
Design Accepted Head  : 10eba0b8e1d95a49f34becc5ed87301bc2e47320
Package Frozen Base   : 98ad8eb67bfd3e09701a730487e049f3fc348789
Branch                : claude/phase5-c1-amane-adapter
```

## 1. 坐标与提交链（线性，无 squash / amend / rebase / force push）

| 提交 | 内容 |
|---|---|
| `10eba0b8e1d95a49f34becc5ed87301bc2e47320` | Design Accepted Head（Frozen Contract / Plan） |
| `447ce389de3a8d9f929a6e4744884df42caabe83` | **S1** 宿主边界与骨架 |
| `897a75ef4cb5b90eb4129d30532322a186c4c5b0` | **S2** Core 调用与结果映射 |
| `723af11dbfc74cd752b31a53fd089f38a8241978` | **S3** 端到端合同与证据（见证日志、打包、mutation、隔离） |
| 本 HANDOFF 所在提交（`git log -1 --format=%H -- fc2-organizer/docs/review/P5_C1_HANDOFF.md`） | **Review Candidate Head**（仅新增本文件；所有证据均取自 S3 提交的树） |

* Amane：tag `v0.15.0`（annotated，tag 对象 `3292c957a092f85ddde1ba7462ffe9813827f4f1`），commit `45dff2159369883e028a296d775a4598836c1ddd`；检出位于仓库之外，状态干净；`pip install -e` 到 Python 3.14.7 的见证环境。
* 环境：3.12 = 项目既有 `.venv`（Python 3.12.10，httpx 0.27.2，pytest 9.1.1）；3.14 = Python 3.14.7 + Amane v0.15.0 + pytest + `httpx>=0.27,<0.28`；Core 经 `PYTHONPATH=src`。Windows 11。

## 2. E1..E28 逐项结果

| ID | 结果 | 证据 |
|---|---|---|
| E1 | **PASS** | `git diff --name-only 10eba0b..HEAD`（S1-S3）共 42 个文件，全部 ⊆ 计划 §4.1；`src/**` diff 为空；`git diff --check` 干净；`pyproject.toml` 只改 `[tool.pytest.ini_options] pythonpath` 增加 `"adapters/amane"`；Contract / Plan / 治理 / Phase 4 / Phase 5 Entry 文档 / CLAUDE.md diff 为空 |
| E2 | **PASS** | §4 的 nodeid 清单（附录 A）：每个合同条款至少一个测试 |
| E3 | **PASS** | `adapters/amane/api_manifest/amane_v0.15.0_api_manifest.json`（生成自 `45dff21…`，3.14 上由 `tools/amane_api_manifest.py` 生成，sha256 `ce05be84…22f7c`）；`test_amane_api_manifest.py`（12）核对 adapter 使用的每个 `amane.plugin` 名字 / 构造器关键字 / `request` 关键字；H-01 真实 import 并重新生成清单与已提交清单逐字节相等 |
| E4 | **PASS** | H-02（树与解压后的 zip 树的 descriptor 与合同 §9 逐项相等）、H-03（真实 `install_plugin_zip` 返回 `ffcc.fc2-metadata`，目录名 = id，重装与 `install_plugin_path` 成功）；`test_amane_zip_build.py`（14） |
| E5 | **PASS** | `test_amane_number_boundary.py`（40）：B1-B5 每行；`file_path / raw_results` 不被读取（属性会抛 `AssertionError` 的 query 对象 + AST）；H-08 |
| E6 | **PASS** | 同上：`[广告]FC2PPV-…`、`xxx@FC2PPV-…`、9 位数字、全角数字、空白、非 str、超长（256 / 257 边界）；全部委托 Core（AST：只 import `fc2_metadata_core.normalize` 与 `._outcome`，无字符串解析方法调用） |
| E7 | **PASS** | `test_amane_bridge_response.py`（43）：头小写化与多值连接、charset 矩阵（utf-8 / shift_jis / euc-jp / 未知 / rot13 / base64 / zlib / hex / bz2 / idna / undefined / NUL；**不含 punycode**）、5 MiB 边界、外来响应 11 种；H-09 / H-07 使用真实 `curl_cffi.Response` |
| E8 | **PASS** | `test_amane_bridge_errors.py`（22）：表 E 每行；用“消息被篡改”的异常证明不解析文本；`CancelledError`、`KeyboardInterrupt`、编程错误原样传播；AST：无 `except Exception/BaseException`、不读取 `.message/.detail/.args`；H-10 |
| E9 | **PASS** | 三层口径：L1 桥 `get` 数 = S；L2 host attempts ≤ S×H；L3 network hops ≤ S×H×21。`test_amane_retry_bounds.py`（91）+ `test_amane_runtime_lifetime.py`（9）；H-09 在真实 v0.15.0 `WebClient` 上：状态码 200/403/404/429/503/500/599 × H∈{1,3,10} 每来源恰 1 个 attempt；`CurlError` / 超时 H=3 → 9、H=10 → 30（= S×H）；混合 2/来源；熔断打开后 0 次；`600` → `RequestError(http_error)`、1 attempt、通用 `HttpTransportError` 兜底（detail `=network_error`）；回环无限 302 + 真实 curl_cffi：S3·H3 = **189** 命中、S3·H1 = 63、S1·H10 = 210（均 = S×H×21，每 attempt 21）；`TooManyRedirects` 被按 H 重试 |
| E10 | **PASS** | `test_amane_outcome_status.py`（11）+ H-08：PARTIAL 返回 metadata + 恰 1 条 WARNING；全 NOT_FOUND → `None`；混合 → `SourceError`；引擎异常 → `unexpected` 且 detail 仅含类型名 |
| E11 | **PASS** | `test_amane_metadata_mapping.py`（36）：Core 16 字段与 `MediaMetadata` 18 字段（manifest）均有显式处置，守护测试穷举；`fanart_urls` 不出现在任何输出；URL 卫生过滤矩阵；H-07 黄金值（演员性别 `unknown`） |
| E12 | **PASS** | `test_amane_narrowing.py`（14）：N-1 随配置顺序（3 种顺序得 3 种 URL）、N-2 恒为 canonical 数字且永不取 Core `external_ids`；`PYTHONHASHSEED` 0/1/2 无影响（`test_amane_determinism.py` 与 H-13） |
| E13 | **PASS** | `test_amane_provenance.py`（4）：记录无内部 provenance 字段、detail / 日志词汇封闭；H-12 真实 `amane.aggregate`：`source_urls` / `external_ids` / `field_sources` 只以 `ffcc.fc2-metadata` 为键 |
| E14 | **PASS** | `test_amane_error_mapping.py`（37）：`SourceErrorKind` **全部 16 个成员**逐一断言（15 个有映射 + `NOT_FOUND`）；未知 kind → `unexpected`；优先级在全部子集 / 排列下确定；detail 模板与长度上界；`AdapterFailure` 无 `url / http_status` 字段；H-08 真实 `invoke_source` 记录的 reason / detail |
| E15 | **PASS** | `test_amane_cancellation.py`（7）+ H-11：真实 `invoke_source` 下 `CancelledError` 原样传播、不记录 outcome、governor 空闲、无遗留任务、host 请求被取消；调用方 `asyncio.timeout` 得 `TimeoutError` |
| E16 | **PASS** | `test_amane_missing_core.py`（22）+ H-05：真实 `discover` → `failures` 且不注册、消息 = 冻结模板；`install_plugin_path` → `ValueError("插件导入失败: …")`；Core 版本过旧（缺公共名字）同模板；非 Core 的 `ImportError` 不被误报 |
| E17 | **PASS** | 既有 `tests/contract`（237）全绿；新增 AST 守护：`src/**` 无人 import `amane` / `fc2_amane_adapter` |
| E18 | **PASS** | `test_amane_architecture_guards.py`：无 `httpx / requests / aiohttp / curl_cffi / urllib3 / socket / http.client / urllib.request`，不 import `httpx_client`；M-11 被杀死 |
| E19 | **PASS** | 静态 AST（无写文件 / 子进程 / `print` / `os`）+ `test_amane_no_side_effects.py`（3，运行前后文件系统 / 环境 / socket 活动）+ H-14（`data_dir` 仅出现宿主工厂自建的 `plugins/ffcc.fc2-metadata`；fetch 期间 socket 连接被封堵且零活动） |
| E20 | **PASS** | `test_amane_determinism.py`（4：`PYTHONHASHSEED` 0/1/2 的子进程输出逐字节相同）+ H-13（进程内重复 3 次 + 3 个种子的子进程，payload sha256 `04647e95…e550`）；AST：映射模块不迭代 set，不 import 时钟 / 随机 |
| E21 | **PASS** | M-01..M-17 全部被杀死（§6）；哨兵证明被测代码来自被篡改副本；恢复证明：工作树 `git status` 干净，原树测试全绿 |
| E22 | **PASS（含如实记录）** | 三种收集顺序（§5.1）均 `8376 passed, 40 skipped`，计数一致；主进程从不 import `amane`（哨兵 + 子进程屏蔽 `amane` 后纯逻辑测试仍通过 + adapter / contract 树的收集不 import `amane`）；`tests/**` 静态无 `import amane`（host_scripts 除外）；新测试不写 `sys.modules`。**pre-import 见证（3.14 + 真实 Amane，先 `import amane.plugin` 再运行既有 `tests/contract`）：3 failed / 234 passed**（`test_materialization_architecture.py::test_mapping_works_with_transport_nfo_publication_and_amane_blocked`、`test_nfo_architecture.py::test_explicit_import_of_fc2_organizer_nfo_works_and_renders_with_amane_blocked`、`test_publication_architecture.py::test_prepare_publication_runs_end_to_end_with_amane_blocked_at_runtime`）；对照组（同环境不预导入）237 passed。这是既有的 P5-ENTRY-CLOSURE-OBS-01（`sys.modules` 缓存使 `meta_path` blocker 失效）——属 Entry Closure 范围，**未修复**；P5-C1 新测试未加重 |
| E23 | **PASS** | 3.12：`tests/amane_adapter` 467 passed；3.14 集合 A / B / C 见 §5.2 |
| E24 | **PASS** | `architecture_guards + api_manifest + zip_build`：45 passed（3.12） |
| E25 | **PASS** | `tests/contract`：237 passed（与基线一致） |
| E26 | **PASS** | `pytest tests`：8376 passed, 40 skipped = baseline 7909 passed + 40 skipped + 467 新测试 |
| E27 | **PASS** | 无新增 skip / xfail；3 种顺序的 `SKIPPED` 清单（`-rs`）与 S1 baseline 逐行一致（`diff` 为空；40 个 skip 全部是既有的 Windows / POSIX 平台 skip）；新测试 AST 无 skip / xfail |
| E28 | **PASS** | §9 |

## 3. 测试数字

| 环境 / 范围 | collected | passed | skipped | failed | error | xfail |
|---|---|---|---|---|---|---|
| S1 baseline（3.12，`pytest tests`，HEAD = `10eba0b`） | 7949 | 7909 | 40 | 0 | 0 | 0 |
| 最终顺序 1（默认；3.12） | 8416 | 8376 | 40 | 0 | 0 | 0 |
| 最终顺序 2（adapter 最先；3.12） | 8416 | 8376 | 40 | 0 | 0 | 0 |
| 最终顺序 3（adapter 最后；3.12） | 8416 | 8376 | 40 | 0 | 0 | 0 |
| `tests/amane_adapter`（3.12） | 467 | 467 | 0 | 0 | 0 | 0 |
| `tests/contract`（3.12） | 237 | 237 | 0 | 0 | 0 | 0 |

没有 transient failure；所有运行第一次即全绿（因此没有“第二次才通过”被隐藏的情况）。开发过程中遇到的失败均为测试侧问题，已在 §10 如实列出。

## 4. 合同 -> 实现 -> 测试映射（节选；完整 nodeid 见附录 A）

| 合同条款 | 实现 | 测试文件（`tests/amane_adapter/`；括号为用例数） | Evidence |
|---|---|---|---|
| 表 A / I2 / I26 | `plugin.py`；manifest | `test_amane_api_manifest.py`（12） | E3 |
| §8 布局、I1 / I4 / I14 / I21 / I24 / I25 | 整个插件树 | `test_amane_architecture_guards.py`（19） | E17 E18 E19 |
| 表 C / §11 | `_settings.py` + `plugin.py` 模型 | `test_amane_settings.py`（43） | E5 E23 |
| 表 B / §10 | `_number.py` | `test_amane_number_boundary.py`（40） | E5 E6 |
| 表 D / §13 | `_bridge.py` | `test_amane_bridge_response.py`（43） | E7 |
| 表 E / §14 | `_bridge.py` | `test_amane_bridge_errors.py`（22） | E8 |
| §15 | `_runtime.py` `_bridge.py` | `test_amane_retry_bounds.py`（91） | E9 |
| 表 F / §16 | `_outcome.py` `_runtime.py` | `test_amane_outcome_status.py`（11） | E10 |
| 表 G / §17 | `_outcome.py` | `test_amane_error_mapping.py`（37） | E14 |
| 表 H / §19.1-19.2 | `_outcome.py` `plugin.py` | `test_amane_metadata_mapping.py`（36） | E11 |
| §19.3 | `_outcome.py` | `test_amane_narrowing.py`（14） | E12 |
| 表 I / §20 | `_outcome.py` | `test_amane_provenance.py`（4） | E13 |
| §18 | `_runtime.py` | `test_amane_cancellation.py`（7） | E15 |
| §22 | `_core_gate.py` | `test_amane_missing_core.py`（22） | E16 |
| §24 | 全部 | `test_amane_determinism.py`（4） | E20 |
| §21 / I12 / I23 | `_outcome.py` `_runtime.py` | `test_amane_logging_redaction.py`（5） | E13 E20 |
| §23 / I14 | 全部 | `test_amane_no_side_effects.py`（3） | E19 |
| §12 | `_runtime.py` | `test_amane_runtime_lifetime.py`（9） | E9 E21 |
| §25.3 | `_runtime.py` `_bridge.py` | `test_amane_py314_core_path.py`（1） | E23 E24 |
| §25.1 | — | `test_amane_isolation.py`（5） | E22 |
| 打包骨架 | `tools/build_amane_plugin_zip.py` | `test_amane_zip_build.py`（14） | E4 |
| 见证日志新鲜度 | `tools/run_amane_host_witness.py` | `test_amane_host_witness_log.py`（6） | E4 E7-E9 E13 E15 E16 |
| mutation | 整个插件树 | `test_amane_mutation_nonvacuity.py`（19） | E21 |

非测试模块（下划线前缀，不被 pytest 收集）：`_amane_scenarios.py`、`_determinism_probe.py`；`host_scripts/{h_common,h_scenarios}.py` 只在真实宿主子进程内执行。

## 5. 命令与原始输出摘录

### 5.1 3.12 全量（三种收集顺序；`-rs`）

```text
pytest tests -q                                                              -> 8376 passed, 40 skipped in 671.77s
pytest tests/amane_adapter tests/contract tests/phase4_acceptance tests/unit -q -> 8376 passed, 40 skipped in 666.54s
pytest tests/contract tests/phase4_acceptance tests/unit tests/amane_adapter -q -> 8376 passed, 40 skipped in 670.80s
```

### 5.2 Python 3.14（冻结命令；显式路径；无 `--deselect / --ignore / -k / -m / --lf`）

| 集合 | 结果 |
|---|---|
| **A** Core runtime path（30 个显式路径） | `1833 passed in 30.69s`；collected = passed = 1833；0 failed / error / skipped / xfailed |
| **B** adapter 22 个显式文件 | 3.12 collected **448**；3.14 collected **448**（相等）；3.14 `448 passed in 5.96s`；冻结节点 `test_amane_py314_core_path.py::test_core_runtime_objects_and_one_fake_bridge_aggregate` 出现并 PASSED |
| **C** 真实宿主见证 | `tools/run_amane_host_witness.py` 3.14.7：**H-01..H-15 全部 passed（15/15）**；`amane.commit == 45dff2159369883e028a296d775a4598836c1ddd`；两个树哈希与仓库一致（由 B 中的 `test_amane_host_witness_log.py` 在 3.12 与 3.14 各验证一次）；重跑日志字节完全相同 |
| **D** 明确排除（不属于 P5-C1 门） | 未参与任何筛选；`HttpxTransport` 的 punycode 用例与 Phase 4 的 `'/x'` 收集期失败按 L-07 仅作信息记录（`PYTHONPATH=src` 下 `pytest --collect-only tests` 在 3.14 的唯一收集错误即 `tests/unit/execution/test_execution_manifest.py`；本轮没有为它调整任何命令或判据）。为此 `test_amane_isolation.py` 的收集型测试把范围限定为 adapter 与 contract 两棵树（均可在 3.12 / 3.14 收集），整个 `tests` 的收集由 3.12 全量覆盖 |

## 6. Mutation / non-vacuity（M-01..M-17；工具：`python tests/amane_adapter/test_amane_mutation_nonvacuity.py`）

方法：副本 + 恰好一处补丁 + `-o pythonpath=<副本> src tests` + 哨兵（`test_the_adapter_under_test_is_the_expected_tree`）；每个补丁恰好应用 1 次；失败数 = 子进程内被该补丁导致的失败用例数。

| ID | 变异 | 失败数 | 杀死它的指定测试 |
|---|---|---|---|
| M-01 | 桥不传 `ok_statuses` | 67 | `bridge_response`（1）、`retry_bounds`（66） |
| M-02 | Core 重试 `max_attempts = 2` | 52 | `retry_bounds`（52） |
| M-03 | BLOCKED 不再是运行性失败 | 3 | `error_mapping`（3） |
| M-04 | `source_url` 取最后一个 | 7 | `narrowing`（7） |
| M-05 | `external_id` 取 Core `external_ids` | 4 | `narrowing`（4） |
| M-06 | `except BaseException` 吞取消 | 7 | `cancellation`（5）、`architecture_guards`（2） |
| M-07 | detail 拼入 `error_detail` | 19 | `error_mapping`（19） |
| M-08 | 不规范化 | 12 | `number_boundary`（12） |
| M-09 | `fanart_urls` 并入 `thumb_urls` | 3 | `metadata_mapping`（3） |
| M-10 | 每次 fetch 重建 engine | 1 | `runtime_lifetime`（1） |
| M-11 | 桥 `import httpx` | 2 | `architecture_guards`（2） |
| M-12 | PARTIAL 变错误 | 2 | `outcome_status`（2） |
| M-13 | 全 NOT_FOUND 变错误 | 1 | `outcome_status`（1） |
| M-14 | 优先级取最低 | 6 | `error_mapping`（6） |
| M-15 | 删除一项 kind -> reason | 1 | `error_mapping`（1） |
| M-16 | `plugin.py` 非公共 Amane import | 1 | `api_manifest`（1） |
| M-17 | 纯模块写文件 | 1 | `architecture_guards`（1） |

**重要发现（如实记录）**：首次运行时 M-11 / M-16 / M-17 **存活**——AST 守护 / manifest / side-effect 测试检查的是仓库原树，而不是被测模块所在的树。已修复测试（这些测试现在检查“被导入模块所在的树”，哨兵测试证明其正确性），重跑后 17/17 全部被杀死。未改动任何实现。恢复证明：运行后 `git status --porcelain` 为空，原树测试全绿（§3）。

## 7. 真实宿主见证 H-01..H-15（`docs/acceptance/evidence/P5_C1_HOST_WITNESS.json`）

| ID | 观察到的事实 |
|---|---|
| H-01 | Python 3.14.7；amane 0.15.0 / `45dff21…`；检出干净且 `amane` 从该检出导入；重新生成的 API 清单与已提交清单逐字节相同；35 个 `amane.plugin.__all__` 名字可导入 |
| H-02 | 原树与解压后的 zip 树：descriptor 与合同 §9 逐项相等；配置 JSON Schema 字段 `{base_url, enabled, id, source_deadline_seconds, sources}` 无密钥类名；兄弟模块以 `amane_ext_ffcc_d_fc2_h_metadata._xxx` 作为包成员加载；无 `__init__.py` |
| H-03 | 真实 `install_plugin_zip` → `ffcc.fc2-metadata`；zip 确定性（sha256 `6a8f465a…b7018`）；重装替换；`install_plugin_path` 成功；无 staging 残留 |
| H-04 | 6 个合法配置通过；18 个非法配置被 Pydantic 拒绝；`HotSettings` 路由：`content_routes[fc2]` 与 `field_priority[title]` 接受，路由到 `censored`、`field_priority[directors]`、非法插件配置被拒绝 |
| H-05 | Core 缺失：`discover` → `failures == [固定模板]`、不注册；`install_plugin_path` → `ValueError("插件导入失败: …")`；Core 过旧、非 Core `ImportError`、Core 可 import 四种情形各自符合合同 |
| H-06 | 真实 `CrawlerFactory` 缓存并复用 provider；engine / governor / bridge 对象身份在 3 次 fetch 前后不变；4 种合法配置 `build()` 不抛；非法配置使来源不可用而不使工厂崩溃 |
| H-07 | 真实 `MediaMetadata` 与黄金值逐字段相等（标题、发布日期 `2026-09-19`、runtime 78、publisher、演员性别 `unknown`、`source_url`、`external_id=4979299`、`extrafanart=[]`、无 `fanart_urls`） |
| H-08 | 真实 `invoke_source`：SUCCESS→OK；PARTIAL→OK + 恰 1 条 WARNING；全 NOT_FOUND→`None`（`no_usable_metadata`）；混合→`timeout`；非 FC2 / 缺号 / 非 fc2 类型 / 9 位数字→`None` 且 0 请求；外来 query→`unexpected` / `invalid search query`；403 / 429 / 500 / 503 / 418 / 超时 / `CurlError` / 600 / rot13 charset / >5 MiB / 来源 deadline / 熔断打开的 reason 与 detail 全部等于合同 |
| H-09 | 见 E9：L2 与 L3 的逐项数字与 `S×H`、`S×H×21` 上界；`599` 为普通响应、`600` 走通用兜底 |
| H-10 | `timeout`→timeout/`timeout`；`CurlError`→network/`connection_error`；`unexpected`→network/`network_error`（宿主不重试，1 attempt / 来源）；`600`→同上；重定向超限→network/`connection_error`（**不是** `redirect_error`） |
| H-11 | 取消 / 超时见 E15 |
| H-12 | 真实 `amane.aggregate.aggregate` 可用最小参数调用（无 evidence gap）；各映射只以 `ffcc.fc2-metadata` 为键 |
| H-13 | 3 次进程内重复 + `PYTHONHASHSEED` 0/1/2 子进程：payload 相同 |
| H-14 | 见 E19 |
| H-15 | `max_retries = 0`：0 个 host attempt；所有来源 `connection_error`；`FAILED / network`；确定性 |

证据哈希：见证日志 sha256 `12f2f2f6a4a24048b437c0f6c7775e9f834bb345aeaefae40ccae7038ba38d79`；`adapter_tree_sha256 = df2e7a12be6d7b538409eca7962e643c569c021f38529fb8b10d95d8016f42c0`；`core_tree_sha256 = 6077cd6739424848137f2b8a1d6c37d20cc9cb3185cc94df07774169b3fda026`（哈希对 `.py` 内容做 `\r\n` -> `\n` 规范化，与 `autocrlf` 无关）。

独立 Reviewer 必须以计划 §5.3 的命令重跑见证并比对：

```powershell
<py314> tools\run_amane_host_witness.py --amane-src <amane-checkout@45dff21> --core-src src --adapter-tree adapters\amane\fc2_amane_adapter --out <输出.json>
```

## 8. 合同 C-01..C-13 的实现说明

| ID | 实现 |
|---|---|
| C-01 | Core 重试 `RetryPolicy.no_retry()`（`_settings.build_aggregation_config`）；传输重试归宿主；M-02 证明 `A = 1` 被测试强制 |
| C-02 | 桥使用 `PluginContext.web_client.request(..., ok_statuses=frozenset(range(300,600)))`；W-05 / H-09 在真实 `WebClient` 上复现；只用 v0.15.0 与当前 main 的公共子集（I26，AST + manifest 守护） |
| C-03 | 供给模式 A：不复制 / vendor Core；缺失时固定 `ImportError`（H-05）；最终供给属 P5-C2 |
| C-04 | `external_id` = canonical 数字（N-2）；不取 Core `external_ids`（M-05） |
| C-05 | `source_url` = `source_urls` 中第一个合规 URL（N-1）；随配置顺序（M-04） |
| C-06 | `fanart_urls` NOT REPRESENTABLE：不并入任何字段（M-09），字段处置表穷举 |
| C-07 | PARTIAL 返回可用 metadata + 一条 WARNING（M-12；H-08） |
| C-08 | 非 FC2 / 缺号 / 无效号返回 `None`；外来对象 `SourceError(unexpected)` |
| C-09 | 启用 governor / breaker（默认策略；一次构造复用，M-10）；熔断后 0 请求（H-09） |
| C-10 | 输出 URL 仅保留带 host 的 http(s)（I22；URL 矩阵测试） |
| C-11 | 宿主见证是脚本 + 恒执行的新鲜度测试（哈希 / 场景 / commit / 规范化输出） |
| C-12 | 插件 id `ffcc.fc2-metadata` 原样使用（H-02：命名空间合法、不与内置冲突） |
| C-13 | 只暴露 `sources` 与 `source_deadline_seconds`；不暴露重试 / 并发 / 熔断 / 字段优先级 |

## 9. Known Limitations（合同 L-01..L-15）与 Evidence Gaps

L-01..L-15 全部按合同记录且未被改变；本轮实测补充：

* **L-01 / OBS-03**：重定向超限被宿主按 H 重试，最终为 `connection_error`（H-09 / H-10 实测）。
* **L-02 / L-03**：响应体只能事后检查 5 MiB；TLS、重定向上限、指纹属宿主策略（`_bridge` 的 `MAX_RESPONSE_BYTES`；H-08 的 >5 MiB 用例）。
* **L-04**：v0.15.0 的 `max_retries = 0` 缺陷（H-15 实测）。
* **L-05**：PARTIAL 的降级只在 WARNING 日志可见（H-08 实测）。
* **L-07**：Python 3.14：`punycode` 与 Phase 4 `'/x'` 属集合 D；adapter 的桥解码测试不使用 `punycode`。
* **L-08**：Core 必须预装到宿主解释器（模式 A）。
* **L-15**：Core host permit 在宿主内部 retry 期间持续持有（受来源 deadline 约束）。

**Evidence gaps：无。** H-12 的 `aggregate` 可用最小参数调用，因此没有“记录为 gap”的项。需要独立 Reviewer 注意的事实（不是缺口）：

1. E22 pre-import：3 个既有 Phase 4 守卫在“真实 Amane 已预导入”的同进程里失败（既有 OBS-01，Entry Closure 范围，未修复，新测试未加重；对照组全绿）。
2. P5-C1 全离线；唯一的网络活动是 H-09 / H-10 的 127.0.0.1 回环服务器（用于证明每 attempt 21 跳）。
3. 真实运行中的 Amane 应用的安装 / 重载 / 配置往返、当前发布线兼容、最终分发包与 Core 供给：P5-C2。

## 10. 偏差与实现裁决记录（均在 Frozen Contract 之内；合同 / 计划未被修改）

1. **桥不 import amane 与“不得宽捕获”的并存**：合同 §8.1 要求纯模块不 import `amane`，§18 要求除 `_runtime` 外不得 `except Exception`，而 §14 要求按 `RequestError.reason` 分类。实现：`AmaneHttpBridge.__init__` 增加两个仅限关键字、缺省为 `()` 的参数 `request_error_types` / `source_error_types`，由 `plugin.py` 注入 `(RequestError,)` / `(SourceError,)`；`except ()` 什么也不捕获，因此默认桥不吞任何宿主异常；分类仍只读结构化 `reason`。合同 §13.2 的构造器签名 `(web_client, *, clock)` 是其前缀，未被破坏。
2. `_outcome.py` 的中立结果类型在 S1 建立（`_number.py` 需要它），映射在 S2 补入；布局文件集合与合同一致。
3. Amane 源码使用 PEP 758 语法，`tools/amane_api_manifest.py` 须在 3.14 下运行（工具自身语法兼容 3.11；已提交的清单只被 3.12 / 3.14 读取）。
4. `tests/amane_adapter/` 下新增两个下划线前缀的非测试 helper（`_amane_scenarios.py`、`_determinism_probe.py`，位于计划 §4.1 允许的 `tests/amane_adapter/**`）；守护测试断言其集合恰好如此。
5. 测试侧问题（均已修复，无实现改动）：`FakeWebClient.add` 是追加语义，新增 `replace`；mutation 子进程的 `-o pythonpath` 必须使用正斜杠（pytest 用 shlex 切分）；AST / manifest / side-effect 测试曾检查仓库原树而非被测树（导致 M-11/M-16/M-17 初始存活，见 §6）；`sys.modules` 守护最初把只读的哨兵断言也当作篡改，现只禁止清理 / 替换 / 注入；见证场景中 `FakeRecorder` 需实现 `record_http`（真实 `WebClient` 经 ContextVar 调用 Recorder）；H-13 的子进程 stdout 含宿主 structlog 日志，只比较标记行。
6. 3.14 的 `test_amane_isolation.py` 收集型测试范围限定为 adapter + contract 两棵树（原因见 §5.2 D）。
7. 行尾：仓库 `core.autocrlf=true`，新文件以 LF 提交；树哈希与 zip 内容都对 `.py` 做 LF 规范化，因此不依赖检出的行尾设置。

## 11. 状态

```text
P5-C1 Implementation    : COMPLETE CANDIDATE
P5-C1                   : READY FOR LEVEL 1 REVIEW
Risk Class              : B
New Architecture Blocker: NONE
Risk Escalation         : NONE
src Diff                : NONE
Contract / Plan Diff    : NONE
Next                    : P5-C1 INDEPENDENT LEVEL 1 REVIEW（Reviewer 必须自行重跑 §7 的见证命令与计划 §5.3 的 3.14 集合 A / B）
DO NOT START P5-C2
```

---

## 附录 A —— `tests/amane_adapter` 全部 nodeid（467；合同映射见 §4）

```text
tests/amane_adapter/test_amane_api_manifest.py::test_manifest_is_generated_from_exact_v0_15_0
tests/amane_adapter/test_amane_api_manifest.py::test_manifest_records_the_contract_table_a_facts
tests/amane_adapter/test_amane_api_manifest.py::test_plugin_py_imports_only_public_amane_plugin_names_from_the_manifest
tests/amane_adapter/test_amane_api_manifest.py::test_no_other_adapter_module_imports_amane
tests/amane_adapter/test_amane_api_manifest.py::test_keywords_used_with_amane_constructors_exist_in_the_manifest[SourceDescriptor-<lambda>]
tests/amane_adapter/test_amane_api_manifest.py::test_keywords_used_with_amane_constructors_exist_in_the_manifest[MediaMetadata-<lambda>]
tests/amane_adapter/test_amane_api_manifest.py::test_keywords_used_with_amane_constructors_exist_in_the_manifest[FilmActor-<lambda>]
tests/amane_adapter/test_amane_api_manifest.py::test_keywords_used_with_amane_constructors_exist_in_the_manifest[SourceError-<lambda>]
tests/amane_adapter/test_amane_api_manifest.py::test_web_client_request_keywords_exist_in_the_manifest
tests/amane_adapter/test_amane_api_manifest.py::test_descriptor_declares_only_the_cross_version_subset
tests/amane_adapter/test_amane_api_manifest.py::test_no_single_version_host_names_are_used_anywhere_in_the_tree
tests/amane_adapter/test_amane_api_manifest.py::test_enum_members_used_by_the_plugin_exist_in_the_manifest
tests/amane_adapter/test_amane_architecture_guards.py::test_the_adapter_under_test_is_the_expected_tree
tests/amane_adapter/test_amane_architecture_guards.py::test_layout_is_exactly_the_frozen_plugin_tree
tests/amane_adapter/test_amane_architecture_guards.py::test_every_tree_file_is_python_3_11_compatible_syntax
tests/amane_adapter/test_amane_architecture_guards.py::test_imports_are_module_level_only_never_inside_functions
tests/amane_adapter/test_amane_architecture_guards.py::test_intra_tree_imports_are_relative_only
tests/amane_adapter/test_amane_architecture_guards.py::test_core_names_are_limited_to_the_contract_whitelist
tests/amane_adapter/test_amane_architecture_guards.py::test_pure_modules_import_only_stdlib_subset_core_and_siblings
tests/amane_adapter/test_amane_architecture_guards.py::test_plugin_py_is_the_only_module_allowed_amane_and_pydantic
tests/amane_adapter/test_amane_architecture_guards.py::test_no_independent_http_client_anywhere_in_the_tree
tests/amane_adapter/test_amane_architecture_guards.py::test_pure_modules_have_no_filesystem_write_or_process_side_effects
tests/amane_adapter/test_amane_architecture_guards.py::test_cancellation_is_never_swallowed_no_broad_except_outside_runtime
tests/amane_adapter/test_amane_architecture_guards.py::test_runtime_has_a_single_broad_except_wrapping_only_engine_aggregate
tests/amane_adapter/test_amane_architecture_guards.py::test_no_set_iteration_in_mapping_modules
tests/amane_adapter/test_amane_architecture_guards.py::test_plugin_py_has_the_frozen_entry_shape
tests/amane_adapter/test_amane_architecture_guards.py::test_no_test_imports_amane_except_host_scripts
tests/amane_adapter/test_amane_architecture_guards.py::test_new_tests_never_clear_replace_or_inject_sys_modules_or_stub_amane
tests/amane_adapter/test_amane_architecture_guards.py::test_new_tests_have_no_skip_or_xfail
tests/amane_adapter/test_amane_architecture_guards.py::test_new_test_modules_are_named_uniquely_and_host_scripts_are_not_collectable
tests/amane_adapter/test_amane_architecture_guards.py::test_core_and_organizer_never_import_amane_and_nothing_else_imports_the_adapter
tests/amane_adapter/test_amane_bridge_errors.py::test_request_error_reason_maps_to_core_exception_and_kind[timeout-HttpTimeoutError-SourceErrorKind.TIMEOUT]
tests/amane_adapter/test_amane_bridge_errors.py::test_request_error_reason_maps_to_core_exception_and_kind[network-HttpConnectionError-SourceErrorKind.CONNECTION_ERROR]
tests/amane_adapter/test_amane_bridge_errors.py::test_request_error_reason_maps_to_core_exception_and_kind[unexpected-HttpTransportError-SourceErrorKind.NETWORK_ERROR]
tests/amane_adapter/test_amane_bridge_errors.py::test_request_error_reason_maps_to_core_exception_and_kind[http_error-HttpTransportError-SourceErrorKind.NETWORK_ERROR]
tests/amane_adapter/test_amane_bridge_errors.py::test_request_error_reason_maps_to_core_exception_and_kind[server_error-HttpTransportError-SourceErrorKind.NETWORK_ERROR]
tests/amane_adapter/test_amane_bridge_errors.py::test_request_error_reason_maps_to_core_exception_and_kind[rate_limited-HttpTransportError-SourceErrorKind.NETWORK_ERROR]
tests/amane_adapter/test_amane_bridge_errors.py::test_request_error_reason_maps_to_core_exception_and_kind[not_found-HttpTransportError-SourceErrorKind.NETWORK_ERROR]
tests/amane_adapter/test_amane_bridge_errors.py::test_request_error_reason_maps_to_core_exception_and_kind[cloudflare_challenge-HttpTransportError-SourceErrorKind.NETWORK_ERROR]
tests/amane_adapter/test_amane_bridge_errors.py::test_mapping_never_reads_the_exception_message[unexpected-timeout while connecting to the network; dns failure; connection refused]
tests/amane_adapter/test_amane_bridge_errors.py::test_mapping_never_reads_the_exception_message[timeout-connection reset; TLS handshake failed; network is unreachable]
tests/amane_adapter/test_amane_bridge_errors.py::test_mapping_never_reads_the_exception_message[network-operation timed out after 30s]
tests/amane_adapter/test_amane_bridge_errors.py::test_non_request_source_error_is_generic_even_if_its_reason_says_timeout
tests/amane_adapter/test_amane_bridge_errors.py::test_raised_messages_are_fixed_short_texts_without_url_or_host_message
tests/amane_adapter/test_amane_bridge_errors.py::test_cancellation_propagates_unchanged
tests/amane_adapter/test_amane_bridge_errors.py::test_task_cancel_while_the_host_request_hangs_is_not_converted
tests/amane_adapter/test_amane_bridge_errors.py::test_programming_errors_are_not_caught[error0]
tests/amane_adapter/test_amane_bridge_errors.py::test_programming_errors_are_not_caught[error1]
tests/amane_adapter/test_amane_bridge_errors.py::test_programming_errors_are_not_caught[error2]
tests/amane_adapter/test_amane_bridge_errors.py::test_programming_errors_are_not_caught[error3]
tests/amane_adapter/test_amane_bridge_errors.py::test_fatal_exceptions_propagate
tests/amane_adapter/test_amane_bridge_errors.py::test_without_injected_host_types_nothing_is_mapped
tests/amane_adapter/test_amane_bridge_errors.py::test_bridge_ast_has_no_broad_except_and_never_reads_exception_text
tests/amane_adapter/test_amane_bridge_response.py::test_request_uses_only_the_frozen_keywords
tests/amane_adapter/test_amane_bridge_response.py::test_no_headers_and_no_timeout_pass_none
tests/amane_adapter/test_amane_bridge_response.py::test_ok_statuses_covers_300_to_599_exactly
tests/amane_adapter/test_amane_bridge_response.py::test_bridge_satisfies_the_source_http_client_shape
tests/amane_adapter/test_amane_bridge_response.py::test_every_status_is_an_ordinary_response[200]
tests/amane_adapter/test_amane_bridge_response.py::test_every_status_is_an_ordinary_response[301]
tests/amane_adapter/test_amane_bridge_response.py::test_every_status_is_an_ordinary_response[403]
tests/amane_adapter/test_amane_bridge_response.py::test_every_status_is_an_ordinary_response[404]
tests/amane_adapter/test_amane_bridge_response.py::test_every_status_is_an_ordinary_response[429]
tests/amane_adapter/test_amane_bridge_response.py::test_every_status_is_an_ordinary_response[500]
tests/amane_adapter/test_amane_bridge_response.py::test_every_status_is_an_ordinary_response[503]
tests/amane_adapter/test_amane_bridge_response.py::test_every_status_is_an_ordinary_response[599]
tests/amane_adapter/test_amane_bridge_response.py::test_final_url_and_fallback
tests/amane_adapter/test_amane_bridge_response.py::test_headers_are_lowercased_and_multi_values_joined_in_host_order
tests/amane_adapter/test_amane_bridge_response.py::test_elapsed_ms_is_measured_with_the_injected_clock_around_the_whole_request
tests/amane_adapter/test_amane_bridge_response.py::test_dict_like_headers_are_supported
tests/amane_adapter/test_amane_bridge_response.py::test_charset_matrix_decodes_declared_text[utf-8-\u65e5\u672c\u8a9e\u30bf\u30a4\u30c8\u30eb]
tests/amane_adapter/test_amane_bridge_response.py::test_charset_matrix_decodes_declared_text[shift_jis-\u65e5\u672c\u8a9e\u30bf\u30a4\u30c8\u30eb]
tests/amane_adapter/test_amane_bridge_response.py::test_charset_matrix_decodes_declared_text[euc-jp-\u65e5\u672c\u8a9e\u30bf\u30a4\u30c8\u30eb]
tests/amane_adapter/test_amane_bridge_response.py::test_charset_matrix_decodes_declared_text[UTF-8-ascii]
tests/amane_adapter/test_amane_bridge_response.py::test_charset_matrix_decodes_declared_text["utf-8"-quoted]
tests/amane_adapter/test_amane_bridge_response.py::test_missing_charset_defaults_to_utf8_and_replaces_invalid_bytes
tests/amane_adapter/test_amane_bridge_response.py::test_unknown_charset_name_falls_back_to_utf8_like_core_transport
tests/amane_adapter/test_amane_bridge_response.py::test_non_text_or_unusable_charset_is_a_decoding_error[rot13]
tests/amane_adapter/test_amane_bridge_response.py::test_non_text_or_unusable_charset_is_a_decoding_error[base64]
tests/amane_adapter/test_amane_bridge_response.py::test_non_text_or_unusable_charset_is_a_decoding_error[zlib]
tests/amane_adapter/test_amane_bridge_response.py::test_non_text_or_unusable_charset_is_a_decoding_error[hex]
tests/amane_adapter/test_amane_bridge_response.py::test_non_text_or_unusable_charset_is_a_decoding_error[bz2]
tests/amane_adapter/test_amane_bridge_response.py::test_non_text_or_unusable_charset_is_a_decoding_error[idna]
tests/amane_adapter/test_amane_bridge_response.py::test_non_text_or_unusable_charset_is_a_decoding_error[undefined]
tests/amane_adapter/test_amane_bridge_response.py::test_non_text_or_unusable_charset_is_a_decoding_error[utf-8\x00x]
tests/amane_adapter/test_amane_bridge_response.py::test_five_mebibyte_boundary
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response0]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response1]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response2]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response3]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response4]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response5]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response6]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response7]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response8]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response9]
tests/amane_adapter/test_amane_bridge_response.py::test_foreign_responses_become_generic_transport_errors_never_attribute_errors[response10]
tests/amane_adapter/test_amane_cancellation.py::test_cancel_while_all_sources_hang_propagates_cancelled_error_and_leaks_nothing
tests/amane_adapter/test_amane_cancellation.py::test_caller_timeout_cancellation_is_a_timeout_not_a_source_failure
tests/amane_adapter/test_amane_cancellation.py::test_cancellation_is_never_converted_into_an_adapter_failure
tests/amane_adapter/test_amane_cancellation.py::test_source_deadline_is_a_timeout_failure_with_all_sources_released
tests/amane_adapter/test_amane_cancellation.py::test_fatal_exceptions_from_the_host_client_are_not_converted[KeyboardInterrupt]
tests/amane_adapter/test_amane_cancellation.py::test_fatal_exceptions_from_the_host_client_are_not_converted[SystemExit]
tests/amane_adapter/test_amane_cancellation.py::test_a_spontaneous_host_cancelled_error_is_isolated_by_core_to_one_source
tests/amane_adapter/test_amane_determinism.py::test_repeated_lookups_are_identical
tests/amane_adapter/test_amane_determinism.py::test_probe_output_is_byte_identical_under_three_hash_seeds
tests/amane_adapter/test_amane_determinism.py::test_probe_is_not_vacuous_it_really_depends_on_configuration_order
tests/amane_adapter/test_amane_determinism.py::test_mapping_modules_import_no_clock_random_or_environment_module
tests/amane_adapter/test_amane_error_mapping.py::test_every_source_error_kind_has_an_explicit_disposition
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[BLOCKED]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[RATE_LIMITED]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[NETWORK_ERROR]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[PARSE_ERROR]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[INVALID_RESPONSE]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[TIMEOUT]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[CONNECTION_ERROR]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[DECODE_ERROR]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[REDIRECT_ERROR]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[SOURCE_DEADLINE]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[CIRCUIT_OPEN]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[HTTP_SERVER_ERROR]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[RESPONSE_TOO_LARGE]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[ADAPTER_EXCEPTION]
tests/amane_adapter/test_amane_error_mapping.py::test_each_kind_maps_through_the_whole_aggregation_boundary[RESULT_CONTRACT_MISMATCH]
tests/amane_adapter/test_amane_error_mapping.py::test_unknown_kinds_default_to_unexpected[unknown0]
tests/amane_adapter/test_amane_error_mapping.py::test_unknown_kinds_default_to_unexpected[network_error]
tests/amane_adapter/test_amane_error_mapping.py::test_unknown_kinds_default_to_unexpected[None]
tests/amane_adapter/test_amane_error_mapping.py::test_unknown_kinds_default_to_unexpected[7]
tests/amane_adapter/test_amane_error_mapping.py::test_unknown_kinds_default_to_unexpected[SourceStatus.BLOCKED]
tests/amane_adapter/test_amane_error_mapping.py::test_reasons_used_are_the_seven_frozen_values_all_present_in_both_hosts
tests/amane_adapter/test_amane_error_mapping.py::test_pick_reason_follows_the_frozen_priority_for_every_subset_and_order
tests/amane_adapter/test_amane_error_mapping.py::test_precedence_is_independent_of_source_order[kinds0-http_error]
tests/amane_adapter/test_amane_error_mapping.py::test_precedence_is_independent_of_source_order[kinds1-rate_limited]
tests/amane_adapter/test_amane_error_mapping.py::test_precedence_is_independent_of_source_order[kinds2-network]
tests/amane_adapter/test_amane_error_mapping.py::test_precedence_is_independent_of_source_order[kinds3-http_error]
tests/amane_adapter/test_amane_error_mapping.py::test_precedence_is_independent_of_source_order[kinds4-server_error]
tests/amane_adapter/test_amane_error_mapping.py::test_precedence_is_independent_of_source_order[kinds5-parse_error]
tests/amane_adapter/test_amane_error_mapping.py::test_precedence_is_independent_of_source_order[kinds6-network]
tests/amane_adapter/test_amane_error_mapping.py::test_precedence_is_independent_of_source_order[kinds7-unexpected]
tests/amane_adapter/test_amane_error_mapping.py::test_all_not_found_is_no_match_and_a_mix_is_a_failure
tests/amane_adapter/test_amane_error_mapping.py::test_detail_lists_every_participating_source_in_configuration_order
tests/amane_adapter/test_amane_error_mapping.py::test_detail_never_contains_error_detail_urls_or_secrets_and_is_bounded
tests/amane_adapter/test_amane_error_mapping.py::test_amane_error_carries_neither_url_nor_http_status_by_construction
tests/amane_adapter/test_amane_error_mapping.py::test_classification_reads_only_structured_fields_never_error_detail_text
tests/amane_adapter/test_amane_error_mapping.py::test_failure_reason_values_are_validated_closed_vocabulary
tests/amane_adapter/test_amane_host_witness_log.py::test_scenario_ids_are_exactly_h01_to_h15_and_match_the_runner_constant
tests/amane_adapter/test_amane_host_witness_log.py::test_every_scenario_passed_with_observations_and_no_failure_record
tests/amane_adapter/test_amane_host_witness_log.py::test_log_records_the_exact_amane_commit_and_a_python_314_host
tests/amane_adapter/test_amane_host_witness_log.py::test_tree_hashes_equal_the_current_repository_state
tests/amane_adapter/test_amane_host_witness_log.py::test_log_is_canonical_reproducible_output_without_clock_or_environment_data
tests/amane_adapter/test_amane_host_witness_log.py::test_key_witness_observations_match_the_frozen_contract
tests/amane_adapter/test_amane_isolation.py::test_the_main_process_never_imported_amane
tests/amane_adapter/test_amane_isolation.py::test_host_scripts_were_never_imported_by_pytest
tests/amane_adapter/test_amane_isolation.py::test_collecting_the_adapter_and_contract_test_trees_never_imports_amane
tests/amane_adapter/test_amane_isolation.py::test_pure_adapter_tests_pass_even_when_amane_cannot_be_imported_at_all
tests/amane_adapter/test_amane_isolation.py::test_existing_architecture_guards_still_pass_after_adapter_modules_were_imported_in_a_fresh_process
tests/amane_adapter/test_amane_logging_redaction.py::test_exactly_one_logger_and_one_warning_call_exist_in_the_adapter_tree
tests/amane_adapter/test_amane_logging_redaction.py::test_hostile_host_details_never_reach_logs_or_errors
tests/amane_adapter/test_amane_logging_redaction.py::test_failure_outputs_never_contain_hostile_text_even_when_every_source_fails
tests/amane_adapter/test_amane_logging_redaction.py::test_host_response_bodies_and_headers_never_appear_in_failures
tests/amane_adapter/test_amane_logging_redaction.py::test_settings_error_messages_do_not_echo_values
tests/amane_adapter/test_amane_metadata_mapping.py::test_every_core_field_has_an_explicit_disposition
tests/amane_adapter/test_amane_metadata_mapping.py::test_every_amane_target_field_has_an_explicit_source
tests/amane_adapter/test_amane_metadata_mapping.py::test_record_fields_are_exactly_the_mapped_and_narrowed_targets
tests/amane_adapter/test_amane_metadata_mapping.py::test_scalar_and_list_fields_map_one_to_one_in_core_order
tests/amane_adapter/test_amane_metadata_mapping.py::test_missing_values_stay_none_or_empty_and_runtime_zero_is_preserved
tests/amane_adapter/test_amane_metadata_mapping.py::test_blank_actor_names_are_dropped_and_others_kept_verbatim
tests/amane_adapter/test_amane_metadata_mapping.py::test_fanart_is_dropped_and_never_stuffed_into_another_field
tests/amane_adapter/test_amane_metadata_mapping.py::test_clean_http_urls_are_kept_verbatim[https://h.example/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_clean_http_urls_are_kept_verbatim[http://h.example/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_clean_http_urls_are_kept_verbatim[https://h.example:8443/a?x=1&y=2#f]
tests/amane_adapter/test_amane_metadata_mapping.py::test_clean_http_urls_are_kept_verbatim[HTTPS://H.EXAMPLE/A.JPG]
tests/amane_adapter/test_amane_metadata_mapping.py::test_clean_http_urls_are_kept_verbatim[http://127.0.0.1/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_clean_http_urls_are_kept_verbatim[https://[::1]/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_clean_http_urls_are_kept_verbatim[https://h.example/a b.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[/relative/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[//h.example/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[javascript:alert(1)]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[data:image/png;base64,AAAA]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[ftp://h.example/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[file:///C:/x.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[http://]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[https:///a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[https://]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[ https://h.example/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[https://h.example/a.jpg ]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[https://h.example/a\n.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[https://h.example/\x00a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[https://[::1/a.jpg]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[None]
tests/amane_adapter/test_amane_metadata_mapping.py::test_non_http_relative_or_malformed_urls_are_dropped[5]
tests/amane_adapter/test_amane_metadata_mapping.py::test_filtering_only_deletes_never_reorders_or_rewrites
tests/amane_adapter/test_amane_metadata_mapping.py::test_all_url_fields_are_filtered_and_source_url_is_the_first_valid_one
tests/amane_adapter/test_amane_metadata_mapping.py::test_mapping_is_a_deterministic_pure_function
tests/amane_adapter/test_amane_metadata_mapping.py::test_real_fixture_chain_matches_the_values_in_the_fixture_html
tests/amane_adapter/test_amane_missing_core.py::test_template_is_the_frozen_text
tests/amane_adapter/test_amane_missing_core.py::test_core_import_errors_become_the_fixed_message[fc2_metadata_core]
tests/amane_adapter/test_amane_missing_core.py::test_core_import_errors_become_the_fixed_message[fc2_metadata_core.aggregation]
tests/amane_adapter/test_amane_missing_core.py::test_core_import_errors_become_the_fixed_message[fc2_metadata_core.sources.adapters]
tests/amane_adapter/test_amane_missing_core.py::test_core_import_errors_become_the_fixed_message[fc2_metadata_core.http.client]
tests/amane_adapter/test_amane_missing_core.py::test_cannot_import_a_public_name_is_translated_too
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc0]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc1]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc2]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc3]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc4]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc5]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc6]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc7]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc8]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc9]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc10]
tests/amane_adapter/test_amane_missing_core.py::test_non_core_import_errors_are_not_misreported[exc11]
tests/amane_adapter/test_amane_missing_core.py::test_translated_message_is_bounded_and_secret_free
tests/amane_adapter/test_amane_missing_core.py::test_core_gate_loads_without_core_and_translates_the_real_failure_of_a_pure_module
tests/amane_adapter/test_amane_missing_core.py::test_non_core_failure_inside_the_chain_is_returned_untranslated
tests/amane_adapter/test_amane_missing_core.py::test_core_gate_module_itself_never_imports_core
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-01]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-02]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-03]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-04]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-05]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-06]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-07]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-08]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-09]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-10]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-11]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-12]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-13]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-14]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-15]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-16]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_every_mutant_is_killed_by_a_designated_test[M-17]
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_the_mutant_table_covers_m01_to_m17_exactly
tests/amane_adapter/test_amane_mutation_nonvacuity.py::test_the_original_tree_is_untouched_by_the_harness
tests/amane_adapter/test_amane_narrowing.py::test_author_constants_are_present_in_the_fixture_html
tests/amane_adapter/test_amane_narrowing.py::test_n1_source_url_follows_configuration_order_only[order0-https://fc2db.net/work/4979299/]
tests/amane_adapter/test_amane_narrowing.py::test_n1_source_url_follows_configuration_order_only[order1-https://123av.com/en/v/fc2-ppv-4979299]
tests/amane_adapter/test_amane_narrowing.py::test_n1_source_url_follows_configuration_order_only[order2-https://javdb.com/v/QNkPbM]
tests/amane_adapter/test_amane_narrowing.py::test_n1_source_url_follows_configuration_order_only[order3-https://javdb.com/v/QNkPbM]
tests/amane_adapter/test_amane_narrowing.py::test_n1_is_stable_across_repeated_runs
tests/amane_adapter/test_amane_narrowing.py::test_n1_skips_invalid_urls_then_none_when_none_valid_or_empty
tests/amane_adapter/test_amane_narrowing.py::test_n2_external_id_is_the_canonical_digits_whatever_the_order
tests/amane_adapter/test_amane_narrowing.py::test_n2_unit[FC2-4825061-4825061]
tests/amane_adapter/test_amane_narrowing.py::test_n2_unit[FC2-12345-12345]
tests/amane_adapter/test_amane_narrowing.py::test_n2_unit[FC2-12345678-12345678]
tests/amane_adapter/test_amane_narrowing.py::test_n2_never_uses_core_external_ids_even_when_they_conflict
tests/amane_adapter/test_amane_narrowing.py::test_real_core_ids_differ_from_the_narrowed_external_id
tests/amane_adapter/test_amane_narrowing.py::test_conflicting_source_urls_and_ids_change_only_with_documented_inputs
tests/amane_adapter/test_amane_no_side_effects.py::test_running_every_path_leaves_the_filesystem_environment_and_network_untouched
tests/amane_adapter/test_amane_no_side_effects.py::test_the_plugin_never_uses_the_host_data_dir_or_any_persistence_api
tests/amane_adapter/test_amane_no_side_effects.py::test_the_adapter_tree_contains_only_python_modules
tests/amane_adapter/test_amane_number_boundary.py::test_dirty_forms_are_canonicalised_by_core[FC2-1234567]
tests/amane_adapter/test_amane_number_boundary.py::test_dirty_forms_are_canonicalised_by_core[FC2PPV-1234567]
tests/amane_adapter/test_amane_number_boundary.py::test_dirty_forms_are_canonicalised_by_core[FC2-PPV-1234567]
tests/amane_adapter/test_amane_number_boundary.py::test_dirty_forms_are_canonicalised_by_core[[\u5e7f\u544a]FC2PPV-1234567]
tests/amane_adapter/test_amane_number_boundary.py::test_dirty_forms_are_canonicalised_by_core[xxx@FC2PPV-1234567]
tests/amane_adapter/test_amane_number_boundary.py::test_dirty_forms_are_canonicalised_by_core[fc2-ppv-1234567]
tests/amane_adapter/test_amane_number_boundary.py::test_dirty_forms_are_canonicalised_by_core[ FC2-PPV-1234567 ]
tests/amane_adapter/test_amane_number_boundary.py::test_five_to_eight_digit_canonical_forms[FC2-12345-FC2-12345]
tests/amane_adapter/test_amane_number_boundary.py::test_five_to_eight_digit_canonical_forms[FC2-PPV-4825061-FC2-4825061]
tests/amane_adapter/test_amane_number_boundary.py::test_five_to_eight_digit_canonical_forms[FC2PPV-12345678-FC2-12345678]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[   ]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[abc]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[FC2-]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[FC2-1234]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[FC2-123456789]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[FC2-\uff11\uff12\uff13\uff14\uff15\uff16\uff17]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[FC2-PPV-]
tests/amane_adapter/test_amane_number_boundary.py::test_not_fc2_is_no_match_never_a_request[ABC-123]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_other_content_type_is_no_match_even_for_a_valid_number[censored0]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_other_content_type_is_no_match_even_for_a_valid_number[uncensored]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_other_content_type_is_no_match_even_for_a_valid_number[western]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_other_content_type_is_no_match_even_for_a_valid_number[amateur]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_other_content_type_is_no_match_even_for_a_valid_number[]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_other_content_type_is_no_match_even_for_a_valid_number[censored1]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_other_content_type_is_no_match_even_for_a_valid_number[7]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_none_and_fc2_content_types_continue[None]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_none_and_fc2_content_types_continue[fc2_0]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_none_and_fc2_content_types_continue[fc2_1]
tests/amane_adapter/test_amane_number_boundary.py::test_b2_precedes_b3_and_b4
tests/amane_adapter/test_amane_number_boundary.py::test_b3_length_boundary_is_256
tests/amane_adapter/test_amane_number_boundary.py::test_b1_non_string_number_is_unexpected_failure[None]
tests/amane_adapter/test_amane_number_boundary.py::test_b1_non_string_number_is_unexpected_failure[1234567]
tests/amane_adapter/test_amane_number_boundary.py::test_b1_non_string_number_is_unexpected_failure[FC2-1234567]
tests/amane_adapter/test_amane_number_boundary.py::test_b1_non_string_number_is_unexpected_failure[number3]
tests/amane_adapter/test_amane_number_boundary.py::test_b1_non_string_number_is_unexpected_failure[number4]
tests/amane_adapter/test_amane_number_boundary.py::test_b1_foreign_object_without_attributes_is_failure_not_attribute_error
tests/amane_adapter/test_amane_number_boundary.py::test_only_number_and_content_type_are_ever_read
tests/amane_adapter/test_amane_number_boundary.py::test_unread_query_attributes_do_not_appear_in_the_module_ast
tests/amane_adapter/test_amane_number_boundary.py::test_number_module_has_no_fc2_parser_of_its_own
tests/amane_adapter/test_amane_outcome_status.py::test_success_returns_a_usable_record_with_nothing_degraded
tests/amane_adapter/test_amane_outcome_status.py::test_partial_returns_the_usable_record_and_exactly_one_warning
tests/amane_adapter/test_amane_outcome_status.py::test_partial_degraded_list_follows_configuration_order
tests/amane_adapter/test_amane_outcome_status.py::test_all_not_found_is_no_match_not_an_error
tests/amane_adapter/test_amane_outcome_status.py::test_a_not_found_plus_an_operational_failure_is_an_error_never_none
tests/amane_adapter/test_amane_outcome_status.py::test_every_source_failing_reports_the_highest_priority_reason
tests/amane_adapter/test_amane_outcome_status.py::test_non_fc2_inputs_return_no_match_without_any_request
tests/amane_adapter/test_amane_outcome_status.py::test_foreign_number_is_an_unexpected_failure_without_any_request
tests/amane_adapter/test_amane_outcome_status.py::test_an_engine_exception_becomes_a_bounded_unexpected_failure_naming_only_the_type
tests/amane_adapter/test_amane_outcome_status.py::test_fatal_exceptions_from_the_engine_are_not_converted[KeyboardInterrupt]
tests/amane_adapter/test_amane_outcome_status.py::test_fatal_exceptions_from_the_engine_are_not_converted[SystemExit]
tests/amane_adapter/test_amane_provenance.py::test_record_has_no_internal_provenance_fields
tests/amane_adapter/test_amane_provenance.py::test_single_source_identity_is_left_to_the_host
tests/amane_adapter/test_amane_provenance.py::test_failure_detail_is_a_closed_vocabulary_over_many_scenarios
tests/amane_adapter/test_amane_provenance.py::test_partial_log_line_is_closed_vocabulary_only
tests/amane_adapter/test_amane_py314_core_path.py::test_core_runtime_objects_and_one_fake_bridge_aggregate
tests/amane_adapter/test_amane_retry_bounds.py::test_registry_size_and_frozen_core_attempts_define_s_and_a
tests/amane_adapter/test_amane_retry_bounds.py::test_three_layer_arithmetic_for_the_documented_configurations
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-1-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-1-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-1-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-1-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-1-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-1-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-1-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-3-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-3-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-3-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-3-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-3-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-3-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-3-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-10-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-10-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-10-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-10-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-10-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-10-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[1-10-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-1-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-1-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-1-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-1-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-1-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-1-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-1-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-3-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-3-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-3-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-3-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-3-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-3-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-3-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-10-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-10-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-10-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-10-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-10-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-10-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[2-10-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-1-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-1-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-1-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-1-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-1-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-1-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-1-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-3-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-3-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-3-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-3-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-3-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-3-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-3-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-10-200]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-10-403]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-10-404]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-10-429]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-10-500]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-10-503]
tests/amane_adapter/test_amane_retry_bounds.py::test_status_paths_cost_exactly_one_host_attempt_per_source[3-10-599]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[1-1-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[1-1-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[1-3-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[1-3-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[1-10-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[1-10-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[2-1-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[2-1-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[2-3-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[2-3-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[2-10-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[2-10-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[3-1-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[3-1-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[3-3-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[3-3-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[3-10-curl_error]
tests/amane_adapter/test_amane_retry_bounds.py::test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall[3-10-timeout]
tests/amane_adapter/test_amane_retry_bounds.py::test_mixed_path_curl_error_then_503_is_still_within_h
tests/amane_adapter/test_amane_retry_bounds.py::test_default_and_maximum_host_bounds_hold_with_transport_failures
tests/amane_adapter/test_amane_retry_bounds.py::test_host_defect_zero_retries_sends_nothing_and_fails_closed
tests/amane_adapter/test_amane_retry_bounds.py::test_disabled_sources_reduce_s
tests/amane_adapter/test_amane_retry_bounds.py::test_breaker_open_sources_send_zero_requests
tests/amane_adapter/test_amane_retry_bounds.py::test_breaker_state_is_per_source_and_does_not_leak_to_healthy_sources
tests/amane_adapter/test_amane_retry_bounds.py::test_non_fc2_and_foreign_queries_send_no_request_at_all
tests/amane_adapter/test_amane_retry_bounds.py::test_a_successful_lookup_costs_s_requests_and_s_host_attempts
tests/amane_adapter/test_amane_runtime_lifetime.py::test_core_runtime_objects_are_built_exactly_once_for_many_lookups
tests/amane_adapter/test_amane_runtime_lifetime.py::test_non_fc2_lookups_do_not_construct_anything
tests/amane_adapter/test_amane_runtime_lifetime.py::test_the_same_governor_serves_every_lookup
tests/amane_adapter/test_amane_runtime_lifetime.py::test_two_runtimes_do_not_share_governor_state
tests/amane_adapter/test_amane_runtime_lifetime.py::test_construction_does_not_touch_the_network_or_the_host_client
tests/amane_adapter/test_amane_runtime_lifetime.py::test_concurrent_lookups_on_one_runtime_are_independent_and_leave_the_governor_idle
tests/amane_adapter/test_amane_runtime_lifetime.py::test_valid_configuration_never_makes_construction_raise
tests/amane_adapter/test_amane_runtime_lifetime.py::test_invalid_configuration_fails_before_a_runtime_exists[raw0]
tests/amane_adapter/test_amane_runtime_lifetime.py::test_invalid_configuration_fails_before_a_runtime_exists[raw1]
tests/amane_adapter/test_amane_settings.py::test_default_settings_use_core_default_order_all_enabled
tests/amane_adapter/test_amane_settings.py::test_explicit_sources_are_authoritative_and_ordered
tests/amane_adapter/test_amane_settings.py::test_unlisted_registered_sources_are_not_used
tests/amane_adapter/test_amane_settings.py::test_core_config_has_no_core_retry_and_frozen_defaults
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw0]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[sources]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw2]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw3]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw4]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw5]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw6]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw7]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw8]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw9]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw10]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw11]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw12]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw13]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw14]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw15]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw16]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw17]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw18]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw19]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw20]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw21]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw22]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw23]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw24]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw25]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw26]
tests/amane_adapter/test_amane_settings.py::test_invalid_configuration_is_rejected_before_any_network[raw27]
tests/amane_adapter/test_amane_settings.py::test_deadline_upper_bound_comes_from_core_not_adapter
tests/amane_adapter/test_amane_settings.py::test_error_messages_never_echo_configuration_values[raw0]
tests/amane_adapter/test_amane_settings.py::test_error_messages_never_echo_configuration_values[raw1]
tests/amane_adapter/test_amane_settings.py::test_error_messages_never_echo_configuration_values[raw2]
tests/amane_adapter/test_amane_settings.py::test_error_messages_never_echo_configuration_values[raw3]
tests/amane_adapter/test_amane_settings.py::test_error_messages_never_echo_configuration_values[raw4]
tests/amane_adapter/test_amane_settings.py::test_error_messages_never_echo_configuration_values[raw5]
tests/amane_adapter/test_amane_settings.py::test_error_messages_never_echo_configuration_values[raw6]
tests/amane_adapter/test_amane_settings.py::test_error_messages_are_deterministic
tests/amane_adapter/test_amane_settings.py::test_descriptor_constants_follow_the_contract
tests/amane_adapter/test_amane_settings.py::test_no_secret_like_configuration_field_names
tests/amane_adapter/test_amane_zip_build.py::test_builder_plugin_id_equals_the_adapter_plugin_id
tests/amane_adapter/test_amane_zip_build.py::test_build_is_deterministic_byte_for_byte
tests/amane_adapter/test_amane_zip_build.py::test_zip_has_one_top_level_folder_named_by_the_plugin_id_and_exactly_the_tree_files
tests/amane_adapter/test_amane_zip_build.py::test_zip_contains_no_core_tests_docs_or_non_python_files
tests/amane_adapter/test_amane_zip_build.py::test_timestamps_permissions_and_system_are_fixed
tests/amane_adapter/test_amane_zip_build.py::test_zip_contents_equal_the_tree_with_lf_line_endings
tests/amane_adapter/test_amane_zip_build.py::test_crlf_and_lf_checkouts_give_identical_bytes
tests/amane_adapter/test_amane_zip_build.py::test_zip_is_within_the_amane_size_limit_and_contains_no_secrets
tests/amane_adapter/test_amane_zip_build.py::test_builder_refuses_trees_that_break_the_frozen_layout[<lambda>-__init__]
tests/amane_adapter/test_amane_zip_build.py::test_builder_refuses_trees_that_break_the_frozen_layout[<lambda>-only .py]
tests/amane_adapter/test_amane_zip_build.py::test_builder_refuses_trees_that_break_the_frozen_layout[<lambda>-Core]
tests/amane_adapter/test_amane_zip_build.py::test_builder_refuses_trees_that_break_the_frozen_layout[<lambda>-plugin.py]
tests/amane_adapter/test_amane_zip_build.py::test_builder_refuses_trees_that_break_the_frozen_layout[<lambda>-non-file]
tests/amane_adapter/test_amane_zip_build.py::test_pycache_directories_are_skipped
```
