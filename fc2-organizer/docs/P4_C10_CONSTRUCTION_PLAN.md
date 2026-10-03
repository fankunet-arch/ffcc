# P4-C10 施工计划（Construction Plan）-- Phase 4 最终验收（Phase 4 Final Acceptance）

```text
Governance Mode                    : ACCELERATED v2
Governance Authority               : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Package Frozen Base                : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c（P4-C9 Final Closure Docs Head）
Planning Parent                    : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c
Risk Class                         : B（带强制升级门 U-1..U-7；合同第 3 节）
User Capability / Vertical Closure : Phase 4 Final Acceptance —— 已 CLOSED 的 P4-C1..P4-C9 作为一个整体系统，经真实跨包链路
                                     （discover_media -> 真实 MultiSourceEngine -> planning / publication / NFO -> 真实 HttpxImageClient
                                     -> mapping -> P4-C7 执行 -> retry / merge -> diagnostics）在可丢弃 fixture 上验收，得出 Phase 4
                                     Exit Criteria 的裁决与 Phase 4 → Phase 5 输入边界
Why Not Merge With Previous C      : P4-C9 已正式 CLOSED（c293ed75…）；P4-C9 是“诊断能力”，P4-C10 是“全部 package 的整体验收”，
                                     验收对象包含 P4-C9 本身；合并会要求重开 CLOSED package 并使其 closure 证据失效（第 1 节 Q1、Q4）
Why Not Split Further              : 证据基础设施（harness / oracle）、跨包场景 / 安全 / mutation 门、回归 / 平台 / HANDOFF 共同构成同一个
                                     “Phase 4 是否可以 CLOSED”的裁决；任何一段单独都不构成可验收的结论；拆分只增加等待（第 1 节 Q3）
Internal Stages                    : S1 / S2 / S3（连续施工；无中间 Review；无 S 级状态 docs）
Independent Review Plan            : Design Authority Review（Original 17c194a…：FAIL -> Design-R1：R-01/R-02/R-03 CLOSED，发现 R1-01 -> Design-R2：R1-01 CLOSED，
                                       发现 R2-01 -> Design-R3 增量闭合复查，一次）
                                     + 1 次 C10 Independent Level 1 Final Acceptance Review（S1-S3 全部完成后；分别给出 Technical Acceptance 与
                                       Phase 4 Exit Authorization 两个裁决；含 F2 路径下的 Failed Acceptance Head）
                                     + 1 次 Phase 4 Final Closure Docs-Only Review（EC-15；Phase 级 Frozen Base 交接，治理文档第 11.2 节；
                                       显式承担 XD-A08 authority disposition review）
                                     C 内中间 Review：NONE（含生产改动的统一 C10-R1 例外，见第 12 节；F2 不新增任何中间 Review）
Owner Question Gate                : BUSINESS DECISIONS ONLY（唯一可能的 Owner 事项：是否授权可选原生跨卷证据目录，非阻塞）
Evidence Gate                      : 第 10 节（Contract -> 测试映射、diff scope、G-T / G-P4 / G-FULL、skip nodeid 对账、L-01..L-14、
                                     SI-01..SI-22、S-01..S-22、G-500、M-01..M-14 与恢复证明、PC-01..PC-09、Exit Debt Ledger
                                     （A = 8 / B = 17 / C = 15，含 XD-A08 状态）、环境记录、known limitations、evidence gaps；
                                     失败路径记录：F2 findings、F2 之后收集的安全证据、被 F2 阻塞的场景；三层状态字段：
                                     Technical Acceptance Candidate Status / Technical Acceptance Verdict（S3 恒 NOT ESTABLISHED）/
                                     Final Reviewed Acceptance Head（S3 恒 NOT ESTABLISHED）/ XD-A08 / Phase 4 Exit Authorization / Phase 4 / Phase 5）
Python Runtime Authority           : Python >= 3.11（不修改 pyproject.toml；Windows 11 / Python 3.12.x 只是正式验收证据环境）
Production Change                  : NONE（默认；任何 src/** 改动 = 升级门 U-1，且只可能发生在统一 C10-R1 中）
Design-R1                          : 只闭合 P4-C10-DESIGN-R-01 / R-02 / R-03；不改变 Risk Class B、G-500、L / SI / S / PC / M 矩阵语义、
                                     F3 / F5 处置、原生跨卷处置、DF-07、EC-15（见下方“Design-R1 修订记录”）
```

### Design-R1 修订记录（本计划侧；与合同“Design-R1 修订记录”一一对应）

| Finding | 本计划的同步内容 | 状态 |
|---|---|---|
| P4-C10-DESIGN-R-01（HIGH / BLOCKING） | Evidence Gate / 第 8 节 / 第 10 节 / 第 13 节 / 自审第 5 项：C5-R1-L1 = XD-A08（A 类、OPEN、阻塞 Phase 4 Closure）；Ledger A = 8 / B = 17 / C = 15；Final Closure 前必须取得 authority | REMEDIATED — INDEPENDENT REVIEW REQUIRED |
| P4-C10-DESIGN-R-02（HIGH / BLOCKING） | 第 4.3 节新增读 / 改访问规则；STOP-02 / STOP-05 / 第 5.1 节 / 第 8 节 PC-08 措辞对齐合同第 3.4 节；原生跨卷例外不变 | REMEDIATED — INDEPENDENT REVIEW REQUIRED |
| P4-C10-DESIGN-R-03（MEDIUM / BLOCKING） | 第 3 节 S1-S3 规则、第 11 节 Review 计划、第 12 节 C10-R1 路径、第 14 节 STOP-02 / STOP-03 及“F2 流程（非 STOP）”：F2 流程（禁止修复 -> 记录 -> 继续安全证据 -> Failed Acceptance Head -> Level 1 FAIL -> 统一 C10-R1）；F3 / F4 / 真正 U 门仍立即 STOP | REMEDIATED — INDEPENDENT REVIEW REQUIRED |

（上表是 Design-R1 提交时的状态；其后独立 DESIGN-R1 Closure Review 已确认 R-01 / R-02 / R-03 = CLOSED。）

### Design-R2 修订记录（本计划侧；与合同“Design-R2 修订记录”一一对应）

| Finding | 本计划的同步内容 | 状态 |
|---|---|---|
| P4-C10-DESIGN-R1-01（HIGH / BLOCKING；Authority / Closure Ordering / Constructibility） | 采用方案 B：Technical Acceptance 与 Phase 4 Exit Authorization 分成两个裁决（合同第 16 节）。本计划同步：S3 状态措辞（第 3 节）、第 10 节 HANDOFF verdict 字段、第 11 节 Level 1 双裁决与 XD-A08 路径、第 13 节 Final Closure 路径重排（XD-A08 的 authority disposition 由 EC-15 Review 承担，不再是创建 Final Closure Docs 的前置）、第 14 节 F2 流程状态措辞、第 15 节状态、第 16 节自审 | REMEDIATED — INDEPENDENT REVIEW REQUIRED |

Design-R2 不改变 Design-R1 已 CLOSED 的内容与 Risk Class B、G-500、L / SI / S / PC / M 矩阵语义、F3 / F5 处置、原生跨卷处置、DF-07、EC-15 的独立性、
Ledger 计数 A = 8 / B = 17 / C = 15、U-2、读 / 改边界、F2 流程、F3 / F4 立即 STOP。（R1-01 后经独立 DESIGN-R2 Incremental Closure Review 确认 CLOSED。）

### Design-R3 修订记录（本计划侧；与合同“Design-R3 修订记录”一一对应）

| Finding | 本计划的同步内容 | 状态 |
|---|---|---|
| P4-C10-DESIGN-R2-01（MEDIUM / BLOCKING；Verdict Lifecycle / HANDOFF Constructibility / Review Ordering） | 采用 Model 1：candidate status 与 reviewed verdict 分成两套字段（合同第 16.1a / 16.1b 节）。本计划同步：头部 Evidence Gate、S3 第 6 / 7 项（候选状态 READY FOR LEVEL 1 REVIEW / FAILED / BLOCKED；Verdict 与 Final Reviewed Acceptance Head 恒 NOT ESTABLISHED；开发者不得写 PASS）、第 10 节 HANDOFF 字段、第 11 节 Level 1 reviewed verdict 与 authority carrier、第 13 节 Final Closure 记录 reviewed verdict、第 14 节 F2 流程状态措辞、第 15 节状态、第 16 节自审 | REMEDIATED — INDEPENDENT REVIEW REQUIRED |

Design-R3 不改变：Technical Acceptance / Phase Exit 双裁决模型、XD-A08 语义（OPEN 不阻塞 Technical Acceptance、阻塞 Phase Exit）、EC-10 / EC-14 / EC-15 的含义、
XD-A08 fail-closed 发现路径、Risk Class B、Ledger A = 8 / B = 17 / C = 15、U-2、读 / 改边界、F2 流程、F3 / F4 立即 STOP、G-500、各矩阵、F3 / F5 与原生跨卷处置、DF-07、Phase 5 边界。
R2-01 不得写为 CLOSED / PASS / ACCEPTED / FROZEN；Design Accepted Head 仍为 NOT ESTABLISHED。

