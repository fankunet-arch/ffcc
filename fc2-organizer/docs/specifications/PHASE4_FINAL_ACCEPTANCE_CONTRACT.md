# FC2 Organizer -- Phase 4 / P4-C10 Phase 4 最终验收合同（Phase 4 Final Acceptance Contract）

```text
文档状态              : DESIGN CANDIDATE —— INDEPENDENT DESIGN / CONTRACT / CONSTRUCTION PLAN REVIEW REQUIRED
Package               : P4-C10 Phase 4 Final Acceptance（不新增任何生产 package）
Package Frozen Base   : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c（P4-C9 Final Closure Docs Head）
Planning Parent       : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c
Governance Authority  : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Branch                : claude/phase4-c10-final-acceptance（自 c293ed75… 创建）
施工计划              : docs/P4_C10_CONSTRUCTION_PLAN.md
Risk Class            : B（第 3 节；带强制升级门）
P4-C10 Implementation : NOT STARTED
Phase 4               : NOT CLOSED
```

本合同与施工计划一起，一次性冻结 P4-C10 的全部验收语义。Design Review PASS 之前，本文件只是 Design Candidate；
PASS 之后才成为 Frozen Contract。之后对本文件唯一允许的改动是第 20 节状态行；任何语义改动都是 authority 修订，
必须 STOP 并经独立复查（治理文档第 11.2 节）。

Authority 优先级（冻结，治理文档第 4 节）：

```text
P4-C1..P4-C9 Frozen Contracts（各自合同对其 package 语义优先）
> 本合同（只对 Phase 4 最终验收的范围、证据与退出条件有效）
> P4-C10 Frozen Construction Plan
> docs/PROJECT_GOVERNANCE_ACCELERATION.md
> Task Prompt
```

本合同**不得**重新定义任何 CLOSED package 的语义。凡本合同引用某个已冻结规则之处，以被引用合同的原文为准；
引用文字与原文不一致时，以原文为准，且该不一致本身构成 P4-C10 finding。

---

## 1. Scope / Non-Scope

### 1.1 P4-C10 回答的问题

```text
已经 CLOSED 的 P4-C1 .. P4-C9，作为一个整体系统，
是否满足 Phase 4 Exit Criteria（第 16 节），从而可以宣布 Phase 4 = CLOSED？
```

### 1.2 Scope（做）

1. Phase 4 Package Authority Matrix 的建立与机器核对（第 4 节）。
2. Cross-Package Integration Gate：以**真实**下层实现组成的完整链路验证（第 5 节）。
3. Phase 4 Safety Gate：把已冻结的安全不变量做成统一验收门（第 6 节）。
4. Acceptance Scenario Matrix 与 Phase 4 跨 package 500-item 全局门槛 G-500（第 7 节；G-500 由 P4-C8 合同第 3、37 节
   明确划归 P4-C10）。
5. 三层回归门（第 8 节）与 skip 基线逐项对账。
6. Platform / Compatibility Gate 与平台证据处置（第 9 节）。
7. Phase 4 Exit Debt Ledger（第 10 节）。
8. Non-Vacuity / Mutation 门（第 11 节）。
9. Phase 4 Final HANDOFF（第 17 节）与 Phase 4 → Phase 5 输入边界（第 18 节）。
10. Phase 4 Closure 判定路径（第 16 节）。

P4-C10 的全部新增代码只允许是**测试代码**（`tests/phase4_acceptance/**`，见施工计划第 4 节）与 docs。

### 1.3 NO FEATURE EXPANSION（冻结）

P4-C10 **不得**新增、扩展或改变任何生产能力。明确禁止（不穷尽）：

```text
新 metadata source / 新 scraper / 新 adapter
新图片策略（缩放、转码、选择、缓存、DNS 防御）
新 NFO schema / 新 NFO 字段
新 planning capability / 新命名策略
新 execution behavior / 新 overwrite 或 collision 策略
新 retry behavior / 新 RetryKind
新 diagnostics schema / 新诊断字段 / 新路径策略
新 persistence（文件、数据库、cache、resume store）
新 reporting feature / CLI / UI / 进度流
新 API / 新 public export / 新 workflow
Amane adapter 或任何 Phase 5 内容
```

任何真正的新功能都不属于 P4-C10，应进入后续 Phase（第 18 节）。为“验收更完整”而顺手加入的任何生产改动都是
越权，构成 BLOCKING finding。

### 1.4 Non-Scope（不做）

* 不修改 `src/**`（默认）；CLOSED package 生产缺陷只按第 14、15 节处理。
* 不修改任何既有测试（`tests/unit/**`、`tests/contract/**`、`tests/support/**`、`tests/fixtures/**`）。
* 不修改任何 P4-C1..P4-C9 合同、施工计划、HANDOFF；不修改 `CLAUDE.md`、治理文档、`pyproject.toml`、`upstream/**`、
  `tools/**`。
* 不访问网络；不操作任何真实用户数据（第 12.2 节）。
* 不重跑 Phase 3 50-ID 线上门槛，不做线上 source 可用性探测（属于 Phase 2 / Phase 6 / Phase 8）。
* 不设计、不实现 P5-C1 或任何 Phase 5 代码。

---

## 2. Authority / Frozen Base

### 2.1 坐标（冻结）

```text
Repo                       : https://github.com/fankunet-arch/ffcc.git
P4-C10 Package Frozen Base : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c   P4-C9 Final Closure Docs Head（P4-C9 = CLOSED）
Planning Parent            : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c
Governance Authority       : 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d   Acceleration Governance v2 accepted head
```

设计阶段核对结果（可复现，命令见施工计划第 7.1 节）：

* `origin/claude/phase4-c9-diagnostics == c293ed75…`；本分支自该 SHA 创建，未修改 C9 分支历史。
* `3b9d39e…` 是 `c293ed75…` 的祖先；`git diff 3b9d39e… c293ed75… -- CLAUDE.md docs/PROJECT_GOVERNANCE_ACCELERATION.md pyproject.toml`
  为空：治理权威自其 accepted head 起未变。P4-C9 Frozen Construction Plan 第 10 节记录 `Acceleration Governance v2 : ACCEPTED / CLOSED`、
  Governance Authority = `3b9d39e…`。治理文档文件头仍写着“R1 IMPLEMENTED — INDEPENDENT GOVERNANCE REVIEW REQUIRED”，这是该文件头
  未在 PASS 后同步的历史文字；它与 P4-C9 冻结记录不冲突，P4-C10 **不**修改治理文档（设计发现 DF-07，非阻塞）。
* 第 4.1 节全部 P4-C1..P4-C9 坐标均为 `c293ed75…` 的祖先。
* 九个 package 的 `src/fc2_organizer/<package>/**` 自各自 Final Reviewed Code Head 起到 `c293ed75…` **零差异**；
  `src/fc2_metadata_core/**` 自 P4-C3 Final Reviewed Code Head `1e66ab4…` 起零差异；`src/fc2_organizer/__init__.py` 最后修改于 P4-C2。
  因此 Frozen Base 上的生产代码 = 各 package 被独立复查 PASS 的生产代码。

未发现与本坐标冲突的 Frozen Authority。

### 2.2 Phase 4 authority 链

```text
3edab6e (Phase 3 C5 closure) -> P4-C1 -> P4-C2 -> P4-C3 -> P4-C4 -> P4-C5 -> P4-C6
  -> DOCS-CN（80e3ec1 / 32be09f，Final a0a69c7：只把既有文档中文化，语义不变）
  -> P4-C7 -> P4-C8 -> Acceleration Governance v2（99254d9 / 3b9d39e） -> P4-C9 -> c293ed7（P4-C10 Frozen Base）
```

### 2.3 与早期“Phase 4 — 批量引擎”提示词的对账（冻结）

`docs/prompts/ClaudeCode_00_实施总提示词.md` 的 “Phase 4 — 批量引擎” 是项目早期的 Phase 4 定义；此后 Phase 4 被冻结为
P4-C1..P4-C10 的合同序列。按 authority 优先级，以 Frozen Contracts 为准；下表把早期条目映射到已冻结的实现与 P4-C10 证据，
任何不一致都进入第 10 节 Ledger，不静默忽略：

| 早期 Phase 4 条目 | 冻结 authority 中的落点 | P4-C10 证据 / 处置 |
|---|---|---|
| N 个号码 -> N 个独立 item | P4-C8 `BatchOrchestrator`（条目身份 = index，第 12 节） | S-17、G-500 账目门 |
| 单片失败不影响其它 | P4-C8 第 20 节；P4-C7 单影片执行器 | S-15、G-500（GK/GH/GI） |
| 只 retry failed | P4-C8 第 25-26 节 `preview_retry` / `merge_retry` | S-13、S-14、S-16、S-17、G-500 g1-g4 |
| 断点 / cache | 进程内 checkpoint（P4-C7 第 14 节）；durable 断点 / cache 被 P4-C7 第 34 节、P4-C8 第 33 节冻结为 v1.0 非目标 | 进程内部分：S-13；durable 部分：XD-C01 |
| bounded concurrency / 不允许无界并发 | P4-C8 第 19 节；Phase 3 `BatchScheduler` | S-22、G-500 峰值门、M-11 |
| batch summary | P4-C8 第 28 节 `PreviewSummary` / `ExecutionSummary` / `BatchOutcome` | G-500 恒等式门 |
| 每个 item 的 source outcomes | P4-C9 `SourceDiagnostics` | S-03、S-18 |
| 取消尚未开始的 item | P4-C8 第 27 节 `CANCELLED` | S-16 |
| 状态 pending / running / success / partial / failed / cancelled | P4-C8 第 11.2、11.4 节映射（PENDING / RUNNING 为瞬时、不物化） | 映射已冻结；实时状态 = XD-C04 |
| 至少 100-item 离线模拟 | P4-C7 / P4-C8 / P4-C9 各自 500-item 门槛 | G-500（跨 package） |

---

## 3. Risk Class

### 3.1 裁决：Risk Class = B

| 考量 | 结论 |
|---|---|
| 生产改动 | 默认 **NONE**（设计调查 DF-05：验收不需要任何新生产能力） |
| 新安全边界 / 安全不变量变化 | NONE |
| 持久化 / 跨进程 locking / durable resume / migration | NONE |
| 文件系统修改 | 只由**既有、已复查**的 P4-C7 / P4-C6 代码执行，且**只**作用于 pytest `tmp_path` 下的可丢弃 fixture（第 12.2 节） |
| 修改 CLOSED package 行为 | NONE（只读验证；验证 ≠ 修改，治理文档第 8.3 节 C 类列的是“修改多个已经 CLOSED 的 package 的行为”） |
| 决定 Phase 4 是否 CLOSED | 是 —— 主要风险是“虚假验收”（空洞门槛让缺陷通过），由第 11 节 mutation 门、第 8 节回归门与独立 Review 控制 |

**为什么不是 A**：A 类覆盖“测试补强 / 文档 / compatibility matrix docs”，但 P4-C10 是 Phase 级退出门：它驱动真实文件系统
移动 / 重命名 / 落盘场景，并给出 Phase 4 CLOSED 的裁决；虚假 PASS 的后果高于普通测试补强，因此按 B 类要求完整证据与独立 Review。

**为什么不是 C**：C 类针对“工作本身改变或引入”删除 / 覆盖 / 移动用户文件、原子文件系统操作、source-loss 风险、持久化、
安全边界或多个 CLOSED package 的行为。P4-C10 不改变任何一项；它只在可丢弃副本上**观察**既有行为。

### 3.2 强制升级门（冻结；任一触发即停止 B 类施工，按 C 类重新治理）

```text
U-1  需要修改任何 CLOSED package 的 src/**（含 C10-R1 中的生产修复，治理文档第 13 节）
U-2  任何测试或脚本需要触碰 pytest tmp_path 之外的路径（第 12.2 节唯一例外的可选跨卷证据除外，且必须满足其全部条件）
U-3  需要新的安全边界、安全不变量变化或公开 API 变化
U-4  需要持久化、跨进程 locking、durable resume
U-5  需要 Contract semantic amendment（本合同或任何 CLOSED 合同）
U-6  需要新增第三方依赖或修改 pyproject.toml
U-7  任何其它实际达到治理文档第 8.3 节 C 类定义的风险
```

升级时：停止施工，在 HANDOFF / 状态说明中记录触发项与证据，等待治理裁决；没有治理依据不得降级。

### 3.3 C 内中间独立 Review

不需要。治理文档第 9 节五个触发条件中，只有“前一步定义新的 Frozen Contract”适用于**设计**本身，已由 P4-C10 Design Review 覆盖；
S1-S3 不建立在不可逆安全边界上、不修改既有代码、不涉及 C 类核心边界。例外：若 C10-R1 触发 U-1，该 C10-R1 本身按第 15 节需要独立 Review。

