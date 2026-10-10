# PHASE 6 总体计划（MASTER PLAN）—— Amane 真实批量集成

```text
Phase 6                       : DESIGN CANDIDATE
P6-C1                         : DESIGN CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract               : NOT YET ACCEPTED
Construction Plan             : NOT YET ACCEPTED
Design Accepted Head          : NOT ESTABLISHED
Implementation                : NOT STARTED
Production Modified           : NO
Tests Modified                : NO
Risk Class                    : C
Phase 6 package count         : 1（P6-C1；P6-C2 默认不存在）
Package Frozen Base           : 4189b9552d26b3cc5273e0ac09e46e5a3759121d（P5-C2 Final Closure Docs Head）
Governance Authority          : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Upstream Final Reviewed Head  : 1ef23247c2c65649589e9919c00093901bbcb517（P5-C2；Independent Level 1 PASS；Risk Class C）
Branch                        : claude/phase6-c1-amane-batch-integration
```

本文记录 Phase 6 Governance Coordinator 已作出的总体架构裁决，并把它落成可审查的计划。它**不**改变任何 CLOSED 的 P4 / P5 语义，**不**重新打开 P5-C1 / P5-C2。
具体行为合同见 `docs/specifications/PHASE6_C1_AMANE_BATCH_INTEGRATION_CONTRACT.md`，施工细节见 `docs/P6_C1_CONSTRUCTION_PLAN.md`。
三份文档的范围 / Risk Class / Frozen Base / Governance Authority 必须逐字一致。

---

## 1. Phase 6 在路线图中的位置

```text
Phase 0-3   Core：号码规范化、多来源聚合、批量调度、弹性与资源控制            CLOSED
Phase 4     fc2_organizer：发现 → planning → publication → NFO → 图片 → 物化 → 执行 → 编排 → 诊断   CLOSED
Phase 5     Amane Thin Adapter：ffcc.fc2-metadata 插件（P5-C1）+ 兼容性与发布闭合（P5-C2）            CLOSED
Phase 6     真实 Amane 批量集成（本计划）                                       ← 当前
Phase 7     真实文件系统整理验收（mkdir / rename / move / collision / subtitle / source preservation）
Phase 8     发布（兼容矩阵与打包 / v1.0 Release Closure）
```

Phase 6 回答：“把 P4（批量编排）与 P5（Amane 插件）接在一起，在**真实 Amane 宿主**上，是否能稳定、可审计地完成批量元数据 → 图片 → NFO → 预检 → 预览？”
它**不**回答“真实移动文件是否正确”——那是 Phase 7。

---

## 2. 总体裁决（Coordinator 已决定；本计划不重新讨论）

1. **Phase 6 不拆成两个 C。** 采用单一的 **P6-C1：Real Amane Batch Integration & Closure**，一次完成原计划中的“真实批量集成”与“失败 / 重试 / 批量收尾”。**P6-C2 默认不存在。**
2. **Risk Class: C。** 不是因为会移动文件（不会），而是因为**新的集成边界**：Amane Host HTTP API 边界、宿主认证与凭据、宿主任务所有权、宿主任务取消、宿主侧持久化的 SCRAPE 生命周期、跨进程交互、失败 / 取消的歧义。
3. 因此：**新的 Frozen Contract 必须先通过独立 Design Review，之后才允许 S1**；全部实现完成后还有**一次** C-level Independent Level 1 Review。S1 / S2 / S3 默认连续施工，不逐 S Review。
4. **运行时架构**：Phase 6 不修改 Amane 源码、不修改 P5 plugin、不修改 P4 `BatchOrchestrator`。新增的集成层位于 **组织器一侧**，是 Amane Host 的**外部 client / bridge**，
   作为一个 Amane-backed `AggregationEngine` 注入现有 `BatchOrchestrator`。**禁止写第二套 scheduler。**

### 2.1 为什么必须这样连接

* P5-C1 的 plugin 只是 `FilmSourcePlugin` / `FilmSourceProvider`：`SearchQuery → canonical FC2 → Core aggregate → Amane MediaMetadata`。它没有批量编排、图片、NFO、整理、文件系统执行、durable resume；
  不得给它增加 Amane 不存在的 batch capability；P5 Core wheel 只含 `fc2_metadata_core`，不得塞入 `fc2_organizer`。