```text
Package               = P4-C10 Phase 4 Final Acceptance（不新增生产 package）
Branch                = claude/phase4-c10-final-acceptance（自 c293ed75… 创建；不在 claude/phase4-c9-diagnostics 上工作）
规范合同              = docs/specifications/PHASE4_FINAL_ACCEPTANCE_CONTRACT.md
Original Design Cand. = 17c194a71f0292e323591b8849ac65b9e14f7779（Independent Design Review：FAIL）
Design-R1 Candidate   = 5dc80fdebb467f38a852c4501c32ba65c6dd153f（R-01/R-02/R-03 CLOSED；发现 R1-01）；Design-R1a = 18e6e54fc6ba016a5a5e1b0b262b7a5e23210792（亦为 Design-R2 Base）
Design-R2 Candidate   = c284108c6f4e542e8d5e574bafa8e0815681957c（R1-01 CLOSED；发现 R2-01；亦为 Design-R3 Base）
Design-R3 Candidate   = 本 docs-only 提交（git log -1 --format=%H -- fc2-organizer/docs/P4_C10_CONSTRUCTION_PLAN.md）
Frozen Contract       = NOT ACCEPTED
Construction Plan     = NOT ACCEPTED（本文件）
Design Accepted Head  = NOT ESTABLISHED
Implementation        = NOT AUTHORIZED
```

坐标规则（冻结）：Package Frozen Base = Planning Parent = `c293ed75…`；Governance Authority = `3b9d39e…`（`c293ed75…` 的祖先，治理文档自此未变）。
唯一 authority transition：P4-C10 Independent Design-R3 Closure Review PASS -> Design Accepted Head = Design-R3 Candidate -> Frozen Contract /
Construction Plan = Design-R3 Candidate -> 才允许进入 S1（Design-R3 开发者完成修订本身不等于 PASS）。不创建 design closure / design accepted 之类的纯状态 docs 提交（治理文档第 11.1 节）。

Design PASS 之后，开发者只能**执行**本计划：不得重新设计、不得调整 S 边界、不得把任何设计项推迟到“开发时再决定”。合同与本计划
未写明的实现细节（helper 命名、文件内部组织、fixture 写法、断言写法）由开发者按以下优先级自行裁决，并在 commit message 中记录理由：

```text
1. Frozen Contracts（P4-C1..P4-C9 与本合同）  2. fail closed  3. 只作用于可丢弃 fixture  4. oracle 独立于被测 package
5. 不改变 CLOSED package  6. deterministic  7. bounded resources / 运行时间  8. minimal dependency  9. testability
```

---

## 1. 治理四问（治理文档第 15 节）与 C 粒度

### Q1 为什么这项工作不能和前一个 C（P4-C9）一起完成？

* P4-C9 已正式 CLOSED（Final Closure Docs Head `c293ed75…`），其 Contract / Plan / HANDOFF 按治理文档第 5 节不受追溯修改。
* P4-C10 的验收对象**包含** P4-C9：诊断覆盖是 P4-C9 合同第 30 节明确留给 P4-C10 的跨包义务。验收者不能与被验收的最后一个 package 合并而不
  降低独立性。
* 治理文档第 14.2 节明确规划“P4 : C9 + C10 = 2”，P4-C10 为“一个最终验收 C”。

### Q2 单独拆包降低了什么具体风险？

* 把“Phase 4 是否可以 CLOSED”的裁决与任何生产开发隔离：P4-C10 的 diff 可以用一条机器可验证的判据审计——
  `git diff <Design Accepted Head>..<C10 head> -- fc2-organizer/src` 为空，`-- fc2-organizer/tests` 只含 `tests/phase4_acceptance/**`。
* 防止 Final Acceptance 演变为“顺手功能”的入口（合同第 1.3 节 NO FEATURE EXPANSION）。

### Q3 该风险是否值得额外增加一次“开发停止 + Review + Closure”？

* 值得，且只值一次 C 级边界：P4-C10 是 Phase 级退出门，必须有独立的 Design Review 与独立的 Level 1 Final Acceptance Review。
* 不值得在 C 内部增加边界：S1（harness / oracle / 语料）不产生任何验收结论；S2（跨包场景 / 安全 / G-500 / mutation）依赖 S1；
  S3（回归 / 平台 / HANDOFF）依赖 S2。任何一段单独 Review 都无法回答 Exit Criteria，只增加等待。因此**不**拆成 C10-1 / C10-2 / C10-3。

### Q4 如果取消这个边界，是否影响 correctness、safety 或 auditability？

* 取消 **P4-C9 / P4-C10** 之间的边界：**会**——验收者与被验收者混合，降低 auditability，并要求重开 CLOSED package。
* 取消 **S1 / S2 / S3** 之间的边界：**不会**——三者共享同一 Frozen Contract、同一测试树、同一次 C 级 Review；每个 S 仍有 developer
  checkpoint、独立 commit 与非空洞性证据。按治理文档第 15 节原则上必须合并。

### 1.1 为什么采用一个 C

治理文档第 14.2 节的规划建议与本风险分析一致：Phase 4 Final Acceptance 是**一个**完整、可独立验收的纵向闭环（Phase 4 整体 -> Exit
Criteria 裁决）。没有任何 C 类风险要求拆分（合同第 3 节：无生产改动、无新安全边界、无持久化、文件系统修改只在可丢弃 fixture 上由既有代码执行）。

### 1.2 为什么不与 C9 合并

见 Q1、Q4。补充：P4-C9 的 Risk Class B 不被机械继承；P4-C10 的 B 是独立裁决（合同第 3.1 节），理由不同（P4-C9：诊断 observer；
P4-C10：Phase 退出门，主要风险是虚假验收）。

### 1.3 为什么不继续拆分

见 Q3。另：若拆成“集成验收 C”与“平台 / 回归 C”，后者的 Exit Criteria 结论依赖前者的全部证据，二者之间的 Review 不会产生任何独立可用的
结论；而真正需要独立环境的平台边界（原生 symlink、POSIX、原生跨卷、ACL、长路径）已经按 Ledger 指派给 P7-C2，不在 Phase 4 内拆包。

---

## 2. Risk Class 与升级门

* **Risk Class = B**（合同第 3.1 节）。保持 B 的前提：Production Change = NONE；全部文件系统**修改**只在 pytest `tmp_path` 或 harness 登记的可丢弃验收根内的
  可丢弃 fixture 上由既有、已复查的 P4-C6 / P4-C7 代码执行（对仓库内文件只有只读访问，合同第 3.4 节）；无新安全边界；无持久化。
* **升级门 U-1..U-7**（合同第 3.2 节，冻结）：任一**真正**触发即停止 B 类施工，在状态说明中记录触发项与证据，等待治理裁决；没有治理依据不得降级。
  U-1 只在 CLOSED package `src/**` 被实际修改时触发；S1-S3 中发现 F2 本身不触发 U-1，走合同第 13.1 节 F2 流程（本计划第 3、14 节）。
* **C 内中间独立 Review：NONE**（合同第 3.3 节）。唯一例外：含 CLOSED package 生产改动的 C10-R1（U-1）自身需要独立 Review（第 12 节）。

---

## 3. 内部施工模型（S1 -> S2 -> S3，连续施工）

规则（全部 S 适用）：

* 连续施工：S1、S2 完成后不 STOP、不等待 Review、不创建 docs commit。
* 每个 S 结束时执行 developer checkpoint（不是治理节点）：该 S 的新测试全部通过；G-P4 无回归；`git diff --check` 干净；diff 只触及该 S 允许的
  文件（第 4 节）。checkpoint 结果写入该 S 的 commit message。F2 流程下的例外：若 checkpoint 失败的原因经分类为 F2（被验收 production 偏离其
  Frozen Contract），该测试 / 场景按合同第 13.1 节记录为 F2 finding，不得为使 checkpoint 通过而修改 production、修改既有测试、降低断言或添加
  skip / xfail；其余全部测试仍须通过。
* 每个 S 一个或多个线性 commit；禁止 rebase、amend、squash、force push、历史改写。
* 合同与本计划在 S1 / S2 中一律不修改（包括状态行）；S3 的 HANDOFF commit 中允许一次性同步合同第 20 节与本计划第 15 节的状态行（仅状态）。
  任何语义改动 = authority 修订，STOP 并走独立复查。