---

## 4. Phase 4 Package Authority Matrix

### 4.1 坐标矩阵（冻结；全部为 `c293ed75…` 的祖先，设计阶段已核对）

| Package | Capability（顶层 package） | Frozen Base | Final Reviewed Code / Package Head | Final Closure Docs Head | Frozen Contract | Construction Plan | HANDOFF |
|---|---|---|---|---|---|---|---|
| P4-C1 | 递归媒体发现（`discovery`） | `3edab6eb4ab363c1fedabd847c61b7061be8343d` | `c4f5a415d8fd8d0d56ff4ee227e7b87a01fbe79f`（R3） | `51933a81382d7922a61b5fcdddc54b17b5293e6f` | `PHASE4_DISCOVERY_CONTRACT.md` | 无（当时治理形态：任务简报 + 合同） | `P4_C1_HANDOFF.md` |
| P4-C2 | 不可变整理计划（`planning`） | `51933a81382d7922a61b5fcdddc54b17b5293e6f` | `f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7`（R2） | `b44ca7a1a3ca70dddf8686d9d14a98d52b481b82` | `PHASE4_ORGANIZE_PLAN_CONTRACT.md` | 无 | `P4_C2_HANDOFF.md` |
| P4-C3 | Metadata 发布边界（`publication`）+ C2-L2 / P2-R-10 | `b44ca7a1a3ca70dddf8686d9d14a98d52b481b82` | `1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f` | `8439da97f4e23e475a20619b4adb6bfd4ae30b6a` | `PHASE4_PUBLICATION_BOUNDARY_CONTRACT.md` | 无 | `P4_C3_HANDOFF.md` |
| P4-C4 | 纯 NFO 渲染（`nfo`） | `8439da97f4e23e475a20619b4adb6bfd4ae30b6a` | `526177b7c4279057633a2fb893fab79804c97835` | `97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6` | `PHASE4_NFO_RENDERING_CONTRACT.md` | 无 | `P4_C4_HANDOFF.md` |
| P4-C5 | 图片获取（`images`） | `97f6aeba8d11d9bc8a29d5397b9a1e1711d36cd6` | `65036e3857f87d821b5b282d7162ddbdabd42773`（R1） | `e44790f57004825957f2212921171667e7c576cf` | `PHASE4_IMAGE_ACQUISITION_CONTRACT.md` | 无 | `P4_C5_HANDOFF.md` |
| P4-C6 | 原子 artifact 落盘（`materialization`） | `e44790f57004825957f2212921171667e7c576cf` | `8f845b429b6b35f86038b393a2c98864f35a68b0` | `397f6d92cf6919a58e2225187e3ac27aedbb5f00`（之后 DOCS-CN Final `a0a69c71…`） | `PHASE4_ATOMIC_MATERIALIZATION_CONTRACT.md` | 无 | `P4_C6_HANDOFF.md` |
| P4-C7 | 安全文件系统执行器（`execution`） | `a0a69c71a1451232ded2c8ae8ecd514cf48ba95b` | `ae1ace96c86874b3f33ec59819e4aa065136e521`（S6；S5 生产 `3a2d737…`） | `586f92f9b96576dbd71c005a6c95b6e7e52210f4` | `PHASE4_SAFE_FILESYSTEM_EXECUTION_CONTRACT.md`（E0 `8f18ec6…` + S5-A1/A2/A2-R1/A2-R2） | `P4_C7_CONSTRUCTION_PLAN.md` | `P4_C7_HANDOFF.md` |
| P4-C8 | 批量编排 / 预览 / 重试（`orchestration`） | `586f92f9b96576dbd71c005a6c95b6e7e52210f4` | `15912b1b5e0c2a813998e898423d11c280e965fb`（S6-R1） | `a662659dfd6e801531b14af7913d84a5f9f859e2` | `PHASE4_BATCH_ORCHESTRATION_CONTRACT.md`（E0-R2 `9e118de…`） | `P4_C8_CONSTRUCTION_PLAN.md`（S5-A1 `0f591ff…`） | `P4_C8_HANDOFF.md` |
| P4-C9 | 结构化诊断（`diagnostics`） | `a662659dfd6e801531b14af7913d84a5f9f859e2` | `9cd7bf56ba98878145cdae95456edd6ef9fb2ae9`（C9-R2） | `c293ed75e6ab3160d57ab8bf1248d1ce16ec241c` | `PHASE4_DIAGNOSTICS_CONTRACT.md`（Design Accepted `dbb0c13…`） | `P4_C9_CONSTRUCTION_PLAN.md` | `P4_C9_HANDOFF.md` |

全部合同在 `docs/specifications/`，施工计划在 `docs/`，HANDOFF 在 `docs/review/`。

### 4.2 能力 / 风险 / 不变量 / 局限 / 依赖矩阵

Risk Class 一列：Acceleration Governance v2 从 P4-C9 起生效、**不追溯**（治理文档第 5 节）；P4-C1..P4-C8 记为 N/A，并给出当时的治理形态。

| Package | Risk Class | Key Safety Invariants（来源节） | Known Limitations | Deferred / Evidence Gaps（处置见第 10 节） | 依赖的 Phase 4 package |
|---|---|---|---|---|---|
| P4-C1 | N/A（单 C + R1-R3 增量复查） | 只读、确定性排序（§7）、根目录失败不伪装为空（§8）、子树失败隔离为 `DiscoveryIssue`（§9）、symlink / junction 不跟随（§10）、`source_path` 绝对（R1） | 递归深度受调用栈限制；symlink 文件被排除；无长路径压力测试；无并发声明 | P4-C1-R-02..R-05；Windows 真实目录 symlink（4 skip） | 无（不依赖 `fc2_metadata_core`） |
| P4-C2 | N/A（单 C + R1/R2） | 零文件系统访问；标题不参与路径（§5）；组件安全（§10）；目标包含（§11）；完全限定根（§11a）；冲突 fail closed、overwrite = NEVER（§12）；确定性（§14） | 不携带 `OutputPolicy`；无真实预检 | P4-C2-R1-02；扩展保留名；POSIX 路径形式（10 skip） | P4-C1 |
| P4-C3 | N/A | 只发布 SUCCESS / PARTIAL（§4）；身份关联（§6）；无诊断信息（§8）；零 I/O（§12）；C2-L2 trace 加固（§14） | `hash(record)` 抛 `TypeError`；trace 不携带策略 | P4-C3-R-01 / R-02 | P4-C2 |
| P4-C4 | N/A | 冻结 XML 形态 / 顺序（§3-4）；XML 1.0 字符安全（§10）；注入安全（§11）；状态隔离（§7）；纯函数（§13） | fc2db_net datetime release 使 NFO fail closed（§18） | P4-C4-R-01；fc2db_net release 规范化 | P4-C3 |
| P4-C5 | N/A（S1-S5 + R1） | URL 安全门（§8）；手动重定向逐跳重验（§12.4）；流式上限 / 总 deadline（§12.5-12.7）；清理异常边界（§12.9a）；JPEG-only（§13）；角色隔离 / 候选上限 / 总量上限（§14）；敏感数据排除；取消原样传播 | 无 DNS 解析 / rebinding 防御；JPEG 结构校验非完整解码 | DNS rebinding | P4-C3 |
| P4-C6 | N/A（S1-S3） | overwrite = NEVER（§6）；无替换原子发布（§7）；只清理自有临时文件（§8-9）；致命异常原样传播（§10）；并发恰一胜者（§13）；无 mkdir / 无 MOVE_MEDIA（§23） | POSIX 不支持 hard link 的文件系统 fail closed；父目录不 fsync | Windows 真实 symlink（5 skip） | P4-C2、P4-C5（仅模型） |
| P4-C7 | N/A（E0 + S1-S6 逐批独立复查） | 执行边界加固（§5-7）；状态语义（§8）；forward-only、无回滚（§28）；no silent source loss 核心不变量（§31）；overwrite = NEVER（§23）；修改前重验（§25）；平台规则（§26）；进程内源所有权占用（§15.6） | 字符串路径 API 的 TOCTOU（§25）；checkpoint 仅进程内；跨进程同源不保证最多一个 SUCCESS | Windows native symlink、POSIX native、kernel `O_NOFOLLOW`、native cross-volume（共 20 skip） | P4-C2、P4-C6 |
| P4-C8 | N/A（E0 + S1-S6 逐批独立复查） | 不直接触碰文件系统（§3、§30）；条目隔离 / 致命边界（§20）；批内冲突全部阻断（§14）；preview 零修改（§16）；有界并发与资源硬限制（§19）；无持久化（§33）；确定性（§29） | §37 全部（library_root 晚校验、资源上限、执行不可中断、致命异常无部分结果、无跨进程协调、无 durable resume、无进度流、番号只从 basename 识别、冲突组全阻断、metadata PARTIAL 不重刮） | 跨进程并发；POSIX native | P4-C1..P4-C7 + Phase 3 batch / Phase 1 normalize |
| P4-C9 | **B** | 只读 / 零副作用（§26）；本地校验先于分派（§9）；A 类渠道绝对脱敏、默认 `PathPolicy.NONE`（§17-18）；确定性 JSON（§15、§22）；资源 / 输出上界（§21）；fail closed（§25） | §31 全部 | POSIX 原生 basename 语义 | P4-C8（只读消费其公开模型及可达下层模型） |

---

## 5. Cross-Package Integration Matrix

### 5.1 真实链路（冻结；模块与调用点取自 Frozen Base 源码，设计阶段已核对）

```text
pytest tmp_path 下的脏下载目录（可丢弃 fixture）
  -> fc2_organizer.discovery.discover_media(root)                                         P4-C1
  -> BatchOrchestrator.preview(result.items)                                               P4-C8
       recognition.normalize_fc2_number(basename)                                          Phase 1
       Phase A 冲突（recognition）
       BatchScheduler(engine).run(numbers)                                                 Phase 3 C4
         -> MultiSourceEngine.aggregate -> execute_sources_traced -> SourceAdapter.fetch
            -> merge_source_results（字段级聚合）                                           Phase 3 C1-C3
       stages.build_organize_plan                                                          P4-C2
       stages.prepare_publication                                                          P4-C3
       stages.render_movie_nfo                                                             P4-C4
       preview.acquire_images(record, image_client) -> HttpxImageClient.get -> JPEG 校验     P4-C5
       stages.build_artifact_requests                                                      P4-C6 mapping
       stages.preflight_execution（只读）+ Phase B 冲突                                      P4-C7
  -> BatchPreview
  -> BatchOrchestrator.execute(preview, selection=, cancel=)
       execute.execute_filesystem -> U1..U8 -> materialize_artifact -> materialize_atomic_bytes   P4-C7 / P4-C6
  -> BatchExecutionResult
  -> BatchOrchestrator.preview_retry(result, scope=) -> execute -> merge_retry              P4-C8（checkpoint -> P4-C7）
  -> build_preview_diagnostics / build_execution_diagnostics -> render_diagnostics_json     P4-C9
```

### 5.2 Link 矩阵（每个 link 都必须有 P4-C10 真实链路证据；全部 Blocking）

