# FC2 Organizer — 加速版治理规则 v2

```text
文档状态              : ACTIVE（Owner Approved；仓库 amendment 待独立治理复查）
Owner Approved        : YES
Effective From        : P4-C9 及之后尚未冻结的 Phase / Package
Non-Retroactive       : YES
Governance Amendment  : IMPLEMENTED — INDEPENDENT GOVERNANCE REVIEW REQUIRED
Governance Base       : a662659dfd6e801531b14af7913d84a5f9f859e2（P4-C8 Final Closure Docs Head）
P4-C9 Frozen Base     : a662659dfd6e801531b14af7913d84a5f9f859e2
P4-C9                 : NOT STARTED
```

项目所有者已正式批准本规则。本文件是该决策在仓库中的书面表达；只有本 amendment 经独立治理复查 PASS 后，
其 Final Reviewed Governance Head 才成为仓库中的 Project Governance Authority Head。在此之前，仓库中的治理权威尚未生效。

## 1. 目标与核心原则

目标：扩大施工颗粒度，减少治理往返，同时保持最终验收强度不变。

核心原则：

* **减少过程，不减少证据。**
* **扩大施工包，不扩大风险。**
* **减少人工等待，不降低正确性、安全性和最终验收标准。**

## 2. 适用范围

本规则只调整以下内容：

* 施工颗粒度（一个 C 覆盖多大的工作）；
* Review 的时点；
* 纯状态型 docs-only 循环；
* 人工等待次数；
* session / handoff 的数量。

本规则**不得**用于：

* 削减既定功能；
* 降低 correctness；
* 降低 safety；
* 降低 auditability；
* 减少必要测试；
* 绕过 independent review；
* 绕过 finding closure。

## 3. 绝对不可降低的门槛

以下门槛全部保持原标准。加速治理**不能**成为降低其中任何一项的 authority：

* Frozen Contract；
* no silent source loss（不得静默丢失源文件）；
* overwrite = NEVER；
* fail closed；
* source isolation（单一 source 失败不影响其它 source）；
* item isolation（单一影片失败不阻断其它影片）；
* bounded concurrency（有界并发）；
* deterministic behavior（确定性行为）；
* 必要的 targeted / contract / full tests；
* 必要的平台证据；
* 独立 Review；
* finding closure。

## 4. Authority 优先级（冻结）

```text
Frozen Contract
>
Frozen Construction Plan
>
docs/PROJECT_GOVERNANCE_ACCELERATION.md（本文件）
>
Task Prompt
```

解释：

* 本规则负责指导“尚未冻结的新工作应该怎样拆包、何时 Review”。
* 一旦某 Package 自己的 Contract / Construction Plan 已经冻结，不得用本规则绕过其中已冻结的、更细的治理要求。
* 如果既有 Frozen Contract / Frozen Construction Plan 明确要求更细的 Review，以既有 Frozen Authority 为准。
* 本规则与任何 Frozen Contract / Frozen Construction Plan 冲突时，后者优先。

## 5. 生效边界

* **不追溯**修改已经 CLOSED 的 package。
* **不追溯**修改已经冻结的 Contract / Construction Plan。
* P4-C8 已经 CLOSED，完全不受本规则追溯影响；其 Contract、Construction Plan 与 HANDOFF 保持原样。
* 本规则从 P4-C9 开始生效，并适用于以后 Phase 5、Phase 6、Phase 7、Phase 8 中尚未冻结的新规划。

## 6. 新默认施工模型

正式默认流程：

```text
设计 / Contract 冻结
  -> 一个较大的 C，完成一个完整用户能力 / 纵向技术闭环
  -> 开发者连续完成 C 内部的 S1 / S2 / S3 ...
  -> package-level 完整测试与证据
  -> 一次独立 Level 1 Review
  -> 必要时统一的 R1 / R2
  -> Final Closure
```

不再默认采用以下流程，除非风险本身要求：

```text
S1 -> Review -> docs closure -> S2 -> Review -> docs closure -> S3 -> ...
```

## 7. C 的正确粒度

一个 C 优先对应：

* 一个完整用户能力；
* 一条完整纵向技术链；
* 一个可独立验收的业务闭环。