* 任何阶段都不得修改 `src/**`；发现生产缺陷时按合同第 13、14 节分类，不得顺手修：
  * **F2**（普通生产缺陷）：按合同第 13.1 节 F2 流程——禁止 production repair、禁止改 affected CLOSED package、记录 `P4-C10-F2-<NN>`、验收转 FAIL、
    **继续**收集仍安全的 S1 / S2 / S3 证据（可丢弃边界内、不改 production、无 authority amendment、无其它真正 U 门）、被缺陷路径直接阻塞的场景记录
    `NOT RUN / BLOCKED BY F2 <id>`、S3 形成 Failed Acceptance Head 与 HANDOFF（`Candidate Status : FAILED — F2 PRODUCTION FINDING(S)`；`Technical Acceptance Verdict : NOT ESTABLISHED`；
    `Production repair : NOT PERFORMED`）、
    Level 1 Review 判 FAIL、统一 C10-R1（第 12 节）。**不**为每个 F2 单独 Review，**不**机械往返。
  * **F3 / F4 / 真正的 U 门 / 第 14 节其它 STOP 条件**：立即 STOP C10 执行（不属于 F2 流程）。
* 全部 C10 测试在模块顶层 import `fc2_*` 名称（合同第 12.7 节）。

### S1 —— Authority 机器核对、基线、acceptance harness、语料与独立 oracle

交付：

1. **Authority / 基线证据（不入库，写入 HANDOFF）**：执行第 7.1 节全部核对命令（坐标祖先关系、`src` 零漂移、各 package 状态行为 CLOSED）；
   在 Design Accepted Head 上于正式证据环境执行 G-FULL 基线运行，得到基线数字与 `SKIP_BASE` nodeid 集合（合同第 8.3 节）。
2. `tests/phase4_acceptance/__init__.py`（空）。
3. `tests/phase4_acceptance/_harness.py` —— 真实链路构建器（第 5 节）：脚本化 source 引擎、真实 adapter 引擎、真实 `HttpxImageClient` +
   `MockTransport` 路由、orchestrator 工厂、可丢弃场景树、sandbox guard、按条目一次性故障注入器（只经合同第 12.6 节授权接缝）、写操作观察包装、
   socket 陷阱、并发观测与门控事件。
4. `tests/phase4_acceptance/_corpus.py` —— FX-1..FX-6 与 G-500 的用例定义、合成 JPEG 构造器、URL -> 字节的确定性映射、由定义推导的全部期望值
   （布局、计数、RetryKind、outcome、NFO 字段、诊断计数）。
5. `tests/phase4_acceptance/_oracles.py` —— `AcceptanceGateViolation(AssertionError)` 与共享门：全树快照（路径 / 类型 / 大小 / mtime_ns /
   sha256 / inode）、`gate_source_not_lost`、overwrite / 预置条目不变、包含关系与写操作路径集合、临时文件残留、preview 零修改、
   布局精确列举、NFO 解析对照（`xml.dom.minidom`）、图片字节身份、summary / outcome / 账目恒等式、诊断 canary 扫描与 JSON 结构检查、
   确定性归一化比较。
6. `tests/phase4_acceptance/test_p4_acceptance_harness.py` —— harness 自检：每个共享门在干净输入上通过、在植入违规时失败（正 / 负向对照）；
   sandbox guard 拒绝 `tmp_path` 之外的路径；socket 陷阱与写操作观察包装生效且透明（包装前后同一场景结果投影相等）；授权接缝注入确实触发；
   `_corpus` 期望值的内部一致性（例如 G-500 各组之和 = 500、各代计数推导自定义）。
7. `tests/phase4_acceptance/test_p4_acceptance_architecture.py` —— C10 测试层守卫（AST）：只 import 被验收 package 的公开 API、合同第 12.6 节
   授权接缝、`tests/support/**`、标准库、`httpx`、`pytest`；不 import `tests/unit/**`；`httpx` 只用于 `MockTransport` 与真实 `HttpxImageClient`，
   不 import 其它网络库（`requests`、`urllib.request`、`http.client` 等）；`socket` 只允许出现在 `_harness.py` 的陷阱实现中；无 3.12+ 专属名称（合同 PC-01）；无盘符根字面量、无 `expanduser` / `Path.home()`；无函数内局部 `fc2_*` import；
   mutation 表面（合同第 11.3 节）只出现在 `test_p4_acceptance_mutations.py` 与 harness 自检测试中。

S1 允许改动文件：

```text
A tests/phase4_acceptance/__init__.py
A tests/phase4_acceptance/_harness.py
A tests/phase4_acceptance/_corpus.py
A tests/phase4_acceptance/_oracles.py
A tests/phase4_acceptance/test_p4_acceptance_harness.py
A tests/phase4_acceptance/test_p4_acceptance_architecture.py
```

S1 完成：继续 S2，不等待 Review，不创建 docs commit。

### S2 —— 跨包场景、Safety Gate、G-500、mutation

交付（测试文件 -> 合同条目）：

| 文件 | 覆盖 |
|---|---|
| `test_p4_acceptance_chain.py` | S-01..S-09、S-12；L-01..L-11 的真实链路证据 |
| `test_p4_acceptance_real_adapters.py` | S-20（`build_default_registry()` + `default_aggregation_config()` + `FakeHttpClient` + 既有 fixture HTML） |
| `test_p4_acceptance_safety.py` | S-10、S-11、S-15、S-21；SI-01..SI-22 的集中断言入口 |
| `test_p4_acceptance_retry.py` | S-13、S-14、S-16、S-17；L-12、L-13 |
| `test_p4_acceptance_diagnostics.py` | S-18；L-14；FX-5 canary |
| `test_p4_acceptance_determinism.py` | S-19、S-22 |
| `test_p4_acceptance_global_gate.py` | G-500（合同第 7.4 节全部冻结计数、断言与确定性重跑） |
| `test_p4_acceptance_mutations.py` | M-01..M-14（合同第 11 节），每个以 `pytest.raises(AcceptanceGateViolation)` 断言，并断言被替换绑定名恢复 |

S2 允许改动文件：

```text
A tests/phase4_acceptance/test_p4_acceptance_chain.py
A tests/phase4_acceptance/test_p4_acceptance_real_adapters.py
A tests/phase4_acceptance/test_p4_acceptance_safety.py
A tests/phase4_acceptance/test_p4_acceptance_retry.py
A tests/phase4_acceptance/test_p4_acceptance_diagnostics.py
A tests/phase4_acceptance/test_p4_acceptance_determinism.py
A tests/phase4_acceptance/test_p4_acceptance_global_gate.py
A tests/phase4_acceptance/test_p4_acceptance_mutations.py
M tests/phase4_acceptance/_harness.py      （只允许修复 S1 缺陷或追加 S2 需要的 harness 能力，不得改变 oracle 语义）
M tests/phase4_acceptance/_corpus.py       （同上）
M tests/phase4_acceptance/_oracles.py      （同上）
M tests/phase4_acceptance/test_p4_acceptance_harness.py
M tests/phase4_acceptance/test_p4_acceptance_architecture.py
```

S2 完成：继续 S3，不等待 Review，不创建 docs commit。

### S3 —— 回归 / 平台证据 / skip 对账 / Final HANDOFF

交付：

1. 在正式证据环境执行 G-T、G-P4、G-FULL（第 7.2 节），完成 skip nodeid 对账（合同第 8.3 节）。
2. 平台证据（第 8 节）：PC-01..PC-06 结果；PC-07 现状记录；PC-08 / PC-09 按可用性执行或记录为缺口。
3. mutation 恢复证明：`git hash-object --no-filters` 对 `src/**` 全部文件与 HEAD blob 逐一比较；`git status --porcelain` 为空。
4. `docs/review/P4_C10_HANDOFF.md`（合同第 17 节 Part I 全部——**含第 15 项失败路径记录**；Part II 除“Phase 4 = CLOSED”与 final closure coordinates 外的全部）。
5. 同一 commit 中同步合同第 20 节与本计划第 15 节状态行（仅状态）。
6. **S3 的三层状态字段**（合同第 16.1a / 16.1b、17 节；取代原单一 Acceptance verdict，禁止再写 `INCOMPLETE` 承担两种含义）。S3 HANDOFF 是 **candidate evidence snapshot**，
   必须分别写：
   * `P4-C10 Technical Acceptance Candidate Status`：`READY FOR LEVEL 1 REVIEW`（S3 证据收集完成、全部已知 technical gate 在 candidate evidence 中满足、无 OPEN F2 / F3 / F4）/
     `FAILED — F2 PRODUCTION FINDING(S)` / `BLOCKED — <F3 / F4 / U-GATE / ENVIRONMENT / OTHER AUTHORIZED REASON>`。`READY FOR LEVEL 1 REVIEW` **不是** PASS；
   * `P4-C10 Technical Acceptance Verdict : NOT ESTABLISHED` —— **S3 / 开发者不得写 PASS**（亦不得抢先写 FAIL / BLOCKED 的 reviewed 含义）；只有独立 Level 1 Review 才能建立；
   * `C10 Acceptance Head`（S3 candidate 提交，HANDOFF 自指记录）与 `Final Reviewed Acceptance Head : NOT ESTABLISHED`（Level 1 PASS 后由 Review Report 确立）；
   * `XD-A08` 状态、`Phase 4 Exit Authorization : BLOCKED — LEVEL 1 / EC-15 PENDING`（XD-A08 OPEN / OPEN F2 则一并列出）、`Phase 4 : NOT CLOSED`、`Phase 5 : NOT STARTED`。
   XD-A08 OPEN **不**改变 Candidate Status（仍可 `READY FOR LEVEL 1 REVIEW`）。EC-13（HANDOFF candidate evidence complete）在 Verdict = NOT ESTABLISHED 时即可满足，
   先于 EC-14。S3 之后不为“记录 Review 结果”而修改 S3 commit（合同第 16.1b 节）。