| Link | 上游 -> 下游 | 真实调用点 | 包内既有证据（不重复） | P4-C10 新增证据 |
|---|---|---|---|---|
| L-01 | 文件系统 -> P4-C1 | `discover_media(root)` | P4-C1 全套 | 每个场景与 G-500 的输入都由真实 `discover_media` 产生 |
| L-02 | P4-C1 -> P4-C8 | `BatchOrchestrator.preview(DiscoveryResult.items)`；`recognition.validate_media_items` / `bounded_snapshot` | P4-C8 integration（脚本化 engine） | 全部场景 |
| L-03 | P4-C8 -> Phase 1 | `recognition.normalize_fc2_number`（文件 basename） | P4-C8 recognition | S-06、G-500（GE） |
| L-04 | P4-C8 -> Phase 3 batch | `BatchScheduler(engine, config.metadata)`；重试经 Phase 3 `retry_failed` / `apply_retry` | P4-C8（**脚本化** engine） | **真实** `MultiSourceEngine` 下的 S-05、G-500（GC） |
| L-05 | Phase 3 batch -> aggregation | `MultiSourceEngine.aggregate` -> `execute_sources_traced` -> `SourceAdapter.fetch` -> `merge_source_results` | Phase 3 全套（未接入 P4-C8） | **首次**在 P4-C8 链路中使用真实引擎：S-01..S-05、S-20（真实 adapter + fixture HTML）、G-500（GA/GB/GC）；DF-01 |
| L-06 | P4-C8 -> P4-C2 | `stages.build_organize_plan` | P4-C2、P4-C8 | 布局 oracle（S-01、S-12）；S-09 规划拒绝 |
| L-07 | P4-C8 -> P4-C3 | `stages.prepare_publication` | P4-C3、P4-C8 | 真实 `AggregationResult` -> `PublicationRecord`（S-02、S-04） |
| L-08 | P4-C8 -> P4-C4 | `stages.render_movie_nfo` | P4-C4、P4-C8 | NFO oracle 对照字段级聚合结果（S-04、S-08、S-20） |
| L-09 | P4-C8 -> P4-C5 | `preview.acquire_images(record, image_client, policy=)` -> `HttpxImageClient.get` -> `validate_acquired_image` | P4-C5（真实 transport 未接入 P4-C8）；P4-C8（**脚本化** client） | **首次**在 P4-C8 链路中使用真实 `HttpxImageClient(transport=httpx.MockTransport(...))`：S-07、G-500（GD）；DF-01 |
| L-10 | P4-C8 -> P4-C6 mapping | `stages.build_artifact_requests` | P4-C6、P4-C8 | 图片字节身份 oracle（落盘字节 == 提供给该 URL 的字节，S-01、S-07） |
| L-11 | P4-C8 -> P4-C7 preflight | `stages.preflight_execution` | P4-C7、P4-C8 | S-11 preflight 阻断、S-21 junction root |
| L-12 | P4-C8 -> P4-C7 / P4-C6 执行 | `execute.execute_filesystem` -> `materialize_artifact` -> `materialize_atomic_bytes` | P4-C7 S6、P4-C8 S6 | 全部执行场景；Safety Gate（第 6 节） |
| L-13 | 重试 / checkpoint 交接 | `preview_retry` / `merge_retry`；`ExecutionResult.checkpoint` -> `preflight_execution(..., checkpoint=)` | P4-C8 retry chain | S-13、S-14、S-16、S-17、G-500 g1-g4（真实引擎 + 真实 transport 下） |
| L-14 | P4-C8 -> P4-C9 | `build_preview_diagnostics` / `build_execution_diagnostics` / `render_diagnostics_json` | P4-C9 integration（脚本化 engine） | 真实链路产物上的诊断：S-18、G-500 全部 14 个模型；履行 P4-C9 合同第 30 节“P4-C10 跨包集成门槛对 diagnostics 的覆盖” |

### 5.3 验收重点覆盖表（任务要求逐项 -> 场景）

| 验收重点 | 场景 |
|---|---|
| 合法输入成功链 | S-01、S-20 |
| metadata partial | S-02 |
| 单 source failure | S-03、G-500 GB |
| 多 source mixed outcome | S-04 |
| image partial / failure | S-07、G-500 GD |
| NFO generation | S-08、S-04、S-20 |
| planning success / rejection | S-01 / S-09 |
| preflight blocker | S-11、G-500 GG |
| execution success | S-01、S-12 |
| execution partial | S-13、G-500 GH |
| execution failure | S-14、G-500 GI |
| retry material | S-13、S-17 |
| fresh retry | S-14 |
| resume retry | S-13 |
| deferred | S-16、G-500 GJ |
| merge / retry result | S-17、G-500 |
| diagnostics PREVIEW / EXECUTION | S-18、G-500 |
| diagnostics redaction | S-18、M-08 |
| deterministic output | S-19、G-500 重跑 |

---

## 6. Safety Invariant Matrix（冻结）

P4-C10 只**验证**既有规则，不重新定义。每一行的 Normative Rule 以引用合同原文为准。
“共享 oracle”指 `tests/phase4_acceptance/_oracles.py` 中由 P4-C10 独立实现的门函数（不 import `tests/unit/**` helper，第 12.4 节）。

| ID | 不变量 | Originating Package / Contract | Normative Rule | P4-C10 Acceptance Evidence | Blocking |
|---|---|---|---|---|---|
| SI-01 | no silent source loss | P4-C7 §25、§29、§31 核心不变量；P4-C8 §30.1、§35 | 任何失败后，源字节完整存在于源路径或最终路径（或两者） | 每个执行 / 注入 / 重试轮之后对**全部**输入条目执行 `gate_source_not_lost`（S-11..S-17、S-21、G-500 每轮）；M-01 证明该门会失败 | YES |
| SI-02 | overwrite = NEVER | P4-C2 §12；P4-C6 §6-7；P4-C7 §23 | 已存在条目永不被覆盖 / 截断 / 替换 / 重命名 / 加后缀 | 预置用户目标与 case 变体目标（S-11、S-21）字节 / inode / mtime 不变；M-02（`_FS.rename = os.replace`）使门失败 | YES |
| SI-03 | fail closed | 全部合同（P4-C7 §25、P4-C8 §20、P4-C9 §25） | 检测到不一致即停止并类型化报告，不猜测、不修复 | 每个故障场景断言类型化 disposition / failure kind / blocker，而非成功或裸异常 | YES |
| SI-04 | source isolation | CLAUDE.md；Phase 3 聚合合同 §状态表 | 单一 source 失败不导致整片失败 | S-03、G-500 GB（单源失败 -> 聚合 `PARTIAL` -> 执行 `SUCCESS`）；M-12 使门失败 | YES |
| SI-05 | item isolation | CLAUDE.md；P4-C8 §20 | 单一影片失败不阻断其它影片 | S-15、G-500（GH/GI/GK 与 GA 同批，GA 全部 SUCCESS） | YES |
| SI-06 | bounded concurrency | P4-C8 §19；Phase 3 batch | metadata ≤ M、图片 ≤ K、执行 ≤ W；无每条目一线程 | S-22（门控下峰值 == 上限且 ≤ 上限）；G-500 峰值 ≤ 4；M-11 使门失败 | YES |
| SI-07 | deterministic behavior | P4-C1 §7；P4-C2 §14；P4-C8 §29；P4-C9 §15 | 相同输入 -> 相同结果投影 / 相同诊断字节 | S-19（两树 + 反转完成顺序）；G-500 全量重跑诊断 JSON（`NONE`）逐字节相等；M-10 使门失败 | YES |
| SI-08 | atomic materialization boundaries | P4-C6 §7、§9；P4-C7 §24 | artifact 要么完整、要么不存在；无部分最终文件 | 每个最终 artifact 字节 / sha256 == 期望；注入写失败后最终路径不存在（S-13 NFO publish 故障、G-500 GH） | YES |
| SI-09 | source preservation（非成功条目） | P4-C8 §30.1；P4-C7 §28 | 未执行 / 阻断 / 失败条目的源字节与位置不变 | G-500 最终：65 个非成功条目的源仍在原位、字节不变；S-06、S-09、S-10 | YES |
| SI-10 | collision behavior | P4-C2 §12；P4-C8 §14；P4-C7 §21、§30 | 批内冲突组全部阻断、不选胜者；同目标竞争恰一胜者 | S-10（重复番号 / 同文件两次 / hardlink）与 G-500 GF；M-03 使门失败 | YES |
| SI-11 | partial failure semantics | P4-C7 §8；P4-C8 §11.5、§23 | `PARTIAL` ⇔ 至少一个已验证 effect + checkpoint；`FAILED` ⇔ 无可记录 effect；`ABORTED` 永不计为成功 | S-13 / S-14 / S-15 逐项断言状态、checkpoint 存在性、effect 前缀；outcome 恒等式 | YES |
| SI-12 | retry ownership | P4-C8 §24-26、§12.3 | RetryKind 由冻结判定得出；重试只作用于 scope；结果 / preview 只能消费一次；身份（`media_item is`）一致 | S-17（scope 子集、二次 `preview_retry` / `merge_retry` -> `OrchestrationConsumedError`）；M-05 使门失败 | YES |
| SI-13 | checkpoint / resume integrity | P4-C7 §14；P4-C8 §24 | RESUME 只用本进程签发的 checkpoint；已完成 effect 不重写；旧 checkpoint 被消费 | S-13：RESUME 后已完成 artifact 与媒体 inode / mtime 不变、最终布局与一次成功相同；M-06 使门失败 | YES |
| SI-14 | temporary-file cleanup / leftovers | P4-C6 §8-10；P4-C7 §20、§24 | 只清理自有临时文件；遗留临时文件必须被如实报告；无关临时文件不被触碰 | 每个场景后：除被报告的 `LeftoverTemporary` 外无 `.fc2tmp-*.part`；预置无关 `.fc2tmp-*` / `.part` / `.tmp` 字节不变；M-13 使门失败 | YES |
| SI-15 | path containment | P4-C2 §11、§11a；P4-C7 §6.6、§26.3 | 一切写入只发生在 `library_root` 下本条目目标目录内（源删除 / 移动除外） | 写操作观察记录（第 12.5 节）中每个修改性路径 ∈ 允许集合；全树快照差异只出现在预期路径；M-04 使门失败 | YES |
| SI-16 | symlink / reparse / path safety | P4-C1 §10；P4-C7 §10、§26.1 | 不跟随链接；junction / symlink library root 被拒绝 | S-21：junction library root -> 阻断、零修改（Windows 原生）；symlink 原生证据处置见 XD-B01 | YES（junction）/ 证据缺口按 Ledger |
| SI-17 | cross-package validation ownership | P4-C3 §6；P4-C7 §5-7；P4-C9 §9 | 每个边界自行校验输入，不信任上游 `__post_init__` | 包内已有完整证据；P4-C10 回归门（第 8 节）保持其全部通过；S-04 / S-20 证明真实 producer 输出跨边界全部被接受 | YES |
| SI-18 | diagnostics redaction | P4-C9 §17-18 | A 类渠道在任何策略下绝不输出；默认 `PathPolicy.NONE` 不输出路径文本 | S-18 与 G-500：对全部渲染 JSON 做 canary 扫描（`NONE` 与 `BASENAME`）；M-08 使门失败 | YES |
| SI-19 | no unexpected persistence | P4-C8 §33；P4-C9 §4、§22.4；P4-C7 §34 | 不写任何状态 / 诊断 / cache 文件 | 写操作观察记录中无 library 目标目录之外的写入；诊断期间写 API 陷阱；运行后 repo 工作树 `git status --porcelain` 为空 | YES |
| SI-20 | no network | 全部 Phase 4 测试合同（离线） | 测试不访问真实网络 | C10 场景期间 `socket.socket` / `socket.create_connection` / `socket.getaddrinfo` 陷阱（MockTransport 与 `FakeHttpClient` 不使用 socket）；陷阱非空洞性对照 | YES |
| SI-21 | preview zero-mutation | P4-C8 §16 | preview / preview_retry 零文件系统修改 | 每次 preview / preview_retry 前后全树快照相等（全部场景与 G-500）；M-14 使门失败 | YES |
| SI-22 | 汇总 / 账目一致（no silent loss in accounting） | P4-C8 §28.3-28.4 | 每个输入 index 在结果中恰出现一次；summary 恒等式与 outcome 真值表成立 | G-500 每代结果与合并结果；S-17；M-07 使门失败 | YES |

---

## 7. Acceptance Scenario Matrix

### 7.1 Fixture 设计（少量、高价值、全部可丢弃）

| Fixture | 内容 | 用途 |
|---|---|---|
| FX-1 小型确定性语料 | 12 个合成媒体文件（几字节到 4 KiB；含 0 字节、1 MiB + 1 一个；CJK / 假名 / emoji / NFC + NFD 名称；`.MP4` / `.mkv` 大小写扩展名），三个脚本化 source，固定图片 URL 表 | S-01..S-08、S-12、S-19 |
| FX-2 混合结果批 | 24 个条目，每种 disposition / ExecutionStatus / RetryKind 至少一次 | S-13..S-17 |
| FX-3 文件系统安全 fixture | 预置用户目标目录与 `user-note.txt`、case 变体同名目标、无关 `.fc2tmp-<32hex>.part` / `unrelated.part` / `unrelated.tmp` / `user-file.txt`、library 中的用户影片目录 `FC2-0000001-user/keep.mp4`、junction library root（Windows）、重复番号 / 同文件两次 / hardlink 对 | S-10、S-11、S-21 |
| FX-4 retry / partial fixture | 经授权 `_FS` 接缝按条目、一次性注入的故障（U1 前、U1 后、U2、artifact、U7、extrafanart） | S-13、S-14、S-15 |
| FX-5 diagnostics fixture | A 类 canary：`error_detail` 中 `Authorization: Bearer C10CANARY-AUTH` / `Cookie: session=C10CANARY-COOKIE`；标题 / 简介 `C10CANARY-TEXT`；图片 URL query `token=C10CANARY-URL`；异常 message `C10CANARY-EXC`；源父目录 `C10CANARYDIR`、library root `C10CANARYROOT`；secret-like 文件名 `Authorization-C10CANARY.mp4` / `Cookie-C10CANARY.mp4` / `token-C10CANARY.mp4` | S-18 |
| FX-6 真实 adapter 语料 | `build_default_registry()` + `default_aggregation_config()` 的真实 adapter，`tests/support/fake_http_client.FakeHttpClient` 提供 `tests/fixtures/sources/**` 既有 HTML（`FC2-4825061`、`FC2-4979299`、`FC2-4824605`，以及 cloudflare challenge 页） | S-20 |
| G-500 全局语料 | 第 7.4 节 | G-500 |

