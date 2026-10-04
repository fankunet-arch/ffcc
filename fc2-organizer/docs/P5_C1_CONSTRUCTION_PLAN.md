# P5-C1 施工计划（Construction Plan）-- Amane Adapter End-to-End

```text
Governance Mode                    : ACCELERATED v2
Governance Authority               : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Package                            : P5-C1 — Amane Adapter End-to-End
Package Frozen Base                : 98ad8eb67bfd3e09701a730487e049f3fc348789（Phase 5 Entry Closure Head；不是 8f12bb69…）
Planning Parent                    : 98ad8eb67bfd3e09701a730487e049f3fc348789
Risk Class                         : B（带强制升级门 U-1..U-8；合同第 5 节；本次设计调查未触发 B -> C）
User Capability / Vertical Closure : 一个 FC2 影片查询从 Amane 的 SearchQuery 出发，经薄 adapter 进入现有 FC2 Metadata Core（单一 MultiSourceEngine +
                                     共享 governor），再回到 Amane 的 MediaMetadata / None / SourceError：包含插件发现、配置、号码边界、宿主 HTTP 桥、
                                     有界重试、结果与错误映射、来源归属、取消与缺失 Core 的失败行为，并有真实 Amane v0.15.0 公开 API 的宿主见证
Why Not Merge With Previous C      : 前一个 C 是 Phase 5 Entry Closure（98ad8eb…，F3 / F5 test-only closure，已独立 Review PASS）。它是历史 blocker 的关闭；
                                     P5-C1 是新的用户能力，authority（合同 vs Owner Ratification）、能力与实现边界都不同；合并会使已 PASS 的 closure 证据失效
                                     （合同第 4 节 Q1）
Why Not Split Further              : 号码边界、桥、Core 调用、结果映射、错误映射、窄化、归属共同构成“一个查询是否得到正确且安全的 Amane 结果”这一个裁决；
                                     任何一段单独都不能得出结论，拆成 models / config / mapping / errors / tests / packaging 只增加等待而不提高
                                     correctness / safety / auditability（本计划第 1 节）。P5-C1 / P5-C2 的边界保留，理由见合同第 4 节 Q2-Q4
Internal Stages                    : S1 / S2 / S3（连续施工；无中间 Review；无 S 级状态 docs）
Independent Review Plan            : Design / Authority Review（实现之前，必需；本文件与合同均为 CANDIDATE）
                                     + 1 次 C 级 Independent Level 1 Review（S1-S3 全部完成之后）
                                     + 必要时统一 R1 + Final Closure
                                     C 内中间 Review：NONE（除非触发第 11.3 节的升级条件）
Owner Question Gate                : BUSINESS DECISIONS ONLY（本设计未发现需要 Owner 的业务问题；插件 id 命名空间 `ffcc` 为技术标识，已由设计者裁决，
                                     可被 Design Reviewer 否决，不阻塞）
Evidence Gate                      : 第 7 节 E1..E28（Contract -> 实现 -> 测试映射、diff scope、API manifest、真实宿主见证、桥 / 异常映射、
                                     有界性、状态 / 错误 / 字段映射、窄化、归属、取消、缺失 Core、架构与副作用守护、确定性、mutation、
                                     测试隔离、targeted / contract / full suite、skip 对账、evidence gaps）
Python Runtime Authority           : 宿主 Amane v0.15.0 要求 Python >= 3.14；Core 声明 >= 3.11（不修改 pyproject.toml 的依赖与版本）。
                                     主套件正式证据环境 Windows 11 / Python 3.12.x；宿主见证与 3.14 子集在 Python 3.14.x
Production Change                  : NONE（`src/**` 零 diff；任何 src/** 改动 = 升级门 U-1）
```

```text
Package               = P5-C1 Amane Adapter End-to-End
Branch                = claude/phase5-c1-amane-adapter（自 98ad8eb… 创建；不在 claude/phase5-entry-planning 上工作）
规范合同              = docs/specifications/PHASE5_C1_AMANE_ADAPTER_CONTRACT.md
Design Candidate      = 本 docs-only 提交（git log -1 --format=%H -- fc2-organizer/docs/P5_C1_CONSTRUCTION_PLAN.md）
Frozen Contract       = NOT ACCEPTED
Construction Plan     = NOT ACCEPTED（本文件）
Design Accepted Head  = NOT ESTABLISHED
Implementation        = NOT AUTHORIZED
Phase 5               = ENTRY AUTHORIZED
```

坐标规则（冻结）：Package Frozen Base = Planning Parent = `98ad8eb…`；Governance Authority = `3b9d39e…`（`98ad8eb…` 的祖先，治理文档自此未变）。
唯一 authority transition：独立 Design / Authority Review PASS -> 该 Review 建立 Design Accepted Head -> Frozen Contract / Construction Plan -> 才允许进入 S1。
不创建 design closure / design accepted 之类的纯状态 docs 提交（治理文档第 11.1 节）。

Design PASS 之后，开发者只能**执行**本计划：不得重新设计、不得调整 S 边界、不得把设计项推迟到“开发时再决定”。合同与本计划未写明的实现细节
（helper 命名、文件内部组织、fixture 写法、断言写法）由开发者按以下优先级自行裁决，并在 commit message 中记录理由：

```text
1. Frozen Contract（P5-C1 与 Phase 1-4）  2. fail closed  3. 宿主 HTTP 生命周期不被绕过  4. 不改变 CLOSED package
5. deterministic  6. bounded requests / 时间  7. 最小依赖（纯模块仅标准库 + Core）  8. testability
```

---

## 1. 治理四问（治理文档第 15 节）与 C 粒度

完整的四问及真实判断见**合同第 4 节**，此处只记录与施工粒度相关的结论。

* **Q1** 不与 Phase 5 Entry Closure 合并：历史 blocker 关闭 vs 新用户能力。
* **Q2 / Q3** 与 P5-C2 分开：设计期实测发现宿主已漂移（当前 main 的 `multi_language -> traits`、`raw_results` 移除、`WebClient.request(max_attempts)`、浏览器回退），
  真实宿主验收天然带环境依赖，Core 的最终供给方式是独立 authority 决策。单独的 P5-C2 降低的是**兼容与发布**风险，不是 adapter 逻辑风险。
* **Q4** 取消 P5-C1 / P5-C2 边界：不影响 correctness / safety，**影响 auditability**，故保留边界；P5-C2 不是无条件必需（若无新增工作可缩减），**不规划 P5-C3**。
* **P5-C1 内部不再拆分**：S1 / S2 / S3 共享同一 Frozen Contract、同一测试树、同一次 C 级 Review；每个 S 仍有 developer checkpoint、独立 commit、
  非空洞性证据。任何一段单独 Review 都无法回答“一个查询是否得到正确且安全的结果”。

---

## 2. Risk Class 与升级门

Risk Class = **B**（合同第 5 节）。升级门（任一触发 = 立即 STOP，按 C 类重新治理，不得自行继续）：

```text
U-1 任何 src/** 改动                              U-5 需要绕过宿主 HTTP 生命周期（自建客户端）
U-2 vendor / 复制 / 打包 Core 源码                U-6 Core 在 Python 3.14 上出现需要生产修改的缺陷
U-3 任何持久化 / 文件写入 / 磁盘缓存              U-7 需要改变已 CLOSED 测试的语义
U-4 无法证明重试 / 物理请求有界（DESIGN BLOCKED） U-8 出现新的 security boundary（凭据 / cookie / 监听 / 读宿主 DB）
```

另：真实宿主见证与设计期实测（合同 W-05）**不一致**（例如 `ok_statuses` 行为不同）= 设计前提失效，STOP 并回到 Design Review。

---

## 3. 内部施工模型（S1 -> S2 -> S3，连续施工）

**连续施工**：S1 -> S2 -> S3 之间不停止、不等待 Owner、不自动 Review、不写状态 docs。每个 S 结束时：全部相关测试绿、独立 commit（可 push）、
commit message 记录重要裁决。S 级 checkpoint 不是 Review 触发点。

### S1 —— 宿主边界与骨架（Host Boundary & Skeleton）

目标：建立插件树、纯模块的输入侧与传输侧、API manifest 与架构守护。

1. **Authority 机器核对与基线**（输出写入 HANDOFF）：`HEAD` 是 `98ad8eb…` 的后代；`git diff 98ad8eb..HEAD -- fc2-organizer/src` 为空；Design Accepted Head 已存在；
   Python 3.12 上记录 `pytest tests -q` 的 collected / passed / skipped 与 **skip nodeid 清单**（E27 基线）。
2. `pyproject.toml`：仅在 `[tool.pytest.ini_options] pythonpath` 增加 `"adapters/amane"`（唯一允许的改动）。
3. 建立 `adapters/amane/fc2_amane_adapter/`（无 `__init__.py`）：
   * `_core_gate.py`：`translate_core_import_error(exc) -> ImportError | None`（合同第 22 节冻结模板；自身不 import Core）；
   * `_settings.py`：`AdapterSettings` / `SourceSetting`、`parse_settings(raw)`（合同第 11 节全部规则）、`AdapterConfigError`、`build_aggregation_config(settings)`；
   * `_number.py`：`resolve_query(number, content_type) -> canonical | AdapterNoMatch | AdapterFailure`（合同表 B 的 B1-B5）；
   * `_bridge.py`：`AmaneHttpBridge`（合同第 13、14 节的全部规则：`ok_statuses`、头小写化、charset 解码、5 MiB 事后上限、外来响应防御、异常映射）；
   * `plugin.py`（骨架）：`Plugin`、`descriptor()`（合同第 9 节）、Pydantic `Fc2MetadataConfig` / `SourceEntry`（`model_validator` 调用 `parse_settings`）、顶层导入守门（`_core_gate`）、
     provider 类骨架（`fetch` 的引擎段在 S2 接入；S1 内 `fetch` 对引擎段可抛 `NotImplementedError`，该 checkpoint 不可发布）。
4. `tools/amane_api_manifest.py`：对一个 Amane 检出做 AST 提取并输出确定性 JSON；对 **exact v0.15.0（`45dff21…`）** 生成并提交
   `adapters/amane/api_manifest/amane_v0.15.0_api_manifest.json`（内容：`amane.plugin.__all__`、合同表 A 涉及的类 / 字段 / 枚举成员 / 方法签名 / 常量、检出的 commit SHA）。
5. `tests/support/amane_host_fakes.py`：duck-typed 宿主 web client 替身（可编排：响应 / `RequestError` 形状异常 / 挂起；可模拟“宿主重试 H 次”的模型；记录调用与 kwargs）。**不 import amane。**
6. S1 测试（见第 6 节映射）：`test_amane_api_manifest.py`、`test_amane_architecture_guards.py`、`test_amane_settings.py`、`test_amane_number_boundary.py`、
   `test_amane_bridge_response.py`、`test_amane_bridge_errors.py`、`test_amane_missing_core.py`（纯部分）。
7. S1 出口：S1 测试全部通过（Python 3.12）；既有套件无回归；`src/**` diff 为空。

### S2 —— Core 调用与结果映射（Core Invocation & Result Mapping）

目标：接通 Core，完成全部输出侧映射、有界性与取消。

1. `_runtime.py`：`AdapterRuntime`（**一次构造**：registry / `AggregationConfig`（`RetryPolicy.no_retry()`）/ `SourceResourceGovernor()` / bridge / `MultiSourceEngine`）、
   `async lookup(number, content_type) -> AdapterFound | AdapterNoMatch | AdapterFailure`（`except Exception` 仅包住 `engine.aggregate`；取消 / 致命异常原样传播；PARTIAL 时一条 `WARNING` 日志）。
2. `_outcome.py`：状态映射（合同表 F）、逐 kind 错误映射与 7 级优先级（合同表 G）、`detail` 模板、`AdapterRecord` 映射与 N-1 / N-2 窄化、URL 卫生过滤、字段处置完备性元数据（合同表 H）。
3. `plugin.py`：provider `fetch` 接入 `AdapterRuntime`；中立结果 -> `MediaMetadata`（`FilmActor(name=…)`，性别 unknown）/ `None` / `SourceError(FailureReason(reason), detail=…)`；`SourceError.url` / `http_status` 恒 `None`。
4. S2 测试：`test_amane_retry_bounds.py`、`test_amane_outcome_status.py`、`test_amane_error_mapping.py`、`test_amane_metadata_mapping.py`、`test_amane_narrowing.py`、
   `test_amane_provenance.py`、`test_amane_cancellation.py`、`test_amane_determinism.py`、`test_amane_logging_redaction.py`、`test_amane_no_side_effects.py`、`test_amane_runtime_lifetime.py`。
5. S2 出口：S1 + S2 测试全部通过；`E9`（纯逻辑部分）、`E10`、`E11`、`E12`、`E14`、`E15`（纯逻辑部分）达到各自通过判据。

### S3 —— 端到端合同与证据（End-to-End Contract & Evidence）

目标：真实宿主见证、打包骨架、隔离证据、mutation、全量回归、HANDOFF。

1. `tools/run_amane_host_witness.py` + `tests/amane_adapter/host_scripts/**`：在 **Python >= 3.14 且已安装 Amane v0.15.0** 的解释器中执行第 8 节的场景 H-01..H-15，
   输出并提交 `docs/acceptance/evidence/P5_C1_HOST_WITNESS.json`。
2. `tools/build_amane_plugin_zip.py`（确定性 zip）+ `test_amane_zip_build.py`；H-03 以真实 `install_plugin_zip` 安装该 zip。
3. `test_amane_host_witness_log.py`（恒执行、不 skip）：见证日志的新鲜度与完整性。
4. `test_amane_isolation.py` + E22 的三种收集顺序与 pre-import 见证。
5. mutation 门（第 9 节 M-01..M-17）及恢复证明。
6. Python 3.14 子集：adapter 纯测试 + `tests/unit/{aggregation,resource_control,sources,core}` 在 3.14 上的结果（已知 `punycode` 失败按 L-07 记录，不修复）。
7. 全量回归 `pytest tests -q`（3.12）；skip / xfail 对账（E27）；`git diff --check`；diff scope（E1）。
8. `adapters/amane/README.md`（中文安装骨架说明，明确标注“最终分发与 Core 供给属 P5-C2”）。
9. 编写 `docs/review/P5_C1_HANDOFF.md`（第 10 节）。**S3 完成状态只能写 `READY FOR LEVEL 1 REVIEW` / `FAILED` / `BLOCKED`，绝不写 PASS / CLOSED。**
10. S3 出口：第 7 节所有 Evidence 项给出结果；停止，等待 C 级 Independent Level 1 Review。

---

## 4. 精确的允许 / 禁止文件（冻结）

### 4.1 允许（范围 = `<Design Accepted Head>..<P5-C1 head>`）

```text
fc2-organizer/adapters/amane/**                              （新增：插件树、README、api_manifest）
fc2-organizer/tools/amane_api_manifest.py                    （新增）
fc2-organizer/tools/build_amane_plugin_zip.py                （新增）
fc2-organizer/tools/run_amane_host_witness.py                （新增）
fc2-organizer/tests/amane_adapter/**                         （新增；pytest 文件名 test_amane_*.py；host_scripts/）
fc2-organizer/tests/support/amane_host_fakes.py              （新增）
fc2-organizer/docs/acceptance/evidence/P5_C1_HOST_WITNESS.json（新增）
fc2-organizer/docs/review/P5_C1_HANDOFF.md                   （新增）
fc2-organizer/pyproject.toml                                 （仅 [tool.pytest.ini_options] pythonpath 增加 "adapters/amane"）
```

### 4.2 禁止

```text
fc2-organizer/src/**                                  任何改动（U-1）
fc2-organizer/tests/** 中除 4.1 以外的任何既有文件      任何改动（U-7）
fc2-organizer/docs/** 中除 4.1 以外的任何既有文档       任何改动（含 Phase 4 docs、Phase 5 Entry Authority、治理文档、本合同 / 本计划——合同 / 计划的修订只能经 Review 的 amendment）
CLAUDE.md、README.md、其它 pyproject.toml 字段、依赖声明
上游 Amane 源码（任何形式提交进仓库；检出必须位于仓库之外并被 .gitignore 既有规则以外的位置）
```

### 4.3 访问规则

* Amane 检出只读、位于仓库外（例如用户临时目录）；`upstream/amane/` 既有规则不变。
* 主测试进程**不** import `amane`；真实宿主只在 subprocess 内出现（合同第 25 节）。
* 不访问真实站点、不发真实网络请求（P5-C1 全离线）。
* 所有写文件仅限 4.1 所列路径与 `tmp_path` 类的临时目录。

---

## 5. 命令（冻结；均在 `fc2-organizer/` 下执行；`<py312>` / `<py314>` 为对应解释器）

### 5.1 Authority 与漂移核对（S1 起始；输出写入 HANDOFF）

```powershell
git rev-parse HEAD
git merge-base --is-ancestor 98ad8eb67bfd3e09701a730487e049f3fc348789 HEAD
git diff --stat 98ad8eb67bfd3e09701a730487e049f3fc348789..HEAD -- fc2-organizer/src          # 必须为空
git status --porcelain=v2 ; git ls-files --others --exclude-standard                           # 必须干净
git -C <amane-checkout> rev-parse HEAD                                                         # 必须 = 45dff2159369883e028a296d775a4598836c1ddd
<py312> -m pytest tests -q -p no:cacheprovider                                                 # 基线计数与 skip 清单
```

### 5.2 测试门

```powershell
<py312> -m pytest tests/amane_adapter -q -p no:cacheprovider                      # E23 targeted
<py312> -m pytest tests/amane_adapter/test_amane_architecture_guards.py tests/amane_adapter/test_amane_api_manifest.py tests/amane_adapter/test_amane_zip_build.py -q   # E24
<py312> -m pytest tests/contract -q -p no:cacheprovider                           # E25 既有 contract 套件
<py312> -m pytest tests -q -p no:cacheprovider                                    # E26 full
# E22 三种收集顺序（均必须通过且 collected / passed 计数一致）
<py312> -m pytest tests -q -p no:cacheprovider
<py312> -m pytest tests/amane_adapter tests/contract tests/phase4_acceptance tests/unit -q -p no:cacheprovider
<py312> -m pytest tests/contract tests/phase4_acceptance tests/unit tests/amane_adapter -q -p no:cacheprovider
```

### 5.3 真实宿主见证与 3.14 子集

```powershell
<py314> tools\run_amane_host_witness.py --amane-src <amane-checkout> --core-src src --adapter-tree adapters\amane\fc2_amane_adapter --out docs\acceptance\evidence\P5_C1_HOST_WITNESS.json
<py314> -m pytest tests/amane_adapter -q -p no:cacheprovider --deselect <仅需主进程 3.12 的测试>      # 记录结果
<py314> -m pytest tests/unit/core tests/unit/sources tests/unit/aggregation tests/unit/resource_control -q -p no:cacheprovider
```

`<py314>` 环境要求：Python 3.14.x，`pip install -e <amane-checkout>`（v0.15.0）+ `pytest`；Core 通过 `PYTHONPATH=src` 提供。若无法提供该环境 = **STOP-02（needs input）**，不得降级为替身测试。

### 5.4 diff scope 与整洁性

```powershell
git diff --stat <Design Accepted Head>..HEAD
git diff --stat <Design Accepted Head>..HEAD -- fc2-organizer/src                 # 必须为空（E1）
git diff --name-only <Design Accepted Head>..HEAD                                 # 必须 ⊆ 第 4.1 节
git diff --check
git status --porcelain=v2
```

---

## 6. 测试布局与 Contract -> 实现 -> 测试映射（E2；文件级冻结）

pytest 文件名一律 `test_amane_<主题>.py`（既有 tests 目录没有 `__init__.py`，基名必须全局唯一）。

| 合同条款 | 实现 | 测试文件（`tests/amane_adapter/`） | Evidence |
|---|---|---|---|
| 表 A / I2 / I26：只用 v0.15.0 公共 API | `plugin.py`；manifest | `test_amane_api_manifest.py` | E3 |
| §8 布局、I1 / I4 / I14 / I21 / I24 / I25、Core 白名单、无函数内导入、无 `except BaseException` | 整个插件树 | `test_amane_architecture_guards.py` | E17 E18 E19(静态) |
| 表 C / §11：配置 | `_settings.py`、`plugin.py` 模型 | `test_amane_settings.py` | E5(配置)、E23 |
| 表 B / §10：SearchQuery 与 canonical | `_number.py` | `test_amane_number_boundary.py` | E5 E6 |
| 表 D / §13：响应映射 | `_bridge.py` | `test_amane_bridge_response.py` | E7 |
| 表 E / §14：传输异常映射 | `_bridge.py` | `test_amane_bridge_errors.py` | E8 |
| §15：所有权与有界性 | `_runtime.py`、`_bridge.py` | `test_amane_retry_bounds.py` | E9 |
| 表 F / §16：状态映射 | `_outcome.py`、`_runtime.py` | `test_amane_outcome_status.py` | E10 |
| 表 G / §17：错误映射、优先级、detail | `_outcome.py` | `test_amane_error_mapping.py` | E14 |
| 表 H / §19.1-19.2：逐字段 | `_outcome.py` | `test_amane_metadata_mapping.py` | E11 |
| §19.3：N-1 / N-2 窄化 | `_outcome.py` | `test_amane_narrowing.py` | E12 |
| 表 I / §20：来源归属（纯逻辑部分） | `_outcome.py` | `test_amane_provenance.py` | E13 |
| §18：取消 | `_runtime.py` | `test_amane_cancellation.py` | E15 |
| §22：缺失 Core（纯逻辑部分） | `_core_gate.py` | `test_amane_missing_core.py` | E16 |
| §24：确定性 | 全部 | `test_amane_determinism.py` | E20 |
| §21 / I12 / I23：诊断与封闭词汇、日志 | `_outcome.py`、`_runtime.py` | `test_amane_logging_redaction.py` | E13 E20 |
| §23 / I14：无副作用 | 全部 | `test_amane_no_side_effects.py` | E19 |
| §12：Core 调用一次构造 | `_runtime.py` | `test_amane_runtime_lifetime.py` | E9 E21(M-10) |
| §25：主进程隔离 | — | `test_amane_isolation.py` | E22 |
| 打包骨架 | `build_amane_plugin_zip.py` | `test_amane_zip_build.py` | E4(打包部分) |
| 真实宿主见证的新鲜度 / 完整性 | `run_amane_host_witness.py` | `test_amane_host_witness_log.py` | E4 E7 E8 E9 E13 E15 E16 |
| 无 skip / xfail | — | `test_amane_architecture_guards.py`（扫描新测试） | E27 |
| mutation | 整个插件树 | `test_amane_mutation_nonvacuity.py` | E21 |

---

## 7. Evidence Gate（E1..E28；Developer 必须在 HANDOFF 中逐项给出结果；不适用必须写 `N/A + reason`）

| ID | 内容 | 产生方式 | 通过判据 |
|---|---|---|---|
| E1 | 精确 diff scope | 第 5.4 节命令 | `src/**` 空；变更文件 ⊆ 第 4.1 节；`git diff --check` 干净 |
| E2 | Contract -> 实现 -> 测试映射 | 第 6 节表，HANDOFF 给出实际 nodeid 清单 | 每条合同条款至少一个测试；无孤儿条款 |
| E3 | Amane v0.15.0 公共 API 见证 | API manifest（生成自 `45dff21…`）+ AST 使用核对 + H-01 的真实 import | adapter 使用的每个名字 / 关键字 ∈ manifest；manifest 记录的 commit = `45dff21…`；真实 import 成功 |
| E4 | 插件发现 / skeleton 见证 | H-02 / H-03（真实 `PluginManager.discover`、`install_plugin_zip`）+ 打包测试 | descriptor 字段与合同 §9 逐项相等；`install` 返回 `ffcc.fc2-metadata`；zip 单一顶层文件夹、确定性 |
| E5 | SearchQuery 映射矩阵 | `test_amane_number_boundary.py`、H-08 | 表 B 每行（B1-B5）≥ 1 用例；`file_path / raw_results` 从不被读取 |
| E6 | canonical / dirty / invalid FC2 矩阵 | 同上 | 覆盖 Phase 1 正向集的全部形态（含 `[广告]FC2PPV-…`、`xxx@FC2PPV-…`）、9 位数字、Unicode 数字、空白、非 str、超长；全部委托 Core |
| E7 | Amane HTTP 响应映射 | `test_amane_bridge_response.py`、H-09 | 表 D 每行；头小写化；charset 矩阵（utf-8 / shift_jis / 未知 / `rot13` / NUL）；5 MiB 边界；外来响应 |
| E8 | 传输异常映射 | `test_amane_bridge_errors.py`、H-10 | 表 E 每行；**不解析消息文本**（AST + 用“消息被篡改”的异常验证）；CancelledError 原样传播；编程错误不被捕获 |
| E9 | 重试 / 限速 / 资源控制有界性 | `test_amane_retry_bounds.py`、`test_amane_runtime_lifetime.py`、H-09 | 合同 §15.2 公式逐项成立：状态码路径 1 次；`CurlError`/超时路径 ≤ H；`H ∈ {1,3,10}`；S ∈ {1,2,3}；熔断打开的来源 0 次；Core `max_attempts == 1`；真实 `WebClient` 上物理请求总数 ≤ S×H；429 / 403 / 404 / 5xx 每来源恰 1 次 |
| E10 | SUCCESS / PARTIAL / FAILED 映射 | `test_amane_outcome_status.py`、H-08 | 表 F 每行；PARTIAL 返回 metadata + 恰 1 条 WARNING；全 NOT_FOUND → `None`；混合 → `SourceError` |
| E11 | MediaMetadata 完整字段映射表 | `test_amane_metadata_mapping.py`、H-07 | 对 `NormalizedMetadata` 的**每个字段**与 manifest 中 `MediaMetadata` 的**每个字段**有显式处置（守护测试穷举）；`fanart_urls` 不出现在任何输出；FilmActor 性别 `unknown`；URL 卫生过滤 |
| E12 | 复数 -> 单数确定性窄化 | `test_amane_narrowing.py` | N-1 / N-2 冲突测试：多来源不同 URL / 不同 `external_ids`、改变配置顺序、全部 URL 非法、空集合；`PYTHONHASHSEED` 无影响；`external_id` 永不取 Core `external_ids` |
| E13 | 来源归属 | `test_amane_provenance.py`、H-12（真实 `amane.aggregate`） | Amane 可见输出不含任何内部 provenance；真实聚合只产生 `ffcc.fc2-metadata` 这一个来源键；`detail` / 日志只含封闭词汇 |
| E14 | 错误映射矩阵 | `test_amane_error_mapping.py`、H-08 | `SourceErrorKind` **全部成员**逐一断言（枚举完备）；未知 kind -> `unexpected`；优先级在全部排列下确定；`detail` 模板与长度上界；`url / http_status` 恒 `None` |
| E15 | 取消传播 | `test_amane_cancellation.py`、H-11 | 取消时 `CancelledError` 原样传播、无结果、governor `in_flight == 0`、无遗留任务；真实 `invoke_source` 不吞取消；`KeyboardInterrupt` 同样传播 |
| E16 | 缺失 Core 失败 | `test_amane_missing_core.py`、H-05 | 真实 `discover` -> `failures` 且不注册、消息等于冻结模板；`install` -> `ValueError("插件导入失败: …")`；非 Core 的 `ImportError` 不被误报 |
| E17 | Core / Organizer 不 import Amane | 既有 `tests/contract/*architecture*`（E25）+ 新守护 | 既有守卫全绿；新增守卫证明 adapter 之外无人 import amane |
| E18 | adapter 无独立 HTTP 客户端 | `test_amane_architecture_guards.py` | AST：无 `httpx / requests / aiohttp / curl_cffi / urllib.request / socket / http.client`；不 import `fc2_metadata_core.http.httpx_client` |
| E19 | 无文件系统 / 持久化副作用 | 静态 AST + `test_amane_no_side_effects.py` + H-14 | 无写文件 API；运行前后文件系统快照相同（宿主工厂自建的 `plugins/<id>` 目录除外并显式记录）；无 socket 创建 |
| E20 | 确定性 | `test_amane_determinism.py`、H-13 | 同输入重复 N 次逐字节相同；`PYTHONHASHSEED ∈ {0,1,2}` 的 subprocess 输出相同；AST：映射模块不迭代 `set` |
| E21 | mutation / non-vacuity | 第 9 节 | M-01..M-17 每个至少被一个指定测试杀死；记录失败用例与失败数；恢复证明 |
| E22 | Amane pre-import / `sys.modules` 隔离见证 | 第 5.2 节三种顺序 + `test_amane_isolation.py` + pre-import 见证 | 三种顺序均通过且计数一致；主进程 `sys.modules` 从无 `amane`（哨兵测试）；`tests/**` 静态无 `import amane`（host_scripts 除外）；pre-import 见证：在 3.14 + 真实 Amane 中先 `import amane.plugin` 再运行既有 `tests/contract`，如实记录结果（既有守卫的 OBS-01 行为属 Entry Closure 范围，**不在此修复**；P5-C1 新测试不得加重） |
| E23 | targeted tests | 第 5.2 节 | 全绿；记录 collected / passed |
| E24 | adapter contract tests | 第 5.2 节 | 全绿 |
| E25 | 既有 contract 套件 | `pytest tests/contract` | 全绿，计数与基线一致 |
| E26 | full suite | `pytest tests` | 全绿；计数 = 基线 + 新测试数 |
| E27 | skip / xfail 对账 | 基线 skip nodeid 清单 vs 最终清单 | 无新增 skip / xfail；清单逐项一致 |
| E28 | evidence gaps / known limitations | 合同第 28 节 L-01..L-14 + 实施中新发现 | 逐条记录；无“静默缺口” |

---

## 8. 真实宿主见证计划（`tools/run_amane_host_witness.py`；场景 H-01..H-15）

运行器在 subprocess 解释器（Python >= 3.14，已安装 Amane v0.15.0）中执行场景脚本；传输层是**脚本化的 `WebClient._session`**（与合同附录 A 相同的方法），**无真实网络**。
输出 JSON：`schema_version`、`python`、`amane{version, commit}`、`adapter_tree_sha256`、`core_tree_sha256`、`scenarios[{id, passed, observations}]`（不含时间戳 / 耗时，保证可复现）。

| ID | 场景 | 判据 |
|---|---|---|
| H-01 | 环境记录与真实 import | `amane.plugin` 可 import；`amane` 版本 = 0.15.0；commit = `45dff21…`；记录 Python 版本 |
| H-02 | `PluginManager.discover`（原始树与解压后的 zip 树） | 注册 `ffcc.fc2-metadata`；descriptor 逐项等于合同 §9；`configuration_model().model_json_schema()` 成功且无秘密类字段名 |
| H-03 | `install_plugin_zip(构建出的 zip)` | 返回 id；落盘目录名 = id；重新 discover 成功 |
| H-04 | 配置矩阵 | 合法：`None` / 显式 `sources` / 镜像 `base_url`；非法：未知 id、重复、空列表、全禁用、`base_url` 含 userinfo / 非 http、`deadline` 非法、未知字段；`HotSettings` 路由：`content_routes[fc2]=[id]` 接受，路由到 `censored` 拒绝（`content_types`），`field_priority` 含 `directors` 拒绝（`metadata_fields`） |
| H-05 | 缺失 Core | 屏蔽 `fc2_metadata_core` 后 `discover` -> `failures`、不注册、消息 = 冻结模板；`install_plugin_path` -> `ValueError("插件导入失败: …")` |
| H-06 | 经真实 `CrawlerFactory` 构造 provider | 同一 provider 被缓存复用；Core engine 只构造一次；`build()` 在合法配置下不抛 |
| H-07 | `fetch` SUCCESS 的真实 `MediaMetadata` | 与合同表 H 的黄金值逐字段相等（含 `source_url`、`external_id`、`extrafanart`、actors 性别 unknown、`fanart_urls` 缺席） |
| H-08 | 经真实 `invoke_source` 的结果矩阵 | SUCCESS -> OK；PARTIAL -> OK + 日志；全 NOT_FOUND -> `None`（记 `no_usable_metadata`）；各 `SourceErrorKind` -> 记录的 `reason` / `detail` 等于合同；非 FC2 / 缺号 -> `None` 且 0 次请求；外来 query -> `SourceError(unexpected)` |
| H-09 | 真实 `WebClient.request` 上的物理请求数 | 状态码 200 / 404 / 403 / 429 / 503 / 5xx：每来源 1 次；`CurlError` / 超时：≤ H；`max_retries ∈ {1,3,10}`；混合；熔断打开后 0 次；总数 ≤ S×H；对照合同 W-05 |
| H-10 | 真实 `RequestError` 的异常映射 | `timeout` / `network` / `unexpected` 分别得到合同表 E 的 Core kind |
| H-11 | 取消 | 挂起会话 + 取消：`CancelledError` 穿过真实 `invoke_source`；无结果；governor 空闲 |
| H-12 | 真实 `amane.aggregate.aggregate` 贯通（仅见证运行器使用该内部 API 作 oracle；adapter 不使用） | `source_urls / external_ids / extrafanart_urls` 只以 `ffcc.fc2-metadata` 为键；标量字段来源为该 id。若 `aggregate` 无法以最小参数调用，须在 HANDOFF 中记录为 evidence gap（不得悄悄略过） |
| H-13 | 确定性 | 同场景重复 3 次，及 `PYTHONHASHSEED ∈ {0,1,2}` 的 subprocess：输出逐字节相同 |
| H-14 | 无副作用 | `data_dir` 前后快照：除宿主工厂自建的 `plugins/<id>/` 空目录外无变化 |
| H-15 | v0.15.0 宿主缺陷 `max_retries = 0` | 所有来源 -> `FAILED / network`（fail-closed、确定性、0 次物理请求），与合同 L-04 一致 |

`test_amane_host_witness_log.py`（主进程，恒执行，不 skip）校验：日志 `amane.commit == 45dff21…`、`amane.version == 0.15.0`；场景 ID 集合恰等于 H-01..H-15（与运行器常量一致）；全部 `passed`；
`adapter_tree_sha256` 与 `core_tree_sha256` 等于当前仓库计算值（防止陈旧日志 / Core 被改动）。独立 Reviewer **必须**以第 5.3 节命令重跑见证并比对。

---

## 9. Mutation / Non-Vacuity 计划

方法：把插件树复制到临时目录，对副本施加一处文本补丁，在 subprocess 中运行指定测试（以 `-o pythonpath=…` 把副本置于最前；一个哨兵测试断言被测的 `fc2_amane_adapter.__file__` 位于副本内，证明确实测的是被篡改代码）。
每个 mutant 必须被**至少一个**指定测试杀死；HANDOFF 记录失败用例与失败数；最后证明工作树恢复（`git status` 干净，原树测试仍全绿）。

| ID | 变异 | 应被杀死的测试 |
|---|---|---|
| M-01 | 桥不传 `ok_statuses` | `test_amane_bridge_response`、`test_amane_retry_bounds` |
| M-02 | Core 重试改为 `max_attempts = 2` | `test_amane_retry_bounds`、`test_amane_runtime_lifetime` |
| M-03 | `BLOCKED` 映射到 `None` / `not_found` | `test_amane_error_mapping`、`test_amane_outcome_status` |
| M-04 | `source_url` 取 `source_urls[-1]` | `test_amane_narrowing` |
| M-05 | `external_id` 取 Core `external_ids` 的某个值 | `test_amane_narrowing` |
| M-06 | `runtime` 吞掉取消（`except BaseException`） | `test_amane_cancellation`、`test_amane_architecture_guards` |
| M-07 | `SourceError.detail` 拼入 `SourceResult.error_detail` / URL | `test_amane_error_mapping`、`test_amane_logging_redaction` |
| M-08 | 不规范化，直接用原始 `query.number` | `test_amane_number_boundary` |
| M-09 | 把 `fanart_urls` 并入 `thumb_urls` | `test_amane_metadata_mapping` |
| M-10 | 每次 `fetch` 重建 engine | `test_amane_runtime_lifetime` |
| M-11 | 桥模块加入 `import httpx` | `test_amane_architecture_guards` |
| M-12 | `PARTIAL` -> 抛 `SourceError` | `test_amane_outcome_status` |
| M-13 | 全 NOT_FOUND -> 抛 `SourceError` | `test_amane_outcome_status` |
| M-14 | 优先级改用 `set` 迭代 / 取最后一个 | `test_amane_error_mapping`、`test_amane_determinism` |
| M-15 | kind -> reason 表删除一项 | `test_amane_error_mapping`（枚举完备） |
| M-16 | `plugin.py` 引入非公共 Amane 导入（如 `amane.db`） | `test_amane_api_manifest`、`test_amane_architecture_guards` |
| M-17 | 纯模块加入文件写入 | `test_amane_architecture_guards`、`test_amane_no_side_effects` |

---

## 10. HANDOFF 证据要求（`docs/review/P5_C1_HANDOFF.md`；中文）

必须包含：坐标（Frozen Base、Design Accepted Head、S1 / S2 / S3 提交、Review Candidate head、Amane commit）；E1..E28 的逐项结果；合同 -> 测试映射实际 nodeid；
第 5 节命令及其**原始输出摘录**（collected / passed / skipped 数字）；见证日志路径与哈希；mutation 记录（失败用例与失败数）与恢复证明；E22 三种顺序的计数；
3.14 子集结果与 L-07 的如实记录；Evidence gaps / Known Limitations；对合同 C-01..C-13 各项的实现说明；偏差记录（若有）；**候选状态**：`READY FOR LEVEL 1 REVIEW` / `FAILED` / `BLOCKED`
（开发者**不得**写 PASS / CLOSED / FROZEN）；`New Architecture Blocker`；`Risk Escalation`。

---

## 11. Independent Review Plan

### 11.1 Design / Authority Review（实现之前；必需）

对象：本合同与本计划。Reviewer 应直接核对：Amane 坐标（`45dff21…`）、表 A 的文件 / 行号、W-05 / W-06 的复现（附录 A / B）、Core 白名单名字是否真实存在、
重试有界性公式、表 B-J 的完备性与一致性、不变量 I1-I26、升级门、P5-C1 / P5-C2 边界。通过后由该 Review 建立 Design Accepted Head。

### 11.2 C 级 Independent Level 1 Review（S1-S3 全部完成之后；一次）

Reviewer 审计：完整线性 diff（`Design Accepted Head..HEAD`）、完整合同映射、完整测试证据、安全不变量、mutation / non-vacuity、见证日志（**必须自行重跑第 5.3 节见证**）、evidence gaps。
裁决后若 FAIL，按治理文档第 12 节统一 R1（findings 满足同根因 / 不需新架构 / 不需新合同 authority 时）。

### 11.3 C 内中间 Review：NONE，除非出现

新的 Frozen Contract amendment、修改已 CLOSED package 的生产语义、持久化、新的 security boundary、升级门 U-1..U-8 中任一项。

---

## 12. STOP 条件（冻结）

```text
STOP-01 任一升级门 U-1..U-8 触发
STOP-02 无法提供 Python >= 3.14 + Amane v0.15.0 的见证环境（needs input；不得降级为只做替身测试）
STOP-03 真实宿主行为与合同 W-05 / W-06 不一致（设计前提失效 -> DESIGN BLOCKED，回到 Design Review）
STOP-04 API manifest 与 exact v0.15.0 不一致，或检出的 commit != 45dff21…
STOP-05 需要修改 Core / Organizer / 既有测试才能继续（发现 Core 缺陷：记录，不修复）
STOP-06 发现必须使用白名单之外的 Core 名字或非公共 Amane API
STOP-07 无法在不 skip 的前提下完成 E22 / E27
```

STOP 之后：写明 blocker 与证据，停止，不自行猜测合同。

---

## 13. 状态

```text
P5-C1 Design                 : CANDIDATE —— INDEPENDENT DESIGN REVIEW REQUIRED
P5-C1 Contract               : CANDIDATE
P5-C1 Construction Plan      : CANDIDATE（本文件）
P5-C1 Implementation         : NOT STARTED
Phase 5                      : ENTRY AUTHORIZED
src Diff                     : NONE
tests Diff                   : NONE
New Architecture Blocker     : NONE
Risk Escalation              : NONE（B -> C 未触发）
Next                         : P5-C1 CONTRACT / CONSTRUCTION PLAN INDEPENDENT DESIGN REVIEW（不得开始实现）
```

---

## 14. Design 静态自审（提交前确认）

1. 头部包含治理文档第 18 节要求的全部字段，且 Risk Class 与升级门已显式声明。✔
2. 治理四问有真实判断（合同第 4 节），P5-C1 / P5-C2 边界基于设计期实测（宿主漂移、环境依赖、Core 供给）而非照抄示例。✔
3. 合同表 A-J 齐全；I1-I20 全部出现，另新增 I21-I26。✔
4. 重试 / 限速 / 资源控制：所有权明确，公式有界（S×H，A=1），已由对真实 v0.15.0 `WebClient` 的实测支撑；不存在乘法重试。✔
5. 无需修改 CLOSED Core 合同：Core 重试经既有的 `RetryPolicy.no_retry()` 关闭，governor 使用既有默认。✔
6. 测试隔离：主进程不 import amane；真实宿主在 subprocess；不 skip；见证日志有新鲜度测试。✔
7. 本轮未修改 `src/**`、`tests/**`、`pyproject.toml`、Phase 4 docs、Phase 5 Entry Authority、治理文档、`CLAUDE.md`。✔
8. 未写 Contract FROZEN / Design PASS / P5-C1 STARTED。✔