7. **F2 路径下的 S3**：若 S1-S3 中存在 OPEN F2，S3 在完成全部仍安全的证据收集后照常形成 C10 Acceptance Head 与 HANDOFF（Failed Acceptance Head），但 HANDOFF 与状态行必须写
   `Candidate Status : FAILED — F2 PRODUCTION FINDING(S)` / `Technical Acceptance Verdict : NOT ESTABLISHED` / `Final Reviewed Acceptance Head : NOT ESTABLISHED` /
   `Phase 4 Exit Authorization : BLOCKED — OPEN F2`（XD-A08 同时 OPEN 则一并列出）/ `Phase 4 : NOT CLOSED` / `Production repair : NOT PERFORMED`，
   不得写 Technical Acceptance PASS（合同第 13.1、16.1a 节）。随后独立 Level 1 Review **必须**判 `Verdict : FAIL`，再进入统一 C10-R1。
8. 若无法形成完整 S3 candidate：可写 `Candidate Status : BLOCKED — <reason>`；reviewed verdict 仍 `NOT ESTABLISHED`，直到独立 Review 真正发生。

S3 允许改动文件：

```text
A docs/review/P4_C10_HANDOFF.md
M docs/specifications/PHASE4_FINAL_ACCEPTANCE_CONTRACT.md   （仅第 20 节状态行，与 HANDOFF 同一 commit）
M docs/P4_C10_CONSTRUCTION_PLAN.md                          （仅第 15 节状态行，与 HANDOFF 同一 commit）
M tests/phase4_acceptance/**                                 （只允许修复 S1 / S2 测试缺陷，F1 类，记录于 HANDOFF）
```

S3 完成后：STOP，等待 P4-C10 Independent Level 1 Final Acceptance Review。

---

## 4. 精确的允许 / 禁止文件（冻结）

### 4.1 允许（整个 P4-C10，范围 = `<Design Accepted Head>..<C10 Acceptance Head>`）

```text
fc2-organizer/tests/phase4_acceptance/**                       （第 3 节逐 S 清单；不得出现清单外的文件）
fc2-organizer/docs/review/P4_C10_HANDOFF.md                    （S3 新增；Final Closure 时追加 closure 节）
fc2-organizer/docs/specifications/PHASE4_FINAL_ACCEPTANCE_CONTRACT.md   （仅第 20 节状态行）
fc2-organizer/docs/P4_C10_CONSTRUCTION_PLAN.md                 （仅第 15 节状态行）
```

### 4.2 禁止

```text
fc2-organizer/src/**                                           （任何改动 = 升级门 U-1，只能经第 12 节 C10-R1 生产路径）
fc2-organizer/tests/unit/**、tests/contract/**、tests/support/**、tests/fixtures/**   （只读复用 support / fixtures）
fc2-organizer/tests/README.md
fc2-organizer/pyproject.toml、fc2-organizer/CLAUDE.md、fc2-organizer/docs/PROJECT_GOVERNANCE_ACCELERATION.md
fc2-organizer/docs/specifications/**（本合同第 20 节状态行除外）
fc2-organizer/docs/P4_C7_CONSTRUCTION_PLAN.md、P4_C8_CONSTRUCTION_PLAN.md、P4_C9_CONSTRUCTION_PLAN.md
fc2-organizer/docs/review/**（P4_C10_HANDOFF.md 除外）
fc2-organizer/docs/prompts/**、docs/acceptance/**、docs/sources/**、docs/source-probes/**
fc2-organizer/upstream/**、fc2-organizer/tools/**、fc2-organizer/scripts/**
任何 Phase 5 文件 / 目录
```

不新增第三方依赖；不新增任何写文件、访问网络或持久化的**生产**代码（P4-C10 没有生产代码）。

### 4.3 仓库内访问规则（读 / 改，冻结；与合同第 3.4 节逐条一致，Design-R1 新增）

* **只读允许**：`src/**`（import 被验收 production）、`docs/**`（authority 检查）、`tests/support/**`、`tests/fixtures/**`（FX-6 / S-20 加载 `tests/fixtures/sources/**`）、
  `pyproject.toml`、Git metadata / history。第 4.2 节“禁止”列表里的 `tests/support/**`、`tests/fixtures/**` 等条目指**禁止修改**，不禁止只读复用。
* **修改只允许在可丢弃验收根内**：pytest `tmp_path`，或 harness 登记且位于 `tmp_path` 之下的可丢弃验收根；合同第 12.3 节经 Owner 授权的原生跨卷目录是唯一例外，
  且处置不变（无授权 = NOT RUN / accepted evidence gap，XD-B04，不阻塞 Phase 4 Closure）。
* **STOP-05 只针对修改**：需要对可丢弃验收根之外的路径执行修改性操作、需要真实用户媒体 / 真实 production library / 现存个人目录充当 fixture、或某个
  blocking acceptance 只有 tmp_path 之外的真实数据才能成立时才 STOP。只读访问仓库内文件**不**触发 STOP-05 / U-2。

---

## 5. Acceptance Harness 策略

### 5.1 组装原则

* **真实下层、离线替身只在网络边界**：被验收的 Phase 4 / Phase 3 代码全部是真实实现；只有两个网络边界使用替身——source 层的
  `SourceAdapter`（脚本化，或真实 adapter + `FakeHttpClient` + 既有 fixture HTML）与图片层的 `httpx.MockTransport`（注入真实
  `HttpxImageClient`）。
* **oracle 独立**：期望值来自 `_corpus.py` 的用例定义与被引用合同的冻结规则，门函数由 `_oracles.py` 独立实现，不 import `tests/unit/**`。
* **可丢弃**：每个场景在自己的 `tmp_path` 中建立 `downloads/`（脏下载目录）与 `library/`（library root），sandbox guard 对**修改**全程生效；仓库内
  fixture / support 只读加载（第 4.3 节）。

### 5.2 组件

| 组件 | 构造 | 用途 |
|---|---|---|
| 脚本化 source 引擎 | `SourceRegistry` + `support.scripted_adapters.scripted_adapter_class(source_id, script)`（source id `fc2db_net`、`javdb`、`av123`，满足 P4-C9 安全 id 规则）+ `AggregationConfig`（三源、固定优先级）+ `MultiSourceEngine(config, registry, FakeHttpClient())` | S-01..S-17、S-21、S-22、G-500：真实执行 / 重试 / 合并 / 状态判定 |
| 真实 adapter 引擎 | `build_default_registry()` + `default_aggregation_config()` + `MultiSourceEngine(..., FakeHttpClient)`，`FakeHttpClient` 按既有 adapter 测试使用的 URL 形态注册 `tests/fixtures/sources/**` HTML | S-20 |
| 图片 transport | `HttpxImageClient(transport=httpx.MockTransport(handler))`；handler 按 URL 路由：200 + 合成 JPEG（字节由 URL 确定性推导）、404、302 到私有地址、错误 Content-Type、非法 JPEG；记录每个实际发出的请求与在途数 | 全部图片场景、G-500 |
| orchestrator | `BatchOrchestrator(engine, image_client, str(library_root), config=OrchestrationConfig(...))` | 全部场景 |
| 故障注入 | 按条目源路径 / 目标路径匹配、一次性、断言已触发；只用合同第 12.6 节授权接缝 | S-11..S-16、S-21、G-500 |
| 写操作观察 | 只观察、call-through 的 `_FS` 属性与 `open` / `io.open` / `os.open` 写模式包装 | SI-15、SI-19 |
| 并发观测 | 脚本化 adapter（engine 在途条目）、MockTransport handler（图片在途）、`execute_filesystem` 包装（执行在途）；门控事件用于 S-19 反转完成顺序与 S-22 峰值达到上限 | SI-06、SI-07 |
| socket 陷阱 | `socket.socket` / `socket.create_connection` / `socket.getaddrinfo` 在场景期间抛 `AcceptanceGateViolation` | SI-20 |

`HttpxImageClient` 的生命周期由测试拥有（`async with`）；orchestrator 不构造、不关闭 client（P4-C8 §7.2）。

### 5.3 运行时间预算

G-500 两次完整运行（第二次用于确定性）在正式证据环境中预计与 P4-C8 S6 门槛同一量级（约 2-4 分钟）；G-T 整体应在 10 分钟内完成。
超出时只允许优化测试实现（例如减少重复快照），不得减少冻结的计数、场景或断言。

---

## 6. 场景执行顺序

S2 内的实现与 checkpoint 顺序（由依赖决定）：