禁止因为不同文件、不同模块、models、config、mapping、errors、tests、packaging、docs 等**纯代码组织原因**，机械地拆成多个 C。

对比示例（Owner 给出）：

```text
错误：
  C1 models
  C2 config
  C3 mapping
  C4 errors
  C5 tests
  C6 packaging

优先：
  C1 Adapter 输入到输出完整闭环
  C2 真实宿主兼容与发布验收
```

## 8. 风险分级

### 8.1 A 类：低风险

默认直接并入当前 C，**不得**单独建立 C：

* API wiring；
* model mapping；
* config mapping；
* adapter glue；
* error translation；
* public export；
* architecture guard；
* 测试补强；
* 文档；
* packaging metadata；
* install guide；
* compatibility matrix docs。

### 8.2 B 类：中风险

包括：

* 新 adapter；
* 新 service / client glue；
* retry orchestration；
* diagnostics；
* progress / status aggregation；
* compatibility bridge。

规则：

* 允许一个 C 内部划分 S1 / S2 / S3，但默认**连续施工**。
* 内部每个 S 仍可以拥有 developer checkpoint、单元测试、contract test、mutation / non-vacuity、静态检查和独立 commit。
* 普通的 S1 / S2 / S3 **不自动触发**独立 Review、开发停止或 docs closure。
* 整个 C 完成后统一进行一次 Independent Level 1 Review。

### 8.3 C 类：高风险

包括：

* 删除用户文件；
* 覆盖用户文件；
* 移动用户文件；
* 原子文件系统操作；
* source-loss 风险；
* persistence；
* durable resume；
* 跨进程 locking；
* race / concurrency ownership；
* irreversible migration；
* security boundary；
* 大规模公共数据契约变化；
* 修改多个已经 CLOSED 的 package 的行为。

C 类可以继续细拆，可以设置中间 Review，可以设置独立安全 gate。**不得**以“Acceleration v2”为理由取消必要的安全 Review。

### 8.4 风险必须显式声明

从 P4-C9 起，每份新的 Construction Plan 在冻结前必须显式声明：

* Risk Class：A / B / C；
* 为什么采用当前 C 粒度；
* 为什么不能与前一个 C 合并；
* 为什么不需要继续细拆；
* 是否需要 C 内中间独立 Review。

施工中允许风险升级（A -> B、B -> C）。没有治理依据时，**不得**自行降级（C -> B、B -> A）。

## 9. C 内中间独立 Review 的触发条件

只有以下情况默认需要 C 内中间独立 Review：

1. 下一步骤建立在不可逆的安全边界上；
2. 前一步定义新的 Frozen Contract；
3. 后一步的错误可能污染大量已有代码；
4. 风险显著高于减少一次 Review 所节省的时间；
5. 涉及 C 类的 source-loss / overwrite / persistence / locking / migration / security 核心边界。

不能因为“过去每个 S 都 Review”就继续机械地 Review。

## 10. Review 默认策略

正式默认：一个 C -> 完整 implementation -> 完整 tests / evidence -> 一次独立 Level 1 Review。

* 独立 Review **不会被取消**；减少的是 Review **次数**，不是 Review **强度**。
* C-level Reviewer 必须能够审计：完整线性 diff、完整 Contract mapping、完整测试证据、完整安全不变量、必要的
  mutation / non-vacuity、必要的平台证据，以及 evidence gaps。

## 11. 文档治理压缩

### 11.1 可以压缩的纯状态 docs

纯状态型 docs-only commit 应尽量减少。如果文档只记录 `IMPLEMENTED`、`REVIEW PASS`、`CLOSED`、Final Reviewed Head 等状态，
并且**不改变** Contract、施工范围、Frozen Base、下一阶段输入语义、risk boundary 或 finding authority，则优先与 Final Closure
合并。

不得为了记录一个中间状态而制造“开发停止 -> docs commit -> docs review -> 恢复开发”的循环。

### 11.2 不能压缩的 authority docs

以下 docs 改动**不能**因为加速而省略独立审查：