* P4-C8 已拥有 `BatchScheduler`、有界并发、取消语义、planning、图片、NFO、materialization、preflight、`BatchPreview`、汇总。重复实现会产生两个互相漂移的 scheduler。
* 所以正确连接是：`P4 BatchOrchestrator ← 注入 ← Amane-backed AggregationEngine → Amane 公共 HTTP/Task API → ffcc.fc2-metadata → Core`。

```text
dirty media root → discover_media → DiscoveredMediaItem×N → P4 BatchOrchestrator(engine = Amane-backed)
   → [仅规范 FC2 号；无本地路径 / 字节 / oshash] → Amane POST /api/tasks (scrape, content_type=fc2)
   → ffcc.fc2-metadata → Core MultiSourceEngine → MediaMetadata → Amane Metadata → P6 桥（fail closed）
   → 合法 AggregationResult → P4 planning / publication / 图片 / NFO / manifest / preflight → BatchPreview → AmaneBatchSummary
```

---

## 3. 权威与坐标

| 项 | 值 |
|---|---|
| Package Frozen Base | `4189b9552d26b3cc5273e0ac09e46e5a3759121d`（P5-C2 Final Closure Docs Head）。**不是** Governance Authority |
| Governance Authority | `docs/PROJECT_GOVERNANCE_ACCELERATION.md` @ `3b9d39e9adbcc8a009707486eebbb8736a5b1c4d` |
| P5-C2 Final Reviewed Technical Head | `1ef23247c2c65649589e9919c00093901bbcb517` |
| Amane v0.15.0 | tag `3292c957…` → commit `45dff215…` |
| Amane v0.18.0 | tag `7d219070…` → commit `0a8a731d…` |
| 必需宿主坐标 | SC-03（v0.15.0 / source host / Windows x64）、SC-04（v0.18.0 / source host / Windows x64）；SC-01 / SC-02 可选；其它平台 `UNVERIFIED` |

Authority 优先级：Frozen Contract > Frozen Construction Plan > `PROJECT_GOVERNANCE_ACCELERATION.md` > Task Prompt。

---

## 4. 单一包的范围与顺序

| 阶段 | 内容 | 对应合同 |
|---|---|---|
| S1 | Host boundary + 安全 client + 结构化映射（credential、config、wire、client、lifecycle、mapping、engine） | §7-§12 |
| S2 | `BatchOrchestrator` 集成 + 10-item 纵向 preview + 失败 / 重试 / 取消 / 并发 + 汇总 | §13-§21 |
| S3 | 双版本真实宿主矩阵 + 确定性 / mutation / 证据 + 全量回归 + HANDOFF 候选 | §22-§27 |

评审：**Independent Design Review（一次，S1 前）** + **C-level Independent Level 1 Review（一次，S3 后）**；必要时统一 R1；然后纯状态 Final Closure。

---

## 5. 何时才允许重新提出 P6-C2

只有同时满足以下条件，才允许重新提出 P6-C2：

1. 发现一个**真实的、无法在同一个 C 内安全控制的**独立 Risk-C boundary（例如：必须引入持久化 / durable resume，或必须修改 CLOSED production 语义——这类情况同时触发合同 §28 的升级门，需要 Coordinator 裁决）；
2. 拆分**确实提高** correctness / safety / auditability（Governance v2 §15 第 4 问的答案为“是”）。

**不是**理由：代码多、测试多、文件多、模型多、helper 多。这些纯代码组织原因不得被用来拆 C（Governance v2 §7）。

---

## 6. 设计期发现（Designer 实证；已在合同中冻结了处理方式，供 Coordinator / Design Review 复核）

这些发现来自对 Frozen Base 源码与两个 Amane release 源码树的直接核查，**没有一项**需要修改 CLOSED production 语义。

