# PHASE 5 ENTRY AUTHORITY —— F3 / F5 Owner Authority Ratification Candidate

```text
文档性质           : Phase 5 Entry Authority（仅 docs；Owner Authority Ratification Candidate）
Package            : Phase 5 Entry Blocker XD-B11（F3 / F5）
Phase 4 Frozen Base: 8f12bb695784af7a9696d401a292dbbded2c9d05
Governance Authority: 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d（Acceleration v2 有效）
Branch             : claude/phase5-entry-planning
```

## 当前状态（CURRENT）

```text
F3 Authority                 : RATIFIED BY OWNER — INDEPENDENT AUTHORITY REVIEW REQUIRED
F5 Authority                 : RATIFIED BY OWNER — INDEPENDENT AUTHORITY REVIEW REQUIRED
F3                           : OPEN
F5                           : OPEN
XD-B11                       : OPEN
Phase 5 Entry Gate           : FAIL — AUTHORITY REVIEW + CLOSURE REQUIRED
Phase 5                      : NOT STARTED
Next                         : PHASE 5 ENTRY F3/F5 OWNER AUTHORITY RATIFICATION INDEPENDENT DOCS-ONLY REVIEW
```

本文件不声明 F3 CLOSED、F5 CLOSED、XD-B11 CLOSED 或 Entry Gate PASS。

## 1. Phase 4 Frozen Base

Phase 4 Final Closure Docs Head 为 `8f12bb695784af7a9696d401a292dbbded2c9d05`：EC-15 PASS、Phase 4 Exit AUTHORIZED、P4-C10 CLOSED、Phase 4 CLOSED。该 SHA 是 Phase 5 Frozen Base Candidate。Phase 4 不得重新打开或修改。

Authority priority：Frozen Contract > Frozen Construction Plan > Project Governance > Task Prompt。

## 2. XD-B11

Frozen Phase 4 Final Contract 第 18.3 节与 XD-B11 条目：F3 / F5 是 Phase 5 ENTRY BLOCKER，在 P5-C1 开工前必须关闭。本 ratification 不降低也不扩大该 blocking semantics。

历史 carry-forward 曾写作“必须最迟在 Phase 5 集成之前关闭”（`PHASE1_R1_HANDOFF.md`、`PHASE3_ENTRY_C0_HANDOFF.md`）。该措辞弱于冻结合同的 ENTRY BLOCKER。Owner 裁决：继续服从 Frozen Contract 的 ENTRY BLOCKER 语义，不得降级为“可先实施 P5-C1 再关闭”。

## 3. 来源 Provenance（必须区分）

**Historical restatement source（历史转述来源）**

```text
Path        : C:\Users\Ctg\.claude\projects\C--Users-Ctg-Projects-ffcc\0a332397-7312-4be9-9a48-9866c5483077.jsonl
Session ID  : 0a332397-7312-4be9-9a48-9866c5483077
SHA-256     : cafacad7c47e1110b3960a3fd8d5ba5d44a93f40410b7b310285f3374a8d9d8b
Size        : 1115093 bytes
Owner historical definition message SHA-256 : d60ed13a292b9434caacaca028581863fe5e211b4f8552e8e91f857b1e950d76
```

该来源是 Phase 2 L2 Review prompt 中 Owner 对 F3 / F5 的历史转述（restatement）。它**不是** original Phase 0/1 reviewer report。

**Original Phase 0/1 review report : NOT RECOVERED。** 仓库内所有 F3 / F5 出现处只有 carry-forward / cross-reference，没有完整 original definition。不再继续搜索。

**Current Owner ratification authority（当前 Owner 裁决）**：本文件记录项目 Owner 直接给出的 governance authority，正式补足 definition、severity、scope、closure requirement 与 Phase 5 blocking semantics。它不声称自己是 original Phase 0/1 review。

上一轮调查 session 写入 Claude memory 的一条 reference，**不是** authority source，不得作为 F3 / F5 的 evidence。本次 authority 仅依赖 repo history、上述外部 JSONL 来源与 Owner ratification。

## 4. F3 —— Owner Ratified Authority

