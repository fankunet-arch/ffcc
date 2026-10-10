# P6-C1 施工计划 —— Amane 真实批量集成与批量收尾（Real Amane Batch Integration & Closure）

```text
Governance Mode                    : ACCELERATED v2
Governance Authority               : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Package Frozen Base                : 4189b9552d26b3cc5273e0ac09e46e5a3759121d
Risk Class                         : C
User Capability / Vertical Closure : 一个真实用户把“脏”媒体目录经由真实 Amane 宿主（v0.15.0 / v0.18.0），完整走完
                                     scan → canonical FC2 识别 → P4 批量调度 → Amane SCRAPE（ffcc.fc2-metadata → Core 多来源 → Amane Metadata）
                                     → P6 桥 → P4 planning / publication / 图片 / NFO / 产物清单 / 执行前预检 → BatchPreview → 确定性 batch summary；
                                     并在来源降级、条目失败、混合批、宿主任务失败、宿主 API 传输失败、图片部分失败、坏 / 缺 metadata 下条目隔离正确；
                                     失败子集重试（成功条目不重跑）、取消（精确到任务、有界、不确定性显式）、并发上界、确定性与审计分离。
                                     不执行任何真实文件整理（Phase 7）。
Why Not Merge With Previous C      : P5-C2 已 CLOSED；P6 是新的 host batch integration boundary，不能追溯塞进 P5
Why Not Split Further              : failure/retry/cancel/summary 与 real integration 使用同一个 host-task boundary；拆开不提高 correctness/safety/auditability
Internal Stages                    : S1 / S2 / S3
Independent Review Plan            : Independent Design Review once before S1 + one C-level Independent Level 1 Review after complete implementation
Owner Question Gate                : BUSINESS DECISIONS ONLY
Evidence Gate                      : 合同第 23 节 E6-01..E6-27 全部满足（含：≥10 FC2 的两个真实宿主纵向门、失败 / 重试 / 取消 / 并发 / 确定性、route ownership 机械证明、
                                     安全 canary、不执行三层机检、16 项 mutation / non-vacuity、全量回归与基线对账、live smoke 记录、HANDOFF）
```

```text
Phase 6                       : DESIGN CANDIDATE
P6-C1                         : DESIGN CANDIDATE
Frozen Contract               : NOT YET ACCEPTED（docs/specifications/PHASE6_C1_AMANE_BATCH_INTEGRATION_CONTRACT.md）
Construction Plan             : NOT YET ACCEPTED（本文）
Design Accepted Head          : NOT ESTABLISHED
Implementation                : NOT STARTED
Production Modified           : NO
Tests Modified                : NO
```

本计划只有在独立 Design Review PASS 之后才成为 Frozen Construction Plan；在此之前**禁止 Developer 开始 S1**。Frozen 之后，计划与合同冲突时以合同为准。
本文与 `docs/PHASE6_MASTER_PLAN.md`、Frozen Contract 的范围 / Risk Class / Frozen Base / Governance Authority 必须逐字一致（合同 U6-12）。

---

## 1. 授权与坐标

* 合同：`docs/specifications/PHASE6_C1_AMANE_BATCH_INTEGRATION_CONTRACT.md`（以下简称“合同”；条款号 §n）。
* **Package Frozen Base = `4189b9552d26b3cc5273e0ac09e46e5a3759121d`**（P5-C2 Final Closure Docs Head）。**Governance Authority 是另一个坐标**
  （`3b9d39e9adbcc8a009707486eebbb8736a5b1c4d`），不得写成 Package Frozen Base。
* 工作 branch：`claude/phase6-c1-amane-batch-integration`。设计提交的 parent 精确为 Frozen Base；实现从 **Design Accepted Head** 继续。
* P5-C2 Final Reviewed Technical Head：`1ef23247c2c65649589e9919c00093901bbcb517`。

---

## 2. 拆包四问与中间 Review 裁决