| ID | 发现 | 冻结的处理 | 合同 |
|---|---|---|---|
| F-1 | P4 `preview_retry` 的 `previous` 必须是 `execute` 之后的完整 `BatchExecutionResult`；Phase 6 禁止 `execute`，所以它**不可用** | 失败子集重试 = 对失败条目的原始 `DiscoveredMediaItem` 再调用一次 P4 `preview`；P6 只做子集选择；P6 只拥有 eligibility / 子集选择，P4 拥有重试执行 / 调度 / 并发 | §13 |
| F-2 | 5 个 CLOSED 架构测试逐字钉死了 `fc2_organizer` 的顶层子包集合；在其下新增 `amane_batch` 会使它们失败 | 新增**顶层同级包** `src/fc2_amane_batch/`（依赖方向 `fc2_amane_batch → fc2_organizer → fc2_metadata_core`），CLOSED 测试零改动 | §5.3 |
| F-3 / HG-1 | P5-C2 的两个 CLOSED 测试把历史范围门的上界写成 `HEAD`，P6 分支任何新增文件都会使其失败（含本设计提交自身）；并且其中 reconciliation 门禁在 Frozen Base 上按断言逻辑求值**本来就是红**（P5-C2 Final Closure 改了 `adapters/amane/README.md`） | 最小、纯测试门禁的重绑：上界改为不可变的 P5-C2 Final Reviewed Technical Head `1ef23247…`（实测两个门禁在该上界都通过），并移除工作树分量；断言逻辑与 allow-list 逐字不变；**需要 Design Review 明确裁决**，否决则 AUTHORITY ESCALATION | §5.4 |
| F-4 | Amane `TaskStatus` 只有 `queued / running / done / failed`，没有 `CANCELLED`；取消的终态是 `failed`（错误文本 “Cancelled by user”） | 取消确认只依据“取消请求之后观察到的结构化终态”；不读 `error` 文本；`CancelOutcome` 区分已确认 / 不确定 | §10 |
| F-5 | 宿主 SCRAPE 的 `field_sources` 给出每个字段的来源站点 id | 以它做逐条结构化归属校验（`ffcc.fc2-metadata` 独占）；route 含其它贡献站点则该条目 fail closed | §7.6、§11.3 |
| F-6 | SCRAPE 会 upsert **Amane 的 Metadata 数据库**；`auto_scrape` 还可能扇出 `ACTOR_SCRAPE` | preview 不执行用户媒体的文件系统整理，但 SCRAPE 会写宿主 Metadata 库（不得声称对宿主数据库只读）；`acknowledge_host_metadata_writes=True` 作为显式确认；后继任务属宿主所有 | §8.2、§27 L6-08 |
| F-7 | 两个版本的 `TaskResponse` 都没有 progress 字段；进度只经 WebSocket | P6-C1 不使用 WebSocket、不新造 progress 契约 | §17 |
| F-8 | Amane 可能把 poster 物化 / 裁剪成宿主内部 URL | 只接受绝对 http(s) URL，内部 URL 确定性剔除并计数；P4 图片获取不依赖 Amane Resource | §18 |
| F-9 | 宿主对“失败”只给 `failed` + 文本，无法在不解析文本的前提下区分“号不存在”与“来源故障” | 统一 `HOST_TASK_FAILED`；P6 从不产生 `NOT_FOUND` | §12、§27 L6-05 |
| F-10 | Amane 认证成功后会下发 `Set-Cookie: amane_token` | client 使用“拒绝一切 cookie”的 jar，不回传 | §8.3 |

### 6.1 对 Owner 可见的产品后果（由 Designer 按“更安全的 fail-closed 默认”裁决；Coordinator 可推翻）

* **独占 route 前提**（L6-01）：P5 INSTALL 把 plugin 放在 FC2 route 最前并保留原站点；P6 为了不伪造来源归属，要求其它站点不再贡献字段。这是 P6 生产使用的前置配置要求。
* **非回环主机只支持 https**（L6-02）：不提供“关闭 TLS 校验”或明文局域网开关。
* **宿主数据库会被写入**（L6-08）：预览不是对 Amane 数据库的只读操作。

这些是由本任务书自身约束（不伪造 provenance、不静默降级 TLS、不修改用户 Amane 配置）直接推出的结果，不是新增的业务功能；如 Owner 希望放宽，需要作为业务裁决另行提出。

---

## 7. 风险登记