```text
Finding ID            : F3
Severity              : MEDIUM
Historical status     : DEFERRED，对更早 Phase non-blocking
Phase 5 status        : ENTRY BLOCKER
Closure Nature        : TEST-ONLY
Production Obligation : NONE
Safety Obligation     : NONE
```

Definition：

```text
test_amane_is_not_actually_installed_in_this_test_environment

该测试依赖“当前测试环境中 Amane 不可 import”这一环境状态来证明架构独立性。
当 Amane 实际已安装 / 可 import 时，该测试会 false fail，
即使 fc2_metadata_core 本身仍完全不依赖 Amane。
```

成为 Phase 5 入口阻塞项的原因不是 production defect，而是 Phase 5 将实际安装 / import Amane，从而直接触发该测试的错误环境假设。

Scope：仅限该 specific historical test 及直接必要的 test-only support。

Closure Requirement：该测试必须改造成 environment-independent，并继续证明真正的 invariant——`fc2_metadata_core` 不依赖 / 不 import Amane——而不是证明“Amane 恰好未安装”。允许 test-only isolation、mock / monkeypatch / import interception 或其它等价测试机制，前提是：不降低原 architecture invariant、不要求卸载 Amane、不修改 production code。

## 5. F5 —— Owner Ratified Authority

```text
Finding ID            : F5
Severity              : LOW
Historical status     : DEFERRED，对更早 Phase non-blocking
Phase 5 status        : ENTRY BLOCKER
Closure Nature        : TEST-ONLY
Production Obligation : NONE
```

Definition：历史 Phase 1 tests 中使用的 `pytest.raises(Exception)` 异常断言过宽，可能让错误的异常类型也被测试接受。

**Scope 冻结为 F5 产生时已存在的 6 处 `pytest.raises(Exception)`**（上一轮机械历史核对结果）：

```text
test_metadata      : 1 处
test_source_result : 5 处
TOTAL              : 6
```

当前 HEAD 全仓库另外存在的 14 处 `pytest.raises(Exception)` 来自之后 Phase 3 / Phase 4 的 CLOSED work，**不属于 F5**，不得因字符串相同而追溯扩大 F5 scope；它们将来是否改善，由各自 package authority 独立判断，不能借 F5 修改。

Closure Requirement：对上述 6 处，替换为 the narrowest source-supported expected exception type：

1. 不得修改 production code 来配合测试。
2. 不得换成另一个同样宽泛的 BaseException / Exception subclass umbrella，除非该 exact broad type 就是冻结 public behavior 且有现有 authority 明确支持。
3. 根据当前 frozen implementation 与对应 test intent 逐项确定真正预期的 exception type。
4. 不同测试真实预期不同时逐项使用正确类型，不得虚构共同异常。
5. narrowing 后 test behavior semantics 必须不变。
6. 后来的 14 处：ZERO DIFF。

## 6. Closure Scope / Forbidden Scope

允许（将来的 TEST-ONLY closure task，须待本 authority 经独立 Review PASS 后才可创建）：仅 F3 的 specific test 及直接必要的 test-only support；仅 F5 的 6 处 historical occurrences。

禁止：production behavior change、core API change、Amane integration design change；修改后来的 14 处 `pytest.raises(Exception)`；修改 Phase 4 Final Closure docs 或 P4-C1..P4-C10 frozen docs；实现 Amane adapter；开始 P5-C1；创建 P5-C1 Contract / Construction Plan。

本轮（authority docs 轮）不修改 `src/**`、`tests/**`、`pyproject.toml`、`CLAUDE.md`、`PROJECT_GOVERNANCE_ACCELERATION.md`。

## 7. Deadline

继承 Frozen Phase 4 Contract 第 18.3 节：在 F3 / F5 完成合法 closure 并经独立 Entry Closure Review PASS 之前，不得开始 P5-C1 implementation。

## 8. Lifecycle

```text
1. 本文件（Owner Authority Ratification Candidate）            : 当前
2. 独立 F3/F5 Owner Authority Ratification Docs-Only Review     : 待进行
3. 通过后才可创建 F3/F5 ENTRY BLOCKER TEST-ONLY CLOSURE TASK    : 未创建
4. Entry Closure Review                                         : 未开始
5. Phase 5 Entry Gate                                           : FAIL，直至上述全部完成
```
