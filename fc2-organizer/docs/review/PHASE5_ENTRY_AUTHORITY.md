# PHASE 5 ENTRY AUTHORITY —— F3 / F5 Owner Authority Ratification（R1 Candidate）

```text
文档性质           : Phase 5 Entry Authority（仅 docs；Owner Authority Ratification R1 Candidate）
Package            : Phase 5 Entry Blocker XD-B11（F3 / F5）
Phase 4 Frozen Base: 8f12bb695784af7a9696d401a292dbbded2c9d05
Governance Authority: 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d（Acceleration v2 有效）
Branch             : claude/phase5-entry-planning
R1 Base            : a139ee8a158bd2fe694b2fceadffb312f42f99fc（上一版 Authority Candidate，独立 Review 结论 FAIL）
```

## 当前状态（CURRENT）

```text
F3 Authority                 : OWNER-RATIFIED R1 — INDEPENDENT REVIEW REQUIRED
F5 Authority                 : OWNER-RATIFIED R1 — INDEPENDENT REVIEW REQUIRED
F3                           : OPEN
F5                           : OPEN
XD-B11                       : OPEN
Phase 5 Entry Gate           : FAIL — AUTHORITY REVIEW + CLOSURE REQUIRED
Phase 5                      : NOT STARTED
Next                         : PHASE 5 ENTRY F3/F5 OWNER AUTHORITY R1 INCREMENTAL INDEPENDENT DOCS-ONLY CLOSURE REVIEW

上一轮 Review findings（均需独立复核后才可关闭；本文件不自行写 CLOSED）:
P5-ENTRY-AUTH-R-01 : REMEDIATED — INDEPENDENT REVIEW REQUIRED   （F5 历史事实修正，见 §5）
P5-ENTRY-AUTH-R-02 : REMEDIATED — INDEPENDENT REVIEW REQUIRED   （F3 historical identity 与同型副本，见 §4）
P5-ENTRY-AUTH-R-03 : REMEDIATED — INDEPENDENT REVIEW REQUIRED   （§18.3 original-definition authority 取代条款，见 §3A）
```

在独立 Review PASS 之前：**F3/F5 Authority：NOT ACCEPTED。**

本文件不声明 F3 CLOSED、F5 CLOSED、XD-B11 CLOSED、Entry Gate PASS 或 P5-C1 STARTED。

## 1. Phase 4 Frozen Base

Phase 4 Final Closure Docs Head 为 `8f12bb695784af7a9696d401a292dbbded2c9d05`：EC-15 PASS、Phase 4 Exit AUTHORIZED、P4-C10 CLOSED、Phase 4 CLOSED。该 SHA 是 Phase 5 Frozen Base Candidate。Phase 4 不得重新打开或修改（但见 §4.4 对三个 Phase 4 contract test 文件的 TEST-ONLY 兼容性授权，该授权不构成 Phase 4 production 行为或 contract 语义变更）。

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

### 3A. §18.3 Original-Definition Authority 的取代条款（P5-ENTRY-AUTH-R-03）

Frozen Phase 4 Final Contract §18.3 原文要求：Phase 5 planner 必须先取得 F3 / F5 的 original definitions。事实：original Phase 0/1 independent review reports **NOT RECOVERED**。

Owner 裁决：本 Owner Authority Ratification，**在经独立 Authority Review PASS 后**，作为 **CURRENT GOVERNANCE AUTHORITY**，取代 Phase 5 Entry Closure 所需、但无法恢复的 original-definition authority。

限定：

```text
- 不声称 original report 已被恢复（DOES NOT claim original report was recovered）。
- 不改写历史 provenance（DOES NOT rewrite historical provenance）。
- 不降低 Phase 5 ENTRY BLOCKER 语义（DOES NOT lower Phase 5 ENTRY BLOCKER semantics）。
- 在独立 Review PASS 之前：F3/F5 Authority = NOT ACCEPTED，本取代条款不生效。
```

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

本节严格区分两个概念：**Original F3 Finding Identity**（历史事实，不得伪造）与 **Current Phase 5 Entry Closure Scope**（Owner 当前裁决）。

### 4.1 Original F3 Finding Identity（历史事实）

唯一的 original historical test：

```text
fc2-organizer/tests/contract/test_core_independent_of_amane.py
::
test_amane_is_not_actually_installed_in_this_test_environment
```

```text
Origin commit            : 1e2f4d753aad9050a79589776abda74f2e063e7b（Phase 1 reviewed head）
Line @ 1e2f4d7           : def L124；pytest.raises(ModuleNotFoundError) L128；importlib.import_module("amane") L129
Line @ a139ee8 (R1 base) : def L237；pytest.raises(ModuleNotFoundError) L241；importlib.import_module("amane") L242
git blame（上述三行）@ a139ee8 : 均为 1e2f4d753aad9050a79589776abda74f2e063e7b
```

