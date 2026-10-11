# PHASE 6 总体计划（MASTER PLAN）—— Amane 真实批量集成

```text
Phase 6                       : DESIGN CANDIDATE
P6-C1                         : DESIGN CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract               : NOT YET ACCEPTED
Construction Plan             : NOT YET ACCEPTED
Design-R1                     : SUPERSEDED（Design-R1 Head c05c7ebca04ded9e1853b71e82796a419fadc192）
Design-R2                     : SUPERSEDED BY DESIGN-R3 CANDIDATE（Design-R2 Head b071d149f8f99385851cb6f8dc38f9904c624262）
Design-R3                     : SUPERSEDED BY DESIGN-R4 CANDIDATE（Design-R3 Head 85d3da8b7450fd50a112e8bbc47a248b9473e9a9）
Design-R4                     : VERIFIED CLOSURE CANDIDATE — COMPLETE GOVERNANCE REPAIR（R4-01..R4-09；Design-R4 Base 85d3da8b7450fd50a112e8bbc47a248b9473e9a9；待独立复核）
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
| F-8 | Amane 可能把 poster 物化 / 裁剪成宿主内部 URL | 只接受绝对 http(s) URL，内部 URL 确定性剔除并计数；P4 图片获取不依赖 Amane Resource | §18 |
| F-9 | 宿主对“失败”只给 `failed` + 文本，无法在不解析文本的前提下区分“号不存在”与“来源故障” | 统一 `HOST_TASK_FAILED`；P6 从不产生 `NOT_FOUND` | §12、§27 L6-05 |
| F-10 | Amane 认证成功后会下发 `Set-Cookie: amane_token` | client 使用“拒绝一切 cookie”的 jar，不回传 | §8.3 |
| F-11 | 提交尝试次数 ≠ 宿主创建的任务数：401 / 连接失败可能创建零个，响应丢失时创建状态未知（R1-02） | `SubmissionState` 四态；每个 aggregate 最多一次 `POST` 且永不自动重试；`CREATION_UNKNOWN` 不折算为 0 / 1，也不是重新提交的理由；任务账本用不等式对账 | §9.2、§13.1 |
| F-12 | `raise … from None` 不清除 `__context__`（R1-03）；Design-R1 只约束 `host_client.py` / `facade.py`，`credential.py` / `config.py` 等仍可 `except UnicodeEncodeError: raise … from None` 而保留 `.object=token`（Design-R2 / R2-02） | 规则扩展到整个 `src/fc2_amane_batch/**`：处理体内禁止带参数 `raise`、校验用纯谓词、失败路径重新绑定 `token` 局部、传输两层；保护面 P1–P3 / 禁入内容 F；区分“新引入的泄漏”与“调用方持有对象本身的认证状态”；强制失败矩阵与红绿孪生 | §8.3.1、§20.2 |
| F-13 | P4 `_claim()` 是私有方法，P6 门面无法在 preflight 之前“委托 P4 busy-first”（R1-05） | 撤销该声明；冻结实际调用顺序（本地校验 → preflight → P4 公开 `preview`）；不复制 P4 锁、不承诺零网络或错误优先级 | §9.5 |
| F-14 | P4 Phase B 以 `(device, inode)` 检测冲突，不同番号可共享 hardlink 源；单独重试子集看不见前轮 READY（R1-06） | 撤销“不可能冲突”断言；READY / 冲突只对本轮有效；汇总区分 `ready_round_local` 与 `cross_round_verified`；Phase 7 跨轮执行必须重新验证 | §13.4、§20.4 |
| F-15 | 8 MiB 字节上限不限制 JSON 深度 / 节点 / 集合规模（R1-07）；Design-R1 的 `O(min(bytes, tokens))` 成本公式不成立（长字符串 / 长空白必须遍历）（R2-03） | `MAX_JSON_DEPTH=32` / `MAX_JSON_NODES=200000` / `MAX_JSON_COLLECTION_ITEMS=20000`；迭代式预扫描；成本修正为正常通过 `O(B)`（`B ≤ 8 MiB`），辅助空间 `O(MAX_JSON_DEPTH)`；超限 `HOST_RESPONSE_TOO_COMPLEX` | §8.4 |
| F-16 | Amane `WorkerConfig.concurrency` 缺省为 10（不是 3，3 只是 `Worker` 构造函数的类默认）（R1-08）；Design-R1 的真实宿主 oracle 仍要求宿主上本批全部任务 `≤ M`，与 `CREATION_UNKNOWN` / 孤儿任务冲突（R2-04） | 区分 P4 并发 M / 宿主配置并发 / 孤儿任务占用；冻结三个集合 A（活跃 aggregate）/ K（等待中的已知 id）/ H（含孤儿的全部关联宿主任务），`\|A\| ≤ M`、`\|K\| ≤ \|A\|`，**不要求** `\|H\| ≤ M`；独立 POST 账本 + `ORPHAN-M1` 强制用例 | §14、L6-07 |
| F-17 | R1 的 `NOT_APPLICABLE` 同时被绑定到“POST 前”与“未取消”，正常成功路径（已创建、未取消）无合法组合（R2-05） | 正交模型 `SubmissionState × CleanupTrigger × CancelOutcome × AggregateTerminal`；`NOT_APPLICABLE ⇔ 未触发清理`；新增 `NOTHING_TO_CANCEL`；合法组合与计数口径；正常成功 / 未取消失败不计入 `abandoned_attempts` | §10.3、§20.5 |
| F-18 | R2 只要求 `raw` 含插件键，插件与外来来源并存的记录仍会通过，与 H6-1（FC2 route 是插件单源）不一致（R3-01） | 严格键集合 `set(raw.keys()) == {"ffcc.fc2-metadata"}`，缺失 / 外来 / 混合 / 语言后缀 / 未知键统一 `HOST_ATTRIBUTION_FOREIGN`；这是对独占来源前提的验收，不恢复 E1/E2/E3/R0 | §11.3 |
| F-19 | `record_freshness` 的名称与 §22.3 的要求暗示了无法证明的“实际后写入”事实；墙钟回拨 / 同刻精度下后写入仍得到 `≤`（R3-02） | 重命名 `TimestampRelation`（`UPDATED_AFTER_FINISHED` / `UPDATED_NOT_AFTER_FINISHED` / `INDETERMINATE`），只由两个字符串决定；CASE A–D；真实宿主与替身的共同强证明只有“语义 title == raw.title ≠ B” | §11.3.4、§22.3 |
| F-20 | `_transport` 在取消 / 致命时 `request` / `response` 仍留在 traceback 帧；`_call` 抛出时持有 `body_bytes`；R3 用 `asyncio.shield` 关闭 Response 与“独立被 shield 的清理 task”会留下仍持有 Response 的 task（Gate C 实测，R3-03 / R4-02） | **唯一规范 = 合同 §10.2 内联清理生命周期**：全部清理在 aggregate 自己的 task 内联执行，包内无 shield / create_task / ensure_future / gather / TaskGroup；所有等待有界；二次取消停止后续 I/O；Response 内联有界关闭；`CancelledError` 只置标志、出口为 C5c 同类型新实例；致命 `BaseException` 原样传播且零清理 I/O，第三方帧可达性据实披露（L6-21）。有界性的作用域 = 生产传输路径（L6-23：注入的吞取消 `transport=`、DNS 线程、黑洞地址为 UNVERIFIED / 不在保证内） | §8.3.1、§10.2 |
| F-21 | O2 以 `(番号, generation)` 为粒度错误（重复显式 `retry_failed` 合法）；O3 混淆 H2 / H4 且在取消响应处过早结束 K（R3-04 / R3-05） | `attempt_id` + `X-FFCC-Attempt`；H1–H4；K = `[task_known_event, end_event)`；可复算区间证据 + oracle 自检；20 ms 采样仅作佐证 | §14、§22.5 |
| F-22 | POST 前致命异常无合法审计状态；取消请求发送与否没有见证字段；R3 的 LC 规则与命名场景表对 `CALLER_CANCEL + RAISED`、缺 H4 的 confirmed、`UNKNOWN + DEADLINE` 等过度接受（Gate B：1728 组合里谓词接受 137 条，独立模拟器只产生 39 条）（R3-06 / R3-07 / R4-06 / R4-07） | **唯一规范 = 合同 §10.3.1 谓词 `record_is_legal` + §10.3.4 的 39 条可产生记录表**；谓词从合同抽取执行，接受集合与独立参考模拟器相等（过度接受 0、接受不足 0）；H4 事件、事件全序、`attempt_id` 稠密；取消见证区分自报告（谓词只验内部一致）与独立事实（代理对账 O2-5） | §10.3、§14.4、§20.5 |
| F-23 | §18 / L6-10 遗留“Amane 裁剪导致 P6 poster 被剔除”的旧语义，与 raw-only 模型冲突（R3-08）；E6-28 只比较开关则可能空跑（R4-09） | 宿主展示 poster 与 P6 raw URL 候选分离；E6-28 冻结确定性输入（缺海报 / 短海报 / 缩略图重排）并要求展示值**实际改变**才算证明，否则 FAIL（NON-VACUITY）/ NOT_RUN | §18、L6-10、E6-28 |
| F-24 | R3 的 §11.2 把号等价放在键集合与 `PluginRaw` 校验之前，缺键 / null / 缺 number 会在解引用处抛异常，混合来源 + 号错被误归 NUMBER_MISMATCH（Gate A：7/16 用例无单一分类）（R4-01） | **唯一规范 = 合同 §11.2 代码块 `map_host_result`**：外层结构 → 键集合 → PluginRaw → 号等价 → 映射 → 最低成功；从合同抽取执行，42 个有序优先级用例 + 20000 次 fuzz 无未处理异常 | §11.2 |
| F-25 | O2 以 `(番号, generation)` 为粒度、无条件“成功恰好 1 个 / 恢复恰好 2 个”与合法的重复显式重试冲突；pre-proxy 取消 / 致命的 `POST = 0` 被误拒；`attempt_id` 只验单条记录（R4-03 / R4-04） | **唯一规范 = 合同 §14.4 请求账本模型**：任务数由独立调用脚本历史 `calls(N)` 决定；pre-proxy `POST = 0` 须被 `Mf` 注入清单或传输类 outcome 解释；`attempt_id` 靠 `seq` 稠密保证跨记录（含溢出后）唯一 | §9.2、§13.3、§14.4 |
| F-26 | R3 同时要求“累计计数溢出后仍准确”和“全部计数 / 峰值由保留记录重算”（Gate D：20001 条时 submitted 20001 vs 20000、unknown 5 vs 4，历史峰值 5 vs 窗口 1）（R4-05） | **唯一规范 = 合同 §20.5**：累计状态 Z 在线更新、溢出后权威；保留窗口 W 只作证据窗口；全历史安全不变量靠测试工具在丢弃前分段流式取走验证，缺口 ⇒ NOT_VERIFIED | §14.4、§20.5 |
| F-27 | L6-01 仍声称“真正的证明是逐字段双侧证据”（R4-08） | 统一为：任务侧 field_sources（必要条件）+ raw 键集合恰好插件（独占来源验收）+ PluginRaw 值（内容证据）；展示列 field_sources / 锁 / 时间戳不是证据，E1/E2/E3/R0 不得重新启用 | §11.3、L6-01 |
| F-28 | 证据状态没有统一词汇，NOT_RUN / UNVERIFIED 可能被统计为通过（R4-09） | 合同 §23.2：PASS / FAIL / NOT_RUN / UNVERIFIED / BLOCKED，后三者不计为 PASS | §23.2 |

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
Design-R3                     : SUPERSEDED BY DESIGN-R4 CANDIDATE
Design-R4                     : VERIFIED CLOSURE CANDIDATE（待独立复核）
Design Accepted Head          : NOT ESTABLISHED
Implementation                : NOT STARTED
Production Modified           : NO
Tests Modified                : NO
```

下一步：**独立 Design-R4 复核**（G / C / x；验证 R4-01..R4-09 全部修复，且 R1–R3 已接受事项未回退；状态机的独立性与 E6-28 的真实宿主证明均尚未建立）。通过并由 Governance Coordinator 接受之前禁止 Developer 开始 S1。Reviewer 的强制审查点见合同第 30 节（DR-01..DR-10、Design-R1 追加的 DR-11..DR-18、Design-R2 追加的 DR-19..DR-22、Design-R3 追加的 DR-23..DR-28、Design-R4 追加的 DR-29..DR-35）：

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