```text
1. S-01（最小成功链，验证 harness 全部组件联通）
2. S-02..S-08、S-12（单条目链路变体）
3. S-09、S-10、S-11、S-21（阻断 / 冲突 / 文件系统安全）
4. S-13、S-14、S-15、S-16（执行故障与延后）
5. S-17（重试链与合并）
6. S-18（诊断，覆盖 1-5 的代表形态）
7. S-19、S-22（确定性与并发）
8. S-20（真实 adapter）
9. G-500
10. M-01..M-14（每个 mutant 复用上面已通过的场景作为 positive control）
```

运行时（pytest）不依赖文件间顺序：每个测试自建 fixture，结果与收集顺序无关（合同第 12.7 节）。

---

## 7. 命令（冻结；均在 `fc2-organizer/` 下执行）

### 7.1 Authority 与漂移核对（S1；输出写入 HANDOFF）

```text
git rev-parse HEAD
git rev-parse origin/claude/phase4-c9-diagnostics                         # 必须为 c293ed75…
git merge-base --is-ancestor <每个合同第 4.1 节 SHA> HEAD                  # 全部为真
git diff --name-only <P4-Cn Final Reviewed Code Head> HEAD -- src/fc2_organizer/<package>   # 九个 package 均为空
git diff --name-only 1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f HEAD -- src/fc2_metadata_core   # 为空
git diff 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d HEAD -- CLAUDE.md docs/PROJECT_GOVERNANCE_ACCELERATION.md pyproject.toml   # 为空
```

并逐一引用九个 HANDOFF 的最终状态行（`P4-Cn: CLOSED` / `P4-Cn = CLOSED`）。

### 7.2 测试门

```text
基线（S1，Design Accepted Head，正式证据环境）
  python -m pytest -q -p no:cacheprovider -rs --basetemp=<JOB_TMP>/c10-base-full --junitxml=<JOB_TMP>/c10-base-full.xml

G-T
  python -m pytest tests/phase4_acceptance -q -p no:cacheprovider --basetemp=<JOB_TMP>/c10-gt-<run> --junitxml=<JOB_TMP>/c10-gt-<run>.xml
G-P4
  python -m pytest tests/contract tests/unit/discovery tests/unit/planning tests/unit/publication tests/unit/nfo tests/unit/images tests/unit/materialization tests/unit/execution tests/unit/orchestration tests/unit/diagnostics -q -p no:cacheprovider --basetemp=<JOB_TMP>/c10-gp4-<run> --junitxml=<JOB_TMP>/c10-gp4-<run>.xml
G-FULL
  python -m pytest -q -p no:cacheprovider -rs --basetemp=<JOB_TMP>/c10-full-<run> --junitxml=<JOB_TMP>/c10-full-<run>.xml
```

通过规则、cache / basetemp / skip / 瞬时失败政策以合同第 8 节为准。证据运行禁止 `--lf` / `--ff` / `-x` / `--maxfail` / `-k` / `--deselect`。

### 7.3 diff scope 与整洁性

```text
git diff --stat <Design Accepted Head> HEAD
git diff --name-only <Design Accepted Head> HEAD -- src                 # 必须为空
git diff --name-only <Design Accepted Head> HEAD -- tests               # 只含 tests/phase4_acceptance/**
git diff --check <Design Accepted Head> HEAD                            # 干净
git status --porcelain                                                  # 为空（既有约定的未跟踪 .claude/ 除外）
```

---

## 8. 平台证据计划

| 项 | 计划 |
|---|---|
| 正式环境记录 | `python -VV`、`platform.platform()`、`sys.getwindowsversion()`、`httpx.__version__`、`pytest --version`、basetemp 所在卷、symlink 权限可用性（以既有 skip 原因为准）、`FC2_EXECUTION_CROSS_VOLUME_ROOT` 是否设置 |
| PC-01..PC-06 | 由 G-T（含 C10 架构测试）、G-P4、G-FULL 与 S-09 / S-12 / S-13 / S-21 给出 |
| PC-07 | 从 G-FULL 的 JUnit XML 提取 XD-B01..XD-B07 相关测试的实际状态（执行 / skip + 原因），写入 HANDOFF |
| PC-08 | 默认**不执行**（处置不变：无 Owner 授权 = NOT RUN / accepted evidence gap，XD-B04，不阻塞 Phase 4 Closure）。只有所有者对专门新建、初始为空、仅供本轮验收、路径明确的目录给出明确授权并满足合同第 12.3 节全部条件时，设置环境变量后重跑 G-FULL；记录 k 与父目录前后列举。禁止扫描现有第二卷个人文件、复用现存个人目录、自动选择其它盘目录 |
| PC-09 | 主机若有 Python 3.11.x：运行 G-T 与 G-P4；若有 POSIX 主机：运行 G-T（Windows 原生断言按合同第 8.1 节平台门控）。不可用则记录为 XD-B02 / XD-B08 证据缺口，不伪造 |

不得为获取平台证据而提权、启用 Developer Mode、修改组策略或关闭任何安全功能（CLAUDE.md）。

---

## 9. Mutation / Non-Vacuity 计划

* 实现：`test_p4_acceptance_mutations.py` 中每个 mutant 一个（或一组参数化）测试：用 `monkeypatch` 在合同第 11.3 节允许的表面植入缺陷，
  运行对应场景的最小形态，断言 `pytest.raises(AcceptanceGateViolation)`；测试末尾断言被替换的绑定名已恢复为原对象（`is`）。
* positive control：同一场景在不植入 mutant 时通过（由 S2 对应场景测试与 mutation 文件内的对照用例共同证明）。
* 门函数层面的正 / 负向对照在 `test_p4_acceptance_harness.py`（S1）。
* 可选：像 P4-C9 那样对生产源码做单点文本替换并在内存中编译一次性模块；若使用，目标文本必须在源码中恰出现一次，否则测试显式失败，
  绝不写盘。
* HANDOFF 记录：每个 mutant 的表面、杀死它的门、失败用例名、失败数；S3 的 `git hash-object --no-filters` 逐文件恢复证明。

---

## 10. HANDOFF 证据要求

`docs/review/P4_C10_HANDOFF.md` 必须满足合同第 17 节全部条目（Part I 1-15、Part II 1-6；Part II 7 与“Phase 4 = CLOSED”只在 Final Closure Docs
中写入）。HANDOFF **不得只有成功路径**：第 15 项失败路径记录（XD-A08 状态；F2 findings；F2 之后收集的安全证据；被 F2 阻塞的场景；Production repair；
三层状态字段（Candidate Status / Verdict / Phase Exit）；F3 / F4 / U 门 STOP 记录）无内容时必须明确写 `NONE`。另外必须：

* 如实记录任何瞬时失败、环境问题（F0）与 C10 自身测试缺陷修复（F1）的经过与重跑结果；
* 逐项回答升级门 U-1..U-7 是否触发；
* 明确写出 `Production Modified : NO`（或附 CLOSED package amendment record）；
* 写出 XD-A08（C5-R1-L1）当前状态；OPEN 时写 `XD-A08 : OPEN` 与 `Phase 4 Exit Authorization : BLOCKED — LEVEL 1 / EC-15 PENDING；XD-A08`，**不**改变 Candidate Status
  （全部技术门在 candidate evidence 中满足时仍为 `READY FOR LEVEL 1 REVIEW`；不得写 `INCOMPLETE`）；
* HANDOFF 是 candidate evidence snapshot：`Technical Acceptance Verdict : NOT ESTABLISHED`、`Final Reviewed Acceptance Head : NOT ESTABLISHED`（EC-13 在此状态即可满足）；
  **开发者不得写 `Technical Acceptance Verdict : PASS`**；
* 不自我宣布 Review PASS、reviewed verdict、P4-C10 CLOSED 或 Phase 4 CLOSED。

---

## 11. Independent Review Plan