Original F3 **只**指上述 Phase 1 test。本文件不声称 original F3 一开始就包括任何 Phase 4 tests。

Definition：该测试依赖“当前测试环境中 Amane 不可 import”这一环境状态来证明架构独立性。当 Amane 实际已安装 / 可 import 时，该测试会 false fail，即使 `fc2_metadata_core` 本身仍完全不依赖 Amane。

成为 Phase 5 入口阻塞项的原因不是 production defect，而是 Phase 5 将实际安装 / import Amane，从而直接触发该错误环境假设。

### 4.2 Phase 4 同型副本（P5-ENTRY-AUTH-R-02，已机械确认）

同一错误环境假设后来被复制进三个 Phase 4 contract test 文件。四处均为同名 test `test_amane_is_not_actually_installed_in_this_test_environment`，断言形态同为 `pytest.raises(ModuleNotFoundError)` + `importlib.import_module("amane")`。以下行号为 R1 base a139ee8 当前行号，introducing commit 来自 `git blame`（def / raises / import 三行一致）：

```text
# | File（fc2-organizer/tests/contract/）  | Package | def | raises / import | Introducing commit
1 | test_core_independent_of_amane.py       | Phase 1 | 237 | 241 / 242       | 1e2f4d753aad9050a79589776abda74f2e063e7b（original F3）
2 | test_discovery_architecture.py          | P4-C1   | 160 | 162 / 163       | ffe49927760f57d3ea0179cde22f2c19c8dd10a9
3 | test_planning_architecture.py           | P4-C2   | 189 | 191 / 192       | 1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8
4 | test_publication_architecture.py        | P4-C3   | 166 | 167 / 168       | 1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f
```

各文件中，该 test 之外还有基于 `sys.meta_path` blocker 的动态测试与 static AST import guards；这些才是真实的架构 invariant 证据，必须保留。

### 4.3 Current Phase 5 Entry Closure Scope（Owner R1 裁决）

项目 Owner 正式扩大**当前 closure implementation scope**：

```text
F3 ENTRY CLOSURE SCOPE = 4 mechanically equivalent environment-dependent architecture tests
  1. Phase 1 core independence test      (test_core_independent_of_amane.py)
  2. P4-C1 discovery architecture copy   (test_discovery_architecture.py)
  3. P4-C2 planning architecture copy    (test_planning_architecture.py)
  4. P4-C3 publication architecture copy (test_publication_architecture.py)
```

理由：四者都依赖 `pytest.raises(ModuleNotFoundError)` + `importlib.import_module("amane")` 来证明“Amane 没安装”。Phase 5 安装 Amane 后，四者都会因同一环境假设而 false fail。只修 Phase 1 original test 无法真正满足 Phase 5 Entry Gate。

这是 CURRENT OWNER CLOSURE AUTHORITY，不是对 original F3 identity 的改写（§4.1 不变）。

### 4.4 对 CLOSED Phase 4 Tests 的修改授权

Owner 明确授权将来的 F3 test-only closure 修改上述 3 个 Phase 4 contract test files（§4.2 的 #2 / #3 / #4）。这是：

```text
TEST-ONLY COMPATIBILITY CLOSURE
不是 Phase 4 production behavior change
不是 Phase 4 contract semantic reopening
```

允许范围仅限：移除 / 替代“Amane 必须不可 import”这一环境依赖 assertion；同时必须保留真实 frozen invariant——对应 package / `fc2_metadata_core` 不依赖、不 import Amane。

不得：削弱 static AST import guards；删除真实 architecture boundary assertions；修改 package import direction；修改 `src/**`；改变 Phase 4 production semantics。

### 4.5 Closure Requirement 与 Mechanism Authority

四个测试都必须改造成 environment-independent：**即使真实 Amane 已经安装，测试仍必须证明被测 package / core 本身不会依赖或 import Amane。**

将来的 closure executor 可使用：environment-independent import blocking、`meta_path` finder、monkeypatch、module isolation、controlled import interception，或其它等价机制。

禁止通过以下方式“修复”：跳过测试；xfail；检测到 Amane installed 后直接 return；要求卸载 Amane。

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

本节严格区分 **Original F5 historical observation** 与 **Current F5 Entry Closure Scope**，二者不是同一个概念。

### 5.1 Original F5 Historical Observation（P5-ENTRY-AUTH-R-01 更正）