1. **为什么这项工作不能和前一个 C 一起完成？** 前一个 C（P5-C2）已 CLOSED；P6 是新的宿主批量集成边界。
2. **单独拆包降低了什么具体风险？** 对 P6-C2（Failure / Retry / Batch Closure）：没有——失败映射、重试、取消、汇总与真实集成共用同一个 host-task 边界、同一 client、同一份审计、同一组真实宿主。
3. **该风险是否值得额外增加一次“开发停止 + Review + Closure”？** 否。
4. **如果取消这个边界，是否影响 correctness / safety / auditability？** 不影响；合并提高 auditability。⇒ **必须合并，Phase 6 只有一个 C；P6-C2 默认不存在**
   （重新提出的条件见 `docs/PHASE6_MASTER_PLAN.md` 第 5 节）。

**C 内中间独立 Review**：默认**不需要**。S1 / S2 / S3 连续施工，每个 S 仍有 developer checkpoint、单元 / 契约测试、mutation / non-vacuity、静态检查和独立 commit，
但**不**触发独立 Review、开发停止或 docs closure。只有出现以下情形之一才停止并升级（见合同 §28）：新的 CLOSED-package production 修改（U6-1）、真实 filesystem 执行（U6-2）、
持久化 / durable resume / 跨进程锁（U6-3）、新的安全架构（U6-8 / U6-5）、与合同 §7 不符的宿主观测（U6-6）。Risk C 的安全 Review 不被 Acceleration v2 取消：
**Design Review（一次）+ C-level Level 1 Review（一次）** 即为本包的安全 Review 计划。

---

## 3. 文件范围（机检：`tests/amane_batch/test_amane_batch_scope_gate.py`）

### 3.1 允许新增 / 修改（allow-list，逐字作为范围门的正则）

```text
src/fc2_amane_batch/.+\.py
tests/amane_batch/.+
tools/run_amane_batch_gate\.py
tests/amane_compat/test_amane_compat_scope_gate\.py                       （仅 HG-1，合同 §5.4）
tests/amane_compat/test_amane_compat_evidence_reconciliation\.py          （仅 HG-1，合同 §5.4）
docs/PHASE6_MASTER_PLAN\.md
docs/P6_C1_CONSTRUCTION_PLAN\.md
docs/specifications/PHASE6_C1_AMANE_BATCH_INTEGRATION_CONTRACT\.md
docs/review/P6_C1_HANDOFF\.md
docs/acceptance/evidence/P6_C1_(HOST_MATRIX|LIVE_SMOKE)\.json
```

### 3.2 零 diff（任何改动 = 升级门）

```text
src/fc2_metadata_core/.+          src/fc2_organizer/.+          adapters/.+
tools/(?!run_amane_batch_gate\.py).+       pyproject\.toml        CLAUDE.md       docs/PROJECT_GOVERNANCE_ACCELERATION\.md
tests/(?!amane_batch/|amane_compat/test_amane_compat_(scope_gate|evidence_reconciliation)\.py).+
docs/ 下全部既有文件（上面 allow-list 之外）
```

范围门同时断言：(a) `git diff 4189b95…..HEAD` 与工作树都落在 allow-list 内；(b) 两个 HG-1 文件中模块级常量
`ALLOWED_PATTERNS` / `FROZEN_PATTERNS` / `RECONCILIATION_ALLOWED` / `RECONCILIATION_ZERO_DIFF` 的 AST 与 Frozen Base 版本（`git show 4189b95…:<path>`）**逐字相同**，
且这两个文件的改动总行数不超过一个小常数（Design Review 在冻结时确认，建议 ≤ 60 行）。

### 3.3 新增文件清单（冻结的名字；测试文件 basename 必须全局唯一，`tests/amane_batch/` 内**无** `__init__.py`）