所有期望值来自 fixture / 用例定义与被引用合同的冻结规则，**不得**从被测输出回填。FX-6 的期望标题等字面量由测试作者阅读
fixture HTML 后写成常量（与 Phase 2 adapter 测试同一做法）。

### 7.2 场景矩阵（冻结；全部 Blocking）

列说明：Meta = metadata 结果；Plan = planning；Exec = execution；Retry = retry；Diag = diagnostics；FS = 文件系统不变量。
Phase 3 聚合状态按其冻结规则：NOT_FOUND 不是运行性失败；BLOCKED / NETWORK_ERROR / RATE_LIMITED / PARSE_ERROR / INVALID_RESPONSE 是运行性失败。

| ID | Input | Meta | Plan | Exec | Retry | Diag | FS 不变量 | Blocking assertion |
|---|---|---|---|---|---|---|---|---|
| S-01 合法成功链 | FX-1 条目，三源全部 SUCCESS，poster / fanart / thumb + 2 张 extrafanart | `SUCCESS` | READY；默认布局 | `EXECUTED + SUCCESS` | `NONE` | PREVIEW / EXECUTION 均可构建、渲染；outcome SUCCESS | 最终目录精确列举；源已不存在；媒体字节 == 源字节；无临时残留 | 布局 / 字节 / sha256 与定义逐项相等 |
| S-02 metadata partial | 一源 SUCCESS、两源运行性失败 | `PARTIAL` | READY；`ItemWarning.METADATA_PARTIAL` | `SUCCESS` | `NONE` | `metadata.status = partial`；source 状态逐项 | 同 S-01 | metadata `PARTIAL` 永不计入文件系统 `partial` |
| S-03 单 source failure | A=BLOCKED(403)、B=SUCCESS、C=NOT_FOUND | `PARTIAL` | READY | `SUCCESS` | `NONE` | A 的 `operational_failure`、C 的 `not_found` 如实呈现 | 同 S-01 | 单源失败不影响整片（SI-04） |
| S-04 多 source mixed + 字段级聚合 | 三源全部 SUCCESS 但各自提供不同字段：title 只来自 A、release 只来自 B、tags 来自 A 与 C | `SUCCESS` | READY | `SUCCESS` | `NONE` | `field_provenance` 与定义中的来源逐字段一致 | 同 S-01 | NFO 中 title / premiered / tag 与聚合定义一致；聚合 ↔ NFO ↔ 诊断三方一致 |
| S-05 全部 source 失败 | 三源 NOT_FOUND / 运行性失败；g1 时脚本翻转为成功 | `FAILED` -> g1 `SUCCESS` | UNPREPARED `METADATA_UNAVAILABLE` -> READY | `NOT_READY` -> `SUCCESS` | `METADATA_REFETCH` -> 合并 | 两代诊断 | 源在 g0 不变 | 真实 `MultiSourceEngine` 经 Phase 3 重试恢复 |
| S-06 番号不可识别 | 文件名无 FC2 番号 | 不请求（engine 调用 0） | UNPREPARED `NUMBER_NOT_RECOGNIZED` | `NOT_READY` | `NONE` | issue stage / reason | 源不变 | engine / client 调用计数 0 |
| S-07 image partial / failure | poster：首候选 404、次候选合法；fanart：302 -> `http://10.1.2.3/…`；thumb：合法 JPEG 声明 `image/png`；extrafanart：一个非法 JPEG、一个合法 | `SUCCESS` | READY + 图片 warnings | `SUCCESS` | `NONE` | `image_failures` 分组：`HTTP_STATUS 404`、`UNSAFE_URL`、`CONTENT_TYPE_MISMATCH`、`INVALID_JPEG` | 只落盘成功角色；私有地址从未被请求（MockTransport 请求记录） | poster 字节 == 次候选字节；无 fanart / thumb 文件；extrafanart 仅 1 张 |
| S-08 NFO generation | 标题含 `&<>"'`、CJK、emoji；另一条目 release = `2026-02-30` | `SUCCESS` | 前者 READY；后者 UNPREPARED `NFO_RENDER_FAILED` | `SUCCESS` / `NOT_READY` | `NONE` / `NONE` | issue 呈现 | 后者源不变 | NFO 可解析、逐字还原、无注入元素；非法日期 fail closed |
| S-09 planning rejection | orchestrator `library_root` 为相对路径；另一组为 Windows 有根无盘符（`\lib`，仅 Windows） | metadata 正常获取 | UNPREPARED `PLANNING_REJECTED` | `NOT_READY` | `NONE` | issue 呈现 | 零修改 | 无任何目录被创建 |
| S-10 批内冲突 | 两目录同番号；同一 `DiscoveredMediaItem` 出现两次；hardlink 对（番号不同） | Phase A 冲突条目不请求 metadata | BLOCKED `DUPLICATE_*`（Phase A / Phase B） | `NOT_READY` | `NONE` | 冲突组呈现 | 全部源不变 | 不选胜者；engine 未被询问 Phase A 条目（SI-10） |
| S-11 preflight blocker | 目标目录已存在（含 `user-note.txt`）；g2 前测试作为“用户”删除它 | `SUCCESS` | BLOCKED `PREFLIGHT_BLOCKED` -> READY | `NOT_READY` -> `SUCCESS` | `PREFLIGHT_RECHECK` | blocker 呈现（preview 诊断） | 用户文件在删除前字节 / inode / mtime 不变 | 阻断期间零修改（SI-02、SI-21） |
| S-12 execution success 变体 | 同卷原生；`_FS.device_of` 接缝强制跨卷（含 1 MiB + 1 字节流式）；0 字节媒体；NFC / NFD 名称；`.MP4` -> `.mp4` | `SUCCESS` | READY | `SUCCESS`；跨卷 `transfer_mode = CROSS_VOLUME` | `NONE` | execution effect 计数 | 同卷 inode 保持；跨卷 sha256 == 源 | 字节、扩展名小写、容器不变 |
| S-13 execution partial -> RESUME | 经 `_FS.device_of` 强制跨卷的条目在删除源时注入 `SOURCE_UNLINK_FAILED`（Windows 原生同卷为原子 rename，不执行源 unlink）；另一条目 NFO publish 失败 | `SUCCESS` | READY | `PARTIAL`（携带 checkpoint） -> RESUME `SUCCESS` | `RESUME` | `checkpoint_present = true`；retry_kind resume | 失败后 SI-01；RESUME 后已完成 artifact / 媒体 inode / mtime 不变 | 最终布局 == 一次成功布局（SI-13） |
| S-14 execution failure -> FRESH | U1 前注入（源重验 lstat 失败）；另一条目 U1 `EACCES`（“目标不可写”接缝级） | `SUCCESS` | READY | `FAILED`（零 effect、无 checkpoint） -> `SUCCESS` | `FRESH_REEXECUTE` | failure step / kind | 源不变；无目标目录 | 零 effect 失败可 fresh 重执行 |
| S-15 ABORTED / item isolation | U2 注入外来 `RuntimeError`（message = `C10CANARY-EXC`），同批另有正常条目 | `SUCCESS` | READY | 该条目 `ABORTED`；其余 `SUCCESS` | `NONE` | ABORTED 呈现，canary 不泄露 | SI-01 对该条目显式断言；空目标目录如实存在 | ABORTED 永不计为成功（SI-05、SI-11） |
| S-16 deferred | selection 排除 3 条；另一轮 `W = 1` 在第 2 条后设置 `CancellationToken` | `SUCCESS` | READY | `NOT_SELECTED` / `CANCELLED`（后缀） | `DEFERRED` -> `SUCCESS` | disposition 呈现 | 未执行条目源不变 | 取消只停止准入；延后条目可重试至成功 |
| S-17 retry chain / merge | FX-2：g0 -> g1 {RESUME} -> g2 {METADATA_REFETCH, FRESH_REEXECUTE, PREFLIGHT_RECHECK} -> g3 {DEFERRED} | 混合 | 混合 | 每代精确计数 | 每代精确 scope | 每代 PREVIEW / EXECUTION / MERGED 诊断 | 每代 SI-01 | 二次 `preview_retry` / `merge_retry` -> `OrchestrationConsumedError`；summary 恒等式（SI-12、SI-22） |
| S-18 diagnostics | FX-5 canary 全部植入，跑完 S-01..S-17 的代表形态 | 混合 | 混合 | 混合 | 混合 | 默认 `NONE` 与显式 `BASENAME` 各渲染；`json.loads` 可解析；schema 常量 | 诊断前后全树快照相等 | A 类 canary 在两种策略下均不出现；默认 `NONE` 下 `C10CANARY` 完全不出现（SI-18） |
| S-19 determinism | FX-1 在两棵全新树中各跑一次；第二次以门控事件反转 engine / 图片 / 执行完成顺序 | 相同 | 相同 | 相同 | 相同 | 诊断 JSON（`NONE`）逐字节相同 | -- | 确定性投影与诊断字节相等（SI-07） |
| S-20 真实 adapter 链 | FX-6：`FC2-4825061`（av123 命中、fc2db_net 404、javdb 命中）、`FC2-4979299`（全部命中）、`FC2-4824605`（fc2db_net 命中、av123 404、javdb 近似未命中）；另一组一个 source 返回 cloudflare challenge 页 | 前三者 `SUCCESS`；challenge 组 `PARTIAL` | READY | `SUCCESS` | `NONE` | source 状态与 fixture 一致 | 同 S-01 | NFO title / uniqueid 与 fixture 常量一致；真实 parser 输出跨全部边界被接受 |
| S-21 文件系统安全 | FX-3：junction library root（Windows 原生）；目标目录的大小写变体（`fc2-1234567`）已存在；无关临时文件 / 用户文件 / 用户影片目录 | `SUCCESS` | junction root 组：全部 BLOCKED `PREFLIGHT_BLOCKED`；大小写变体条目：BLOCKED `PREFLIGHT_BLOCKED`（NTFS 大小写不敏感，目标目录已存在） | `NOT_READY` | `PREFLIGHT_RECHECK` | preview blocker 呈现 | 全部预置条目字节 / inode / mtime 不变；无链接被跟随；零修改 | SI-02、SI-14、SI-16 |
| S-22 bounded concurrency | 8 条目，`M = K = W = 2`，门控事件保持在途 | 正常 | READY | `SUCCESS` | `NONE` | -- | preview 零修改 | 观测峰值 == 2 且全程 ≤ 2（三个预算各自） |

### 7.3 场景执行规则

* 每个场景在独立的 `tmp_path` 树中执行；场景之间不共享文件系统状态。
* 故障注入只经第 12.6 节授权接缝，按条目路径限定作用域、只触发一次，并断言确实触发（非空洞注入）。
* 每个执行 / 重试轮之后都执行 SI-01、SI-14、SI-15、SI-21（preview 前后）、SI-22 共享门。

### 7.4 G-500：Phase 4 跨 package 500-item 全局门槛（冻结）

依据：P4-C8 合同第 3、37 节把“跨 package 的 Phase 4 500-item 全局门槛”划归 P4-C10；v1.0 规格书关键验收“500 项批次中注入
单源 / 单项失败，整体任务仍完成”。G-500 与 P4-C7 / P4-C8 / P4-C9 的 500-item 门槛的区别：**真实** `MultiSourceEngine`（脚本化
`SourceAdapter`）+ **真实** `HttpxImageClient`（MockTransport）+ 真实 `discover_media` + 真实 P4-C7 文件系统 + 真实 P4-C9 诊断，
同一批次贯通。

配置：`OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=4), image_in_flight_items=4, filesystem_workers=4)`；
其余默认。500 个物理媒体文件全部由真实 `discover_media` 发现（500 个逻辑输入）。