* Contract semantic amendment；
* Construction Plan scope amendment；
* Frozen Base change；
* risk boundary change；
* 下一阶段输入语义 change；
* finding authority change；
* 安全不变量 change。

即：纯状态 docs 可以压缩；authority docs 不能省略治理。

## 12. Finding 修复

### 12.1 统一 R1

Reviewer 判 FAIL 后，如果 findings 满足以下全部条件，允许统一进入一个 R1：

* 同一根因，或影响范围明确；
* 不需要新的架构设计；
* 不需要新的 Contract authority。

不得机械地把 R1-01、R1-02、R1-03 分别开发、分别 Review。统一的 R1 必须一次闭合全部已知 findings，并检查 direct regression。

### 12.2 Finding Authority Boundary

如果一组 findings 中存在以下任何一项，则必须先解决 authority，然后才允许统一实施 R1：

* Contract amendment；
* Construction Plan scope amendment；
* 新的安全设计；
* 新的公共 API 裁决。

“大 R1”不能越权。

## 13. 修改 CLOSED Package

未来某个 C 如果需要改变已经 ACCEPTED / CLOSED 的 package 的生产语义，默认自动提升为**高风险治理事件**。必须说明：

* 为什么必须修改；
* 影响哪个历史 Contract；
* 回归范围；
* 兼容性影响；
* 安全影响。

并且必须执行独立 Review。不能因为修改发生在“大 C”中，就静默改变 CLOSED package。

## 14. 后续 Phase / Package 的推荐粒度

以下是规划推荐，不替代各 Package 自己冻结的 Contract / Construction Plan。

### 14.1 P4-C9 — Diagnostics

* 默认保持**一个 C**，风险默认 **B 类**。
* 内部允许：S1 diagnostic model / event；S2 orchestration integration；S3 output / redaction / tests。
* S1-S3 默认连续完成，只做一次 C9 Level 1 Review。
* 只有当 diagnostics 引入 persistence、敏感信息落盘、不可逆 schema 或新的 security boundary 时，才升级治理颗粒度。

### 14.2 P4-C10 — Phase 4 Final Acceptance

* 保持**一个最终验收 C**。
* 重点：cross-package integration gate、regression、真实安全场景、compatibility、final HANDOFF、Phase 4 Closure。
* 禁止借 Final Acceptance 无限加入顺手功能。
* 发现普通缺陷时统一进入 C10-R1。

### 14.3 Phase 5 — Amane Thin Adapter（目标 2 个 C，最多 3 个）

* **P5-C1 Amane Adapter End-to-End**：plugin discovery、config、SearchQuery mapping、FC2 Core invocation、MediaMetadata
  mapping、error mapping、source attribution、contract tests、package / install skeleton；一次 C-level Review。
* **P5-C2 Amane Compatibility & Adapter Closure**：v0.15.0、current release、plugin install / reload、configuration、
  integration test、final adapter package、HANDOFF。
* 没有重大架构障碍时，不得拆成 5-8 个小 C。

### 14.4 Phase 6 — Amane Batch Integration（1-2 个 C）

* **P6-C1 Real Batch Integration**：至少 10 个 FC2；scan -> scrape -> multi-source -> Amane metadata -> images -> NFO ->
  organize preview。
* **P6-C2 Failure / Retry / Batch Closure**：source failure、item failure、partial、retry、cancel、batch summary、真实宿主
  集成回归。
* 若 C1 已覆盖大部分异常场景，允许进一步合并。

### 14.5 Phase 7 — 真实整理验收（1-2 个 C）

* 优先一个 C：**P7-C1 Real Filesystem Acceptance**，覆盖 mkdir、rename、move、collision、subtitle pairing、NFO、poster、
  fanart、extrafanart、partial metadata、failed item、source preservation；全部使用测试副本。
* 仅在真正需要时设立 **P7-C2 Platform / Edge Closure**，用于 Windows、跨盘、权限、特殊 filesystem 等真实环境边界。

### 14.6 Phase 8 — Release（目标 2 个 C，最多 3 个）

* **P8-C1 Compatibility & Packaging**：Amane v0.15.0、latest release、main canary、adapter zip、core package、install guide、
  upgrade test。