```text
F5 arose against the Phase 1 reviewed head
1e2f4d753aad9050a79589776abda74f2e063e7b,
where ONE pytest.raises(Exception) occurrence existed:
  fc2-organizer/tests/unit/core/test_source_result.py:292
  (git blame: 1e2f4d753aad9050a79589776abda74f2e063e7b)

Five additional Phase-1-owned occurrences were subsequently introduced by
Phase 1 R1  051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8
("fix(core): close Phase 1 metadata contract invariants").
```

上一版关于 F5 原始 occurrence 数量的表述与历史不符，已删除并以本节替换。机械核对：`git grep -n -F "pytest.raises(Exception)" 1e2f4d7 -- fc2-organizer/tests` 仅得 1 处。

### 5.2 Current F5 Entry Closure Scope（Owner R1 裁决）

这是 CURRENT OWNER CLOSURE AUTHORITY，**不是**对 original F5 scope 的主张。

```text
F5 Closure Scope Anchor : e6472f948f885c52e6f4c62cf29383e9dcd3d4e3
                          （"docs(review): add Phase 1 R2 handoff"；HEAD 的 ancestor）
F5 ENTRY CLOSURE SCOPE  : Phase 1 final closed tree e6472f9 中属于 Phase 1 tests 的全部
                          pytest.raises(Exception) occurrences
TOTAL                   : 6
```

Anchor 理由：e6472f9 是 Phase 1 最终 closure lineage 中明确继续把 F5 标记为 deferred 的 closed tree；Phase 5 entry closure 针对该 Phase 1 closed state，完整关闭其所有 Phase-1-owned broad assertions。**不得把 HEAD 当前 tree 当作 F5 scope anchor。**

### 5.3 六处机械清单

来源：`git grep -n -F "pytest.raises(Exception)" e6472f9 -- fc2-organizer/tests/unit/core`（全部命中即这 6 处，均位于 `test_metadata.py` / `test_source_result.py`），introducing commit 来自 `git blame`（在 e6472f9 tree 上）：

```text
# | File（fc2-organizer/tests/unit/core/） | Line @e6472f9 | Enclosing test | Introducing commit
1 | test_metadata.py      | 341 | TestImmutability::test_scalar_attribute_assignment_is_rejected | 051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8
2 | test_source_result.py | 292 | TestSourceResultIsImmutable::test_fields_cannot_be_reassigned  | 1e2f4d753aad9050a79589776abda74f2e063e7b（original occurrence）
3 | test_source_result.py | 364 | test_scalar_mutation_attempt_fails_and_invariant_survives      | 051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8
4 | test_source_result.py | 420 | test_result_metadata_attribute_itself_cannot_be_reassigned     | 051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8
5 | test_source_result.py | 445 | TestPartialFailureLifetimeInvariant::test_partial_metadata_cannot_be_mutated_into_minimum_success | 051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8
6 | test_source_result.py | 466 | TestCallerOwnedAliasSafetyThroughSourceResult::test_mutating_original_metadata_instance_reference_cannot_succeed | 051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8

test_metadata      : 1
test_source_result : 5
TOTAL              : 6   （1 个 original occurrence 来自 1e2f4d7 + 5 个 Phase 1 R1 occurrence 来自 051d6c9）
```

核对：这 6 处在 R1 base a139ee8 中的行号与 e6472f9 相同（341 / 292 / 364 / 420 / 445 / 466），blame 同上。行号随 anchor tree 记录；将来 closure executor 以 e6472f9 anchor 的 enclosing test 为准，不得仅凭行号定位。

### 5.4 排除的其它 14 处（OUT OF F5 ENTRY CLOSURE SCOPE）

排除 authority：**F5 current closure scope 由 Owner 明确冻结为 Phase 1 final closed tree e6472f9 中的 Phase-1-owned occurrences。** 不再使用“因为它们晚于 finding 出现所以排除”作为规则（该规则同样会误排 Phase 1 R1 新增的 5 处）。

R1 base a139ee8 中其余 14 处（`git grep -n -F "pytest.raises(Exception)" HEAD -- fc2-organizer/tests` 共 20 处，减去 §5.3 的 6 处）：