```text
1. P4-C10 INDEPENDENT DESIGN / CONTRACT / CONSTRUCTION PLAN REVIEW（Original Design Candidate 17c194a…）                -> FAIL
     （P4-C10-DESIGN-R-01 / R-02 / R-03）
   P4-C10 DESIGN-R1 INCREMENTAL INDEPENDENT DESIGN CLOSURE REVIEW（Design-R1 / R1a Candidate 18e6e54…）
     -> R-01 / R-02 / R-03 CLOSED；发现 P4-C10-DESIGN-R1-01（XD-A08 / EC-10 / EC-14 / EC-15 排序循环）
   P4-C10 DESIGN-R2 INCREMENTAL INDEPENDENT DESIGN CLOSURE REVIEW（Design-R2 Candidate c284108…）
     -> R1-01 CLOSED；发现 P4-C10-DESIGN-R2-01（S3 candidate 与 reviewed verdict 的生命周期）
   P4-C10 DESIGN-R3 INCREMENTAL INDEPENDENT DESIGN CLOSURE REVIEW（Design-R3 Candidate）
     PASS -> Design Accepted Head = Design-R3 Candidate；Frozen Contract / Construction Plan = Design-R3 Candidate；之后才允许进入 S1
             （唯一 authority transition；不创建 design closure docs）
     FAIL -> 再一轮设计修订（authority docs，一次闭合全部 design findings），再次增量 Design Review
2. S1 -> S2 -> S3 连续施工（不单独 Review，不创建 S 级 docs）
     正常路径：S1 -> S2 -> S3 -> Level 1
       S3：Candidate Status = READY FOR LEVEL 1 REVIEW；Technical Acceptance Verdict = NOT ESTABLISHED；Final Reviewed Acceptance Head = NOT ESTABLISHED；
           Phase 4 Exit Authorization = BLOCKED — LEVEL 1 / EC-15 PENDING；Phase 4 NOT CLOSED；Phase 5 NOT STARTED（S3 不得写 PASS）
     F2 路径（合同第 13.1 节）：S1 / S2 / S3 中发现 F2 -> 不修复 -> 记录 -> 继续收集仍安全的证据 -> S3 形成 Failed Acceptance Head
                              （Candidate Status = FAILED — F2 PRODUCTION FINDING(S)；Verdict = NOT ESTABLISHED）->
                              Level 1（Verdict = FAIL，必须）-> 一个统一 C10-R1；不为每个 F2 设立 Review
     F3 / F4 / 真正 U 门：立即 STOP C10 执行，authority first（无法形成完整 candidate 时 Candidate Status = BLOCKED — <reason>；Verdict 仍 NOT ESTABLISHED）
3. P4-C10 INDEPENDENT LEVEL 1 FINAL ACCEPTANCE REVIEW
     Review Range = <Design Accepted Head>..<C10 Acceptance Head>
     Reviewer 必须在正式证据环境（Windows 11 / Python 3.12.x）独立重跑 G-T、G-P4、G-FULL，并抽查 mutation 与 G-500；
     并核对 S3 HANDOFF 的 Candidate Status / Verdict 字段符合合同第 16.1a 节（S3 HANDOFF 若写了 `Technical Acceptance Verdict : PASS` 则本身是 finding）
     Reviewer 是 reviewed verdict 的**唯一**建立者，必须**分别**给出（合同第 16.5 节）：
       P4-C10 Technical Acceptance Verdict : PASS / FAIL / BLOCKED
       Final Reviewed Acceptance Head      : <C10 Acceptance Head SHA>（仅 PASS）/ NOT ESTABLISHED（FAIL / BLOCKED）
       Phase 4 Exit Authorization          : AUTHORIZED / BLOCKED（Level 1 阶段只能给 BLOCKED，因为 EC-15 尚未发生）
     authority carrier（合同第 16.1b 节）：S3 HANDOFF = candidate evidence snapshot（不改写）；Independent Level 1 Review Report = reviewed verdict authority；
       Phase 4 Final Closure Docs = 把 reviewed verdict 与 Final Reviewed Acceptance Head 记录为 closure history（经 EC-15 复查）。Reviewer 不修改 S3 commit；
       不为纯状态创建“Review 后状态 docs commit -> docs review”循环（治理文档第 11.1 节）。
     Verdict PASS -> Final Reviewed Acceptance Head = C10 Acceptance Head；EC-14 satisfied（**与 XD-A08 是否 OPEN 无关**）
       -> 第 13 节 Phase 4 Final Closure 路径；若 XD-A08 OPEN：Phase 4 Exit Authorization = BLOCKED — XD-A08；Phase 4 NOT CLOSED；Phase 5 NOT STARTED
     Verdict FAIL -> 第 12 节 C10-R1（存在 OPEN F2 时 PASS 不可达，Reviewer 必须判 FAIL 并确认全部已知 findings；Final Reviewed Acceptance Head 保持 NOT ESTABLISHED）
     Verdict BLOCKED -> F3 / F4 / 真正 U 门：authority first（Final Reviewed Acceptance Head 保持 NOT ESTABLISHED）
4. PHASE 4 FINAL CLOSURE DOCS-ONLY REVIEW（EC-15；独立）
     职责：建立 Phase 4 → Phase 5 输入边界与 Phase 5 Frozen Base Candidate，并**显式承担 XD-A08 authority disposition review**
     （authority source、disposition legitimacy、Ledger change、Phase 4 Exit Criteria；不得只审格式 / 状态；合同第 16.4 节）
     PASS -> XD-A08 CLOSED -> EC-10 / EC-15 satisfied -> Phase 4 Exit Authorization = AUTHORIZED；Phase 4 = CLOSED；
             Phase 4 Final Closure Docs Head = Phase 5 Frozen Base Candidate
     若 definition 显示 C5-R1-L1 实际要求 Phase 4 内 production repair / safety work / contract change / 额外 acceptance evidence：
             不得简单 PASS；Phase 4 Closure 保持 BLOCKED；按 F2 / F3 / F4 / F5 或 authority amendment 处理；受影响的 Technical Acceptance 证据须重做并重新 Review
     FAIL -> 修订 closure docs 后再次 docs-only Review
```

Per-S Independent Review：**NO**。C-Level Independent Review：**YES**。Design Authority Review：**YES**。
Phase 4 Final Closure Docs Review：**YES**（它改变下一阶段输入语义与 Frozen Base，治理文档第 11.2 节不可压缩）。

---

## 12. C10-R1 路径

* 触发：Level 1 Final Acceptance Review FAIL（含 F2 路径下的 Failed Acceptance Head）。
* 分类：按合同第 13 节（F1..F6）。
* 统一 R1：同根因 / 范围明确、不需要新架构设计或 Contract authority 的全部 findings（含实施期记录的全部 F2 与 Level 1 findings）进入**一个** C10-R1，
  一次闭合并检查 direct regression。C10-R1 必须重新执行合同第 13.1 节中 `NOT RUN / BLOCKED BY F2` 的 blocking 场景。不得为每个 F2 单独 Review。
* 只改测试 / docs 的 C10-R1：允许文件 = `tests/phase4_acceptance/**` + `docs/review/P4_C10_HANDOFF.md`（追加 R1 节）+ 合同第 20 节 / 本计划
  第 15 节状态行；Risk Class B；增量 Level 1 Review。
* 含 CLOSED package 生产改动的 C10-R1（F2；生产修复**只可能**发生在这里，触发 U-1）：Risk Class 升级为 C；必须记录 affected CLOSED package、affected Frozen Contract、
  为什么必须修改、regression scope、compatibility impact、safety impact（合同第 14 节第 2、3 条）；允许文件另加被修复 package
  的 `src/**`（精确列出）与针对该缺陷的回归测试——回归测试只允许新增在 `tests/phase4_acceptance/**`（不修改 CLOSED package 既有测试）；
  回归范围 = 受影响 package 全部测试 + G-T + G-P4 + G-FULL；独立 Review 必须显式审计 CLOSED package 改动。
* 需要 authority 的 finding（F3 / F4）：立即 STOP C10 执行，先完成 authority 修订与独立复查，之后才允许 C10-R1；不得当作普通 failed acceptance 继续。
* C10-R1 不得加入任何新功能（合同第 1.3 节）。

---

## 13. Phase 4 Final Closure 路径

路径次序（合同第 16.4 节，冻结；**不存在循环**：Technical Acceptance 先于 Phase Exit，EC-14 先于 EC-10 / EC-15）：

```text
S3 HANDOFF（candidate evidence snapshot：Candidate Status = READY FOR LEVEL 1 REVIEW；Verdict / Final Reviewed Acceptance Head = NOT ESTABLISHED）
  -> Technical Acceptance Verdict = PASS（由 Level 1 Review Report 建立）-> Final Reviewed Acceptance Head；EC-14 satisfied
  -> 若 XD-A08 OPEN：Phase 4 Exit Authorization = BLOCKED — XD-A08；Phase 4 NOT CLOSED；Phase 5 NOT STARTED
  -> 取得 C5-R1-L1 的可审计 authority
  -> 在 Phase 4 Final Closure Docs（authority docs）中写入 XD-A08 disposition（Ledger 修订）
  -> EC-15 Docs-Only Review（显式承担 XD-A08 authority disposition review）
  -> PASS：XD-A08 CLOSED、EC-10 / EC-15 satisfied、Exit AUTHORIZED、Phase 4 CLOSED、Phase 5 Frozen Base Candidate 建立
```

0. 前置：存在由独立 Level 1 Review Report 建立的 `Technical Acceptance Verdict : PASS` 与 Final Reviewed Acceptance Head（EC-14）；不存在任何 OPEN 的 F2 / F3 / F4。**XD-A08 在写入 Final Closure Docs 之前可以仍是 OPEN**：本步骤取得其可审计
   authority（合同第 10.1 节 Required closure：exact source、exact SHA / 文档、finding definition、severity、deadline、scope、disposition authority），
   disposition 在第 2 步的 Final Closure Docs 中首次写入，并由第 3 步 EC-15 Review 审查。XD-A08 = OPEN 时**不得**写入 `Phase 4 = CLOSED`（EC-15 PASS 之前一律不得写）。
   若取得的 definition 显示 C5-R1-L1 要求 Phase 4 内 production repair / safety work / contract change / 额外 acceptance evidence：**不得创建“关闭”性质的
   Final Closure Docs**，按 F2 / F3 / F4 / F5 或 authority amendment 处理（合同第 16.4 节）。
