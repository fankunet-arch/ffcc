# PHASE 6 总体计划（MASTER PLAN）—— Amane 真实批量集成

```text
Phase 6                       : DESIGN CANDIDATE
P6-C1                         : DESIGN CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract               : NOT YET ACCEPTED
Construction Plan             : NOT YET ACCEPTED
Design-R1                     : SUPERSEDED（Design-R1 Head c05c7ebca04ded9e1853b71e82796a419fadc192）
Design-R2                     : SUPERSEDED BY DESIGN-R3 CANDIDATE（Design-R2 Head b071d149f8f99385851cb6f8dc38f9904c624262）
Design-R3                     : SUPERSEDED（Design-R3 Head 85d3da8b7450fd50a112e8bbc47a248b9473e9a9）
Design-R4                     : SUPERSEDED BY DESIGN-R5 DRAFT（Design-R4 Head 6ccf7d38ef637af6e8b481475441b4d1e13dfcca；独立复核 FAIL，C 报告 BLOCKED — SECURITY AUTHORITY）
Design-R5                     : COMMITTED REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（Reviewer C / G / x 均 FAIL；候选内容：致命异常 F3 = 确定性所有权清理 + 异常引用脱离，生产路径禁止 gc.get_referrers / sys._getframe / frame.clear；X-NARROW 仅用于独立载荷对照，四个植入凭据用例与 trace 注入 = OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS（B1 / B2）；Reviewer x 的 Findings Addendum（x-01..x-07）已交付，其修复项为 R5-R1-04..R5-R1-10，R5-02..R5-07 与其编号对应由 Governance 保留，均不得视为已关闭；本状态不得改写为 PASS）
R5 Candidate                  : 22a3fa4922c655cb5ce127ee2825b1678f4855db（已提交并推送的 R5 Review Candidate；不得改写 / amend / reset）
Design-R5-R1                  : REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（R5-R1 Candidate d16a0a308a5488bde17a03b32b0cee65ba7d2343 是位于 R5 Candidate 之上的单个 docs-only 提交，已提交并推送；Reviewer G / C / x 独立复核 FAIL；不得改写 / amend / reset；该轮正式编号 R5-R1-01..R5-R1-10）
Design-R5-R2                  : REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（R5-R2 Candidate 55144ba8fc7eef0df57c0639c04b6418a9595002 是位于 R5-R1 Candidate 之上的单个 docs-only 提交，已提交并推送；独立复核 FAIL（Reviewer C：R5-R2-03 仍 OPEN——MC1 嵌套 / 容器变异使入口扫描与数据流守卫假绿；Reviewer x：Metadata 来源见证与严格 GET reader 漏检）；不得改写 / amend / reset；该轮正式编号 R5-R2-01..R5-R2-11）
Design-R5-R3                  : REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（R5-R3 Candidate aacbbf2764bc32c6d50ce3083cf38ad75c1a43ef 是位于 R5-R2 Candidate 之上的单个 docs-only 提交，已提交并推送；三位独立 Reviewer（C / x / G）均 FAIL，发现 R5-R4-01..R5-R4-07；不得改写 / amend / reset 该提交）
Design-R5-R4                  : REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（R5-R4 Candidate ee9fc2a3bb4b53589d7cd102257109209e0fb71b 是位于 R5-R3 Candidate 之上的单个 docs-only 提交；独立复核 FAIL：Reviewer C——R5-R4-01 OPEN（NX1 模块级 `__getattr__`、NX2 模块级 dunder 函数、NX3 模块内命名空间、NX4 类上公共容器暴露 callable，使入口清单 `[M]` 假绿）、R5-R4-03 OPEN（MR4：清理循环第 4 轮及以后的账本写入使按键矩阵、提交区门与类型门假绿）；Reviewer G——G-R5-R4-G-01（状态文字过期）、G-R5-R4-G-02（S2N / S2C 的取消预算 0.12 s 超出合同范围）；Reviewer x——R5-R4-06 / R5-R4-07 PASS；R5-R4-02、R5-R4-04、R5-R4-05（Reviewer G 证据核验）、R5-R4-06、R5-R4-07 的闭合结论保持；不得改写 / amend / reset 该提交）
Design-R5-R5                  : REVISION CANDIDATE — INDEPENDENT REVIEW REQUIRED（R5-R5 Base = R5-R4 Candidate ee9fc2a3bb4b53589d7cd102257109209e0fb71b；Package Frozen Base 4189b9552d26b3cc5273e0ac09e46e5a3759121d；正式编号 R5-R5-01..R5-R5-05；GOV-R5R3-CRED = BLOCKED — SECURITY AUTHORITY（Reviewer C 意见为 ACCEPT NARROW LIMITATION — CONDITIONAL，不是豁免；其条件 M5（`[M]` 完整）**未满足**，须待 Reviewer C 对修复后的 `[M]` 门独立复核，设计者自检不得写成 PASS；授权包另附于证据包）；GOV-R5R3-EXC = RESOLVED — ORIGINAL P1/P2/P3 PRESERVED；HG-1 = ACCEPTED — NOT EXECUTED；S1 = NOT AUTHORIZED；Design Accepted Head = NOT ESTABLISHED；不是 Design Accepted，不是 CLOSED / PASS；本设计文档只描述稳定的阶段门与历史审查状态，实时 HEAD 与提交进度由 Governance Coordinator 裁决并记录在 HANDOFF / 审查报告中）
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
| F-3 / HG-1 | P5-C2 的两个 CLOSED 测试把历史范围门的上界写成 `HEAD`，P6 分支任何新增文件都会使其失败（含本设计提交自身）；并且其中 reconciliation 门禁在 Frozen Base 上按断言逻辑求值**本来就是红**（P5-C2 Final Closure 改了 `adapters/amane/README.md`） | 最小、纯测试门禁的重绑：上界改为不可变的 P5-C2 Final Reviewed Technical Head `1ef23247…`（实测两个门禁在该上界都通过）；**实质裁决已被三份独立 Design Review 一致 ACCEPTED**，Design-R1 仅精确化文字：文件集合恰为两个；唯一移交的工作树断言恰好两处（scope_gate 的 `test_working_tree_changes_are_limited_to_the_allow_list_as_well` 整个函数；reconciliation 的 `_changed_since_authority()` 中 `git status --porcelain` 输入分量），其余断言一律不删；四个历史模式常量 AST 逐字不变；无新增 skip / xfail；diff 行数上限冻结为 60；P6 范围门覆盖自身 diff、工作树与 C0 控制字符检查。仍是**未来 S1 的 test-only 修复，本轮不执行** | §5.4 |
| F-4 | Amane `TaskStatus` 只有 `queued / running / done / failed`，没有 `CANCELLED`；取消的终态是 `failed`（错误文本 “Cancelled by user”）。**v0.15.0 在“DB 已 RUNNING、协程尚未登记”（含信号量等待）的窗口内取消，只会让记录变 FAILED，执行协程仍会继续运行并写 Metadata；v0.18.0 窗口更小但无法证明不存在**（Design-R1 / R1-04） | 区分 L1 请求已发送 / L2 数据库终态已观察 / L3 执行已停止：P6 只能观察 L1、L2，L3 永远 UNVERIFIED；撤销 `CONFIRMED_STOPPED`，改为 `TERMINAL_FAILED_OBSERVED` / `TERMINAL_DONE_OBSERVED` 与 `UNCERTAIN_*`；不读 `error` 文本；晚到写入不可排除 | §10 |
| F-5 | 任务侧 / 持久化侧的 `field_sources`、字段锁、`updated_at` 都只是**标签或时间戳**，没有一个读取字段的实际值：用户 `PATCH` 把 title 改成 B 之后，持久化 `field_sources` 仍指向插件（`PATCH` 不改它；v0.18.0 解锁后也不再受锁保护），Design-R1 的 E1/E2/E3/R0 会全部通过并把 B 错误归属于插件（Design-R2 / R2-01）。核查两个 pinned release 发现 `Metadata.raw`（`dict[来源键, MediaMetadata.model_dump()]`，与展示列同次写入，`use_cache=[]` 时每个来源重新抓取，翻译 / FacetRule / 物化不改写，公开 `PATCH` 不能写，`GET /api/metadata/{id}` 返回）保存了插件的原始记录 | **方案 A（冻结，唯一）**：字段值只由 `raw["ffcc.fc2-metadata"]` 经严格 reader 与确定性映射派生；展示列、持久化 `field_sources` / `locked_fields` 不作内容证据；放弃的宿主后处理语义（翻译、FacetRule、物化、手工编辑）显式声明；`timestamp_relation` 只是审计提示；保证范围是“插件来源内容”，**不**是“任务独占内容”；放弃方案 B（逐值比较需无界变换白名单） | §7.3、§11.3 |
| F-6 | SCRAPE 会 upsert **Amane 的 Metadata 数据库**；`auto_scrape` 还可能扇出 `ACTOR_SCRAPE` | preview 不执行用户媒体的文件系统整理，但 SCRAPE 会写宿主 Metadata 库（不得声称对宿主数据库只读）；`acknowledge_host_metadata_writes=True` 作为显式确认；后继任务属宿主所有 | §8.2、§27 L6-08 |
| F-7 | 两个版本的 `TaskResponse` 都没有 progress 字段；进度只经 WebSocket | P6-C1 不使用 WebSocket、不新造 progress 契约 | §17 |
| F-8 | Amane 可能把**展示列**里的 poster 物化 / 裁剪成宿主内部 URL（`/api/resources/<hash>`） | **展示 poster 的裁剪 / 物化不进入 P6 的 URL 过滤**：P6 的图片候选只来自 `PluginRaw` 的原始 URL；`map_host_result` 第 7 步只对 `PluginRaw` 三个 URL 列表做 P5 I22 卫生（带 host 的绝对 http(s)、无控制字符 / 首尾空白），只删除不合规项并精确计入 `dropped_url_count`；`dropped_url_count` **只**统计这类 `PluginRaw` 清洗，与 Amane 展示裁剪无关（R5-08 / R5-09）；P4 图片获取不依赖 Amane Resource | §11.2、§11.4、§18 |
| F-9 | 宿主对“失败”只给 `failed` + 文本，无法在不解析文本的前提下区分“号不存在”与“来源故障” | 统一 `HOST_TASK_FAILED`；P6 从不产生 `NOT_FOUND` | §12、§27 L6-05 |
| F-10 | Amane 认证成功后会下发 `Set-Cookie: amane_token` | client 使用“拒绝一切 cookie”的 jar，不回传 | §8.3 |
| F-11 | 提交尝试次数 ≠ 宿主创建的任务数：401 / 连接失败可能创建零个，响应丢失时创建状态未知（Design-R1 / R1-02） | `SubmissionState` 四态；每个 aggregate 最多一次 `POST` 且永不自动重试；`CREATION_UNKNOWN` 不折算为 0 / 1，也不是重新提交的理由；任务账本用不等式对账 | §9.2、§13.1 |
| F-12 | `raise … from None` 不清除 `__context__`（Design-R1 / R1-03）；Design-R1 只约束 `host_client.py` / `facade.py`，`credential.py` / `config.py` 等仍可 `except UnicodeEncodeError: raise … from None` 而保留 `.object=token`（Design-R2 / R2-02） | 规则扩展到整个 `src/fc2_amane_batch/**`：处理体内禁止带参数 `raise`、校验用纯谓词、失败路径重新绑定 `token` 局部、传输两层；保护面 P1–P3 / 禁入内容 F；区分“新引入的泄漏”与“调用方持有对象本身的认证状态”；强制失败矩阵与红绿孪生 | §8.3.1、§20.2 |
| F-13 | P4 `_claim()` 是私有方法，P6 门面无法在 preflight 之前“委托 P4 busy-first”（Design-R1 / R1-05） | 撤销该声明；冻结实际调用顺序（本地校验 → preflight → P4 公开 `preview`）；不复制 P4 锁、不承诺零网络或错误优先级 | §9.5 |
| F-14 | P4 Phase B 以 `(device, inode)` 检测冲突，不同番号可共享 hardlink 源；单独重试子集看不见前轮 READY（Design-R1 / R1-06） | 撤销“不可能冲突”断言；READY / 冲突只对本轮有效；汇总区分 `ready_round_local` 与 `cross_round_verified`；Phase 7 跨轮执行必须重新验证 | §13.4、§20.4 |
| F-15 | 8 MiB 字节上限不限制 JSON 深度 / 节点 / 集合规模（Design-R1 / R1-07）；Design-R1 的 `O(min(bytes, tokens))` 成本公式不成立（长字符串 / 长空白必须遍历）（R2-03） | `MAX_JSON_DEPTH=32` / `MAX_JSON_NODES=200000` / `MAX_JSON_COLLECTION_ITEMS=20000`；迭代式预扫描；成本修正为正常通过 `O(B)`（`B ≤ 8 MiB`），辅助空间 `O(MAX_JSON_DEPTH)`；超限 `HOST_RESPONSE_TOO_COMPLEX` | §8.4 |
| F-16 | Amane `WorkerConfig.concurrency` 缺省为 10（不是 3，3 只是 `Worker` 构造函数的类默认）（Design-R1 / R1-08）；Design-R1 的真实宿主 oracle 仍要求宿主上本批全部任务 `≤ M`，与 `CREATION_UNKNOWN` / 孤儿任务冲突（R2-04） | 区分 P4 并发 M / 宿主配置并发 / 孤儿任务占用；冻结三个集合 A（活跃 aggregate）/ K（等待中的已知 id）/ H（含孤儿的全部关联宿主任务），`\|A\| ≤ M`、`\|K\| ≤ \|A\|`，**不要求** `\|H\| ≤ M`；独立 POST 账本 + `ORPHAN-M1` 强制用例 | §14、L6-07 |
| F-17 | R1 的 `NOT_APPLICABLE` 同时被绑定到“POST 前”与“未取消”，正常成功路径（已创建、未取消）无合法组合（R2-05） | 正交模型 `SubmissionState × CleanupTrigger × CancelOutcome × AggregateTerminal`；`NOT_APPLICABLE ⇔ 未触发清理`；新增 `NOTHING_TO_CANCEL`；合法组合与计数口径；正常成功 / 未取消失败不计入 `abandoned_attempts` | §10.3、§20.5 |
| F-18 | R2 只要求 `raw` 含插件键，插件与外来来源并存的记录仍会通过，与 H6-1（FC2 route 是插件单源）不一致（R3-01） | 严格键集合 `set(raw.keys()) == {"ffcc.fc2-metadata"}`，缺失 / 外来 / 混合 / 语言后缀 / 未知键统一 `HOST_ATTRIBUTION_FOREIGN`；这是对独占来源前提的验收，不恢复 E1/E2/E3/R0 | §11.3 |
| F-19 | `record_freshness` 的名称与 §22.3 的要求暗示了无法证明的“实际后写入”事实；墙钟回拨 / 同刻精度下后写入仍得到 `≤`（R3-02） | 重命名 `TimestampRelation`（`UPDATED_AFTER_FINISHED` / `UPDATED_NOT_AFTER_FINISHED` / `INDETERMINATE`），只由两个字符串决定；CASE A–D；真实宿主与替身的共同强证明只有“语义 title == raw.title ≠ B” | §11.3.4、§22.3 |
| F-20 | `_transport` 在取消 / 致命时 `request` / `response` 仍留在 traceback 帧；`_call` 抛出时持有 `body_bytes`；R3 用 `asyncio.shield` 关闭 Response 与“独立被 shield 的清理 task”会留下仍持有 Response 的 task（Gate C 实测，R3-03 / R4-02）；R4 的 `asyncio.timeout_at` 在 CPython 3.11.0–3.11.2 上把到期报告为 `CancelledError`，且 `_transport` 让非 `httpx` 异常带着含 token 的帧逃出（R5-10 / R5-12）；R5 草案只靠每次 I/O 的 `httpx.Timeout`，响应头 slowloris 可使请求远超超时（实测 62.56 s / 1.0 s） | **唯一规范 = 合同 §10.2 内联清理生命周期**：全部清理在 aggregate 自己的 task 内联执行，包内无 shield / create_task / ensure_future / gather / TaskGroup / `asyncio.timeout` / `wait_for`；**每个请求有定时器强制的总墙钟 deadline**（`loop.call_at` + `Task.cancelling()` / `uncancel()` 记账，`finally` 撤销，调用方取消永远胜出），清理预算在发出下一个请求前检查；二次取消停止后续 I/O；Response 内联关闭；`CancelledError` 只置标志、出口为 C5c 同类型新实例；`_transport` 的异常分类封闭完备（非 `httpx` 异常 ⇒ `HOST_NETWORK`，块外抛出）；**致命 `BaseException` 采用 F3：同一对象，确定性所有权清理 + 异常引用脱离（合同 §10.5：各层拥有者重绑自己的敏感局部，`__traceback__` / `__cause__` / `__context__` 置 `None`；生产路径不得 `frame.clear` / `gc.get_referrers` / `sys._getframe`，不访问第三方帧，不终结挂起协程；安全断言是敏感引用不可达，不是 traceback 不含任何本包帧；F1 / F2 均未被治理接受）**。**证据范围按状态词汇分别标注**（合同 L6-23）：生产 `httpx` 路径设计探针在 3.11.0–3.11.9 / 3.12 / 3.13 / 3.14 **PASS**，P6 实现在 3.13 的验收 **NOT_RUN**（E6-25，S3 必须运行）；DNS 线程 **UNVERIFIED**；任意注入的吞取消 `transport=`：方案 A（**APPROVED FOR DESIGN REVISION ONLY**，已从公共构造面移除；见 F-30） | §8.3.1、§10.2、§10.5、§10.6 |
| F-21 | O2 以 `(番号, generation)` 为粒度错误（重复显式 `retry_failed` 合法）；O3 混淆 H2 / H4 且在取消响应处过早结束 K（R3-04 / R3-05） | `attempt_id` + `X-FFCC-Attempt`；H1–H4；K = `[task_known_event, end_event)`；可复算区间证据 + oracle 自检；20 ms 采样仅作佐证 | §14、§22.5 |
| F-22 | POST 前致命异常无合法审计状态；取消请求发送与否没有见证字段；R3/R4 的谓词对 `CALLER_CANCEL + RAISED`、缺 H4 的 confirmed、`UNKNOWN + DEADLINE` 等过度接受；R4 的字符串谓词遇到真实枚举会 `KeyError`，“39 条”把取消确认 / 非终态观察折叠掉（R3-06 / R3-07 / R4-06 / R4-07 / R5-01 / R5-02 / R5-06） | **唯一规范 = 合同 §10.3.1 的真实枚举 / 冻结数据类 + 谓词 `record_is_legal` + §10.3.4 的 63 条可产生记录表**；`CancelOutcome` 10 个成员（`NO_RESPONSE` 取消未确认 / `NOT_TERMINAL` 已确认且见过非终态 / `OBSERVATION_FAILED` 已确认而无成功观察，严格优先级）；谓词对任意输入返回 bool；接受集合与独立参考模拟器相等（Designer 编写，独立性 NOT ESTABLISHED）；H4 事件、事件全序、`attempt_id` 稠密、`completion_seq`；在途 / 静止快照分开；**R1 追加**：`terminal_status` 与其它 `str` 字段严格 exact `str`、`HostAttemptRecord` 构造处拒绝 `UserString` 等可变别名、`record_is_legal` 对任意输入（`None` / 错误对象 / 未初始化实例 / 鸭子类型）返回 `bool`（x-01，R5-R1-04）；取消确认与终态观察必须有独立代理事实（已送达 `200`、精确 id、其后的终态 `GET`；x-06，R5-R1-09）；63 个抽象状态不变 | §10.3、§14.4、§20.5 |
| F-23 | §18 / L6-10 遗留“Amane 裁剪导致 P6 poster 被剔除”的旧语义，与 raw-only 模型冲突（R3-08）；E6-28 只比较开关则可能空跑（R4-09）；展示裁剪不得进入 `dropped_url_count`（R5-09） | 宿主展示 poster 与 P6 raw URL 候选分离；E6-28 冻结确定性输入（缺海报 / 短海报 / 缩略图重排）并要求展示值**实际改变**才算证明，否则 FAIL（NON-VACUITY）/ NOT_RUN | §18、L6-10、E6-28 |
| F-24 | R3 的 §11.2 把号等价放在键集合与 `PluginRaw` 校验之前，缺键 / null / 缺 number 会在解引用处抛异常，混合来源 + 号错被误归 NUMBER_MISMATCH（Gate A：7/16 用例无单一分类）（R4-01） | **唯一规范 = 合同 §11.2 代码块 `map_host_result`**：外层结构 → 键集合 → PluginRaw → 号等价 → 映射 → 最低成功；从合同抽取执行，42 个有序优先级用例 + 20000 次 fuzz 无未处理异常 | §11.2 |
| F-25 | O2 以 `(番号, generation)` 为粒度、无条件“成功恰好 1 个 / 恢复恰好 2 个”与合法的重复显式重试冲突；pre-proxy 取消 / 致命的 `POST = 0` 被误拒；`attempt_id` 只验单条记录（R4-03 / R4-04） | **唯一规范 = 合同 §14.4 请求账本模型**：任务数由独立调用脚本历史 `calls(N)` 决定；pre-proxy `POST = 0` 须被 `Mf` 注入清单或传输类 outcome 解释；`attempt_id` 靠 `seq` 稠密保证跨记录（含溢出后）唯一；**R1 追加**：H3 不证明 P6 已建立 H4——`H2 = H3 = TRUE, H4 = FALSE, outcome = TIMEOUT, Submission = UNKNOWN, 无后续请求` 合法，迟到的 `202` 不能构成 H4 也不能证明 P6 拒绝过 body（x-02，R5-R1-05）；O2-3 按身份归属，删除 `highest_dropped_seq`，`seq` 与 `completion_seq` 两个序号空间分别证明，缺失历史 ⇒ `NOT_VERIFIED`（x-04，R5-R1-07） | §9.2、§13.3、§14.4 |
| F-26 | R3 同时要求“累计计数溢出后仍准确”和“全部计数 / 峰值由保留记录重算”（Gate D：20001 条时 submitted 20001 vs 20000、unknown 5 vs 4，历史峰值 5 vs 窗口 1）（R4-05） | **唯一规范 = 合同 §20.5**：累计状态 Z 在线更新、溢出后权威；保留窗口 W 只作证据窗口；全历史安全不变量靠测试工具在丢弃前分段流式取走验证，缺口 ⇒ NOT_VERIFIED；**R1 追加**：冻结 `Z`（全生命周期累计）/ `W`（仅已完成记录）/ `InFlight`（当前未完成）三个统计域，`Z.submitted = 已完成 submitted + 在途 ATTEMPTED/CONFIRMED`，不能在 `in_flight > 0` 时由 `W` 求得；任何时刻 / 仅静止 / 未溢出可由 `W` 验证 / 溢出后只能由 `Z` 或完整分段历史验证四类不变量分开（x-03，R5-R1-06）；快照全局界限、`completion_seq` 唯一与稠密、Harvester 冲突检测不得 `setdefault`（x-05，R5-R1-08） | §14.4、§20.5 |
| F-27 | L6-01 仍声称“真正的证明是逐字段双侧证据”（R4-08） | 统一为：任务侧 field_sources（必要条件）+ raw 键集合恰好插件（独占来源验收）+ PluginRaw 值（内容证据）；展示列 field_sources / 锁 / 时间戳不是证据，E1/E2/E3/R0 不得重新启用 | §11.3、L6-01 |
| F-28 | 证据状态没有统一词汇，NOT_RUN / UNVERIFIED 可能被统计为通过（R4-09） | 合同 §23.2：PASS / FAIL / NOT_RUN / UNVERIFIED / BLOCKED，后三者不计为 PASS | §23.2 |
| F-29 | 项目 `requires-python >= 3.11`，但 R4 只设计在 3.12 / 3.14 验证，且依赖 `asyncio.timeout`（3.11.0–3.11.2 有缺陷）（R5-10） | 设计不依赖任何 `asyncio` 超时上下文管理器；Gate B / C / D 在 3.11.0、3.11.1、3.11.2、3.11.3、3.11.9、3.12.10、3.14.7 上执行；3.13 未安装 ⇒ `NOT_RUN`；`pyproject.toml` 不修改 | §10.2、E6-25 |
| F-30 | `AmaneHostClient(..., transport=)` 可注入吞取消的传输，清理被拖过预算约 2.2 s（R5-11）；Governance 裁决：发现后把注入传输排除出范围 / 允许吞取消 / 无界清理 / 游离清理 task **均 NOT AUTHORIZED** | **方案 A，APPROVED FOR DESIGN REVISION ONLY（治理裁决；不是豁免，不是 Independent PASS）**：从未发布的 P6 公共 API 移除 `transport=`（`AmaneHostClient` / `AmaneBatchIntegration`），并衍生地移除 `AmaneAggregationEngine` 的 `_clock` / `_sleep` 注入（待确认）；故障注入改为真实回环 HTTP / TCP 服务与故障代理；E6-05 / E6-09 / E6-17 的强制能力全部保留（故障覆盖矩阵见合同 §22.5）；P4 / P5 的 `MockTransport` 不动；反例记录为“仅可经进程级猴子补丁复现”的信息项；方案 B（证明吞取消不能突破预算）否决 | 合同 §10.6、§22.5 |
| F-31 | 非合作服务端（治理附加 B）：持续发送数据但永不结束响应的 slowloris / trickle 不能只靠每次 read timeout | 每个请求的总墙钟 deadline（定时器强制）；墙钟上界公式写入合同 §10.2；红孪生（关闭总 deadline）复现缺陷；D1–D10 验证调用方取消 / 到期竞速与 `cancelling()` 记账 | 合同 §10.2、M6-43 / M6-44、L6-26 |
| F-32 | 致命 `BaseException`（治理附加 GOV-R5-G2 / GOV-R5-G8；R5-C-01 / R5-C-02）：F1 保留第三方 traceback 中的凭据 `Request`，F2 丢失异常身份，均未被接受；R5 草案的“兄弟 `except` 净化”够不到处理体窗口，链“允许名单”看不见 C 级槽位 | F3 + **边界所有权**：边界帧的内联致命处理体先用 `STORE_FAST` 重绑自己持有的响应数据，再把 `__traceback__` / `__context__` / `__cause__` 置 `None`（**确定性所有权清理 + 异常引用脱离**；生产路径不访问任何帧：无 `frame.clear` / `gc.get_referrers` / `sys._getframe`；R5-CL-01 / R5-GOV-01 / R5-NEW-01），然后裸 `raise` 同一对象；`_transport` 无致命处理体；`args` / `__dict__` / `__notes__` / 类型不动；窗口探针（历史名称“穷举窗口探针”；任一字节码 / CPython 检查点两种模型 × 四个出口 × k = 1/2/3 的**计划点**，实际到达并注入的点数与未到达点见合同 §10.5“覆盖口径”）在已到达的点上 0 违例，R5 草案红；审计器改用 `gc.get_referents` 覆盖 C 级槽位，红绿孪生。**IMPLEMENTED CANDIDATE，非 Security PASS**。抛出方植入致命异常自身字段的四个用例保留，逐项记录 payload 来源 / 凭据归属 / 注入点 / 受支持边界 / 可达性 / 裁决（凭据取自当前 P6 请求，不能按载荷豁免，**不标 X-NARROW PASS**；需要主动进程内篡改 ⇒ `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`，可达性已记录）；调试器 / trace 在任意字节码处注入且数量无界的假想模型 = `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`（B2），不为此改变进程级 `SIGINT` 策略 | 合同 §10.5、C9、L6-21 / L6-24 / L6-25、M6-45..47 / M6-51 / M6-52 |
| F-33 | 取消归属与竞态（治理 Gate C-Final-01）：内部 deadline 不得吞掉或转换外部取消，也不得泄漏取消计数 | O1–O5 不变量；R1–R11 逐步记录的交错（外部先 / 内部先 / 同轮次 / 两次外部 / TaskGroup / 调用方 `asyncio.timeout` / 正常完成竞争 / 响应关闭期 / 后续协程 / 3.11 与 3.13 计数差异）；三个破坏归属的红孪生 | 合同 §10.2、M6-48 |
| F-34 | 测试接缝撤销后的验收能力与故障网络独立性（治理 Gate C-Final-03）；`_clock` / `_sleep` 移除 | 迟到 202 / 精确 id 取消 / 最小 deadline 的真实时间构造 / 无残留 task、定时器、连接、线程；`faultnet.py` 只依赖标准库，判定规则在 Gate 脚本里 | 合同 §22.5、M6-49 / M6-50 |
| F-35 | 取消归属在内层转换下丢失外部取消（R5-C-03；Reviewer C 的 R10：`cancelling() == 1` 但没有 `CancelledError` 再被投递） | 单点分类：`fired` 则 `uncancel()` 一次；`cancelling() > base` ⇒ 外部取消 ⇒ 抛出新的 `CancelledError`；响应关闭后再检查；RC10 系列与 Reviewer C 原始 `race.py`（R5 草案红）/ `race_c_revised.py`（修订版绿）；5 个红孪生 | 合同 §10.2、M6-53 |
| F-36 | X-NARROW（仅独立载荷对照）的受支持边界与依赖矩阵；四个植入用例的 B1 归类 | 钩子注入点需要私有属性 `_http`；`dep_matrix.py` 对 httpx 0.27.2 / httpcore 1.0.9 / anyio 4.15.1 / h11 0.16.0 / sniffio 1.3.1 的 AST 扫描无任何把请求放进致命异常字段的位置；S1 矩阵守卫，矩阵外降为 UNVERIFIED | 合同 §10.5、L6-27、M6-55 |
| F-37 | `frame.clear()` 终结挂起的生成器 / 协程帧（R5-CL-01）：3.11 / 3.12 运行其 `finally`，3.13 / 3.14 抛 `RuntimeError`；“捕获后忽略”不是修复；上一版用 `gc.get_referrers` 判定存活也不成立（R5-GOV-01） | F3 重新设计为**确定性所有权清理 + 异常引用脱离**：不访问任何帧；持有响应数据的边界帧自己重绑；异常的 traceback / 链全部置 `None`；已结束的帧随引用计数释放，挂起的帧从不被触碰；`frame_safety.py` 红（上一版，`gc.freeze()` 下）/ 绿（本版，两种 GC 状态）孪生，3.11–3.14；Reviewer C `frameclear.py` / `liveness.py` 作基线 | 合同 §10.5、C8 / C9、M6-56 |
| F-38 | 审计工具对非 canary 凭据失明（R5-EV-01） | `reach.py` 检测任何带 `Authorization` 的 `Request` / `Response.request`，与令牌值无关；非 canary 正向对照、负向对照、变异；仅证据工具 | 合同 §10.5、M6-57 |
| F-39 | 进程内信任边界与异步致命异常投递边界（Governance B1 / B2） | B1：P6 不隐藏凭据于同进程恶意代码（`gc` / 帧内省、补丁、私有属性、trace、任意异常注入）；B2：区分真实信号投递（仅检查点）与 trace 注入；只声明运行时证据覆盖的保证；真实信号 fuzz 不是绝对证明；不改变进程级 `SIGINT` 策略 | 合同 §10.5、L6-29 / L6-30 |
| F-40 | 生产路径不得依赖不完整的 GC 引用者枚举（R5-GOV-01） | AST 守卫 `fatal_path_guard.py` 拒绝 `gc.get_referrers` / `sys._getframe` / `frame.clear` 及别名 / 字符串 / 替代手段（16 个变异）；旧版 `gc.freeze()` 下失败、新版通过 | 合同 §10.5、C8、M6-56 / M6-58 |
| F-41 | F3 不得经审计事件向外暴露敏感帧（R5-NEW-01） | F3 不触发 `sys._getframe` / `gc.*`；`audit_f3.py` 与 Reviewer C `audit_getframe.py` 在公共 client 与 `aggregate` 两条出口验证；“审计钩子有执行权限”属 B1，不作为解决方式 | 合同 §10.5、E6-17、M6-58 |
| F-42 | Reviewer x 的 Findings Addendum（x-01..x-07）：R5 的验证器（oracle）对若干情形漏检或误报（`UserString` 别名、迟到 `202` 被误判、自报告的取消确认 / 终态无网络事实、`seq > last_seq` 的合法形式伪造记录、`setdefault` 吞掉冲突、旧序号空间水位）（R5-R1-04..R5-R1-10） | R5-R1 验证器 `oracle_r1.py`（三态 RED / NOT_VERIFIED / GREEN）；对 R5 验证器在同一输入上复现缺陷、对 R5-R1 验证器的 10 个单缺陷变异全部变红；实时回环宿主 + 独立代理账本（`gateD_r1.py`）与模拟反事实（`counterfactuals_r1.py`，含 20000 规模）分别标注执行条件；M6-60..M6-65 | 合同 §10.3.1、§14.4、§20.5、E6-08 / E6-09 / E6-10 |
| F-43 | 边界入口（R5-R2-03 → R5-R3-01 / R5-R3-02；Reviewer C R1-C-01 / MC1）：R5-R1 证据以文本代替执行；R5-R2 的入口扫描只按 AST 顶层语句取注入点、数据流守卫是禁止名单，MC1（嵌套块 + 容器）与 Reviewer C 的七种绕过全部假绿；R5-R2 的“17 项”= 逐层检查 9 个 + 入口注入点 8 个（`Client.call` 2、`Engine.aggregate` 6），随被测文件形态变化（MC1 上 19），**不是**覆盖度量 | 规范入口模板：冻结表 E（34 个生产入口）+ [M] 运行时枚举相等 + [A] 模板 AST 相等 + [B] live 代码对象字节码复核 + [R] 运行时注入与字节码预测对账；非法即 Fail-Closed；`boundary_dataflow_guard.py` 只作辅助诊断；证据按六种单位分开统计（建模 23 / 未建模 11 / 运行时命中 22 个生产入口；19 个结构变异 + 480 次随机编辑全部判红；注入点逐解释器列出）；M6-74..M6-78 | 合同 §8.3.1 C9、§10.5“规范入口模板”、§23.1、E6-03 / E6-09 / E6-17 |
| F-44 | 谓词的封闭枚举与全域性（R5-R2-05）：`object.__new__(枚举类)` 与超大 `seq` 使谓词抛异常或放过同类型非成员 | 成员按身份、纯算术 `attempt_id` 一致性、合法 `seq` 范围不降低、固定错误、63 个抽象状态不变；`x05_enum_totality.py` / `x05_mutants.py`；M6-66 | 合同 §10.3.1、E6-08 |
| F-45 | 账本与验证器（R5-R2-06 / 07 / 08）：Task 与 Metadata 命名空间被混用；O2-6 只做了一部分；跨记录事件号可重复 | O2-9 按资源类型 + 完整路径隔离；O2-6 全量（不等式 + 对账 + 六个对照）；O2-10 事件全局唯一；`oracle_r2.py`、`counterfactuals_r2.py`（91 例 / 19 变异）、`gateD_r2.py`（90 项 LIVE）；M6-67..M6-69 | 合同 §14.4、§20.5、E6-10 |
| F-46 | 真实宿主 schema 与取消确认（R5-R2-09 / 10 / 11）：Amane 取消响应不回显 id；代理“送达”≠ P6“已验证”；GET 观察需严格 reader | 确认不要求 `task_ids` 回显；严格 `HostBatchCancelResult` / `HostTask`（id 匹配）；送达与验证之间的中断为 `UNCERTAIN_CLEANUP_INTERRUPTED`；故障宿主遵循真实 schema（v0.15.0 / v0.18.0 源码快照）；M6-70..M6-72 | 合同 §7、§8.5、§10.2、§14.4、E6-09 |
| F-47 | Metadata 来源与严格 GET reader（R5-R3-03 / R5-R3-04；Reviewer x，原始反例待补齐）：R5-R2 验证器对 11 种伪造来源判绿（猜中的 id、late 的 DONE、自报 id 不符、无 Metadata 请求、伪造 attempt 头、路径 id 与响应体 id 不符、`result` 缺字段、未送达、两次请求、`metadata.id` 不符、借用他人 DONE 的 id）；`obj.get("result") is None` 把缺 `result` 当作观察（原型 `_valid_task` 同样） | O2-11 只用独立代理事实（自报告只能反驳）；字段分为必需非空 / 必需可空 / 可选（`result` 必需可空，`error` 可选）；两版 Amane 序列化无 Authority 冲突；`oracle_r3.py`、`counterfactuals_r3.py`（131 例 / 35 变异 / 崩溃 0）、`gateD_r3_live.py`（76 项 LIVE）；M6-79 / M6-80 | 合同 §8.5、§14.4 O2-11、E6-09 / E6-10 |
| F-48 | Metadata 路径逃逸（R5-R3-05）：R5-R2 原型在校验 DONE 结果之前就用 `metadata_id` 拼路径，`"7/../../tasks/101"` 被 httpx 规范化为 `GET /api/tasks/101`（代理账本中与普通轮询无法区分），`True` / `0` / `-1` / 百分号编码 / 查询串等原样进入路径 | `gate:done_result_precheck`（第 9.4 节第 1–2 步）先于任何 Metadata 请求；路径只由固定模板 + 已验证的 `int` 构成；AST 守卫只允许模板函数；O2-12 请求面 = 表 H1；20 个非法 DONE 结果（18 个非法 `metadata_id` 取值 + 2 个结构 / 归属违规）实时测得 DONE 之后零请求；M6-81 | 合同 §9.4、§14.4 O2-12、E6-03 / E6-07 / E6-10 |
| F-49 | 致命记账窗口（R5-R3-06）：R5-R2 原型在 `aggregate` 的 `try` 之前登记 attempt（致命信号留下永久 `BEGUN` 在途记录），`_finish` 在构造记录之前推进计数（致命信号丢失记录） | 入口跳板不登记；两阶段 + 无检查点提交区（字节码复核）；致命记账为无调用状态转移，记录延迟物化；`fatal_accounting_probe.py`（检查点模型 k = 1 的计划点验证，实际触发与未触发点数见合同 §10.5“覆盖口径”；R5-R2 原型为 RED 孪生）；任一字节码模型的提交区内违例属 B1 并单独计数；M6-82 | 合同 §20.5“致命记账完整性”、E6-08 / E6-10 |
| F-50 | GOV-R5R3-CRED / GOV-R5R3-EXC（Governance 裁决）：凭据构造函数的入口窗口经本包 traceback 帧暴露调用方原始 token；普通异常是否需要 F3 | GOV-R5R3-CRED = **BLOCKED — SECURITY AUTHORITY**（全面豁免 REJECTED；本文只提出窄限定候选与反例证据，不改 P1 / P2，不标 PASS；`G1-KNOWN-EXPOSURE` 单独计数）；GOV-R5R3-EXC = **RESOLVED — ORIGINAL P1 / P2 / P3 PRESERVED**（不强制 F3，C1–C7 与封闭转换保持，直接回归保留） | 合同 §8.3.1、§10.5“GOV-R5R3-CRED”、L6-31 |
| F-51 | 证据完整性（R3-EV-01..03）：`reach.audit` 不报告与探针同一对象的令牌（GOV-R5R3-CRED 被隐藏）；R5-R2 反事实表中 M-x03b / M-x05b 只因 harness 崩溃被计为捕获（A/B 复现）；3.12+ 协程隐式 `StopIteration` 异常表项使受保护区之前的测量空洞化（本轮诊断探针曾出现） | 相等但身份不同的令牌探针；每个验证器以自身类构造清单、崩溃次数必须为 0；受保护区按致命处理体的闭包定义并与模板 `try` 行对账；M6-83 | 合同 §10.5、§23.1、E6-17 / E6-21 |
| F-52 | 入口清单 `[M]` 假绿（R5-R4-01；Reviewer C 的 N1 嵌套类 / N2 `partialmethod` / N3 外部文件可调用 / N5 外来基类）：R5-R3 门只枚举本模块 `__dict__` 里的函数 | 失败即关闭的发现流程：`dir()` + MRO 各类 `__dict__` + `inspect.getattr_static()`、递归嵌套类、严格基类白名单、封闭的属性分类；冻结的 34 个入口不变；与 API 冲突时报告 `AUTHORITY CONFLICT`；M6-84..M6-87 |
| F-53 | `[B]` 只检查受保护区之前，提交区操作数类型只是断言（R5-R4-02） | 两侧复核（R5-R3 假绿、R5-R4 红的单元证据）；提交区类型证明 GT-1..GT-5（静态语法 / 类闭包 / 精确类型见证 / 剖面钩子 / 红孪生），未证明项保持 OPEN；34 个入口：动态命中 22、仅静态 1、`NOT_RUN` 11；M6-88、M6-91 |
| F-54 | Gate C 覆盖口径（R5-R4-03）：R5-R3 窗口探针预热不忠实（3.13.9 丢失事件），记账探针把未触发的计划计为运行 | 忠实预热；逐解释器逐模型报告 planned / reachable / injected / unreached；未到达点 `NOT_VERIFIED`；“穷举窗口探针”仅为历史名称；更正 F-32、合同 §10.5 / DR-54 / L6 / E6；S2 因事件数不确定（根因：清理循环按墙钟预算轮询）改为按目标身份定向注入（代码对象 + `co_firstlineno` + 偏移 + 阶段 + 出现序号）、测试宿主闸门默认关闭且不改 P6、三态结论、红孪生与错目标自检、独立重算；M6-89、M6-90、M6-97..M6-99、L6-35；**状态：CLOSED CANDIDATE — DEFINED KEYED k=1 COVERAGE; RESIDUAL NOT_VERIFIED DISCLOSED**——执行结果（目标全部执行并通过）、稳定集合上的位置覆盖、不稳定自然时序下观察到的目标、未观察分支（`NOT_VERIFIED`）、k = 2 / 任一字节码的抽样边界五类口径分开记载，见合同 §10.5 与 L6-35 |
| F-55 | 治理编号命名空间（R5-R4-04）：裸 `G-1` / `G-2` 在历史 Design-R5 与 R5-R3 被复用 | 全局唯一编号：`GOV-R5-G1..G9`、`GOV-R5R3-CRED`、`GOV-R5R3-EXC`；映射表在合同修订索引；状态不变 |
| F-56 | 旧门的 Authority（R5-R4-05）：DR-71 / M6-73 的 `boundary_dataflow_guard.py` / `ownership_proof_r2.py` 已被证明不健全 | 编号与原文保留，注明只是历史反例 / 辅助诊断；Authority = 入口门 `[M]` / `[A]` / `[B]` / `[R]` + M6-74..M6-77 + M6-84..M6-88；Gate E 执行真实反例 |
| F-57 | 验证器 reader（R5-R4-06 / R5-R4-07；Reviewer x，`RECONSTRUCTED`）：H4 取自 digest `task_id`；`HostMetadata` 可选字段被忽略 | O2-4 对原始 `202` 体用独立严格 reader；O2-11 表驱动 `HostMetadata` reader；合法拒绝账本绿、伪造成功红；M6-92..M6-95 |
| F-58 | GOV-R5R3-CRED 授权（Reviewer C：ACCEPT NARROW LIMITATION — CONDITIONAL） | 状态仍 **BLOCKED — SECURITY AUTHORITY**，不是豁免；下一份候选附独立的 Authority Decision Package（证据包内）；M6-96：崩溃 ≠ 检测 |
| F-59 | 入口清单 `[M]` 对模块级 dunder / 模块内命名空间 / 公共容器假绿（R5-R5-01；Reviewer C 的 NX1..NX4） | 模块级 dunder 精确白名单、`__getattr__` 无默认安全、容器封闭分类（失败即关闭）；R5-R4 门假绿、R5-R5 门红；M5 = NOT SATISFIED，待 Reviewer C 独立复核；`GOV-R5R3-CRED` 仍 BLOCKED |
| F-60 | 清理循环第 4 轮及以后的账本写入（R5-R5-02；Reviewer C 的 MR4）使按键矩阵 / 提交区 / 类型门假绿；轮间状态含 `a["nt"]`；第 2 轮网络路径未注入 | 账本写入所有权门 + 循环不变量门；轮次感知的目标身份；5 轮 S2G5；清理路径变体逐一验证或 `NOT_VERIFIED` |
| F-61 | k = 1 权威（R5-R5-03）：R5-R4 把“每一个检查点指令（穷举）”降为“计划点验证” | 复位冻结措辞；Authority Comparison Table；静态检查点清单对账；剩余 `NOT_VERIFIED` / `AUTHORITY CONFLICT` 上报 Governance，不自行豁免 |
| F-62 | S2N / S2C 取消预算 0.12 s 超出合同范围（R5-R5-05；Reviewer G 的 G-R5-R4-G-02）；三份文档状态文字过期（R5-R5-04；G-R5-R4-G-01） | AUXILIARY 降级、合法预算重建（S2N5 / S2C5）、覆盖验证器读取真实运行参数；三份文档只写稳定的历史审查状态 |

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
| R2 | 遗留 / 孤儿宿主任务（提交歧义 `CREATION_UNKNOWN`、取消后执行层未验证、进程退出）；孤儿任务可能继续写 Metadata 并占用宿主并发 | 精确 id 取消 + 有界预算 + `SubmissionState` / `CancelOutcome` / `abandoned_attempts` 一等输出 + 审计；L3 永远 UNVERIFIED；无持久化故不承诺找回（L6-03 / L6-04） |
| R3 | 凭据泄漏（repr / 异常 / `__context__` / 帧局部 / 日志 / 预览 / 诊断），含凭据 / 配置校验路径与 `UnicodeError.object` | redacted 凭据、`httpx.Auth` 附加、整个包的构造规则 C1–C7（`from None` 不算证明）、本包零 logging、保护面 P1–P3 的异常图递归 canary 测试与强制失败矩阵（含真实宿主 canary）；明确不承诺调用方持有对象本身的认证状态 |
| R4 | 非确定性（完成顺序、时间、任务 id） | 语义 / 运维输出分离；语义投影等价判据；完成顺序反转 + 非空性控制 |
| R5 | 乘法重试 | 重试 eligibility 归 P6、执行 / 调度 / 并发归 P4；POST 永不重试；不使用宿主 retry 动作；宿主任务账本计数 |
| R6 | 误取消他人任务 | 请求体不含 `status` / `type`；旁观任务控制；M6-08 |
| R7 | 误执行真实整理 | S6-1..S6-5 三层机检；M6-10 |
| R8 | 环境不可得（Python 3.14 宿主 / 端口 / 公网） | 缺失如实 `NOT_RUN` / `UNVERIFIED`，不扩大支持声明；确定性门不依赖公网 |
| R9 | CLOSED 测试历史门禁碰撞 | HG-1（Design Review 裁决）；P6 自己的范围门 |
| R10 | 夹具本身无效导致“假绿” | 派生夹具页必须先通过 Core 解析器预检；上游内容变化必须使语义投影变化（非空性） |
| R11 | 虚假 provenance：把用户手工覆盖的值（含 `PATCH` 之后来源标签仍指向插件）归属于插件 | 值级证据：输出只来自 `raw["ffcc.fc2-metadata"]`；七类反事实（v0.15.0 / v0.18.0 手工覆盖、同号竞争覆盖、外来标签、raw 缺失 / 非法、raw 与展示不一致、干净孪生）带绿色孪生；M6-17 / M6-18 / M6-23 |
| R12 | 跨轮 READY 被误当作全局安全 | 逐轮口径 + `cross_round_verified`；Phase 7 重新验证；M6-22 |
| R13 | 结构炸弹（字节未超限但深度 / 节点 / 集合超限） | `MAX_JSON_*` + 迭代式预扫描；M6-21 |

---

## 8. 对后续 Phase 的输入（非约束性）

* **Phase 7**：对某个 `AmaneBatchRound.preview` 通过 P4 原路径调用 `execute`；需要为门面增加执行入口并为此编写自己的 Contract；多轮视图不能合并执行（逐轮执行）。P6 的 `AmaneBatchPreview` 是其输入。**P6 不提供跨轮 READY / 冲突保证**（不同番号可共享 hardlink 源，单轮 preview 看不见别的轮次）：Phase 7 如需跨轮执行，必须对合并范围重新验证源文件身份与目标冲突。
* **Phase 8**：兼容矩阵沿用坐标级声明（SC-xx）；P6 的 `P6_C1_HOST_MATRIX.json` 与 live smoke 记录是发布验收的输入；`UNVERIFIED` 项不得出现在 v1.0 支持声明中。

---

## 9. 状态与下一步

```text
Phase 6                       : DESIGN CANDIDATE
P6-C1                         : DESIGN CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract               : NOT YET ACCEPTED
Construction Plan             : NOT YET ACCEPTED
Design-R1                     : SUPERSEDED
Design-R2                     : SUPERSEDED BY DESIGN-R3 CANDIDATE
Design-R3                     : SUPERSEDED
Design-R4                     : SUPERSEDED BY DESIGN-R5 DRAFT（6ccf7d3；独立复核 FAIL）
Design-R5                     : COMMITTED REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（Reviewer C / G / x 均 FAIL；候选内容：致命异常 F3 = 确定性所有权清理 + 异常引用脱离，生产路径禁止 gc.get_referrers / sys._getframe / frame.clear；X-NARROW 仅用于独立载荷对照，四个植入凭据用例与 trace 注入 = OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS（B1 / B2）；Reviewer x 的 Findings Addendum（x-01..x-07）已交付，其修复项为 R5-R1-04..R5-R1-10，R5-02..R5-07 与其编号对应由 Governance 保留，均不得视为已关闭；本状态不得改写为 PASS）
R5 Candidate                  : 22a3fa4922c655cb5ce127ee2825b1678f4855db（已提交并推送的 R5 Review Candidate；不得改写 / amend / reset）
Design-R5-R1                  : REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（R5-R1 Candidate d16a0a308a5488bde17a03b32b0cee65ba7d2343 是位于 R5 Candidate 之上的单个 docs-only 提交，已提交并推送；Reviewer G / C / x 独立复核 FAIL；不得改写 / amend / reset；该轮正式编号 R5-R1-01..R5-R1-10）
Design-R5-R2                  : REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（R5-R2 Candidate 55144ba8fc7eef0df57c0639c04b6418a9595002 是位于 R5-R1 Candidate 之上的单个 docs-only 提交，已提交并推送；独立复核 FAIL（Reviewer C：R5-R2-03 仍 OPEN——MC1 嵌套 / 容器变异使入口扫描与数据流守卫假绿；Reviewer x：Metadata 来源见证与严格 GET reader 漏检）；不得改写 / amend / reset；该轮正式编号 R5-R2-01..R5-R2-11）
Design-R5-R3                  : REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（R5-R3 Candidate aacbbf2764bc32c6d50ce3083cf38ad75c1a43ef 是位于 R5-R2 Candidate 之上的单个 docs-only 提交，已提交并推送；三位独立 Reviewer（C / x / G）均 FAIL，发现 R5-R4-01..R5-R4-07；不得改写 / amend / reset 该提交）
Design-R5-R4                  : REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（R5-R4 Candidate ee9fc2a3bb4b53589d7cd102257109209e0fb71b 是位于 R5-R3 Candidate 之上的单个 docs-only 提交；独立复核 FAIL：Reviewer C——R5-R4-01 OPEN（NX1 模块级 `__getattr__`、NX2 模块级 dunder 函数、NX3 模块内命名空间、NX4 类上公共容器暴露 callable，使入口清单 `[M]` 假绿）、R5-R4-03 OPEN（MR4：清理循环第 4 轮及以后的账本写入使按键矩阵、提交区门与类型门假绿）；Reviewer G——G-R5-R4-G-01（状态文字过期）、G-R5-R4-G-02（S2N / S2C 的取消预算 0.12 s 超出合同范围）；Reviewer x——R5-R4-06 / R5-R4-07 PASS；R5-R4-02、R5-R4-04、R5-R4-05（Reviewer G 证据核验）、R5-R4-06、R5-R4-07 的闭合结论保持；不得改写 / amend / reset 该提交）
Design-R5-R5                  : REVISION CANDIDATE — INDEPENDENT REVIEW REQUIRED（R5-R5 Base = R5-R4 Candidate ee9fc2a3bb4b53589d7cd102257109209e0fb71b；Package Frozen Base 4189b9552d26b3cc5273e0ac09e46e5a3759121d；正式编号 R5-R5-01..R5-R5-05；GOV-R5R3-CRED = BLOCKED — SECURITY AUTHORITY（Reviewer C 意见为 ACCEPT NARROW LIMITATION — CONDITIONAL，不是豁免；其条件 M5（`[M]` 完整）**未满足**，须待 Reviewer C 对修复后的 `[M]` 门独立复核，设计者自检不得写成 PASS；授权包另附于证据包）；GOV-R5R3-EXC = RESOLVED — ORIGINAL P1/P2/P3 PRESERVED；HG-1 = ACCEPTED — NOT EXECUTED；S1 = NOT AUTHORIZED；Design Accepted Head = NOT ESTABLISHED；不是 Design Accepted，不是 CLOSED / PASS；本设计文档只描述稳定的阶段门与历史审查状态，实时 HEAD 与提交进度由 Governance Coordinator 裁决并记录在 HANDOFF / 审查报告中）
Design Accepted Head          : NOT ESTABLISHED
Implementation                : NOT STARTED
Production Modified           : NO
Tests Modified                : NO
```

下一步：由 Governance Coordinator 指派独立 Design Review；R5 Candidate `22a3fa4922c655cb5ce127ee2825b1678f4855db` 与 R5-R1 Candidate `d16a0a308a5488bde17a03b32b0cee65ba7d2343` 均不得被改写 / amend / reset；Design Accepted Head 建立之前禁止 Developer 开始 S1，也不得宣布 DESIGN ACCEPTED / FROZEN；Reviewer x 的 Findings Addendum（x-01..x-07）的修复项 R5-R1-04..R5-R1-10 以及 R5-R1 独立复核的残留项 R5-R2-01..R5-R2-11 均待独立复核，不得视为已关闭；R5-R2 Candidate `55144ba8fc7eef0df57c0639c04b6418a9595002` 已被独立复核判 FAIL，不得改写；R5-R3 Candidate `aacbbf2764bc32c6d50ce3083cf38ad75c1a43ef` 与 R5-R4 Candidate `ee9fc2a3bb4b53589d7cd102257109209e0fb71b` 均已被独立复核判 FAIL（历史事实，不得改写）；R5-R5-01..R5-R5-05 为 R5-R5 REVISION CANDIDATE，待独立复核；GOV-R5R3-CRED = BLOCKED — SECURITY AUTHORITY（待 Reviewer C 安全意见与最终 Governance Authority 裁决）；GOV-R5R3-EXC = RESOLVED — ORIGINAL P1/P2/P3 PRESERVED；Reviewer x 对 R5-R3-03 / 04 的原始反例尚待独立补齐；状态机的独立性与 E6-28 的真实宿主证明均尚未建立；HG-1 ACCEPTED — NOT EXECUTED；S1 NOT AUTHORIZED。Reviewer 的强制审查点是合同第 30 节的**完整范围 DR-01..DR-100**（DR-01..DR-10 摘要如下；Design-R1 追加 DR-11..DR-18、Design-R2 追加 DR-19..DR-22、Design-R3 追加 DR-23..DR-28、Design-R4 追加 DR-29..DR-35、Design-R5 追加 DR-36..DR-63、Design-R5-R1 追加 DR-64..DR-69、Design-R5-R2 追加 DR-70..DR-79、Design-R5-R3 追加 DR-80..DR-87、Design-R5-R4 追加 DR-88..DR-95、Design-R5-R5 追加 DR-96..DR-100；下表只列摘要，**不构成范围限制，不得删减 DR-36..DR-100**；Reviewer 的责任边界见合同第 30 节）：

R5-R3 Candidate `aacbbf2764bc32c6d50ce3083cf38ad75c1a43ef`（单个 docs-only 提交）独立复核 FAIL，不得改写 / amend / reset；R5-R4 Candidate `ee9fc2a3bb4b53589d7cd102257109209e0fb71b` 同样独立复核 FAIL；Design-R5-R5 是 REVISION CANDIDATE — INDEPENDENT REVIEW REQUIRED（R5-R5-01..R5-R5-05），S1 仍 NOT AUTHORIZED，Design Accepted Head 仍 NOT ESTABLISHED。

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

HG-1（F-3）实质裁决已被三份独立 Design Review 一致 ACCEPTED；它仍是 FUTURE S1 TEST-ONLY COMPATIBILITY REPAIR，本候选**不执行**（`Tests Modified = NO`）；精确化后的条款若不能在 60 行内完成，则 `AUTHORITY ESCALATION REQUIRED`。