```text
src/fc2_amane_batch/   __init__.py errors.py credential.py config.py audit.py _wire.py host_client.py _lifecycle.py _mapping.py engine.py models.py facade.py

tests/amane_batch/     conftest.py（autouse：执行类 tripwire，合同 §19.2.2）
                       test_amane_batch_scope_gate.py        E6-01
                       test_amane_batch_architecture.py      E6-03, E6-18(静态)
                       test_amane_batch_config.py            E6-04
                       test_amane_batch_client.py            E6-05
                       test_amane_batch_wire.py              E6-06
                       test_amane_batch_mapping.py           E6-07
                       test_amane_batch_lifecycle.py         E6-08
                       test_amane_batch_cancellation.py      E6-09
                       test_amane_batch_concurrency.py       E6-10
                       test_amane_batch_security.py          E6-17
                       test_amane_batch_summary.py           E6-19
                       test_amane_batch_facade.py            P4 集成、retry_failed 选择、preflight、preview_root
                       test_amane_batch_determinism.py       E6-20（以及 E6-15 的进程内对照）
                       test_amane_batch_mutation_nonvacuity.py   E6-21
                       test_amane_batch_matrix_json.py       E6-26
                       test_amane_batch_gate_tools.py        门工具本身的单测（不启动宿主）
                       _batch_host_double.py                 脚本化宿主替身（见本计划第 4.2 节；永远不当作 Amane 证据）
                       _batch_upstream.py                    确定性回环上游（合同 §22.4）
                       _batch_fault_proxy.py                 故障注入代理（合同 §22.5）
                       _batch_oracles.py                     语义投影 / 树摘要 / 账本断言（真实宿主门与变异测试共用）
                       _batch_corpus.py                      ≥10 个号与行为表、图片路由
tools/                 run_amane_batch_gate.py               真实宿主门 / live smoke（子命令 --hosts / --live / --out）
docs/                  review/P6_C1_HANDOFF.md  acceptance/evidence/P6_C1_HOST_MATRIX.json  acceptance/evidence/P6_C1_LIVE_SMOKE.json
```

---

## 4. 内部阶段

三个阶段**连续施工**；阶段之间没有 Review、没有停下等人。每个阶段末尾做 developer checkpoint（commit + 本阶段测试全绿 + 范围门绿 + 本阶段 mutation 绿）。

### 4.0 第 0 步（S1 开工前，不是 Review）

1. 确认 Design Accepted Head 已由 Review 建立并记录进 HANDOFF；工作 branch 从该 Head 继续。
2. 重做合同 §7.1 的 Amane 四个 SHA 核查，并重做 §7.3 的逐项核查（与合同表 H2 对账）；任何不符 → U6-6 停止。
3. 在 Frozen Base `4189b95…`（或 Design Accepted Head，二者代码相同）上**记录基线**：各测试目录的通过 / 失败 / 跳过数（`tests/unit`、`tests/contract`、`tests/amane_adapter`、`tests/amane_compat`、`tests/phase4_acceptance` 等）与解释器版本。
   这是 E6-22 全量回归“基线对账”的依据；不得事后补。基线必须**如实**标出继承的既有红：设计期按断言逻辑求值，
   `test_amane_compat_evidence_reconciliation.py` 的两个范围测试在 `4189b95…` 上应为红（P5-C2 Final Closure 修改了 `adapters/amane/README.md`，合同 §5.4）；
   以真实 pytest 结果为准，标 `PRE-EXISTING RED @ 4189b95`，不得写成 P6 回归。
4. **HG-1 提交**（独立 commit，标注 `HG-1`）：按合同 §5.4 重绑两个历史门禁；该 commit 的 diff 只含这两个文件；完成后这两个文件在 P6 分支上全绿。

### 4.1 S1 —— Host Boundary + 安全 client + 结构化映射

交付（对应合同 §8-§12、§20.2-§20.3、§20.5）：