1. EC-14 满足（Technical Acceptance 经 Level 1 Final Acceptance Review PASS）。EC-14 先于 EC-10 / EC-15。
2. 创建一个 docs-only 的 **Phase 4 Final Closure Docs** 提交：
   * `docs/review/P4_C10_HANDOFF.md` 追加“P4-C10 最终闭合 / Phase 4 最终闭合”节（快照声明——声明 S3 HANDOFF 是 candidate evidence snapshot、其 `Verdict : NOT ESTABLISHED`
     不被改写；记录由 Level 1 Review Report 建立的 reviewed `Technical Acceptance Verdict` 与 Final Reviewed Acceptance Head 作为 closure history；Review 历史、
     合同第 17 节 Part II 第 7 项 final closure coordinates、`P4-C10 : CLOSED`、`Phase 4 : CLOSED — EFFECTIVE UPON PHASE 4 FINAL CLOSURE DOCS-ONLY REVIEW PASS`）；
   * 若 XD-A08 尚未关闭：在合同第 10 节写入 XD-A08 disposition 的 Ledger 修订（新 ID 承接，不重用 XD-C14；不得借机修改其它 Ledger 项分类），并附 authority source。
   * 合同第 20 节、本计划第 15 节状态行同步（仅状态）。
   * 不修改任何其它文件（包括 `CLAUDE.md`、治理文档、P4-C1..P4-C9 文档）。
3. 独立 Phase 4 Final Closure Docs-Only Review（EC-15）：必须同时验证 XD-A08 authority source、disposition legitimacy、Ledger change 与 Phase 4 Exit Criteria
   （EC-01、EC-10 及对 EC-14 的承接）。PASS 之后 XD-A08 CLOSED、`Phase 4 = CLOSED` 生效；该提交成为 Phase 5 Frozen Base Candidate。
   在该 Review PASS 之前：XD-A08 = OPEN、Phase 4 = NOT CLOSED、Phase 5 = NOT STARTED。
4. 不开始 Phase 5。

---

## 14. STOP 条件（冻结）

出现以下 STOP-01..STOP-10 任何一项，立即停止 C10 执行，在状态说明 / HANDOFF 中记录证据，等待治理裁决：