| 组 | 数量 | 构造 | g0 preview | g0 执行 / RetryKind | 后续 |
|---|---|---|---|---|---|
| GA 正常 | 260 | 三源 SUCCESS（字段级聚合）；8 种 poster / fanart / thumb 组合 × extrafanart 0..3 轮换 | READY | SUCCESS / NONE | -- |
| GB 单源失败 | 60 | 一源运行性失败（20 BLOCKED、20 NETWORK_ERROR、20 PARSE_ERROR），其余 SUCCESS | READY（`METADATA_PARTIAL`） | SUCCESS / NONE | -- |
| GC metadata 全失败 | 30 | 三源全部失败；其中 20 个在第二次聚合时恢复 | UNPREPARED `METADATA_UNAVAILABLE` | NOT_READY / METADATA_REFETCH | g2：20 READY -> SUCCESS；10 仍失败 |
| GD 图片部分失败 | 30 | 候选 404 / 不安全重定向 / Content-Type 不符 / 非法 JPEG 轮换 | READY（图片 warning） | SUCCESS / NONE | -- |
| GE 番号不可识别 | 20 | 文件名无番号 | UNPREPARED `NUMBER_NOT_RECOGNIZED` | NOT_READY / NONE | -- |
| GF 批内重复番号 | 20 | 10 对同番号不同文件 | BLOCKED `DUPLICATE_*`（Phase A） | NOT_READY / NONE | -- |
| GG preflight 阻断 | 20 | 目标目录预置（含 `user-note.txt`）；g2 前测试删除其中 15 个 | BLOCKED `PREFLIGHT_BLOCKED` | NOT_READY / PREFLIGHT_RECHECK | g2：15 SUCCESS；5 仍阻断 |
| GH 执行 PARTIAL | 20 | 媒体发布之后经 `materialization.atomic._FS` 注入：10 个 NFO publish 失败、10 个 poster 写入失败（GH 条目全部带 poster） | READY | PARTIAL / RESUME | g1：20 SUCCESS |
| GI 执行 FAILED | 20 | U1 前注入（源重验 lstat 失败） | READY | FAILED / FRESH_REEXECUTE | g2：20 SUCCESS |
| GJ 未选中 | 10 | g0 selection 排除 | READY | NOT_SELECTED / DEFERRED | g3：10 SUCCESS |
| GK 外来异常 | 10 | U2 注入 `RuntimeError` | READY | ABORTED / NONE | -- |

冻结计数（全部精确断言；由上表推导，不从输出回填）：

```text
g0 preview      total 500 / ready 410 / blocked 40 / unprepared 50
g0 result       success 350 / partial 20 / failed 20 / aborted 10 / not_selected 10 / not_ready 90；outcome PARTIAL
                retryable 90（RESUME 20、FRESH_REEXECUTE 20、METADATA_REFETCH 30、PREFLIGHT_RECHECK 20）/ deferred 10
g1 {RESUME}                                             20 READY -> 20 SUCCESS；轮 outcome SUCCESS；合并 success 370
g2 {METADATA_REFETCH, FRESH_REEXECUTE, PREFLIGHT_RECHECK} 70 条 -> ready 55 / blocked 5 / unprepared 10 -> 55 SUCCESS；合并 success 425
g3 {DEFERRED}                                           10 READY -> 10 SUCCESS；轮 outcome SUCCESS；合并 success 435
g4 scope=None                                           15 条（GC 10 + GG 5）-> ready 0、执行 0；轮 outcome FAILED
最终（合并）    success 435 / blocked 25 / unprepared 30 / aborted 10；outcome PARTIAL；retryable 15
```

G-500 断言（全部 Blocking）：

1. 上述全部计数与 outcome；summary 恒等式与 P4-C8 第 11.5 节真值表（SI-22）。
2. 每轮执行后对全部 500 条执行 SI-01；SI-09：最终仍在下载目录原位且字节不变的源恰为 65 个（GE 20、GF 20、GG 5、GC 10、GK 10）。
3. 最终 library 精确列举：435 个成功影片目录（媒体字节 == 源字节；NFO 可解析且 title / uniqueid 与定义一致；图片字节 == 该 URL
   被提供的字节；extrafanart 名称与顺序）；5 个用户阻断目录（`user-note.txt` 不变）；10 个 ABORTED 条目的空目标目录；用户影片目录不变；
   无未报告的临时文件（SI-14）。
4. 每次 preview / preview_retry 前后全树快照相等（SI-21）；g1 RESUME 的 GH 条目已完成 artifact 与媒体 inode / mtime 不变（SI-13）。
5. 峰值：metadata、图片、文件系统执行三者各自 ≤ 4（SI-06）。
6. 诊断：14 个模型（主 preview、主结果、4 × {重试 preview、重试轮结果、合并结果}）全部以 `NONE` 构建并渲染，`json.loads` 可解析，
   诊断中的 summary / outcome / retry_kind 与上表一致；主 preview 与最终合并结果另以 `BASENAME` 渲染；全部 JSON canary 扫描通过（SI-18）。
7. 确定性：整个 G-500 在第二棵全新树中再完整运行一次；14 个 `NONE` 诊断 JSON 逐字节相等（SI-07）。
8. 写操作观察记录中全部修改性路径 ∈ 允许集合（SI-15、SI-19）；网络陷阱零触发（SI-20）。

---

## 8. Regression Gates

### 8.1 三层门（冻结）

| 层 | 范围 | 通过规则 |
|---|---|---|
| G-T P4-C10 targeted | `tests/phase4_acceptance` | 0 failed、0 errors；正式证据环境下 **0 skipped**；全部 C10 测试被收集并执行。C10 测试中只有 Windows 原生断言（S-09 有根无盘符组、S-21 junction 与大小写变体组）允许以 `os.name != "nt"` 平台门控，只在第 9 节 PC-09 的非 Windows 补充运行中 skip |
| G-P4 Phase 4 contract / architecture suite | `tests/contract` + `tests/unit/{discovery,planning,publication,nfo,images,materialization,execution,orchestration,diagnostics}` | 0 failed、0 errors；skipped 测试集合 ⊆ 基线 skip 集合（按 nodeid） |
| G-FULL 全量 | 整个测试套件 | 0 failed、0 errors；`passed = 7767 + N_C10 + k`、`skipped = 40 − k`（k = 因第 9 节声明的可选证据环境而由 skip 变为执行的基线测试数，默认 0）；`collected = passed + skipped`；新增 skip = NONE |

基线（Frozen Base `c293ed75…` = P4-C9 Final Reviewed Package Head `9cd7bf56…` 的生产与测试 + docs-only 提交）：P4-C9 最终 Windows 验收
`7767 passed / 0 failed / 40 skipped / 0 errors`（Windows 11 10.0.26200 / Python 3.12.10）。S1 必须在同一正式证据环境中于 Design Accepted Head
上重新测得基线（第 8.3 节）；若与上述数字不同，以重新测得并记录的基线为准，并在 HANDOFF 中解释差异。

### 8.2 命令形式（冻结；均在 `fc2-organizer/` 下执行）

```text
G-T    python -m pytest tests/phase4_acceptance -q -p no:cacheprovider --basetemp=<JOB_TMP>/c10-gt-<run> --junitxml=<JOB_TMP>/c10-gt-<run>.xml
G-P4   python -m pytest tests/contract tests/unit/discovery tests/unit/planning tests/unit/publication tests/unit/nfo tests/unit/images tests/unit/materialization tests/unit/execution tests/unit/orchestration tests/unit/diagnostics -q -p no:cacheprovider --basetemp=<JOB_TMP>/c10-gp4-<run> --junitxml=<JOB_TMP>/c10-gp4-<run>.xml
G-FULL python -m pytest -q -p no:cacheprovider -rs --basetemp=<JOB_TMP>/c10-full-<run> --junitxml=<JOB_TMP>/c10-full-<run>.xml
```

* **Cache policy**：一律 `-p no:cacheprovider`（不写 `.pytest_cache`、不按 lastfailed 重排）；证据运行禁止 `--lf` / `--ff` / `-x` /
  `--maxfail` / `-k` / `--deselect`。
* **Basetemp policy**：每次运行使用唯一的、job 自有的临时目录；必须位于仓库工作树之外、与系统盘同卷；运行前不存在；
  不得指向任何真实用户目录。
* **JUnit XML**：只用于 skip / 结果集合的逐项对账（pytest 内置功能，不新增依赖）；不提交到仓库。

### 8.3 skip 基线对账（冻结）

1. S1：在 Design Accepted Head（相对 `c293ed75…` 只有 docs 差异）上执行一次 G-FULL，得到基线 skip nodeid 集合 `SKIP_BASE` 及每个
   skip 的原因文本。
2. 预期构成（P4-C8 / P4-C9 HANDOFF 记录）：execution symlink 权限 14、discovery symlink 权限 4、materialization symlink 权限 5、
   P4-C7 POSIX 原生证据 4 + 原生 POSIX link 1、原生跨卷 2（`FC2_EXECUTION_CROSS_VOLUME_ROOT` 未配置）、planning POSIX 路径形式 10，
   共 40。实际集合与此不同时，逐项记录。
3. S3：C10 head 上的 G-FULL skip 集合 `SKIP_C10` 必须满足 `SKIP_C10 ⊆ SKIP_BASE`；差集 `SKIP_BASE − SKIP_C10` 只能来自第 9 节声明的
   可选证据环境，并逐项列出。
4. `SKIP_BASE` 的**每一个** skip 都必须映射到第 10 节 Ledger 的一项（XD-B01..XD-B07），不得出现无解释的 skip。
5. 只比较数字不算对账；必须按 nodeid 比较。

### 8.4 失败与瞬时失败规则（冻结）

* 0 new unexpected failure、0 new unexpected error、0 new unexplained skip。
* 唯一已知的瞬时失败候选：`tests/unit/aggregation/test_agg_retry_execution.py::test_17_total_deadline_covers_attempt_backoff_and_retry_not_deadline_times_attempts`
  （Phase 3 墙钟断言，P4-C5 与 P4-C8 HANDOFF 各记录一次高负载瞬时失败）。若它失败：单独连续运行 3 次且全部通过，并再完整重跑 G-FULL
  一次且全部通过，才可判定为瞬时；两次结果都写入 HANDOFF。其它任何失败按第 13 节分类，不得以“瞬时”处理。
* 不得为通过而添加 skip / xfail、修改既有测试或调整断言。

---

## 9. Platform / Compatibility Gates

| ID | 门 | 规则 | 证据 | Blocking |
|---|---|---|---|---|
| PC-01 | Python 运行时权威 | 项目 `requires-python = ">=3.11"` 不变；C10 测试代码不得使用 3.12+ 专属 API | C10 架构测试 AST 禁止 `os.path.isjunction`、`pathlib.Path.walk`、`itertools.batched`、`typing.override`、PEP 695 `type` 语句等 3.12+ 名称；`pyproject.toml` 零差异 | YES |
| PC-02 | 正式证据环境 | Windows 11 / Python 3.12.x（验收证据环境，**不是**运行时支持边界） | 第 12.1 节环境记录；G-T / G-P4 / G-FULL 均在该环境执行 | YES |
| PC-03 | 依赖 | 唯一第三方运行时依赖 `httpx>=0.27,<0.28`；测试依赖 pytest；不新增依赖 | 记录 `httpx.__version__`、`pytest --version`；`pyproject.toml` 零差异 | YES |
| PC-04 | 既有架构守卫 | `tests/contract/` 下 11 个文件全部通过且**未修改**（C10 不新增 `src` 顶层 package，因此无需任何守卫更新） | G-P4；`git diff --name-only <Design Accepted Head>..<C10 head> -- tests/contract` 为空 | YES |
| PC-05 | Windows 路径语义（真实链路） | 盘符绝对 library root、casefold 冲突、junction 拒绝、NFC / NFD、大写扩展名 | S-09、S-12、S-21 | YES |
| PC-06 | 文件系统语义 | NTFS 同卷 rename 无替换；接缝强制跨卷；0 字节；跨卷流式 | S-12、S-13 | YES |
| PC-07 | 平台证据缺口 | Windows native symlink、POSIX native、kernel `O_NOFOLLOW`、native cross-volume、真实 ACL / 权限、长路径、UNC | 不在 P4-C10 关闭；按 Ledger XD-B01..XD-B07 处置；HANDOFF 记录既有相关测试在正式环境中的实际状态（执行 / skip 及原因） | 处置完整 = YES；关闭 = NO |
| PC-08 | 可选原生跨卷证据 | 只能经既有 P4-C7 测试与 `FC2_EXECUTION_CROSS_VOLUME_ROOT`，且必须满足第 12.3 节全部条件 | 若执行：记录 k 与结果；若未执行：XD-B04 保持 EVIDENCE GAP | NO（可选） |
| PC-09 | 补充证据（非阻塞） | 若主机可用：在 Python 3.11.x 上运行 G-T 与 G-P4；在 POSIX 主机上运行 G-T | 执行则记录；未执行则 XD-B02 / XD-B08 保持 EVIDENCE GAP | NO |

---

## 10. Phase 4 Exit Debt Ledger

分类（冻结）：

```text
A. MUST CLOSE BEFORE PHASE 4 CLOSURE   —— P4-C10 必须产出证据并关闭
B. ACCEPTED DEFERRED TO LATER PHASE    —— 不阻塞 Phase 4 Closure；目标阶段为规划性指派（依据治理文档第 14 节各阶段范围），
                                          该阶段冻结其 Contract 时须重新确认，P4-C10 不为其新增 authority
C. OUT OF PHASE 4 SCOPE                —— Phase 4 / v1.0 冻结的设计边界或 Phase 4 之前阶段的债务，不阻塞 Phase 4 Closure
```