* `errors.py` / `credential.py` / `config.py` / `audit.py`（枚举与记录模型）/ `_wire.py` / `host_client.py` / `_lifecycle.py` / `_mapping.py` / `engine.py`。
* 测试：E6-01、E6-03、E6-04、E6-05、E6-06、E6-07、E6-08、E6-09、E6-10（引擎层）、E6-17（安全 canary，基于 `httpx.MockTransport` 与一个真实的回环 TLS / 重定向 / cookie 测试服务器）。
* 本阶段 mutation（进程内）：M6-03 / M6-04 / M6-05 / M6-06 / M6-09 / M6-12 / M6-13 / M6-15 / M6-16 的**单测层**对应项，每项带未变异孪生。

要点（合同条款的落实顺序）：

1. 先写 `_wire.py` 与 `host_client.py` 并用 `MockTransport` 钉死“请求账本”（方法 / 路径 / 体键集 / 头集 / 无 cookie / 无重定向 / 响应上限）。
2. 再写 `_lifecycle.py`：状态机、deadline（至少一次观察）、观察失败容忍、清理预算、`CancelOutcome` 的 8 种结局；**提交永不重试**。
3. 再写 `_mapping.py`：字段表穷举守卫、URL 卫生与 P5 I22 对账、最低成功、号等价、归属校验、`HostFailureKind` → Core 配对表（用 `ALLOWED_ERROR_KINDS` 穷举验证）、产出的 `AggregationResult` 通过 Core 校验并被 P4-C9 诊断投影接受。
4. 最后写 `engine.py`：把以上串起来；`aggregate` 是类属性里的普通 `async def`（P4 静态形态检查要求）。

S1 退出条件：E6-03..E6-10 + E6-17 的单测全绿；范围门绿；S1 mutation 全部“孪生绿 / 变异红”；无任何 CLOSED 文件改动（HG-1 除外）。**无需 Review，直接进入 S2。**

### 4.2 S2 —— P4 BatchOrchestrator 集成 + 10-item 纵向 preview + 失败 / 重试 / 取消 / 并发

交付（合同 §13-§19、§20.4、§21）：

* `models.py`（`AmaneBatchRound` / `AmaneBatchPreview` / `AmaneBatchSummary`，含全部 `__post_init__` 不变量）与 `facade.py`（preflight、`preview`、`preview_root`、`retry_failed`、`audit_snapshot`、`aclose`）。
* 测试替身 `_batch_host_double.py`：一个基于 `httpx.MockTransport` 的**脚本化宿主**，实现表 H1 的 5 个端点并建模 Amane 的任务队列（QUEUED → RUNNING → DONE / FAILED、可配置 worker 并发、可控完成顺序、
  两种取消语义 DIFF-P6-01 的 v0.15.0 / v0.18.0 变体、`Set-Cookie: amane_token`、401 行为）。
  **它只服务于 S1 / S2 的进程内确定性测试，永远不被当作 Amane 证据**（E6-11..E6-16 必须是真实宿主）。S3 用“同一场景在替身与真实宿主上语义投影一致”的对账来约束替身不偏离真实行为。
* 测试：E6-10（全链并发）、E6-19、E6-20（进程内）、`test_amane_batch_facade.py`（主轮 / 重试 / preflight / `preview_root` / 输入校验 / 取消）、E6-09（门面层取消）、E6-18（tripwire 全链）。
* 进程内纵向：≥ 10 个 FC2 经 `scan → … → BatchPreview → summary`，图片走真实 `HttpxImageClient` + `MockTransport`；失败 / 重试 / 取消 / 并发 / 确定性（完成顺序反转）全覆盖。
* 本阶段 mutation：M6-07 / M6-08 / M6-10 / M6-11 / M6-14 的进程内对应项（孪生绿 / 变异红）。

S2 退出条件：进程内纵向全绿；`AmaneBatchSummary` 与 P4 `PreviewSummary` 交叉校验；`peak_in_flight ≤ M` 在完成顺序反转 / 慢 / 失败 / 取消下成立；范围门绿。**无需 Review，直接进入 S3。**

### 4.3 S3 —— 双版本真实宿主矩阵 + 确定性 / mutation / 证据 + 全量回归 + HANDOFF 候选

交付（合同 §22-§25）：