```text
STOP-01  第 7.1 节任一核对失败（坐标不是祖先、src 漂移、某 package 状态不是 CLOSED、C9 远端 head 不等于 c293ed75…）
STOP-02  升级门 U-1..U-7 任一**真正**触发（U-1 = CLOSED package src/** 被实际修改；U-2 见 STOP-05；S1-S3 中发现 F2 本身不触发 U-1，走 STOP-03 / F2 流程）
STOP-03  发现 F3（需要 authority 的生产缺陷）或 F4（合同冲突）：立即 STOP，authority first，不得当作普通 failed acceptance 继续。
         （F2 **不**在此列——F2 走合同第 13.1 节 F2 流程，见下方“F2 流程（非 STOP）”）
STOP-04  需要修改第 4.2 节任一禁止文件
STOP-05  需要对可丢弃验收根（合同第 3.4.2 节）之外的路径执行**修改性**操作；或真实用户媒体 / 真实 production library / 现存个人目录被当作 fixture；
         或某个 blocking acceptance 只有 tmp_path 之外的真实数据才能成立（合同第 12.3 节经 Owner 授权的可选原生跨卷目录在其全部条件满足时除外）。
         只读访问仓库内 `src/**`、`docs/**`、`tests/support/**`、`tests/fixtures/**`、`pyproject.toml`、Git metadata 不触发 STOP-05（第 4.3 节）
STOP-06  基线测量出现 failed / errors 且无法归类为 F0 / F6
STOP-07  合同或本计划之间、或与任何 CLOSED 合同之间出现语义冲突
STOP-08  需要新增依赖或修改 pyproject.toml
STOP-09  需要 Owner 的业务决策（Owner Question Gate），且该决策阻塞 Exit Criteria
STOP-10  S3 完成（正常停止点：等待 Level 1 Final Acceptance Review；F2 路径下为 Failed Acceptance Head 之后）
```

**F2 流程（非 STOP，合同第 13.1 节；冻结）**：

```text
F2 discovered during S1 / S2 / S3
  -> STOP PRODUCTION REPAIR（禁止修复；禁止修改 affected CLOSED package）
  -> MARK ACCEPTANCE FAILING（记录 P4-C10-F2-<NN>；Phase 4 Closure 暂时不可达）
  -> CONTINUE SAFE EVIDENCE COLLECTION（可丢弃边界内；不改 production；无 authority amendment；无其它真正 U 门）
  -> 被缺陷路径直接阻塞的场景：NOT RUN / BLOCKED BY F2 <id>（须证明直接依赖；否则必须照常执行）
  -> Failed Acceptance Head（S3；Candidate Status : FAILED — F2 PRODUCTION FINDING(S)；Technical Acceptance Verdict : NOT ESTABLISHED；Phase 4 Exit Authorization : BLOCKED — OPEN F2；Production repair : NOT PERFORMED）
  -> Independent Level 1 Review（PASS 不可达 -> Verdict = FAIL，必须）
  -> 一个统一 C10-R1（第 12 节）
```

若继续收集证据会越出可丢弃边界、对真实数据产生 source-loss 风险、需要 production repair、需要 authority amendment、需要新安全设计，或触发其它真正的 U 门，
则该 F2 流程在该点终止并按 STOP-02 / STOP-03 / STOP-05 处理。

---

## 15. 状态

S1 / S2 / S3 施工期间本节未更新；整个 C10 implementation 完成后随 HANDOFF 一次同步（本次同步）。

```text
P4-C1 .. P4-C9                 : CLOSED
P4-C10 Frozen Base             : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c
Governance Authority           : 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Original Design Candidate      : 17c194a71f0292e323591b8849ac65b9e14f7779 —— Independent Design Review：FAIL
Design-R1 Candidate            : 5dc80fdebb467f38a852c4501c32ba65c6dd153f（Design-R1a：18e6e54fc6ba016a5a5e1b0b262b7a5e23210792）
P4-C10-DESIGN-R-01 / R-02 / R-03 : CLOSED（经独立 DESIGN-R1 Closure Review 确认）
Design-R2 Candidate            : c284108c6f4e542e8d5e574bafa8e0815681957c（亦为 Design-R3 Base）
P4-C10-DESIGN-R1-01            : CLOSED（经独立 DESIGN-R2 Incremental Closure Review 确认）
P4-C10-DESIGN-R2-01            : CLOSED（经独立 DESIGN-R3 Incremental Closure Review 确认；据任务指令记录）
P4-C10 Design                  : ACCEPTED @ fc59e2020e4df237bf3bed83a07950d67c19b475（Independent Design-R3 Closure Review PASS）
Frozen Contract                : ACCEPTED @ fc59e2020e4df237bf3bed83a07950d67c19b475
Construction Plan              : ACCEPTED @ fc59e2020e4df237bf3bed83a07950d67c19b475（本文件）
Design Accepted Head           : fc59e2020e4df237bf3bed83a07950d67c19b475
S1 / S2 / S3                   : COMPLETED（S1 f9f95567b9f6ea243e7587219404b1e258023233；S2 eeac4e420202031944d3d0ca8dd405c469b93537；S3 = C10 Acceptance Head）
P4-C10 Implementation          : S3 CANDIDATE SUBMITTED —— WAITING FOR INDEPENDENT LEVEL 1 FINAL ACCEPTANCE REVIEW
P4-C10 Technical Acceptance Candidate Status : BLOCKED — ENVIRONMENT（正式证据环境 Windows 11 / Python 3.12.x 证据未取得；详见 docs/review/P4_C10_HANDOFF.md）
P4-C10 Technical Acceptance Verdict          : NOT ESTABLISHED
C10 Acceptance Head            : 本提交（git log -1 --format=%H -- fc2-organizer/docs/review/P4_C10_HANDOFF.md）
Final Reviewed Acceptance Head : NOT ESTABLISHED
XD-A08（C5-R1-L1）             : OPEN —— UNRESOLVED AUTHORITY DEBT（阻塞 Phase 4 Exit / Closure；不阻塞 Technical Acceptance）
Phase 4 Exit Authorization     : BLOCKED — LEVEL 1 / EC-15 PENDING；XD-A08；正式环境证据未取得
Production Modified            : NO
Production repair              : NOT PERFORMED
P4-C10                         : NOT CLOSED
Phase 4                        : NOT CLOSED
Phase 5                        : NOT STARTED
```

S3 提交之后 **STOP**：不创建 Review 后状态提交、不建立 Final Reviewed Acceptance Head、不关闭 XD-A08、不开始 EC-15、不开始 Phase 5；
下一步是 P4-C10 INDEPENDENT LEVEL 1 FINAL ACCEPTANCE REVIEW。

---

## 16. Design 静态自审（提交前确认；Design-R1 同步）

| # | 自审项 | 结论 | 依据 |
|---|---|---|---|
| 1 | P4-C10 是不是只做 Final Acceptance？ | PASS | 合同第 1.2 节；本计划第 3、4 节只允许测试与 docs |
| 2 | 有没有偷偷新增功能？ | PASS | 合同第 1.3 节 NO FEATURE EXPANSION；第 4.2 节禁止 `src/**`；Production Change = NONE |
| 3 | 有没有重新定义 CLOSED package semantics？ | PASS | 合同开头 authority 优先级；第 6 节只引用原条款；引用不一致即 finding |
| 4 | 所有 Phase 4 package 是否有 authority 坐标？ | PASS | 合同第 4.1 节九行全部 Frozen Base / Final Reviewed Head / Final Closure Docs Head；设计阶段已核对祖先关系与 `src` 零漂移 |
| 5 | 所有历史 Deferred / Evidence Gap 是否有 disposition？ | PASS | 合同第 10 节：A 类 8（XD-A01..A08）、B 类 17（XD-B01..B17）、C 类 15（XD-C01..C13、C15、C16；XD-C14 已移出且不重用）与第 10.4 节。定义不在仓库内的 F3 / F5 按原裁决（Phase 4 非阻塞、Phase 5 入口阻塞）；C5-R1-L1 因无 authority 不能被判 non-blocking，改为 XD-A08（OPEN、阻塞 Phase 4 Closure） |
| 6 | Phase 4 Exit Criteria 是否明确？ | PASS | 合同第 16 节 EC-01..EC-15，全部 Blocking |
| 7 | 真实 filesystem 测试是否只使用 disposable fixtures？ | PASS | 合同第 12.2 节 + sandbox guard + C10 架构测试；唯一例外第 12.3 节为可选、需所有者明确授权、只经既有测试 |
| 8 | production defect 被发现后的治理路径是否明确？ | PASS | 合同第 13-15 节；本计划第 12、14 节 |
| 9 | Risk Class 是否显式裁决？ | PASS | 合同第 3 节（B，含为何非 A / 非 C 与升级门）；本计划头部与第 2 节 |
| 10 | 是否存在 TBD / TODO？ | PASS | 合同与本计划无 TBD / TODO / 以后再定；全部计数、场景期望、命令、门规则已冻结 |
| 11 | 是否定义 Windows / platform evidence？ | PASS | 合同第 9、12.1 节；本计划第 8 节 |
| 12 | 是否定义 regression + skip baseline？ | PASS | 合同第 8 节（三层门、nodeid 对账、瞬时失败规则）；本计划第 7.2 节 |
| 13 | 是否定义 non-vacuity？ | PASS | 合同第 11 节 M-01..M-14 与允许表面；本计划第 9 节 |
| 14 | 是否定义最终 HANDOFF？ | PASS | 合同第 17 节；本计划第 10、13 节 |
| 15 | 是否明确 P5 不在本 C 实施？ | PASS | 合同第 1.4、18 节；本计划第 4.2、13、15 节 |
| 16 | 是否只有一个 C、无机械拆分、无 C 内中间 Review？ | PASS | 本计划第 1 节；合同第 3.3 节 |
| 17 | Frozen Base / Planning Parent / Governance Authority 是否与 Frozen Authority 一致？ | PASS | 合同第 2.1 节；未发现冲突 |
| 18 | （Design-R1 / R-01）未决 authority 债务是否没有被无 authority 地归为 non-blocking？Ledger 计数与全文是否一致？ | PASS | C5-R1-L1 = XD-A08（A 类、OPEN、阻塞）；A = 8 / B = 17 / C = 15；XD-C14 不重用；EC-10、合同第 17 / 18.3 节、DF-04、本计划头部 / 第 13 / 15 节同步；设计阶段已核对：该 ID 在 Phase 3 收口基线上不存在，仓库内最早出现于 `00dc40d…` 的延续清单，无定义 |
| 19 | （Design-R1 / R-02）全文是否不再同时存在“仓库 fixture 可只读”与“tmp_path 之外任何访问立即 STOP”？ | PASS | 合同第 3.4 节（只读允许 / 可丢弃修改 / FORBIDDEN）为唯一权威；U-2、第 12.2 / 12.4 节、FX-6、STOP-05、本计划第 4.3 / 5.1 节对齐；原生跨卷例外与处置不变 |
| 20 | （Design-R1 / R-03）实施期 F2 是否有出口、不产生每个 F2 一次 Review、且不放宽 production repair 治理、F3 / F4 仍立即 STOP？ | PASS | 合同第 13.1 节；本计划第 3、11、12、14 节；C10-R1 才触发 U-1 并升级为 C 类；HANDOFF 含失败路径记录（合同第 17 节 Part I 第 15 项） |
| 21 | Design-R1 是否只改三个 finding 直接相关内容，未改动 Risk Class B、G-500、L / SI / S / PC / M 矩阵语义、F3 / F5、原生跨卷处置、DF-07、EC-15？ | PASS | 合同 / 计划 diff 仅涉及上述章节与引用 / 状态同步 |
| 22 | （Design-R2 / R1-01）是否消除了 XD-A08 / EC-10 / EC-14 / EC-15 的排序循环？Technical Acceptance 与 Phase Exit 是否分成两个裁决？ | PASS | 合同第 16 节重写：EC-02..EC-09、EC-11..EC-14 = Technical Acceptance gate；EC-01 / EC-10 / EC-15 = Phase Exit gate；EC-14 先于 EC-10 / EC-15；XD-A08 OPEN 允许 Technical Acceptance PASS 但 Exit BLOCKED；本计划第 3、10、11、13、14、15 节同步 |
| 23 | （Design-R2）Technical Acceptance 的技术强度是否未降低？OPEN F2 / F3 / F4 是否仍阻止 PASS？ | PASS | 合同第 16.2 节沿用 EC-02..EC-09、EC-11..EC-13 全部原定义并要求无 OPEN F2 / F3 / F4；第 16.4 节严格区分 XD-A08 OPEN 与 F2 OPEN；F2 流程与 F3 / F4 立即 STOP 未改 |
| 24 | （Design-R2）EC-15 是否仍独立、并显式承担 XD-A08 authority disposition review，且真实技术 obligation 不能被 docs disposition 关闭？ | PASS | 合同第 16.4 节：审查 authority source / legitimacy / Ledger change / Exit Criteria；definition 显示需要 repair / safety work / contract change / 额外证据则 Review 不得简单 PASS，Closure 保持 BLOCKED，受影响 Technical 证据须重做 |
| 25 | （Design-R2）是否不再残留“XD-A08 OPEN => Technical Acceptance 不可 PASS”或“Technical Acceptance PASS => Phase 4 自动 CLOSED”？ | PASS | 合同第 16.6 节禁止两种写法；全文搜索已核对（`INCOMPLETE` 仅出现在“禁止再用”的说明中） |
| 26 | （Design-R3 / R2-01）“S3 完成、Level 1 未发生”是否有合法 pre-review 状态？Candidate Status 是否与 reviewed verdict 分成两套字段、不复用 PASS / FAIL / BLOCKED？ | PASS | 合同第 16.1a 节：Candidate Status（READY FOR LEVEL 1 REVIEW / FAILED — F2 PRODUCTION FINDING(S) / BLOCKED — \<reason\>）；Verdict 取 NOT ESTABLISHED / PASS / FAIL / BLOCKED；生命周期表覆盖 S3 前、S3 后、F2、无法形成 candidate、Level 1 PASS / FAIL / BLOCKED、EC-15 |
| 27 | （Design-R3）S3 / 开发者是否被禁止写 `Technical Acceptance Verdict : PASS` 与 Final Reviewed Acceptance Head？EC-13 是否可在 Verdict = NOT ESTABLISHED 时满足并先于 EC-14？ | PASS | 合同第 16.1a / 16.2（EC-13 = candidate evidence complete）/ 16.6 / 17 节；本计划 S3 第 6 / 7 / 8 项与第 10 节 |
| 28 | （Design-R3）reviewed verdict 的 authority carrier 是否冻结且不制造纯状态 review loop？Reviewer 是否不需要修改 S3 commit？ | PASS | 合同第 16.1b 节：S3 HANDOFF = candidate evidence snapshot；Level 1 Review Report = reviewed verdict authority；Final Closure Docs = closure history（经 EC-15）；符合治理文档第 11.1 节 |
| 29 | （Design-R3）F2 路径是否未被削弱？Failed Acceptance Head 上 Verdict 是否 NOT ESTABLISHED、Level 1 是否必须判 FAIL？ | PASS | 合同第 13.1 / 16.1a 节；Level 1 FAIL / BLOCKED 时 Final Reviewed Acceptance Head 保持 NOT ESTABLISHED；F3 / F4 仍立即 STOP |