* **P8-C2 v1.0 Release Closure**：release notes、source status matrix、SECURITY、troubleshooting、clean-install validation、
  final regression、final independent acceptance、v1.0 release。
* 只有真正独立的发布 blocker 才允许增加 C3。

### 14.7 总体目标包数量

```text
P4 : C9 + C10 = 2
P5 : 2-3
P6 : 1-2
P7 : 1-2
P8 : 2-3
剩余主要施工包目标：约 8-12 个
```

这是**规划目标，不是硬限制**。safety / correctness 允许时继续合并；高风险要求时允许增加。不得为了数字强行合并风险。

## 15. 每次拆 C 前的四问

创建任何新 C 前，设计者必须显式回答并记录：

1. 为什么这项工作不能和前一个 C 一起完成？
2. 单独拆包降低了什么具体风险？
3. 该风险是否值得额外增加一次“开发停止 + Review + Closure”？
4. 如果取消这个边界，是否影响 correctness、safety 或 auditability？

如果第 4 问的答案是“不会”，原则上**必须合并**。

## 16. Owner Question Gate

```text
Owner Question Gate: BUSINESS DECISIONS ONLY
```

只有真正需要项目所有者决定的业务问题、产品取舍、不能由 Frozen Authority 推导的战略裁决，才暂停并询问 Owner。

以下事项**不得**频繁询问 Owner，由设计者自行裁决并记录理由：

* helper 命名；
* 文件内部组织；
* fixture；
* 普通测试结构；
* 明显更安全的 fail-closed 默认；
* Contract 已经明确回答的问题；
* 历史 HANDOFF 已经裁决的问题。

## 17. Evidence Gate 不降低

较大的 C 减少了 Review 次数，最终 evidence 必须**更完整**。根据风险，至少包括：

* Contract -> implementation -> test mapping；
* 完整 diff scope；
* targeted tests；
* contract tests；
* full suite；
* mutation / non-vacuity；
* 安全不变量；
* determinism；
* concurrency bounds；
* platform evidence；
* evidence gaps；
* known limitations。

加速不能通过减少证据来实现。

## 18. Mandatory Construction Plan Header

从 P4-C9 起，每份新的 Construction Plan 最前面必须包含以下字段（或等价内容）：

```text
Governance Mode                  : ACCELERATED v2
Governance Authority             : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ <accepted governance head>
Package Frozen Base              : <sha>
Risk Class                       : A / B / C
User Capability / Vertical Closure : <该 C 完整交付什么能力>
Why Not Merge With Previous C    : <具体风险理由>
Why Not Split Further            : <为什么继续拆不会提高 correctness / safety / auditability>
Internal Stages                  : S1 / S2 / S3 / ...
Independent Review Plan          : C-level once，或 <明确列出的高风险中间 Review>
Owner Question Gate              : BUSINESS DECISIONS ONLY
Evidence Gate                    : <该 C 必须提供的证据>
```

## 19. P4-C9 特殊坐标要求

P4-C9 首次 E0 / Contract / Construction Plan 必须**同时**记录两个坐标：

```text
P4-C9 Frozen Base    : a662659dfd6e801531b14af7913d84a5f9f859e2
Governance Authority : <本 amendment 独立复查 PASS 后的 Final Reviewed Governance Head>
```

* P4-C9 Frozen Base 是 package baseline，继续保持 `a662659dfd6e801531b14af7913d84a5f9f859e2`；本 amendment **不**重新定义它。
* 本 amendment 的 accepted head 是 post-base 的 governance authority，也是 P4-C9 的 Planning Parent；**不得**把它写成新的
  P4-C9 Frozen Base。
* P4-C9 工作 branch 可以从 Governance Authority Head 继续创建，但 P4-C9 Frozen Base 仍是 `a662659…`。

## 20. 最终成功标准

加速的成功不是 commit 变少，而是在最终结果与证据强度不下降的前提下，显著减少：

* session 数；
* 人工转发次数；
* 等待 reviewer 的次数；
* docs-only 循环；
* 重复的 context handshake；
* 没有功能价值的中间 closure。

v1.0 的全部硬指标保持不变。