* `tools/run_amane_batch_gate.py`：准备 HOST-A-SRC（v0.15.0）与 HOST-B-SRC（v0.18.0）（只读复用 P5-C2 的 `prepare_amane_hosts` / `build_core_wheel` / `build_amane_release` 与台账 pin），
  按合同 §22.2 配置；运行 E6-11 .. E6-16；写 `P6_C1_HOST_MATRIX.json`（确定、自洽；允许的非确定字段仅限显式列出的运维字段）。
* `_batch_upstream.py` / `_batch_fault_proxy.py` / `_batch_corpus.py` / `_batch_oracles.py`；宿主级 mutation M6-01 / M6-02（门工具变体运行，退出码非 0）。
* 双版本矩阵：纵向门（≥ 10 FC2）、失败矩阵、重试（宿主任务账本计数）、取消（含旁观任务与不确定性）、确定性（完成顺序反转 + 非空性）、route ownership、安全 canary（token 为 canary 的真实宿主）、不执行（文件系统树摘要）。
* 替身 / 真实宿主对账：把 S2 的核心场景（ALL_OK×10、一个失败条目、取消）同样在真实宿主上运行，两边语义投影必须一致。
* 可选：HOST-A-WIN / HOST-B-WIN（SC-01 / SC-02）；运行了才记录，没运行记 `UNVERIFIED`。
* `P6_C1_LIVE_SMOKE.json`：`--live` 尝试（合同 §25）；结果 `VERIFIED` / `UNVERIFIED_ENVIRONMENT` / `NOT_RUN`，**不得**默认写成 PASS。
* E6-21（全部 16 项 mutation 孪生）、E6-22（全量回归与基线对账）、E6-23（构件同一性）、E6-25（Python 3.12 与 3.14）、E6-26（证据 JSON 校验）、E6-27（HANDOFF）。

S3 退出条件：合同 §23 的 E6-01..E6-27 全部有证据（或把无法获得的项如实写入 evidence gaps，并且不扩大任何支持声明）；HANDOFF 候选完成；然后**停止，等待 C-level Independent Level 1 Review**。

---

## 5. 提交计划

```text
D0  docs(phase6): P6-C1 Design Candidate           本提交（docs-only；parent = Package Frozen Base）
——— Independent Design Review ——— PASS → Design Accepted Head ———
T0  test(p6): HG-1 rebind historical P5-C2 diff gates         （仅两个文件）
S1  feat(p6-s1): host boundary, secure client, structured mapping      （可多个 checkpoint commit）
S2  feat(p6-s2): batch integration facade, retry/cancel/concurrency    （可多个 checkpoint commit）
S3  test(p6-s3): real-host matrix, determinism, mutation, evidence     （可多个 checkpoint commit）
H   docs(p6): P6-C1 HANDOFF + evidence                                 （实现候选）
——— C-level Independent Level 1 Review ———
R1  统一 R1（若 FAIL；同根因 / 范围明确 / 无需新 authority）
F   纯状态 Final Closure（Governance v2 §11.1：与 Final Closure 合并，不为中间状态单独做 docs 循环）
```

* Developer 不得改写 Design Accepted Head 以前的历史。
* 每个 commit 必须通过范围门；任何一次让范围门红的 commit 都是缺陷。
* 不得夹带无关提交；设计提交 D0 必须是 **ONE docs-only commit**。

---

## 6. 评审计划（Risk C）

| 评审 | 时点 | 内容 |
|---|---|---|
| **Independent Design Review**（一次） | S1 之前 | 三份文档一致性；合同 §7 宿主事实复核；**HG-1 裁决**；F-1（`preview_retry` 不可用）裁决；L6-01 独占 route 前提；包位置裁决（§5.3） |
| **C-level Independent Level 1 Review**（一次） | S3 之后 | 完整线性 diff、合同→实现→测试映射、全部证据与 mutation、安全不变量、真实宿主矩阵、evidence gaps |
| 统一 R1（必要时） | Level 1 FAIL 之后 | 同一根因 / 范围明确 / 不需要新 authority；一次闭合全部已知 findings 并检查直接回归 |
| Final Closure | Level 1（或 R1）PASS 之后 | 纯状态 docs；不单独再做 docs-only Review |