原则：不静默忽略任何历史 evidence gap；不把历史 Deferred 擅自升级为 blocker（A 类只来自 Frozen Authority 或第 16 节 Exit Criteria
的直接要求）。

### 10.1 A 类：MUST CLOSE BEFORE PHASE 4 CLOSURE

| ID | 项 | Origin | Reason / Authority | P4-C10 证据 | 阻塞 Phase 4 Closure |
|---|---|---|---|---|---|
| XD-A01 | Phase 4 跨 package 500-item 全局门槛 | P4-C8 合同 §3、§37 | 被明确划归 P4-C10；v1.0 规格书 500 项注入失败验收 | G-500（第 7.4 节） | YES（直至 PASS） |
| XD-A02 | 跨包集成门槛对 diagnostics 的覆盖 | P4-C9 合同 §30 | “P4-C10 自行规划” | S-18、G-500 诊断断言 | YES |
| XD-A03 | 真实 Phase 3 引擎与真实图片 transport 从未在 P4-C8 链路中联合验证 | 设计调查 DF-01（P4-C8 §35 明确 engine / client 为脚本化替身） | Exit Criteria EC-03 要求跨包真实链路 | L-04、L-05、L-09（S-01..S-07、S-20、G-500） | YES |
| XD-A04 | Phase 4 级正式回归证据（最终验收 head 上） | 治理文档第 17 节；EC-08 | 各 package 证据只覆盖各自 head | G-T / G-P4 / G-FULL（第 8 节） | YES |
| XD-A05 | 40 个基线 skip 的逐项对账 | 各 package HANDOFF 只给数字 | EC-08 | 第 8.3 节 | YES |
| XD-A06 | Phase 4 Package Authority Matrix 机器核对 | 本合同第 4 节 | EC-01 | 坐标祖先关系、`src` 零漂移、状态行 CLOSED 的命令输出（施工计划第 7.1 节） | YES |
| XD-A07 | v1.0 关键验收中 Phase 4 层面的部分 | v1.0 规格书“关键验收” | “500 项注入单源 / 单项失败整体仍完成”、“Failed / Partial 可单独批量重刮”、“整理冲突、跨盘、目标不可写不得导致源视频静默丢失”在 Phase 4（离线、接缝级）层面的验证 | G-500、S-13/S-14/S-17、S-12（接缝跨卷）、S-14（接缝 `EACCES`）、S-21 | YES（Phase 4 层面）；真实环境部分见 XD-B04 / XD-B05 |

### 10.2 B 类：ACCEPTED DEFERRED TO LATER PHASE