```text
#  | File（fc2-organizer/tests/unit/）                 | Line | Introducing commit                       | Owning package / phase
1  | aggregation/test_agg_config.py                    | 95   | 26917af196517b2d90f480f9eded8636fdbcfecc | Phase 3 C1（aggregation）
2  | aggregation/test_agg_config.py                    | 228  | 26917af196517b2d90f480f9eded8636fdbcfecc | Phase 3 C1（aggregation）
3  | aggregation/test_agg_merge.py                     | 337  | 26917af196517b2d90f480f9eded8636fdbcfecc | Phase 3 C1（aggregation）
4  | aggregation/test_agg_merge.py                     | 339  | 26917af196517b2d90f480f9eded8636fdbcfecc | Phase 3 C1（aggregation）
5  | aggregation/test_agg_merge.py                     | 341  | 26917af196517b2d90f480f9eded8636fdbcfecc | Phase 3 C1（aggregation）
6  | diagnostics/test_diagnostics_redaction.py         | 155  | 891161774d0ecc521dadec7ee198b58120a3ade8 | Phase 4 P4-C9（diagnostics）
7  | diagnostics/test_diagnostics_redaction.py         | 198  | 891161774d0ecc521dadec7ee198b58120a3ade8 | Phase 4 P4-C9（diagnostics）
8  | diagnostics/test_diagnostics_redaction.py         | 205  | 891161774d0ecc521dadec7ee198b58120a3ade8 | Phase 4 P4-C9（diagnostics）
9  | discovery/test_discovery_models.py                | 33   | ffe49927760f57d3ea0179cde22f2c19c8dd10a9 | Phase 4 P4-C1（discovery）
10 | discovery/test_discovery_models.py                | 86   | ffe49927760f57d3ea0179cde22f2c19c8dd10a9 | Phase 4 P4-C1（discovery）
11 | discovery/test_discovery_models.py                | 119  | ffe49927760f57d3ea0179cde22f2c19c8dd10a9 | Phase 4 P4-C1（discovery）
12 | discovery/test_discovery_policy.py                | 61   | ffe49927760f57d3ea0179cde22f2c19c8dd10a9 | Phase 4 P4-C1（discovery）
13 | materialization/test_materialization_failures.py  | 365  | b088db8acb2c4ae47037d58546000c41543b73b1 | Phase 4 P4-C6（materialization）
14 | resource_control/test_rc_breaker_execution.py     | 529  | fb4dddaf4ef00ed201c94d9a7e29d1e86a20f17d | Phase 3 C5（resource control）
```

这 14 处在 F5 closure 期间：**ZERO DIFF**。它们将来是否改善，由各自 package authority 独立判断，不得借 F5 修改。

### 5.5 Closure Requirement

对 §5.3 的 6 处，替换为 the narrowest source-supported expected exception type：

1. 不得修改 production code 来配合测试。
2. 不得换成另一个同样宽泛的 BaseException / Exception subclass umbrella，除非该 exact broad type 就是冻结 public behavior 且有现有 authority 明确支持。
3. 根据当前 frozen implementation 与对应 test intent 逐项确定真正预期的 exception type。
4. 不同测试真实预期不同时逐项使用正确类型，不得虚构共同异常。
5. narrowing 后 test behavior semantics 必须不变。
6. §5.4 的 14 处：ZERO DIFF。

F5 closure 仍为 **TEST-ONLY**。

## 6. Closure Scope / Forbidden Scope

允许（将来的 TEST-ONLY closure task，须待本 authority 经独立 Review PASS 后才可创建）：

```text
F3 : §4.3 的 4 个 tests（含 3 个 Phase 4 contract test files，§4.4 授权，仅限 test-only 兼容性修改）及直接必要的 test-only support
F5 : §5.3 的 6 处 Phase-1-owned occurrences（anchor e6472f9）
```

禁止：production behavior change、core API change、Amane integration design change；`src/**` 任何修改；修改 §5.4 的 14 处 `pytest.raises(Exception)`；削弱 static AST import guards 或真实 architecture boundary assertions；skip / xfail / “检测到 Amane 已安装即 return” / 要求卸载 Amane；修改 Phase 4 Final Closure docs 或 P4-C1..P4-C10 frozen docs；实现 Amane adapter；开始 P5-C1；创建 P5-C1 Contract / Construction Plan。

本轮（authority docs R1 轮）仅修改本文件，不修改 `src/**`、`tests/**`、Phase 4 docs、`pyproject.toml`、`CLAUDE.md`、`PROJECT_GOVERNANCE_ACCELERATION.md`。即使 implementation scope 已清晰，本轮也不实施 closure。

## 7. Deadline

继承 Frozen Phase 4 Contract 第 18.3 节：在 F3 / F5 完成合法 closure 并经独立 Entry Closure Review PASS 之前，不得开始 P5-C1 implementation。

## 8. Lifecycle

```text
1. 本文件（Owner Authority Ratification R1 Candidate）                   : 当前
2. 独立 F3/F5 Owner Authority R1 Incremental Docs-Only Closure Review      : 待进行
3. 通过后才可创建 F3/F5 ENTRY BLOCKER TEST-ONLY CLOSURE TASK               : 未创建
4. Entry Closure Review                                                    : 未开始
5. Phase 5 Entry Gate                                                      : FAIL，直至上述全部完成
```