Finding authority 边界（Governance v2 §12.2）：Contract amendment、Plan scope amendment、新的安全设计、新的公共 API 裁决都**不得**混入普通 R1，必须先解决 authority。

---

## 7. Developer 纪律

1. **不得削弱或删除** CLOSED 测试；HG-1 之外不得改动任何 CLOSED 测试；不得 `skip` / `xfail` 新测试来“通过”。
2. 真实宿主证据不得由替身代替；替身永远带显式标签；缺少环境 → 如实 `NOT_RUN` / `UNVERIFIED`，不得写 PASS。
3. 凭据只用 canary 值；仓库中不得出现任何真实 token / cookie；测试宿主一律一次性、回环、临时目录。
4. 不触碰用户的 Amane 实例或数据目录；所有宿主产物都在临时目录。
5. 不得在生产代码里加入版本分支、feature detection、文本解析、日志、文件 / 环境访问（合同 §6.4、§12、§26）。
6. 每个 mutation 控制都必须带“未变异孪生”；只证明变异为红而没有孪生为绿的控制视为空洞。
7. 测试文件 basename 全局唯一；`tests/amane_batch/` 内不建 `__init__.py`；辅助模块以下划线开头。
8. 任何疑似需要 CLOSED production 修改的情形：**停止**并按合同 U6-1 上报 `AUTHORITY ESCALATION REQUIRED`，不得自行写进普通 P6。
9. 不询问 Owner 普通技术问题（命名、文件内部组织、fixture、测试结构、明显更安全的 fail-closed 默认）；只有业务裁决才暂停。

---

## 8. 环境前提（缺失则对应证据如实标 NOT_RUN / UNVERIFIED）

```text
项目解释器：Python ≥ 3.11（E6-25：3.12 与 3.14 各跑受影响测试）；httpx 0.27.x（Core 既有依赖）
宿主解释器：Python 3.14.x（独立 venv，沿用 P5-C2 的 prepare_amane_hosts）
平台：Windows x64（SC-03 / SC-04）；回环端口；git；pip（仅用于准备宿主 venv，不是任何信任来源）
live smoke：需要公网（失败则 UNVERIFIED_ENVIRONMENT / NOT_RUN，不影响确定性门）
```

---

## 9. HANDOFF 要求（`docs/review/P6_C1_HANDOFF.md`）

必须包含：状态头（Risk C、Frozen Base、Design Accepted Head、各阶段 commit、branch）；合同 → 实现 → 测试映射（逐条款 / 不变量 / E6-xx）；完整 diff scope（含 HG-1 两个文件的逐行说明）；
基线与最终通过数对账；每个命令与原始输出摘要；真实宿主矩阵摘要（两个必需坐标）；mutation 控制清单与结果；live smoke 状态；**evidence gaps**；**known limitations（L6-xx）**；
Phase 7 输入（合同 §19.3）；明确声明：Production CLOSED 范围零 diff、未调用任何执行、无持久化。纯状态内容采用 Final Closure 合并（Governance v2 §11.1）。

---

## 10. 状态

```text
Phase 6                       : DESIGN CANDIDATE
P6-C1                         : DESIGN CANDIDATE
Frozen Contract               : NOT YET ACCEPTED
Construction Plan             : NOT YET ACCEPTED
Design Accepted Head          : NOT ESTABLISHED
Implementation                : NOT STARTED
Production Modified           : NO
Tests Modified                : NO
Risk Class                    : C
Next                          : INDEPENDENT DESIGN REVIEW（通过之前禁止 Developer 开始 S1）
```

唯一 authority 转换：独立 Design Review PASS → 该 Design Candidate SHA 成为 Design Accepted Head（Frozen Contract / Plan Head、Implementation Input）→ 才允许进入 S1。