| ID | 风险 | 缓解（合同 / 证据） |
|---|---|---|
| R1 | 宿主语义随版本漂移（v0.15.0 vs v0.18.0） | 表 H2 逐项核查 + 版本差异白名单 DIFF-P6-01..04 + 双版本真实宿主矩阵；超出白名单即 U6-6 |
| R2 | 遗留 / 孤儿宿主任务（提交歧义、取消不确定、进程退出） | 精确 id 取消 + 有界预算 + `UNCERTAIN_*` 一等输出 + 审计；无持久化故不承诺找回（L6-03） |
| R3 | 凭据泄漏（repr / 异常 / 日志 / 预览 / 诊断） | redacted 凭据、httpx 异常不保存不链接、本包零 logging、canary 测试（含真实宿主 canary） |
| R4 | 非确定性（完成顺序、时间、任务 id） | 语义 / 运维输出分离；语义投影等价判据；完成顺序反转 + 非空性控制 |
| R5 | 乘法重试 | 重试 eligibility 归 P6、执行 / 调度 / 并发归 P4；POST 永不重试；不使用宿主 retry 动作；宿主任务账本计数 |
| R6 | 误取消他人任务 | 请求体不含 `status` / `type`；旁观任务控制；M6-08 |
| R7 | 误执行真实整理 | S6-1..S6-5 三层机检；M6-10 |
| R8 | 环境不可得（Python 3.14 宿主 / 端口 / 公网） | 缺失如实 `NOT_RUN` / `UNVERIFIED`，不扩大支持声明；确定性门不依赖公网 |
| R9 | CLOSED 测试历史门禁碰撞 | HG-1（Design Review 裁决）；P6 自己的范围门 |
| R10 | 夹具本身无效导致“假绿” | 派生夹具页必须先通过 Core 解析器预检；上游内容变化必须使语义投影变化（非空性） |

---

## 8. 对后续 Phase 的输入（非约束性）

* **Phase 7**：对某个 `AmaneBatchRound.preview` 通过 P4 原路径调用 `execute`；需要为门面增加执行入口并为此编写自己的 Contract；多轮视图不能合并执行（逐轮执行）。P6 的 `AmaneBatchPreview` 是其输入。
* **Phase 8**：兼容矩阵沿用坐标级声明（SC-xx）；P6 的 `P6_C1_HOST_MATRIX.json` 与 live smoke 记录是发布验收的输入；`UNVERIFIED` 项不得出现在 v1.0 支持声明中。

---

## 9. 状态与下一步

```text
Phase 6                       : DESIGN CANDIDATE
P6-C1                         : DESIGN CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract               : NOT YET ACCEPTED
Construction Plan             : NOT YET ACCEPTED
Design Accepted Head          : NOT ESTABLISHED
Implementation                : NOT STARTED
Production Modified           : NO
Tests Modified                : NO
```

下一步仅为 **Independent Design Review**。通过之前禁止 Developer 开始 S1。Reviewer 的强制审查点见合同第 30 节：

```text
DR-01  F-1：`preview_retry` 是否真的要求完整 `BatchExecutionResult`（P4 `retry.py` / `orchestrator.py` 源码核对）
DR-02  F-2：`fc2_organizer` 顶层子包集合是否被多个 CLOSED 测试精确钉死；同级包 `fc2_amane_batch` 的选择
DR-03  HG-1：历史 P5-C2 浮动 `HEAD` 门禁，以及最小重绑是否降低历史验收强度
DR-04  重试所有权拆分：P6 拥有 eligibility / 子集选择；P4 拥有执行 / 调度 / 并发
DR-05  真实 Amane v0.15.0 / v0.18.0 的 endpoint / schema 事实（表 H1 / H2）
DR-06  `TaskStatus` 无 `CANCELLED` 与取消不确定性模型（`CancelOutcome`）
DR-07  宿主 Metadata 库写入 / 不得声称“对宿主数据库只读”
DR-08  route / provenance fail-closed 规则（独占 route 前提、`field_sources` 归属校验）
DR-09  凭据 / 安全边界（redaction、无 cookie / 代理 / netrc、无重定向、TLS）
DR-10  不执行文件系统 / Phase 7 隔离（S6-1..S6-5 三层机检）
```

HG-1（F-3）是 FUTURE S1 TEST-ONLY COMPATIBILITY REPAIR，本候选不执行；Reviewer 不接受则 `AUTHORITY ESCALATION REQUIRED`。