| ID | 项 | Origin | Reason | Authority | Target Phase / Package | P4-C10 需要的证据 | 阻塞 |
|---|---|---|---|---|---|---|---|
| XD-B01 | Windows native symlink 证据 | P4-C1 §12、P4-C6 §22、P4-C7 §10 | 主机无 `SeCreateSymbolicLinkPrivilege`；不得为测试改系统安全设置（CLAUDE.md） | P4-C1 / C6 / C7 closure 接受为非阻塞缺口 | P7-C2 Platform / Edge Closure | 记录相关 skip（discovery 4、materialization 5、execution symlink 14 中的对应项）在正式环境的状态 | NO |
| XD-B02 | POSIX 原生主机证据 | P4-C7 §26.2、P4-C8 §9、P4-C9 §11（P4-C1 / P4-C6 曾有独立 POSIX 复查证据） | 正式证据环境为 Windows；基线测试大量面向 Windows | 各 closure 接受 | P7-C2 / P8-C1 | 记录 POSIX skip（P4-C7 原生 5、planning 10）；PC-09 可选补充 | NO |
| XD-B03 | kernel `O_NOFOLLOW` 原生证据 | P4-C7 §26.2 | Windows 无该标志 | P4-C7 closure 接受 | P7-C2 | 随 XD-B02 | NO |
| XD-B04 | 原生跨卷真实设备 | P4-C7 §17、§31；P4-C8 §9 | `FC2_EXECUTION_CROSS_VOLUME_ROOT` 未配置；主机第二卷含所有者个人文件（DF-06） | P4-C7 closure 接受 | P7-C2 | 接缝级跨卷（S-12）；可选原生（PC-08） | NO |
| XD-B05 | 真实权限 / ACL / 目标不可写 / 只读介质 | v1.0 规格书关键验收；P4-C7 §26.1 | Phase 4 只有接缝级与只读属性证据 | 治理文档第 14.5 节（P7-C2 覆盖权限） | P7-C2 | S-14 接缝级 `EACCES` | NO |
| XD-B06 | Windows 长路径（`MAX_PATH`） | P4-C1 §14、P4-C7 §26.1 | 未做长路径压力测试；不改写 `\\?\` | P4-C1 / C7 已知局限 | P7-C2 | 无 | NO |
| XD-B07 | UNC library root | P4-C7 HANDOFF §10 | 取决于主机管理共享 | P4-C7 closure 接受 | P7-C2 | 记录既有 UNC 用例在正式环境的状态 | NO |
| XD-B08 | Python 3.11 实际运行证据 | `pyproject.toml` `>=3.11`；正式证据环境为 3.12 | 运行时权威与证据环境不同 | P4-C9 计划 Python Runtime Authority | P8-C1 Compatibility & Packaging | PC-01 静态门；PC-09 可选 | NO |
| XD-B09 | fc2db_net `uploadDate` datetime 使 NFO fail closed | P4-C4 §18 / KL-2；P4-C8 §36 | 冻结的 fail-closed 行为；规范化需要独立合同 | P4-C4 closure 裁定非缺陷 | P6-C1 Real Batch Integration（真实 source 前裁决） | S-08 证明非法 release 被如实报告 | NO |
| XD-B10 | DNS rebinding / 公网名解析到私有地址 | P4-C5 §8.5、§12.11 | 冻结的明确不作声明；修复需新安全设计 | P4-C5 closure | P8-C2（SECURITY 文档记录）；若要防御须独立安全设计 | S-07 证明重定向到私有地址被拒绝（已覆盖部分） | NO |
| XD-B11 | F3、F5 | Phase 0 / Phase 1 独立复查（定义不在本仓库，仅记录 ID） | 延后的非阻塞 finding | `PHASE1_R1_HANDOFF.md`、`PHASE3_ENTRY_C0_HANDOFF.md`：“必须最迟在 Phase 5 集成之前关闭” | Phase 5 入口门槛（P5-C1 开工前） | 无；HANDOFF 如实记录“定义不在仓库内” | NO（Phase 4）；Phase 5 入口阻塞 |
| XD-B12 | P4-C1-R-02（MEDIUM）、R-03..R-05（LOW） | P4-C1 R1.11 | 主题：防 TOCTOU 的 scanner 重写、symlink / junction 架构扩展、扩展名策略；已由 P4-C7 源快照重验中和 | P4-C1 closure CARRIED / non-blocking；P4-C7 §33 | P7-C1 Real Filesystem Acceptance 复核 | 回归门保持 P4-C1 / P4-C7 全部通过 | NO |
| XD-B13 | P4-C2-R1-02 裸 `\\server` | P4-C2 R2.10 | 已在 P4-C7 §6.6 执行边界拒绝 | P4-C2 closure；P4-C7 §33 | P8-C2 已知问题清单复核 | 回归门 | NO |
| XD-B14 | 扩展的 Windows 保留名（planning finding） | P4-C2 R1.10 | 已在 P4-C7 §26.3 执行边界 fail closed | P4-C7 §33 | P8-C2 | 回归门 | NO |
| XD-B15 | P4-C3-R-01（测试名漂移）、P4-C3-R-02（正向对照覆盖） | P4-C3 closure | 可追溯性 / 测试强度，运行时行为正确 | P4-C3 closure LOW / CARRIED | P8-C2 | 无（C10 不修改既有测试） | NO |
| XD-B16 | P4-C4-R-01 容器子类纵深防御不对称 | P4-C4 C.3 | 未被证明的风险；需要冻结信任语义 | P4-C4 closure LOW / CARRIED | Phase 5 设计时复核（若 adapter 向 Phase 4 链路提供自构造对象），否则 P8-C2 | 无 | NO |
| XD-B17 | C3-N1..C3-N4（50-ID 门槛工具与证据可追溯性） | Phase 3 C4 / C4-R1 | 属于 v1.0 50-ID 验收证据 | Phase 3 HANDOFF LOW / OPEN | P8-C2 v1.0 Release Closure | 无 | NO |

### 10.3 C 类：OUT OF PHASE 4 SCOPE

| ID | 项 | Origin | Reason / Authority | 阻塞 |
|---|---|---|---|---|
| XD-C01 | durable resume / 断点 / cache / 持久化 | 早期 Phase 4 提示词“支持断点 / cache”；P4-C7 §34；P4-C8 §24.3、§33 | v1.0 冻结非目标；进程内 checkpoint RESUME 已交付（S-13） | NO |
| XD-C02 | 跨进程协调 / 跨进程同源唯一性 / 跨进程并发证据 | P4-C7 §25；P4-C8 §30.3 | v1.0 冻结边界（仍保证不覆盖、无静默源丢失、fail closed） | NO |
| XD-C03 | 恶意本地行为者的 TOCTOU | P4-C7 §25 | 字符串路径 API 固有限制，v1.0 威胁模型之外 | NO |
| XD-C04 | 实时进度 / PENDING · RUNNING 物化 | P4-C8 §11.4；P4-C9 §2 | v1.0 冻结非目标 | NO |
| XD-C05 | P4-C8 §37 已知局限（library_root 晚校验、资源硬限制、执行不可中断、致命异常无部分结果、番号只从 basename 识别、冲突组全阻断、metadata PARTIAL 不重刮） | P4-C8 §37 | 冻结的设计选择 | NO |
| XD-C06 | P4-C9 §30 延续项与 §31 已知局限（absolute path opt-in、诊断落盘、人类可读渲染等） | P4-C9 §30-31 | 冻结；人类可读渲染属于 Phase 5+ Adapter / UI | NO |
| XD-C07 | P4-C1 递归深度、symlink 文件排除、无并发声明 | P4-C1 §7、§10、§14 | 冻结的 v1.0 设计局限 | NO |
| XD-C08 | JPEG 只做结构校验、不转码 / 缩放 | P4-C5 §13、§16 | 冻结范围之外 | NO |
| XD-C09 | 不支持 hard link 的 POSIX 文件系统 fail closed；父目录不 fsync | P4-C6 §7、§25.5 | 冻结的兼容性边界 | NO |
| XD-C10 | P2-R-05、P2-R-06（探测工具） | Phase 2 / Phase 3 Entry C0 | 工具层面 LOW；与 Phase 4 无关 | NO |
| XD-C11 | P2-R-07（adapter 失败结果 `elapsed_ms = 0`） | Phase 2 | Phase 4 侧义务已由 P4-C9 §12.7 满足（只发布 engine 测量的 `SourceAttempt.elapsed_ms`）；底层 Phase 2 行为 CARRIED | NO |
| XD-C12 | C4-N1（durable batch id） | Phase 3 C4-R1 | 仅在持久化时需要；持久化为 v1.0 非目标 | NO |
| XD-C13 | C4-R1-N1..N3（非 `MultiSourceEngine` 生产者、恶意 metaclass、诊断信息丢失） | Phase 3 C4-R1 / C5 | Phase 3 batch 层债务，Phase 4 未依赖相应机制 | NO |
| XD-C14 | C5-R1-L1 | Phase 3 C5-R1（定义不在本仓库） | Phase 3 债务；HANDOFF 如实记录“定义不在仓库内” | NO |
| XD-C15 | Phase 3 C5 已记录未修复的资源控制局限（熔断状态只在内存、无 `Retry-After`、静态 host 限制、单事件循环 governor） | `PHASE3_C5_HANDOFF.md` §13 | Phase 3 设计边界 | NO |
| XD-C16 | Amane 集成、CLI、UI | v1.0 规格书；治理文档第 14.3 节以后 | Phase 5+ | NO |

### 10.4 已闭合 / 已满足的入口门槛（只做回归确认，不重开）

| 项 | 闭合位置 | P4-C10 证据 |
|---|---|---|
| P4-C2 `metadata.number != canonical_number` 身份缺口 | P4-C3 §6 | 回归门；S-04 / S-20 |
| C2-L2、P2-R-10 | P4-C3 §14、§16 | 回归门 |
| OrganizePlan 操作图加固（executor 入口门槛） | P4-C7 §6 | 回归门 |
| overwrite 执行器语义（NEVER） | P4-C7 §23 | SI-02 |
| P4-C1-R-01 / R1-01 / R2-01、P4-C2-GOV-01..03 / R1-01、P4-C5-R-01 / R-02、P4-C7 S1-S5 findings、P4-C8-S6-R-01、P4-C9-L1-01、P4-C9-WIN-01 | 各自 HANDOFF closure | 回归门 |

---

## 11. Non-Vacuity / Mutation Requirements

### 11.1 原则（冻结）

* 每个 Blocking 门都必须证明“会抓错”：在测试进程内植入缺陷（mutant），对应门必须失败。
* mutant **只存在于测试进程内**：通过 `monkeypatch` 包装 / 替换（第 11.3 节允许的表面），或像 P4-C9 那样把生产源码文本单点替换后
  在内存中编译为一次性模块；**绝不**写盘、**绝不**提交。
* 不新增第三方 mutation 框架或任何依赖。
* 杀死判据：未植入 mutant 时同一场景通过（positive control）；植入后对应门抛出 `AcceptanceGateViolation`（`AssertionError` 子类），
  或在门期望成功之处观察到类型化 fail closed 而使场景断言失败。
* mutation 测试是常驻测试（`tests/phase4_acceptance/test_p4_acceptance_mutations.py`），随 G-T 一起执行，形式为
  `with pytest.raises(AcceptanceGateViolation): ...`。
* 恢复证明：每个 mutant 测试结束后断言被替换的绑定名对象 `is` 原对象；S3 以 `git hash-object --no-filters` 对比 `src/**` 全部文件与 HEAD
  blob，并确认 `git status --porcelain` 为空。

### 11.2 必须的 mutant（冻结；每个至少杀死一次，HANDOFF 记录失败用例与失败数）

| ID | 类别 | mutant（测试进程内） | 必须失败的门 |
|---|---|---|---|
| M-01 | source loss | 包装 `fc2_organizer.orchestration.execute.execute_filesystem`：对一个条目在真实执行返回 `SUCCESS` 后删除其最终媒体 | SI-01 |
| M-02 | overwrite | `fc2_organizer.execution._fs._FS.rename` 替换为 `os.replace`（P4-C7 变异 A1 的跨包复现） | SI-02（S-21 / S-11 预置目标被覆盖） |
| M-03 | collision | 使 Phase A 冲突分组失效（包装 `fc2_organizer.orchestration.preview` 中绑定的 `recognize`，去掉冲突标记） | SI-10（S-10 / G-500 GF） |
| M-04 | path escape | 包装 `execute_filesystem`：执行后在 `library_root` 之外（同一 `tmp_path` 内）创建一个文件 | SI-15 |
| M-05 | wrong retry ownership | monkeypatch `ItemExecution.retry_kind` 使 RESUME 与 FRESH_REEXECUTE 对调 | SI-12（S-17） |
| M-06 | wrong checkpoint | 包装 `execute_filesystem`：对 PARTIAL 结果把 `checkpoint` 替换为另一条目的 checkpoint（`object.__setattr__`） | SI-13（S-13 RESUME 不再收敛） |
| M-07 | partial-result corruption | 包装 `merge_retry`（场景所用绑定）：丢弃一个条目或以旧代条目替换 | SI-22（S-17 / G-500 账目） |
| M-08 | diagnostics redaction | monkeypatch 诊断渲染使输出附带 canary（或把默认路径策略改为 `BASENAME`） | SI-18（S-18） |
| M-09 | cross-package wiring | 包装 `fc2_organizer.orchestration.stages.build_artifact_requests`：交换 poster 与 fanart 内容；另一变体包装 `render_movie_nfo` 渲染另一条目的记录 | L-10 图片字节身份 oracle；L-08 NFO oracle |
| M-10 | ordering / determinism | 在结果装配边界把条目改为完成顺序（或在诊断渲染前反转条目） | SI-07（S-19） |
| M-11 | bounded concurrency | 执行 worker 改为每条目一线程（包装 `execute` 的并发入口） | SI-06（S-22） |
| M-12 | source isolation | 包装真实 `MultiSourceEngine.aggregate`：任一 source 失败即返回 `FAILED` | SI-04（S-03 / G-500 GB） |
| M-13 | temporary leftovers | 包装 `execute_filesystem`：执行后在目标目录留下一个未报告的 `.fc2tmp-<32hex>.part` | SI-14 |
| M-14 | preview mutation | 包装 preview 阶段绑定（例如 `preflight_execution`）：在只读阶段创建一个目录 | SI-21 |

另外：harness 自检测试（施工计划 S1）必须证明每个共享门在“干净”输入上通过、在植入违规的输入上失败（门函数层面的 positive /
negative control），以及 socket 陷阱、写操作观察包装、sandbox guard 确实生效。

### 11.3 允许的 mutation 表面（冻结）

只允许在 `tests/phase4_acceptance/test_p4_acceptance_mutations.py` 与 harness 自检测试中：

* `monkeypatch` 替换 / 包装 `fc2_organizer.orchestration.{preview,stages,execute,retry,recognition}` 模块级绑定名（对下层公开函数的包装，
  call-through 后植入缺陷）；
* `monkeypatch` 替换 `fc2_organizer.execution._fs._FS`、`fc2_organizer.materialization.atomic._FS` 的属性（P4-C7 §31、P4-C8 §34.2 授权接缝）；
* `monkeypatch` 模型类的派生 property（只在测试进程内）；
* `monkeypatch` `fc2_organizer.diagnostics` 模块级函数绑定；
* 测试替身（脚本化 adapter、MockTransport handler）内部的缺陷植入。

不得修改任何生产源文件，不得把 mutant 留在任何非 mutation 测试中。

---

## 12. Test Environment Requirements

### 12.1 正式证据环境（冻结）

```text
操作系统     : Windows 11（记录 platform.platform() 与 NT 版本号）
Python       : 3.12.x（记录 python -VV）
依赖         : httpx 0.27.x（记录 __version__）；pytest（记录版本）
文件系统     : 系统盘 NTFS（记录 basetemp 所在卷）
权限         : 普通用户；不提权、不启用 Developer Mode、不修改组策略、不关闭 Windows Defender 或任何安全功能（CLAUDE.md）
网络         : 测试不访问网络（SI-20）
```

HANDOFF 必须记录上述全部值，以及 symlink 权限是否可用、`FC2_EXECUTION_CROSS_VOLUME_ROOT` 是否设置。

### 12.2 “真实安全场景”的边界（冻结）

所有 destructive / filesystem acceptance（move、rename、materialization、cleanup、mkdir、unlink）**只能**作用于：

```text
pytest tmp_path 下创建的临时目录
测试自己生成的可丢弃 fixture
测试自己生成的合成源文件
```

明确禁止：

```text
真实用户媒体目录、下载目录、媒体库
任何真实生产库
不可恢复文件
未经隔离的数据
用户主目录、仓库工作树、系统目录
主机上的其它卷（第 12.3 节唯一例外除外）
```

强制机制：harness 的 sandbox guard 对传给 `discover_media`、`BatchOrchestrator(library_root=…)` 的每个路径，以及写操作观察记录中的
每个修改性路径，断言其位于当前测试的 `tmp_path` 之下；违反即 `AcceptanceGateViolation`。C10 架构测试禁止 C10 测试源码中出现
盘符根字面量与 `os.path.expanduser` / `Path.home()` 调用。

### 12.3 可选原生跨卷证据的唯一例外（冻结）

只有在**全部**条件满足时才允许执行，且只能经既有 P4-C7 测试（`test_native_cross_volume_integrated_execution` 等）进行，P4-C10 不新增此类测试：

1. 项目所有者对一个**专门新建、唯一命名、初始为空**的目录给出明确书面授权（设计发现 DF-06：P4-C1 R3 记录主机第二卷存放所有者的
   真实个人文件，任何触碰都需要明确授权）；
2. `FC2_EXECUTION_CROSS_VOLUME_ROOT` 指向该目录；
3. 运行前后对该目录的父目录做顶层列举对比并记录；
4. 测试只在该目录内创建与删除自己的条目；
5. 任一条件不满足即不执行，XD-B04 保持 EVIDENCE GAP（非阻塞）。

### 12.4 Oracle 独立性（冻结）

* C10 的期望值与门函数由 P4-C10 独立实现，**不** import `tests/unit/**` 下的任何 helper（避免与被验收 package 共享同一缺陷的 oracle；
  并且 `tests/unit` 不在 C10 目标运行的 import 路径上）。
* 允许只读复用 `tests/support/**`（离线 `FakeHttpClient`、`scripted_adapters`）与 `tests/fixtures/**`；不得修改它们。
* 允许 import 被验收 package 的公开 API 与第 12.6 节授权接缝。

### 12.5 写操作观察（冻结）

harness 以**只观察、call-through**的包装记录修改性调用：`fc2_organizer.execution._fs._FS` 与 `fc2_organizer.materialization.atomic._FS`
的修改性属性，以及 `builtins.open` / `io.open` / `os.open` 的写模式打开。包装不得改变返回值、异常或调用顺序；harness 自检测试证明
包装生效且透明（同一场景包装前后结果投影相等）。

### 12.6 授权故障注入接缝（冻结）

`fc2_organizer.execution._fs._FS`（含 `device_of`）、`fc2_organizer.materialization.atomic._FS`、
`fc2_organizer.orchestration.execute.execute_filesystem`（包装真实函数，P4-C8 §34.2）、脚本化 `SourceAdapter` 脚本、
`httpx.MockTransport` handler。第 11.3 节的其它表面只用于 mutation。

### 12.7 测试隔离（冻结）

既有架构守卫会清理 `sys.modules` 而不恢复（P4-C5 / P4-C6 / P4-C9 HANDOFF 记录的测试顺序缺陷）。C10 测试必须在模块顶层 import 全部
`fc2_*` 名称，不使用函数内局部 import；G-FULL 中 C10 测试在任意收集顺序下都必须稳定。

---

## 13. Failure Classification（冻结）

| 类 | 定义 | 处理 |
|---|---|---|
| F0 环境 / 基础设施 | basetemp 权限、主机负载、工具缺失；与被测代码无关 | 修复环境后重跑；如实记录；不得改测试或生产 |
| F1 C10 测试缺陷 | C10 自己的测试 / oracle / fixture 错误，被测代码符合 Frozen Contract | 在施工中修复 C10 测试；若在 Level 1 Review 中发现，进入 C10-R1（只改 `tests/phase4_acceptance/**`） |
| F2 普通生产缺陷 | CLOSED package 生产行为偏离其 Frozen Contract；修复只需恢复合同语义，不需要任何 authority amendment | 不得顺手修；记录；按第 14、15 节进入 C10-R1（触发 U-1，C10-R1 升级为 C 类治理事件） |
| F3 需要 authority 的生产缺陷 | 修复需要 Contract semantic amendment、Construction Plan scope amendment、安全设计、公开 API 变化或风险边界变化 | **停止 Final Acceptance**；先解决 authority（独立复查）；不得以 C10-R1 修复 |
| F4 合同冲突 | 两个 Frozen Contract 之间、或本合同与 CLOSED 合同之间的语义冲突 | 停止；记录；治理裁决 |
| F5 新观察到的证据缺口 | 历史上未记录的平台 / 证据缺口 | 进入第 10 节 Ledger 并分类；若属于 A 类则阻塞 |
| F6 瞬时失败 | 仅第 8.4 节列出的已知墙钟测试 | 按第 8.4 节规则；其它一律不按瞬时处理 |

---

## 14. CLOSED Package Modification Rules（冻结）

1. Final Acceptance **默认不修改** P4-C1..P4-C9 的任何生产代码、合同、施工计划或 HANDOFF。
2. 验收中发现的生产问题，**不得**在验收过程中顺手修复；先按第 13 节分类并记录：
   * affected CLOSED package；
   * affected Frozen Contract 与条款；
   * 复现场景与最小复现；
   * regression scope（受影响 package 的全部测试、G-P4、G-FULL）；
   * compatibility impact；
   * safety impact。
3. 任何对 CLOSED package `src/**` 的改动都自动构成治理文档第 13 节的高风险治理事件（升级门 U-1）：
   * 必须说明为什么必须修改、影响哪个历史 Contract、回归范围、兼容性影响、安全影响；
   * 修复必须**恢复**被引用合同的既有语义，不得改变它；
   * 必须经独立 Review（该 C10-R1 的 Review 必须显式审计 CLOSED package 改动，不只是增量）；
   * 被修改 package 的 HANDOFF / 合同 / 施工计划**不修改**；改动记录写入 P4-C10 HANDOFF 的“CLOSED package amendment record”。
4. 需要 authority amendment 的问题（F3 / F4）：停止 Final Acceptance，先解决 authority；不得越权。

## 15. C10-R1 Rules（冻结）

* Level 1 Final Acceptance Review FAIL 后，同根因或范围明确、且不需要新的架构设计或 Contract authority 的全部 findings 统一进入**一个**
  C10-R1，一次闭合全部已知 findings 并检查 direct regression（治理文档第 12.1 节）。不得逐项开发、逐项 Review。
* 只改 `tests/phase4_acceptance/**` 与 P4-C10 docs 的 C10-R1：保持 Risk Class B；增量 Review。
* 含 CLOSED package 生产改动的 C10-R1：Risk Class 升级为 C（U-1）；满足第 14 节第 3 条全部要求；回归范围 = 受影响 package 全部测试 +
  G-T + G-P4 + G-FULL；并重新执行受影响 package 原有的 mutation / 非空洞性证据中与改动相关的部分。
* 任一 finding 需要 Contract amendment、Plan scope amendment、新安全设计或新公开 API 裁决：先解决 authority，再实施（治理文档第 12.2 节）。
* C10-R1 不得借机加入任何新功能（第 1.3 节）。

---

## 16. Phase 4 Exit Criteria（冻结）

只有下列**全部** Blocking 项满足，才允许宣布 `Phase 4 = CLOSED`：

| ID | 条件 |
|---|---|
| EC-01 | P4-C1..P4-C9 均 CLOSED，第 4.1 节坐标全部机器核对通过（祖先关系、`src` 自各 Final Reviewed Code Head 零漂移，或任何漂移都来自经第 14 节处理的 C10-R1） |
| EC-02 | P4-C10 Contract 与 Construction Plan 经独立 Design Review PASS（Design Accepted Head 已建立） |
| EC-03 | Cross-Package Integration Gate PASS：L-01..L-14 全部有 P4-C10 真实链路证据 |
| EC-04 | Acceptance Scenario Matrix S-01..S-22 全部 PASS |
| EC-05 | G-500 PASS（含全部冻结计数与确定性重跑） |
| EC-06 | Phase 4 Safety Gate PASS：SI-01..SI-22 全部 Blocking 项 PASS |
| EC-07 | Non-Vacuity PASS：M-01..M-14 全部被杀死；harness 正 / 负向对照通过；恢复证明通过 |
| EC-08 | Regression PASS：G-T、G-P4、G-FULL 在正式证据环境中全部通过；skip 基线逐项对账通过；新增 skip = NONE；0 failed、0 errors |
| EC-09 | Compatibility disposition complete：PC-01..PC-06 PASS；PC-07..PC-09 处置完整 |
| EC-10 | Exit Debt Ledger complete：XD-A01..XD-A07 全部 CLOSED 并有证据；每个 B / C 项都有 disposition；无未处置的阻塞性 evidence gap |
| EC-11 | Production Modified = NO；或每一处 CLOSED package 生产改动都已按第 14、15 节处理且独立 Review PASS |
| EC-12 | 全部 P4-C10 blocking findings CLOSED |
| EC-13 | Final HANDOFF 按第 17 节完整 |
| EC-14 | Final Reviewed Acceptance Head 已建立（P4-C10 Level 1 Final Acceptance Review PASS） |
| EC-15 | Phase 4 Final Closure Docs 经独立 docs-only closure review PASS（它确立下一阶段输入边界与 Phase 5 Frozen Base Candidate，治理文档第 11.2 节不可压缩） |

在 EC-15 满足之前，任何文档都不得写 `Phase 4 = CLOSED`。

---

## 17. Final HANDOFF Requirements（冻结）

`docs/review/P4_C10_HANDOFF.md`（S3 新增，中文）分两部分：

**Part I —— P4-C10 验收证据**

1. 坐标：Frozen Base、Planning Parent、Governance Authority、Design Candidate、Design Accepted Head、S1 / S2 / S3 提交、C10 Acceptance Head、
   Review Range；提交线性证明。
2. 完整 diff scope：`git diff --stat <Design Accepted Head>..<C10 head>`；`-- fc2-organizer/src` 为空的证明（或 C10-R1 amendment record）；
   `-- fc2-organizer/tests` 只含 `tests/phase4_acceptance/**`。
3. Contract -> 测试映射：第 5、6、7、9、11 节每个 ID -> 测试文件 -> 测试名。
4. 环境记录（第 12.1 节全部字段）。
5. 测试数字：G-T、G-P4、G-FULL（命令、passed / failed / skipped / errors / collected、耗时）；基线测量结果；瞬时失败记录。
6. skip 基线对账表（nodeid、原因、对应 Ledger 项；`SKIP_BASE` 与 `SKIP_C10` 的集合比较）。
7. Cross-package acceptance summary（L-01..L-14 逐项）。
8. Safety invariants summary（SI-01..SI-22 逐项结果）。
9. Scenario 与 G-500 结果（逐项计数、确定性重跑结果、峰值、诊断模型数量）。
10. Mutation / non-vacuity 表（M-01..M-14：mutant、表面、杀死的门、失败用例、失败数）；恢复证明（`git hash-object --no-filters` 对比、`git status --porcelain`）。
11. Platform / compatibility evidence（PC-01..PC-09）。
12. Exit Debt Ledger 最终状态（第 10 节每项）。
13. 风险升级门 U-1..U-7 核对；`Production Modified`；CLOSED package amendment record（若有）。
14. known limitations（第 19 节）与 evidence gaps。

**Part II —— Phase 4 Final HANDOFF**

1. Phase 4 Package Authority Matrix（第 4 节，补入 P4-C10 行）。
2. P4-C1..P4-C10 final heads（Final Reviewed Code / Package Head 与 Final Closure Docs Head）。
3. Phase 4 能力总览（第 5.1 节链路）。
4. safety invariants summary、platform / compatibility evidence、full test evidence、skip baseline、mutation / non-vacuity 摘要。
5. Exit Debt Ledger（含 accepted deferred items 与 known limitations）。
6. Phase 5 input boundary（第 18 节）。
7. final closure coordinates（Final Reviewed Acceptance Head、Phase 4 Final Closure Docs Head、Phase 5 Frozen Base Candidate）。

Part II 中“Phase 4 = CLOSED”与 final closure coordinates 只能在 EC-14 满足后的 Final Closure Docs 提交中写入，并以 EC-15 为生效条件。

---

## 18. Phase 5 Input Boundary（冻结）

P4-C10 只建立 Phase 4 → Phase 5 的**已验收输入边界**；不开始 Phase 5，不设计 P5-C1，不实现 Amane adapter，不修改任何 Phase 5 代码。

### 18.1 Phase 4 提供给 Phase 5 的已验收能力

| 能力 | 公开入口 | 验收依据 |
|---|---|---|
| 递归媒体发现 | `fc2_organizer.discovery.discover_media` | P4-C1 + L-01 |
| 批量预览 / 显式执行 / 重试 / 合并（整理闭环的唯一组合入口） | `fc2_organizer.orchestration.BatchOrchestrator`（`preview` / `execute` / `preview_retry`）、`merge_retry` 及第 7.1 节公开模型 | P4-C8 + L-02..L-13 + G-500 |
| 结构化诊断 | `fc2_organizer.diagnostics.build_preview_diagnostics` / `build_execution_diagnostics` / `render_diagnostics_json` | P4-C9 + L-14 |
| 下层构件（planning / publication / nfo / images / materialization / execution） | 各自公开 API | P4-C2..P4-C7；作为 orchestration 的构件已在真实链路中验收 |
| FC2 Metadata Core（Phase 1-3） | `fc2_metadata_core` 公开 API（`normalize`、`MultiSourceEngine`、`NormalizedMetadata`、`BatchScheduler`） | Phase 1-3 closure；Phase 4 只在 P4-C3 授权修改了 C2-L2 与 P2-R-10；L-04 / L-05 |

### 18.2 Phase 5 必须继承、不得改变的冻结语义

overwrite = NEVER；no silent source loss；fail closed；source / item isolation；bounded concurrency；确定性；默认 `PathPolicy.NONE`；
无持久化；`fc2_organizer` / `fc2_metadata_core` 不 import `amane`（既有架构守卫）；Phase 5 不修改 Phase 4 生产代码（如需修改，按治理文档第 13 节）。

### 18.3 Phase 5 入口门槛（由 Phase 4 传递，不由 P4-C10 解决）

* XD-B11 F3 / F5：最迟在 Phase 5 集成之前关闭；定义不在本仓库，Phase 5 规划者须先取得其原始定义。
* XD-B16 P4-C4-R-01：若 adapter 向 Phase 4 链路提供自构造的 `NormalizedMetadata` / `OrganizePlan`，须先裁决容器信任语义。
* 第 10.2 / 10.3 节其余项按各自目标阶段处理。

### 18.4 Phase 4 不提供的能力（Phase 5 不得假定存在）

durable resume / 持久化、跨进程协调、实时进度流、CLI / UI、人类可读诊断渲染、Amane `MediaMetadata` 映射、DNS rebinding 防御。

### 18.5 Phase 5 Frozen Base Candidate

= Phase 4 Final Closure Docs Head（EC-15 PASS 后生效）。Phase 5 自己的 Contract / Construction Plan 冻结时自行确认其 Frozen Base。

---

## 19. Known Limitations（P4-C10 自身）

* P4-C10 证据全部离线、合成：脚本化 `SourceAdapter`、既有 fixture HTML + `FakeHttpClient`、`httpx.MockTransport`；不证明线上 source
  当前可用（属于 Phase 2 探测、P6、P8）。
* 正式证据环境是单一 Windows 主机；POSIX 与 Python 3.11 只有可选补充证据（XD-B02、XD-B08）。
* 原生 symlink、原生跨卷、真实 ACL、长路径、UNC 不在 P4-C10 关闭（XD-B01..XD-B07）。
* mutation 是在跨包边界上的定向 mutant，不是穷举式 mutation testing。
* 确定性只针对冻结的 fixture 证明，不是对全部输入的证明。
* G-500 的文件很小（几字节到几 KiB）；大文件流式行为以 P4-C7 既有门槛与 S-12 的 1 MiB + 1 跨卷用例为准。
* 本合同不对 Amane 宿主行为作任何声明。

---

## 20. Status

```text
P4-C1 .. P4-C9                 : CLOSED
P4-C10 Frozen Base             : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c
Governance Authority           : 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
P4-C10 Design                  : DESIGN CANDIDATE —— INDEPENDENT DESIGN REVIEW REQUIRED
P4-C10 Frozen Contract         : NOT YET ACCEPTED（本文件）
P4-C10 Construction Plan       : NOT YET ACCEPTED
Design Accepted Head           : NOT ESTABLISHED
S1 / S2 / S3                   : NOT STARTED
P4-C10 Implementation          : NOT STARTED
Production Modified            : NO
Final Reviewed Acceptance Head : NOT ESTABLISHED
P4-C10                         : NOT CLOSED
Phase 4                        : NOT CLOSED
Phase 5                        : NOT STARTED
```

---

## 附录 A. 设计调查发现（Design Findings）

| ID | 发现 | 处置 |
|---|---|---|
| DF-01 | Frozen Base 上没有任何测试把真实 `MultiSourceEngine` 或真实 `HttpxImageClient` 接入 `BatchOrchestrator`（P4-C8 §35 明确使用脚本化替身） | XD-A03；L-04 / L-05 / L-09 由 C10 测试补足，无需生产改动 |
| DF-02 | P4-C8 合同 §3、§37 把“跨 package 的 Phase 4 500-item 全局门槛”划归 P4-C10 | 按 authority 优先级纳入 G-500，与任务提示词“少量 fixture”不冲突（G-500 文件极小） |
| DF-03 | F3 / F5 的定义不在本仓库，只记录 ID 与“最迟 Phase 5 集成前关闭” | XD-B11；Phase 5 入口门槛 |
| DF-04 | C5-R1-L1 的定义不在本仓库 | XD-C14，如实记录 |
| DF-05 | 验收不需要任何新生产能力：全部链路都可由既有公开 API、既有授权接缝与既有 `tests/support` 组装 | Production Modified = NO；无 DESIGN FINDING / SCOPE PROBLEM |
| DF-06 | P4-C1 R3 记录主机第二卷存放所有者真实个人文件 | 第 12.2、12.3 节；可选跨卷证据需要所有者明确授权 |
| DF-07 | 治理文档文件头仍为“R1 IMPLEMENTED — INDEPENDENT GOVERNANCE REVIEW REQUIRED”，而 P4-C9 冻结计划记录其 ACCEPTED / CLOSED（`3b9d39e…`），且文件自此未变 | 不冲突；P4-C10 不修改治理文档；非阻塞观察 |
| DF-08 | 早期“Phase 4 — 批量引擎”提示词条目与冻结合同之间的差异 | 第 2.3 节对账；durable 断点 / cache = XD-C01 |
| DF-09 | P4-C1..P4-C9 的 `src` 自各 Final Reviewed Code Head 起零漂移 | EC-01 的设计阶段预检通过 |
