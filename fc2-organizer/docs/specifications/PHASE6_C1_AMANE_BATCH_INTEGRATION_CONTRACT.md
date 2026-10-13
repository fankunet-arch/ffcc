# PHASE 6 / P6-C1 — Amane 真实批量集成与批量收尾（Real Amane Batch Integration & Closure）合同

```text
文档状态                    : DESIGN CANDIDATE — NOT YET ACCEPTED
Phase 6                     : DESIGN CANDIDATE
P6-C1                       : DESIGN CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract             : NOT YET ACCEPTED
Construction Plan           : NOT YET ACCEPTED（docs/P6_C1_CONSTRUCTION_PLAN.md）
Design-R1                   : SUPERSEDED（R1-01..R1-09；Design-R1 Head c05c7ebca04ded9e1853b71e82796a419fadc192）
Design-R2                   : SUPERSEDED BY DESIGN-R3 CANDIDATE（R2-01..R2-05；Design-R2 Head b071d149f8f99385851cb6f8dc38f9904c624262；三份增量审查仍有 7 项 MUST-FIX + 1 项 SHOULD-FIX）
Design-R3                   : SUPERSEDED BY DESIGN-R4 CANDIDATE（R3-01..R3-08；Design-R3 Head 85d3da8b7450fd50a112e8bbc47a248b9473e9a9；三份增量复核仍有 7 项 MUST-FIX + 2 项 SHOULD-FIX）
Design-R4                   : SUPERSEDED BY DESIGN-R5 DRAFT（R4-01..R4-09；Design-R4 Head 6ccf7d38ef637af6e8b481475441b4d1e13dfcca；独立复核 G / C / x：FAIL，C 报告 BLOCKED — SECURITY AUTHORITY）
Design-R5                   : COMMITTED REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（Reviewer C / G / x 均 FAIL；候选内容：致命异常 F3 = 确定性所有权清理 + 异常引用脱离，生产路径禁止 gc.get_referrers / sys._getframe / frame.clear；X-NARROW 仅用于独立载荷对照，四个植入凭据用例与 trace 注入 = OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS（B1 / B2）；Reviewer x 的 Findings Addendum（x-01..x-07）已交付并由 R1-04..R1-10 在本地修复，R5-02..R5-07 与其编号对应由 Governance 保留，均不得视为已关闭；本状态不得改写为 PASS）
R5 Candidate                : 22a3fa4922c655cb5ce127ee2825b1678f4855db（已提交并推送的 R5 Review Candidate；不得改写 / amend / reset）
Design-R5-R1                : UNIFIED CLOSURE REPAIR — LOCAL DRAFT（本地未提交；R1-01..R1-10 已在本地修复并附红绿证据，待 Governance 审阅；这不是 Review Candidate，不是 CLOSED / PASS；HG-1 = ACCEPTED — NOT EXECUTED；S1 = NOT AUTHORIZED）
Design Accepted Head        : NOT ESTABLISHED
Implementation              : NOT STARTED
Production Modified         : NO
Tests Modified              : NO
Risk Class                  : C
Package Frozen Base         : 4189b9552d26b3cc5273e0ac09e46e5a3759121d（P5-C2 Final Closure Docs Head）
Governance Authority        : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Upstream Final Reviewed Head: 1ef23247c2c65649589e9919c00093901bbcb517（P5-C2 Final Reviewed Technical Head）
Phase 6 package count       : 1（P6-C1；P6-C2 默认不存在）
Branch                      : claude/phase6-c1-amane-batch-integration
Next                        : Governance Coordinator 审阅 Design-R5-R1 UNIFIED CLOSURE PRE-COMMIT REPORT（批准之前不得 commit / push R5-R1，不得改写 / amend / reset R5 Candidate；建立 Design Accepted Head 之前禁止 Developer 开始 S1；HG-1 仍为 ACCEPTED — NOT EXECUTED）
```

**Design-R1 修订索引**（三份独立 Design Review 的合并 findings；本文所有改动都在设计文档内，未改 production / tests / Amane 源码）：

| R1 | 主题 | 主要落点 |
|---|---|---|
| R1-01 | 持久化 Metadata 的字段级 provenance（任务结果 ≠ 持久化记录） | §7.6、§8.5、§11.2–§11.5、§12.1、I6-09..I6-11、E6-07 / E6-16、M6-02 / M6-17 / M6-18、L6-18 |
| R1-02 | 提交尝试 ≠ 已创建任务（`SubmissionState`） | §9.2、§13.1、I6-05、E6-08 / E6-13、M6-16 / M6-19 |
| R1-03 | 异常 `__context__` / 帧局部不得保留凭据 | §8.3、§20.2、I6-14、E6-03 / E6-17、M6-12 |
| R1-04 | 数据库终态 ≠ 执行协程已停止（取消真实性） | §10.3、`CancelOutcome`、L6-04、E6-09 / E6-14、M6-14、Master F-4 |
| R1-05 | 门面 busy-first 不可直接委托 P4 | §9.5、§13.3、I6-21、E6-10、M6-20 |
| R1-06 | 跨轮 Phase B 冲突不被单轮 preview 发现 | §13.3、§20.4（`AmaneBatchSummary`）、§19.3、L6-16、E6-19 |
| R1-07 | JSON 深度 / 节点 / 集合上限 | §8.4–§8.5、I6-15、E6-06 / E6-17、M6-21 |
| R1-08 | Amane 默认 worker concurrency 为 10（不是 3） | §14、L6-07 |
| R1-09 | HG-1 精确化 | §5.4、E6-01 |

**Design-R2 修订索引**（Design-R1 增量审查后剩余的 5 项阻塞；仍然只改设计文档）：

| R2 | 主题 | 主要落点 |
|---|---|---|
| R2-01 | 字段内容的值级来源证明：撤销 E1/E2/E3/R0；改为只从 `raw["ffcc.fc2-metadata"]`（插件原始记录）派生字段值 | §7.3、§7.6、§8.5、§11.2–§11.5、§12.1、§22.3、I6-09 / I6-11 / I6-25、E6-06 / E6-07 / E6-16、M6-17 / M6-18 / M6-23、L6-06 / L6-18 / L6-19 |
| R2-02 | 异常 / 凭据边界扩展到整个 `src/fc2_amane_batch/**`，并区分“新引入的泄漏”与“调用方持有对象本身的认证状态” | §8.3.1（保护面 P1–P3、禁入内容 F、构造规则 C1–C7、失败矩阵）、§20.2、I6-14、E6-17、M6-12 |
| R2-03 | JSON 预扫描成本模型修正为 `O(B)`（`B ≤ MAX_RESPONSE_BYTES`），辅助空间 `O(MAX_JSON_DEPTH)` | §8.4、E6-06、M6-21 |
| R2-04 | 孤儿任务与并发 oracle：区分 A / K / H，不再要求 `\|H\| ≤ M` | §14、E6-10、M6-11、I6-29、L6-07 |
| R2-05 | `SubmissionState` / `CleanupTrigger` / `CancelOutcome` / `AggregateTerminal` 正交模型与合法组合；`NOT_APPLICABLE` ⇔ 未触发清理 | §10.3、§20.5、E6-08 / E6-09、M6-24、I6-28 |

**Design-R3 修订索引**（Design-R2 增量审查后剩余的 7 项 MUST-FIX 与 1 项 SHOULD-FIX；仍然只改设计文档）：

| R3 | 主题 | 主要落点 |
|---|---|---|
| R3-01 | 混合来源 `raw` 必须拒绝：`set(raw.keys()) == {"ffcc.fc2-metadata"}` | §7.6、§11.2（代码块）、§11.3.2、§12.1、E6-07 / E6-16（⑤）、M6-25、I6-30 |
| R3-02 | 时间戳证据与事件先后不得混淆：重命名为 `TimestampRelation`（仅两个字符串的比较标签），CASE A–D | §11.3.4、§22.3 ①②②′②″③⑦、§20.5、L6-19、E6-07、M6-26 |
| R3-03 | `_transport` / `_call` 的取消与致命异常出口：局部清理 C5a、响应体清理 C5b、`CancelledError` 新实例 C5c（方案 A）、致命异常原样传播并披露第三方帧（方案 B） | §8.3.1（P2、C5/C5a/C5b/C5c、失败矩阵）、§20.2、E6-17、M6-12、L6-21 |
| R3-04 | O2 以真正的 aggregate attempt 为单位：`attempt_id` + `X-FFCC-Attempt` | §8.3、§14 第 4–6 条、§22.5、E6-10 / E6-13、M6-11 / M6-28、I6-31 |
| R3-05 | O3 的已知 id 与等待生命周期：H1–H4、K 的进入 / 退出、可复算区间、oracle 自检 | §14、§22.5、E6-10、M6-11 / M6-28、L6-22 |
| R3-06 | POST 前 / 在途 / 确认后的取消与致命异常合法组合矩阵 | §10.2、§10.3.1 谓词与 §10.3.4 表、E6-08、M6-24 |
| R3-07 | 取消请求的 L1 见证：`cancel_post_attempted` / `cancel_event` / `task_known_event` / `attempt_id` 与代理对账 | §10.3.3、§14.4（O2-5）、§20.5、E6-09、M6-27 |
| R3-08 | 图片裁剪语义：宿主展示 poster 与 P6 raw URL 候选分离 | §18、L6-10、E6-28 |

**Design-R4 修订索引**（Design-R3 增量复核后剩余的 7 项 MUST-FIX + 2 项 SHOULD-FIX；每个主题只有**一个**规范性定义，其它章节引用它）：

| R4 | 主题 | 唯一规范性定义 | 引用 / 证据 |
|---|---|---|---|
| R4-01 | `raw` 校验顺序与唯一错误分类 | §11.2 代码块 `map_host_result` | §12.1、E6-07、M6-29、I6-34 |
| R4-02 | 异步清理：无 detached task、有界、致命原样传播 | §10.2 清理生命周期 | §8.3.1 C1 / C5a / C5c、E6-03 / E6-09 / E6-17、M6-30、I6-35、L6-03 / L6-21 / L6-23 |
| R4-03 | 代理前取消 / 致命的对账；`attempt_id` 跨记录唯一 | §14.4 请求账本模型（O2-1..O2-8） | §10.3.2、§20.5、E6-10、M6-32 |
| R4-04 | 重复显式重试的任务基数由脚本历史决定 | §14.4（`calls(N)`、4.5 用例表） | §9.2 第 6 条、§13.3、E6-13、I6-36 |
| R4-05 | 审计溢出：累计状态 `Z` 与保留窗口 `W` 分开 | §20.5 | §14.4 第 5 点（分段流式验证）、E6-10、M6-31、I6-37 |
| R4-06 | confirmed 必有合法 H4 事件；事件全序；attempt_id | §10.3.1 谓词 + §10.3.2 | §20.5、E6-08、M6-32 |
| R4-07 | 取消状态矩阵（1728 穷举 vs 独立模拟器 39 条） | §10.3.1 谓词 + §10.3.4 表 | E6-08 / E6-09、M6-24、I6-28 |
| R4-08 | 撤销旧“双侧逐字段证据”声明 | §11.3 | L6-01、Master F-5、Plan §3 |
| R4-09 | 图片裁剪的非空验证 | §18 E6-28 冻结用例 | E6-28、M6-33、§23.2 |

**Design-R5 修订索引**（Design-R4 独立复核 G / C / x 的 12 项 findings；仍然只改三份设计文档，不动 `pyproject.toml`、CLOSED P4 / P5、Amane、production、tests）：

| R5 | 主题 | 唯一规范性定义 | 引用 / 证据 |
|---|---|---|---|
| R5-01 | `record_is_legal` 必须接受真实枚举且不抛 `KeyError` | §10.3.1 `gate:host_attempt_record_types` + `gate:record_is_legal` | §20.5、E6-08、M6-35、I6-38、DR-36 |
| R5-02 | 完整类型 / 见证约束；状态数诚实（63，不是预设 39） | §10.3.1、§10.3.4 | E6-08、M6-35、DR-37 |
| R5-03 | H3 已送达而 H4 缺席合法；H3 单独不授权取消 | §14.4 4.2 / O2-4、§10.3.1 | E6-10、M6-36、DR-38 |
| R5-04 | 在途快照与静止快照分开；`Z` 更新点；五个必测场景 | §20.5 | E6-10、M6-37、I6-39、DR-39 |
| R5-05 | 乱序完成：`completion_seq`、FIFO 窗口、收集器游标、`NOT_VERIFIED` | §20.5、§14.4 第 5 点 | E6-10、M6-38、DR-40 |
| R5-06 | 取消请求未确认（`NO_RESPONSE`）与已确认非终态（`NOT_TERMINAL` / `OBSERVATION_FAILED`）拆分，严格优先级 | §10.2 第 3 条、§10.3 `CancelOutcome`（10 个成员） | E6-08 / E6-09、M6-34、I6-40、DR-41 |
| R5-07 | Master F-20 与合同安全范围措辞一致；`FAIL` / `NOT_RUN` / `UNVERIFIED` / `BLOCKED` 不混用 | §10.2 第 8 条、§10.6、§23.2 | Master F-20、L6-23、DR-42 |
| R5-08 | `map_host_result` 第 7 步做 P5 I22 URL 卫生并精确计 `dropped_url_count` | §11.2 代码块 | §11.4、E6-07、M6-39、I6-41、DR-43 |
| R5-09 | 宿主展示 poster 裁剪不进入 P6 URL 过滤；`dropped_url_count` 只计 `PluginRaw` 清洗 | §18、§11.4 | L6-10、Master F-8、DR-44 |
| R5-10 | Python 3.11.0+ 支持：不依赖 `asyncio.timeout` / `wait_for` | §10.2 | E6-25 / E6-08 / E6-09 / E6-17、M6-40、DR-45 |
| R5-11 | 注入 `transport=`：**方案 A，APPROVED FOR DESIGN REVISION ONLY（治理裁决）**；公共构造面撤销 `transport=`（及衍生的 `_clock` / `_sleep`），故障改由真实回环代理注入；方案 B 否决 | §10.6、§20.3 / §20.4、§22.5 | E6-03 / E6-05 / E6-09 / E6-17、M6-42、DR-46 |
| R5-12 | 非 `httpx` 的普通 `Exception` 安全分类（catch-all → `HOST_NETWORK`，块外抛出） | §10.2 第 7 条、§8.3.1 C5 | E6-17、M6-41、I6-42、DR-47 |

**Design-R5 治理安全附加裁决（Governance Security Addendum）**：

| 项 | 主题 | 落点 |
|---|---|---|
| G-1 | R5-11 方案 A 的设计修订授权（不是豁免）；API 兼容性、故障覆盖矩阵 | §10.6、§22.5、E6-03 / E6-05 / E6-09 / E6-17、M6-42 |
| G-2 | 致命 `BaseException`：F1 / F2 均未被接受；评估并采用 F3（同一实例，确定性所有权清理 + 异常引用脱离）；**IMPLEMENTED CANDIDATE（见 C-1..C-10；R5 Candidate 已被独立复核判 FAIL，R5-R1 修复准备中），非 Security PASS** | §10.5、C1 / C5c / C8、L6-21 / L6-24 / L6-25、M6-45..47、DR-48 |
| G-3 | Python 3.13：正式运行时验收项（设计探针已执行，实现验收 NOT_RUN） | E6-25、L6-23 |
| G-4 | 非合作服务端：总 deadline（响应头 / 响应体 slowloris），墙钟上界与 `Task.cancelling()` / `uncancel()` 记账 | §10.2、E6-09、M6-43 / M6-44、L6-26、DR-49 |
| G-5 | 状态机独立性：63 状态仍只是 Designer 的内部验证；脚本与原始输出全部保留供 Reviewer x 独立交叉验证 | §10.3.4、证据包 |
| G-7 | 取消归属与竞态（Gate C-Final-01）：O1–O5、交错 R1–R11、红孪生、3.11 / 3.13 差异 | §10.2、E6-09、M6-48、DR-51 |
| G-8 | F3 安全覆盖（Gate C-Final-02）：六个概念分开；抛出方植入的 `args` / `__dict__` / `__notes__`：四个植入凭据用例保留并逐项说明，**不标 X-NARROW PASS**，按 B1 标 `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`（X-NARROW 只保留给独立载荷对照；Y / Z 继续 REJECTED） | §10.5、L6-25、E6-17、DR-52 / DR-57 |
| C-1 | **R5-C-01** 致命异常落在异常处理体 / `finally` / try 之后的窗口：边界所有权（内联致命处理体、`_transport` 无致命处理体、持有者重绑 + 引用脱离、整条链切断；不访问任何帧）；穷举窗口探针 | §10.5、C9、E6-03 / E6-09 / E6-17、M6-51、DR-54 |
| C-2 | **R5-C-02** C 级槽位盲区：链整条切断，审计器改用 `gc.get_referents`，红绿孪生 | §10.5、E6-17、M6-52、DR-55 |
| C-3 | **R5-C-03** 外部取消 + deadline + 内层转换：单点按计数分类，`cancelling() > base` ⇒ 抛出新的 `CancelledError`；RC10 系列 | §10.2、E6-09、M6-53、DR-56 |
| C-4 | **X-NARROW**（仅独立载荷对照）：六个强制条件、四个植入用例逐项说明（现标 OUT_OF_THREAT_MODEL，见 B1）、受支持依赖矩阵与矩阵守卫；Y / Z REJECTED | §10.5、L6-25 / L6-27、M6-55、DR-57 |
| C-5 | **R5-CL-01**（重开后的最终修复）`frame.clear()` 终结挂起的生成器 / 协程帧（3.11 / 3.12 运行其 `finally`；3.13 / 3.14 抛 `RuntimeError`）：F3 采用**确定性所有权清理 + 异常引用脱离**——生产路径**不访问任何帧**（不 `clear()`、不枚举引用者、不取栈帧）；拥有响应数据的边界帧自己用纯 `STORE_FAST` 重绑，然后把 `__traceback__` / `__context__` / `__cause__` 置 `None`；红 / 绿孪生（含 `gc.freeze()`）+ Reviewer C `frameclear.py` / `liveness.py` 基线 | §10.5、C8 / C9、E6-09 / E6-17、M6-56、DR-58 |
| C-9 | **R5-GOV-01** F3 依赖不完整的 `gc.get_referrers()` 枚举（`gc.freeze()` 后存活的协程对其不可见 ⇒ 被清理、`finally` 被执行）：生产路径彻底移除 `gc.get_referrers` / `sys._getframe` / `frame.clear`，不得以 `gc.collect()` / `gc.get_objects()` / 全堆扫描替代；AST 守卫 `fatal_path_guard.py` + 变异；旧版在 `gc.freeze()` 下失败，新版通过 | §10.5、C8、E6-03、M6-56 / M6-58、DR-61 |
| C-10 | **R5-NEW-01** F3 为清理帧而调用 `sys._getframe` / `gc.get_referrers`，其审计事件把带 `Authorization` 的 `Request` 的帧作为参数交给进程内审计钩子：P6 不得主动把敏感帧作为新增审计事件参数向外暴露；公共 client 与 `aggregate` 两条路径分别验证（Reviewer C `audit_getframe.py` 原样运行 + 派生的 `audit_f3.py`） | §10.5、E6-17、M6-58、DR-62 |
| C-6 | **R5-EV-01** 审计器仅在头部含测试 canary 时才报告 `Request`：改为检测任何带 `Authorization` 的 `Request` / `Response.request`，与令牌值无关；非 canary 正向对照 + 变异 | §10.5、E6-17、M6-57、DR-59 |
| C-7 | **B1 进程内信任边界**：P6 不防御同进程恶意代码（`gc` / 帧内省、猴子补丁、私有属性改写、trace / profile、任意异常注入）；不排除正常公共 API、受支持依赖、P6 自身泄漏、普通信号、正常取消 | §10.5 “B1”、L6-29、DR-60 |
| C-8 | **B2 异步致命异常投递边界**：区分 CPython 真实信号投递（仅 eval-breaker 检查点）与调试器 / trace 在任意字节码注入；保证只声明运行时证据覆盖的范围；不改变进程级 `SIGINT` 策略 | §10.5 “B2”、L6-28 / L6-30、DR-60 |
| G-9 | 接缝撤销后的验收能力与故障网络独立性（Gate C-Final-03）；`_clock` / `_sleep` 移除已验证 | §10.6、§22.5、E6-03 / E6-05、M6-49 / M6-50、DR-53 |
| G-6 | 审查证据：保留原 R5 证据包（SHA-256 `e75ed9509a78d63503132567330200a881ae7a80a915cae98ca79ec3b6ea03c9`）；本轮修改后的证据包有新的 SHA-256 | 报告 |

**Design-R5-R1 统一修复状态（本地未提交；不是 Review Candidate；不是 CLOSED / PASS）**：Design-R5 Candidate 已被 Reviewer C / G / x 独立复核判 FAIL。下表是已冻结的 R1 修复范围与本地修复落点；所有项都**待独立复核**。

| 编号 | 来源 | 级别 | 范围 | 主要落点 | 状态 |
|---|---|---|---|---|---|
| R1-01 | R5-GOV-02 + G-R5-G-01 | MUST-FIX | 统一 F3 的唯一机制与断言口径：安全断言是敏感引用不可达，不是“所有真实信号下 traceback 绝对不含本包帧”；边界入口检查点留下的无敏感局部边界帧允许存在；旧 `frame.clear` 方案被 M6-56 明确拒绝 | §8.3.1 P2 / C5a / C5c / C8 / C9、§10.5、E6-09 / E6-17、I6-32 / I6-44、L6-21 / L6-24、Master F-20 | 本地修复；待独立复核 |
| R1-02 | Governance | MUST-FIX | Master / Plan 引用合同 §30 的完整 DR 范围并明确 Reviewer 责任边界；M6-01 起连续编号不重排 | §30、Master、Plan | 本地修复；待独立复核 |
| R1-03 | Governance | SHOULD-FIX | 状态：`Design-R5: COMMITTED REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL`、`R5 Candidate: 22a3fa4922c655cb5ce127ee2825b1678f4855db`、`Design-R5-R1: UNIFIED CLOSURE REPAIR — LOCAL DRAFT`；删除过时的“先批准 pre-commit 再 commit”下一步 | 三份文档状态块 | 本地修复；待独立复核 |
| R1-04 | x-01 | MUST-FIX | 严格类型与不可变性：`terminal_status` 严格 `str`，`HostAttemptRecord` 构造处拒绝可变别名；`record_is_legal` 对任意输入返回 `bool` | §10.3.1（gate 代码块）、E6-08、M6-60、DR-64 | 本地修复；待独立复核 |
| R1-05 | x-02 | MUST-FIX | H3 / H4 时序歧义：`H2 = H3 = TRUE, H4 = FALSE` 的合法情形（含迟到的 `202`） | §14.4 4.2 / O2-4 / 4.6、§10.2、E6-10、M6-61、DR-65 | 本地修复；待独立复核 |
| R1-06 | x-03 | MUST-FIX | `Z` / `W` / `InFlight` 统计域与四类不变量；`Z.submitted` 在途与溢出后的口径 | §10.3.4 计数口径、§20.5、E6-10、M6-62、DR-66、Master F-26 | 本地修复；待独立复核 |
| R1-07 | x-04 | MUST-FIX | 删除 `highest_dropped_seq`；`seq` 与 `completion_seq` 两个序号空间分别证明；缺失历史 ⇒ `NOT_VERIFIED` | §14.4 O2-3、§20.5、E6-10、M6-63、DR-67、Master F-25 / F-26 | 本地修复；待独立复核 |
| R1-08 | x-05 | MUST-FIX | 快照全局上界、`completion_seq` 唯一 / 稠密、Harvester 冲突检测（不得 `setdefault`） | §14.4 第 5 点、§20.5、E6-10、M6-64、DR-68 | 本地修复；待独立复核 |
| R1-09 | x-06 | MUST-FIX | 取消确认与终态观察必须有独立代理网络事实 | §14.4 O2-5 / 4.7、§10.3.3、E6-09、M6-65、DR-69、Master F-22 | 本地修复；待独立复核 |
| R1-10 | x-07 | 汇总 | x-03 与 x-04 的文档一致性汇总（不是第七个独立运行时缺陷）：Contract §10.3 / §14.4 / §20.5、Master F-22 / F-25 / F-26、Construction Plan、E6-08 / E6-09 / E6-10、Gate B / D / E | 全部 | 一致性已检查（Gate E）；待独立复核 |
| R5-02..R5-07 | Reviewer x 旧编号 | — | Reviewer x 的完整 Findings Addendum（x-01..x-07）已交付并由 R1-04..R1-10 对应修复；旧编号与新编号的对应关系由 Governance 保留，本文不推断 | — | **不得视为已关闭** |


本文是 P6-C1 的 **Frozen Contract 候选**。它只有在独立 Design Review PASS 之后才成为 Frozen Contract；在此之前不得被解读为 FROZEN /
DESIGN PASS / IMPLEMENTATION AUTHORIZED。唯一 authority 转换：独立 Design Review PASS → 该 Design Candidate SHA 成为 Design Accepted Head
（Frozen Contract / Plan Head、Implementation Input）→ 才允许 Developer 开始 S1。

配套文档：

| 文档 | 作用 |
|---|---|
| `docs/PHASE6_MASTER_PLAN.md` | Phase 6 总体裁决（一个 C、不拆 P6-C2、架构、Phase 7 边界、风险登记） |
| 本文 | P6-C1 的 Frozen Contract 候选（行为、接口、不变量、证据门） |
| `docs/P6_C1_CONSTRUCTION_PLAN.md` | S1 / S2 / S3 施工计划候选（Governance v2 强制头、文件清单、允许 / 零 diff 范围、停止条件） |

三者范围、Risk Class、Frozen Base、Governance Authority 必须逐字一致；不一致即设计缺陷（U6-12）。

---

## 1. 目的与用户能力

P6-C1 回答一个问题：**一个真实用户能否在不修改任何已 CLOSED 代码的前提下，把一个“脏”媒体目录经由真实的 Amane 宿主，批量地
走完 “识别番号 → 多来源元数据 → 图片 → NFO → 产物清单 → 执行前预检 → 批量预览与汇总”，并且在失败、重试、取消下行为正确、可审计？**

用户可见的完整纵向能力（Vertical Closure）：

```text
dirty media root
  → 扫描并识别规范 FC2 番号（P4）
  → 有界并发的批量调度（P4 BatchOrchestrator / Phase 3 BatchScheduler）
  → 每个番号向真实 Amane 宿主提交一个 SCRAPE 任务（本合同新增）
  → 宿主 route 中的 ffcc.fc2-metadata 插件（P5，CLOSED）→ Core MultiSourceEngine（Phase 3，CLOSED）
  → Amane Metadata 持久化 → 本合同的“宿主结果 → Core AggregationResult”桥
  → P4 继续：planning → publication → 图片 → NFO → 产物清单 → 执行前预检
  → BatchPreview + 确定性批量汇总 + 运维审计（与语义结果分离）
  → 失败子集重试、取消（精确到任务）、取消不确定性的显式报告
```

P6-C1 **不**执行任何用户媒体的真实文件整理（第 19 节）。真实文件系统验收是 Phase 7。

**副作用声明（不得写成笼统的“Phase 6 只读”）**：Amane SCRAPE 本身会产生**宿主级持久副作用**——持久化的 Task、Metadata upsert，以及在用户配置允许时可能产生的其它宿主所有的副作用
（如 `ACTOR_SCRAPE` 后继任务、Resource 物化）。因此 P6 既**不**宣称 durable resume，也**不**宣称“对 Amane 宿主数据库只读”。验收宿主可以关闭 actor auto scrape / resource download / 翻译以降低不确定性；
生产环境中 P6 **不得**偷偷 PATCH 用户的 Amane 全局配置。

---

## 2. 权威、坐标与优先级

```text
Frozen Contract (本文，Design Review PASS 之后)
>
Frozen Construction Plan
>
docs/PROJECT_GOVERNANCE_ACCELERATION.md
>
Task Prompt
```

| 坐标 | 值 | 说明 |
|---|---|---|
| Package Frozen Base | `4189b9552d26b3cc5273e0ac09e46e5a3759121d` | P5-C2 Final Closure Docs Head；P6-C1 的 package baseline |
| Governance Authority | `3b9d39e9adbcc8a009707486eebbb8736a5b1c4d` | `docs/PROJECT_GOVERNANCE_ACCELERATION.md` 的 accepted governance head；**不是** Package Frozen Base |
| P5-C2 Final Reviewed Technical Head | `1ef23247c2c65649589e9919c00093901bbcb517` | P5-C2 CLOSED；Independent Level 1 PASS；Risk Class C |
| Amane v0.15.0 | tag object `3292c957a092f85ddde1ba7462ffe9813827f4f1`；peeled commit `45dff2159369883e028a296d775a4598836c1ddd` | P5 已正式支持的最低版本目标 |
| Amane v0.18.0 | tag object `7d2190704fa1e3c0f7f86889111d12b9fa6701c8`；peeled commit `0a8a731d7746bde5e8828d1eb74c7bd9752b42e4` | P5 已正式支持的当前稳定版目标 |

设计期已用 `git rev-parse` 在 `https://github.com/sqzw-x/amane.git` 的 bare clone 上核对以上四个 SHA 全部相符（第 7.1 节）。

支持声明是**坐标级**的（沿用 P5-C2 I-C2-14）：P6-C1 的必需坐标是 **SC-03**（v0.15.0 / source host / Windows x64）与 **SC-04**
（v0.18.0 / source host / Windows x64）；SC-01 / SC-02（冻结桌面包）为**可选**坐标，只有实际运行并 PASS 才可声明，否则保持 `UNVERIFIED`；
macOS / Linux / Docker 保持 `UNVERIFIED`。不得写“支持 v0.15.0 / v0.18.0”这类脱离平台 / 形态的概括。

---

## 3. 范围与非目标

### 3.1 范围（本包交付）

1. 新增独立 package `fc2_amane_batch`（第 5.3 节）：Amane Host 的**外部 HTTP client / bridge**。
2. Amane-backed `AggregationEngine`：满足 Phase 3 `AggregationEngine` Protocol（`async aggregate(number) -> AggregationResult`），注入现有
   `BatchOrchestrator`。
3. 宿主任务生命周期：提交 / 观察 / 精确取消 / 有界超时。
4. 宿主结果 → Core `AggregationResult` 的 fail-closed 映射（含结构化失败映射）。
5. 批量门面：扫描 + 预览 + 失败子集重试 + 汇总 + 运维审计。
6. 真实 Amane v0.15.0 与 v0.18.0 宿主上的确定性纵向验收（≥ 10 个 FC2）、失败 / 重试 / 取消 / 并发 / 确定性 / mutation 证据。
7. 一次真实公网 live smoke 尝试（结果如实记录，缺失则如实声明 UNVERIFIED）。

### 3.2 非目标（明确不做；任何一项出现在实现里都是 STOP 条件，见第 28 节）

```text
× 真实 organize 执行：不调用 BatchOrchestrator.execute / execute_filesystem / 任何会 mkdir、rename、move、copy、delete 的 API
× Amane ORGANIZE / TRASH / CLEANUP / UPSCALE / R18_IMPORT / RESCRAPE / ACTOR_SCRAPE 任务的提交
× 修改 Amane 源码、monkeypatch Amane、import amane.*、读取 Amane SQLite、访问 Amane Repository
× 修改 P5 plugin（ffcc.fc2-metadata）、P5 Core wheel / plugin zip、P5 release 安全机制
× 修改 P4 BatchOrchestrator / BatchScheduler 的任何生产语义
× 第二套 scheduler、隐藏 worker pool、无界 fan-out
× durable batch id / checkpoint 文件 / JSON resume / pickle / SQLite 状态 / 跨进程锁 / 进程崩溃后恢复
× 使用 Amane POST /tasks/batch 的 retry / delete 动作作为重试机制
× 修改用户的 Amane 全局配置；读取 Amane /api/config（含 cookie / token）
× 读取 Amane 日志、解析任何错误文本 / 日志文本 / 异常消息作为控制依据
× 重建跨 P5 边界已丢失的内部 provenance（JavDB / FC2PPVDB / “source X 选了 title”）
× 在 P4 一侧声明 PARTIAL 的细分来源失败
```

---

## 4. 风险分级与 C 粒度裁决

```text
Risk Class: C
```

Risk C **不是**因为 Phase 6 会移动文件（它不会）。Risk C 来自**新的集成边界**：

| 风险点 | 为什么是 Risk C |
|---|---|
| Amane Host HTTP API 边界 | 跨进程、跨版本（v0.15.0 / v0.18.0）的外部系统契约 |
| 宿主认证 / 凭据处理 | Bearer token 的注入、传输、泄漏面（repr / 异常 / 日志 / 预览 / 诊断） |
| 宿主任务所有权 | 只能操作“自己创建的那一个任务”；误操作会影响用户的其它任务 |
| 宿主任务取消 | 取消的语义是**异步且可能不确定**的（第 10 节） |
| 宿主侧持久化 SCRAPE 生命周期 | 宿主会把结果写入用户的 Amane Metadata 库；任务本身持久化在宿主（第 7.6、27 节） |
| 失败歧义 | 提交超时后任务是否已被创建？取消后任务是否已停止？——必须显式建模为“不确定”，不得猜测 |

因此：**新的 Frozen Contract 必须先通过独立 Design Review，之后才允许 S1**；Phase 6 完成后还有**一次** C-level Independent Level 1 Review。
S1 / S2 / S3 默认连续施工，不逐 S Review（除非触发第 28 节的升级门）。

### 4.1 Governance v2 “四问”（针对“是否拆出 P6-C2”）

1. **为什么不能和前一个 C 一起完成？** 前一个 C 是 P5-C2（已 CLOSED）。P6 是新的宿主批量集成边界，不能追溯塞进 P5。
2. **单独拆出 P6-C2（Failure / Retry / Batch Closure）降低了什么具体风险？** 没有。失败映射、重试、取消、汇总与真实集成**使用同一个
   host-task 边界、同一套 client、同一份审计与同一组真实宿主**；拆开后 P6-C1 无法在没有失败 / 取消语义的情况下被独立验收
   （一个只处理成功路径的 Host client 会在 Review 时被要求补齐失败路径，等于把 C2 的内容回退到 C1）。
3. **该风险是否值得额外增加一次“开发停止 + Review + Closure”？** 否。
4. **如果取消这个边界（即不拆），是否影响 correctness / safety / auditability？** 不影响；合并反而提高 auditability（一份证据覆盖完整的
   host-task 生命周期）。

结论：**Phase 6 只有一个 C**。P6-C2 默认不存在；只有出现“无法在同一个 C 内安全控制的、真实且独立的 Risk-C 边界，并且拆分确实提高
correctness / safety / auditability”时才允许重新提出（Master Plan 第 5 节）。代码多 / 测试多 / 文件多 / 模型多 / helper 多**不是**理由。

---

## 5. 复用、不可变性与包位置

### 5.1 CLOSED 边界与复用方式

| CLOSED 边界 | P6-C1 如何使用 | 禁止 |
|---|---|---|
| `fc2_metadata_core`（Phase 1-3） | 只使用公共模型：`AggregationResult` / `AggregateStatus` / `SourceResult` / `SourceStatus` / `SourceErrorKind` / `NormalizedMetadata` / `normalize_fc2_number` / `require_canonical_number` / `validate_base_url` / `BatchConfig` | 修改；构造 Core 内部 `SourceExecutionTrace` 以伪造执行 |
| `fc2_organizer.discovery` | `discover_media` / `DiscoveredMediaItem` / `DiscoveryPolicy`（门面 `preview_root`） | 修改 |
| `fc2_organizer.orchestration`（P4-C8） | **注入** Amane-backed engine 的 `BatchOrchestrator(...).preview(...)`；`OrchestrationConfig`；`BatchPreview` / `ItemPreview` / `PreviewSummary` / `IssueReason` / `OrchestrationStage` / `PreviewState` | 调用 `execute` / `preview_retry` / `merge_retry`（第 13、19 节）；伪造 / 重建其模型 |
| `fc2_organizer.images`（P4-C5） | 调用方传入的 `ImageHttpClient`（生产为 `HttpxImageClient`）；`ImageAcquisitionPolicy` | 重写图片获取；依赖 Amane Resource 文件 |
| `fc2_organizer.planning / publication / nfo / materialization / execution / diagnostics` | 经 `BatchOrchestrator` 间接使用 | 直接调用 `execute_filesystem` 或任何写文件系统 API |
| `adapters/amane/fc2_amane_adapter`、`adapters/amane/shim`、P5 release 机制 | 只**读取**其常量作测试对账（`PLUGIN_ID`），不 import 进 `src/` | 修改；把 `fc2_organizer` 塞进 Core wheel / plugin zip；增加 Amane 不存在的 batch plugin capability |

### 5.2 零 production diff 范围（冻结）

以下路径在 P6-C1 全程**零 diff**（`git diff 4189b9552d26b3cc5273e0ac09e46e5a3759121d..HEAD` 机检）：

```text
src/fc2_metadata_core/**
src/fc2_organizer/**                       （含 discovery / planning / publication / nfo / images / materialization /
                                            execution / orchestration / diagnostics 与 __init__.py）
adapters/amane/**                          （含 fc2_amane_adapter / shim / release / api_manifest / README）
tools/ 中全部既有文件
pyproject.toml
docs/PROJECT_GOVERNANCE_ACCELERATION.md  CLAUDE.md
docs/specifications/ 中全部既有文件       docs/review/ 中全部既有 HANDOFF
docs/acceptance/evidence/ 中全部既有文件
```

如果设计或实现过程证明**必须**修改上述任何 CLOSED production 语义，必须立即停止并返回 `AUTHORITY ESCALATION REQUIRED`
（第 28 节 U6-1），列出：必须改哪个 CLOSED package、为什么不可避免、影响范围、兼容性、security impact、regression scope，由 Governance
Coordinator 裁决。**不得**把它写进普通 P6 施工。设计期结论：**无需修改任何 CLOSED production 语义**。

### 5.3 包位置裁决（冻结）：`src/fc2_amane_batch/`（顶层同级包）

任务书建议的名称形如 `fc2_organizer.amane_batch`，并明确“名称由 Designer 决定”。设计期核查发现：**多个 CLOSED 架构测试逐字钉死了
`fc2_organizer` 的顶层子包集合**：

```text
tests/contract/test_discovery_architecture.py:187   top_level_dirs == {discovery, planning, publication, nfo, images, materialization, execution, orchestration, diagnostics}
tests/contract/test_nfo_architecture.py:206         同上
tests/contract/test_planning_architecture.py:212    同上
tests/contract/test_publication_architecture.py:187 同上
tests/phase4_acceptance/test_p4_acceptance_architecture.py:29-30  PUBLIC_PACKAGES = 同一集合
```

在 `fc2_organizer` 下新增 `amane_batch` 会使这些 CLOSED 测试失败，必须修改至少 5 个 CLOSED 测试文件。因此冻结选择**顶层同级包**：

```text
src/fc2_amane_batch/            新增；与 fc2_metadata_core、fc2_organizer 同级
```

* 命名与既有的 `fc2_amane_adapter`（宿主 / 插件侧）形成对照：`fc2_amane_batch` 是**组织器侧**的 Amane 批量集成。
* 依赖方向（冻结）：`fc2_amane_batch → fc2_organizer → fc2_metadata_core`；反向 import 禁止（CLOSED 包不得 import `fc2_amane_batch`）。
* `fc2_amane_batch` **不 import** `amane`、`fc2_amane_adapter`（P5-C1 守卫 `test_core_and_organizer_never_import_amane_and_nothing_else_imports_the_adapter`
  对整个 `src/` 做 AST 检查，本包天然满足）。
* 该包不属于 Core wheel（`tools/build_core_wheel.py` 只打包 `src/fc2_metadata_core/**/*.py`），也不进入 plugin zip；P5 release 机制零影响。
* `pyproject.toml` 已有 `[tool.setuptools.packages.find] where = ["src"]`，自动发现新顶层包，**不修改** `pyproject.toml`。
* 其它 `src/` 级别的钉死（逐一核查）：没有 CLOSED 测试枚举 `src/` 顶层包集合；没有按文本扫描 `src/` 中的 “amane” 字样。

### 5.4 历史 diff 门禁碰撞 HG-1（设计期发现；FUTURE S1 TEST-ONLY COMPATIBILITY REPAIR；三份独立 Design Review 的实质裁决：ACCEPTED；Design-R1 精确化文字）

**本 Design Candidate 不执行 HG-1：`Tests Modified = NO`。** 只有当前设计候选通过独立审查，并由 Governance Coordinator 正式建立 Design Accepted Head 之后，Developer 才允许在 S1 第 0 步按下述精确条款修改那两个历史测试（这不重新打开 HG-1 的实质裁决）。

CLOSED 的 P5-C2 测试中有两个**绑定到 `HEAD` 的历史范围门**：

| 文件 | 门禁 |
|---|---|
| `tests/amane_compat/test_amane_compat_scope_gate.py` | `git diff 232ece06…..HEAD` 必须全部落在 P5-C2 allow-list；`src/.+`、`tests/(?!amane_compat/).+`、`pyproject.toml` 等零 diff；工作树改动同样受限 |
| `tests/amane_compat/test_amane_compat_evidence_reconciliation.py`（“范围门：b8480e74..HEAD”） | `b8480e74…..HEAD` ∪ 工作树只能含被授权的证据面；`src/.+`、`tests/(?!amane_compat/).+` 零 diff |

这两个门禁表达的是“**P5-C2 这一个包**的 diff 范围”，但它们的上界写成了 `HEAD`。P6 分支任何新增文件（包括本设计提交的三份 docs）
都会使它们失败。这不是 production 语义问题，但**是对 CLOSED 测试文件的修改**，必须在合同层面冻结，而不是由 Developer 临时决定。

**设计期实测（用两个文件里的真实正则字面量对真实 `git diff --name-only` 求值）**：

| 范围 | 文件数 | scope_gate（`ALLOWED_PATTERNS` / `FROZEN_PATTERNS`） | reconciliation（`RECONCILIATION_ALLOWED` / `RECONCILIATION_ZERO_DIFF`） |
|---|---|---|---|
| `232ece06…..1ef23247…`（Final Reviewed Technical Head） | 33 | 通过（范围外 0；冻结范围被触碰 0） | — |
| `b8480e74…..1ef23247…` | 12 | — | 通过（范围外 0；零 diff 范围被触碰 0） |
| `232ece06…..4189b955…`（Frozen Base） | 33 | 通过 | — |
| `b8480e74…..4189b955…`（Frozen Base） | 13 | — | **失败**：多出的一个文件是 `adapters/amane/README.md`（P5-C2 纯状态 Final Closure 提交修改；该文件落在 `RECONCILIATION_ZERO_DIFF` 的 `adapters/amane/.+`，且不在 `RECONCILIATION_ALLOWED`） |

即：**reconciliation 门禁在 Package Frozen Base 上，按其断言逻辑求值为红**（P5-C2 Final Closure 修改了 `adapters/amane/README.md`；scope_gate 的 allow-list 允许该 README，因此它在 Frozen Base 上求值为绿）。
设计期只做了上述求值，**没有运行 pytest**（本轮是 docs-only）；S1 第 0 步的基线记录会用真实 pytest 结果确认。若确认为红，它是继承的既有红，不是 P6 引入的，
必须如实标为 `PRE-EXISTING RED @ 4189b95`（不得写成回归；它由 HG-1 的重绑恢复为绿，而不是被掩盖）。

**冻结的最小重绑（HG-1；实质裁决 ACCEPTED；若精确化后的条款不被接受或无法在 60 行内完成 → `AUTHORITY ESCALATION REQUIRED`，Developer 不得自行换办法）**：

**HG-1 的“已命名的断言移交”（恰好两处）与全部其它约束（Design-R1 精确化，消除“不删除任何 assertion”与“移除一个完整测试函数”的文字冲突）**：

1. **允许修改的文件恰好两个**：`tests/amane_compat/test_amane_compat_scope_gate.py` 与 `tests/amane_compat/test_amane_compat_evidence_reconciliation.py`。HG-1 commit 的 diff 文件集合必须**精确等于**这两个文件。
2. **唯一允许被移交（移除并由 P6 新范围门接管）的工作树断言恰好是下列两处，且仅此两处**：
   * `test_amane_compat_scope_gate.py::test_working_tree_changes_are_limited_to_the_allow_list_as_well`（整个测试函数，约 6 行；它是一个“工作树 ⊆ P5-C2 allow-list”的断言，其语义在 P6 分支上必然为假）；
   * `test_amane_compat_evidence_reconciliation.py::_changed_since_authority()` 中的 `working = [... git status --porcelain ...]` 分量（它是**输入采集**，不是 `assert`；删除后该函数只返回已提交 diff，调用它的两个 `assert` 语句保持原样）。
   这两处的语义由 `tests/amane_batch/test_amane_batch_scope_gate.py` 以 P6 的 allow-list 承接（见第 7 条）。**除这两处之外，不删除、不弱化、不改写任何其它 assertion 或测试函数**；机检：两个文件在 HG-1 后的“测试函数名集合”恰好等于 Frozen Base 版本的集合减去上面那 1 个函数名；两个文件除被移交处外的 `ast.Assert` 节点数与 Frozen Base 相同。
3. **四组历史模式常量逐字不变**：`ALLOWED_PATTERNS` / `FROZEN_PATTERNS`（scope_gate）与 `RECONCILIATION_ALLOWED` / `RECONCILIATION_ZERO_DIFF`（reconciliation）这四个模块级常量的 AST 与 `git show 4189b95…:<path>` 中的版本**相同**；因此 allow-list 覆盖与 frozen-pattern 覆盖都不减少。
4. **唯一的“上界重绑”**：把 `git diff --name-only <BASE>..HEAD` 的上界由浮动 `HEAD` 改为不可变常量 `P5_C2_REVIEWED_HEAD = "1ef23247c2c65649589e9919c00093901bbcb517"`（P5-C2 Final Reviewed Technical Head；上表实测两个门禁在该上界上都通过；Final Closure 只追加了纯状态的 `adapters/amane/README.md` 与 `docs/review/P5_C2_HANDOFF.md`）。这同时使 reconciliation 门禁恢复为绿。该常量是 HG-1 唯一新增的模块级名字。
5. **不新增 `skip` / `xfail`**，不关闭 mutation / non-vacuity，不改变任何夹具、导入或其它测试的行为；“Base 可达且是 HEAD 祖先”测试保持不变。
6. **diff 行数上限冻结为 60 行**：HG-1 commit 相对其 parent 的 `git diff --numstat` 对这两个文件的 `added + deleted` 之和 **≤ 60**。超出 → HG-1 违约，停止并 `AUTHORITY ESCALATION REQUIRED`（不再由 Reviewer 在 S1 之后决定）。
7. **P6 新范围门必须覆盖自身的 diff 与工作树，并承接被重绑后失去活动范围的保护**（`tests/amane_batch/test_amane_batch_scope_gate.py`）：
   * `git diff --name-only 4189b95…..HEAD` ⊆ P6 allow-list，闭合范围零 diff；
   * 工作树（`git status --porcelain=v1 --untracked-files=all`）⊆ P6 allow-list（承接被移交的两处工作树断言）；
   * **文本控制字符检查**：对 `4189b95…..HEAD` ∪ 工作树 内全部 `.py` / `.md` / `.json` / `.toml` 文件检查不含 C0 控制字符（`[\x00-\x08\x0b\x0c\x0e-\x1f]`）。原先的 `test_no_source_file_in_the_change_set_contains_control_characters` 因上界重绑只覆盖到 `1ef23247…`，P6 新增文件不再被它保护；本检查把保护**重新建立**在 P6 的活动范围上，不得省略；
   * 四个历史常量 AST 与 Frozen Base 相同、HG-1 diff 文件集合与行数上限、HG-1 之外的 CLOSED 测试零 diff。
8. 这是 **S1 的第一个提交**（独立 commit，commit message 标注 `HG-1`），随 C-level Review 一并审查。**本设计轮次不执行 HG-1：`Tests Modified = NO`。**

> 注意：本设计提交（docs-only）在其自身 HEAD 上**会**使 scope_gate 的两个历史范围测试失败（三份新 docs 不在 P5-C2 allow-list 内），
> reconciliation 的两个范围测试则在 Frozen Base 上就已经是红的。这是本设计无法避免的、已知的后果；在 HG-1 落地之前，这些测试在 P6 分支上预期失败，
> 不属于回归。

---

## 6. 运行时架构（冻结）

### 6.1 纵向链路

```text
dirty media root
    │  discover_media()                                   [fc2_organizer.discovery，CLOSED]
    ▼
DiscoveredMediaItem × N
    │  BatchOrchestrator(engine=AmaneAggregationEngine, image_client, library_root, …).preview(items)
    ▼                                                    [fc2_organizer.orchestration，CLOSED；注入 engine]
P4 识别 + Phase A 冲突  →  Phase 3 BatchScheduler（M 个并发 worker，M = OrchestrationConfig.metadata.max_in_flight_items）
    │  每个 worker：await AmaneAggregationEngine.aggregate("FC2-<digits>")          [fc2_amane_batch，新增]
    ▼
AmaneHostClient（httpx，显式 base URL / 显式凭据，无 cookie / 无 env / 无重定向）
    │  POST /api/tasks   {"type":"scrape","number":N,"content_type":"fc2","use_cache":[]}
    │  GET  /api/tasks/{id}  （有界轮询）
    │  GET  /api/metadata/{metadata_id}
    │  POST /api/tasks/batch {"action":"cancel","task_ids":[id]}   （仅取消路径，精确到该 id）
    ▼
Amane 宿主  →  P5 ffcc.fc2-metadata  →  Core MultiSourceEngine（多来源聚合）  →  P5 MediaMetadata 映射  →  Amane Metadata 持久化
    │
    ▼
host 结果 → 结构化映射（第 11、12 节）
    ▼
合法 Core AggregationResult（SUCCESS，唯一 SourceResult：ffcc.fc2-metadata）或 FAILED（结构化 SourceStatus / SourceErrorKind）
    ▼
P4 继续（CLOSED）：planning → publication → 图片（HttpxImageClient）→ NFO → 产物清单 → 执行前预检 → BatchPreview
    ▼
fc2_amane_batch：AmaneBatchPreview（语义结果）+ AmaneBatchSummary（确定性汇总）+ AmaneHostAuditSnapshot（运维审计，与语义分离）
```

**不进入宿主的东西**：本地源文件路径、本地文件字节、oshash、`media_id`、`library_id`——提交体**只有**第 8.1 节的四个键，且 `number`
是规范 FC2 号。

### 6.2 为什么必须这样连接

* P5-C1 的 plugin 是 `FilmSourcePlugin` / `FilmSourceProvider`，职责止于 `SearchQuery → canonical FC2 → Core aggregate → MediaMetadata`；
  它**没有**批量编排、图片、NFO、整理、文件系统执行、durable resume。不得为 Phase 6 给它增加 Amane 不存在的 batch capability。
* P5 release Core wheel 只含 `fc2_metadata_core`，不含 `fc2_organizer`；不得把 `fc2_organizer` 塞进已 CLOSED 的 Core wheel 或 plugin zip。
* P4-C8 已拥有 `BatchScheduler`、有界并发、取消语义、planning、图片、NFO、materialization、preflight、`BatchPreview`、汇总。
  **禁止写第二套 scheduler**；正确方式是注入一个 Amane-backed `AggregationEngine`。

### 6.3 冻结的模块地图（`src/fc2_amane_batch/`）

| 模块 | 职责 | 公共 / 私有 |
|---|---|---|
| `__init__.py` | 精确的 `__all__`（第 20.1 节）；不 eager import 重模块以外的任何东西 | 公共 |
| `errors.py` | 错误层次（第 20.2 节） | 公共 |
| `credential.py` | `AmaneHostCredential`（redact、不可序列化） | 公共 |
| `config.py` | `AmaneHostConfig`、常量、URL / 数值校验 | 公共 |
| `audit.py` | `HostFailureKind` / `CancelOutcome` / `SubmissionState` / `CleanupTrigger` / `AggregateTerminal` / `TimestampRelation` / `HostAttemptRecord`（含组合校验 `__post_init__`）/ `AmaneHostAuditSnapshot` / 内部 `_AuditLedger` | 公共 + 私有 |
| `_wire.py` | 宿主响应的**有界**严格解析：迭代式 JSON 结构预扫描（第 8.4 节）+ `HostTask` / `HostBatchCancelResult` / `HostMetadata` / `HostWorkerState` | 私有 |
| `host_client.py` | `AmaneHostClient`：5 个操作（第 7.2 节），传输安全，响应上限 | 公共（便于测试），仅 engine / facade 使用 |
| `_lifecycle.py` | 提交 / 观察 / deadline / 精确取消 / 清理预算（第 9、10 节） | 私有 |
| `_mapping.py` | host 结果 → `NormalizedMetadata` / `AggregationResult`；失败映射表（第 11、12 节） | 私有 |
| `engine.py` | `AmaneAggregationEngine`（唯一的 `async def aggregate`） | 公共 |
| `models.py` | `AmaneBatchRound` / `AmaneBatchPreview` / `AmaneBatchSummary` | 公共 |
| `facade.py` | `AmaneBatchIntegration`：preflight / preview / preview_root / retry_failed / audit / aclose | 公共 |

模块数量与职责是冻结的；Developer 可以在不改变上述公共接口与不变量的前提下增加私有 helper 文件，但**不得**增加新的公共符号，
也不得把职责移到 `fc2_organizer` / `fc2_metadata_core` 一侧。

### 6.4 允许 / 禁止的 import（AST 守卫，第 23 节 E6-03）

```text
允许：标准库（asyncio / dataclasses / datetime（仅用于第 11.3.4 节 `timestamp_relation` 的 ISO-8601 解析与比较）/ enum / ipaddress / json / math / time / types / urllib.parse / http.cookiejar / re / collections / typing）
      httpx（0.27.x，Core 已有依赖）
      fc2_metadata_core 的公共子包：aggregation / models / normalize / batch / sources.base（require_canonical_number）/ errors
      fc2_organizer 的公共子包：discovery / orchestration / images（仅类型：ImageAcquisitionPolicy）/ planning（仅 OutputPolicy）
禁止：amane / amane.* / fc2_amane_adapter / requests / aiohttp / urllib.request / socket / ssl（直接） / subprocess / sqlite3 / pickle / marshal / shelve /
      logging（本包零日志）/ os（环境、文件）/ pathlib（文件 API）/ shutil / tempfile / fc2_organizer.execution / .materialization / .nfo / .publication /
      任何 fc2_* 包的私有（下划线）模块
```

> 实现提示：`secrets` 不需要；`http.cookiejar` 仅用于构造“拒绝一切 cookie”的 jar；`ssl` 由 httpx 内部使用，本包不直接 import。
> 本包既不读取环境变量，也不读取任何文件：凭据与 base URL 只来自显式参数。

---

## 7. Amane Host 公共边界核查（设计期实证）

### 7.1 核查方法与坐标

设计期对 `https://github.com/sqzw-x/amane.git` 做 bare clone，并直接读取两个 release 的**源码树**（`git archive v0.15.0` / `git archive v0.18.0`），
而不是依赖他人的转述。以下事实都来自这两棵树；每一条在第 7.3 节标注了文件。

```text
git rev-parse v0.15.0           = 3292c957a092f85ddde1ba7462ffe9813827f4f1   (tag object)
git rev-parse v0.15.0^{commit}  = 45dff2159369883e028a296d775a4598836c1ddd
git rev-parse v0.18.0           = 7d2190704fa1e3c0f7f86889111d12b9fa6701c8   (tag object)
git rev-parse v0.18.0^{commit}  = 0a8a731d7746bde5e8828d1eb74c7bd9752b42e4
```

实现期必须在 S1 开始时重做一次同样的核查并把结果写进 HANDOFF（U6-6 的基线），P6 的 client 不做任何版本分支。

### 7.2 最小 endpoint 子集（表 H1，冻结；这是 P6 唯一允许的宿主表面）

所有路径都在 `/api` 前缀之下（`routes/__init__.py: API_PREFIX = "/api"`）。

| 操作 | 方法与路径 | 请求体（精确键集） | 成功响应 | 用途 |
|---|---|---|---|---|
| `submit` | `POST /api/tasks` | `{"type":"scrape","number":"FC2-<digits>","content_type":"fc2","use_cache":[]}` | **精确 `202`**，`TaskResponse` | 每个 aggregate 恰好一次，**永不重试** |
| `observe` | `GET /api/tasks/{task_id}` | — | `200`，`TaskResponse` | 有界轮询精确 id |
| `cancel` | `POST /api/tasks/batch` | `{"action":"cancel","task_ids":[<该 id>]}`（**不含** `status` / `type`） | `200`，`{affected,skipped,missing,submitted,task_ids}` | 仅在放弃 / 取消 / 超时时，精确到自己的任务 |
| `metadata` | `GET /api/metadata/{metadata_id}` | — | `200`，`MetadataDetailResponse`（只使用 `.metadata`） | 读取 DONE 任务产生的 Metadata |
| `probe` | `GET /api/tasks/worker` | — | `200`，`{"paused": bool}` | 仅门面 preflight（第 9.5 节），每次 preview 一次 |

**明确禁止的宿主表面**（静态守卫 + mutation 覆盖，M6-08 / M6-09）：

```text
POST /api/tasks 的其它 type（organize / trash / refresh / cleanup / upscale / r18_import / actor_scrape / rescrape）
POST /api/tasks 带 media_id / library_id / path / oshash 等任何本地标识
POST /api/tasks/batch 的 action = delete / retry；或带 status / type 过滤（会取消“别人的”任务）
GET /api/tasks（列表）、/api/tasks/{id}/children|report|record、/api/tasks/schema
/api/ws（WebSocket）、/api/config*（含 cookie / token）、/api/plugins*、/api/files*、/api/resources*、/api/media*、/api/libraries*
POST /api/metadata/batch/*、PUT / PATCH / DELETE 任何 metadata
```

### 7.3 逐项核查结果（表 H2）

| 事实 | v0.15.0（`45dff21…`） | v0.18.0（`0a8a731…`） | 结论 |
|---|---|---|---|
| 提交任务 | `src/amane/api/routes/tasks.py`：`@router.post("", status_code=202)` → `TaskResponse` | 同文件；除 `/batch` 处理函数的取消回调参数（`worker=` → `cancel_task=`）外逐字节相同 | 相同 |
| `TaskSubmission` 判别联合含 `ScrapeSubmission`（`type:"scrape"`，`number` / `media_id` / `content_type` / `use_cache`） | `api/models/tasks.py` | `api/models/tasks.py` **逐字节相同** | 相同 |
| `ScrapeRequest` 校验：`number` 与 `media_id` 至少一个；`number` 去空白；`content_type` 缺省则按番号推断 | 同上 | 同上 | 相同 |
| `use_cache: set[CacheKind]`，缺省 `{metadata, trans}`；`[]` = 全部强制刷新 | `handlers/models.py: CacheKind` | 同 | 相同 |
| 读取任务 | `GET /{task_id}` → `TaskResponse`（404 若不存在） | 相同 | 相同 |
| `TaskResponse` 字段 | `id,type,status,title,payload,result,error,log_file,retries,priority,root_task_id,child_*,created_at,started_at,finished_at`；**无 progress 字段** | `api/models/tasks.py` 相同 | 相同；见第 17 节 |
| `TaskStatus` | `db/models.py`：`QUEUED / RUNNING / DONE / FAILED`（**没有 CANCELLED**） | 相同 | 相同；取消的终态是 `FAILED`（第 10 节） |
| 精确 id 取消 | `POST /tasks/batch` → `support/task_batch.py: execute_task_batch(task_ids=…)`：QUEUED → `repo.fail_queued_tasks(task_ids)`；RUNNING → `worker.cancel_task(id)`，失败则 `repo.fail_task(id, "Cancelled by user")` | 同入口；RUNNING → `runtime.cancel_task`，回退用 `repo.fail_running_task`（**不覆盖已终态**） | **DIFF-P6-01**（第 7.4 节） |
| `task_ids` 与 `status/type` 互斥 | `TaskBatchRequest._exclusive_scope` | 相同 | 相同 |
| 响应 `TaskBatchResponse{affected,skipped,missing,submitted,task_ids}` | 是 | 是 | 相同 |
| 认证 | `api/middleware.py: TokenAuthMiddleware`：`Authorization: Bearer <token>` 或同值 HttpOnly cookie `amane_token`；`runtime.api_token is None` = 关闭；`/api/health` 豁免；失败 `401` | **逐字节相同** | 相同 |
| 认证成功后服务器 `Set-Cookie: amane_token` | 是 | 是 | client 必须**丢弃**（第 8.3 节） |
| SCRAPE 结果 | `handlers/scrape.py: ScrapeResult{metadata_id:int, field_sources:dict[str,str], failed_sites:list[str]}` | `handlers/models.py` 相同 | 相同 |
| `field_sources` 的值 = route 中的站点 id（插件即 `ffcc.fc2-metadata`），键 = `MetadataField` 值（`title` / `poster_urls` …） | `aggregate/engine.py`、`enums.py: MetadataField` | 相同 | 相同；任务结果侧的归属证据（第 11.3 节）。**它只描述 SCRAPE 当时想写入什么，不描述最终持久化的记录**（见下面两行） |
| 持久化 Metadata 的锁定 / 来源保留 | `db/repos/metadata.py: upsert_metadata`（AUTO 写入）直接写入，无字段锁；`field_sources` 随记录持久化；手工 `PATCH`（`update_metadata`）**不修改** `field_sources` | `_locked_fields_of()` / `_filter_locked()`：AUTO 写入**跳过**锁定列，并让 `field_sources` **保留锁定字段的既有来源**；手工 `PATCH` 把写入的列加入 `locked_fields`，同样**不改** `field_sources`；用户解锁后锁不再保护 | **DIFF-P6-03 的扩展**：任务的 `ScrapeResult.field_sources` 不等于最终展示列的来源，**持久化 `field_sources` 也不是展示列实际内容的证明**（手工写入后仍显示旧来源）。因此 P6 不以任何 `field_sources` / 锁 / 时间戳作内容归属证据，改用 `raw`（第 11.3 节） |
| `raw`（插件的原始记录） | `aggregate/engine.py`：`raw = {source_key: MediaMetadata.model_dump()}`；`handlers/scrape.py` 与展示列同一次 `upsert_metadata(raw=…)`；`use_cache=[]` 时每个来源重新抓取；翻译 / FacetRule / 物化不改写 `raw`；公开 `PATCH` 不能写 `raw`（`ignore_fields`） | 相同（`MediaMetadata` 同形；`SearchQuery` 内部字段变化不影响 `raw`） | 相同；`GET /api/metadata/{id}` 返回 `MetadataResponse.raw`。**这是 P6 的内容来源**（第 11.3.2 节） |
| `MetadataField`（`field_sources` 的键空间） | `enums.py`：`title, plot, actors, directors, tags, series, release, runtime, publisher, studio, poster_urls, thumb_urls, trailer_urls, extrafanart, score` | 相同 | 相同；仅用于理解宿主，**P6 不以它作证据**。`source_urls` / `external_ids` 在 P6 中恒为空（第 11.4 节） |
| 默认 worker 并发 | `config/manager.py: WorkerConfig.concurrency = Field(default=10, ge=1, le=64)`；`app/bootstrap.py` 把 `hot.worker.concurrency` 传给 `Worker`。（`scheduler/worker.py` 的构造函数默认值 `3` 只是类默认，**不是**宿主实际配置） | 相同（`WorkerConfig.concurrency` 缺省 10） | 相同；**Amane 缺省并发是 10，不是 3**（第 14 节、L6-07） |
| 任务认领与取消登记 | `Worker._run_loop`：`claim_next_task()`（DB 状态已是 RUNNING）→ `asyncio.create_task(self._execute(task))`；`_running_tasks[task_id]` 仅在 `_execute` 内部、**获得信号量并通过 handler 查找之后**才登记（`worker.py` 约 159–162 行） | `_run_loop` 在 claim 之后同步地 `create_task` 并登记 `_active_tasks`；`_execute` 另有取消落点的条件补写（`fail_running_task`） | **DIFF-P6-01 / DIFF-P6-05**：v0.15.0 存在“DB 已 RUNNING、协程尚未登记”的窗口（含信号量等待），此窗口内取消 API 的回退会把任务记为 FAILED，而执行协程仍会继续；v0.18.0 窗口缩小为 claim 提交返回到登记之间的最小窗口，**设计期无法证明其不存在**。第 10.3 节据此撤销“FAILED ⇒ 已停止” |
| SCRAPE 空结果 | `if not result.field_sources:` → 任务 FAILED（"No metadata found"） | `if not result.raw:` → 标量可全空仍 DONE | **DIFF-P6-02**：v0.18.0 可能 DONE 但没有 title（第 11.2 节会 fail closed） |
| Metadata 详情 | `GET /api/metadata/{metadata_id}` → `MetadataDetailResponse{metadata: MetadataResponse,…}`；404 若不存在 | 相同路由与外层模型 | 相同 |
| `MetadataResponse` | 含 `number,title,actors,studio,publisher,release,runtime,tags,plot,poster_urls,thumb_urls,extrafanart,extrafanart_urls,source_urls,external_ids,field_sources,raw,…` | 相同，**多** `locked_fields` | **DIFF-P6-03**：client 为容忍额外键的 reader |
| Worker 暂停状态 | `GET /tasks/worker` → `{paused}`；`POST /tasks/worker/pause|resume` | 相同 | 相同；P6 只读 |
| SCRAPE 可能自行物化 Resource | `handlers/scrape.py` → `media.materialize_images`，受 `scraping.download_resources`（缺省含 poster / thumb / extrafanart…）控制；`crop_poster` 缺省 True 时 poster 可能被替换为宿主内部 URL（`/api/resources/<hash>`） | 相同 | **DIFF-P6-04** 之外的共同事实；第 18 节 |
| SCRAPE 可能扇出 `ACTOR_SCRAPE` 后继任务 | `actor_scraping.auto_scrape` 缺省 `True` | 相同 | 宿主拥有；第 27 节 L6-08 |
| `ContentType.FC2 = "fc2"` | `parsing/file_info.py` | 相同 | 相同 |

### 7.4 版本差异白名单（只允许这五项；出现其它差异 = U6-6）

| ID | 差异 | P6 处理 |
|---|---|---|
| DIFF-P6-01 | 取消 RUNNING 任务的回退：v0.15.0 用无条件的 `repo.fail_task`（可能把“刚好完成的任务”改写成 FAILED / “Cancelled by user”）；v0.18.0 用 `fail_running_task`（不覆盖终态） | P6 不依赖任何一种：取消路径只使用“取消请求之后观察到的结构化数据库终态”（第 10.3 节），**该终态只证明任务记录的状态，不证明执行协程已停止**；不读 `error` 文本；v0.15.0 的改写窗口记入 L6-04 |
| DIFF-P6-02 | v0.18.0 的 SCRAPE 在标量全空时仍可 DONE | 第 11.2 节最低成功门 fail closed（`HOST_METADATA_BELOW_MINIMUM`） |
| DIFF-P6-03 | v0.18.0 的 `MetadataResponse` 多 `locked_fields`，且 AUTO 写入保留锁定字段的既有 `field_sources`（见 7.3 表） | P6 的 reader **不读取** `locked_fields` / `field_sources`（它们不是内容证据，第 11.3 节），多余键被忽略；因此两个版本走**同一条代码路径**，无版本分支 |
| DIFF-P6-04 | 内部实现：v0.15.0 `worker.cancel_task`（只看 `_running_tasks`）；v0.18.0 `runtime.cancel_task`（`app/runtime.py`：先问当前 worker，再问被退役的旧 worker `_retiring`，覆盖宿主重建 worker 期间仍在运行的任务） | 对 public 表面不可见；P6 只依赖取消后观察到的结构化数据库终态（且不据此推断协程已停止）；仅记录 |
| DIFF-P6-05 | “DB 已 RUNNING、执行协程尚未登记”的窗口：v0.15.0 的 `_running_tasks` 在 `_execute` 内信号量与 handler 查找**之后**才登记（窗口含信号量等待）；v0.18.0 在 claim 后同步登记，窗口缩小为 claim 提交返回到登记之间 | 取消 API 在该窗口内只能经回退把记录改为 FAILED，**协程仍可能继续运行并写 Metadata**。P6 不读 worker 私有运行表，因此无法区分；第 10.3 节把“数据库终态已观察到”与“执行已停止”解耦，`execution stop` 永远是 UNVERIFIED，记入 L6-04 |

### 7.5 P6 不使用的宿主能力（理由）

* **WebSocket 进度**：`/api/ws` 的认证走 cookie / 握手，且 P4-C8 §11.4 没有进度契约；不引入（第 17 节）。
* **Task 列表过滤**：无按 number 过滤；用来“找回丢失提交的任务”会命中用户自己的同号任务，违反“只操作自己的任务”。放弃找回，改为显式的 `submission_ambiguous`（第 10.4 节）。
* **`/api/config`**：返回 site cookie / token；生产代码零读取（U6-5）。验收宿主的配置回读只发生在测试工具里（第 22 节）。
* **`/api/tasks/batch` retry**：会创建新任务并与 P4 重试相乘；禁止。

### 7.6 宿主前置条件（P6 的正确性假设；违反时 fail closed，不静默降级）

```text
H6-1  宿主的 FC2 内容 route 恰好是 [ffcc.fc2-metadata]（独占 route）。
      P6 不读取、不修改宿主配置；独占 route **只是前提，不是证明**。每个条目的证明链（第 11.3 节）：任务侧 field_sources 只含插件且含 title（必要条件）；
      字段内容**只**来自 Metadata 的 raw["ffcc.fc2-metadata"]（插件的原始记录，公开 PATCH 不能改写）。任务侧出现非插件来源，或 raw 的键集合不是恰好 {ffcc.fc2-metadata}（缺失 / 只有外来 / 插件与外来并存 / 带语言后缀或未知来源键）
      → 该条目 fail closed（HOST_ATTRIBUTION_FOREIGN）。P5 INSTALL 把插件放在 route 最前并保留原站点——P6 需要把其它站点移出该 route（见 L6-01）。
H6-2  宿主任务 worker 未暂停（preflight 检查；暂停时 SCRAPE 永远 QUEUED）。
H6-3  宿主 token 与 P6 凭据一致（401/403 → 结构化 BLOCKED 失败；preflight 提前拒绝）。
H6-4  用户同意“SCRAPE 会把结果写入 Amane 的 Metadata 库”（AmaneHostConfig.acknowledge_host_metadata_writes=True，第 8.2 节）。
H6-5  宿主 base URL 是 origin（scheme://host[:port]），无路径前缀（反向代理路径前缀不在 P6-C1 范围）。
H6-6  宿主 Metadata 是**按番号唯一、跨任务共享**的记录：用户手工编辑、其它任务（含遗留孤儿任务）、字段锁都可能在 SCRAPE 完成与 P6 读取之间改变它。
      P6 只能保证“读取那一刻 raw 中的插件记录被确定性映射为输出”，**不能**证明该记录是本任务的独占产物或不可变快照（第 11.3.4 节、L6-18）。
```

---

## 8. Host Client（`AmaneHostClient`；冻结）

### 8.1 提交体（精确键集，静态 + 运行时双重校验）

```json
{"type": "scrape", "number": "FC2-1234567", "content_type": "fc2", "use_cache": []}
```

* 键集**恰好**这四个；任何其它键（尤其 `media_id`、路径、hash）= 实现缺陷（测试用请求账本逐键断言）。
* `number` 必须先通过 `require_canonical_number`（Core）；非规范号 → `InvalidCanonicalNumberInputError`（调用方 bug，零网络）。
* `use_cache: []`（强制刷新）的理由：宿主缺省会复用 DB 中既有的 per-site 快照（可能由**其它**爬虫写入），那样结果就不能归属于
  `ffcc.fc2-metadata`；强制刷新让每个 aggregate 的元数据都来自本次 route 内的站点。

### 8.2 `AmaneHostConfig`（不可变；构造即校验；零 I/O）

| 字段 | 类型 / 范围 | 缺省 | 说明 |
|---|---|---|---|
| `base_url` | `str`；origin only | 必填 | 先过 Core `validate_base_url`（无 userinfo / query / fragment / 控制字符），再要求 path ∈ {"", "/"}；去掉尾部 `/`。`https` 任意主机；`http` **仅**回环（`127.0.0.0/8` / `::1` / `localhost`）。非回环 `http` → `AmaneBatchConfigError`（不提供关闭开关；L6-02） |
| `credential` | `AmaneHostCredential \| None` | 必填（可显式 `None`） | `None` = 宿主关闭了 token 校验（`AMANE_TOKEN=off`） |
| `request_timeout_seconds` | `float`，`0 < x ≤ 120` | `15.0` | 单个 HTTP 请求（连接 + 读取）的墙钟上限 |
| `poll_interval_seconds` | `float`，`0.05 ≤ x ≤ 10` | `0.5` | 观察间隔 |
| `aggregate_deadline_seconds` | `float`，`1 ≤ x ≤ 3600` | `300.0` | 一次 aggregate 从提交开始的总墙钟预算（**含宿主排队时间**） |
| `cancel_budget_seconds` | `float`，`0.5 ≤ x ≤ 60` | `10.0` | 一次取消 / 放弃清理的总预算（第 10 节） |
| `max_consecutive_poll_errors` | `int`，`1..10` | `3` | 连续观察失败的容忍次数（仅对幂等 GET；第 9.3 节） |
| `acknowledge_host_metadata_writes` | `bool`，**必须为 `True`** | `False` | 显式承认“SCRAPE 会向 Amane Metadata 库 upsert 数据”；`False` → `AmaneBatchConfigError` |

没有 `verify_tls` / `proxy` / `follow_redirects` / `retries` / `concurrency` / `cookies` / `headers` 旋钮：它们是冻结语义，不是选项。
并发预算只有一个来源：`OrchestrationConfig.metadata.max_in_flight_items`（第 14 节）。

### 8.3 `AmaneHostCredential` 与传输安全

```text
AmaneHostCredential(token: str)
  token：非空 str，仅可打印 ASCII（0x21..0x7E），无空白，长度 ≤ 512；违反 → AmaneBatchConfigError（异常文本不含 token）
  __repr__ / __str__ / __format__ → "AmaneHostCredential(<redacted>)"
  __reduce__ / __reduce_ex__ / __getstate__ / __copy__ / __deepcopy__ → TypeError（不可序列化、不可复制；永不落盘）
  __eq__ / __hash__ → 对象身份（不比较 token）
  取值只发生在 host_client 内部构造 Authorization 头的那一行
```

| 规则 | 要求 |
|---|---|
| 显式注入 | 凭据只来自参数；包内**零**环境变量读取、零文件读取、零 `.netrc` |
| 不持久化 | 不写盘、不写日志（本包**零 logging**）、不进入 `repr` / 异常文本 / `__cause__` 或 `__context__` 链 / `BatchPreview` / 汇总 / 审计 / 诊断 |
| 不泄漏异常（Design-R1 / R1-03；Design-R2 / R2-02 扩展到整个包） | 见下面第 8.3.1 节。要点：`raise … from None` **不清除** `__context__`，不是安全证明；规则适用于 `src/fc2_amane_batch/**` 的**全部**文件（credential / config / engine / _lifecycle / models / facade / host_client / 任何私有 helper），不只是 `host_client.py` 与 `facade.py` |
| 无环境代理 | `httpx.AsyncClient(trust_env=False)`：忽略 `HTTP_PROXY` / `ALL_PROXY` / `NO_PROXY` / `SSL_CERT_*` / `.netrc` |
| 无 cookie | 宿主在认证成功后会 `Set-Cookie: amane_token`（两个版本）。client 使用“拒绝一切 cookie”的 cookie jar：`client.cookies` 在任何响应之后保持为空；后续请求**不**带 `Cookie` 头 |
| 无重定向 | `follow_redirects=False`；任何 `3xx` → `HOST_HTTP_UNEXPECTED`；因此凭据永不会被带到另一个 origin |
| TLS | `https` 使用 httpx 缺省证书校验；**不存在**关闭校验的参数；证书 / 握手失败 → `HOST_CONNECTION`（结构上无法降级为明文） |
| 明文策略 | 非回环主机必须 `https`（第 8.2 节） |
| 请求头 | 只有 `Authorization`（若有凭据）、`Accept: application/json`、`Content-Type: application/json`（POST）、固定 `User-Agent: fc2-amane-batch/0.1`、`X-FFCC-Attempt: <attempt_id>`（第 14 节 O2：仅含 `[A-Za-z0-9-]`，不含番号 / 路径 / 凭据；宿主忽略，P6 不据此做任何控制；不改变任何请求体键集） |
| 连接池 | 有界（`max_connections ≤ 66`，不随批量大小增长）；一个 `AsyncClient` per `AmaneHostClient`（构造时创建，**不**在 import 时创建；`aclose()` 幂等） |

### 8.3.1 异常与凭据边界（整个包；Design-R2 / R2-02）

**1. 保护面（Protected Surface）——合同承诺的对象，逐项可测：**

* **P1 出口异常**：由 `src/fc2_amane_batch/**` 的任何公共入口（含各类 `__init__`）抛出并到达调用方的每个异常 `E`。
* **P2 可达集合 `G(E)`**：以 `E` 为根，沿 `__cause__`、`__context__`（链深至多 8 级，visited 集合防环）、`args`（元素；`list` / `tuple` / `dict` / `set` 再展开一层）、`__notes__`、`E.__dict__` 的值（一层）、以及 `__traceback__` 链上**属于本包的栈帧**（`f_code.co_filename` 位于 `fc2_amane_batch` 包目录内）的 `f_locals` 值（浅层：值本身，容器再展开一层）。调用方 / 测试自己的栈帧不在保护面内。**适用对象（Design-R3 / R3-03，诚实边界）**：① 本包创建的全部异常（`AmaneBatchError` 家族）；② 本包在 `_call` 边界新建的 `asyncio.CancelledError` 实例（C5c）。③ **致命 `BaseException`**（`KeyboardInterrupt` / `SystemExit` / `GeneratorExit`；同一对象，F3，第 10.5 节）：引用脱离后其 `__cause__` / `__context__` 为 `None`，经 `__traceback__` 与链**不可达任何敏感引用**（断言的是敏感引用不可达，**不是**“traceback 绝对不含任何本包帧”：正常信号落在边界入口检查点时，留下的、局部不含敏感数据的边界帧是允许的，C9），必须通过独立可达性审计（Gate C `reach.py`，含 C 级槽位；**检测任何带 `Authorization` 的 `Request` / `Response.request`，与令牌值无关**，R5-EV-01）；其 `args` / `__dict__` / `__notes__` 由抛出方创建，本包不读取不修改，P2 对它们只断言“本包没有新增”（独立载荷对照按 X-NARROW；抛出方植入当前 P6 凭据的四个用例按 B1 = OUT_OF_THREAT_MODEL，第 10.5 节；L6-21 / L6-25）。
* **P3 输出文本与结构**：`str(E)`、`repr(E)`、`traceback.format_exception(E)` 的全文；`AmaneBatchPreview` / `AmaneBatchSummary` / `AggregationResult` / `AmaneHostAuditSnapshot` / P4-C9 诊断投影的 `repr` 及可序列化结果。

**2. 禁入内容 `F`**：`G(E)` 与 P3 中不得出现：(a) 任何等于或**包含** token canary 的 `str` / `bytes`；(b) 任何 `httpx.Request`、`httpx.Response`、`httpx.Headers`、`httpx.HTTPError` 及其子类实例；(c) 任何 `UnicodeError` 实例及任何持有其 `.object` 的对象；(d) 响应体 `bytes`；(e) 宿主返回的文本、URL、任务 id（异常文本）。

**3. 所有权状态不在承诺内（区分“新引入的泄漏”与“对象本身持有的认证状态”）**：`AmaneHostCredential`（持有 token）、`AmaneHostConfig`、`AmaneHostClient`、`AmaneAggregationEngine`、`AmaneBatchIntegration` 以及它们内部的 `httpx.AsyncClient` / `httpx.Auth` 对象，是**调用方自己创建并持有、本来就含认证状态**的对象。它们可以作为帧局部 `self` 出现在 `G(E)` 中，遍历**不进入**这些对象（视为不透明）。合同**不**承诺“从这些对象出发不可达凭据”——调用方持有 client，就能经其属性到达凭据，这不是异常泄漏。合同承诺的只有：**异常、输出文本与结果对象没有新引入 `F` 中的任何内容**，且凭据对象本身的 `repr` / `str` / `format` 恒为 redacted、不可 pickle / copy（第 8.3 节）。

**4. 构造规则（冻结；AST 守卫扫描 `src/fc2_amane_batch/**/*.py` 的每个文件，含未来新增的私有 helper）：**

| # | 规则 |
|---|---|
| C1 | 任何 `except` 处理体内**不得**出现 `raise <表达式>` 或 `raise … from <任何>`（含 `from None`）。允许的唯一例外是 `except (KeyboardInterrupt, SystemExit, GeneratorExit):` 内的**裸** `raise`（同一个致命异常对象，身份保持；处理体按 C9 的内联形式：先 `try: _fatal_scrub(e)`，失败时内联属性赋值，再 `raise`——对**该对象**的 `__traceback__` / `__cause__` / `__context__` 赋值，第 10.2 节第 6 条与第 10.5 节）。`asyncio.CancelledError` **不再有例外**：它在 `except` 里只置标志，离开 `except` 之后抛出 C5c 的新实例。需要转换时：处理体内只做赋值（分类为枚举 / 布尔局部），**离开处理体之后**再 `raise` 固定异常 |
| C2 | 本包异常的构造实参只允许：闭合枚举成员、固定字符串字面量、整数计数；禁止传入 token、URL、宿主文本、`str(exc)`、`exc.args` 或任何变量字符串（AST 守卫） |
| C3 | 凭据 / 配置校验必须用**不抛异常的纯谓词**（`str.isascii()`、`str.isprintable()`、`len`、字符区间判断等）；**禁止**对 token 调用 `.encode()` / `.decode()` / `int()` 等可能抛 `UnicodeError` / `ValueError` 的转换，也不得用 `try/except` 包裹对 token 的操作（`UnicodeEncodeError.object` 会保留原始 token） |
| C4 | **栈帧局部**：接收原始 token 的本包函数（`AmaneHostCredential.__init__` 及其 helper）在校验失败路径上，必须在 `raise` **之前**把持有 token 的局部名（含形参名）重新绑定为 `None`；因此 `E.__traceback__` 中本包帧的 `f_locals` 不含 token。成功路径只把 token 存入凭据对象的私有属性。`httpx.Auth.auth_flow` 内的 token 局部随函数返回而失效 |
| C5 | **传输两层**：内层 `_transport(...)` 只返回纯数据 `(kind \| None, status \| None, body_bytes \| None)`（`body_bytes` 的处理见 C5b），**永不抛出本包异常**；内层的异常处理是封闭完备的（第 10.2 节第 7 条，R5-12：`httpx.TimeoutException` / `httpx.ConnectError` / 其余任何 `Exception` ⇒ 封闭种类，非 `httpx` 异常 ⇒ `HOST_NETWORK`，只在 `except` 块里记一个枚举值）；外层 `_call(...)` 只持有纯数据，**离开全部 `except` 之后**才 `raise AmaneHostCallError(kind)` |
| C5a | **`_transport` 的局部清理与 Response 关闭**（唯一规范在第 10.2 节第 7 条，此处不再复述机制）：`_transport` 使用显式的“捕获 → 内联有界关闭 → 重绑”结构，**无** `shield`、**无** task；`finally` / 退出路径上把 `request` / `response` / `stream` / `headers` / `body` / `chunk` / `chunks` 等全部白名单局部重绑为 `None`；**致命异常落在 `_transport` 的任何字节码上时，这些局部既不靠 `_transport` 自己的处理体，也不靠任何 `frame.clear()`：边界帧切断异常对 `_transport` 帧的全部引用（`__traceback__` / `__context__` / `__cause__`），该帧随引用计数连同局部一起释放（确定性所有权清理 + 异常引用脱离，第 10.5 节）**；AST 守卫要求这两个函数内出现的**每一个**局部名都在冻结白名单里，把 httpx 对象赋给白名单外的名字、放入 `list` / `dict` / `tuple` / 闭包、或经别名间接持有，一律被拒绝；运行时以栈帧 `f_locals` 扫描作最终证明。**R3 的“`asyncio.shield` 限时 `aclose`”已撤销**（它会留下仍持有 Response 的 task） |
| C5b | **`_call` 的响应体**：`body_bytes`、解码后的字符串 / 对象、`json.JSONDecodeError`（其 `.doc` 持有完整响应体）只能出现在**纯函数** `_decode(body) -> (kind \| None, obj \| None)` 内部：函数内 `except json.JSONDecodeError` 只给 `kind` 赋值，异常名随处理体结束被清除，返回值不含原始文本。`_call` 在抛出**任何**本包异常之前，必须把 `body_bytes`、`obj` 及全部中间值重新绑定为 `None`（AST 守卫：抛出点之前必有对白名单局部名的重绑）。5xx、JSON 违规、schema 违规、`HOST_RESPONSE_TOO_COMPLEX` 全部适用；成功路径返回的是已通过严格 reader 的纯数据，不含原始字节。F(d) **不放宽** |
| C5c | **取消的出口（冻结）**：`asyncio.CancelledError` 在 `_transport` / `_call` / engine 内都只被分类为标志（`cancelled = True`）；**离开 `except` 块并完成第 10.2 节的内联处理之后**，抛出一个**新的** `asyncio.CancelledError()` 实例（无参数；`__cause__` 为 `None`；`__traceback__` 从本包帧起算，不含 httpx / httpcore / asyncio 第三方帧；`__context__` 的边界见第 10.2 节第 9 条）。P4 只按**类型**判定取消，`TaskGroup` / `Task.cancel()` 语义不依赖异常对象的同一性；除第 10.2 节第 7 条的“撤销本包自己的 deadline 取消请求”外不调用 `Task.uncancel()`。**致命 `BaseException` 不适用“新实例”规则**：它们保持**同一个异常对象**（不替换、不包装、不吞），本包按 F3 只切断其暴露面（第 10.5 节）：各层拥有者重绑自己的敏感局部，`__traceback__` / `__cause__` / `__context__` 引用脱离（不访问、不清理任何帧；异常链整条切断，不再有允许名单）。F3 若被独立复核否决，则为 `BLOCKED — SECURITY AUTHORITY`，不得退回 F1 / F2 |
| C6 | engine / `_lifecycle` / facade / models：捕获 `AmaneHostCallError` 只读取 `.kind` 赋给局部；`AmaneHostPreflightError`、`AmaneBatchRetryError`、`AmaneBatchContractError`、`AmaneBatchInputError` 一律在 `except` 之外构造；`aggregate` 的 `except Exception` 兜底只做分类（记录类名常量）并在块外决定返回 FAILED 或抛 `AmaneBatchContractError`（固定文本） |
| C7 | 本包永不调用 `add_note()`（`__notes__` 恒不存在） |
| C8 | **asyncio / 帧接口白名单（R5 附加）**：包内只允许 `asyncio.get_running_loop()`、`asyncio.current_task()`、`loop.time()`、`loop.call_at()`（仅 `_transport`，武装在 `finally` 保护的 `try` 内，回调受 `active` 标志约束；`active` 由 `_call` 创建并在其 `finally` 里清除，`_transport` 的 `finally` 里 `active[0] = False` 先于 `timer.cancel()`）、`Task.cancel()`（仅 `_transport` 的 `_expire`，且只作用于当前 task）、`Task.cancelling()` / `Task.uncancel()`（仅 `_transport` 的唯一分类点）、`asyncio.sleep`（观察间隔）、`asyncio.CancelledError`；**生产路径一律禁止**：`import gc` / `import inspect`；`gc.get_referrers` / `gc.get_referents` / `gc.get_objects` / `gc.collect` / `gc.freeze` / `gc.unfreeze`；`sys._getframe` / `sys._current_frames` / `inspect.currentframe`；`frame.clear()`；对 `tb_frame` / `f_back` / `f_locals` / `f_globals` / `cr_frame` / `gi_frame` / `ag_frame` 的任何访问；`except RuntimeError` 与裸 `except:`；也不得以其它手段（字符串形式的 `getattr`、别名、全堆扫描）实现同样的机制（AST 守卫 `fatal_path_guard.py`，E6-03；M6-56 / M6-58；R5-CL-01 / R5-GOV-01 / R5-NEW-01）。独立证据 / 审计脚本可以使用 `gc.get_referents()` 等调试手段，但生产实现不得依赖它们；`asyncio.timeout` / `timeout_at` / `wait_for` / `shield` / `create_task` / `ensure_future` / `gather` / `TaskGroup` / `run_in_executor` / `to_thread` / `threading` 一律禁止（AST 守卫，E6-03，M6-30）。公共构造面不得出现传输 / HTTP 客户端 / mounts / event hooks / sleep / clock 参数（AST + 签名守卫，E6-03，M6-42）；`AmaneHostClient` 的公共名只有 `aclose` 与各公共方法，**不暴露其内部 httpx 客户端**（属性 `_http` 私有；X-NARROW 的受支持边界依赖这一点） |
| C9 | **致命异常的边界所有权（R5-C-01）**：每个边界帧（公共 client 方法、`_call`、`aggregate`、门面公共方法）的致命处理体**内联**写成第 10.5 节的形式——先用纯 `STORE_FAST` 把本帧持有的响应数据局部（`_call` 的 `body` / `obj`）重绑为 `None`（确定性所有权清理：没有调用，因而没有检查点），然后第一条带调用的语句是 `try: _fatal_scrub(e)`，`except BaseException` 里只有内联的纯属性赋值与 `isinstance` 判定，之后裸 `raise`；不得在 `try` 之前调用任何函数；`_transport` 不得有致命处理体；边界帧的局部变量不得持有凭据 / `Request` / `Response` / 响应体（也不得持有 `Response` 的派生对象）；`aggregate` 的致命记账幂等且失败不遮盖；`_fatal_scrub` 只是三条属性赋值（`__traceback__` / `__cause__` / `__context__` = `None`），**不访问任何帧**；边界帧**可以**出现在到达调用方的 traceback 中（例如正常信号落在边界入口的检查点、处理体尚未建立），只要其局部不含敏感数据——安全断言是敏感引用不可达，不是 traceback 不含任何本包帧（AST 守卫 + 穷举探针 + 逐层所有权证明，E6-03 / E6-09 / E6-17，M6-51 / M6-56 / M6-59） |


**5. 强制失败矩阵（E6-17；每一条适用路径逐项检查 `__cause__` / `__context__` / `args` / `__notes__` / 本包帧 `f_locals` / `str` / `repr` / traceback 文本 / 审计·汇总·preview，并断言 `F` 不出现）：**

| 对象 | 必须覆盖的失败 |
|---|---|
| `AmaneHostCredential` / `AmaneHostConfig` | 非法 ASCII（控制字符）、非 ASCII、含空白、空串、超长（> 512）token；非法 base_url（userinfo / 非回环 http / 带路径）；数值越界；`acknowledge_host_metadata_writes=False` |
| `AmaneHostClient` 全部 5 个公共方法 | `401` / `403`、`5xx`（**带响应体**）、超时、连接失败（含 TLS 证书失败）、响应体过大、非 JSON（**畸形 JSON 带响应体**）、严格 reader 违规（schema-invalid 带响应体）、结构超限（`HOST_RESPONSE_TOO_COMPLEX`）、流中途断开；**取消 / 致命矩阵（Design-R3 / R3-03）**：连接建立期间取消、等待响应头期间取消、响应流中途取消、请求进行中注入致命 `BaseException`（`KeyboardInterrupt` / `SystemExit`） |
| `AmaneHostPreflightError` | 4 个 reason 全部 |
| `AmaneAggregationEngine` | 内部契约错误（`AmaneBatchContractError`）、非规范号、未预期 `Exception`、`CancelledError`（含清理期间）、**批量被取消时 HTTP 请求正在进行（batch cancelled while HTTP in flight）**（出口为 C5c 的新实例，且本包帧干净） |
| `AmaneBatchIntegration` | 非法输入、retry 拒绝（3 个 reason）、`aclose` 之后调用、门面把 `AmaneHostCallError` 转换为 `AmaneHostPreflightError` 的路径 |

**红绿孪生**：① 凭据路径——`try: token.encode("ascii") except UnicodeEncodeError: raise AmaneBatchConfigError(…) from None` 的变体必须被判红（`__context__` 持有带 `.object=token` 的 `UnicodeEncodeError`）；纯谓词 + 块外抛出的实现为绿；② 校验失败时 `token` 形参仍留在本包帧局部的变体为红，已重新绑定为 `None` 的为绿；③ `_transport` 在 `except` 内 `raise AmaneHostCallError(...) from None` 的变体为红；④ 外层 `_call` 帧局部仍持有 `Response` / `Request` 的变体为红；⑨ **（R4-02）** 用 `asyncio.shield` / `create_task` / `ensure_future` 起清理 task，或让清理在取消返回之后继续运行的实现为红（M6-30）；⑤ **（R3-03）** `_transport` 的 `finally` 未重绑 `request` / `response` / `stream` / `chunk`（取消发生在 connect / 等待响应头 / 流中途时本包帧 `f_locals` 仍含 httpx 对象）为红，已全部重绑为绿；⑥ `_call` 在 5xx / 畸形 JSON / schema 违规 / 结构超限路径上抛出时仍持有 `body_bytes`（或经 `JSONDecodeError.doc` 保留响应体）为红，已清理为绿；⑦ `CancelledError` 原样穿过 httpx 栈帧（traceback 含第三方帧且其 `f_locals` 含 `Request`）为红，方案 A 的新实例为绿；⑧ 致命异常路径（F3）：断言**原异常对象的身份保持**（`is` 同一对象）、类型 / `args` / `__dict__` / `__notes__` 与抛出时逐项相等、`_transport` 期间**零额外 I/O**、无新增 P6 task，并由独立审计器（含 C 级槽位）断言第三方帧与整条异常链**不可达**；红孪生（F1：保留原始 traceback）必须可达 ≥ 2 条路径；⑩ **（Design-R5）** `_transport` 缺少 `finally: timer.cancel()`、未做总 deadline、或在调用方取消时撤销了调用方的取消计数为红（M6-43 / M6-44）。

### 8.4 响应处理

* 响应体**流式读取**并设上限 `MAX_RESPONSE_BYTES = 8 * 1024 * 1024`；超限 → `HOST_RESPONSE_TOO_LARGE`（不读完）。
* 只接受 `application/json` 内容（或无 `content-type` 但可被严格 JSON 解析）；JSON 解析使用拒绝 `NaN` / `Infinity` 的严格模式。
* **有界 JSON 结构（Design-R1 / R1-07；Design-R2 / R2-03 修正成本模型）**：字节数上限不等于结构上限（`[[[[…` 几 MB 就可使递归解析器耗尽栈，数百万个 `[]` 可耗尽内存）。字节检查通过后、`json.loads` **之前**，必须对原始字节做一次**迭代式（非递归）预扫描**，并强制下列确定常量（均进入 `__all__`，测试逐值断言）：

  | 常量 | 值 | 度量（冻结定义） |
  |---|---|---|
  | `MAX_JSON_DEPTH` | `32` | 当前打开的数组 / 对象的嵌套层数；顶层容器深度为 1；第 33 层即超限 |
  | `MAX_JSON_NODES` | `200_000` | 累计 token 数：每个容器（含空对象 / 空数组）、每个字符串（含对象键）、每个数字 / `true` / `false` / `null` 字面量各计 1 |
  | `MAX_JSON_COLLECTION_ITEMS` | `20_000` | 单个数组的元素数、单个对象的成员数（空容器为 0）各自的上限 |

  各自“= 上限”通过、“= 上限 + 1”拒绝。数值选择依据不变：两个版本的合法响应——`TaskResponse`（含 `payload` / `result`）与 `MetadataDetailResponse`（含 `raw`，其中是插件原始记录与可能存在的其它来源记录）——在真实宿主上的实测最大值须低于上限的 **1/4**（S1 第 0 步实测并写入 HANDOFF；任何一项超过 1/4 → 停止并提交修订，不得悄悄放宽）。

  **成本模型（修正）**：设 `B` = 实际被扫描的输入字节数，`B ≤ MAX_RESPONSE_BYTES`。扫描必须逐字节（或等价地按 token 跳转）经过字符串内部与空白，所以一个超长字符串或长空白即使只有一个结构节点也要付出其长度的代价。因此：**正常通过扫描时 Time = O(B)**；触达任一结构上限时可以**提前拒绝**，但**不声称**成本只取决于 token 数。**辅助空间**：O(`MAX_JSON_DEPTH`)（每层一个元素计数器的栈）+ 固定个数的标量计数器 / 状态位；不递归、不复制响应体、不为每个 token 或字符串物化子串（只保留位置）。
  **扫描语义**：对语法合法的 JSON，三个计数与上面的定义**完全一致**（测试以独立的递归参考计数器在小输入上逐项对账）；对非法 JSON，预扫描只需在 O(B) 内终止且辅助空间不超界（深度下溢取 0、未闭合字符串扫到末尾即停），随后由 `json.loads` 拒绝为 `HOST_SCHEMA_INVALID`。预扫描必须正确处理：字符串内部的 `{ } [ ] , :`、转义引号 `\"`、连续反斜杠 `\\`、`\uXXXX`、对象键、空对象 / 空数组、未知嵌套字段。
  **时序与失败**：超限在 `json.loads` **之前**拒绝 → `HOST_RESPONSE_TOO_COMPLEX`（封闭枚举，映射见第 12.1 节），不保留原始响应；`json.loads` 的 `RecursionError`（纵深防御，理论上不应发生）映射为 `HOST_SCHEMA_INVALID`，**不得**把 Python 默认递归限制当作主要防护；`_wire.py` 之后的遍历只读取已知键，不对任意嵌套结构做递归遍历。
* 状态码：`submit` 必须是 `202`；其它四个操作必须是 `200`。其它 `2xx` → `HOST_HTTP_UNEXPECTED`；`401/403` → `HOST_AUTH_REJECTED`；`429` →
  `HOST_RATE_LIMITED`；`5xx` → `HOST_SERVER_ERROR`；`404` 见各操作；其它 `4xx` / `3xx` / `1xx` → `HOST_HTTP_UNEXPECTED`。
* **宿主返回的任何文本**（`error`、`detail`、响应体、日志）都不进入控制逻辑、不进入异常、不进入结果、不进入审计。解析 `error` 字段只用于类型校验，
  之后立即丢弃。

### 8.5 严格 reader（`_wire.py`）

* `HostTask`：必需 `id`（`int`，非 `bool`，`≥ 1`）、`type`（`str`）、`status`（`"queued"|"running"|"done"|"failed"`）、`payload`（`dict`）、
  `result`（`dict | None`）；`finished_at`（**可选**，`str | None`；仅用于审计 `timestamp_relation`，缺失 / 不可解析不是失败）；`error`（`str | None`，只验类型、不保留）。额外键忽略。
* `HostBatchCancelResult`：必需 `affected` / `skipped` / `missing`（非负 `int`，非 `bool`）。
* `HostMetadata`（Design-R2 / R2-01 缩小为内容证据所需的最小集合）：必需 `id:int`、`number:str`、`raw:dict`（其中只会进一步读取精确键 `ffcc.fc2-metadata`，由第 11.3.3 节 `PluginRaw` reader 解析）；
  **可选** `title:str|None`（仅用于审计 `display_title_diverged`，类型非法 ⇒ `HOST_SCHEMA_INVALID`）、`updated_at:str|None`（仅用于审计 `timestamp_relation`）。
  **所有其它展示列与键（`actors` / `tags` / `*_urls` / `studio` / `field_sources` / `locked_fields` / `source_urls` / `external_ids` / 时间戳 …）一律忽略且不保留**；它们不是内容证据，也不进入输出。
* **`files` 等宿主返回的文件系统路径**（`MetadataDetailResponse` 的 `files` 可能含用户本机路径）：reader 不读取、不存入任何 P6 对象，因此不得出现在输出、异常、日志、审计、诊断中；E6-17 用含 canary 路径的 `files` 响应断言此点。
* 任一必需键缺失 / 类型不符 → `HOST_SCHEMA_INVALID`（不猜测、不修复、不部分接受）。

---

## 9. Host Task 生命周期（冻结）

### 9.1 状态机（每个 aggregate 一个实例）

```text
SUBMITTING ──202 + echo 校验通过──► OBSERVING ──status=done──► FETCHING_METADATA ──映射成功──► SUCCESS
    │                                  │  │                              │
    │ 请求失败 / 非 202 / echo 失败      │  │ status=failed                │ 任何映射 / 取回失败
    ▼                                  │  ▼                              ▼
 FAILED(HostFailureKind)                │ FAILED(HOST_TASK_FAILED)     FAILED(HostFailureKind)
                                       │
                          deadline 到期 / 连续观察失败 / 取消 / 未预期异常
                                       ▼
                                  ABANDONING ──有界清理（第 10 节）──► FAILED(…) 或 重新抛出 CancelledError
```

* 终态只有三种：`SUCCESS`（返回 SUCCESS `AggregationResult`）、`FAILED`（返回 FAILED `AggregationResult`，**不抛**）、取消（有界清理后重新抛 `CancelledError`）。
* `observe` 的终态判定**只**读取结构化 `status`：`done` / `failed`；`queued` / `running` 继续观察。

### 9.2 提交（`submit`）与创建基数（Design-R1 / R1-02）

**撤销旧不变量**：旧稿写“一次 aggregate 尝试 = 恰好一个新创建的 SCRAPE 任务”。这在 401 / 连接失败 / 响应丢失下不成立（请求可能没抵达宿主，也可能已创建而响应丢失）。把“尝试了几次 POST”与“宿主实际创建了几个任务”混为一谈会让任务账本、重试与取消的结论失真。冻结为下列**四个封闭状态**（`SubmissionState`，进入审计，不进入语义输出）：

| `SubmissionState` | 含义 | 任务数 |
|---|---|---|
| `SUBMISSION_NOT_ATTEMPTED` | `POST` 从未发出（非规范号、准入前取消、门面 / admission 在发请求之前终止等） | P6 创建了 **0** 个 |
| `SUBMISSION_ATTEMPTED` | `POST` 已开始发送、结果尚未知；**仅作为 aggregate 进行中的瞬态存在，终态审计记录不得停在此值** | 未定 |
| `CREATION_CONFIRMED` | 响应为精确 `202`，且 `HostTask` 通过严格 reader（得到合法 `id`） | 宿主确认存在 id 为该值的任务（回显不符时仍是此状态，第 3 步） |
| `CREATION_UNKNOWN` | `POST` 已发出，但没有 `202` + 合法 `id`：超时 / 连接中断 / 响应丢失 / 响应过大或过于复杂 / 非 JSON / schema 非法，或宿主给出了非 `202` 状态（含 `401` / `403` / `429` / `4xx` / `5xx`） | **未知**：可能 0 个，也可能 ≥ 1 个 |

冻结规则：

1. **每个进入提交阶段的 aggregate 最多发送一次 `POST /api/tasks`；永不自动重试**（包括传输层：`httpx` 不得配置 `retries`；engine / facade 也不得因为任何失败或不确定状态而再次提交）。重试一次非幂等创建会产生重复任务。
2. 记录 `started = clock()`（单调时钟），分配审计 `seq`，状态置 `SUBMISSION_ATTEMPTED`，发送 `POST /api/tasks`（第 8.1 节）。
3. `202` 且 `HostTask` 通过严格 reader → `CREATION_CONFIRMED`；并做 **echo 校验**：`type == "scrape"`、`payload.number == number`、`payload.content_type == "fc2"`。
   不符 → `HOST_SCHEMA_INVALID`，状态**仍是** `CREATION_CONFIRMED`（任务 id 已知 → 进入 ABANDONING 清理，因为宿主确实对这次 `POST` 创建了任务）。
4. 其它所有结果 → `CREATION_UNKNOWN`。**`CREATION_UNKNOWN` 不得被自动折算为“零个”或“一个”**：
   * `401` / `403`：宿主的认证中间件先于路由执行，期望零个任务，但 P6 **不据此断言**为零（仍记 `CREATION_UNKNOWN`，失败种类 `HOST_AUTH_REJECTED` 单独说明原因）；
   * 超时 / 连接失败 / 响应丢失：宿主可能已创建任务而 P6 不知道 id。P6 **不**尝试找回（第 7.5 节：列表过滤会命中用户自己的同号任务）；
   * 结果为 `FAILED(HOST_TIMEOUT / HOST_CONNECTION / HOST_AUTH_REJECTED / …)`，审计 `submission = CREATION_UNKNOWN`、取消结果 `UNCERTAIN_SUBMISSION_UNRESOLVED`（不是“没有任务”）。
5. **不得以“状态不确定”为由重试**：engine 在 `CREATION_UNKNOWN` 之后不会再提交；`retry_failed` 是调用方显式发起的新操作（第 13.3 节），每个被选入的条目会发起**新的** aggregate 与新的 `POST`，它可能与此前未解析的遗留任务并存。审计快照的 `creation_unknown` 计数用于让调用方知情，P6 不据此自动阻止或自动放行重试。
6. 任务基数不变量（Design-R4 / R4-04 重写；用于 E6-13 / E6-14 的宿主账本对账，**唯一规范在第 14.4 节**）：每个 aggregate attempt 至多一个 `POST`；一个番号在整个过程中的任务数**由调用脚本的实际操作历史决定**，不存在“成功恰好 1 个、失败后恢复恰好 2 个”这类无条件断言。设 `calls(N)` = 调用脚本（独立于 P6 审计）对番号 `N` 实际触发的 aggregate 次数（每次 `preview` 含 `N` 计 1，每次 `retry_failed` 选中 `N` 计 1），则：`CREATION_CONFIRMED(N) ≤ 宿主上由 P6 创建的 N 的 SCRAPE 任务数 ≤ CREATION_CONFIRMED(N) + CREATION_UNKNOWN(N)`，且 `CREATION_CONFIRMED(N) + CREATION_UNKNOWN(N) ≤ calls(N)`。重复的显式 `retry_failed(previous)` 是两次独立操作，各自最多一个任务。

### 9.3 观察（`observe`）

```text
loop:
    GET /api/tasks/{id}
    成功 → 重置连续错误计数；status ∈ {done, failed} → 终态；否则继续
    失败（HostFailureKind ∈ {TIMEOUT, CONNECTION, NETWORK, SERVER_ERROR, HTTP_UNEXPECTED, RESPONSE_TOO_LARGE, SCHEMA_INVALID, TASK_VANISHED(404)}）
        → 连续错误计数 +1；达到 max_consecutive_poll_errors → ABANDONING（TASK_VANISHED 立即终止，不重试）
    HOST_AUTH_REJECTED（401/403）→ 立即 ABANDONING（凭据问题不会被重试修复）
    若 clock() - started ≥ aggregate_deadline_seconds → ABANDONING(HOST_DEADLINE)
    await sleep(min(poll_interval, 剩余 deadline))
```

* 至少执行一次 `GET`（即使 deadline 极小），避免“刚提交就判超时而没有机会观察到 done”。
* 观察失败重试是**对幂等 GET 的有界重复观察**，不重复执行工作，不创建任务，因而不构成第二个重试执行者（第 13 节）。
* 一次 aggregate 的请求数上界：`1`（submit）+ `⌈deadline / poll_interval⌉ + max_consecutive_poll_errors`（observe）+ `1`（metadata）+ 清理预算内的请求。

### 9.4 终态处理

* `status == "failed"`（且 P6 **没有**发出过取消）→ `FAILED(HOST_TASK_FAILED)`。**不**读取 `error` 文本，因此无法区分“番号不存在”与“来源故障”（L6-05）。
* `status == "done"`：
  1. `result` 必须是 `dict`，且含 `metadata_id`（`int`，非 `bool`，`≥ 1`）、`field_sources`（`dict[str,str]`）、`failed_sites`（`list[str]`）；否则
     `HOST_RESULT_INVALID`（“DONE 但缺 metadata_id / 结果结构非法”）。
  2. 任务侧归属校验（第 11.3.1 节）。
  3. `GET /api/metadata/{metadata_id}`（单次，不重试）。`404` → `HOST_METADATA_MISSING`；其它失败按第 8.4 节映射。
  4. 插件原始记录证据（第 11.3.2 节）与映射（第 11.4 节）。

### 9.5 门面 preflight（`AmaneHostClient.probe_worker`）与门面调用顺序（Design-R1 / R1-05）

**撤销旧声明**：旧稿声称门面 busy-first、“与 P4 一致，委托 P4 的 busy 守卫”。这无法实现：P4 `BatchOrchestrator._claim()` 是**私有**方法，只在其公开 `preview()` / `execute()` / `preview_retry()` 内部使用；P6 不得调用私有符号（第 6.4 节），也**不会**为保留这句话而复制 P4 的内部锁、引入第二套 admission 机制或 scheduler。冻结的是**实际调用顺序**，而不是无法实现的错误优先级：

```text
preview(items):
    1. 输入形态校验（items 为 list / tuple 且元素均为 DiscoveredMediaItem）→ AmaneBatchInputError      本地，零网络
    2. worker preflight：一次 GET /api/tasks/worker                                                       只读
    3. await orchestrator.preview(items)        ← P4 的 busy claim 只发生在这一步的入口；P4 已忙则其公开拒绝原样传播
preview_root(media_root, policy):
    参数校验（本地）→ worker preflight → discover_media（只读）→ await orchestrator.preview(items)
retry_failed(previous):
    previous 校验（FOREIGN_PREVIEW）→ 子集选择（NO_RETRYABLE_ITEMS / ROUND_LIMIT；纯函数、本地）
    → worker preflight → await orchestrator.preview(subset)
```

由此得到的、可测试的后果：

* P4 已忙（另一个 `preview` 正在运行）时，后到的调用可能已完成第 1、2 步——其中包含一次只读 `GET`——随后才被 P4 的公开接口拒绝。**不声称零网络访问**；声称的只是：被拒绝的调用**不提交任何 `POST /api/tasks`**，P4 的 busy 拒绝由 P4 原样给出，P6 不吞、不转换。
* 同时存在非法参数与 P4 busy 时，按上面的实际顺序，P6 自身的校验（第 1 步）先于 P4 busy，因此返回 `AmaneBatchInputError`；P6 **不承诺**“busy 优先于参数错误”或反之的全局优先级。
* preflight 不提交 SCRAPE、不创建任何宿主任务、不修改业务数据。“零副作用”的准确含义仅是**不创建 SCRAPE / 其它任务，也不修改 Task / Metadata 等业务数据**；宿主可能记录访问日志或指标，P6 不对此作任何声明。
* P6 门面**不绕过** P4 的并发控制：宿主 SCRAPE 只会由 P4 `BatchScheduler` 驱动的 `engine.aggregate` 发出；门面不直接调用 `engine.aggregate`，也不自行 `gather` / 开 task（AST 守卫，M6-20）。
* 若实现者发现“不新增操作 admission guard 就无法满足某条必需安全不变量”，**停止**并报告设计升级需求（U6-10），不得悄悄引入锁。

| 结果 | 行为 |
|---|---|
| `200 {"paused": false}` | 继续 |
| `200 {"paused": true}` | `AmaneHostPreflightError(WORKER_PAUSED)`（未创建任何宿主任务） |
| `401/403` | `AmaneHostPreflightError(AUTH_REJECTED)` |
| 超时 / 连接失败 | `AmaneHostPreflightError(HOST_UNREACHABLE)` |
| 其它 / 结构不符 | `AmaneHostPreflightError(PROTOCOL_MISMATCH)` |

引擎本身不做 preflight（便于直接注入与单测）。preflight 是**整批前置条件**，在任何任务被创建之前失败，因此不违反“单个条目失败不得拖垮整批”。`AmaneHostPreflightError` 在捕获 `AmaneHostCallError` 的 `except` 块**之外**构造（第 8.3 节：`__context__` 为 `None`）。

---

## 10. 取消合同（冻结）

### 10.1 所有权

* 取消**只**针对 P6 自己创建、并且已知 id 的那一个任务；动作是 `POST /api/tasks/batch {"action":"cancel","task_ids":[id]}`。
* 请求体里**永远不得**出现 `status` / `type`（宿主会把它解释成“取消所有 running 的 scrape”）；永远不得使用 `delete` / `retry`。
* 取消触发源：调用方取消（`CancelledError`）、批量取消（P4 TaskGroup 拆除）、deadline 到期、连续观察失败、echo 校验失败、未预期异常。
  **没有**其它触发源。

### 10.2 清理生命周期（唯一规范；Design-R4 / R4-02 重写，Design-R5 / R5-06、R5-10、R5-11、R5-12 修订）

**撤销 R3 的做法**：旧稿让清理在“独立的、被 `asyncio.shield` 的 task”里运行，并在 C5a 里用 `shield` 关闭 Response。实测（Python 3.12.10 / 3.14.7，`gateC.py`）证明：`shield` 内层 task 在二次取消或超时后继续存活并持有带 `Authorization` 的 Response；对内层 task `cancel()` 后无限 `await` 会让不配合取消的协程把取消变成无界等待；有界等待则会把仍在运行的 task 留下。这三种结果都被 Governance 拒绝（**允许 detached 清理 task：否决；接受无界取消：否决；用日志 / 计数掩盖泄漏：否决；悄悄削弱冻结要求：否决**）。

**R4 → R5：不再使用 `asyncio.timeout` / `asyncio.timeout_at` / `asyncio.wait_for`（R5-10）。** R4 用 `asyncio.timeout_at(deadline_at)` 区分“预算耗尽”与“二次取消”。实测（`t311.py`，CPython 3.11.0 / 3.11.2 与 3.11.3 / 3.11.9 并排运行）：3.11.0–3.11.2 中，在一次已被吞掉（消耗）的取消之后，`asyncio.timeout` 到期会以 `CancelledError` 而不是 `TimeoutError` 浮现（该缺陷在 3.11.3 起修复）。项目的 `requires-python` 是 `>=3.11`（不修改 `pyproject.toml`），3.11.0 属于受支持范围，因此 R5 **不依赖**该上下文管理器的内部计数。

**R5 治理附加裁决 B：每个宿主请求有一个总墙钟 deadline（修订了早先“每个等待只由 `httpx.Timeout` 约束”的说法）。** `httpx.Timeout` 的 `connect / read / write / pool` 是**每次 I/O 操作**的超时，每收到一个字节就重新计时。一个持续滴灌响应头的 slowloris 服务端可让一次请求远超 `request_timeout`：实测（`slow_probe.py`）R5 草案在 `request_timeout = 1.0` 下，响应头每 0.2 s 一个字节的服务端使 `_transport` 在 **62.56 s** 后才返回；红孪生（总 deadline 关闭，服务端滴灌 4 s）复现为 4.47 s / 1.0 s。因此 `_transport` 为每个请求加一个**由事件循环定时器强制的总 deadline**（不是 task，不是 `asyncio.timeout`）：

1. `deadline = loop.time() + t`；`base = task.cancelling()`；`timer = None`；`active` 是 `[False]` 形式的标志，**由调用者 `_call` 创建并传入 `_transport`，`_call` 在自己的 `finally` 里也清除它**（第二个独立所有者：它位于另一个帧、有自己的异常表项；Python 3.14 上的任一字节码探针发现 `_transport` 内存在没有任何异常表项覆盖的指令，致命异常落在那里会跳过 `_transport` 自己的 `finally`，只有第二所有者才能保证不留下活跃的定时器）。**在受 `finally` 保护的 `try` 内部**：`timer = loop.call_at(deadline, _expire)`，然后 `active[0] = True`。`_expire` 在 `active[0]` 为假时直接返回（一个泄漏的句柄永远不会取消无辜的 task）；否则 `fired = True` 并对**当前** task 调用 `cancel()`（本包唯一允许调用 `Task.cancel()` 的位置）。
2. 内层 `try` 的各个 `except` 只**记录事实**（`ce_seen = True`、`kind = …`），**不在处理体里分类**。`finally` 的第一条语句是 `active[0] = False`，随后撤销定时器；外层 `finally` 再保证一次。
3. **唯一的分类点**（在定时器撤销之后；R5-C-03）：若 `fired` 且尚未撤销 ⇒ `task.uncancel()` **恰好一次**，无论内层怎样回应了那次取消（传播 / 吞掉 / 转换成别的异常）；然后：`task.cancelling() > base` **或**（`ce_seen` 且未 `fired`）⇒ 存在尚未传播的外部取消 ⇒ `cancelled = True`、`kind = None`（出口抛出新的 `CancelledError`，C5c）；否则若 `fired` ⇒ `kind = "timeout"`（含内层把 deadline 取消转成了别的异常的情形）；否则保留处理体记录的 `kind`。**不再依赖 `await asyncio.sleep(0)` 是否抛出 `CancelledError` 来判断外部取消是否仍然存在**（R5 草案的冲洗在内层转换时会静默丢失调用方的取消，`task.cancelling() == 1` 但没有 `CancelledError` 再被投递）。
4. 响应关闭之后**再检查一次** `task.cancelling() > base`：关闭层吞掉或转换了一个外部取消时，同样抛出 `CancelledError`。
5. 响应体循环在每个块之后再检查 `loop.time() >= deadline`；每阶段 `httpx.Timeout(q = max(0.01, t/4))` 保留为次级上界。

**墙钟上界（真实服务端行为，不是 per-read 超时）**：单个请求 ≤ `t + ε`（ε = 一次事件循环迭代 + 本地套接字关闭，空闲机器上实测 ≤ 0.03 s，Gate 允许 0.45 s 调度余量）；清理阶段每个请求的 `t = max(0.05, min(request_timeout, 剩余预算))` 且**每次发出下一个请求之前**检查预算，所以清理（取消请求 + 轮询）≤ `cancel_budget_seconds + 0.05 + ε`；正常路径的一个 aggregate ≤ `aggregate_deadline_seconds + request_timeout + cancel_budget_seconds + 3ε`。依赖的 asyncio 接口只有 `Task.cancelling()` / `Task.uncancel()`（Python 3.11.0 起可用）和 `loop.call_at`，不依赖 `asyncio.timeout` 的内部计数；Gate C 的 D4–D9 在 3.11.0–3.14 上逐项验证（调用方自己的 `asyncio.timeout` 包住 P6 调用仍然工作）。

**取消归属不变量（Design-R5 最终安全闸；治理 Gate C-Final-01）**。设 `base` 为进入 `_transport` 时的 `Task.cancelling()`：

| 编号 | 不变量 |
|---|---|
| O1 | 内部 deadline **只拥有它自己发出的那一次**取消请求；`uncancel()` 至多调用一次，且仅当 `fired` |
| O2 | 调用方取消（含 `TaskGroup` 的取消与调用方 `asyncio.timeout`）**永不被吞掉，也永不被转换成 `HOST_TIMEOUT` / `HOST_NETWORK`**——**即使内层把 `CancelledError` 转换成了普通异常或吞掉了它**；判据是撤销自己那一次之后 `task.cancelling() > base` |
| O3 | 仅 deadline 到期时不泄漏取消计数：返回时 `cancelling() == base` |
| O4 | 定时器在每条退出路径上都被撤销，退出后没有挂起的 `must_cancel`，之后的 `await` 没有残留的 `CancelledError` |
| O5 | deadline 先到而调用方取消随后到达（在调用方的后续协程里）时，该取消被调用方观察到 |
| O6 | 武装发生在 `finally` 保护的 `try` 内部，回调受 `active` 标志约束；致命异常落在武装前后任一字节码处，都不会留下仍然活跃的 deadline 定时器，也不会让泄漏的句柄取消无辜的 task |

**已记录的确定性交错（Gate C `race_probe.py`，每一步都输出：外部取消次数、内部 deadline 是否触发、`Task.cancelling()` 前后、`uncancel` 调用、观察到的异常、定时器句柄是否已撤销、残留的挂起取消）**：R1 外部取消先于 deadline；R2 deadline 先于外部取消（外部取消随后到达调用方的后续协程）；R3 / R4 同一事件循环轮次内两种先后顺序；R5 / R5b 两次外部取消与 deadline 竞争；R6 `TaskGroup` 兄弟失败的取消与 deadline 竞争（早于 / 同轮次两种顺序）；R7 调用方 `asyncio.timeout()` 与 deadline 竞争（调用方先 / deadline 先 / 同轮次两种顺序）；R8a 请求正常完成而定时器必须被撤销、之后不得触发；R8b 请求完成与定时器回调同一轮次；R9a / R9b / R9c 响应关闭期间的外部取消（含 deadline 已触发之后）；R10 超时处理后调用方继续执行后续协程（两次超时、一次正常调用、`asyncio.timeout`、`TaskGroup`）；R11a / b / c `cancelling()` 基线已为 1（首次取消已被消耗，即清理阶段）时的 deadline、第二次外部取消、二者同轮次；**RC10 系列（Reviewer C 的 R10 反例族，R5-C-03）**：内层把 `CancelledError` 转换成普通异常——RC10-0 仅 deadline ⇒ `HOST_TIMEOUT`（不是 `HOST_NETWORK`）；RC10-1 仅外部取消 ⇒ `CancelledError`；RC10a / a' 同轮次外部 + deadline（两种先后）；RC10b 两次外部取消 + deadline；RC10c `TaskGroup` 取消 + deadline（早于 / 同轮次）；RC10d 调用方 `asyncio.timeout` + deadline（早于 / 同轮次）；RC10e 响应关闭期间到达的外部取消被关闭层转换。Reviewer C 的独立 `race.py`（逐字节保留）在 R5 草案规则下 R9 / R10 / R11 与新增用例变红，`race_c_revised.py`（同一 harness，仅替换 `transport()` 的归属规则，并有 `old` 变异模式）在 3.11.0 / 3.12 / 3.13 / 3.14 全部满足；原型的第五个红孪生 `r5_old_rule` 被 RC10-0 / RC10-1 / RC10a / RC10e 抓到。**红孪生**（三种破坏归属的实现必须使至少一个用例变红）：只按 `fired` 判定超时（会把外部取消转换成 `HOST_TIMEOUT`）、不 `uncancel`（计数泄漏）、无条件 `uncancel`（抹掉调用方取消）。

**R8b 的已知取舍（如实记录）**：响应在与定时器回调相同轮次、略早于它完成时，到期仍然胜出（`Task.cancel()` 在 future 已完成时置 `must_cancel`，`CancelledError` 在该 `await` 处抛出），已完成的响应被丢弃并分类为 `HOST_TIMEOUT`；这对提交请求意味着 `CREATION_UNKNOWN`（保守，且不会丢失“任务可能已创建”的事实）。

**Python 版本差异**：asyncio 自身在 `TaskGroup` 兄弟失败之后，父任务的 `cancelling()` 在 3.11 / 3.12 为 1、在 3.13 / 3.14 为 0（无 P6 代码的控制实验）；R6 的期望取该控制值。其余计数、异常与定时器状态在 3.11.0、3.12、3.13、3.14 逐项相同（race 表摘要一致）。探针接缝（`HOOK_BEFORE_EXPIRE` / `HOOK_AFTER_EXPIRE` / `HOOK_ARMED` / `TRACE`）**只存在于设计探针**，不是合同面；实现不得包含任何模块级测试钩子、开关或环境变量（E6-03，M6-50）。

**冻结的不可变要求**：有界取消；本包不创建任何游离（detached）清理 task；本包持有的敏感局部由其拥有者在致命处理体里重绑，且异常不再引用任何本包帧；不泄漏本包异常图；致命 `BaseException` 原样传播；致命路径不做清理 HTTP I/O。

**冻结的机制：全部清理在 aggregate 自己的 asyncio task 内联执行，包内不存在任何第二个 task。**

1. **所有权**：`src/fc2_amane_batch/**` 内**禁止**出现 `asyncio.shield`、`asyncio.timeout`、`asyncio.timeout_at`、`asyncio.wait_for`、`create_task`、`ensure_future`、`gather`、`TaskGroup`、`run_in_executor`、`to_thread`、`threading`（AST 守卫，E6-03，M6-30）。第 14 节 / 第 6.4 节中“清理 task 例外”一并撤销。
2. **取消到达**：`asyncio.CancelledError` 在 `except` 块里**只置标志** `cancelled = True`（C1），离开 `except` 块之后再按下表内联处理，处理完毕后以 C5c 抛出同类型新实例。**调用方发起的取消的计数从不被本包改动**：除第 7 条所述“撤销本包自己的 deadline 取消请求”的那一次 `uncancel()` 之外，本包不调用 `Task.uncancel()`，因此调用方 `TaskGroup` / `asyncio.timeout` 对取消计数的判断保持不变。

   | 取消到达时的 `S` | 内联动作 |
   |---|---|
   | `SUBMISSION_NOT_ATTEMPTED` | 无 I/O；记录 `C = NOTHING_TO_CANCEL` |
   | `CREATION_UNKNOWN`（`POST` 已交给传输层，尚无合法 `202`） | 无 I/O；`POST` 的等待已被取消（连接被丢弃），**不再等待响应**；记录 `C = UNCERTAIN_SUBMISSION_UNRESOLVED`。后果：取消落在 `POST` 在途期间时，宿主上可能留下孤儿任务（L6-03）；这是不使用游离 task 的代价，据实接受 |
   | `CREATION_CONFIRMED` | 内联取消流程（第 3 条）；即使此前已观察到终态，也仍发送一次精确取消（结果为 `TERMINAL_*_OBSERVED`），保持流程单一 |
3. **内联取消流程（仅 `S = CONFIRMED`）与取消结果的**唯一**分类（R5-06）**：`deadline_at = loop.time() + cancel_budget_seconds`。
   ① 置 `cancel_post_attempted = True`，分配 `cancel_event`，发送**一次**精确取消 `client.cancel_task(host_task_id)`（超时 `max(0.05, min(request_timeout, deadline_at - now))`；取消请求永不重发）。
   ② 取消请求得到有效 `200`（严格 reader：`affected` / `skipped` / `missing` 均为 `int`）⇒ 置 `cancel_request_confirmed = True`；否则（超时 / 连接失败 / 非 2xx / 畸形响应）⇒ 结束，`C = UNCERTAIN_NO_RESPONSE`，**不再观察**。
   ③ 已确认且 `missing ≥ 1` ⇒ `C = UNCERTAIN_TASK_VANISHED`，结束。
   ④ 已确认且 `missing = 0` ⇒ 观察循环：**每次发出下一个请求（sleep 之前与之后各一次）都先检查** `deadline_at - loop.time() ≤ 0`；`sleep` 不超过剩余预算；单次观察超时不超过剩余预算；观察失败（传输失败 / 畸形响应）**不**结束循环，继续轮询直到预算耗尽；观察到 `queued` / `running` 置 `nonterminal_observed = True`；观察到 `done` / `failed` ⇒ `TERMINAL_DONE_OBSERVED` / `TERMINAL_FAILED_OBSERVED`；观察得 `404` ⇒ `UNCERTAIN_TASK_VANISHED`。
   ⑤ 预算在没有终态 / 404 时耗尽：**已观察到过 `queued` / `running`** ⇒ `UNCERTAIN_NOT_TERMINAL`；**确认之后没有任何一次成功的状态观察** ⇒ `UNCERTAIN_OBSERVATION_FAILED`（新成员，R5-06）。

   **取消结果的严格优先级**（同一次清理里多条证据同时出现时按序判定，先命中者胜出；谓词 / 模拟器 / 表按此编码）：
   `被打断（二次取消 / 致命异常）` ＞ `取消请求无有效确认（NO_RESPONSE）` ＞ `missing ≥ 1 / 404（TASK_VANISHED）` ＞ `观察到终态（TERMINAL_*）` ＞ `预算耗尽且见过非终态（NOT_TERMINAL）` ＞ `预算耗尽且无成功观察（OBSERVATION_FAILED）`。
   含义：`NO_RESPONSE` 只表示**取消请求本身**没有被确认；`NOT_TERMINAL` 与 `OBSERVATION_FAILED` 的前提都是取消请求**已被确认**。二者之外绝不存在“取消没确认却说任务非终态”的组合（谓词规则；E6-08 / E6-09 / M6-34 / M6-35）。
4. **二次取消**：清理期间再次收到 `CancelledError`（落在任何一个 `await` 上）⇒ 在清理块的 `except asyncio.CancelledError` 里置 `interrupted = True`，**立即停止一切后续 I/O**，记录 `C = UNCERTAIN_CLEANUP_INTERRUPTED`、`T := CALLER_CANCEL`（二次取消取代原触发，成为终态的决定者），`cancel_post_attempted` / `cancel_request_confirmed` / `nonterminal_observed` 如实保留已发生的部分，随后以 C5c 抛出新实例。第三次及以后的取消同理（此时已无 I/O 可中断）。`S = UNKNOWN` 时的二次取消不改变 `C = UNCERTAIN_SUBMISSION_UNRESOLVED`（创建未知的事实不丢失）。
5. **清理期间的异常**：清理里的任何 `Exception`（连接失败、5xx、畸形响应……）只被分类为取消结果（见第 3 条），**绝不**遮盖正在传播的取消；清理块不吞掉 `CancelledError`。
6. **致命 `BaseException`**（`KeyboardInterrupt` / `SystemExit` / `GeneratorExit`）：不被捕获为取消，**不做任何清理 HTTP I/O**。`_transport` 没有致命处理体（它只武装 / 撤销 deadline 定时器并重绑局部）；**由边界帧的内联致命处理体**（第 10.5 节“生命周期设计”）先重绑自己持有的响应数据局部，再把 `__traceback__` / `__context__` / `__cause__` 置 `None`（确定性所有权清理 + 异常引用脱离；不访问任何帧），然后**裸 `raise`** 同一个对象（C1 的第二类允许；身份保持）。`aggregate` 的致命分支在此之后做**同步、幂等**的记账（`T := FATAL_BASEEXCEPTION`，`C := UNCERTAIN_CLEANUP_INTERRUPTED` 或按 `S` 取 `NOTHING_TO_CANCEL` / `UNCERTAIN_SUBMISSION_UNRESOLVED`，`R := RAISED`；该 attempt 已有记录则不重复，记账失败不得遮盖致命异常）。若致命异常打断一个正在进行的取消尝试，则 `cancel_post_attempted` 已为真。
7. **Response 关闭与 `_transport` 的异常分类（C5a / C5b 引用本条；R5-12）**：`Response` 的关闭在 `_transport` 内联执行（`await response.aclose()`），**不用 `shield`、不用 `asyncio.timeout`**、不起 task；关闭发生在定时器撤销之后；关闭期间的二次取消被捕获为标志（返回 `cancelled=True`），关闭异常被丢弃；致命路径不关闭（只同步重绑局部并净化）。关闭本身是本地套接字关闭，由 `httpcore` 保证有界，Gate C 在 5 个受支持解释器上实测。随后把 `request` / `response` / `stream` / `chunk` / `chunks` / `body` 全部重绑为 `None`。
   **`_transport` 的异常处理是封闭、完备的（R5-12）**：`CancelledError` ⇒ 置标志；致命 `BaseException` ⇒ 重绑局部后裸 `raise`；`httpx.TimeoutException` ⇒ `HOST_TIMEOUT`；`httpx.ConnectError` ⇒ `HOST_CONNECTION`；**其余任何 `Exception`（`httpx.HTTPError` 家族**或**任何非 `httpx` 的异常，例如被替换的传输层 / 第三方库在 `handle_async_request` 里抛出的 `RuntimeError`、`OSError` 子类、`ssl.SSLError`、`ValueError` 等）⇒ 一律 `HOST_NETWORK`**。不使用 `except` 之外的重抛：分类在 `except` 块里只**记一个封闭枚举值**，`HostCallError` 在 `except` 块**之外**由 `_call` 构造抛出，`__cause__` / `__context__` 均不携带原异常（因此不携带其 traceback 与栈帧里的 `Request` / `Response`）。红绿孪生（Gate C，E6-09）：把 `catch-all` 去掉（红）能复现 R4 的泄漏——非 `httpx` 异常带着含 token 的 `httpx` 帧逃出；加上（绿）则只得到 `HostCallError(HOST_NETWORK)`、无 cause / context、存活的带 token `Request` / `Response` 为 0。
8. **有界性的证据与未决范围（Gate C 覆盖必须分别标注，不得合并为一个无条件 PASS）**：

   | 项 | 状态 | 说明 |
   |---|---|---|
   | 生产 `httpx` 场景（缺省传输 + `httpcore` + `anyio`）：首次取消（等响应头 / 流中途 / 观察期）、二次取消、多次取消、清理超时、清理请求被对端关闭、清理请求永不返回、取消请求已确认而之后观察全部停滞、50 次流中取消、TLS 握手停滞、连接黑洞、**响应头 / 响应体 slowloris 的总 deadline（D1–D10）**、故障覆盖矩阵（22 项）、取消归属交错 R1–R11（含步骤记录与红孪生）、致命异常（F3 边界所有权，33 项 + 穷举窗口探针 + C 级槽位孪生，四个植入用例按 X-NARROW 逐项说明，见第 10.5 节）、测试接缝撤销后的验收能力（C3-1..C3-7） | **PASS（设计探针）**（已执行：Python 3.11.0 / 3.11.1 / 3.11.2 / 3.11.3 / 3.11.9 / 3.12.10 / 3.13.0 / 3.13.9 / 3.14.7，`httpx 0.27.2`；Gate C 全部 0 失败） | 剩余 P6 task = 0；存活的带 token `Request` / `Response` = 0；连接池仍可用；清理墙钟 ≤ 预算 + 调度余量；致命异常零额外 HTTP 请求。依据：定时器强制的总 deadline + 每阶段 `httpx.Timeout`，`httpcore` 的关闭路径是本地套接字关闭。**这是设计探针结论，不是对 S1 实现的 PASS** |
   | Python 3.13 | **设计探针 PASS；实现验收 NOT_RUN** | 设计探针已在 3.13.0 与 3.13.9（embeddable）上执行；**E6-25 在 S3 必须对真实 P6 包与其测试运行 3.13**（正式运行时验收计划）。在此之前不对“3.11–3.14 全范围”作出已实测通过的声明 |
   | `asyncio.timeout` 在 3.11.0–3.11.2 的缺陷 | **已复现并由设计规避**（`t311.py`；5 个 3.11 小版本并排） | R5 不使用 `asyncio.timeout` / `timeout_at` / `wait_for`；AST 守卫禁止（M6-30） |
   | DNS 解析线程（`getaddrinfo` 在 `anyio` 工作线程） | **UNVERIFIED** | 未探测；线程不是 P6 的 asyncio task，只含主机名不含凭据，但不可取消 |
   | 任意注入、吞掉 `CancelledError` 的 `transport=` | **方案 A：APPROVED FOR DESIGN REVISION ONLY（治理裁决；第 10.6 节）——DESIGN UPDATED** | 该参数（及 `_clock` / `_sleep`）已从 P6 公共构造面移除，故障改由真实回环代理注入；反例不再可经 P6 入口触发（仅进程级猴子补丁可复现，作为信息项记录）。独立复核尚未进行；不是 Independent PASS |

   `NOT_RUN` / `UNVERIFIED` / `BLOCKED` 都**不得**计为 `PASS`（第 23.2 节）。

   **R3 → R4：提交在途取消行为的变更（不得悄悄删除，取消合同在此处**并非**不变）**：

   | 项 | R3 | R4（R5 保持，待独立审查） |
   |---|---|---|
   | `POST /api/tasks` 在途时收到取消 | 清理 task 最多等待 `min(剩余预算, request_timeout)` 取得响应（best-effort response recovery）；若拿到合法 `202` 则取得 id、转入精确取消 | **不再等待响应**：对 `POST` 的等待被取消、连接被丢弃，不尝试恢复 id；记录 `CREATION_UNKNOWN`（`T = CALLER_CANCEL`，`C = UNCERTAIN_SUBMISSION_UNRESOLVED`，表 P05） |
   | 原因 | — | 恢复响应需要在取消到达之后继续持有在途请求，只能靠游离 / `shield` task。Gate C 实测这类 task 在二次取消 / 超时后继续存活并持有带 token 的 Response，或把取消变成无界等待；Governance 否决 detached 清理 task 与无界取消 |
   | 风险 | 仍可能漏掉在 `202` 之前丢失的响应 | 取消落在 `POST` 在途期间时，宿主上留下孤儿 SCRAPE 任务的概率**上升**；“尽力停止”的能力下降 |
   | 保持不变的安全保证 | `CREATION_UNKNOWN` 严格保守 | **`CREATION_UNKNOWN` 的语义不变且仍严格保守**：没有收到响应**绝不**被解释为“宿主没有创建任务”；任务数只有区间 `[0, ≥1]`，不折算为 0 或 1；计入 `creation_unknown` / `abandoned_attempts` / `uncertain_cancellations`；不自动重试、不找回（第 7.5 节）；调用方必须向用户呈现“可能仍有任务在运行并写入 Amane Metadata”（第 10.4 节）；晚到写入与 L3 `UNVERIFIED` 的声明不变 |

9. **`__context__` 的边界（C5c 澄清）**：新实例的 `__cause__` 恒为 `None`；`__context__` 为 `None`，**或**为调用方在调用 `aggregate` 时**已经在处理**的那个异常对象（Python 的隐式链接，实测 `ValueError` 被链入）。该对象是调用方自己的，不是本包引入的，不在保护面内；测试用 `sys.exception()` 在调用入口取样，断言 `e.__context__ is None or e.__context__ is entry_exception`，其它任何 `__context__` 都是违例。
10. **取消 / 致命的审计窗口**：本包在上述每个出口都同步地写完整条 `HostAttemptRecord`（无 I/O），然后才抛出；`aggregate` 在分配 `seq` 之前被取消 / 失败则**没有记录**。

**探针（Gate C，真实 `httpx 0.27.2`，Python 3.11.0 / 3.11.1 / 3.11.2 / 3.11.3 / 3.11.9 / 3.12.10 / 3.14.7，结果一致）**：首次取消（等响应头 / 流中途 / 观察期）、二次取消（取消请求停滞时）、清理超时、清理请求被对端关闭、清理请求永不返回（每请求超时兜底）、取消已确认而之后观察全部停滞（`OBSERVATION_FAILED`）、50 次流中取消、TLS 握手停滞、黑洞、slowloris、致命异常（零额外 HTTP 请求，身份保持）。输出：P6 task 前后差 = 0；最长耗时 = 预算内；`Request` / `Response` 存活 = 0；清理 HTTP 请求数 = 预期。

### 10.3 提交、清理与取消结果的状态机（唯一规范；Design-R4 / R4-07 重写）

**三个必须分开的层次（Design-R1 保留，不得互相推断）**：

| 层次 | 含义 | P6 能否通过公开结构化 API 观察 |
|---|---|---|
| L1 请求层 | 取消请求已发出 / 被宿主受理（`affected` / `skipped` / `missing`） | 能 |
| L2 记录层 | 宿主**数据库里的任务记录**到达终态（`done` / `failed`） | 能（`GET /api/tasks/{id}` 的 `status`） |
| L3 执行层 | 宿主里**执行该任务的协程已经停止**，不会再写 Metadata 或产生其它宿主副作用 | **不能**：P6 不读 worker 私有运行表、不读 SQLite、不解析错误文本 |

`CONFIRMED_STOPPED` 保持撤销（DIFF-P6-01 / DIFF-P6-05）：`failed` 只证明 L2；**不存在任何会断言 L3 已达成的枚举值**；L3 对每一次放弃 / 取消都是 `UNVERIFIED`。

**四个维度正交冻结，外加三个取消见证（Design-R5）**：

```text
S  SubmissionState     SUBMISSION_NOT_ATTEMPTED | CREATION_CONFIRMED | CREATION_UNKNOWN         （终态记录不得为 SUBMISSION_ATTEMPTED）
T  CleanupTrigger      NONE | CALLER_CANCEL | DEADLINE | OBSERVATION_FAILURE | ECHO_MISMATCH |
                       SUBMISSION_UNRESOLVED | INTERNAL_ERROR | FATAL_BASEEXCEPTION             终态的**决定性**触发（后到的二次取消 / 致命异常取代先前触发）；NONE = 没有触发
C  CancelOutcome       见下表（10 个成员）                                                      清理路径的结果；NOT_APPLICABLE ⇔ T == NONE
R  AggregateTerminal   SUCCESS | FAILED | RAISED | CANCELLED                                      aggregate 对 P4 的终态
cpa  cancel_post_attempted      bool   取消请求已“尝试发送”（自报告，L1）
cf   cancel_request_confirmed   bool   取消请求得到了有效的 200 响应（自报告）
nt   nonterminal_observed       bool   取消确认之后观察到过 queued / running（自报告）
```

“可产生状态”由 `(S, T, C, R, cpa, cf, nt)` 七元组刻画；**状态数不是预设的**：参考模拟器从控制流穷举得到（下方表），当前为 **63** 条，由独立复算得出，不是 R4 的固定数字 39（R4 的 39 条把“取消已确认”“见过非终态”等见证折叠掉了，遗漏了第 10.2 节第 3 条的全部分类路径，被 R5-02 / R5-06 指出）。

#### `CancelOutcome`（封闭枚举，**10** 个成员；全部来自结构化观察）

| 值 | 含义 | 观察依据 |
|---|---|---|
| `NOT_APPLICABLE` | **没有触发任何清理 / 取消路径**（`T == NONE`）。正常成功与未取消的失败（含 `HOST_TASK_FAILED`、`done` 之后的映射失败）都是此值，**不论任务是否已创建** | 无 |
| `NOTHING_TO_CANCEL` | 清理被触发，但宿主上没有可取消的东西：`S == SUBMISSION_NOT_ATTEMPTED`（`POST` 从未发出） | 请求账本里没有 submit |
| `TERMINAL_FAILED_OBSERVED` | 取消请求**已确认**之后，观察到该 id 的数据库终态 `failed`。**仅证明记录为 FAILED；不证明协程已停止，不证明之后不会再有宿主侧写入** | `status == "failed"` |
| `TERMINAL_DONE_OBSERVED` | 取消请求已确认之后观察到数据库终态 `done`（宿主已写入 Metadata；是否发生在取消之前 P6 无法区分）。**不会**被当作本次 aggregate 的成功使用 | `status == "done"` |
| `UNCERTAIN_NO_RESPONSE` | **取消请求本身**超时 / 连接失败 / 非 2xx / 畸形响应——从未得到有效确认（`cf = 否`）。此时 P6 **不知道**任务是否仍是非终态，**不能**说“任务非终态” | 传输 / 状态码 |
| `UNCERTAIN_NOT_TERMINAL` | 取消请求**已确认**（`cf = 是`），并且确认之后观察到过 `queued` / `running`（`nt = 是`），预算耗尽时仍无终态 | 结构化 `status` |
| `UNCERTAIN_OBSERVATION_FAILED`（R5-06 新增） | 取消请求**已确认**（`cf = 是`），但确认之后**没有任何一次成功的状态观察**（`nt = 否`），预算耗尽。P6 不能说任务是否终态 | 控制流（每次观察都失败 / 停滞） |
| `UNCERTAIN_SUBMISSION_UNRESOLVED` | `S == CREATION_UNKNOWN`：任务 id 从未获得（可能 0 个，也可能 ≥ 1 个），无法取消 | 无 id |
| `UNCERTAIN_TASK_VANISHED` | 取消响应 `missing ≥ 1` 或观察得到 `404` | 结构化计数 / 状态码 |
| `UNCERTAIN_CLEANUP_INTERRUPTED` | 清理被第二次取消打断，或致命 `BaseException` 之后未做任何清理 I/O | 控制流 |

#### 10.3.1 规范类型与谓词（`HostAttemptRecord.__post_init__` 的唯一定义；Design-R5 / R5-01、R5-02、R5-03 重写）

下面两个代码块是 `HostAttemptRecord` 的**唯一规范性定义**：第一个是**真实的**枚举与冻结 `slots` 数据类（`HostAttemptRecord`、`SubmissionState`、`CleanupTrigger`、`CancelOutcome`、`AggregateTerminal`、`HostFailureKind`、`TimestampRelation`、`AmaneBatchContractError`），第二个是 `record_is_legal`。合同其它章节、Master Plan、Construction Plan 与证据行只引用它们，**不得**另写一套条件。违反 ⇒ `AmaneBatchContractError("illegal HostAttemptRecord")`（固定文本）。Gate B 从本文件抽取这两个代码块、用**真实枚举与真实数据类**构造记录并直接执行（不再使用字符串替身；R4 的字符串谓词遇到真实枚举会 `KeyError`，R5-01）。

R5 谓词的性质：① **对任意输入返回 `bool`，不抛出**（`KeyError` / `TypeError` / `AttributeError` 均不会出现在谓词内部：先做类型层检查，再做语义规则）；② 枚举字段必须是**本包的真实枚举成员**（字符串替身、外来枚举、未知值一律拒绝）；③ 布尔见证必须是严格 `bool`（`0` / `1` / `"x"` 拒绝）；④ 整数字段排除 `bool`、范围检查；⑤ `outcome` 必须与触发匹配（例如 `DEADLINE ⇒ HOST_DEADLINE`、`ECHO_MISMATCH ⇒ HOST_SCHEMA_INVALID`、`SUBMISSION_UNRESOLVED ⇒` 传输类、`T = NONE ∧ FAILED ⇒` 传输类或 `TASK_FAILED` 或映射失败类）；⑥ `terminal_status` 必须与路径一致（`T = NONE`：`HOST_TASK_FAILED ⇔ "failed"`，其余 `"done"`；清理路径：`TERMINAL_FAILED_OBSERVED ⇔ "failed"`、`TERMINAL_DONE_OBSERVED ⇔ "done"`，其它必为 `None`；`TERMINAL_FAILED_OBSERVED` 搭配 `terminal_status = "done"` 被拒绝）；⑦ `cancel_request_confirmed ⇒ cancel_post_attempted`、`nonterminal_observed ⇒ cancel_request_confirmed`；⑧ **H3 已送达（取消尝试）而 H4 缺席（`UNKNOWN`）**——合法的是 `cancel_post_attempted = 否`（H3 单独**永不**授权取消，第 14.4 节）；致命 / 取消落在 `H3 ⇒ H4` 之间的窗口都落入 `S = UNKNOWN` 的 P05 / P06 / P07，字段 `host_task_id = None`。

**R1 / x-01 严格类型与不可变性（追加）**：⑨ **对象层**：谓词先要求 `type(r) is HostAttemptRecord`（子类、鸭子类型、`None`、错误对象一律拒绝）并要求全部字段已初始化（未初始化的 slots 实例拒绝），所以对**任意**不可信输入都返回 `bool`，不会抛出 `AttributeError` / `KeyError` / `TypeError`；⑩ **严格 str**：`terminal_status`、`number`、`attempt_id` 必须是 exact `str`——`UserString` 之类“比较行为像 str”的可变对象一律拒绝（否则冻结记录的不可变性被绕过：构造时 `terminal_status == "done"` 通过校验，之后改 `.data` 即可让已验证的记录变成非法）；构造边界与谓词是同一处：`HostAttemptRecord.__post_init__` 调用本谓词，不允许只改测试 oracle 而放过模型构造；⑪ 违规一律抛出固定文本 `AmaneBatchContractError("illegal HostAttemptRecord")`，不回显任何字段内容、不链接其它异常；⑫ Enum / 严格 bool / 事件 / `HostFailureKind` 的原有约束全部保持，63 个抽象状态集合不变（Gate B：7680 个基础组合仍是 63 接受、0 崩溃、0 越权接受）。红绿孪生（`x01_strict_types.py`，真实枚举 / 真实冻结 `slots` 数据类 / 从合同抽取的谓词）：`good.terminal_status == "done"`；`bad = replace(good, terminal_status=UserString("done"))` 在 R5 被接受并可随后 `bad.terminal_status.data = "failed"`，在 R1 于构造处被拒绝；`record_is_legal(None) is False`、`record_is_legal(SimpleNamespace()) is False`（R5 抛 `AttributeError`）。

```python gate:host_attempt_record_types
import dataclasses
import enum


class AmaneBatchContractError(RuntimeError):
    """P6 内部不变量被破坏（缺陷，不是外部失败）；消息固定。"""


class HostFailureKind(enum.Enum):                       # 第 12.1 节：19 个成员；value = 去掉 HOST_ 前缀的小写
    HOST_TIMEOUT = "timeout"
    HOST_CONNECTION = "connection"
    HOST_NETWORK = "network"
    HOST_AUTH_REJECTED = "auth_rejected"
    HOST_RATE_LIMITED = "rate_limited"
    HOST_SERVER_ERROR = "server_error"
    HOST_HTTP_UNEXPECTED = "http_unexpected"
    HOST_RESPONSE_TOO_LARGE = "response_too_large"
    HOST_RESPONSE_TOO_COMPLEX = "response_too_complex"
    HOST_SCHEMA_INVALID = "schema_invalid"
    HOST_TASK_VANISHED = "task_vanished"
    HOST_TASK_FAILED = "task_failed"
    HOST_DEADLINE = "deadline"
    HOST_RESULT_INVALID = "result_invalid"
    HOST_ATTRIBUTION_FOREIGN = "attribution_foreign"
    HOST_METADATA_MISSING = "metadata_missing"
    HOST_METADATA_NUMBER_MISMATCH = "metadata_number_mismatch"
    HOST_METADATA_CONTRACT = "metadata_contract"
    HOST_METADATA_BELOW_MINIMUM = "metadata_below_minimum"


class SubmissionState(enum.Enum):                       # 第 9.2 节
    SUBMISSION_NOT_ATTEMPTED = "not_attempted"
    SUBMISSION_ATTEMPTED = "attempted"                  # 仅瞬态；终态记录不得使用
    CREATION_CONFIRMED = "confirmed"
    CREATION_UNKNOWN = "unknown"


class CleanupTrigger(enum.Enum):                        # 第 10.3 节：终态的决定性触发
    NONE = "none"
    CALLER_CANCEL = "caller_cancel"
    DEADLINE = "deadline"
    OBSERVATION_FAILURE = "observation_failure"
    ECHO_MISMATCH = "echo_mismatch"
    SUBMISSION_UNRESOLVED = "submission_unresolved"
    INTERNAL_ERROR = "internal_error"
    FATAL_BASEEXCEPTION = "fatal_baseexception"


class CancelOutcome(enum.Enum):                         # 第 10.3 节：10 个成员（无任何断言“执行已停止”的成员）
    NOT_APPLICABLE = "not_applicable"
    NOTHING_TO_CANCEL = "nothing_to_cancel"
    TERMINAL_FAILED_OBSERVED = "terminal_failed_observed"
    TERMINAL_DONE_OBSERVED = "terminal_done_observed"
    UNCERTAIN_NO_RESPONSE = "uncertain_no_response"                 # 取消请求本身从未得到有效确认
    UNCERTAIN_NOT_TERMINAL = "uncertain_not_terminal"               # 取消已确认，且观察到过 queued/running，预算耗尽时仍非终态
    UNCERTAIN_OBSERVATION_FAILED = "uncertain_observation_failed"   # 取消已确认，但确认之后没有任何一次成功的状态观察
    UNCERTAIN_SUBMISSION_UNRESOLVED = "uncertain_submission_unresolved"
    UNCERTAIN_TASK_VANISHED = "uncertain_task_vanished"
    UNCERTAIN_CLEANUP_INTERRUPTED = "uncertain_cleanup_interrupted"


class AggregateTerminal(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RAISED = "raised"
    CANCELLED = "cancelled"


class TimestampRelation(enum.Enum):                     # 第 11.3.4 节：仅两个时间戳字符串的比较标签
    UPDATED_NOT_AFTER_FINISHED = "updated_not_after_finished"
    UPDATED_AFTER_FINISHED = "updated_after_finished"
    INDETERMINATE = "indeterminate"


@dataclasses.dataclass(frozen=True, slots=True)
class HostAttemptRecord:                                # 唯一定义；__post_init__ 调用第 10.3.1 节的 record_is_legal
    seq: int
    engine_index: int
    attempt_id: str
    completion_seq: int                                 # 完成序号（稠密 1..completed），第 20.5 节
    number: str
    host_task_id: "int | None"
    outcome: "HostFailureKind | None"
    terminal_status: "str | None"                       # "done" | "failed" | None
    submission: SubmissionState
    cleanup_trigger: CleanupTrigger
    cancel: CancelOutcome
    terminal: AggregateTerminal
    cancel_post_attempted: bool                         # L1 见证（自报告）
    cancel_request_confirmed: bool                      # 取消请求得到有效 200 响应（自报告）
    nonterminal_observed: bool                          # 取消确认之后观察到 queued / running（自报告）
    begin_event: int
    task_known_event: "int | None"
    cancel_event: "int | None"
    end_event: int
    polls: int
    requests: int
    dropped_url_count: int
    display_title_diverged: bool
    timestamp_relation: TimestampRelation
    metadata_id: "int | None"
    elapsed_ms: float

    def __post_init__(self):
        if not record_is_legal(self):
            raise AmaneBatchContractError("illegal HostAttemptRecord")
```

```python gate:record_is_legal
def record_is_legal(r):
    """HostAttemptRecord 合法性的唯一规范谓词。只接受上面真实枚举与严格类型；对**任意**输入（None、错误对象、未初始化实例、鸭子类型）都返回 bool，
    绝不抛出 AttributeError / KeyError / TypeError，也不在任何输出里回显字段内容（调用方 __post_init__ 只抛出固定文本）。"""
    SS, TT, CC, RR, FK = SubmissionState, CleanupTrigger, CancelOutcome, AggregateTerminal, HostFailureKind

    # ---- 0. 对象层：只有真实的冻结 slots 数据类实例（子类、鸭子类型、None 一律拒绝）；字段必须全部已初始化
    if type(r) is not HostAttemptRecord:
        return False
    for _name in HostAttemptRecord.__dataclass_fields__:
        if not hasattr(r, _name):                         # 未初始化的 slots 实例：缺属性 ⇒ 拒绝，不让 AttributeError 逃出
            return False

    def is_int(x, lo):                                   # int（排除 bool）且 >= lo
        return type(x) is int and x >= lo

    def opt_int(x, lo):
        return x is None or is_int(x, lo)

    # ---- 1. 类型层：枚举必须是真实枚举成员（字符串替身、外来枚举、未知值一律拒绝）
    S, T, C, R = r.submission, r.cleanup_trigger, r.cancel, r.terminal
    if not (type(S) is SS and type(T) is TT and type(C) is CC and type(R) is RR and type(r.timestamp_relation) is TimestampRelation):
        return False
    if not (r.outcome is None or type(r.outcome) is FK):
        return False
    for flag in (r.cancel_post_attempted, r.cancel_request_confirmed, r.nonterminal_observed, r.display_title_diverged):
        if type(flag) is not bool:                        # 0 / 1 / "x" 都不是 bool
            return False
    if not (type(r.number) is str and r.number and type(r.attempt_id) is str):
        return False
    if not (is_int(r.seq, 1) and is_int(r.engine_index, 1) and is_int(r.completion_seq, 1)
            and r.attempt_id == "e%d-a%d" % (r.engine_index, r.seq)):
        return False
    if not (is_int(r.polls, 0) and is_int(r.requests, 0) and is_int(r.dropped_url_count, 0)):
        return False
    if not (type(r.elapsed_ms) in (int, float) and r.elapsed_ms >= 0 and r.elapsed_ms == r.elapsed_ms and r.elapsed_ms != float("inf")):
        return False
    if not (opt_int(r.host_task_id, 1) and opt_int(r.metadata_id, 1) and opt_int(r.task_known_event, 1) and opt_int(r.cancel_event, 1)):
        return False
    if not (r.terminal_status is None or (type(r.terminal_status) is str and r.terminal_status in ("done", "failed"))):
        return False                                      # 严格 str：UserString 等“比较行为像 str”的可变对象一律拒绝（x-01）
    if S is SS.SUBMISSION_ATTEMPTED:                      # 瞬态；终态记录不得使用
        return False
    # ---- 2. 事件
    if not (is_int(r.begin_event, 1) and is_int(r.end_event, 1) and r.begin_event < r.end_event):
        return False
    # ---- 3. T -> R（终态由决定性触发唯一确定）与 outcome 的类型一致性
    allowed_R = {TT.NONE: (RR.SUCCESS, RR.FAILED), TT.CALLER_CANCEL: (RR.CANCELLED,), TT.FATAL_BASEEXCEPTION: (RR.RAISED,),
                 TT.INTERNAL_ERROR: (RR.RAISED,), TT.DEADLINE: (RR.FAILED,), TT.OBSERVATION_FAILURE: (RR.FAILED,),
                 TT.ECHO_MISMATCH: (RR.FAILED,), TT.SUBMISSION_UNRESOLVED: (RR.FAILED,)}
    if R not in allowed_R[T]:
        return False
    transport = (FK.HOST_TIMEOUT, FK.HOST_CONNECTION, FK.HOST_NETWORK, FK.HOST_AUTH_REJECTED, FK.HOST_RATE_LIMITED, FK.HOST_SERVER_ERROR,
                 FK.HOST_HTTP_UNEXPECTED, FK.HOST_RESPONSE_TOO_LARGE, FK.HOST_RESPONSE_TOO_COMPLEX, FK.HOST_SCHEMA_INVALID)
    allowed_outcome = {TT.NONE: transport + (FK.HOST_TASK_FAILED, FK.HOST_RESULT_INVALID, FK.HOST_ATTRIBUTION_FOREIGN, FK.HOST_METADATA_MISSING,
                                             FK.HOST_METADATA_NUMBER_MISMATCH, FK.HOST_METADATA_CONTRACT, FK.HOST_METADATA_BELOW_MINIMUM),
                       TT.SUBMISSION_UNRESOLVED: transport, TT.OBSERVATION_FAILURE: transport + (FK.HOST_TASK_VANISHED,),
                       TT.ECHO_MISMATCH: (FK.HOST_SCHEMA_INVALID,), TT.DEADLINE: (FK.HOST_DEADLINE,)}
    if R is RR.FAILED:
        if r.outcome is None or r.outcome not in allowed_outcome[T]:
            return False
    elif r.outcome is not None:
        return False
    if (C is CC.NOT_APPLICABLE) != (T is TT.NONE):        # NOT_APPLICABLE <=> 未触发清理
        return False
    # ---- 4. 不同提交状态下的字段
    no_cancel_witness = (not r.cancel_post_attempted and not r.cancel_request_confirmed and not r.nonterminal_observed and r.cancel_event is None)
    if S is SS.SUBMISSION_NOT_ATTEMPTED:
        return (r.host_task_id is None and r.task_known_event is None and no_cancel_witness and r.terminal_status is None and r.metadata_id is None
                and T in (TT.CALLER_CANCEL, TT.INTERNAL_ERROR, TT.FATAL_BASEEXCEPTION) and C is CC.NOTHING_TO_CANCEL)
    if S is SS.CREATION_UNKNOWN:
        return (r.host_task_id is None and r.task_known_event is None and no_cancel_witness and r.terminal_status is None and r.metadata_id is None
                and T in (TT.SUBMISSION_UNRESOLVED, TT.CALLER_CANCEL, TT.INTERNAL_ERROR, TT.FATAL_BASEEXCEPTION)
                and C is CC.UNCERTAIN_SUBMISSION_UNRESOLVED)
    # ---- 5. CREATION_CONFIRMED：H4 事件、任务 id
    if not (is_int(r.host_task_id, 1) and is_int(r.task_known_event, 1) and r.begin_event < r.task_known_event < r.end_event):
        return False
    if T is TT.SUBMISSION_UNRESOLVED:
        return False
    if R is RR.SUCCESS and r.metadata_id is None:
        return False
    if T is TT.NONE:                                      # 正常路径：不发取消；terminal_status 与 outcome 对应
        if not (C is CC.NOT_APPLICABLE and no_cancel_witness):
            return False
        task_failed = (R is RR.FAILED and r.outcome is FK.HOST_TASK_FAILED)
        return r.terminal_status == ("failed" if task_failed else "done")
    # ---- 6. 清理路径（T != NONE）
    if C in (CC.NOT_APPLICABLE, CC.NOTHING_TO_CANCEL, CC.UNCERTAIN_SUBMISSION_UNRESOLVED):
        return False
    if r.cancel_request_confirmed and not r.cancel_post_attempted:
        return False
    if r.nonterminal_observed and not r.cancel_request_confirmed:
        return False
    if r.cancel_post_attempted:                           # L1 见证：尝试发送取消请求
        if not (is_int(r.cancel_event, 1) and r.task_known_event < r.cancel_event < r.end_event):
            return False
    else:
        if r.cancel_event is not None or C not in (CC.UNCERTAIN_CLEANUP_INTERRUPTED, CC.UNCERTAIN_TASK_VANISHED):
            return False                                  # 其余 C 都以取消尝试为前提
        if C is CC.UNCERTAIN_TASK_VANISHED and T is not TT.OBSERVATION_FAILURE:
            return False                                  # 未发取消而得 404：只来自观察失败
    if (r.outcome is FK.HOST_TASK_VANISHED) != (C is CC.UNCERTAIN_TASK_VANISHED and not r.cancel_post_attempted):
        return False                                      # 观察得 404（未发取消）⇔ outcome = TASK_VANISHED
    # 取消结果与“确认 / 观察”见证的对应（R5-06）
    if C is CC.UNCERTAIN_NO_RESPONSE and (r.cancel_request_confirmed or r.nonterminal_observed):
        return False                                      # 取消请求从未得到有效确认
    if C is CC.UNCERTAIN_NOT_TERMINAL and not (r.cancel_request_confirmed and r.nonterminal_observed):
        return False                                      # 必须确认过取消，且观察到过非终态
    if C is CC.UNCERTAIN_OBSERVATION_FAILED and not (r.cancel_request_confirmed and not r.nonterminal_observed):
        return False                                      # 确认之后一次成功观察都没有
    if C in (CC.TERMINAL_FAILED_OBSERVED, CC.TERMINAL_DONE_OBSERVED) and not r.cancel_request_confirmed:
        return False                                      # 终态只能在确认取消之后经观察得到
    if C is CC.UNCERTAIN_TASK_VANISHED and r.cancel_post_attempted and not r.cancel_request_confirmed:
        return False                                      # 取消响应 missing>=1 或确认后观察 404
    if C is CC.UNCERTAIN_CLEANUP_INTERRUPTED and T not in (TT.CALLER_CANCEL, TT.FATAL_BASEEXCEPTION):
        return False                                      # 清理只会被二次取消或致命异常打断，它们取代 T
    if T is TT.FATAL_BASEEXCEPTION and C is not CC.UNCERTAIN_CLEANUP_INTERRUPTED:
        return False                                      # 致命异常：不做清理 I/O，不会观察到终态
    expected_status = {CC.TERMINAL_FAILED_OBSERVED: "failed", CC.TERMINAL_DONE_OBSERVED: "done"}.get(C)
    return r.terminal_status == expected_status           # 清理路径的 terminal_status = 取消之后观察到的终态
```

规则速览（仅帮助阅读，**以代码为准**）：`T→R` 唯一确定（`CALLER_CANCEL→CANCELLED`、`FATAL_BASEEXCEPTION/INTERNAL_ERROR→RAISED`、`DEADLINE/OBSERVATION_FAILURE/ECHO_MISMATCH/SUBMISSION_UNRESOLVED→FAILED`、`NONE→SUCCESS/FAILED`）；`NOT_APPLICABLE ⇔ T=NONE`；`S=CONFIRMED` 必有合法 `task_known_event`（H4）且 `begin < task_known_event < end`；取消尝试的 `cancel_event` 严格落在 `task_known_event` 与 `end` 之间；`TERMINAL_*` 必须在**确认**之后；`NO_RESPONSE ⇒ ¬cf ∧ ¬nt`；`NOT_TERMINAL ⇒ cf ∧ nt`；`OBSERVATION_FAILED ⇒ cf ∧ ¬nt`；致命异常不会观察到终态；`UNCERTAIN_CLEANUP_INTERRUPTED` 只来自二次取消或致命异常。

#### 10.3.2 事件与标识

* 每个 engine 有一个单调递增的逻辑事件计数器 `next_event`（同一 asyncio 事件循环内天然全序）；`begin_event` / `task_known_event` / `cancel_event` / `end_event` 都取自它，因此**同一 engine 内全部记录的事件互不相同且严格递增**；不同 engine 的计数器相互独立，比较只在 engine 内进行。事件值必须是 `int` 且排除 `bool`、`≥ 1`。
* `seq` 在 engine 内从 1 连续递增（稠密，**按开始顺序**分配）；`attempt_id == "e{engine_index}-a{seq}"`，`engine_index` 由模块级 `itertools.count` 分配、进程内唯一。`completion_seq` 在 engine 内从 1 连续递增（稠密，**按完成顺序**分配）；乱序完成时 `seq` 与 `completion_seq` 不同（第 20.5 节）。分配时断言 `seq == last_seq + 1`、`completion_seq == last_completion_seq + 1`。
* `task_known_event`（H4）在 engine 完成 `202` + 严格 reader 校验、记录 `host_task_id` 的那一刻分配；`cancel_event` 在调用 `client.cancel_task` **之前**分配并置 `cancel_post_attempted = True`（“尝试发送”，**不是**“已送达”）；`cancel_request_confirmed` 在取得有效 `200` 之后置真；`nonterminal_observed` 在取消确认之后的观察得到 `queued` / `running` 时置真。

#### 10.3.3 取消请求见证（L1；自报告与独立事实的区分）

`cancel_post_attempted` / `cancel_request_confirmed` / `nonterminal_observed` / `cancel_event` / `task_known_event` / `attempt_id` 是 P6 **自报告**的见证；谓词只能验证它们的**内部一致性**。网络事实只由独立故障代理证明：对账规则见第 14.4 节 O2-5——`cancel_request_confirmed = True` 必须有代理观察到的、该 attempt 精确 task_id 取消 `POST` 的**已送达 `200`**（非 `late`）；`TERMINAL_FAILED_OBSERVED` / `TERMINAL_DONE_OBSERVED` 必须有该 attempt **自己 task_id** 的、发生在取消确认**之后**的 `GET`，且实际返回对应终态。绝不把布尔值当作“网络请求真实发生”的独立证明；仅有 P6 自报告字段而没有代理事实 ⇒ 红。

#### 10.3.4 可产生记录表（独立参考模拟器的输出；谓词接受集合必须与之相等）

下表共 **63** 条，由一个与谓词**分别编写**的控制流步骤机（参考模拟器；其源码已在审查证据包中，可立即检查；不是合同代码）穷举 `POST` 前 / `POST` 在途 / 确认后 × 取消 / 二次取消 / 致命 / 内部错误 / deadline / 观察失败 / echo 不符 / 404 / 正常成功与失败 × 取消确认与否 × 观察到非终态与否得到。Gate B 对 `3 × 8 × 10 × 4 × 2 × 2 × 2 = 7680`（瞬态 `SUBMISSION_ATTEMPTED` 另行单独断言为非法） 个基础组合逐一判定：**谓词接受 ⇔ 在本表中**。命名场景一律以本表的 ID 引用，不再另立表格。

| ID | S | T | C | R | cpa | cf | nt | abandoned | uncertain | creation_unknown | 场景 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P01 | NOT_ATTEMPTED | CALLER_CANCEL | NOTHING_TO_CANCEL | CANCELLED | 否 | 否 | 否 | 否 | 否 | 否 | POST 前 取消 |
| P02 | NOT_ATTEMPTED | FATAL_BASEEXCEPTION | NOTHING_TO_CANCEL | RAISED | 否 | 否 | 否 | 否 | 否 | 否 | POST 前 致命异常 |
| P03 | NOT_ATTEMPTED | INTERNAL_ERROR | NOTHING_TO_CANCEL | RAISED | 否 | 否 | 否 | 否 | 否 | 否 | POST 前 内部错误 |
| P04 | UNKNOWN | SUBMISSION_UNRESOLVED | UNCERTAIN_SUBMISSION_UNRESOLVED | FAILED | 否 | 否 | 否 | 是 | 是 | 是 | 提交在途 失败 / 超时 / 响应丢失 / 401 / 5xx |
| P05 | UNKNOWN | CALLER_CANCEL | UNCERTAIN_SUBMISSION_UNRESOLVED | CANCELLED | 否 | 否 | 否 | 是 | 是 | 是 | 提交在途 被取消 |
| P06 | UNKNOWN | FATAL_BASEEXCEPTION | UNCERTAIN_SUBMISSION_UNRESOLVED | RAISED | 否 | 否 | 否 | 是 | 是 | 是 | 提交在途 致命异常 |
| P07 | UNKNOWN | INTERNAL_ERROR | UNCERTAIN_SUBMISSION_UNRESOLVED | RAISED | 否 | 否 | 否 | 是 | 是 | 是 | 提交在途 内部错误 |
| P08 | CONFIRMED | NONE | NOT_APPLICABLE | SUCCESS | 否 | 否 | 否 | 否 | 否 | 否 | 正常成功 |
| P09 | CONFIRMED | NONE | NOT_APPLICABLE | FAILED | 否 | 否 | 否 | 否 | 否 | 否 | 正常失败（宿主 failed / done 之后映射失败） |
| P10 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_CLEANUP_INTERRUPTED | CANCELLED | 否 | 否 | 否 | 是 | 是 | 否 | 二次取消打断：取消请求发出之前 |
| P11 | CONFIRMED | FATAL_BASEEXCEPTION | UNCERTAIN_CLEANUP_INTERRUPTED | RAISED | 否 | 否 | 否 | 是 | 是 | 否 | 确认后致命异常（无清理 I/O） |
| P12 | CONFIRMED | OBSERVATION_FAILURE | UNCERTAIN_NO_RESPONSE | FAILED | 是 | 否 | 否 | 是 | 是 | 否 | OBSERVATION_FAILURE 清理：UNCERTAIN_NO_RESPONSE |
| P13 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_CLEANUP_INTERRUPTED | CANCELLED | 是 | 否 | 否 | 是 | 是 | 否 | 二次取消打断：取消请求在途 |
| P14 | CONFIRMED | FATAL_BASEEXCEPTION | UNCERTAIN_CLEANUP_INTERRUPTED | RAISED | 是 | 否 | 否 | 是 | 是 | 否 | 确认后致命异常（打断进行中的取消请求 / 观察） |
| P15 | CONFIRMED | OBSERVATION_FAILURE | UNCERTAIN_TASK_VANISHED | FAILED | 是 | 是 | 否 | 是 | 是 | 否 | OBSERVATION_FAILURE 清理：UNCERTAIN_TASK_VANISHED（未见非终态） |
| P16 | CONFIRMED | OBSERVATION_FAILURE | TERMINAL_FAILED_OBSERVED | FAILED | 是 | 是 | 否 | 是 | 否 | 否 | OBSERVATION_FAILURE 清理：TERMINAL_FAILED_OBSERVED（未见非终态） |
| P17 | CONFIRMED | OBSERVATION_FAILURE | TERMINAL_DONE_OBSERVED | FAILED | 是 | 是 | 否 | 是 | 否 | 否 | OBSERVATION_FAILURE 清理：TERMINAL_DONE_OBSERVED（未见非终态） |
| P18 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_CLEANUP_INTERRUPTED | CANCELLED | 是 | 是 | 否 | 是 | 是 | 否 | 二次取消打断：确认后观察中 |
| P19 | CONFIRMED | FATAL_BASEEXCEPTION | UNCERTAIN_CLEANUP_INTERRUPTED | RAISED | 是 | 是 | 否 | 是 | 是 | 否 | 确认后致命异常（打断进行中的取消请求 / 观察） |
| P20 | CONFIRMED | OBSERVATION_FAILURE | TERMINAL_FAILED_OBSERVED | FAILED | 是 | 是 | 是 | 是 | 否 | 否 | OBSERVATION_FAILURE 清理：TERMINAL_FAILED_OBSERVED（见过非终态） |
| P21 | CONFIRMED | OBSERVATION_FAILURE | TERMINAL_DONE_OBSERVED | FAILED | 是 | 是 | 是 | 是 | 否 | 否 | OBSERVATION_FAILURE 清理：TERMINAL_DONE_OBSERVED（见过非终态） |
| P22 | CONFIRMED | OBSERVATION_FAILURE | UNCERTAIN_TASK_VANISHED | FAILED | 是 | 是 | 是 | 是 | 是 | 否 | OBSERVATION_FAILURE 清理：UNCERTAIN_TASK_VANISHED（见过非终态） |
| P23 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_CLEANUP_INTERRUPTED | CANCELLED | 是 | 是 | 是 | 是 | 是 | 否 | 二次取消打断：见过非终态后观察中 |
| P24 | CONFIRMED | FATAL_BASEEXCEPTION | UNCERTAIN_CLEANUP_INTERRUPTED | RAISED | 是 | 是 | 是 | 是 | 是 | 否 | 确认后致命异常（打断进行中的取消请求 / 观察） |
| P25 | CONFIRMED | OBSERVATION_FAILURE | UNCERTAIN_NOT_TERMINAL | FAILED | 是 | 是 | 是 | 是 | 是 | 否 | OBSERVATION_FAILURE 清理：UNCERTAIN_NOT_TERMINAL（见过非终态） |
| P26 | CONFIRMED | OBSERVATION_FAILURE | UNCERTAIN_OBSERVATION_FAILED | FAILED | 是 | 是 | 否 | 是 | 是 | 否 | OBSERVATION_FAILURE 清理：UNCERTAIN_OBSERVATION_FAILED（未见非终态） |
| P27 | CONFIRMED | OBSERVATION_FAILURE | UNCERTAIN_TASK_VANISHED | FAILED | 否 | 否 | 否 | 是 | 是 | 否 | 观察得 404（未发取消） |
| P28 | CONFIRMED | DEADLINE | UNCERTAIN_NO_RESPONSE | FAILED | 是 | 否 | 否 | 是 | 是 | 否 | DEADLINE 清理：UNCERTAIN_NO_RESPONSE |
| P29 | CONFIRMED | DEADLINE | UNCERTAIN_TASK_VANISHED | FAILED | 是 | 是 | 否 | 是 | 是 | 否 | DEADLINE 清理：UNCERTAIN_TASK_VANISHED（未见非终态） |
| P30 | CONFIRMED | DEADLINE | TERMINAL_FAILED_OBSERVED | FAILED | 是 | 是 | 否 | 是 | 否 | 否 | DEADLINE 清理：TERMINAL_FAILED_OBSERVED（未见非终态） |
| P31 | CONFIRMED | DEADLINE | TERMINAL_DONE_OBSERVED | FAILED | 是 | 是 | 否 | 是 | 否 | 否 | DEADLINE 清理：TERMINAL_DONE_OBSERVED（未见非终态） |
| P32 | CONFIRMED | DEADLINE | TERMINAL_FAILED_OBSERVED | FAILED | 是 | 是 | 是 | 是 | 否 | 否 | DEADLINE 清理：TERMINAL_FAILED_OBSERVED（见过非终态） |
| P33 | CONFIRMED | DEADLINE | TERMINAL_DONE_OBSERVED | FAILED | 是 | 是 | 是 | 是 | 否 | 否 | DEADLINE 清理：TERMINAL_DONE_OBSERVED（见过非终态） |
| P34 | CONFIRMED | DEADLINE | UNCERTAIN_TASK_VANISHED | FAILED | 是 | 是 | 是 | 是 | 是 | 否 | DEADLINE 清理：UNCERTAIN_TASK_VANISHED（见过非终态） |
| P35 | CONFIRMED | DEADLINE | UNCERTAIN_NOT_TERMINAL | FAILED | 是 | 是 | 是 | 是 | 是 | 否 | DEADLINE 清理：UNCERTAIN_NOT_TERMINAL（见过非终态） |
| P36 | CONFIRMED | DEADLINE | UNCERTAIN_OBSERVATION_FAILED | FAILED | 是 | 是 | 否 | 是 | 是 | 否 | DEADLINE 清理：UNCERTAIN_OBSERVATION_FAILED（未见非终态） |
| P37 | CONFIRMED | ECHO_MISMATCH | UNCERTAIN_NO_RESPONSE | FAILED | 是 | 否 | 否 | 是 | 是 | 否 | ECHO_MISMATCH 清理：UNCERTAIN_NO_RESPONSE |
| P38 | CONFIRMED | ECHO_MISMATCH | UNCERTAIN_TASK_VANISHED | FAILED | 是 | 是 | 否 | 是 | 是 | 否 | ECHO_MISMATCH 清理：UNCERTAIN_TASK_VANISHED（未见非终态） |
| P39 | CONFIRMED | ECHO_MISMATCH | TERMINAL_FAILED_OBSERVED | FAILED | 是 | 是 | 否 | 是 | 否 | 否 | ECHO_MISMATCH 清理：TERMINAL_FAILED_OBSERVED（未见非终态） |
| P40 | CONFIRMED | ECHO_MISMATCH | TERMINAL_DONE_OBSERVED | FAILED | 是 | 是 | 否 | 是 | 否 | 否 | ECHO_MISMATCH 清理：TERMINAL_DONE_OBSERVED（未见非终态） |
| P41 | CONFIRMED | ECHO_MISMATCH | TERMINAL_FAILED_OBSERVED | FAILED | 是 | 是 | 是 | 是 | 否 | 否 | ECHO_MISMATCH 清理：TERMINAL_FAILED_OBSERVED（见过非终态） |
| P42 | CONFIRMED | ECHO_MISMATCH | TERMINAL_DONE_OBSERVED | FAILED | 是 | 是 | 是 | 是 | 否 | 否 | ECHO_MISMATCH 清理：TERMINAL_DONE_OBSERVED（见过非终态） |
| P43 | CONFIRMED | ECHO_MISMATCH | UNCERTAIN_TASK_VANISHED | FAILED | 是 | 是 | 是 | 是 | 是 | 否 | ECHO_MISMATCH 清理：UNCERTAIN_TASK_VANISHED（见过非终态） |
| P44 | CONFIRMED | ECHO_MISMATCH | UNCERTAIN_NOT_TERMINAL | FAILED | 是 | 是 | 是 | 是 | 是 | 否 | ECHO_MISMATCH 清理：UNCERTAIN_NOT_TERMINAL（见过非终态） |
| P45 | CONFIRMED | ECHO_MISMATCH | UNCERTAIN_OBSERVATION_FAILED | FAILED | 是 | 是 | 否 | 是 | 是 | 否 | ECHO_MISMATCH 清理：UNCERTAIN_OBSERVATION_FAILED（未见非终态） |
| P46 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_NO_RESPONSE | CANCELLED | 是 | 否 | 否 | 是 | 是 | 否 | CALLER_CANCEL 清理：UNCERTAIN_NO_RESPONSE |
| P47 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_TASK_VANISHED | CANCELLED | 是 | 是 | 否 | 是 | 是 | 否 | CALLER_CANCEL 清理：UNCERTAIN_TASK_VANISHED（未见非终态） |
| P48 | CONFIRMED | CALLER_CANCEL | TERMINAL_FAILED_OBSERVED | CANCELLED | 是 | 是 | 否 | 是 | 否 | 否 | CALLER_CANCEL 清理：TERMINAL_FAILED_OBSERVED（未见非终态） |
| P49 | CONFIRMED | CALLER_CANCEL | TERMINAL_DONE_OBSERVED | CANCELLED | 是 | 是 | 否 | 是 | 否 | 否 | CALLER_CANCEL 清理：TERMINAL_DONE_OBSERVED（未见非终态） |
| P50 | CONFIRMED | CALLER_CANCEL | TERMINAL_FAILED_OBSERVED | CANCELLED | 是 | 是 | 是 | 是 | 否 | 否 | CALLER_CANCEL 清理：TERMINAL_FAILED_OBSERVED（见过非终态） |
| P51 | CONFIRMED | CALLER_CANCEL | TERMINAL_DONE_OBSERVED | CANCELLED | 是 | 是 | 是 | 是 | 否 | 否 | CALLER_CANCEL 清理：TERMINAL_DONE_OBSERVED（见过非终态） |
| P52 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_TASK_VANISHED | CANCELLED | 是 | 是 | 是 | 是 | 是 | 否 | CALLER_CANCEL 清理：UNCERTAIN_TASK_VANISHED（见过非终态） |
| P53 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_NOT_TERMINAL | CANCELLED | 是 | 是 | 是 | 是 | 是 | 否 | CALLER_CANCEL 清理：UNCERTAIN_NOT_TERMINAL（见过非终态） |
| P54 | CONFIRMED | CALLER_CANCEL | UNCERTAIN_OBSERVATION_FAILED | CANCELLED | 是 | 是 | 否 | 是 | 是 | 否 | CALLER_CANCEL 清理：UNCERTAIN_OBSERVATION_FAILED（未见非终态） |
| P55 | CONFIRMED | INTERNAL_ERROR | UNCERTAIN_NO_RESPONSE | RAISED | 是 | 否 | 否 | 是 | 是 | 否 | INTERNAL_ERROR 清理：UNCERTAIN_NO_RESPONSE |
| P56 | CONFIRMED | INTERNAL_ERROR | UNCERTAIN_TASK_VANISHED | RAISED | 是 | 是 | 否 | 是 | 是 | 否 | INTERNAL_ERROR 清理：UNCERTAIN_TASK_VANISHED（未见非终态） |
| P57 | CONFIRMED | INTERNAL_ERROR | TERMINAL_FAILED_OBSERVED | RAISED | 是 | 是 | 否 | 是 | 否 | 否 | INTERNAL_ERROR 清理：TERMINAL_FAILED_OBSERVED（未见非终态） |
| P58 | CONFIRMED | INTERNAL_ERROR | TERMINAL_DONE_OBSERVED | RAISED | 是 | 是 | 否 | 是 | 否 | 否 | INTERNAL_ERROR 清理：TERMINAL_DONE_OBSERVED（未见非终态） |
| P59 | CONFIRMED | INTERNAL_ERROR | TERMINAL_FAILED_OBSERVED | RAISED | 是 | 是 | 是 | 是 | 否 | 否 | INTERNAL_ERROR 清理：TERMINAL_FAILED_OBSERVED（见过非终态） |
| P60 | CONFIRMED | INTERNAL_ERROR | TERMINAL_DONE_OBSERVED | RAISED | 是 | 是 | 是 | 是 | 否 | 否 | INTERNAL_ERROR 清理：TERMINAL_DONE_OBSERVED（见过非终态） |
| P61 | CONFIRMED | INTERNAL_ERROR | UNCERTAIN_TASK_VANISHED | RAISED | 是 | 是 | 是 | 是 | 是 | 否 | INTERNAL_ERROR 清理：UNCERTAIN_TASK_VANISHED（见过非终态） |
| P62 | CONFIRMED | INTERNAL_ERROR | UNCERTAIN_NOT_TERMINAL | RAISED | 是 | 是 | 是 | 是 | 是 | 否 | INTERNAL_ERROR 清理：UNCERTAIN_NOT_TERMINAL（见过非终态） |
| P63 | CONFIRMED | INTERNAL_ERROR | UNCERTAIN_OBSERVATION_FAILED | RAISED | 是 | 是 | 否 | 是 | 是 | 否 | INTERNAL_ERROR 清理：UNCERTAIN_OBSERVATION_FAILED（未见非终态） |

**证据声明（必须读）**：参考模拟器与谓词**都由同一位 Designer 编写**——`Reference simulator author: Designer`；`Independence: NOT ESTABLISHED`。两者相等只说明它们彼此一致，**不是**独立审查的结论；独立复核者应据本表与下面的字段规则自行复算。

**字段值与边界（复算所需的全部规则；与谓词逐条对应）**：① `begin_event`、`end_event` 为 `int`（排除 `bool`）、`≥ 1`，且 `begin_event < end_event`；② `host_task_id`：仅 `S = CONFIRMED` 时存在，且为 `int ≥ 1`（排除 `bool`），否则为 `None`；③ `task_known_event`：仅 `S = CONFIRMED` 时存在，且 `begin_event < task_known_event < end_event`；④ `cancel_event`：存在 ⇔ `cancel_post_attempted = 是`，且 `task_known_event < cancel_event < end_event`；⑤ `outcome`：存在 ⇔ `R = FAILED`，且为与触发匹配的 `HostFailureKind` 真实成员；⑥ `seq ≥ 1`、`completion_seq ≥ 1`、`engine_index ≥ 1`、`attempt_id == "e{engine_index}-a{seq}"`；⑦ `S = ATTEMPTED` 不得出现在终态记录；⑧ 表中未列出的 `(S, T, C, R, cpa, cf, nt)` 组合一律非法；⑨ `SUCCESS ⇒ metadata_id ≠ None`。

说明：① `S=UNKNOWN` 的取消只有 P05 一种表示，同时保留“创建未知”与“被取消”（`T = CALLER_CANCEL`，`C = UNCERTAIN_SUBMISSION_UNRESOLVED`）；二次取消不产生新状态。② 清理被二次取消打断时，`T` 被取代为 `CALLER_CANCEL`，`R = CANCELLED`；被致命异常打断时 `T = FATAL_BASEEXCEPTION`，`R = RAISED`。③ `INTERNAL_ERROR` 触发的清理若再被二次取消打断，终态是 `CANCELLED`（`T = CALLER_CANCEL`），因此 `INTERNAL_ERROR + CANCELLED` 不合法。④ 提交（`POST`）不受 aggregate deadline 约束，仅受 `request_timeout` 约束，所以 `S=UNKNOWN` 没有 `DEADLINE`。⑤ 取消落在 `POST` 在途期间时不再等待响应（第 10.2 节第 2 条），因此没有“取消后取得 `202` 而变为 CONFIRMED”的路径。⑥ `OBSERVATION_FAILURE` 触发 `HOST_TASK_VANISHED`（观察 404）时**不发送取消**（任务不存在），对应 P27 唯一的 `cpa = 否` 的 `TASK_VANISHED`。

#### 计数口径（精确；R1 / x-03 冻结三个统计域）

```text
Z        : 全生命周期累计状态（在线更新，溢出后权威）
W        : 仅已完成记录的保留窗口（FIFO；溢出后只是窗口）
InFlight : 当前未完成的尝试（BEGUN / ATTEMPTED / CONFIRMED）

对“已完成记录集合 R”（未溢出时 R = W；溢出后 R 只能来自 Z 或完整分段历史）：
submitted_completed     = #{ r in R : S ≠ SUBMISSION_NOT_ATTEMPTED }  = creation_confirmed + creation_unknown
creation_confirmed      = #{ S == CREATION_CONFIRMED }
creation_unknown        = #{ S == CREATION_UNKNOWN }
abandoned_attempts      = #{ T ≠ NONE ∧ S ≠ SUBMISSION_NOT_ATTEMPTED }      每一个的 L3 都是 UNVERIFIED
uncertain_cancellations = #{ C ∈ UNCERTAIN_* }

Z.submitted             = submitted_completed + #{ 在途明细中阶段 ∈ {ATTEMPTED, CONFIRMED} }      （BEGUN 不计）
```

正常 `SUCCESS`、未取消的 `HOST_TASK_FAILED`、`done` 之后的映射失败**绝不**计入 `abandoned_attempts` / `uncertain_cancellations`。**在 `in_flight > 0` 时不能由 `W` 求得全历史 `submitted`**；强制用例：`W = []`、`completed = 0`、`in_flight = 1`、阶段 `ATTEMPTED`、`Z.submitted = 1` 是合法快照（绿），“仅完成记录求和等于 `Z.submitted`”的旧变体必须红（第 20.5 节）。

#### 语义与限制（Design-R1 保留）

* “已发送取消请求”**不等于**“任务记录已终止”，“记录已终止”**也不等于**“执行已停止”。审计、门面文档、HANDOFF 与任何用户可见文字**不得**使用“已停止 / confirmed stopped”措辞，只能写“终态已观察到（TERMINAL_*_OBSERVED）”或“不确定（UNCERTAIN_*）”。
* **晚到写入（late write）不可排除**：除 `NOT_APPLICABLE` / `NOTHING_TO_CANCEL` 之外的每一次放弃 / 取消之后，宿主里该任务的协程仍可能写 Metadata（包括 `FAILED` 已被记录之后）。因此 ① P6 对已放弃的 aggregate **永不使用**其之后写入的 Metadata；② 同号后续重试读到的 `raw` 可能是晚到写入的结果——由第 11.3.4 节“非任务独占”声明覆盖；③ 取消保证（精确 id、请求体不含 `status` / `type`、有界预算、不影响旁观任务）不意味着“宿主上没有遗留执行”，二者不矛盾。
* `TERMINAL_FAILED_OBSERVED` 不区分“因我们取消而 failed”和“恰好自己 failed”。不读 `error` 文本。

### 10.4 语义级取消与“不确定”的暴露

* P4 `preview` 被取消：`CancelledError` 原样传播，**不返回部分 preview**（P4 §20.2）。因此取消结果只能通过**审计快照**观察
  （`AmaneBatchIntegration.audit_snapshot()` 在取消后仍可调用）。
* “cancel before admission”：在任何 worker 被准入之前取消（P4 的 `admission_open()` 保证不再准入）→ 零 `POST`，审计无记录。
* 取消不确定性是**一等输出**：`AmaneHostAuditSnapshot.abandoned_attempts > 0`（L3 未验证）或 `uncertain_cancellations > 0` 或 `creation_unknown > 0` 时，门面文档与 HANDOFF 要求调用方向用户呈现
  “可能仍有未停止的 Amane SCRAPE 任务，且它们仍可能写入 Amane Metadata”。

### 10.5 致命 `BaseException`：F3（同一实例，确定性所有权清理 + 异常引用脱离）与方案 X-NARROW（Design-R5 最终致命异常安全架构修复；**待独立复核；不是 Security PASS**）

**治理状态**：F1（保持身份、保留第三方 traceback 中的凭据）与 F2（新实例）均**未被接受**；Y（只检测）与 Z（改写异常参数）继续 **REJECTED**；**X-NARROW 获授权**（带强制条件，见下）。独立安全复核（Reviewer C）对 R5 草案给出 FAIL，三个必须修复的 finding（R5-C-01 / R5-C-02 / R5-C-03，已被独立确认关闭，本轮不重开）、随后的 R5-EV-01（已独立确认关闭）、以及最新独立复核重开 / 新增的三个 finding（R5-CL-01、R5-GOV-01、R5-NEW-01）与本节的对应修复：

| Finding | 内容 | 修复（本节 / 第 10.2 节） |
|---|---|---|
| R5-C-01 | 致命异常落在 `_transport` 的 `except Exception` 处理体（或 `finally`、try 之后的代码）里时，兄弟 `except (KeyboardInterrupt, …)` 捕获不到，F3 不运行，`Request` 经 P6 栈帧与 `__context__` 可达；公共 client 与 `aggregate` 两条出口都受影响 | **边界所有权**：引用脱离只在**边界帧**的致命处理体里执行，`_transport` 不再有致命处理体；边界切断异常通向它之下全部帧的引用（任何字节码处被打断都一样；已结束的帧随引用计数释放）；见“生命周期设计” |
| R5-C-02 | 链成员“允许名单”只看 `args` / `__dict__` / `__notes__`，看不见内置异常的 C 级槽位（`AttributeError.obj`、`OSError.filename`、`ImportError.path`、`StopIteration.value`…）；审计器 `reach.py` 同样有盲区 | **链一律整条切断**（不再有允许名单）；审计器改用 `gc.get_referents`（`tp_traverse`）覆盖 C 级槽位，并有红绿孪生 |
| R5-C-03 | 外部取消 + 内部 deadline + 内层把 `CancelledError` 转换成普通异常：`task.cancelling() == 1` 但没有 `CancelledError` 再被投递，调用方的取消被吞掉 | 取消归属在**一处**按计数分类（第 10.2 节）；`cancelling() > base` ⇒ 一定存在尚未传播的外部取消 ⇒ 抛出新的 `CancelledError` |
| R5-CL-01 | `frame.clear()` 对**挂起**的生成器 / 协程帧：Python 3.11 / 3.12 上终结该帧并运行其 `finally`（执行了别的任务 / 生成器的清理代码），3.13 / 3.14 上抛 `RuntimeError`。上一版用 `gc.get_referrers` 判断“帧是否仍被存活的协程持有”来避免清理挂起帧——但该判断不可靠（见 R5-GOV-01），本包自己的挂起帧仍被终结 | **确定性所有权清理 + 异常引用脱离**（见“生命周期设计”第 4 条）：F3 生产路径**不访问任何帧**——不 `clear()`、不枚举引用者、不取栈帧；本帧持有的响应数据由拥有它的边界帧自己用 `STORE_FAST` 重绑；然后异常的 `__traceback__` / `__context__` / `__cause__` 一律置 `None`，所有已结束的帧失去最后一个引用，由引用计数连同局部一起释放；挂起的帧（本包的或第三方的）从不被触碰，因此不会有 `finally` 被执行；红 / 绿孪生 `frame_safety.py`（含 `gc.freeze()`）+ Reviewer C 的 `frameclear.py` / `liveness.py` 基线 |
| R5-GOV-01 | 上一版生产实现把 `gc.get_referrers()` 当作“帧是否已结束”的证明。`gc.freeze()`（预 fork 服务器常用的公共 API）把对象移入永久代，`gc.get_referrers` 看不到它们，存活的协程因而不可见，其帧被清理并运行 `finally`；该扫描还向进程内审计钩子暴露帧，且代价随堆大小线性增长 | 生产实现**完全不再使用**对象图枚举：禁止 `gc.get_referrers` / `sys._getframe` / `frame.clear`（及 `gc.collect` / `gc.get_objects` / 全堆扫描等替代）；AST 守卫 `fatal_path_guard.py`（16 个变异全部被抓住，干净片段通过）；旧版在 `gc.freeze()` 下失败（本包挂起帧的 `finally` 被执行、`Request` 仍可达），新版通过 |
| R5-NEW-01 | F3 为了清理帧而调用 `sys._getframe` / `gc.get_referrers`，二者都会触发进程内审计事件，事件参数就是尚未清理的帧——带 `Authorization` 的 `Request` 经 `f_locals` 可达 | F3 不再发出任何此类事件（没有 `sys._getframe`、没有 `gc.*`）；`audit_f3.py` 在公共 client 与 `aggregate` 两条出口上记录**每个**审计事件，要求：由本包代码触发的 `sys._getframe` / `gc.*` 事件为 0，且没有事件的参数能到达带 `Authorization` 的 `Request`；Reviewer C 的 `audit_getframe.py` 原样运行（旧版：两类事件的参数都暴露凭据；新版：不暴露）。验收对象是“P6 不应主动把敏感帧作为新增审计事件参数暴露”，**不是**“审计钩子是否有执行权限”（后者属 B1） |
| R5-EV-01 | 证据工具缺陷：`reach.py` 只有在请求头含测试 canary 时才报告 `Request`——对任何**其它**凭据失明 | 审计器检测**任何**带 `Authorization` 的 `httpx` / `httpcore` `Request` 与 `Response.request`，与令牌值无关（仅证据工具；不改变生产保护范围）；非 canary 正向对照、负向对照、变异（去掉规则必须变红）：`reach_selftest.py` |

**先区分六个概念（不得混为一谈）**

| 概念 | F3 之下的状态 |
|---|---|
| 异常**对象身份** | **保持**：调用方收到的对象 `is` 原始致命异常对象（裸 `raise`；不创建替代实例） |
| 异常**类型** | **保持** |
| 异常**参数**（`args`、`__dict__`、`__notes__`） | **不读取、不修改**；它们由抛出方创建，本包只保证“本包没有新增” |
| **traceback 保真度** | **降低（如实记录）**：第三方帧被移除，只保留本包自己的帧；原始抛出点的文件 / 行号 / 局部变量丢失 |
| 异常**链**（`__cause__` / `__context__`） | **整条切断**（`__cause__` / `__context__` 置 `None`；链成员不被读取、不被修改，也不被清理）；链上的诊断信息丢失（如实记录） |
| **P4 可见的致命行为** | **不变**：同一对象、同一类型，按 Python 的规则传播（`KeyboardInterrupt` / `SystemExit` 离开事件循环；`GeneratorExit` 经 `TaskGroup` 成为 `BaseExceptionGroup` 成员）；F1 基线与 F3 的可观察类别逐项相等（Gate C 的 TaskGroup 对照） |

#### 生命周期设计（R5-C-01）：谁拥有清理

1. **边界帧**：每条公共出口上的每个包内帧——`AmaneHostClient` 的公共方法、`_call`、`AmaneAggregationEngine.aggregate`、门面的公共方法——都是边界。边界帧的**局部变量不持有任何凭据 / `Request` / `Response` / 响应体**（AST 守卫 + 审计，C9）。
2. **`_transport` 没有致命处理体**。它只负责：武装 deadline 定时器、在 `finally` 里撤销（第 10.2 节）、局部重绑。致命异常落在它的任何字节码上（`try` 体、`except Exception` 处理体、`finally` 体、try 之后的分类代码、响应关闭之后）都只是向上传播。
3. **边界的致命处理体长这样（内联，C9）**：

```text
except (KeyboardInterrupt, SystemExit, GeneratorExit) as e:
    body = obj = None                     # （仅 `_call`：本帧持有响应数据的局部由本帧自己重绑。纯 STORE_FAST，没有调用，因此没有检查点）
    try:                                  # 第一条带调用的语句。此前只有 PUSH_EXC_INFO / STORE_FAST，二者不是异步异常的检查点
        _fatal_scrub(e)                   # 三条属性赋值：__traceback__ / __cause__ / __context__ = None。其后的每一个检查点（RESUME / CALL / JUMP_BACKWARD …）都在这个 try 里
    except BaseException as e2:           # 清理器自己的失败，或第二个致命异常
        e.__traceback__ = e.__context__ = e.__cause__ = None      # 内联的纯属性赋值：没有调用，因此没有检查点，对异步异常是原子的
        e2.__traceback__ = e2.__context__ = e2.__cause__ = None
        if not isinstance(e2, Exception):  # 第二个致命异常继续传播（绝不吞掉）；普通异常被丢弃，原致命异常继续
            raise
    raise                                  # 裸 raise：同一个对象
```

4. **`_fatal_scrub(e)` = 确定性所有权清理 + 异常引用脱离（R5-CL-01 / R5-GOV-01 / R5-NEW-01 的最终形式）**：保持原实例；**不读取、不修改** `type`、`args`、`__dict__`、`__notes__`；函数体只有三条属性赋值：`e.__traceback__ = None`、`e.__cause__ = None`、`e.__context__ = None`。
   ① **它不访问任何帧**：不调用 `frame.clear()`，不调用 `sys._getframe`，不调用 `gc.get_referrers` / `gc.get_referents` / `gc.get_objects` / `gc.collect`，不遍历 `tb_next` / `tb_frame`，不判断“帧是否已结束”，也不导入 `gc` / `inspect`（AST 守卫，C8）。因此：挂起的生成器 / 协程帧（本包的或第三方的）从不被触碰，其 `finally` 不会因 F3 而运行，也不会有别的任务的协程被关闭；无论 `gc.freeze()` 是否启用结果都一样；没有 `except RuntimeError` 可言；也不产生任何会把帧交给审计钩子的事件。
   ② **所有权由持有者自己清理**：哪个帧持有敏感数据，就由哪一层边界在致命处理体里用纯 `STORE_FAST` 重绑（`_call` 的 `body` / `obj`；见下面的所有权表）。`_transport`、`_run`、`_cleanup` 不是边界，它们的帧在异常离开边界后没有任何引用（见③），随引用计数一起被释放，其中的 `request` / `response` / `chunks` / `body` / `obj` / `md` 也随之释放。
   ③ **脱离而非清理**：异常是通向帧的**唯一**引用来源（`__traceback__` → `tb_frame`，以及链成员的 `__traceback__`）。把这些引用全部切断后，已结束的帧（`_transport`、`_call`、`_run`、`httpx` / `httpcore` / `anyio` 帧）失去最后一个引用，随其局部一起释放；仍然存活的帧（挂起的协程）由其所有者持有，与本异常无关。**保证的是敏感引用不可达，而不是 traceback 不含本包帧**：实测（`ownership_proof.py`，九个解释器）在设计探针的各注入点上，到达调用方的 traceback 不含 `httpx` / `httpcore` / `anyio` 帧，也不含 `_transport` / `_run` / `_cleanup` 帧；边界处理体里的裸 `raise` 在 `__traceback__` 已为 `None` 时通常不为当前帧重新添加条目。但正常信号可以在边界入口的检查点（例如 `call` / `aggregate` 的入口，处理体尚未建立）到达，此时该边界帧会留在 traceback 里（确定性替身：`ownership_proof.py` 的 BOUNDARY ENTRY 场景；真实信号 fuzz 中也出现过，违例 0）——这是允许的，因为边界帧不持有敏感局部（C9）。因此任何要求“所有真实信号下 traceback 绝对不含任何本包帧”的断言**都被撤销**（它既不是安全要求，也无法对真实信号投递证明）；测试断言的是：可达性审计为 0，且出现在 traceback 里的本包帧只能是边界帧、其局部不含 `Request` / `Response` / 响应体 / token。
   ④ 若一个致命异常在清理期间被另一个致命异常打断，或清理自己失败（探针注入），回退路径与第 3 条代码块相同：内联属性赋值（对两个异常都做），第二个致命异常继续传播，绝不吞掉。
5. **为什么在边界脱离而不是在 `_transport` 里清理**：致命异常可以落在 `_transport` 的任何字节码上（`try` 体、`except Exception` 处理体、`finally` 体、try 之后、响应关闭之后），`_transport` 内部的处理体永远有“落在处理体入口之前”的窗口（R5-C-01）。边界帧在它之上，致命异常抵达边界时 `_transport` 已经结束，边界只需切断引用；这同样适用于异常落在 `_call` 自己的局部赋值之后（`_call` 自己在处理体里重绑 `body` / `obj`）。

#### 各层敏感引用所有权（R5 架构修复；逐层证明）

敏感数据 = 带 `Authorization` 的 `httpx.Request` / `Response.request`、凭据字符串、`Response` 对象、响应体字节及其解析结果。验证对象是**到达调用方的那一个异常对象**（`reach.py` 可达性审计，所有权对象为不透明节点），同时对公共 client 与 `aggregate` 两条出口，`ownership_proof.py` 在每一层持有敏感数据的程序点注入致命异常（`sent` / `loop` / `after_close` / `call` / `after_meta`）并断言：同一实例、`args` 不变、凭据路径 0、响应体 canary 路径 0、异常链为空、致命路径零额外 HTTP I/O、零额外 P6 task、出现在 traceback 里的本包帧（若有）只能是边界帧且其局部不含敏感数据。

| 层 | 持有的敏感数据 | 谁拥有清理 | 处理体 / `finally` / 返回点 / 清理器失败 / 二次致命 |
|---|---|---|---|
| `_transport` | `request`、`response`、`chunks`、`chunk`、`body`（以及 httpx / httpcore 帧中的同一批对象） | **不由它自己清理**（它没有致命处理体）：它的帧在异常离开 `_call` 边界之后无引用，随引用计数释放；正常返回路径上它显式重绑 `request = response = chunks = chunk = None` 再返回（C5a） | 致命异常落在它的任何字节码上都只是向上传播；它自己的 `finally` 只撤销 deadline 定时器（`active[0] = False`、`timer.cancel()`），不持有敏感数据；窗口探针对其每个字节码注入（k = 1、2、3） |
| `_call`（第二边界） | 返回点附近的 `body`（响应体字节）、`obj`（解码结果） | **`_call` 自己**：致命处理体第一组语句 `body = obj = None`（纯 `STORE_FAST`，无调用）；正常路径上 `body = None` 在使用后立即执行 | 处理体里：重绑 → `try: _fatal_scrub(e)` → 内联回退 → 裸 `raise`；`finally` 只做 `active[0] = False`；致命异常落在 `finally` 里时 `_call` 已不持有数据 |
| `Client.call`（公共，第一边界） | 无（仅有调用方传入的参数与 `self`） | 无需清理；处理体只做引用脱离 | 同上；二次致命：内联回退对两个异常都做属性赋值，第二个致命异常继续传播 |
| `Engine._run` / `_cleanup` | `obj`（任务 JSON）、`md`（元数据 JSON）、`terminal_obj` | 不由它们自己清理（不是边界）：帧在 `aggregate` 边界脱离引用后释放 | 窗口探针对 `_run` 每个字节码注入；`after_meta` 程序点由 `ownership_proof.py` 专门验证 |
| `Engine.aggregate`（出口边界） | 无敏感局部（`a` 是账本字典，`number` 是调用方输入） | 无需清理；处理体做引用脱离，再做**幂等**的审计记账（仅当该 attempt 仍在途；记账失败不遮盖致命异常） | 记账失败被丢弃，致命异常继续；`_run` 的 `RETURN` 上落致命时不重复记账 |
| 门面 `AmaneBatchIntegration` | 无（只持有配置、引擎与结果记录；记录不含异常对象，M6-37） | 无需清理；其公共方法的致命处理体与 `aggregate` 的引用脱离形式相同（C9） | **设计要求，探针未建模**：S1 必须用同一组窗口探针与所有权证明在真实门面上重跑（E6-09 / E6-17）；本设计不声称门面已被探针证明 |

**范围声明**：以上所有权证明针对本包的帧与对象。调用方的帧、P4 worker 的帧、被调用方保存的异常不在保护面内。第三方帧在异常离开边界之后只在“仍被其所有者持有”时存活，P6 不触碰它们。
6. **审计记账是幂等的**：`aggregate` 的致命分支只在该 attempt 仍在途时记账，且记账自己的失败不得遮盖致命异常（穷举探针发现：致命异常落在 `_run` 的 `RETURN` 上时，重复记账抛 `KeyError` 取代了致命异常，已修复）。
7. **定时器的武装发生在受 `finally` 保护的 `try` 内部**，且回调受 `active` 标志约束（第 10.2 节）；穷举探针发现并修复了两个窗口：武装与保护之间存在未保护指令；`finally` 内的 seam 先于撤销。

#### 故障模型与证据（R5-C-01；Gate C `window_probe.py`，每个出口 × 每个模型）

* **模型 any**（比 CPython 更强）：异常可在**任一字节码之前**到达。**模型 checkpoint**（CPython 的真实投递点）：只在 eval-breaker 被检查的指令（`RESUME`、`CALL*`、`JUMP_BACKWARD`、`SEND`、`YIELD_VALUE` …）到达。
* **出口**：直接 client 路径与 `aggregate` 路径各两类——请求在传输层失败（`AttributeError` 携带 `obj = Request`）与对真实回环宿主的正常路径（响应对象、响应体循环、响应关闭、轮询、元数据）。
* **k = 1**：对包内每个相关函数的**每一个字节码**注入一个 `KeyboardInterrupt`。**k = 2**：第一个致命异常落在 `try` 体 / `except Exception` 处理体 / `finally` / try 之后 / 响应关闭之后 / `_call` / `_run`，第二个落在其后包内处理代码的**每一个字节码**。**k = 3**：第二个落在清理器内部，第三个落在其后的**每一个字节码**。
* 每次运行后，对**到达调用方的那个异常对象**做独立审计（`reach.py`：帧局部 + `gc` 引用、`args`、`__dict__`、`__notes__`、链、traceback、C 级槽位），并断言：身份（到达的是最后注入的那个）、无额外 P6 task、无“仍然武装且活跃”的 deadline 定时器、无泄漏的定时器取消无辜 task、gc 之后无带 token 的 `Request` / `Response`。
* **红孪生**：对保存下来的 R5 草案（`p6proto_r5_draft.py`）运行同一探针，k = 1 即出现违例（`_transport` 处理体窗口，路径形如 `exc.__traceback__…tb_frame[_transport].f_locals['request']`、`exc.__context__.<C-slot Request>`）；Reviewer C 的原始脚本 `f3_window.py` / `f3_cslots.py` / `race.py` 逐字节保留（SHA-256 见证据包），在 R5 草案上复现三个 finding，在修订版上通过。
* **结论（如实；以运行时证据为界）**：见下面的“B2 异步致命异常投递边界”。**CPython 的真实信号投递**只发生在 eval-breaker 检查点；处理体里的每个检查点都在内联的嵌套 `try` 之内，清理器之外只剩原子的属性赋值。穷举验证覆盖 k = 1、2、3；k > 3 依据这一结构论证，**未穷举**。**调试器 / trace 在任意字节码处注入、数量无界**的假想模型属于 B1 所列的恶意进程内访问（`OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`）：公共 client 路径只有两层边界，探针（`window_probe.py --demo-defeat`）构造了一个具体反例——第一个异常在传输层、第二个落在 `_call` 处理体入口的非检查点指令、第三个落在 `call` 处理体入口——此时凭据经 `__context__` 到达调用方；增加边界层数只会抬高所需异常数量。该反例**需要** `sys.settrace` 之类的主动 trace 注入，普通信号做不到，因此不作为产品缺陷，也**不**为此改变进程级 `SIGINT` 策略（屏蔽 `SIGINT` 的候选方案不采用）。

#### B1 进程内信任边界（Governance 裁决；`OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`）

**P6 不需要对同一进程内的恶意代码隐藏凭据——但不得用 B1 / B2 掩盖 P6 自己新增的泄漏或副作用**（例如 F3 为清理而调用 `sys._getframe` / `gc.get_referrers` 并把帧交给审计钩子，或终结别的任务的协程；这两件事已被 R5-GOV-01 / R5-NEW-01 禁止）。 下列手段属于 B1 的“恶意进程内访问”，不在 P6 的保护面内：`gc.get_objects()` / `gc.get_referrers()` 与帧内省、猴子补丁、私有属性改写（例如 `client._http`）、主动的 trace / profile 插桩（`sys.settrace` / `sys.setprofile`）、任意异常注入。**B1 不排除**：正常的公共 API 使用、受支持的 `httpx` / `httpcore` / `anyio` 路径、P6 自身产生的泄漏、普通操作系统信号投递、正常的 asyncio 取消——这些仍然全部在保护面内并有证据。

* **四个植入凭据用例**（见下表）**全部保留，不标 X-NARROW PASS**；它们要求主动改写进程内状态（安装 `event_hooks` 需要私有属性 `_http` 或进程级补丁；`fatal_f3.py` 逐项实际执行），因此标 `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`，**实际可达性如实记录**：`exc.args[0]` / `exc.args[0].headers` / `exc.__dict__['leaked_request']` / `exc.__notes__[0]` 仍可达，F3 不改写抛出方的字段。
* **同进程的 `gc` 内省**（Reviewer C 的 `inproc_reach.py`，3.11.0 … 3.14.7 全部为 `True`）：无需任何私有 API，只用 `gc.get_objects()`，另一个任务就能找到飞行中的带 `Authorization` 的 `Request`。这是 B1 所列手段，记录为实际可达性，**不是缺陷，也不是 PASS**。

#### B2 异步致命异常投递边界

* 区分 **CPython 的正常信号投递**（`KeyboardInterrupt` 等经 eval-breaker 在检查点 `RESUME` / `CALL*` / `JUMP_BACKWARD` / `SEND` / `YIELD_VALUE` 到达）与**调试器 / trace 在任意字节码处注入**。P6 不要求抵御无限制的恶意 trace（B1）；**不排除**正常的 `KeyboardInterrupt` 与反复的真实信号。
* 合同**只声明有运行时证据支持的保证**：（i）检查点模型下 k = 1、2、3 的穷举 / 分层验证，每个出口 × 每个解释器；（ii）任一字节码模型下 k = 1 穷举、k = 2 / 3 的分层或抽样验证（含上面的反例边界）；（iii）Reviewer C 的真实信号 fuzz（`fuzz_fatal.py`，无 `settrace`；失败路径 / 正常路径）：失败路径（传输层抛 `AttributeError(obj=Request)`）6 个解释器（3.11.0 / 3.11.9 / 3.12.10 / 3.13.0 / 3.13.9 / 3.14.7）× 300 次 = 1800 次，共有 1795 个 `KeyboardInterrupt` 到达调用方，其中 1729 个经过 P6 的致命处理体，**全部 1795 个**都经 `reach.py` 审计，违例 0；正常路径 6 × 150 = 900 次，898 个到达调用方，其中 225 个经过 P6 的致命处理体，全部审计，违例 0。**说明**：Reviewer C 的原始 `fuzz_fatal.py` 只审计 traceback 含本包帧的异常；引用脱离之后到达调用方的 traceback 不含任何本包帧，它的“经过 P6”指标塌缩、审计变得空洞，所以证据包里**同时**保留原版的未改动运行（`real_signal_fuzz_original_unchanged/`，违例 0，仅作旁证）和派生版 `fuzz_fatal_v2.py`（以 `_fatal_scrub` 调用计数判定“经过 P6”、审计每一个到达调用方的异常；`real_signal_fuzz_v2/`）。各有一次因 harness 自己的 `KeyboardInterrupt` 落在其 `try` 之外而以 130 退出，已重跑并记录。**数千次真实信号 fuzz 不是绝对证明**，只是上面结构论证与穷举验证的旁证。
* **不改变进程级 `SIGINT` 策略**：P6 不安装信号处理器，不屏蔽信号，不调用 `signal.pthread_sigmask`。

#### 帧安全、GOV-01、NEW-01 与审计完备性证据（R5-CL-01 / R5-GOV-01 / R5-NEW-01 / R5-EV-01；Gate C）

* **`frame_safety.py`**（15 项；`python frame_safety.py types5.py pred5.py mapcode.py [模块]`；环境变量 `P6FREEZE=1` 在每次净化前执行 `gc.freeze()`）：已结束的普通帧、正在执行的帧、挂起的生成器帧、挂起的协程帧、第三方异常链上的挂起生成器、**本包拥有的**挂起帧（直接调用与经公共 client / `aggregate` 两条出口的端到端用例）、P6 已结束帧；断言：无 `finally` 被执行、生成器 / 协程仍可恢复、无不相关协程被关闭、到达调用方的异常经审计无带凭据的 `Request` / token 可达路径、异常身份 / `args` 不变、零额外 P6 task、生产路径静态守卫 0 违例、源码无 `except RuntimeError`。**红孪生**为上一版（`gc.get_referrers` 判定存活）：正常 GC 状态下仅静态守卫失败；**`gc.freeze()` 下**本包挂起帧的 `finally` 被执行、凭据路径 = 2（直接调用与两条出口均然），静态守卫失败。新版在两种 GC 状态下 15/15。
* **Reviewer C 的独立反例**（原文件保留 SHA-256，原样运行）：`frameclear.py`（`clear()` 对挂起帧的逐解释器行为）、`liveness.py`（基线 / `gc.freeze()` CE1 / 审计钩子 CE2 / 堆规模 CE3：旧版 CE1 本包挂起协程的 `finally` 被执行，CE2 钩子看到 `Request`；新版全部无副作用、无事件、耗时 0 ms）、`audit_getframe.py`（旧版两类事件均暴露凭据；新版不暴露）。派生版 `audit_f3.py` 记录**每个**审计事件并按触发者归因（`asyncio` / `httpx` 等第三方代码自己调用 `sys._getframe` 不算 P6）：公共 client 与 `aggregate` 两条出口上，本包触发的 `sys._getframe` / `gc.*` 事件 = 0，暴露带 `Authorization` 的 `Request` 的事件 = 0。
* **`ownership_proof.py`**（9 项 × 九个解释器）：见上面的逐层所有权表；变异（致命处理体不脱离，`FATAL_MODE=F1`）使 9 项全部变红（凭据路径 4、响应体 canary 路径 5 等）。
* **`fatal_path_guard.py`**：生产路径静态守卫；`--selftest` 含 16 个变异（`gc.get_referrers`、别名 `gc`、`from gc import`、`gc.get_objects`、`gc.collect`、`sys._getframe`、`from sys import _getframe`、`getattr(sys,'_getframe')`、`frame.clear()`、`fr.clear()`、`x.f_back.clear()`、`inspect`、`except RuntimeError`、元组形式的 `except RuntimeError`、裸 `except`、`cr_frame`）全部被抓住，干净片段通过；对设计探针 0 违例，对上一版 14 个违例。
* **`reach_selftest.py`**（10 项）：对**非 canary** 凭据的正向对照（`args`、`__dict__`、`Response.request`、`AttributeError.obj` / `OSError.filename` C 槽位、traceback 帧局部、`httpcore.Request`），一个无 `Authorization` 的 `Request` 作负向对照，以及变异——关掉“任何带 `Authorization`”规则使 ≥ 5 个正向对照变红；Reviewer C 的 `ev01.py` 作回归原样运行。

#### X-NARROW（治理授权，强制条件逐条落实；现仅用于独立载荷对照）

**本轮裁决**：四个植入凭据用例**不得**标为 X-NARROW PASS——它们的凭据取自当前 P6 请求，条件 2 不满足；它们依赖主动的进程内篡改，按 B1 标 `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`，实际可达性已记录。X-NARROW 只保留给**独立载荷对照**（进入 P6 之前就存在于致命异常自身字段里的内容）。

**区分**：*外部预存的独立载荷*（进入 P6 执行路径前已存在于致命异常自身字段中的内容）与 *P6 来源或受支持运行时来源的凭据暴露*。只有前者可以不修改地保留。强制条件与落实：

| 条件 | 落实与证据 |
|---|---|
| 1 字段内容在进入 P6 相关路径前已经存在 | 独立载荷对照用例：`SystemExit('shutdown requested', {'code': 3})`——F3 不触碰，审计为 0 |
| 2 不是当前 P6 请求的 `Authorization`、`Request`、`Response`、响应体的引用或派生 | **四个植入用例都不满足本条**（凭据取自当前 P6 请求）——因此**不能按载荷豁免**，只能分析其注入点是否属于受支持的执行路径 |
| 3 不是受支持的 httpx / httpcore / anyio 运行路径产生或填充的敏感字段 | 受支持依赖矩阵（见下）的静态扫描：三个包里没有任何位置把请求 / 响应对象放进致命异常的 `args` / `__dict__` / `__notes__`（`anyio` 仅有两处无参 `raise KeyboardInterrupt`）；矩阵守卫 |
| 4 P6 没有新增敏感引用路径，没有记录 / 序列化 | 审计器（到达调用方的对象）+ `HostAttemptRecord` 不含异常对象 |
| 5 P6 捕获后不向 `args` / `__dict__` / `__notes__` 添加内容 | 抛出时与到达时的逐项快照相等；C7（永不 `add_note`） |
| 6 X 不适用于敏感 traceback、异常链、链成员的 C 级槽位或 P6 栈帧 | traceback 与链被脱离、C 级槽位随链切断、P6 帧随引用计数释放且从不被清理或枚举（上面的穷举证据与逐层所有权证明） |

**四个原始植入用例（保留，逐项说明；不重命名为 PASS）**：

| 用例 | Payload origin | Credential ownership | Injection point | Supported / unsupported boundary | Actual reachability | Expected security verdict |
|---|---|---|---|---|---|---|
| `args` 含 token 文本 | 收到当前 P6 `Request` 的钩子代码把其 `Authorization` 复制进异常 | 当前 P6 请求的凭据（**条件 2 不满足**） | `httpx` `event_hooks['request']`（需要私有属性 `_http` 或进程级补丁） | **不受支持**：P6 没有任何 API 安装钩子，`AmaneHostClient` 不暴露其 httpx 客户端（公共名只有 `aclose`、`call`；无构造参数；Gate 机检） | `exc.args[0]`（str）仍可达 | **`OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`**（B1；不是 PASS，不是 X-NARROW PASS；可达性保留；F3 不得改写参数） |
| `args` 含带 `Authorization` 的 `Request` | 钩子代码把当前 `Request` 放进 `SystemExit(request)` | 当前 P6 `Request` 本身（条件 2 不满足） | 同上 | 不受支持（同上） | `exc.args[0]` → `Request` → `Headers` 可达 | 同上 |
| `__dict__` 含带凭据的 `Request` | 钩子代码把当前 `Request` 挂到异常实例 | 同上 | 同上 | 不受支持（同上） | `exc.__dict__['leaked_request']` 可达 | 同上 |
| `__notes__` 含 token 文本 | 钩子代码 `add_note()` 当前 `Authorization` | 当前凭据（条件 2 不满足） | 同上 | 不受支持（同上） | `exc.__notes__[0]` 可达 | 同上 |

**独立证据表明这四个用例需要主动的进程内篡改**：`fatal_f3.py` 通过 `client._http.event_hooks = …`（私有属性）安装每个钩子，并断言 `AmaneHostClient` 的公共名只有 `aclose` 与各公共方法、没有任何公共属性暴露 httpx 客户端 / 传输 / auth；无构造参数可注入钩子。**这一归类依赖于该分析**：若将来出现任何受支持的方式让外部代码在 P6 的请求路径上运行（钩子、可注入传输、可替换客户端），这四个用例必须立即重新归类为 BLOCKED。

**受支持依赖矩阵（版本矩阵验证，不依赖 `httpx>=0.27,<0.28` 这一个范围）**：已验证 `httpx==0.27.2`、`httpcore==1.0.9`、`anyio==4.15.1`、`h11==0.16.0`、`sniffio==1.3.1`（`idna==3.20`、`certifi==2026.7.22` 仅作记录）。`dep_matrix.py` 对这些包做 AST 扫描：`raise KeyboardInterrupt / SystemExit / GeneratorExit`、直接继承 `BaseException` 的类、`add_note` 调用——全部包共 2 处无参 `raise KeyboardInterrupt`（`anyio/_backends/_asyncio.py`），0 处涉及 request / response / headers / auth。**S1 必须加入矩阵守卫测试**：安装的版本不在已验证矩阵内时，X-NARROW 的“受支持运行时”声明为 `UNVERIFIED`（并重新运行扫描与 Gate C），而不是默认继承。本设计不修改 `pyproject.toml`。

#### 如实记录的代价与残余

* **诊断能力损失**：致命异常原始抛出点（第三方帧、钩子帧的文件 / 行号 / 局部）与整条异常链不再可见（审计记录里附带“抛出点摘要”的缓解候选需要扩展记录与谓词，未采用）。
* **抛出方放入致命异常自身字段的凭据**：独立载荷按 X-NARROW 保留；取自当前 P6 请求的凭据（四个植入用例）= `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`，均不改写，可达性保留。
* **本包以外的帧**（P4 worker、调用方）不在保护面内。
* **帧处理的副作用（R5-CL-01 / R5-GOV-01）**：F3 不清理、不枚举、不终结任何帧，所以不会执行别的任务或生成器的 `finally`，也不依赖 GC 状态；代价是 traceback 保真度进一步降低——到达调用方的致命异常的 traceback 不含第三方帧，也不含 `_transport` / `_run` / `_cleanup` 帧，至多留下无敏感局部的边界帧（不保证完全没有本包帧）。仍被第三方对象持有的第三方帧由其所有者管理，不在保护面内。
* **结论状态**：F3 + 边界所有权 + 帧安全清理 + 完备审计器在设计探针上 **IMPLEMENTED CANDIDATE**（Python 3.11.0 / 3.11.1 / 3.11.2 / 3.11.3 / 3.11.9 / 3.12.10 / 3.13.0 / 3.13.9 / 3.14.7；`httpx 0.27.2`）；这**不是**独立安全复核的 PASS。实现阶段（S1）必须在真实 P6 代码上重跑同一组探针（E6-09 / E6-17）。若独立复核认为不满足，则按治理要求报告 `BLOCKED — SECURITY AUTHORITY` 并给出最小架构调整候选，**不得**退回 F1 / F2。

### 10.6 R5-11：注入式 `transport=` 与取消吞没（方案 A：APPROVED FOR DESIGN REVISION ONLY）

**治理裁决（Governance Security Ruling）**：方案 A 被授权**仅用于设计修订**——允许从新开发的 P6 公共 API 移除任意 `transport=` 注入；故障注入改为使用真实回环 HTTP / TCP 服务与故障代理。**这不是**原有安全要求的豁免，也不是 Independent PASS。不可降低的要求：E6-05 / E6-09 / E6-17 的全部强制能力保留；覆盖首次 / 二次 / 多次取消、响应头停滞、流中断、连接拒绝、丢失 202、401 / 403 / 5xx、非法 JSON、异常路径、凭据 canary（见第 22.5 节“故障覆盖矩阵”）；保留生产 `httpx` 的有界取消与“无 P6 detached task”；**不修改**已 CLOSED 的 P4 / P5 的 `MockTransport` 或其它注入接口；`transport=` 相关的公开签名、测试清单、Mutation、Master / Contract / Construction Plan 必须一致。

**事实**：R4 的 `AmaneHostClient(..., transport=<任意 httpx.AsyncBaseTransport>)` 允许注入一个吞掉 `CancelledError` 的传输；实测（S9）清理被拖过预算约 **2.2 s**——P6 无法在不创建第二个 task 的前提下抢占一个不配合取消的协程。

**公共 API 兼容性（逐一核对 P6 的全部构造 / 注入 / 验收接口）**

| 接口 | R4 | R5（本草案） | 说明 |
|---|---|---|---|
| `AmaneHostClient.__init__` | `(config, *, transport=None)` | `(config)` | 撤销 `transport=`；client 在内部创建 `httpx.AsyncClient`（`trust_env=False`、`follow_redirects=False`、固定 `Limits` / `Timeout`、拒绝一切 cookie） |
| `AmaneAggregationEngine.__init__` | `(client, *, _clock, _sleep)` | `(client)` | **衍生变更（待确认）**：可注入的 `_sleep` 同样可以吞掉 `CancelledError` 而破坏有界取消，`_clock` 可以让 deadline 判断失真；二者与 `transport=` 属同一类风险。确定性单测改用真实回环宿主 + 短间隔（`poll_interval ≥ 0.05 s`、`aggregate_deadline ≥ 1 s`） |
| `AmaneBatchIntegration.__init__` | `(host, image_client, library_root, *, …, transport=None)` | 去掉 `transport=` | `image_client` 属于调用方（P4 约定，`ImageHttpClient` 是 P4 CLOSED 的接缝，不改动）；它只服务 P4 的图片获取阶段，不进入 P6 的宿主 I/O 路径 |
| `AmaneHostConfig` 字段 | 8 个字段 | 不变 | 没有 `verify_tls` / `proxy` / `transport` / `client` 旋钮（第 8.2 节） |
| P4 / P5 的 `MockTransport` 与 `HttpxImageClient(transport=…)` | CLOSED | **不动** | 仅 P4 自有的图片测试接缝 |

**为什么该反例不能再通过 P6 公共入口触发（记录，不是删除）**：构造面上没有任何参数能提供传输、HTTP 客户端、mounts、event hooks、sleep 或 clock（Gate C 的 API 守卫对合同签名文本与原型签名做机检，并有 R4 签名的红孪生）。反例此后只能通过**进程级猴子补丁** `httpx.AsyncHTTPTransport` 复现——这等价于修改被信任的库，不属于 P6 公共入口的威胁模型；Gate C 把该复现作为**信息项**记录（不计入通过标准）：补丁一个吞取消的 `handle_async_request` 时，清理 aggregate 在约 2.8 s 后结束（取消预算 0.5 s），即反例仍然真实，只是不可经 P6 入口到达。

**仍然可达的路径（逐一验证，故障全部来自真实回环套接字）**：连接拒绝、响应头停滞、响应头 / 响应体 slowloris（总 deadline，第 10.2 节）、流中断（截断 / RST）、丢失 `202`（经代理丢弃响应）、`401` / `403` / `429` / `500` / `503` / `404`、非法 JSON、结构错误的 JSON、超大响应、观察期 `503`、元数据 JSON 非法、取消请求本身被 `401` / `500` / 非法 JSON / RST 回应、连续 4 次取消。每个用例同时断言 token 与响应体 canary 不出现在任何异常文本、审计记录或存活的 `Request` / `Response` 对象里。

**方案 B（保留 `transport=` 并证明吞取消不能突破预算）**：**拒绝**——不可满足（S9 的 2.2 s 是反例；抢占需要第二个 task，被治理否决）。

**状态**：R5-11 = **DESIGN UPDATED**（方案 A 已按治理授权写入设计）；独立复核尚未进行。若独立复核或后续裁决否决方案 A，必须回到本节重新设计，**不得**通过缩小范围或减少测试通过。

---

## 11. Host → Core 桥（冻结；fail closed）

### 11.1 构造什么

* 成功路径：一个合法的 `SourceResult(source_id="ffcc.fc2-metadata", status=SUCCESS, metadata=<NormalizedMetadata>, elapsed_ms=<测量值>)`，
  再构造 `AggregationResult(number, status=SUCCESS, metadata, source_results=(那一个 SourceResult,), contributing_source_ids=("ffcc.fc2-metadata",),
  conflicts=(), disabled_source_ids=(), elapsed_ms, source_execution_traces=())`。
* `source boundary ID` 恒为 `PLUGIN_SOURCE_ID = "ffcc.fc2-metadata"`（常量；测试与 `adapters/amane/fc2_amane_adapter/_settings.py: PLUGIN_ID` 逐字对账）。
* `source_execution_traces` 为空（“纯合并、无执行”，Core 合同允许）：P6 没有运行任何 Core source execution，不得伪造 trace。
* **P6 永远不产生 `AggregateStatus.PARTIAL`**：`PARTIAL` 要求至少一个 SourceResult 是运行性失败，而 P6 只有一个 SourceResult；跨过 P5 边界后，
  内部 JavDB / fc2db_net / av123 的逐来源状态已经丢失，**不得重建**（第 15 节）。因此 `ItemWarning.METADATA_PARTIAL` 在 P6 流程中不会出现。

### 11.2 映射入口：校验顺序与唯一错误分类（唯一规范；Design-R4 / R4-01 重写）

R3 的 11.2 把“号等价”放在严格键集合与 `PluginRaw` reader 之前，导致缺插件键、插件值为 `null` / 列表、缺 `number`、`number` 非字符串时在解引用处抛出 `KeyError` / `TypeError` / `AttributeError`（Gate A 在 R3 文字顺序上 16 个用例里有 7 个没有单一分类），并且“混合来源 + 插件号错误”会被错误地归为 `NUMBER_MISMATCH`。本节的代码块是**映射入口的唯一规范性定义**（其它章节、Master Plan、Construction Plan 只引用它）；预提交验证从本文件抽取并执行它。

**冻结顺序**：1 任务终态与 `result` 有效性 → 2 任务侧归属 → 3 `HostMetadata` 外层结构 → 4 严格 `raw` 来源键集合 → 5 严格 `PluginRaw` 结构 → 6 号等价 → 7 确定性映射（**含 P5 I22 URL 卫生与精确 `dropped_url_count`，R5-08**） → 8 最低成功。**任何字段在其前置校验通过之前不得被解引用**；`normalize_fc2_number` 只对已确认是 `str` 的值调用；整个入口对任何输入都不得抛出异常。

**错误优先级（由顺序唯一决定）**：缺插件键 / 只有外来来源 / 混合 / 语言后缀 / 未知来源键 ⇒ `HOST_ATTRIBUTION_FOREIGN`；键集合恰好是插件、但值为 `null` / 列表 / 缺 `number` / `number` 非字符串 / 任一字段类型非法 ⇒ `HOST_METADATA_CONTRACT`；结构全部合法而 `number` 不等价或无法识别 ⇒ `HOST_METADATA_NUMBER_MISMATCH`；其后才是 `HOST_METADATA_BELOW_MINIMUM`。代码里的失败名省略 `HOST_` 前缀。

```python gate:map_host_result
from urllib.parse import urlsplit

PLUGIN_SOURCE_ID = "ffcc.fc2-metadata"


def is_clean_http_url(value):
    """P5 I22（adapters/amane/fc2_amane_adapter/_outcome.py）的同义判定：带 host 的绝对 http(s) URL；无控制字符、无首尾空白。只判定，不改写。"""
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in value):
        return False
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        return False
    return parts.scheme.lower() in ("http", "https") and bool(host)


def map_host_result(task, metadata_response, canonical, normalize):
    """第 11.2 节的唯一映射入口。返回 ("OK", fields, dropped_url_count) 或 ("FAIL", HostFailureKind 名, 0)；任何输入都不得抛出异常。
    task：GET /api/tasks/{id} 的 JSON（已通过 HostTask 严格 reader，status 为 done）；
    metadata_response：GET /api/metadata/{id} 的 JSON `.metadata`（已通过 JSON 结构预扫描）；
    normalize(str) -> canonical | None（Core normalize_fc2_number 的包装；只对 str 调用）。"""
    def fail(kind):
        return ("FAIL", kind, 0)

    def is_int(x):                                   # int 且排除 bool
        return type(x) is int

    def is_str_list(x):
        return isinstance(x, list) and all(isinstance(i, str) for i in x)

    # 1. 任务终态与 result 有效性
    if not isinstance(task, dict):
        return fail("RESULT_INVALID")
    if task.get("status") == "failed":
        return fail("TASK_FAILED")
    result = task.get("result")
    if not (task.get("status") == "done" and isinstance(result, dict) and is_int(result.get("metadata_id")) and result["metadata_id"] >= 1
            and isinstance(result.get("field_sources"), dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in result["field_sources"].items())
            and isinstance(result.get("failed_sites"), list)):
        return fail("RESULT_INVALID")
    # 2. 任务侧归属（必要条件）
    fs = result["field_sources"]
    if not (fs and "title" in fs and all(v == PLUGIN_SOURCE_ID for v in fs.values())):
        return fail("ATTRIBUTION_FOREIGN")
    # 3. HostMetadata 外层结构（先于任何字段解引用）
    md = metadata_response
    if not (isinstance(md, dict) and is_int(md.get("id")) and isinstance(md.get("number"), str) and isinstance(md.get("raw"), dict)):
        return fail("SCHEMA_INVALID")
    raw = md["raw"]
    # 4. 严格 raw 来源键集合
    if set(raw.keys()) != {PLUGIN_SOURCE_ID}:
        return fail("ATTRIBUTION_FOREIGN")
    # 5. 严格 PluginRaw 结构（此后才允许读取其字段）
    pr = raw[PLUGIN_SOURCE_ID]
    if not isinstance(pr, dict):
        return fail("METADATA_CONTRACT")
    if not isinstance(pr.get("number"), str):
        return fail("METADATA_CONTRACT")
    for key in ("title", "studio", "publisher", "release", "plot"):
        if key not in pr or not (pr[key] is None or isinstance(pr[key], str)):
            return fail("METADATA_CONTRACT")
    if "runtime" not in pr or not (pr["runtime"] is None or (is_int(pr["runtime"]) and pr["runtime"] >= 0)):
        return fail("METADATA_CONTRACT")
    for key in ("tags", "poster_urls", "thumb_urls", "extrafanart"):
        if key not in pr or not is_str_list(pr[key]):
            return fail("METADATA_CONTRACT")
    actors = pr.get("actors")
    if not isinstance(actors, list):
        return fail("METADATA_CONTRACT")
    names = []
    for item in actors:
        name = item if isinstance(item, str) else (item.get("name") if isinstance(item, dict) else None)
        if not (isinstance(name, str) and name.strip()):
            return fail("METADATA_CONTRACT")
        names.append(name)
    # 6. 号等价：持久化号与 raw 内号都必须被识别且等于请求的 canonical（只对 str 调用 normalize）
    if normalize(md["number"]) != canonical or normalize(pr["number"]) != canonical:
        return fail("METADATA_NUMBER_MISMATCH")
    # 7. 确定性映射：URL 卫生（P5 I22）只删除不合规项，保序、不改写、不去重；被删数量精确计入 dropped_url_count
    dropped = 0
    cleaned = {}
    for key in ("poster_urls", "thumb_urls", "extrafanart"):
        kept = [u for u in pr[key] if is_clean_http_url(u)]
        dropped += len(pr[key]) - len(kept)
        cleaned[key] = kept
    fields = {"number": canonical, "title": pr["title"], "studio": pr["studio"], "publisher": pr["publisher"], "release": pr["release"],
              "plot": pr["plot"], "runtime": pr["runtime"], "actors": names, "tags": list(pr["tags"]),
              "poster_urls": cleaned["poster_urls"], "thumb_urls": cleaned["thumb_urls"], "extrafanart": cleaned["extrafanart"]}
    # 8. 最低成功
    if not (isinstance(fields["title"], str) and fields["title"].strip()):
        return fail("METADATA_BELOW_MINIMUM")
    return ("OK", fields, dropped)
```

**第 7 步的 URL 卫生（R5-08）**：`is_clean_http_url`（代码块内）与 P5 `adapters/amane/fc2_amane_adapter/_outcome.py` 的 I22 同义——带 host 的绝对 `http` / `https` URL，无控制字符（含 DEL）、无首尾空白；**只判定，不改写**；三个列表的被删元素总数是 `dropped_url_count`。非 `str` 元素仍是第 5 步的 `METADATA_CONTRACT`（结构违规），而“全是非法 URL 的列表”只是被过滤为空（不是失败）。Gate A 的 URL 用例：空白 / 控制字符 / 无 host / 空串 / scheme 相对，混合合法与非法 URL 的精确计数，三个列表合计，全部合法时为 0，以及“去掉 URL 过滤”变异必须被检出。

说明：失败种类到 Core `SourceStatus` / `SourceErrorKind` 的映射见第 12.1 节；第 9.4 节的“`GET /metadata`”步骤返回 `404` ⇒ `HOST_METADATA_MISSING`、其它传输 / 状态码失败按第 8.4 节映射，都发生在进入本入口**之前**。第 8 步对应 DIFF-P6-02（v0.18.0 可能 `done` 但标量全空）。

### 11.3 字段内容的来源证明（Design-R2 / R2-01 重写；冻结唯一一套方案）

#### 11.3.0 为什么 Design-R1 的证据链不成立

Design-R1 用 `E1`（任务 `field_sources`）、`E2`（持久化 `field_sources`）、`E3`（未被锁定）与 `R0`（`updated_at ≤ finished_at`）判定“字段可归属于插件”。它们**全都是来源标签或时间戳，没有一个读取字段的实际值**，因此无法证明持久化展示列里的内容来自插件。明确反例：

```text
SCRAPE 写入 title=A（field_sources[title] = ffcc.fc2-metadata）
  → 用户 PATCH 把 title 改成 B（PATCH 不改 field_sources；v0.15.0 无字段锁，v0.18.0 在用户解锁之后也不再受保护）
  → SCRAPE 任务被标记 done（updated_at 仍 ≤ finished_at：写入发生在标记 done 之前）
  → P6 GET Metadata → E1/E2/E3/R0 全部成立 → 错误地把 B 归属于插件
```

再叠加一条时间戳条件无法消除这类竞争，且 R0 受墙钟回拨与时间戳精度影响。**本版撤销 E1/E2/E3/R0 作为内容归属证据的地位。**

#### 11.3.1 任务侧证据（必要条件，不充分）

`result.field_sources` 必须满足：非空；`"title" ∈ keys`；`所有 values == "ffcc.fc2-metadata"`。任何其它站点 id 出现，或 `title` 没有归属，说明 route 不独占或任务没有用插件解析出标题 → `HOST_ATTRIBUTION_FOREIGN`（整条目 fail closed）。它只证明“**这个任务的 route 内是插件在贡献**”，**不**证明持久化展示列里现在的内容是什么。

#### 11.3.2 冻结方案：从插件的原始记录 `raw["ffcc.fc2-metadata"]` 派生字段值（方案 A）

**设计期对两个 pinned release 的源码核查结果**（`v0.15.0` = `45dff215…`，`v0.18.0` = `0a8a731d…`；S1 第 0 步用行为测试复核）：

| 事实 | 依据 | 两个版本 |
|---|---|---|
| `raw` 是 `dict[SourceKey, dict]`，值为各来源的 `MediaMetadata.model_dump()`；`SourceKey` 为站点 id（多语言来源才带 `:lang` 后缀，插件不是多语言来源）。因此插件的原始记录在精确键 `ffcc.fc2-metadata` 之下 | `aggregate/engine.py`：`raw = {k: v.model_dump() for k, v in state.fetched.items() if v is not None}` | 相同 |
| `MediaMetadata` 字段：`number, title, actors[{name,gender}], studio, publisher, release(str), runtime, tags, series, plot, poster_urls, thumb_urls, trailer_urls, score, external_id, source_url, directors, extrafanart` | `crawlers/models.py` | 相同（v0.18.0 仅调整 `SearchQuery` 内部字段） |
| `raw` 由 SCRAPE 在 `upsert_metadata(..., raw=result.raw)` 中与展示列**同一次写入** | `handlers/scrape.py` | 相同 |
| `raw` 取自本次任务的抓取：`use_cache=[]` ⇒ `CacheKind.metadata ∉ use_cache` ⇒ 不读 DB 快照，每个来源重新抓取 | `handlers/scrape.py`：`use_metadata_cache = CacheKind.metadata in payload.use_cache` | 相同 |
| 翻译、FacetRule 规范化、Resource 物化、字段清洗**只作用于 `result.metadata` / 展示列**，不改写 `raw` | `handlers/scrape.py` 先取 `result.raw` 后翻译 / 物化；`apply_facet_rules_to_metadata` 作用于 Metadata 列 | 相同 |
| 公开 `PATCH /api/metadata/{id}` **不能**写 `raw`：`PartialMetadata` 的 `ignore_fields` 含 `raw`、`field_sources`（v0.18.0 另含 `locked_fields`），路由只提交模型字段 | `api/models/metadata.py`、`api/routes/metadata.py` | 相同 |
| 公开 merge 端点只**读取** `raw` 去改写展示列与 `field_sources` | `aggregate/merge.py: compute_merge_updates` | 相同 |
| 并发的同号 SCRAPE 会整体替换 `raw`（与展示列一起） | `upsert_metadata` | 相同 |
| `GET /api/metadata/{id}` 的 `MetadataResponse.raw` 返回该字典 | `api/models/metadata.py` | 相同 |

**冻结规则**：

1. `NormalizedMetadata` 的每一个字段值**只**来自 `raw["ffcc.fc2-metadata"]`（经第 11.3.3 节严格 reader 与第 11.4 节确定性映射）。**持久化展示列（`title` / `actors` / `tags` / `poster_urls` …）不参与内容输出**，用户的 PATCH、字段锁、merge 选择、翻译、FacetRule、Resource 物化对输出**没有影响**。
2. 持久化记录只用于三件事：① `number` 等价校验（第 11.2 节代码块第 6 步）；② 展示 `title` 与 `raw` 的 `title` 是否不同的**审计信号** `display_title_diverged`（只进入审计，不影响语义输出，不 fail）；③ 可选的新鲜度提示 `timestamp_relation`（11.3.4，非门禁）。持久化 `field_sources` / `locked_fields` 不再被读取，也不再作为证据。
3. **严格键集合（Design-R3 / R3-01）**：成功的前提是 `set(raw.keys()) == {"ffcc.fc2-metadata"}`。`raw` 缺少插件键（route 不含插件、只有外来站点的记录、旧版本遗留）、**插件与外来来源并存**、带语言后缀的键（如 `…:zh`）、任何未知来源键 → `HOST_ATTRIBUTION_FOREIGN`（统一失败种类）；键集合恰好是插件、但该键的值结构非法 → `HOST_METADATA_CONTRACT`。**这是对“独占来源”前提 H6-1 的验收，不是声称插件字段 A 本身来自外来站点**：混合记录里即使插件那一份是合法的，整条也 fail closed。**不得**回退去读展示列，也不得改读其它 `raw` 键；不得恢复 E1/E2/E3/R0 作为内容证明。
4. **放弃的宿主后处理语义（显式声明，不静默）**：LLM 翻译结果、FacetRule 对演员 / 标签的规范化、Resource 物化与海报裁剪后的内部 URL、用户手工编辑、merge 选择。P6 的输出是**插件的原始数据**（已经过 P5 自己的 I22 URL 卫生），而不是 Amane 展示库里“最终呈现”的版本；二者在用户配置了上述功能或手工编辑过时可以不同，这是有意的、写入 L6-06 / L6-18 的取舍。**保留**的语义：插件在 Core 聚合之后给出的全部可映射字段。
5. 不采用“方案 B（持久化展示值与 raw 逐值比较）”的理由：翻译、FacetRule、物化都会合法地改变展示值，要判定“合法转换”必须枚举一个无界的变换集合，无法在公开 API 内验证；比较失败时只能二选一（拒绝或排除），都会让用户的正常配置导致大面积失败。方案 A 的前提（`raw` 不可被公开 PATCH 改写）已由源码核查支持。

#### 11.3.3 `PluginRaw` 严格 reader（`_wire.py`；解析 `raw["ffcc.fc2-metadata"]`）

必需键：`number: str`；`title: str | None`；`actors: list`，元素为 `str` 或 `{"name": str, ...}`（`name` 必须是非空白 `str`；`gender` 等其它键忽略）；`studio / publisher / release / plot: str | None`；`runtime: int | None`（非 `bool`，非负）；`tags: list[str]`；`poster_urls / thumb_urls / extrafanart: list[str]`。其余键（`series`、`trailer_urls`、`score`、`external_id`、`source_url`、`directors` 及未知键）忽略且不保留。任一必需键缺失 / 类型不符 → `HOST_METADATA_CONTRACT`（不猜测、不修复、不部分接受）。列表元素个数与整体结构受第 8.4 节 `MAX_JSON_*` 约束。

#### 11.3.4 保证范围与不可证明的部分（诚实声明；写入 HANDOFF 与 L6-18）

区分两种性质：

```text
插件来源的字段内容   —— 可以支持：输出值完全由 raw["ffcc.fc2-metadata"] 派生，而 raw 不能被公开 PATCH / 字段锁 / merge 改写
当前任务独占产生的内容 —— 不可证明：宿主 Metadata 是按番号唯一的共享记录
```

P6 **声称**：读取那一刻的 `raw["ffcc.fc2-metadata"]` 里的值，经确定性映射得到输出；任务 route 内只有插件（11.3.1）；输出不含任何来自用户展示列的值。P6 **不声称**：① 该 `raw` 一定来自刚完成的这个任务——并发的同号插件 SCRAPE（含遗留孤儿任务）可能在任务完成后整体替换 `raw`，内容仍是插件的一次独立抓取（`use_cache=[]` 的任务总是重新抓取，但他人的任务不一定），证据上无法与本任务区分；② Amane 的 `raw` 与插件 Core 输出逐字节相同——这是 S1 第 0 步用确定性上游夹具核对的事实，核对失败 ⇒ U6-6；③ 防住对 Amane 数据库的直接篡改或 Amane 自身缺陷（公开 API 之外）。

`timestamp_relation`（审计，非门禁；Design-R3 / R3-02）：它**只是**对两个时间戳字符串**数值与解析状态**的比较标签——**不是**“记录确实被 / 没有被修改过”的事实。旧名 `UNMODIFIED_SINCE_TASK` / `MODIFIED_AFTER_TASK` 暗示了无法证明的事实，已一次性重命名（公共 API、合同、证据、计划同步）：

| 值 | 唯一判定规则（只看这两个字符串） |
|---|---|
| `UPDATED_AFTER_FINISHED` | `updated_at` 与任务 `finished_at` 都存在、可被严格 ISO-8601 解析、时区属性一致，且 `updated_at > finished_at` |
| `UPDATED_NOT_AFTER_FINISHED` | 同样可比，且 `updated_at ≤ finished_at`（**包括相等**）。它**不排除**“实际上更晚发生的写入”因墙钟回拨或同一时刻精度而得到 `≤` |
| `INDETERMINATE` | 任一时间戳缺失 / 不可解析 / 时区属性不一致 / 精度不一致而无法比较 |

计算**不依赖**事件的真实先后顺序；**时间戳顺序不是因果证明**。它不得充当字段来源证明，也不得改变语义输出。墙钟回拨、时间戳精度、任务内部“写入 → 标 done”之间的极短间隔内他人的写入，均不可分辨。

### 11.4 字段映射表（冻结；守卫测试穷举 `PluginRaw` 与 `NormalizedMetadata` 的字段集合）

| `NormalizedMetadata` 字段 | 来源（`raw["ffcc.fc2-metadata"]`） | 规则 |
|---|---|---|
| `number` | 请求的 canonical | 固定；`raw.number` 与持久化 `number` 须等价（第 11.2 节代码块第 6 步） |
| `title` | `title` | 原样；`None` / 空白 → 第 8 步失败 |
| `studio` / `publisher` / `release` / `plot` | 同名 | `str \| None` 原样（`release` 已被 Amane 规范为 `YYYY-MM-DD` 或空；其合法性由 P4 NFO 渲染负责） |
| `runtime` | `runtime` | `int \| None`，负数或 `bool` → `HOST_METADATA_CONTRACT` |
| `actors` | `actors[*]` 的 `name`（或字符串元素本身） | 保持顺序；去除 `gender` |
| `tags` | `tags` | 保持顺序；元素必须是 `str` |
| `poster_urls` / `thumb_urls` / `extrafanart` | 同名 | 仅保留“干净的绝对 http(s) URL”（有 host、无控制字符、无首尾空白；与 P5 I22 规则同义，测试逐样本对账）；**被剔除的数量记入审计 `dropped_url_count`**，不静默。**该过滤与计数发生在 `map_host_result` 第 7 步（R5-08；第 11.2 节代码块）**，返回值是 `("OK", fields, dropped_url_count)`；只删除不合规项、保序、不改写、不去重；`dropped_url_count` 只统计 `PluginRaw` 三个 URL 列表里被删的元素个数（宿主展示列的裁剪 / 物化不进入，R5-09） |
| `fanart_urls` | — | 空元组（Amane 无此概念，P5 同） |
| `source_urls` / `external_ids` | — | **恒为空**：P6 不重建来源 provenance，NFO 渲染器也不读取它们（`raw` 里的 `source_url` / `external_id` 不映射） |
| `field_sources` | 派生 | 对每个**非空**的已映射字段 `f`：`{f: ("ffcc.fc2-metadata",)}`（值必须 ⊆ `contributing_source_ids`，P4-C9 诊断校验要求）；内容确实来自插件的原始记录，所以该标签现在有值级证据 |
| （其余 `MediaMetadata` 字段与全部宿主展示列）`series` / `directors` / `trailer_urls` / `score` / `external_id` / `source_url` / `locked_fields` / `field_sources` / `files` / 时间戳 / `id` | — | **不映射**；`metadata_id`、`display_title_diverged`、`timestamp_relation` 仅进入审计 |

* 容器类型不对（例如 `actors` 不是 list）= schema 违规 → fail closed；元素级的 URL 卫生是确定性过滤（并计数），不是失败。
* 映射是**纯函数**：同样的 `PluginRaw` 总得到同样的 `NormalizedMetadata`；不读取时钟、随机数、环境、持久化展示列。

### 11.5 宿主配置与用户编辑**不**流入结果（诚实声明）

因为输出只来自插件的原始记录（11.3.2 规则 1、4）：用户的 Amane 翻译、FacetRule、Resource 物化、手工编辑、字段锁和 merge 选择**都不会**出现在 P6 的结果里。若用户期望“Amane 里编辑后的标题”进入 NFO，P6-C1 不支持（记入 L6-06）。`display_title_diverged` 审计信号让调用方知道展示列与插件原始标题不同。验收宿主仍使用无翻译、无 FacetRule、禁止物化的配置，使展示列与 `raw` 可逐字段对账（用于独立 oracle 的交叉验证，而不是内容来源）。

---

## 12. 失败映射（冻结；全部基于结构化信号）

### 12.1 `HostFailureKind` → Core 结构化失败（唯一映射表）

所有失败都构造 `FAILED AggregationResult`：`metadata=None`，`source_results=(SourceResult(source_id="ffcc.fc2-metadata", status, None, elapsed_ms, error_kind,
error_detail),)`，`contributing_source_ids=()`。`error_detail` 是**封闭词汇**：`"amane host: " + <HostFailureKind.value>`，绝不含 URL / 宿主文本 / token / 任务 id。

| `HostFailureKind` | 结构化触发 | `SourceStatus` | `SourceErrorKind` |
|---|---|---|---|
| `HOST_TIMEOUT` | `httpx.TimeoutException`（含 Connect / Read / Write / Pool Timeout） | `NETWORK_ERROR` | `TIMEOUT` |
| `HOST_CONNECTION` | `httpx.ConnectError`（含 DNS / 拒绝连接 / TLS 握手与证书失败） | `NETWORK_ERROR` | `CONNECTION_ERROR` |
| `HOST_NETWORK` | 其它 `httpx.TransportError` / `httpx.StreamError` / `httpx.DecodingError` / `httpx.TooManyRedirects` | `NETWORK_ERROR` | `NETWORK_ERROR` |
| `HOST_AUTH_REJECTED` | HTTP `401` / `403` | `BLOCKED` | `BLOCKED` |
| `HOST_RATE_LIMITED` | HTTP `429` | `RATE_LIMITED` | `RATE_LIMITED` |
| `HOST_SERVER_ERROR` | HTTP `5xx` | `INVALID_RESPONSE` | `HTTP_SERVER_ERROR` |
| `HOST_HTTP_UNEXPECTED` | 其它 `4xx` / `3xx` / `1xx` / 非预期 `2xx` | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_RESPONSE_TOO_LARGE` | 响应体超过 `MAX_RESPONSE_BYTES` | `INVALID_RESPONSE` | `RESPONSE_TOO_LARGE` |
| `HOST_RESPONSE_TOO_COMPLEX` | 字节数未超限，但 JSON 结构超过 `MAX_JSON_DEPTH` / `MAX_JSON_NODES` / `MAX_JSON_COLLECTION_ITEMS`（第 8.4 节预扫描） | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_SCHEMA_INVALID` | 非 JSON / 严格 reader 违规 / echo 校验失败 / `json.loads` 的 `RecursionError`（纵深防御） | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_TASK_VANISHED` | 观察时 `404`（任务被用户 / 宿主删除） | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_TASK_FAILED` | 观察到终态 `failed`（P6 未发出取消） | `INVALID_RESPONSE` | `ADAPTER_EXCEPTION` |
| `HOST_DEADLINE` | `aggregate_deadline_seconds` 到期（随后有界清理） | `NETWORK_ERROR` | `SOURCE_DEADLINE` |
| `HOST_RESULT_INVALID` | `done` 但 `result` 缺失 / 缺 `metadata_id` / 类型非法 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_ATTRIBUTION_FOREIGN` | **内容来源无法证明属于插件**：任务侧 `field_sources` 含其它站点或缺 `title`；`raw` 的键集合不是恰好 `{ffcc.fc2-metadata}`（缺失 / 只有外来 / 混合 / 语言后缀 / 未知键，第 11.3 节）。名称沿用，语义是“归属不可证明”，不只是“有外来站点” | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_MISSING` | `GET /metadata/{id}` → `404` | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_NUMBER_MISMATCH` | 第 11.2 节第 5 步 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_CONTRACT` | `PluginRaw` 结构非法 / 字段类型 / 构造 `NormalizedMetadata` 被拒 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_BELOW_MINIMUM` | 不满足 minimum success | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |

* 每个 `(SourceStatus, SourceErrorKind)` 配对都在 Core 的 `ALLOWED_ERROR_KINDS` 内（测试穷举验证）。
* **无法证明的细分类一律不猜**：例如无法区分“番号在所有来源都不存在”与“来源故障”（宿主只给 `failed` + 文本），统一为 `HOST_TASK_FAILED`；P6 从不产生
  `NOT_FOUND`。
* **不存在**基于子串 / 正则 / 日志 / 异常消息的分支（AST 守卫：控制流中不得出现对 `error` / `detail` / `str(exc)` / `exc.args` 的比较或匹配）。
* 非 `Exception` 的 `BaseException` 不被映射，保持 P4 致命语义；P6 自身的编程错误（`AmaneBatchContractError`）作为普通 `Exception` 抛出，
  由 P4 隔离为 `METADATA_ENGINE_FAILURE`（`error_type` = 类名），并仍执行有界清理。

---

## 13. 重试所有权（冻结：eligibility 归 P6，执行 / 调度 / 并发归 P4）

### 13.1 三层重试的归属

| 层 | 所有者 | P6-C1 的态度 |
|---|---|---|
| 宿主 `WebClient` 的传输级重试（插件向来源站点发请求时） | Amane / P5 已冻结 | 不触碰；P6 不感知 |
| Core 语义级来源重试 | **disabled**（P5 冻结：`RetryPolicy.no_retry()`） | 不触碰 |
| 条目级重试：**哪些**上一轮 METADATA 阶段失败的条目有资格进入一次新的显式重试轮次（eligibility / subset selection） | **P6 门面**（纯函数，13.3） | 见 13.3 |
| 条目级重试：**真正再次运行**元数据获取、planning、图片、NFO、预检及其并发预算 | **P4 `BatchOrchestrator` + `BatchScheduler`**（唯一执行者） | 见 13.2 |
| `POST /api/tasks` 的重试 | **无人**（永不重试） | 第 9.2 节 |
| 观察 `GET` 的有界重复 | engine（只重复幂等观察，不重复工作） | 第 9.3 节 |
| Amane `POST /tasks/batch` 的 `retry` / `delete` | **永不使用** | 第 7.2 节 |

冻结（Design-R1 / R1-02 重写）：**一次 P6 aggregate 最多发送一次 `POST /api/tasks`；`POST` 永不自动重试。** 旧稿“一次尝试 = 恰好一个新任务”已撤销：尝试次数（0 或 1 次 `POST`）与宿主实际创建的任务数（0、1 或未知）是两件事，由 `SubmissionState`（第 9.2 节）区分。`CREATION_UNKNOWN` 永不被折算为 0 或 1，也不得成为自动重新提交的理由。

### 13.2 设计期发现 F-1：P4 `preview_retry` 在“禁止 execute”的 Phase 6 中不可用

`BatchOrchestrator.preview_retry(previous, *, scope=None)` 的 `previous` 必须是一个**完整的 `BatchExecutionResult`**（`retry.py` 步骤 2
“exact complete previous result”，其 `RetryMaterial` / `retry_kind` / `result_id` 注册全部来自 `execute`）。而 Phase 6 的安全不变量是**绝不调用
`execute`**（第 19 节）。用 `execute(preview, selection=frozenset())` 绕过会违反该不变量的字面（并且会消费 preview），伪造 `BatchExecutionResult`
则是重建 CLOSED 模型——两者都被禁止。

**冻结裁决（ownership 拆成两个、互不重叠：P6 拥有 retry eligibility / failed-subset selection；P4 拥有 retry execution / scheduling / concurrency）**：失败子集重试 = 对失败条目的**原始 `DiscoveredMediaItem`** 再调用一次同一个
`BatchOrchestrator.preview(subset)`。

* P6 **只做子集选择**（一个纯函数，输入是上一轮已有的 `ItemPreview`），不运行任何 scheduler、不重试、不循环。
* 真正重新执行元数据获取、planning、图片、NFO、预检的仍然是 P4 `preview`；并发预算仍然是 P4 `BatchScheduler`。
* 不修改 P4。不引入第二套 scheduler。不使用 `preview_retry` / `merge_retry` / `RetryMaterial`（它们只对 `execute` 之后的结果有意义；Phase 7 引入 `execute` 后沿用 P4 原有机制）。

### 13.3 `AmaneBatchIntegration.retry_failed(previous) -> AmaneBatchPreview`

1. 调用顺序见第 9.5 节：`previous` 校验 → 子集选择 → worker preflight → `await orchestrator.preview(subset)`。P4 的 busy claim 只发生在 `preview` 入口，其拒绝原样传播；P6 不新增锁，也**不**声称“busy 优先于本节的参数 / 子集错误”（第 9.5 节）。
2. `previous` 必须是 `type(previous) is AmaneBatchPreview`，且最新一轮的 `library_root` / `output_policy` / `image_policy` 与门面一致，否则
   `AmaneBatchRetryError(FOREIGN_PREVIEW)`。
3. **可重试集合 R**（纯函数，按原始下标升序）：最新视图中，`ItemPreview.state is UNPREPARED` 且 `issue.stage is METADATA` 且
   `issue.reason ∈ {METADATA_UNAVAILABLE, METADATA_ENGINE_FAILURE}` 的条目。
   * 成功条目（READY / BLOCKED / 其它阶段的 UNPREPARED）**不会**被重跑：它们的元数据是确定的，重取不会改变 planning / 冲突 / 预检结论。
   * 图片候选级部分失败是 P4 的**警告**（`IMAGE_CANDIDATE_FAILURES` 等），不是失败；P6-C1 不重试它们（L6-09）。
4. `R` 为空 → `AmaneBatchRetryError(NO_RETRYABLE_ITEMS)`（不创建空轮次）。`generation + 1 > MAX_RETRY_ROUNDS (16)` → `AmaneBatchRetryError(ROUND_LIMIT)`。
5. 执行 `await orchestrator.preview([原始 DiscoveredMediaItem for i in R])` → 新一轮 `AmaneBatchRound(generation=k, origin_indices=R, preview=…)`。
6. 返回**新的** `AmaneBatchPreview`（`rounds + (新轮次,)`）；`previous` 不被修改。

* P6 不维护“已重试”注册表（无全局可变状态）；同一 `previous` 可被重试多次，每次都是调用方显式的新操作。**没有自动重试循环。**
* 宿主任务账本期望（real-host 证据 E6-13）：按第 9.2 节第 6 条与第 14.4 节对账——任务数由调用脚本的实际操作历史决定；永不为成功条目新增任务（mutation M6-07，成功条目不会被 `retry_failed` 选中）；含 `CREATION_UNKNOWN` 的番号只断言上下界。
* 对上一轮属于 `CREATION_UNKNOWN` 的条目，`retry_failed` 不会自动放行或阻止：它是调用方显式发起的新 aggregate，新 `POST` 可能与遗留的未知任务并存；调用方可用 `audit_snapshot().creation_unknown` 知情（第 9.2 节第 5 条）。

### 13.4 跨轮冲突（Design-R1 / R1-06 新增；撤销旧的“成功条目与重试子集不可能冲突”断言）

旧稿断言“重试子集与成功条目之间不可能存在冲突”。该断言被 CLOSED 测试证伪：P4 Phase B 以 `(device, inode)` 与目标目录检测冲突，**不同番号可以对应同一个 hardlink 源文件**（`tests/phase4_acceptance/test_p4_acceptance_safety.py::test_s10_in_batch_conflicts_block_every_member_and_select_no_winner`，S-10 / SI-10：两个不同番号共享一个 hardlink 源文件，在 Phase B 以 `duplicate_source_in_batch` 被发现）。单独重试失败子集时，P4 的单轮 `preview` 只看见子集，**看不见**前一轮已经 READY 的条目；前轮的 READY 与新轮的 READY 因此可能形成跨轮冲突，而没有任何一轮的 `BatchPreview` 会报告它。冻结：

* 每个 `BatchPreview` 的 READY / 冲突结论**只对其本轮输入集合有效**。P6 **不**提供跨轮的全局 READY / 冲突安全保证，也不新增 filesystem executor 或跨轮冲突检测器。
* 多轮 `AmaneBatchPreview` **不是**一个全局可执行的 preview；汇总必须区分逐轮计数与可被证明的全局状态（第 20.4 节：`ready_round_local`、`cross_round_verified`、逐轮计数），**不得**把各轮 READY 相加后当作全局安全 READY。
* 仅当 `rounds == 1` 时，该唯一一轮的结论覆盖全部输入条目，`cross_round_verified = True`；`rounds > 1` 时恒为 `False`，包括主轮里未被重试的 READY 条目（它们可能与重试轮的 READY 条目冲突）。
* Phase 7 若要跨轮执行，**必须**对合并范围重新验证源文件身份（device / inode）与目标冲突；这是 Phase 7 必须理解的已知局限（L6-16、第 19.3 节）。
* 证据：E6-19 用该 CLOSED S-10 hardlink 反例构造“前轮 READY + 重试轮 READY 实为同一源文件”，断言汇总**不**声称 `cross_round_verified`；孪生：单轮同样输入时 P4 报告冲突。

---

## 14. 并发合同（冻结）

1. **跨条目并发的唯一所有者是 P4 `BatchScheduler`**（`OrchestrationConfig.metadata.max_in_flight_items = M`，缺省 4，范围 1..64）。
   P6 没有信号量 / 线程池 / worker 池 / `asyncio.gather` / `TaskGroup` / `create_task` / `asyncio.shield`——**没有任何例外**（清理在 aggregate 自己的 task 里内联执行，第 10.2 节）。
2. **每个 aggregate 最多发送一次 `POST /api/tasks`，且同一时刻最多等待一个宿主 SCRAPE 任务。** 一个 aggregate 不 fan-out 多个宿主任务，也不会在任何失败 / `CREATION_UNKNOWN` 之后自动再提交（第 9.2 节）。
3. **三个独立集合（Design-R2 / R2-04；不得混为一谈）**：

   ```text
   A  = P6 当前活跃的 aggregate 尝试（引擎 in_flight：入口 +1，finally -1；含正在 ABANDONING 清理的 aggregate）
   K  = P6 当前正在等待的、id 已知的宿主任务：K(t) = { attempt | task_known_event 已发生 ∧ end_event 尚未发生 }（H4 → aggregate 返回 / 抛出；含观察、清理轮询与收尾）
   H  = 与本批番号关联的全部宿主任务，包括已放弃、CREATION_UNKNOWN 遗留的孤儿任务
   ```

   **冻结的不等式**：`|A| ≤ M`；`|K| ≤ |A|`。**不要求、也不保证** `|H| ≤ M`：遗留的孤儿任务仍可能在宿主上 `queued` / `running`（第 4 条）。
4. **请求账本模型（唯一规范；Design-R4 / R4-03、R4-04、R4-05）**

   *4.1 标识*：`attempt_id = "e{engine_index}-a{seq}"`（第 10.3.2 节；`seq` 稠密、`engine_index` 进程内唯一）。该 aggregate 的**全部**宿主请求（submit / observe / cancel / metadata）都携带 `X-FFCC-Attempt: <attempt_id>`；该头不改变任何请求体键集，宿主忽略，P6 不据此做控制。`attempt_id` 的唯一性靠 `seq` 稠密递增保证：分配时断言 `seq == last_seq + 1`，所以不需要保存全部历史 id，**审计溢出后也不可能复用 id**。

   *4.2 已知 id 的四个事件（不得混用）*：`H1` 宿主创建任务（不可直接观察）；`H2` 代理转发并记录宿主的 `202 + task_id`；`H3` 代理把该 `202` 完整写给 P6 的连接（响应丢弃 / 截断则没有）；`H4` P6 收到完整响应并通过 `202` + 严格 reader（审计 `task_known_event`）。只有 `H4` 使 attempt 成为 `CREATION_CONFIRMED` 并进入 `K`；`H2 ≠ H4`。**H3 已送达而 H4 缺席（R5-03）是合法状态**：代理已把 `202` 写给 P6，但 P6 在 H4 之前被取消 / 致命 / 严格 reader 拒绝；此时 `S = CREATION_UNKNOWN`（`host_task_id = None`），P6 **不得**据 H3 向该 id 发送任何后续请求（H3 单独**永不**授权取消——P6 看不到该 id，也不能从代理账本读取它）；H3 已送达而 H4 缺席时，`cancel_post_attempted` 必须为否，代理账本里该 `attempt_id` 在 `POST /api/tasks` 之后不得出现任何请求（O2-4）。`K` 的进入 = `H4`，退出 = aggregate 返回 / 抛出之前的 `end_event`（取消请求得到 HTTP 响应**不是**退出事件，清理轮询期间仍在 `K` 与 `A` 里）。
   **H3 不证明 P6 收到了可接受的响应（R1 / x-02）**：代理在 P6 超时离开**之后**才写入的 `202`（代理账本标 `late`：写入时客户端连接已关闭 / 正在关闭）、写入后连接被重置、写入后 P6 读超时或响应中断，都是 `H2 = TRUE, H3 = TRUE, H4 = FALSE`。此时合法的 P6 结果是 `S = CREATION_UNKNOWN`、`outcome ∈ {TIMEOUT, CONNECTION, NETWORK}`（P6 自己看到的传输失败）、**没有任何后续请求**。`late` 的 `202` 既不能证明 P6 读到并拒绝过一个 body（拒绝类 outcome ⇒ 红），更不能构成 H4（`CREATION_CONFIRMED` ⇒ 红）。P6 不得伪造 H4，不得向代理索取未知 `task_id` 补救，不得自动重复 `POST`，`UNKNOWN` 之后不得发送该 task 的 observe / cancel / metadata 请求。

   *4.3 证据来源及其作用域*（互不替代）：
   | 来源 | 持有者 | 内容 | 作用域 |
   |---|---|---|---|
   | `Z` 累计状态 | P6（O(1) 内存，第 20.5 节） | 精确的全生命周期计数与峰值 | 全历史，**自报告** |
   | `W` 保留窗口 | P6（≤ `MAX_AUDIT_RECORDS` 条 `HostAttemptRecord`） | 最近的完整记录 | 仅窗口，**自报告** |
   | `L` 代理账本 | 测试工具（故障代理） | 每个请求的 `(attempt_id, 方法, 路径, 请求体键集与号 / ids, 状态)` 与 `forwarded` / `delivered` 事件；连接级 `accepted` / `request_bytes` | 全历史（工具侧可分段落盘），**独立事实** |
   | `Hs` 调用脚本历史 | 测试工具 | 脚本自己发起的每次 `preview` / `retry_failed` 及其包含的番号 | 全历史，**独立事实** |
   | `Mf` 注入清单 | 测试工具 | 脚本声明的故障注入（如“该 attempt 的 `POST` 在抵达代理前被取消 / 致命”） | 全历史，**独立事实** |

   *4.4 对账规则（O2；`Z` / `W` 只用于被 `L` / `Hs` / `Mf` 约束的一方）*：
   * **O2-1** `L` 中每个 `attempt_id` 至多一个 `POST /api/tasks`（单个 aggregate 自动重复提交 ⇒ 红）。
   * **O2-2** 对每个番号 `N`：`L` 中请求体含 `N` 的 `POST` 总数 `≤ calls(N)`（`Hs`）。用于发现“用不同 `attempt_id` 隐藏第二次提交”和“`attempt_id` 被复用”。
   * **O2-3（归属按身份，不按水位；R1 / x-04）** `L` 中每个有 `POST` 的 `attempt_id` 必须按**身份**找到归属：(a) 它是一条已保存的记录（`W` 内，或测试工具在丢弃前取走并保存的记录，按 `attempt_id` 匹配）；或 (b) 它尚在 `in_flight_detail` 且阶段 ∈ `{ATTEMPTED, CONFIRMED}`（阶段为 `BEGUN` 而代理已看到该 attempt 的 `POST` ⇒ `Z` 落后于线路 ⇒ 红）。其它情形：`attempt_id` 格式非法、`seq > snapshot.last_seq`（从未分配的 id）、外来 `engine_index` 且保存的历史完整 ⇒ 红；保存的历史**不完整**（记录在被取走前已被丢弃）⇒ `NOT_VERIFIED`——证据缺口，**不得**静默忽略该 `POST`，也**不得**由任何序号水位推断某个 `seq` 已被证明归属。**两个序号空间不得混用**：`seq` = 准入 / 开始顺序（决定 `attempt_id`）；`completion_seq` = 完成顺序（决定保留窗口与收集器游标）；`highest_dropped_completion_seq` 属于 `completion_seq` 空间，**不能**当作 `seq` 的水位使用（R5 的 `seq` 水位字段已删除）。强制用例：`seq = 2` 先完成（`completion_seq = 1`）、`seq = 1` 后完成（`completion_seq = 2`），随后超过 `MAX_AUDIT_RECORDS = 20000` 条完成记录并发生 FIFO 丢弃：丢弃前已被独立收集器保存的历史可继续验证（绿）；历史缺失只报告 `NOT_VERIFIED`。
   * **O2-4（H3 / H4 时序矩阵；R1 / x-02）** 对每条已保存记录，按 `S` 与 P6 的 `outcome` 对照代理账本（`late` = 代理写入时客户端已离开）：
     * `S = NOT_ATTEMPTED` ⇒ `POST` 数为 0。
     * `S = CREATION_CONFIRMED` ⇒ 恰好一个 `POST`，其 `202` 已 `delivered`、**不是 `late`**、`task_id == host_task_id`（H4 不得由代理的迟到写入伪造）。
     * `S = CREATION_UNKNOWN` 且 `POST` 数为 0：只在 (a) `outcome ∈ {TIMEOUT, CONNECTION, NETWORK}`（请求在抵达代理前失败），或 (b) `terminal ∈ {CANCELLED, RAISED}` 且 `outcome is None` 且 `Mf` 声明了该 attempt 的 pre-proxy 注入时成立；其它“0”⇒ 红（丢失的 `POST` 不得被伪装成取消）。
     * `S = CREATION_UNKNOWN` 且 `POST` 数为 1：(i) 响应未送达（未转发 / 仅 `forwarded`，孤儿 H2）：`outcome ∈ {TIMEOUT, CONNECTION, NETWORK}`，或取消 / 致命（`outcome is None`）；(ii) `202` 已 `delivered`（**H3 = 真，H4 = 假**）：`outcome ∈ {TIMEOUT, CONNECTION, NETWORK}` 合法（`late` 写入、写入后重置、写入后读超时 / 响应中断）；`outcome ∈ {SCHEMA_INVALID, RESPONSE_TOO_LARGE, RESPONSE_TOO_COMPLEX}` 仅当该 `202` 不是 `late`（P6 必须读到 body 才能拒绝它）；取消 / 致命（`outcome is None`）合法；`AUTH_REJECTED` / `RATE_LIMITED` / `SERVER_ERROR` / `HTTP_UNEXPECTED` 与已送达的 `202` 矛盾 ⇒ 红；(iii) 代理转发 / 送达的是非 `202`：`outcome` 必须与状态一致（`401` / `403` ⇒ `AUTH_REJECTED`，`429` ⇒ `RATE_LIMITED`，`≥ 500` ⇒ `SERVER_ERROR`，其它 ⇒ `HTTP_UNEXPECTED`），或 `late` 时传输类。
     * **所有 `UNKNOWN` 情形**：该 `attempt_id` 在 `POST` 之后没有任何后续请求；`L` 中**任何** attempt 的请求都不得引用只出现在 `UNKNOWN` attempt 的 `202` 里的 `task_id`（P6 不得从代理账本补救未知 id；H2 / H3 都不授权请求）；不得自动重复 `POST`（O2-1）。
   * **O2-5（取消 / 终态见证对账；R1 / x-06）** 自报告布尔值必须由独立的网络事实支持（以代理自己的 tick 顺序为准）：
     * `cancel_post_attempted = True` ⇒ 代理观察到该 attempt 的取消 `POST /api/tasks/batch` 恰 1 次，请求体键集恰为 `{action, task_ids}`、`action == "cancel"`、`task_ids == [host_task_id]`；观察到 0 次只允许 `C ∈ {UNCERTAIN_NO_RESPONSE（请求在抵达代理前失败）, UNCERTAIN_CLEANUP_INTERRUPTED}` 且 `cancel_request_confirmed = False`；`cancel_post_attempted = False` ⇒ `L` 中没有该 attempt 的取消 `POST`，也不得有确认 / 观察 / 终态声明。
     * `cancel_request_confirmed = True` ⇒ 该取消 `POST` 有 `delivered` 的 `200`（**不是 `late`**），响应的 `task_ids == [host_task_id]`；反过来，有效 `200` 已送达而 P6 记 `False` ⇒ 红。
     * `C ∈ {TERMINAL_FAILED_OBSERVED, TERMINAL_DONE_OBSERVED}` ⇒ 在取消确认**之后**（代理 tick 严格晚于取消 `200` 的 `delivered`）存在该 attempt **自己 `host_task_id`** 的 `GET /api/tasks/<id>`，已 `delivered`、非 `late`、`200`，响应的 `status` 恰为对应终态。缺少该 `GET`、`GET` 用了别的 id、`GET` 返回 `running`、`GET` 早于确认 ⇒ 红。
     * `C = UNCERTAIN_NOT_TERMINAL` ⇒ 确认后存在 `delivered` 的 `GET` 返回 `queued` / `running`，且之后没有返回终态的 `GET`；`C = UNCERTAIN_OBSERVATION_FAILED` ⇒ 确认后没有任何 `delivered`、非 `late`、`200` 的 `GET`；`nonterminal_observed = True` ⇒ 存在上述非终态 `GET`。
     * 仅有 P6 的 `delivered` / `terminal` 等自报告字段而没有代理事实 ⇒ 红。精确 task_id 取消、预算与“不推断执行协程已停止”的边界不变。
   * **O2-6（累计）** `|{L 中有 POST 的 attempt_id}| ≤ Z.submitted`，且 `Z.submitted ≤ Σ_N calls(N)`。
   * **O2-7** 同一 `previous` 上多次显式 `retry_failed`、重复的主轮 `preview` 都是独立操作：它们产生不同的 `attempt_id`，各自至多一个 `POST`，**合法**。
   * **O2-8（审计溢出）** `W` 之外的历史不得由 `W` 声称可复算；全历史的 O2 / O1 / O3 由第 5 点的分段流式验证提供，缺口 ⇒ `NOT_VERIFIED`，不是 PASS。

   *4.5 `calls(N)` 驱动的强制用例（红绿孪生；正常显式重复必须绿，单 aggregate 自动重复必须红）*：
   | 用例 | 脚本历史 | 期望任务数（`N`） | 结果 |
   |---|---|---|---|
   | 一次初始 + 一次重试 | `preview([N])`（失败）→ `retry_failed` | 2 个 attempt，各 1 个任务 | 绿 |
   | 一次初始 + 两次显式重试 | `preview` → `retry_failed(previous)` ×2 | 3 个 attempt、3 个任务 | 绿 |
   | 两次独立 generation=0 预览 | `preview([N])` ×2 | 2 个 attempt | 绿 |
   | 单 aggregate 自动重复 `POST` | `preview([N])` | `L` 中同一 `attempt_id` 2 个 `POST` | 红（O2-1） |
   | `CREATION_UNKNOWN` 之后显式重试 | `preview`（响应丢失）→ `retry_failed` | 宿主任务数 ∈ [1, 2]（孤儿可能存在） | 绿 |
   | 用不同 `attempt_id` 隐藏第二次 `POST` | `preview([N])` | `L` 有第二个 `attempt_id` 不在 P6 侧 | 红（O2-2 / O2-3） |
   | `attempt_id` 被两个 aggregate 复用 | `preview` ×2 | 审计里重复 id 或 `seq` 不稠密 | 红（O2-3 / 稠密性） |
   *4.6 H3 / H4 时序强制用例（R1 / x-02；红绿孪生；执行条件在证据包的 `gateD_r1.py` 与 `counterfactuals_r1.py` 里逐项标注为 LIVE / SIMULATED）*：
   | 情形 | 代理事实 | P6 | 期望 |
   |---|---|---|---|
   | H3 之前请求超时 | 无 `delivered`（宿主不答 / 未转发） | `UNKNOWN`，`TIMEOUT`，无后续请求 | 绿 |
   | 代理迟到写完 `202` | `delivered` 且 `late` | `UNKNOWN`，`TIMEOUT`，无后续请求（`H2 = H3 = TRUE`，`H4 = FALSE`） | 绿 |
   | H3 → H4 之间连接重置 / 响应中断 | `delivered`，非 `late`，随后连接重置 | `CONFIRMED`（P6 已读到）或 `UNKNOWN` + `CONNECTION` / `NETWORK` | 两者都绿 |
   | H3 → H4 之间调用方取消 / 致命 | `delivered` | `UNKNOWN`，`outcome is None`，`T ∈ {CALLER_CANCEL, FATAL_BASEEXCEPTION}`，零后续请求 | 绿 |
   | reader 拒绝 | `delivered`，非 `late`，body 不合法 | `UNKNOWN`，`SCHEMA_INVALID` / `TOO_LARGE` / `TOO_COMPLEX` | 绿 |
   | 正常 H4 成功 | 一个 `delivered`、非 `late` 的 `202`，同一 id | `CONFIRMED` | 绿 |
   | 违反边界的变异 | `late` 的 `202` + 拒绝类 outcome；`late` 的 `202` + `CONFIRMED`；已送达 `202` + `SERVER_ERROR`；`UNKNOWN` 之后的 `GET` / 取消；后续请求使用只在 `UNKNOWN` 的 `202` 里出现的 id；自动第二次 `POST` | 任一 | 红 |

   *4.7 取消 / 终态见证强制用例（R1 / x-06）*：绿——精确 id 取消、`200` 确认后观察 `failed`；同上观察 `done`；取消未确认 ⇒ `UNCERTAIN_NO_RESPONSE`；确认后无成功观察 ⇒ `UNCERTAIN_OBSERVATION_FAILED`；确认后见过非终态 ⇒ `UNCERTAIN_NOT_TERMINAL`。红——① 取消 `POST` 发出但没有已送达的 `200` 却自称 confirmed；② 只有取消 `POST` 没有任何终态 `GET` 却自称 `TERMINAL_FAILED_OBSERVED`；③ `GET` 用了错误 task_id；④ `GET` 返回 `running` 却自称 `failed` / `done`；⑤ `GET` 早于所需确认事件；⑥ 伪造 `delivered` / `terminal` 自报告字段而没有独立代理事实。
5. **分段流式验证（全历史安全不变量，不依赖无界内存或持久化）**：`peak_in_flight ≤ M` 与“每个 attempt 至多一个 `POST`”是安全不变量，**不因审计溢出而降低**；降低的只是 P6 侧**证据的保留窗口**。测试工具按 `completed` 计数**至少每 `MAX_AUDIT_RECORDS / 2` 条**调用一次 `audit_snapshot()` 取走新记录（**按 `completion_seq` 去重与排序**；记录按完成顺序保留，乱序完成时 `seq` 不单调，R5-05），喂给自己的验证器（`L` / `Hs` / `Mf` 同样流式处理），验证器重建全历史并重算 O1（`begin_event` / `end_event` 最大重叠 ≤ `M`）、O2、O3。每次取走必须满足连续性：新记录的最小 `completion_seq` 恰为已取走的最大 `completion_seq` + 1；出现缺口（`completion_seq ≤ dropped_records` 中有从未被取走的）⇒ 该运行的全历史项记为 `NOT_VERIFIED`（evidence gap），**不得**用保留窗口冒充全历史。验证器对取走记录里重复的 `seq` / `attempt_id`（含溢出后复用旧 id）报红；保留窗口的实现不得以 `seq` 为键折叠记录（否则重复被掩盖）。`Z.peak_in_flight` 始终是权威的历史峰值（第 20.5 节）。
   **收集器（Harvester）规则（R1 / x-05）**：① 每次取走先做快照**全局界限**校验（第 20.5 节：记录 `seq ≤ snapshot.last_seq`、`completion_seq ≤ completed`、窗口内 `completion_seq` / `seq` / `attempt_id` 各自唯一、窗口恰为 `dropped_records + 1 .. completed` 的稠密尾部、按 `completion_seq` 严格升序）；② 以 `completion_seq` 为游标：**同一条**记录再次取到 ⇒ 去重（绿）；**不同**记录绑定同一个 `completion_seq` / `seq` / `attempt_id` ⇒ 红——**不得**用 `setdefault` 等方式静默吞掉冲突；③ 快照计数器（`completed` / `dropped_records` / `last_seq`）不得倒退；④ 溢出前后行为一致：保存的完整历史上的 O2 / O3 对账与是否溢出无关；⑤ 丢弃前未取走 ⇒ `NOT_VERIFIED`（evidence gap）。验证器的结论是三态 **RED / NOT_VERIFIED / GREEN**，证据缺口不得报告为 PASS；单条 `record_is_legal` **不能**取代这些跨记录验证（它对 `seq > last_seq` 的伪造记录仍返回 `True`）。
6. **O3（K 的可复算区间）**：(O3a) 由窗口 / 取走的记录的 `task_known_event` / `end_event` 重算 `K` 的最大重叠，`≤ M` 且 `≤ |A|`；(O3b) 代理视角：区间 = `[该 attempt 的 202 delivered, 该 attempt 最后一个请求的响应 delivered]`（含取消之后的清理轮询；未 delivered 的 `202` 不产生区间），最大重叠 `≤ M`，它能发现经 HTTP 可见的“aggregate 已返回而清理仍在继续”，**不声称**穷尽所有重叠；(O3c) 测试工具以 ≤ 20 ms 间隔采样宿主任务仅作佐证，离散采样不证明连续峰值。未知 id 不被假装归类。**oracle 自检**：对 `ORPHAN-M1` 与“取消被受理后继续轮询”夹具，把 `H2` 孤儿计入 `K` 的变异 oracle、在取消响应处截止 `K` 的变异 oracle 必须与期望**不一致**（M6-28）。**O4 纯净对照**：仅在没有 `CREATION_UNKNOWN` / 放弃 / 孤儿的场景里，宿主上本批 `queued + running ≤ M`，不推广。
7. **强制孤儿用例 `ORPHAN-M1`（M = 1）**：宿主返回 `202 + id=101`（H1、H2），代理记录 `101` 但**丢弃该响应**（没有 H3）；P6 没有收到 `101`，记 `CREATION_UNKNOWN`，该 aggregate 返回 `FAILED`；任务 `101` 被 `HOLD` 保持 `running`（孤儿）；随后下一个 aggregate 创建并完成另一个任务。期望：`101 ∈ H`、`101 ∉ K`、`S = CREATION_UNKNOWN`；未变异实现 PASS（`|A| ≤ 1`、`|K| ≤ 1`、每个 `attempt_id` 至多一个 `POST`、`|H| == 2 > M` 被允许）。**必须 FAIL 的实现错误**：绕过 P4 scheduler 使 `|A| > M`（O1）；`UNKNOWN` 之后自动再 `POST`（O2-1）；隐藏 scheduler / 无界 fan-out；孤儿被归入 `K`；取消响应后提前返回而把轮询留给后台（detached，M6-11 / M6-30）。
8. **三个并发数必须区分**：① P4 metadata 并发 `M = OrchestrationConfig.metadata.max_in_flight_items`（缺省 4；P4 是唯一 owner，不变）；② Amane 宿主**配置的** worker 并发——`WorkerConfig.concurrency` 缺省是 **10**（两个版本相同，`config/manager.py`；`scheduler/worker.py` 构造函数里的 `concurrency=3` 只是类默认），验收宿主若明确配置了其它数值，以**实际配置**为准；③ 孤儿任务占用的并发。当 `M` 大于宿主实际并发，或孤儿任务占满并发时，多出的任务在宿主排队，其排队时间计入 `aggregate_deadline_seconds`（L6-07）。aggregate 返回之后，被放弃 / 取消的任务不再计入 `A` / `K`（清理轮询期间仍计入），但其执行协程可能仍在宿主上运行（第 10.3 节，L3 永远 UNVERIFIED）。
9. 门面不创建任何 event loop / 线程；全部在调用方的 loop 里运行。

---

## 15. Partial 语义（冻结；两个层次必须区分）

| 层次 | 内容 | P6 的立场 |
|---|---|---|
| A. Core 内部多来源 `PARTIAL` | 例如 `javdb` 失败、`fc2db_net` 成功 | 发生在 **P5 边界之内**。P5 把它映射为可用的 Amane `MediaMetadata`（PARTIAL 是可用结果，不是错误），仅在**宿主进程**里记一条 WARNING 日志。P6 **无法**也**不得**重建每个内部来源的失败分类 |
| B. P6 边界级的条目成功 / 失败 | 宿主 SCRAPE 是否产生了可映射、可归属的 Metadata | 唯一可证明的边界。内部来源降级但仍得到合法 `MediaMetadata` → **P6 条目成功**（`AggregateStatus.SUCCESS`，唯一 SourceResult） |

* P6 **不**把日志文本当证据，**不**读宿主日志，**不**声称某内部来源失败。
* “one source degraded, item still usable”的**证据**来自受控上游 fixture 的结构化请求账本（哪个来源页被请求、被指示返回了 5xx / 404）加上该条目最终
  READY——这证明的是“在上游降级下条目仍可用”，**不是** P6 的 provenance 声明（E6-12）。
* 因此在 P6 流程里不会出现 `ItemWarning.METADATA_PARTIAL`；任何测试若观察到它，都是缺陷。

---

## 16. Persistence / Resume（冻结：没有）

P6-C1 **不新增**：P6 batch 数据库、checkpoint 文件、JSON resume 文件、pickle、SQLite 状态、durable batch id、跨进程锁、进程崩溃后的恢复。

* Amane 自己把 Task 持久化在宿主库里——这属于 **Host ownership**，不是 P6 的 durable resume 契约。不得因为 Amane 任务落库就宣称 P6 支持 durable batch resume。
* 内存里存在的只有：`AmaneBatchPreview`（调用方持有）、有界审计账本（累计状态 `O(1)` + 至多 `MAX_AUDIT_RECORDS = 20000` 条保留记录；溢出丢弃最旧记录并如实标注，第 20.5 节）。
  它们**不是**持久化格式，没有序列化保证。
* P4 的进程内 `RetryMaterial` 继续按 CLOSED 合同使用（P6 不使用它，13.2）。
* 进程退出后：宿主上可能遗留 QUEUED / RUNNING 的 P6 任务（尤其 `UNCERTAIN_*`）；P6 不在下次启动时寻找或取消它们（那需要持久化任务 id，违反本节）。记入 L6-03。

---

## 17. Progress（冻结：不新增公共 progress 契约）

* Amane 的 `TaskResponse` 在两个版本里都**没有** progress 字段（见 7.3）；进度只通过 WebSocket（cookie 握手）事件到达。P6-C1 不使用 WebSocket。
* P4-C8 §11.4 明确：批量操作没有进度回调 / 订阅 / 可轮询的实时状态。P6 不修改 P4，也不新造“全局 progress 状态机”。
* 可观察、可用于测试 / 运维证据的只有：宿主任务的结构化 `status`、`AmaneHostAuditSnapshot` 的计数（`submitted` / `in_flight` / `peak_in_flight` /
  `failure_counts` / `uncertain_cancellations`）。它们是**运维观察**，不是语义结果的一部分（第 21 节）。
* 最终必须有确定性的 batch summary（第 20.4、21 节）。

---

## 18. 图片 / NFO / 物化所有权（冻结）

* P4 下游（`HttpxImageClient` 图片获取、NFO 渲染、产物清单、执行前预检、`BatchPreview`）**保持 CLOSED 原样**，由调用方传入的 `ImageHttpClient` 驱动；P6 不重写任何一步。
* Amane SCRAPE 可能按用户的 `scraping.download_resources` 把图片物化为宿主 Resource，且 `crop_poster` 缺省会把**展示列**里的 poster 替换为宿主内部 URL（`/api/resources/<hash>`）。**P6 的图片候选只来自 `PluginRaw` 的 `poster_urls` / `thumb_urls` / `extrafanart`**（第 11.3 / 11.4 节），它们是插件的原始 URL；Amane 的物化 / 裁剪**不改写 `raw`**（第 11.3.2 节核查）。因此（Design-R3 / R3-08，修正 R1 遗留的历史错误语义）：
  * **宿主展示 poster**（可能被裁剪 / 物化）与 **P6 的 poster 候选**是两个不同的东西。当 plugin `raw` 相同、只有宿主的展示裁剪 / 物化配置不同，**P6 的 URL 候选集合必须逐项相同**（E6-28：同一上游内容，在 `crop_poster` 开 / 关、`download_resources` 开 / 关的宿主配置下，P6 的 URL 候选集合、NFO 字节与产物清单一致）；
  * P6 **不依赖**宿主 Resource 文件，不把它们当作 P4 图片获取的替代；
  * 候选 URL 仍经“干净的绝对 http(s) URL”过滤（第 11.4 节）；被剔除的数量计入审计 `dropped_url_count`（由 `map_host_result` 第 7 步产生，第 11.2 节），它只统计 **`PluginRaw` 里插件原始 URL 本身**不合规而被删除的元素；**Amane 展示 poster 的裁剪 / 物化（`/api/resources/<hash>`）从不进入 P6 的 URL 过滤，也不进入 `dropped_url_count`**（R5-09）；
  * **不修改**用户的 Amane 全局配置（零 `/api/config` 访问）。
* P4 仍可能因为**原始 URL 缺失、URL 不合法或图片获取失败**产生 `POSTER_ABSENT` / `FANART_ABSENT` / 候选级失败警告；这些警告**不得**被归因于 Amane 展示列的裁剪或物化（L6-10 已修正）。不修改 CLOSED P4 的图片获取 / NFO 实现。
* **E6-28 冻结用例（Design-R4 / R4-09；只比较配置开关而没有实际展示值变化不算证明）**。依据：两个 pinned 版本的 `media/pipeline.py` 裁剪分支相同——当 `crop_poster = true`、`poster` 在 `download_resources` 里、宿主有 web client、存在可下载的缩略图，且 `should_crop_poster(thumb_size, candidate_size, skip_ratio)` 为真（无海报候选，或 `candidate_height / thumb_height < poster_crop_skip_ratio`）时，展示 poster 被替换为 `/api/resources/<hash>`；缩略图下载成功者前置（`_success_first`）。**固定输入**：缩略图 `T` = 确定性 JPEG 800 × 538（harness 用 Pillow 以固定像素生成，sha256 写入证据）；短海报 `P` = 确定性 JPEG 300 × 300；死 URL `D` 返回 `404`；全部由回环上游夹具提供（回环主机是 Amane 的内置主机）；处理配置 = `download_resources = [poster, thumb]`、`crop_poster = true`、`poster_ratio = 0.7`、`poster_crop_skip_ratio = 0.9`（缺省）。**正向用例**：`X1` 缺海报 + 有效缩略图（`poster_urls = []`，`thumb_urls = [T]`）；`X2` 短海报 + 有效缩略图（`300 / 538 ≈ 0.56 < 0.9`）；`X3` 缩略图重排（`thumb_urls = [D, T]` ⇒ 展示 `[T, D]`）。**对照**：`C1` = `crop_poster = false`；`C2` = `download_resources = []`。**必须同时断言**：① 非空性——`X1` / `X2` 的展示 poster 以 `/api/resources/` 开头且不同于对照组，`GET /api/resources/<hash>` 返回 `200 image/jpeg` 且宽高比符合 `poster_ratio`（±0.02），`X3` 的展示 `thumb_urls` 顺序确实变化；② `raw[ffcc.fc2-metadata]` 在三组配置下逐字节相同；③ P6 的 poster / thumb / extrafanart 候选元组、NFO 字节、产物清单在三组配置下逐项相同；④ `POSTER_ABSENT` 等 P4 警告只随 `raw` 变化。任一非空性断言不成立（宿主无 web client、Pillow 缺失、`acquire` 失败……）⇒ `FAIL（NON-VACUITY）`或`NOT_RUN`，**不得 PASS**。设计期状态：`UNVERIFIED`，待 S3 在真实宿主上实际执行。
* **验收宿主**可以（也必须）明确关闭 Amane 自身的 resource download（`scraping.download_resources = []`）与演员扇出（`actor_scraping.auto_scrape = false`），
  以减少重复网络与不确定性（第 22 节）；这只发生在测试工具里，对象是一次性的临时宿主。
* 图片候选级部分失败（P4 §22）保持为条目**警告**；“image partial failure”场景由 P4 的真实 `HttpxImageClient`（P4 自有 `ImageHttpClient` 测试接缝；P6 自身不使用 `MockTransport`）驱动，P6 只证明它们
  与真实宿主元数据组合时语义不变。

---

## 19. Phase 7 边界与“不执行”安全不变量（冻结）

Phase 6 的目标终点是 `… → NFO → organize preview`。宿主侧：Coordinator 与设计期核查一致确认 v0.15.0 / v0.18.0 存在 ORGANIZE 任务但**没有**可依赖的 dry-run /
organize preview 公共 API，因此 organize preview 由 **P4 `BatchPreview` / 执行前预检** 提供。Phase 7 才做真实文件系统验收（mkdir / rename / move /
collision / subtitle pairing / source preservation）。

### 19.1 安全不变量（机检；缺一即 FAIL）

```text
S6-1  P6 流程绝不调用 BatchOrchestrator.execute / fc2_organizer.execution.execute_filesystem / execute_preview
S6-2  P6 绝不提交 ORGANIZE / TRASH（或任何非 scrape 类型）宿主任务；请求账本的 type 恒为 "scrape"
S6-3  P6 绝不移动 / 重命名 / 删除 / 覆盖 / 创建 用户媒体根与 library root 下的任何文件或目录
S6-4  门面不暴露 BatchOrchestrator 或其 execute（Phase 7 才会增加执行入口）
S6-5  P6 不写任何文件（本包零文件 API、零日志、零临时文件）
```

### 19.2 机检方式

1. **静态（AST）**：`src/fc2_amane_batch/**` 中不得出现标识符 `execute`、`execute_filesystem`、`execute_preview`、`BatchExecutionResult`、`merge_retry`、
   `preview_retry`；不得 import `os` / `shutil` / `pathlib` / `tempfile` / `fc2_organizer.execution` / `.materialization` / `.nfo` / `.publication`；不得调用内建 `open`；
   请求构造中不得出现字符串字面量 `"organize"` / `"trash"` / `"delete"` / `"retry"`（`"cancel"` 与 `"scrape"` 除外）。
2. **运行时 tripwire**：`tests/amane_batch` 的 autouse fixture 把 `BatchOrchestrator.execute`、`fc2_organizer.orchestration.execute.execute_preview`、
   `fc2_organizer.execution.execute_filesystem` 替换为立即 `AssertionError` 的桩；任何一次调用即测试失败（mutation M6-10 证明它非空）。
3. **文件系统树摘要**：每个真实宿主场景前后对“媒体根 + library root”计算递归树摘要（相对路径 + 类型 + 大小 + 内容 sha256），必须逐字节相等。宿主自己的数据目录不在其中。

### 19.3 对 Phase 7 的输入语义（非约束性说明）

Phase 7 将通过 P4 原有路径对某个 `AmaneBatchRound.preview` 调用 `execute`；每一轮的 `BatchPreview` 都是独立、可按 P4 合同执行的对象；P6 **不**提供多轮合并语义，也**不**提供跨轮的 READY / 冲突安全保证（第 13.4 节：不同番号可共享同一个 hardlink 源文件，单轮 preview 看不见别的轮次）。**Phase 7 若需跨轮执行，必须对合并范围重新验证源文件身份与目标冲突**，这是 Phase 7 必须理解的已知局限（L6-16）。
Phase 7 需要为门面增加执行入口（并为此做自己的 Contract），不属于 P6。

---

## 20. 公共 API（冻结）

### 20.1 `fc2_amane_batch.__all__`（精确集合与顺序）

```python
__all__ = [
    # 门面与引擎
    "AmaneBatchIntegration", "AmaneAggregationEngine", "AmaneHostClient",
    # 配置与凭据
    "AmaneHostConfig", "AmaneHostCredential",
    # 结果模型
    "AmaneBatchPreview", "AmaneBatchRound", "AmaneBatchSummary",
    # 运维审计模型
    "AmaneHostAuditSnapshot", "HostAttemptRecord", "HostFailureKind", "CancelOutcome", "SubmissionState", "HostPreflightReason", "RetryRefusal",
    "AmaneRoundCounts", "CleanupTrigger", "AggregateTerminal", "TimestampRelation",
    # 常量
    "PLUGIN_SOURCE_ID", "MAX_RESPONSE_BYTES", "MAX_JSON_DEPTH", "MAX_JSON_NODES", "MAX_JSON_COLLECTION_ITEMS",
    "MAX_AUDIT_RECORDS", "MAX_RETRY_ROUNDS",
    "DEFAULT_REQUEST_TIMEOUT_SECONDS", "DEFAULT_POLL_INTERVAL_SECONDS", "DEFAULT_AGGREGATE_DEADLINE_SECONDS",
    "DEFAULT_CANCEL_BUDGET_SECONDS", "DEFAULT_MAX_CONSECUTIVE_POLL_ERRORS",
    # 错误
    "AmaneBatchError", "AmaneBatchConfigError", "AmaneBatchInputError", "AmaneBatchContractError",
    "AmaneHostCallError", "AmaneHostPreflightError", "AmaneBatchRetryError",
]
```

任何增减都是合同修订（需 Design Review）。`fc2_organizer/__init__.py` 与 `fc2_metadata_core/__init__.py` 不 import 本包（零 diff）。

### 20.2 错误层次

```text
AmaneBatchError(Exception)                      基类；消息固定、不含 URL / 宿主文本 / token / 任务 id
├─ AmaneBatchConfigError(AmaneBatchError, ValueError)     构造参数非法（base_url / 数值范围 / 凭据格式 / 未确认写入）
├─ AmaneBatchInputError(AmaneBatchError, ValueError)      门面输入类型非法（items 不是 list/tuple 等）
├─ AmaneBatchContractError(AmaneBatchError, RuntimeError) P6 内部不变量被破坏（缺陷，不是外部失败）
├─ AmaneHostCallError(AmaneBatchError)                    client 单次调用失败；只有结构化属性 .kind: HostFailureKind
├─ AmaneHostPreflightError(AmaneBatchError)               整批前置条件失败；只有 .reason: HostPreflightReason
└─ AmaneBatchRetryError(AmaneBatchError, ValueError)      retry_failed 被拒绝；只有 .reason: RetryRefusal
```

`HostPreflightReason = {AUTH_REJECTED, HOST_UNREACHABLE, WORKER_PAUSED, PROTOCOL_MISMATCH}`；
`RetryRefusal = {FOREIGN_PREVIEW, NO_RETRYABLE_ITEMS, ROUND_LIMIT}`。

**异常图封闭（Design-R1 / R1-03；Design-R2 / R2-02 重述）**：保护面、禁入内容、所有权状态例外与构造规则 C1–C7 全部以第 8.3.1 节为准，适用于**整个** `src/fc2_amane_batch/**`。本包抛出的每个异常的 `__cause__` / `__context__` 只能是 `None` 或另一个 `AmaneBatchError` 子类；绝不链到 httpx 异常或 `UnicodeError`；`raise … from None` **不被视为**满足要求（它不清除 `__context__`）。不得声称“任何对象都不可能引用认证信息”：调用方持有的 client / config / credential 本身含认证状态（第 8.3.1 节第 3 点）。

### 20.3 引擎与 client

```python
class AmaneHostClient:
    def __init__(self, config: AmaneHostConfig) -> None
    # R5-11 方案 A（待安全授权，第 10.6 节）：没有 transport= 参数；client 自建 httpx.AsyncClient（trust_env=False、固定 Timeout、无重定向）。构造零 I/O，不发请求。
    # 故障 / 协议测试通过真实回环套接字上的故障代理（第 22.5 节）执行，而不是替换传输层。
    async def submit_scrape(self, number: str) -> HostTask
    async def observe_task(self, task_id: int) -> HostTask
    async def cancel_task(self, task_id: int) -> HostBatchCancelResult
    async def fetch_metadata(self, metadata_id: int) -> HostMetadata
    async def probe_worker(self) -> HostWorkerState
    async def aclose(self) -> None          # 幂等；aclose 之后任何调用 → AmaneBatchContractError
    # 每个方法失败时只抛 AmaneHostCallError(kind)；HostTask / HostMetadata / … 是私有 _wire 类型（不进入 __all__）

class AmaneAggregationEngine:
    def __init__(self, client: AmaneHostClient) -> None
    # R5-11 治理附加裁决（方案 A 的衍生变更，待确认）：撤销 R4 的 _clock / _sleep 关键字接缝——可注入的 sleep 同样可以吞掉 CancelledError 而破坏有界取消；
    # 确定性单测改用真实回环宿主 + 短间隔（poll_interval ≥ 0.05 s、aggregate_deadline ≥ 1 s）
    async def aggregate(self, number: str) -> AggregationResult      # 类属性中的普通 async def（P4 静态形态检查要求）
    def audit_snapshot(self) -> AmaneHostAuditSnapshot
```

* `aggregate` 的返回 / 抛出契约：成功 → SUCCESS 结果；**所有宿主侧失败 → 返回 FAILED 结果（不抛）**；非规范号 → `InvalidCanonicalNumberInputError`（零网络）；
  P6 内部缺陷 → `AmaneBatchContractError`（普通 `Exception`，仍先做有界清理）；`CancelledError` → 有界清理后重新抛出（出口一律是 C5c 的同类型新实例：包内不使用裸 `raise` 重新抛出 `CancelledError`）；致命 `BaseException`（`KeyboardInterrupt` / `SystemExit` / `GeneratorExit`）→ 不做 I/O、原异常对象原样传播（第 10.2 节、第 10.3 节矩阵）。
* engine 不关闭传入的 client（所有权在创建者）。

### 20.4 门面与结果模型

```python
class AmaneBatchIntegration:
    def __init__(self, host: AmaneHostConfig, image_client, library_root: str, *,
                 output_policy=None, image_policy=None, config: OrchestrationConfig | None = None) -> None   # R5-11 方案 A：无 transport= 参数
    # 构造：校验 + 创建 AmaneHostClient / AmaneAggregationEngine / BatchOrchestrator；零网络、零文件系统访问
    # image_client 属于调用方（P4 约定）；门面只拥有自己创建的 AmaneHostClient
    async def preview(self, items) -> AmaneBatchPreview           # items: list|tuple[DiscoveredMediaItem]；先 preflight（9.5）
    async def preview_root(self, media_root, policy=None) -> AmaneBatchPreview   # discover_media(read-only) + preview；保留 discovery issues
    async def retry_failed(self, previous: AmaneBatchPreview) -> AmaneBatchPreview   # 13.3
    def audit_snapshot(self) -> AmaneHostAuditSnapshot            # 取消后仍可调用
    async def aclose(self) -> None                                # 幂等；async with 支持
```

```python
@dataclass(frozen=True, slots=True)
class AmaneBatchRound:
    generation: int                   # 0 = 主轮；k = 第 k 次失败子集重试
    origin_indices: tuple[int, ...]   # 严格递增；origin_indices[i] 是 preview.items[i] 在原始输入中的下标
    preview: BatchPreview             # P4 对该轮输入子集给出的、未经改动的 BatchPreview（同一对象）

@dataclass(frozen=True, slots=True)
class AmaneBatchPreview:
    items: tuple[DiscoveredMediaItem, ...]     # 原始输入快照（下标即原始下标）
    discovery_issues: tuple[DiscoveryIssue, ...]   # preview_root 的 DiscoveryResult.issues；preview(items) 时为空
    rounds: tuple[AmaneBatchRound, ...]        # rounds[0] 覆盖全部条目；其后为失败子集重试轮次
    # 派生（不存储）：
    #   latest(i) -> (generation, ItemPreview)   原始下标 i 的最新结果
    #   retryable_indices -> tuple[int, ...]     13.3 的可重试集合 R
    #   summary -> AmaneBatchSummary
```

`AmaneBatchPreview.__post_init__` 校验：`rounds` 非空；`rounds[0].origin_indices == tuple(range(len(items)))`；`rounds[k].generation == k`；
每个 `origin_indices` 严格递增且与对应 `preview.items` 等长；`rounds[k>0].origin_indices ⊆` 上一视图的 `retryable_indices`；
每个 `preview.items[i].media_item is items[origin_indices[i]]`（同一对象）。任一违反 → `AmaneBatchContractError`。

```python
@dataclass(frozen=True, slots=True)
class AmaneRoundCounts:             # 每轮一行；直接取自该轮 BatchPreview.summary 的计数（该轮自己的口径）
    generation: int
    total: int; ready: int; blocked: int; unprepared: int

@dataclass(frozen=True, slots=True)
class AmaneBatchSummary:            # 确定性、纯语义；由最新视图的 ItemPreview 派生，从不存储
    total: int
    ready_round_local: int          # 最新视图中，在各自所属那一轮内为 READY 的条目数；**不是**全局可执行 READY（见 cross_round_verified）
    blocked: int; unprepared: int; warned: int
    retried: int                    # 出现在任一 generation ≥ 1 轮次的不同原始条目数
    rounds: int
    cross_round_verified: bool      # == (rounds == 1)；rounds > 1 时 P6 未做、也不提供跨轮冲突验证（第 13.4 节）
    per_round: tuple[AmaneRoundCounts, ...]                              # 长度 == rounds，按 generation 升序
    stage_counts: tuple[tuple[OrchestrationStage, int], ...]            # 与 P4 PreviewSummary 同口径：Σ == blocked + unprepared
    metadata_failures: tuple[tuple[IssueReason, int], ...]               # 仅 METADATA 阶段原因
    retryable: int                  # == len(retryable_indices)
```

不变量：`total == ready_round_local + blocked + unprepared`；`warned ≤ total`；`Σ stage_counts == blocked + unprepared`；`retryable ≤ unprepared`；`rounds == len(rounds) == len(per_round)`；
`cross_round_verified == (rounds == 1)`；`per_round[k]` 与 `rounds[k].preview.summary` 的对应计数逐项相等（逐轮口径，**不得相加后冒充全局**）；
当 `rounds == 1` 时，`total / ready_round_local / blocked / unprepared / warned / stage_counts` 与 `rounds[0].preview.summary` **逐项相等**（交叉校验，E6-19）。
元组均按枚举声明顺序排序，保证确定性。`ready_round_local` 的命名与文档必须显式表明它是“轮内”口径；任何把它描述为“全局可执行 / 无冲突”的文字都违反本合同（M6-22）。

### 20.5 审计模型（唯一规范；运维，非确定性，与语义分离；Design-R4 / R4-05、R4-06 重写，Design-R5 / R5-04、R5-05 修订）

`HostAttemptRecord` 及全部相关枚举（`HostFailureKind`、`SubmissionState`、`CleanupTrigger`、`CancelOutcome`（10 个成员）、`AggregateTerminal`、`TimestampRelation`）的**唯一定义**是第 10.3.1 节的 `gate:host_attempt_record_types` 代码块；本节不再另抄一份（避免两套定义）。记录相对 R4 新增三个字段：`completion_seq`（完成序号）、`cancel_request_confirmed`、`nonterminal_observed`。

```python
@dataclass(frozen=True, slots=True)
class AmaneHostAuditSnapshot:
    # ---- 保留窗口 W（至多 MAX_AUDIT_RECORDS 条；按 completion_seq 升序，即按完成顺序；只含已完成的 aggregate）
    records: tuple[HostAttemptRecord, ...]
    dropped_records: int; highest_dropped_completion_seq: int; overflowed: bool   # overflowed == (dropped_records > 0)
    retained_window_peak: int                                              # 仅由窗口内记录重算的并发峰值
    # ---- 在途明细（R5-04）：此刻尚未完成的 aggregate，按 seq 升序
    in_flight_detail: tuple[tuple[str, InFlightPhase], ...]                # (attempt_id, 阶段)；InFlightPhase = BEGUN | ATTEMPTED | CONFIRMED
    # ---- 累计状态 Z（权威；在线更新；O(1) 内存；溢出后也精确）
    last_seq: int; last_event: int
    started: int; completed: int; in_flight: int
    peak_in_flight: int                                                    # 全历史并发峰值，在 begin 时更新
    submitted: int                                                         # 发出 POST 的次数（含在途）：在 POST 交给传输层之前递增；不是创建的任务数
    creation_confirmed: int; creation_unknown: int                         # 仅统计已完成的 aggregate
    abandoned_attempts: int                                                # == #{T ≠ NONE ∧ S ≠ NOT_ATTEMPTED}（已完成的）
    uncertain_cancellations: int                                           # == #{C ∈ UNCERTAIN_*}（已完成的）
    failure_counts: tuple[tuple[HostFailureKind, int], ...]
```

**三个统计域（R1 / x-03 冻结；不得混用）**：`Z` = 全生命周期累计状态（在线更新，O(1) 内存，溢出后权威）；`W` = **仅已完成**记录的保留窗口（FIFO，溢出后只是窗口）；`InFlight` = 当前未完成的尝试（`in_flight_detail`：`BEGUN` / `ATTEMPTED` / `CONFIRMED`，不受溢出影响）。`Z.submitted = 已完成且 S ≠ NOT_ATTEMPTED 的尝试数 + 在途中阶段 ∈ {ATTEMPTED, CONFIRMED} 的尝试数`；`creation_confirmed` / `creation_unknown` 在**完成时**计数，所以第一项恒等于 `Z.creation_confirmed + Z.creation_unknown`，因此 **`Z.submitted == Z.creation_confirmed + Z.creation_unknown + live`**（`live` = 在途明细中阶段 ∈ {ATTEMPTED, CONFIRMED} 的个数）在**任何时刻、含溢出之后**成立，并且不依赖 `W`。**不能**在 `in_flight > 0` 时由 `W` 求得全历史 `submitted`。强制用例：`W = []`、`completed = 0`、`in_flight = 1`、阶段 `ATTEMPTED`、`Z.submitted = 1` ⇒ 合法快照（绿）；“仅完成记录求和等于 `Z.submitted`”的旧变体 ⇒ 红。

**两个作用域（冻结）**：
* **累计状态 `Z`**：在 aggregate 的**更新点**在线更新（下表）；**溢出后不得由保留记录重新求和**。`Z` 是全生命周期计数与峰值的唯一权威。
* **保留窗口 `W`**：只保存最近完成的至多 `MAX_AUDIT_RECORDS` 条记录；超出时丢弃 **`completion_seq` 最小者**（FIFO，按完成顺序），更新 `dropped_records` 与 `highest_dropped_completion_seq`，**不**回改 `Z`。因此被丢弃的记录恰好是 `completion_seq = 1..dropped_records`，与 `seq`（开始顺序）无关（R5-05）。

**`Z` 的更新点（R5-04；每个计数器只在下列时刻改变，且每个时刻在同一个同步段内完成，不含 `await`）**：

| 更新点 | 时刻 | 改变的计数器 |
|---|---|---|
| `started` | `aggregate` 入口、分配 `seq` 与 `begin_event` 时 | `started += 1`、`in_flight += 1`、`peak_in_flight = max(peak_in_flight, in_flight)`；阶段 = `BEGUN` |
| `submitted` | 在 `POST /api/tasks` **交给传输层之前** | `submitted += 1`；阶段 = `ATTEMPTED`（`S` 此刻在记录里还不存在；只有终态记录才有 `S`） |
| H4 | 收到合法 `202` + 严格 reader 通过 | 阶段 = `CONFIRMED`（仅在途明细；`creation_confirmed` 在**完成时**才计数） |
| `completed` | 终态记录写入时 | `completed += 1`、`in_flight -= 1`、`creation_confirmed` / `creation_unknown` / `abandoned_attempts` / `uncertain_cancellations` / `failure_counts` 按记录增加；记录获得 `completion_seq = completed`；阶段条目移除 |

**不变量（测试逐项断言；分为四类：“任何时刻”“仅静止”“未溢出时可由 `W` 验证”“溢出后只能由 `Z` 或完整分段历史验证”，R5-04 / R1-06）**：

*任何时刻（包括有 aggregate 在途、包括溢出之后；全部可由快照本身验证）*：① `last_seq == started`；`started == completed + in_flight`；`len(in_flight_detail) == in_flight`；`completed == len(records) + dropped_records`；`highest_dropped_completion_seq == dropped_records`；② **`Z` 内部恒等式**：`submitted == creation_confirmed + creation_unknown + live`；③ `peak_in_flight ≥ in_flight`，且 `peak_in_flight ≥ retained_window_peak`；④ `seq` 稠密（分配时 `seq == last_seq + 1`）、`completion_seq` 稠密（窗口恰为 `dropped_records + 1 .. completed`）；⑤ **全局界限（R1 / x-05）**：窗口内每条记录 `seq ≤ last_seq`、`completion_seq ≤ completed`，窗口内 `completion_seq` / `seq` / `attempt_id` 各自唯一且按 `completion_seq` 严格升序；在途明细的 `attempt_id` 格式合法、`seq ≤ last_seq`、不与窗口记录重复；⑥ 快照是不可变值，不共享可变状态。

*仅静止时（`in_flight == 0`）*：⑦ `in_flight == 0` 且 `in_flight_detail` 为空；

*未溢出（`overflowed == False`）时才可由 `W` 验证的字段*：⑧ `submitted == #{W 中 S ≠ NOT_ATTEMPTED} + live`；静止时再加 `creation_confirmed` / `creation_unknown` / `abandoned_attempts` / `uncertain_cancellations` 与由 `W` 求出的值相等。

*溢出后只能由 `Z` 或完整分段历史验证*：全部累计计数与 `peak_in_flight`；由 `W` 求出的值只是“窗口值”，必须以 `retained_*` 命名并标注；全历史的 O1 / O2 / O3 只由第 14.4 节第 5 点的分段流式验证提供，缺口 ⇒ `NOT_VERIFIED`。**R4 把 ⑧ 当成任何时刻都成立的不变量，在有 aggregate 在途时会错误地报红（`Z.submitted` 已递增而记录尚未存在）——R5-04；R5 又把 ⑧ 的 `W` 求和留在“任何时刻”里，溢出后该式不成立——R1 / x-03 把它移到“未溢出”类，并用 `Z` 内部恒等式 ② 取代。**

**在途快照的必测场景（Gate D；五个，每个断言上面“任何时刻”的不变量与 `in_flight_detail` 的阶段）**：(1) `BEGUN`：`aggregate` 已入口、`POST` 尚未发出；(2) `ATTEMPTED`：`POST` 已交给传输层而响应未到；(3) `CONFIRMED`：已收到 `202`，正在观察；(4) 清理中：取消请求已发送、正在轮询；(5) 多个 aggregate 同时处于不同阶段（并断言 `peak_in_flight` 单调不减）。

**乱序完成与流式收集（R5-05 / R1-07 / R1-08）**：`aggregate` 按 `seq`（开始顺序）分配 id，但按**完成顺序**写入记录，所以窗口里的 `seq` 可能不单调。收集器以 `completion_seq` 为游标：每次 `audit_snapshot()` 之后先做**全局界限**校验（上面的 ⑤），再对窗口内每条记录以 `completion_seq` 去重——同一条记录再次取到是正常的（去重，绿）；**不同**记录绑定同一个 `completion_seq` / `seq` / `attempt_id` 是红（不得静默覆盖或忽略）。**被丢弃的记录恰好是 `completion_seq ≤ dropped_records`**，收集器若在 `1..dropped_records` 中有未见过的 `completion_seq` ⇒ 不可恢复缺口 ⇒ 全历史项 `NOT_VERIFIED`（不是 PASS）；缺口不能由 `completion_seq` 水位推断某个 `seq` 已被证明归属（两个序号空间不同，第 14.4 节 O2-3）。`MAX_AUDIT_RECORDS = 20000` 溢出时按 FIFO 丢弃；溢出后继续运行，`Z` 仍精确。强制红绿用例（`counterfactuals_r1.py` / `gateD_r1.py`）：未来 `seq`（`seq > last_seq`，即使 `attempt_id` 合法、代理 `POST` 使用相同伪造 id、单条 `record_is_legal` 为 `True`）红；冲突的 `completion_seq` 红；同一记录重复取走绿；合法乱序完成绿；溢出且保存了完整历史绿；溢出且历史缺失 ⇒ `NOT_VERIFIED`。

**溢出之后哪些验证仍然成立**：`Z` 级别的计数与历史峰值（自报告）；窗口内记录的合法性与对账（独立事实）；全历史的独立复算只能由第 14.4 节第 5 点的分段流式验证提供——该验证要求测试工具在记录被丢弃之前取走它们（至少每 `MAX_AUDIT_RECORDS / 2` 次完成取走一次），否则全历史项为 `NOT_VERIFIED`。

---

## 21. 语义输出 vs 运维输出（确定性分离，冻结）

| 类别 | 内容 | 是否参与确定性比较 |
|---|---|---|
| **语义输出** | 每轮 `BatchPreview` 的语义投影（条目下标、规范番号、`PreviewState`、`ItemIssue`（stage / reason / error_type / detail）、`warnings`、plan 路径（相对 library root）、产物种类与目标、**NFO 字节**、产物 sha256、`conflict_with`、`retry_origin`）、`AmaneBatchSummary`、问题的出现顺序 | **是** |
| **运维输出** | Amane task id、`metadata_id`、时间戳、`elapsed_ms`、轮询次数、请求次数、逻辑事件序号、随机标识（`BatchLineage.token`、`preview_id`）、墙钟耗时 | **否**（永不进入语义输出） |

* `AggregationResult` / `SourceResult` 内只有封闭词汇（`error_detail`）与测量耗时；任务 id / metadata_id **只**出现在审计里。
* 确定性判据（E6-15）：同一组确定性宿主 / 上游输入，仅**完成顺序**不同（例如上游按番号逆序放行），则：每轮 `BatchPreview` 的语义投影、NFO 字节、artifact requests、
  issue 顺序、`AmaneBatchSummary` 完全相等。测试侧的 `semantic_projection()` 必须显式列出排除项（上表“运维输出”），且有一个非空性控制：改变上游内容必须使投影改变。

---

## 22. 验收环境（冻结）

### 22.1 宿主坐标

| 标签 | 坐标 | 要求 |
|---|---|---|
| HOST-A-SRC | SC-03：v0.15.0 / source host（`python -m amane.server`，独立 venv，Python 3.14.x）/ Windows x64 | **必需** |
| HOST-B-SRC | SC-04：v0.18.0 / source host / Windows x64 | **必需** |
| HOST-A-WIN / HOST-B-WIN | SC-01 / SC-02：官方冻结桌面包 | **可选**：运行并 PASS 才可声明；否则 `UNVERIFIED`，不扩大支持声明 |

两个必需宿主是**真实 Amane 进程**（真实 task worker、真实 P5 plugin、真实 Core、真实 P4 下游）；不是 fake Amane 对象。宿主准备**只读复用** P5-C2 已 CLOSED 的工具
（`tools/prepare_amane_hosts.py`、`tools/build_core_wheel.py`、`tools/build_amane_release.py`）；P6 不修改它们。

### 22.2 宿主准备（仅在测试工具里，对一次性临时宿主）

1. 环境：`AMANE_DATA_DIR` / `AMANE_LOG_DIR`（临时目录）、`AMANE_PORT`（空闲端口）、`AMANE_HOST=127.0.0.1`、`AMANE_TOKEN=<canary token>`、`AMANE_SAFE_DIRS=ALLOW_ALL`。
2. 把 P5 构建的 sidecar Core wheel 放入 `<data>/plugins/_ffcc_core/`（INSTALL 文档流程），经 `POST /api/plugins`（`201`）安装 plugin zip；wheel 的 sha256 必须等于
   `adapters/amane/release/core_release_ledger.json` 的 pin（E6-23）。
3. `PATCH /api/plugins/ffcc.fc2-metadata`：`sources` 为 `fc2db_net` / `javdb` / `av123` 三项，各自 `base_url` 指向 P6 上游 fixture 的对应前缀（回环 `http://127.0.0.1:<port>/…`）；
   `source_deadline_seconds` 取小值（如 5）。
4. `PATCH /api/config`：`scraping.content_routes.fc2 = ["ffcc.fc2-metadata"]`、`scraping.download_resources = []`、`actor_scraping.auto_scrape = false`；LLM 翻译保持关闭。**E6-28 专属例外**：仅在专为 E6-28 创建、结束后销毁的一次性宿主上，harness 自己的 client 可把 `scraping.download_resources` 设为 `[poster, thumb]`、`scraping.crop_poster` 设为 `true / false`（对照组）并回读断言；其余证据宿主仍保持 `download_resources = []`。生产 P6 不访问 `/api/config`。
   随后 `GET /api/config` **回读并断言**（回读只存在于测试工具，宿主是一次性且无任何真实 cookie / token）。

### 22.3 FC2 route ownership 的机械证明（E6-16）

不得以“最后有 Metadata”代替归属。必须同时具备：

1. **配置事实**：route 回读 `== ["ffcc.fc2-metadata"]`；`GET /api/plugins/ffcc.fc2-metadata` 显示已安装且启用。
2. **内容来源的值级证明**：每个成功条目的输出必须能由 `raw["ffcc.fc2-metadata"]`（第 11.3.2 节）确定性重算；harness 用自己的 client 回读同一条记录，**独立**复算一遍 `NormalizedMetadata`（独立 oracle，不复用生产映射代码），二者必须逐字段一致；并与确定性上游夹具经 Core 规范化后的期望值核对（验收宿主无翻译 / 无 FacetRule / 禁止物化时，展示列与 `raw` 也应一致，`display_title_diverged == False`）。
3. **上游请求账本**：Core 三个来源适配器的 URL 形状（`/fc2db/work/<digits>/`、`/javdb/search?q=FC2-PPV-<digits>`、`/av123/en/v/fc2-ppv-<digits>`）只会由“配置了这些 base_url 的 plugin”产生；
   账本逐号记录被请求的来源页，成功条目的号必须出现。
4. **反事实控制**：同一宿主上卸载 / 禁用 plugin（或把 route 清空）→ 同一批号全部在 METADATA 阶段失败（M6-01 / M6-02）。
   **值级 provenance 反事实（Design-R2 / R2-01；每一项都必须非空地使对应门变红，并带绿色孪生）：**
   ① *v0.15.0 手工覆盖（真实宿主）*：任务 `done` → harness 手工 `PATCH` title=B → P6 `GET`（用故障代理在 metadata `GET` 之前挂起请求，期间执行 `PATCH`）。**共同强证明**：语义 title == `raw.title` == A，**绝不是** B，`display_title_diverged == True`；
   ② *v0.18.0 手工覆盖并解锁（真实宿主）*：任务 `done` → `PATCH` B（title 被锁定）→ harness 经公开锁接口**解锁** → P6 `GET`；此时展示列 B 的持久化 `field_sources` 仍指向插件、未被锁定——Design-R1 的做法会误判；断言同上的共同强证明；
   ②′ *宿主替身的精确交错（仅替身，标注 `DOUBLE`，永不当作真实宿主证据）*：SCRAPE UPSERT A → `PATCH` B → 任务 `done` → `GET`。真实宿主与替身**共享的强证明只有**“语义 title == `raw.title` ≠ B”；**两者的时间戳证据不同**（真实宿主上 `PATCH` 发生在任务完成之后；替身交错里 `PATCH` 发生在标 done 之前），不得声称它们有相同的时间戳证据，也不得由 `timestamp_relation` 反推事件顺序；
   ②″ *时间戳比较用例（替身 / 代理改写时间戳字符串；R3-02 四例，结果只由两个字符串决定，而不是由事件先后决定）*：**CASE A** 实际后写入且 `updated_at > finished_at` ⇒ `UPDATED_AFTER_FINISHED`；**CASE B** 实际后写入且 `updated_at == finished_at` ⇒ `UPDATED_NOT_AFTER_FINISHED`；**CASE C** 实际后写入但 `updated_at < finished_at`（模拟墙钟回拨）⇒ `UPDATED_NOT_AFTER_FINISHED`；**CASE D** 时区 / 精度不一致、缺失、不可解析 ⇒ `INDETERMINATE`。每例同时断言语义输出不变（== A）；
   ③ *同号 plugin SCRAPE 竞争覆盖*：另一个同号 SCRAPE（上游夹具内容已切换）在任务完成后整体替换 `raw`；断言输出与**当时读取到的** `raw` 一致（插件来源的另一次抓取），不与过期展示列混合，`timestamp_relation` 仅记录、**不对其作断言**（可能是任一值，因为它只反映两个时间戳字符串），HANDOFF 如实声明“非任务独占”；
   ④ *外来 persisted field_sources*：代理改写展示记录的 `field_sources` / `locked_fields` 注入外来站点 → 输出不变（这些字段不被读取）；孪生：把读取它们作证据的变体（M6-17）判红；
   ⑤ *plugin raw 缺失、混合或非法*（R3-01 必需的四个用例）：`raw = {plugin: valid_A}` ⇒ **PASS**；`raw = {plugin: valid_A, foreign: valid_C}` ⇒ **FAIL**（`HOST_ATTRIBUTION_FOREIGN`）；`raw = {foreign: valid_C}` ⇒ **FAIL**（`HOST_ATTRIBUTION_FOREIGN`）；`raw = {plugin: invalid}`（`title` 非字符串、`actors` 非列表等）⇒ **FAIL**（`HOST_METADATA_CONTRACT`）；另含带 `:lang` 后缀键与未知来源键 ⇒ `HOST_ATTRIBUTION_FOREIGN`。不得回退读展示列（M6-18）；去掉严格键集合校验的变体必须红（M6-25），原实现为绿；
   ⑥ *raw 与 persisted title 不一致*：展示 title ≠ raw title → 输出取 raw，`display_title_diverged == True`，条目不失败；
   ⑦ *干净 plugin raw 正向孪生*：展示列与 `raw` 一致、无竞争 → 输出与独立 oracle 一致，`display_title_diverged == False`；`timestamp_relation` 只作观察记录（预期 `UPDATED_NOT_AFTER_FINISHED`），**不是**正确性断言。
   **关键验收**：任何场景都不得把仅由用户手工覆盖产生的值作为插件字段内容输出。某个版本上无法通过公开 API 构造的格子，用代理改写代替并在矩阵 JSON 标明构造方式；无法构造的如实标 `NOT_RUN`，不得写 PASS。
5. **构件同一性**：plugin zip / sidecar wheel 的哈希与 P5 台账 / 构建器输出一致。

### 22.4 确定性上游 fixture（P6 自有，`tests/amane_batch/`）

* **只读复用** P5-C2 的回环 fixture 语料（`tests/amane_compat/host_scripts/loopback_fixture.py` 所服务的 HTML 夹具）；P6 在自己的目录里写包装层，**不修改**该文件。
* ≥ 10 个互异、满足 canonical 的号：以确定性的数字替换从 VERIFIED 夹具页派生（派生页必须先通过 Core 解析器的预检测试，防止夹具本身无效）。
* 行为类别：`ALL_OK`（≥ 10 个互异号）、`DEGRADED_ONE_SOURCE`（一个来源 5xx / 404，其余命中）、`TOTAL_FAILURE`（全部来源失败）、`HOLD`（响应被扣留直到测试释放；
  用于“宿主任务运行中”的取消）、`SLOW`（可控延迟；用于完成顺序反转）。
* 请求账本只记录（来源、digits、方法、行为），不记录端口 / 时间 / 绝对路径。
* 图片：P4 自有的 `HttpxImageClient(transport=httpx.MockTransport(...))` 测试接缝（**属于 CLOSED 的 P4，不是 P6 公共 API；P6 自身不使用 `MockTransport`**，R5-11），对元数据里的绝对 URL 返回确定性图片字节；单个候选的失败行为由 URL 令牌选择（沿用 P4-C10 harness 的约定，只读复用）。

### 22.5 故障注入代理（测试工具；“真实宿主 + 受控网络 / 响应故障”）

回环 TCP/HTTP 代理，位于 P6 client 与真实宿主之间，按脚本施加**记录在案**的故障：丢弃 / 延迟第 n 个匹配请求的响应、关闭连接、**改写**真实宿主响应中的某个 JSON 字段
（删除 `result.metadata_id`、改 `metadata.number`、清空 / 删除 / 改写 `raw` 中的插件记录或其键、向任务侧 `field_sources` 注入外来站点、改写展示列的 `field_sources` / `locked_fields` / `updated_at`）、并**同时充当独立 POST 账本**（按到达顺序记录**每个**请求的 `(attempt_id, 方法, 路径, 请求体键集与号 / ids, 响应状态)`，并区分 `forwarded`（代理转发并看到宿主的 `202 + id`，H2）与 `delivered`（代理把响应完整写给了 P6 的连接，H3）两种事件；丢弃 / 截断响应时只有 `forwarded`。账本是**代理自己的观察**，不等同于 P6 已经收到的信息（H4）；供第 14 节 O2 / O3 与第 10.3 节取消见证对账使用）、**挂起**第 n 个匹配请求直到 harness 放行（用于“任务完成之后、P6 读取 Metadata 之前”的手工更新）、以及把响应体替换为**字节数未超限但结构超限**的 JSON（深层嵌套 / 海量节点 / 超大集合）。用途：传输超时、取消不确定性（丢弃取消响应）、DONE 缺 `metadata_id`、
号不匹配、低于最低成功、外来归属。故障脚本进入证据 JSON。

**故障覆盖矩阵（R5 治理附加 A；方案 A 之下**所有**故障都来自真实回环 TCP / HTTP，不使用任何可注入传输）**。测试宿主（回环 HTTP 服务器）与代理支持的故障模式，以及它们在 Gate C 中的对应检查（每项检查同时断言 token 与响应体 canary 不出现在异常文本、审计记录、存活的 `Request` / `Response` 里）：

| 要求的故障 | 回环故障模式 | Gate C 检查 | 期望 |
|---|---|---|---|
| 首次 / 二次 / 多次取消 | 宿主停滞 + 调用方 `cancel()` ×1 / ×2 / ×4 | C1–C8；F “四次连续取消” | `CALLER_CANCEL`；仅 1 个取消 `POST`；`INTERRUPTED` |
| 响应头停滞 | `stall` | C1；F “响应头永不到达” | `HOST_TIMEOUT` / `UNKNOWN` |
| 响应头 / 响应体 slowloris | `dribble_hdr` / `dribble` | D1–D2、D10 | 总 deadline 内 `HOST_TIMEOUT` |
| 流中断 | `partial`（部分响应体后停滞）、`truncated`（Content-Length 不足后关闭）、`reset`（RST） | C2；F 三项 | `HOST_NETWORK` / 取消 |
| 连接拒绝 | 已关闭端口 | F “connection refused” | `HOST_CONNECTION` |
| 丢失 `202` | 代理读到宿主 `202` 但不转发（有孤儿任务） | F “lost 202”；Gate D ORPHAN-M1 | `UNKNOWN`；宿主上有任务 |
| `401` / `403` / `429` / `500` / `503` / `404` | `status:N` | F 六项 | 对应 `HostFailureKind` |
| 非法 JSON / 结构错误 / 超大 | `badjson` / `badschema` / `toolarge` | F 三项 | `SCHEMA_INVALID` / `RESPONSE_TOO_LARGE` |
| 观察期故障 | `GET` 全 `503` | F “observation 503” | `OBSERVATION_FAILURE` + `OBSERVATION_FAILED` |
| 元数据阶段非法 JSON | `GET /api/metadata` `badjson:200` | F “metadata” | `SCHEMA_INVALID`，`terminal_status = done` |
| 取消请求自身故障 | 取消 `POST` 回 `401` / `500` / 非法 JSON / RST | F 四项 | `NO_RESPONSE`（`cf = 否`） |
| TLS 握手停滞 / 黑洞地址 | 回环 TLS 服务器不应答 / 不可路由地址 | TLS / blackhole | 超时或取消，无残留 task |
| 异常路径 | 传输层抛非 `httpx` 异常（`httpx.AsyncHTTPTransport` 补丁点，仅测试） | R5-12 红绿孪生 | `HOST_NETWORK`，无链 |
| 致命异常 | 第三方钩子 / 网络读抛出（含抛出方植入凭据的反例）；任一字节码 / 检查点注入 | F3 33 项（4 个植入用例 = OUT_OF_THREAT_MODEL，B1）+ 帧安全 11 项 + 审计自检 10 项 + 窗口探针 | 第 10.5 节 |
| 凭据 canary | 全部用例 | 每项内含 | 不出现 |
| 迟到 `202` | 代理读到宿主 `202` 后延迟投递，直到客户端早已放弃 | C3-4 | `UNKNOWN`；宿主有孤儿任务；P6 之后不再发任何请求 |
| 精确 task id 取消 | 代理账本 | C3-5 | 恰 1 个取消 `POST`，体键恰为 `{action, task_ids}`，`task_ids == [202 里的 id]`，旁观任务未被取消，所有请求带同一 `X-FFCC-Attempt` |

**故障网络的独立性（Gate C-Final-03）**：回环故障宿主与代理在独立模块 `faultnet.py` 中，**只导入标准库**（`asyncio`、`json`），不引用被测的生产状态机、记录谓词、合同类型或期望结果；响应只由脚本化模式决定。判定规则（O2 对账、期望的失败种类、取消结果）写在各 Gate 脚本里，不在被测原型、也不在故障网络里；Gate 对 `faultnet.py` 的导入集合与禁用名字做机检（C3-2 / C3-3）。

**测试接缝撤销后的验收能力（`transport=`、`_clock`、`_sleep` 均不存在）**：

| 需要的确定性能力 | 在没有注入点时如何构造 | 检查 |
|---|---|---|
| 首次 / 二次 / 多次取消，精确 task id 取消 | 真实宿主停滞 + 调用方 `cancel()`；代理账本核对取消体与 id | C1–C8、F “四次连续取消”、C3-5 |
| 迟到 `202`、超时、连接失败、流中断 | 代理延迟投递；回环宿主 `stall` / `dribble*` / `truncated` / `reset`；已关闭端口 | C3-4、第 22.5 节矩阵 |
| aggregate deadline 与观察间隔（原先依赖 `_clock` / `_sleep`） | 真实时间下的最小合法取值：`aggregate_deadline_seconds = 1`、`poll_interval_seconds = 0.05` | C3-6（1.0 s 的 deadline 在约 1.66 s 内以 `DEADLINE` + 清理结束） |
| 取消 / deadline 竞态 | 原型接缝仅用于设计探针；实现的验收用真实回环 + 调用方的 `call_later` / `asyncio.timeout` / `TaskGroup` 构造同一批交错 | race_probe R1–R11 |
| 无隐藏 scheduler、额外 P6 task、长期残留资源 | 每个场景之后检查 P6 task、待触发的 deadline 定时器、连接池连接、线程 | C3-7（0 / 0 / 0 / 无新增线程） |

### 22.6 旁观任务（bystander）

在取消场景里，测试工具先用**自己的** client 在同一宿主上直接创建一个与批量无关的 SCRAPE 任务（保持 QUEUED / RUNNING）。取消完成后断言它**未被取消**；
这是 M6-08 的非空性依据。

---

## 23. Evidence Gate（冻结；根据 Governance v2 第 17 节，较大的 C 证据必须更完整）

| ID | 证据 | 载体 |
|---|---|---|
| E6-01 | 范围门：`git diff 4189b95…..HEAD` ∪ 工作树 ⊆ P6 allow-list；闭合范围零 diff；**HG-1 精确约束**（第 5.4 节：文件集合恰为两个；唯一移交的两处工作树断言；测试函数名集合 = Base 集合减 1；四个历史常量 AST 逐字相同；无新增 skip / xfail；diff 行数 ≤ 60）；**P6 自有的 C0 控制字符检查覆盖 `4189b95…..HEAD` ∪ 工作树内全部文本文件**（承接被重绑的历史检查） | `tests/amane_batch/test_amane_batch_scope_gate.py` |
| E6-02 | Contract → implementation → test 映射表（逐条合同条款 / 不变量） | HANDOFF |
| E6-03 | 架构守卫（AST）：import 允许 / 禁止清单；禁用标识符（19.2）；endpoint 常量集合 **等于** 表 H1；无 logging / 文件 API；控制流不比较 `error` / `detail` / `str(exc)` / `exc.args`；**`host_client.py` / `facade.py` 的 `except` 处理体内不得出现带参数的 `raise`（第 8.3 节）**；JSON 预扫描无递归（无自调用、无递归下降）；门面不直接调用 `engine.aggregate`（第 9.5 节）；**整个包**禁止 `asyncio.shield` / `asyncio.timeout` / `asyncio.timeout_at` / `asyncio.wait_for` / `create_task` / `ensure_future` / `gather` / `TaskGroup` / `run_in_executor` / `to_thread` / `threading`，`loop.call_at` / `Task.cancel` / `Task.cancelling` / `Task.uncancel` 只允许出现在 `_transport`（C8），`_transport` 的 `try` 必有 `finally: timer.cancel()`，且 `host_client.py` / `_lifecycle.py` / `engine.py` 的 `except` 内只有一类裸 `raise`（致命三类，第 10.2 节第 6 条）；**包内不得有任何测试钩子 / 开关 / 环境变量（模块级可变回调、`TRACE` / `HOOK_*` 之类，M6-50）**；**致命处理体形状守卫（C9：边界帧内联、`_transport` 无致命处理体、边界局部干净）**；**公共构造面签名守卫（R5-11）**：`AmaneHostClient` / `AmaneAggregationEngine` / `AmaneBatchIntegration` 的 `__init__` 与 `AmaneHostConfig` 字段中不得出现 `transport` / `http_client` / `client_factory` / `mounts` / `event_hooks` / `verify` / `proxy` / `trust_env` / `sleep` / `clock` 等注入参数，也不得有 `httpx.` 类型注解（含 R4 签名的红孪生） | `test_amane_batch_architecture.py` |
| E6-04 | 配置 / 凭据：校验矩阵（base_url 全部非法形态、数值边界、凭据字符集）；redaction；不可 pickle / copy | `test_amane_batch_config.py` |
| E6-05 | client 协议（**真实回环套接字上的故障代理与测试宿主**，不使用 `httpx.MockTransport`，`AmaneHostClient` 不接受任何传输，R5-11 方案 A）：**请求账本逐键断言**（方法 / 路径 / 体键集 / 头集，由代理独立记录）；无 cookie 回传、无重定向跟随、无环境代理 / `.netrc`、响应上限、状态码映射表穷举；第 22.5 节**故障覆盖矩阵**的全部行（连接拒绝、响应头停滞、slowloris、流中断 / 截断 / RST、丢失 `202`、`401` / `403` / `429` / `500` / `503` / `404`、非法 / 错构 JSON、超大响应） | `test_amane_batch_client.py` |
| E6-06 | 严格 reader：必需键缺失 / 类型错误 / 额外键容忍（`HostMetadata` 仅 `id` / `number` / `raw`，其余展示列与 `locked_fields` / `field_sources` 被忽略且不保留）；`PluginRaw` reader（第 11.3.3 节）；**有界 JSON（R1-07 / R2-03）**：深度 / 节点 / 集合项各自“恰在上限（绿）/ 超一（红）”孪生，字节数均远低于 8 MiB；输入矩阵覆盖长字符串、长空白、转义引号、连续反斜杠、字符串内部的 `{ } [ ]`、对象键、空对象、空数组、未知嵌套字段；预扫描计数与独立递归参考计数器在小输入上逐项对账；超限在 `json.loads` **之前**拒绝（对 `json.loads` 的 spy 断言未被调用）；深层嵌套不触发 `RecursionError`；超限映射 `HOST_RESPONSE_TOO_COMPLEX` 且不保留原始响应；**成本**：正常通过时扫描的操作计数随 `B` 线性（`B` 与 `2B` 的比值有界，用操作计数而非墙钟），辅助栈深度 ≤ `MAX_JSON_DEPTH`，不物化子串；两个版本的真实合法响应（含 `raw`）实测值低于上限的 1/4 | `test_amane_batch_wire.py` |
| E6-07 | 映射：字段表穷举（守卫 `PluginRaw` / `NormalizedMetadata` 字段集合）、URL 卫生与 P5 I22 逐样本对账、最低成功、号等价、每个 `HostFailureKind` → 合法 Core 配对（`ALLOWED_ERROR_KINDS`）、产出的 `AggregationResult` 通过 Core 校验且能被 P4-C9 诊断投影接受；**值级 provenance（R2-01）**：输出完全由 `raw["ffcc.fc2-metadata"]` 派生，展示列的任何改动（title / actors / tags / URL / `field_sources` / `locked_fields` / `updated_at`）都不改变输出；第 22.3 节 ①–⑦ 七类反事实的单测层红 / 绿孪生；`source_urls` / `external_ids` 恒为空；`display_title_diverged` / `timestamp_relation` 只进审计；**R5-08 URL 卫生**：从合同抽取的第 11.2 节代码块在第 7 步删除不合规 URL（空白 / 控制字符 / 无 host / 空串 / scheme 相对），三个列表合计的 `dropped_url_count` 精确；混合合法与非法 URL 的精确计数；全部合法为 0；最终字段的后置条件（号规范、标题非空白、每个 URL 干净、`dropped` 为 `int ≥ 0`）；**去掉 URL 过滤的变异必须被检出**；**R4-01 映射入口**：从合同抽取第 11.2 节代码块并执行——≥ 42 个有序优先级用例（含“混合来源 + 插件号错误 ⇒ `ATTRIBUTION_FOREIGN`”“畸形插件值 + 号不符 ⇒ `METADATA_CONTRACT`”“号不符 + 空标题 ⇒ `NUMBER_MISMATCH`”）与 20000 次随机变异 fuzz：无未处理异常，每个输入恰有一个分类；**R3-01** 严格键集合的四用例 + 语言后缀 / 未知键用例；**R3-02** 时间戳 CASE A–D 的结果只由两个字符串决定 | `test_amane_batch_mapping.py` |
| E6-08 | 生命周期与状态机：deadline（含“至少一次观察”）、观察失败容忍、**提交永不重试**；`SubmissionState`（非规范号 ⇒ 无记录；`202` ⇒ `CREATION_CONFIRMED`；超时 / 连接中断 / 响应丢失 / `401` / `403` / `5xx` / schema 非法 ⇒ `CREATION_UNKNOWN`，不折算为 0 或 1）；**状态机（R4-06 / R4-07 / R5-01 / R5-02 / R5-06，唯一规范 = 第 10.3.1 节类型与谓词 + 第 10.3.4 表）**：从合同抽取**真实枚举与冻结数据类**及谓词并执行（不使用字符串替身）——`3 × 8 × 10 × 4 × 2 × 2 × 2 = 7680` 个基础组合逐一判定，与独立参考模拟器的 **63 条**可产生记录**相等**（过度接受 0、接受不足 0、矛盾 0、崩溃 0；状态数由模拟器重新计算，不预设）；对每条可产生记录做字段级与类型级破坏（事件顺序 / 缺 H4 / 伪造 H4 / `cancel_event` 越界 / `bool` 与浮点伪装的整数 / `attempt_id` 与 `seq` 不符 / 状态 `ATTEMPTED` / `outcome` 错配 / 非严格 `bool` 的 `cancel_post_attempted`（`0`、`"not-bool"`）/ `cancel="BOGUS"` / `outcome="CANARY-SECRET"` / `TERMINAL_FAILED_OBSERVED` + `terminal_status="done"`）共 12890 个全部被拒且无崩溃；`outcome × context` 1260 组合、`terminal_status` 189 组合与模拟器一致；规则消融（28 条独立 `return False` 规则逐条删除，必有反例变红）；命名反例与 **R5-06 三用例**（取消未确认 + 非终态 ⇒ 拒绝；取消未确认 ⇒ `NO_RESPONSE` 接受；确认后无任何成功观察 ⇒ `OBSERVATION_FAILED` 接受）；表 10.3.4 与谓词接受集合逐行相等；**Python 3.11.0（最低）与最新可用 3.11.x、3.12、3.14 都执行；3.13 未安装 ⇒ `NOT_RUN`（R5-10）**；**R1 / x-01 严格类型**（Gate B：`x01_strict_types.py`）：`replace(good, terminal_status=UserString("done"))` 在构造处被拒绝（旧规范接受并可事后改 `.data`）、`record_is_legal(None)` / `record_is_legal(SimpleNamespace())` / 未初始化实例 / 鸭子类型 ⇒ `False` 而不抛出、错误文本固定且不回显字段内容、Enum / 严格 bool / 事件 / `HostFailureKind` 约束与 63 个抽象状态不变；变异（放宽 `terminal_status` 严格性、去掉对象层检查）变红 | `test_amane_batch_lifecycle.py` |
| E6-09 | 取消与清理（唯一规范 = 第 10.2 节）：精确 id、请求体不含 `status` / `type`、预算、`CancelOutcome` 全部 **10** 种（无 `CONFIRMED_STOPPED`）、**内联清理且包内无第二个 task**（任何时刻 `asyncio.all_tasks()` 中无 P6 创建的清理 task）、首次取消、**第二次与多次取消（50 次流中取消后连接池可用）**、清理超时、清理请求抛异常、清理请求永不返回（每请求超时兜底）、**取消已确认而之后每次观察都停滞 ⇒ `UNCERTAIN_OBSERVATION_FAILED`**、响应流中取消（连接期 / 等响应头期 / 流中途）、TLS 握手停滞 / 黑洞地址 / slowloris、致命 `BaseException`（零额外 HTTP 请求、原异常身份保持；经异常不可达任何敏感引用（含第三方帧上的 `Request` / `Response`），第 10.5 节）；**取消结果的严格优先级与 `NO_RESPONSE` / `NOT_TERMINAL` / `OBSERVATION_FAILED` 的拆分（R5-06）**；探针在**每个声明支持的解释器**上运行：Python 3.11 的**最低小版本（3.11.0）与最新可用小版本**、3.12、**3.13（正式运行时验收，S3 必须运行；设计探针已在 3.13.0 / 3.13.9 通过，但实现验收在运行前为 `NOT_RUN`）**、3.14；**响应头 / 响应体 slowloris 的总 deadline**（R5 附加 B：请求超时 1.0 / 2.0 s 下被滴灌的响应头 / 响应体在 `超时 + 余量` 内以 `HOST_TIMEOUT` 返回；红孪生：关闭总 deadline 时同一服务端使请求远超超时）、**deadline 定时器的取消记账**（调用方取消在定时器武装期间到达 / 与到期同时 / 到期之后：调用方取消永远胜出且 `cancelling()` 恰为 1；仅到期时 `cancelling()` 回到 0；内层把取消转成其它异常时无残留 `CancelledError`；调用方自己的 `asyncio.timeout` 包住 P6 调用仍工作）；取消请求本身被 head-dribble 时清理墙钟 ≤ 预算 + 余量；输出 P6 task 前后差、耗时、异常类型 / 身份与链、`httpx.Request` / `Response` 存活数、清理 HTTP 请求数、连接池可用性；*claimed-but-not-registered window*、*FAILED recorded while handler may run* 与晚到写入、*normal running cancellation* 正向孪生、*race-DONE*；取消见证对账 O2-5（无取消 `POST` + `TERMINAL_FAILED_OBSERVED` ⇒ FAIL；精确 id 取消 + `failed` / `done` ⇒ PASS；取消未确认 ⇒ `UNCERTAIN_NO_RESPONSE`；确认后见过非终态 ⇒ `UNCERTAIN_NOT_TERMINAL`）；**取消归属交错 R1–R11**（第 10.2 节 O1–O5，逐步记录外部取消次数 / 内部 deadline / `cancelling()` 前后 / `uncancel` 调用 / 异常 / 定时器句柄 / 残留挂起取消，三个破坏归属的红孪生，Python 3.11 / 3.13 差异记录）；**故障网络独立性与接缝撤销后的验收能力**（第 22.5 节，C3-1..C3-7）；**不测试任意注入的吞取消传输**——R5-11 方案 A（治理授权，仅设计修订）把该参数从公共 API 移除，故障由回环代理注入；该反例仅可经进程级猴子补丁复现，作为**信息项**记录（不计入通过标准）；**致命 `BaseException` 采用 F3**（同一实例，边界所有权，第 10.5 节；**抛出方植入的 `args` / `__dict__` / `__notes__` 四个用例保留，标 `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS` 并逐项说明 payload 来源 / 凭据归属 / 注入点 / 受支持边界 / 实际可达性 / 预期裁决，不重命名为 PASS，不标 X-NARROW PASS**）：**穷举窗口探针（`window_probe.py`）**——两种中断模型（任一字节码 / CPython 检查点）× 四个出口（直接 client、`aggregate`、两者的正常路径）× k = 1 / 2 / 3，每次运行后对到达调用方的对象做独立审计；**帧安全红绿孪生（R5-CL-01 / R5-GOV-01；`frame_safety.py` 15 项 × 正常 GC 与 `gc.freeze()`，Python 3.11.0 … 3.14.7 全部解释器；红孪生 = 上一版 `gc.get_referrers` 判定，`gc.freeze()` 下本包挂起帧的 `finally` 被执行；Reviewer C 的 `frameclear.py` / `liveness.py` 原样运行作独立基线；静态守卫 `fatal_path_guard.py` 16 个变异）**；**审计事件暴露（R5-NEW-01；Reviewer C 的 `audit_getframe.py` 原样运行 + 派生 `audit_f3.py`，公共 client 与 `aggregate` 两条出口，本包触发的 `sys._getframe` / `gc.*` 事件 = 0，暴露凭据的事件 = 0）**；**逐层所有权证明与边界入口场景（`ownership_proof.py`，11 项，断言敏感引用不可达 + 残留的本包帧只能是无敏感局部的边界帧；变异使 9 项变红）**；**审计完备性（R5-EV-01；`reach_selftest.py` 10 项：非 canary 正向对照 + 负向对照 + 变异）**；**Reviewer C 真实信号 fuzz `fuzz_fatal.py`（失败路径 / 正常路径；数字见证据包，不是绝对证明，B2）**；**C 级槽位红绿孪生**（`AttributeError.obj` / `OSError.filename` / `ImportError.path` / `StopIteration.value` / 嵌套链；R5 草案的审计器对它们为盲区）；**Reviewer C 的原始 `f3_window.py` / `f3_cslots.py` / `race.py` 逐字节保留并在 R5 草案上复现**；受支持依赖矩阵与静态扫描（`dep_matrix.py`）；5 个第三方注入点 × `KeyboardInterrupt` / `SystemExit`（可行处加 `GeneratorExit`），红孪生（F1）可达 ≥ 2 条路径、F3 为 0，链成员（`httpx` 异常 / 含 token 文本 / 普通异常）保留与切断，`args` / `__dict__` / `__notes__` / 类型逐项不变，净化失败与第二个致命异常的传播，`asyncio.TaskGroup` 对照；**R1 / x-06 取消 / 终态网络见证**（第 14.4 节 O2-5 / 4.7）：绿——精确 id 取消后 `200` 确认并观察 `failed` / `done`、取消未确认 ⇒ `NO_RESPONSE`、确认后无成功观察 ⇒ `OBSERVATION_FAILED`、确认后见过非终态 ⇒ `NOT_TERMINAL`（真实回环宿主 + 独立代理账本）；红——取消 `POST` 无已送达 `200` 却自称 confirmed、无终态 `GET` 却自称 `TERMINAL_*`、`GET` 用错 id、`GET` 返回 `running`、`GET` 早于确认、仅有 P6 自报告字段而无代理事实（Gate D：`gateD_r1.py`；变异 M6-65） | `test_amane_batch_cancellation.py` |
| E6-10 | 并发与账本（唯一规范 = 第 14.4 节与第 20.5 节）：O1 / O2-1..O2-8 / O3 / O4；**分段流式验证**——测试工具在记录被丢弃前取走并重建全历史，覆盖 `19999 / 20000 / 20001` 条记录、历史峰值 > 窗口峰值（例如历史 4、窗口 1）、代理仍保留早期 `POST` 而 P6 窗口已丢弃对应记录、缺口 ⇒ `NOT_VERIFIED`；**R5-03**：H3 已送达而 H4 缺席（取消 / 致命落在 H3→H4 窗口）合法且 H3 之后无任何请求，把 H3 当作授权取消的实现变红；**R5-04**：在途快照五场景（`BEGUN` / `ATTEMPTED` / `CONFIRMED` / 清理中 / 多阶段混合）与“任何时刻 / 仅静止”不变量分开断言，对在途快照断言静止不变量的变体变红；**R5-05**：乱序完成（后开始者先完成）下 `completion_seq` 稠密、收集器以 `completion_seq` 为游标、`seq > last_seq` 非法、20000 溢出、不可恢复缺口 ⇒ `NOT_VERIFIED`；重复显式 `retry_failed` 与 ORPHAN-M1 在乱序下仍成立；`Z` 与由 `W` 求和在 `overflowed == False` 时必须相等、`overflowed == True` 时只有 `Z` 权威；`attempt_id` 在溢出后仍不可能复用（`seq` 稠密）；pre-proxy 取消 / 致命（`POST` 数 0、`Mf` 已声明）通过，未声明的“0”失败；**强制 `ORPHAN-M1`**（M = 1）；oracle 自检；完成顺序反转 / 慢 / 失败 / 取消下不变；门面并发（一个 `preview` 运行时第二个合法调用被 P4 拒绝且零次 `POST /api/tasks`；非法参数 ⇒ `AmaneBatchInputError`；绕过 P4 的变体变红，M6-20）；**R1-05..R1-09（Reviewer x）**：**x-02** H3 / H4 时序矩阵（第 14.4 节 4.6：H3 之前超时、迟到 `202`（`late`）、H3 后重置 / 中断、H3→H4 取消 / 致命、reader 拒绝、正常 H4；合法歧义 `H2 = H3 = TRUE, H4 = FALSE, outcome = TIMEOUT, Submission = UNKNOWN, 无后续请求` 为绿，伪造 H4 / 迟到写入当作 P6 已读 / UNKNOWN 之后的请求 / 经代理获知的 id 为红）；**x-03** `Z` / `W` / `InFlight` 三个统计域（强制用例 `W = []`、`completed = 0`、`in_flight = 1`、`ATTEMPTED`、`Z.submitted = 1` 为绿，“仅完成记录求和”变体为红；四类不变量分开；`Z` 内部恒等式在溢出后仍可验证）；**x-04** 两个序号空间（`seq` / `completion_seq`；`seq = 2` 先完成、随后超过 20000 条并 FIFO 丢弃；已保存历史绿，缺失 ⇒ `NOT_VERIFIED`；不得用 `highest_dropped_*` 水位推断归属，不得静默忽略代理账本里的早期 `POST`）；**x-05** 全局界限与收集器（`seq > last_seq` 红、同一 `completion_seq` 绑定不同记录红、同一记录重复取走绿、合法乱序绿、溢出且历史完整绿、溢出且历史缺失 `NOT_VERIFIED`；快照上界、`completion_seq` 唯一与稠密、冲突检测、保留窗口与已采集历史交叉校验、溢出前后一致）；**x-06** 见 E6-09。验证器为三态 RED / NOT_VERIFIED / GREEN；对 R5 验证器逐一复现缺陷（`gateD_r1.py` 在同一实时账本上同时运行 R5 与 R1 验证器），对 R1 验证器的 10 个单缺陷变异全部变红（`counterfactuals_r1.py`）；Reviewer x 发现的 oracle 漏检不得仅靠改预期输出闭合 | `test_amane_batch_concurrency.py` |
| E6-11 | **真实宿主纵向门**：≥ 10 个 FC2，HOST-A-SRC 与 HOST-B-SRC 各一次，完整链（scan → … → BatchPreview → summary） | `tools/run_amane_batch_gate.py` → `P6_C1_HOST_MATRIX.json` |
| E6-12 | 真实宿主失败矩阵：来源降级仍可用；整体失败；混合；宿主任务 FAILED；宿主 API 传输失败；图片部分失败；坏 / 缺 metadata（经代理改写）；精确的条目隔离 | 同上 |
| E6-13 | 真实宿主重试（任务数由脚本历史 `calls(N)` 决定，第 14.4 节 4.5 用例表）：一次初始 + 一次重试；一次初始 + 两次显式重试；两次独立 generation=0 预览；单 aggregate 自动重复 `POST`（红）；`CREATION_UNKNOWN` 之后显式重试（宿主任务数 ∈ [1, 2]）；用不同 `attempt_id` 隐藏第二次提交（红）；`attempt_id` 复用（红）。仅失败子集被选中、成功条目不重跑 | 同上 |
| E6-14 | 真实宿主取消：准入前、运行中、终态已观察（`TERMINAL_*_OBSERVED`）、不确定（代理丢弃取消响应）、旁观任务未受影响；*claimed-but-not-registered window* 与晚到写入在真实宿主上尽力复现（HOLD 上游 + 立即取消），无法稳定复现则以替身证据为准并在 evidence gaps 中如实标注，**不得**因此写“已停止” | 同上 |
| E6-15 | 真实宿主确定性：完成顺序反转 → 语义投影 / NFO 字节 / artifact requests / issue 顺序 / summary 相等；上游内容变化 → 投影变化（非空性） | 同上 |
| E6-16 | route ownership 与**值级**内容来源的机械证明（22.3，含 ①–⑦ 七类反事实） | 同上 |
| E6-17 | 安全 canary（R2-02，**整个包**）：保护面 P1–P3 与禁入内容 `F`（第 8.3.1 节）——对第 8.3.1 节第 5 点“强制失败矩阵”中**每一条适用路径**（`AmaneHostCredential` / `AmaneHostConfig` 的非法 ASCII、非 ASCII、空白、超长；`AmaneHostClient` 全部 5 个公共方法的 `401` / `403` / `5xx` / 超时 / 连接失败 / 畸形响应 / 结构超限；`AmaneHostPreflightError` 全部 4 个 reason；`AmaneAggregationEngine` 内部契约错误；`AmaneBatchIntegration` 的非法输入 / retry 拒绝 / 门面转换）递归检查 `__cause__` / `__context__`（visited 集合、深度 ≤ 8）、`args`、`__notes__`、本包栈帧 `f_locals`（浅层）、`str` / `repr` / traceback 文本、审计 / 汇总 / preview，断言 `F` 不出现；所有权对象（credential / config / client / engine / facade）作为不透明节点不遍历，且测试明确区分“新引入的泄漏”与“对象自身持有认证状态”。**红绿孪生**：凭据路径 `try: token.encode(...) except UnicodeEncodeError: raise … from None` 变体判红、纯谓词 + 块外抛出为绿；校验失败时 `token` 形参仍留在本包帧局部为红、已重新绑定 `None` 为绿；`_transport` 内 `raise … from None` 为红；外层 `_call` 帧局部仍持有 `Response` / `Request` 为红；响应的 `files` 字段含 canary 路径时，该路径不出现在任何输出；cookie 不回传；跨源重定向不带凭据；`.netrc` / 环境代理被忽略；TLS 不可降级（自签证书 → `HOST_CONNECTION`，上游零请求）；结构超限响应经真实宿主代理映射为封闭失败且不泄漏响应体；**R3-03**：5 个公共方法 × {连接期取消、等待响应头期取消、流中途取消、请求进行中致命 `BaseException`、带响应体的 5xx、带响应体的畸形 JSON、schema 违规、`HOST_RESPONSE_TOO_COMPLEX`}，以及 engine / facade 的“批量被取消时 HTTP 正在进行”；取消出口为 C5c 的新实例（本包帧干净、无第三方帧），致命异常保持原身份、经异常不可达任何敏感引用（第 10.5 节；**不得**据此声称所有异常路径均无凭据可达——抛出方植入的字段与本包以外的帧不在保护面内，L6-21 / L6-25）；安全证据对致命异常断言**敏感引用不可达**与身份，**不**断言 traceback 不含本包帧；**R5-12**：传输层（第三方或被替换者）在 `httpx.AsyncHTTPTransport.handle_async_request` 之内抛出的**非 `httpx` 异常**（`RuntimeError` / `OSError` 子类 / `ValueError`）⇒ `HostCallError(HOST_NETWORK)`，无 `__cause__` / `__context__`，存活的带 token `Request` / `Response` = 0；去掉 catch-all 的红孪生必须复现泄漏；**测试通过回环故障代理与 `httpx` 补丁点注入，不通过公共 API 的 `transport=`**（R5-11 方案 A）；运行于 Python 3.11 最低 / 最新小版本、3.12、3.13、3.14；**致命异常路径使用边界所有权 + F3 的独立可达性审计（`reach.py` 同类工具；任何带 `Authorization` 的 `Request` / `Response.request` 都算命中，与令牌值无关）**，不再以“第三方帧可达性已披露”作为绿灯依据；`_fatal_scrub` **不得访问任何帧**（无 `frame.clear()`、无 `gc.get_referrers`、无 `sys._getframe`，不得以 `except RuntimeError` 取得通过；R5-CL-01 / R5-GOV-01 / R5-NEW-01）；植入凭据用例按 B1 标 `OUT_OF_THREAT_MODEL`，不得标 X-NARROW PASS | `test_amane_batch_security.py` + 真实宿主 canary |
| E6-18 | 不执行：S6-1..S6-5 三层机检（静态 / tripwire / 文件系统树摘要） | 架构测试 + 宿主场景 |
| E6-19 | `AmaneBatchSummary` 精确计数，并与 P4 `PreviewSummary` 逐项交叉校验；**跨轮（R1-06）**：`ready_round_local` / `per_round` / `cross_round_verified` 精确；用 CLOSED S-10 的 hardlink 反例构造“前轮 READY + 重试轮 READY 实为同一源文件”，汇总在 `rounds > 1` 时 `cross_round_verified == False`，不虚增全局 READY，单轮孪生由 P4 报告冲突 | `test_amane_batch_summary.py` + 宿主场景 |
| E6-20 | 语义 / 运维分离：语义投影中不含任何运维字段 | `test_amane_batch_determinism.py` |
| E6-21 | mutation / non-vacuity：第 24 节全部 65 项 M6-xx 必须使对应门**变红**，且未变异孪生保持绿 | `test_amane_batch_mutation_nonvacuity.py` |
| E6-22 | 全量回归：既有全部套件（adapter / compat（HG-1 之后）/ contract / unit / phase4_acceptance …）通过，**与 Frozen Base 的基线通过数对账**（S1 第一件事是在 `4189b95…` 上记录各目录基线） | HANDOFF |
| E6-23 | 构件同一性：sidecar wheel sha256 == P5 台账 pin；plugin zip 由 CLOSED 构建器产出且 P5 构件零变化 | 宿主矩阵 JSON |
| E6-24 | live-network smoke 记录（第 25 节） | `P6_C1_LIVE_SMOKE.json` |
| E6-25 | 解释器覆盖（R5-10 / 治理附加 A）：项目 `requires-python >= 3.11`（不修改 `pyproject.toml`）。P6 包与其测试在 **Python 3.11 最低小版本（3.11.0）与最新可用 3.11.x**、**3.12**、**3.13**、**3.14** 上运行（受影响测试），并另有 3.11.2 / 3.11.3 并排运行证明 `asyncio.timeout` 缺陷（3.11.0–3.11.2）被设计规避。**3.13 是正式验收项**：设计阶段的探针不等于 P6 实现已通过；S3 若没有 3.13 解释器则该项为 `NOT_RUN`、列入 evidence gaps，并**不作出 3.13 支持声明**。任一受支持版本缺失则明示，不得用已有版本的结果宣布整个 3.11–3.14 范围已实测通过 | HANDOFF |
| E6-26 | 证据 JSON 自洽 + 禁止声明校验（状态只能取第 23.2 节词汇 `PASS` / `FAIL` / `NOT_RUN` / `UNVERIFIED` / `BLOCKED`，后三者不得被统计为 `PASS`，不得被写成 SUPPORTED；坐标级声明；无“durable resume / 已执行整理 / 全版本支持”字样） | `test_amane_batch_matrix_json.py` |
| E6-27 | HANDOFF：Contract 映射、完整 diff scope、命令与输出、evidence gaps、known limitations（L6-xx）、Phase 7 输入；**不得把尚未执行的证据写成已 PASS** | `docs/review/P6_C1_HANDOFF.md` |
| E6-28 | 图片裁剪 / 物化的**非空**验证（R3-08 / R4-09）：在一次性宿主（E6-28 专属例外，第 22.2 节；结束后销毁，生产 P6 仍不访问 `/api/config`）上按第 18 节冻结的 X1 / X2 / X3 正向用例与 C1 / C2 对照执行；必须同时断言 ① 宿主展示 poster **实际改变**为 `/api/resources/<hash>` 且该资源可取回（尺寸 / 比例符合 `poster_ratio`）；② `raw` 不变；③ P6 的 poster / thumb / extrafanart 候选集合、NFO 字节、产物清单与对照组逐项相同；④ 只改 P4 `ImageHttpClient` 的 `MockTransport` 不算证明。展示值未改变 ⇒ `FAIL（NON-VACUITY）` 或 `NOT_RUN`，**不得 PASS**（M6-33）。设计期状态：用例由两个 pinned 版本的 `media/pipeline.py` 推导，**待 S3 阶段在真实宿主上实际执行**，此前为 `UNVERIFIED` | 宿主矩阵 |

### 23.1 声明纪律

* 支持声明只能写：“在 SC-03 / SC-04 上经确定性真实宿主验收”，并按 live smoke 记录单独陈述公网状态。
* 禁止：“支持 v0.15.0 / v0.18.0”（无坐标）；“支持 durable resume / 跨进程恢复”；“已执行 / 已验证真实整理”；“公网已验证”（无 VERIFIED 记录）；
  “P6 保证宿主上无遗留任务”；“任务已停止 / confirmed stopped”（P6 只能报告数据库终态已观察）；“每次尝试恰好创建一个任务”（只有无 `CREATION_UNKNOWN` 且 `CREATION_CONFIRMED` 的番号可断言任务数）；
  “跨轮全局 READY / 无冲突”；“元数据是本任务的不可变快照 / 因果归属于本任务”（只声称读取时刻的字段级插件来源）；“宿主进程上全部 SCRAPE 任务数 ≤ M”。
* `UNVERIFIED` / `ENVIRONMENTALLY_BLOCKED` 不得出现在支持声明里。

---

### 23.2 证据状态词汇（冻结；Design-R4 / R4-09）

| 状态 | 含义 | 可进入后续阶段？ |
|---|---|---|
| `PASS` | 已在声明的环境里**实际执行**，所有断言（含非空性断言与红绿孪生）成立 | 是 |
| `FAIL` | 已执行，至少一个断言不成立，或非空性断言不成立（例如宿主展示值没有改变） | 否 |
| `NOT_RUN` | 因环境缺失（解释器版本、宿主、网络）未执行；必须写明原因 | 否：不得计为 PASS；写入 evidence gaps，**不得扩大任何支持声明** |
| `UNVERIFIED` | 设计期推导 / 局部探针支持，但对应的真实路径尚未执行（例如 E6-28 在 S3 之前、DNS 线程、连接黑洞地址） | 否：不得计为 PASS；必须出现在 HANDOFF 的 evidence gaps |
| `BLOCKED` | 需要 Governance 裁决（架构或安全权限）才能继续，设计内无合规机制 | 否：停止并上报 |

规则：`NOT_RUN`、`UNVERIFIED`、`BLOCKED` 都**不能**统计为 `PASS`；证据 JSON（E6-26）与 HANDOFF 用同一组词；任何把计划中的证据写成已通过的文字都违反本合同（E6-27）。

## 24. Mutation / Non-vacuity 控制（冻结；每项都必须让门真正变红）

每个控制都有**孪生**：未变异版本运行同一断言必须绿；变异版本必须红。变异在进程内通过替换被测生产函数 / 类实现（共享同一个 oracle），宿主级控制通过门工具的变体运行（退出码非 0）。

| ID | 变异 | 必须变红的门 |
|---|---|---|
| M6-01 | plugin 未加载（卸载 / 禁用） | E6-11 / E6-16：全部条目 METADATA 阶段失败 |
| M6-02 | FC2 route 改为空 / 非 plugin；（单测）还原任务侧归属校验使外来 `field_sources` 被接受 | E6-16 / E6-07 |
| M6-03 | 返回错误号（代理改写 `metadata.number`）；（单测）去掉号等价校验 | E6-12 / E6-07 |
| M6-04 | `DONE` 缺 `metadata_id` 被当作成功 | E6-12 / E6-07 |
| M6-05 | metadata 不满足最低成功（title 空白）被接受 | E6-12 / E6-07 |
| M6-06 | 宿主任务 `FAILED` 被当作成功 | E6-08 / E6-12 |
| M6-07 | 重试意外重跑成功条目（可重试集合包含全部） | E6-13（宿主任务账本计数） |
| M6-08 | 取消错误地取消别人的任务（用 `status` / `type` 的宽泛取消） | E6-09 / E6-14（旁观任务被取消） |
| M6-09 | 提交体带 `media_id` / 路径 / hash | E6-05（请求账本键集） |
| M6-10 | 调用 `execute` / 文件系统执行 | E6-18（tripwire + AST） |
| M6-11 | 并发超预算：一个 aggregate 提交两个任务 / `UNKNOWN` 之后自动再 `POST` / 绕过 P4 预算 / 隐藏 scheduler 或无界 fan-out / 取消响应后提前返回而清理轮询在后台继续（detached）（`ORPHAN-M1` 与“取消被受理后继续轮询”夹具下未变异实现 PASS，这些变体 FAIL） | E6-10 / E6-14 |
| M6-12 | 凭据泄漏进 `repr` / 异常文本；**在任何 `except` 块内 `raise … from None`（`__context__` 仍保留 httpx 异常与 `Authorization`）**；**R3-03**：`_transport` 的 request / response / stream 局部未清理（取消 / 致命时仍在帧里）；`_call` 抛出时仍持有 `body_bytes`；`CancelledError` 原样穿过 httpx 帧（以上均有“已清理”绿色孪生）；**凭据 / 配置校验路径**：`token.encode("ascii")` + `except UnicodeEncodeError: raise … from None`（`.object` 保留 token）、校验失败时 `token` 形参仍留在帧局部；`_transport` / `_call` 帧局部保留 `Request` / `Response`；token 存入异常属性 | E6-17 / E6-03 |
| M6-13 | 启用重定向跟随 / cookie 回传 | E6-17 / E6-05 |
| M6-14 | 取消把“请求已发送”或数据库 `FAILED` 当成“执行已停止”（输出 `CONFIRMED_STOPPED` 类结论，或忽略 claimed-window / 晚到写入） | E6-09 / E6-14（不确定性场景、claimed window、晚到写入） |
| M6-15 | 控制流引入错误文本解析（`"timeout" in str(exc)`） | E6-03（AST） |
| M6-16 | 提交超时后重试 `POST /api/tasks`；或把 `CREATION_UNKNOWN` 折算为 0 / 1 并据此再提交 | E6-08 / E6-13（重复任务） |
| M6-17 | 字段值取自持久化展示列，或把展示列的 `field_sources` / `locked_fields` / `updated_at` 当内容证据（Design-R1 的 E1/E2/E3/R0 做法）：手工覆盖 B 被当作插件内容输出 | E6-07 / E6-16（①②④⑥） |
| M6-18 | `raw` 缺少插件键时回退到展示列，或改读其它 `raw` 键 / 带 `:lang` 的键 / 不校验 `PluginRaw` 结构 | E6-07 / E6-16（⑤） |
| M6-19 | 把 `SubmissionState` 记错（响应丢失记为 `CREATION_CONFIRMED`；`CREATION_UNKNOWN` 记为零任务 / `NOT_ATTEMPTED`） | E6-08 / E6-13 |
| M6-20 | 门面绕过 P4 并发控制（直接对 engine 并发 `aggregate`，或在 P4 busy 时仍发 `POST`） | E6-10 / E6-03 |
| M6-21 | 删除 / 放宽 JSON 结构预扫描（无上限，或改成递归实现，或在 `json.loads` 之后才检查，或计数口径与第 8.4 节不符） | E6-06 / E6-17 / E6-03 |
| M6-22 | 汇总把各轮 READY 相加并在 `rounds > 1` 时声称 `cross_round_verified` | E6-19 |
| M6-23 | 映射把 `source_urls` / `external_ids`、`raw` 的非映射字段或展示列送入 `NormalizedMetadata` / `field_sources` | E6-07 |
| M6-24 | 审计记录组合校验被删除或放宽（正常成功被计入 `abandoned_attempts`；`C == NOT_APPLICABLE` 与 `T` 不一致；`S=UNKNOWN` 记为 `NOT_APPLICABLE`；POST 前致命记为 `UNCERTAIN_CLEANUP_INTERRUPTED`；`CALLER_CANCEL + CONFIRMED` 出现 `UNCERTAIN_SUBMISSION_UNRESOLVED`） | E6-08 / E6-09 |
| M6-25 | 去掉严格键集合校验 `set(raw.keys()) == {plugin}`（插件与外来来源并存的记录被接受；原实现为绿） | E6-07 / E6-16（⑤） |
| M6-26 | `timestamp_relation` 由事件先后而非两个时间戳字符串计算（CASE B / C 返回 `UPDATED_AFTER_FINISHED`），或把标签当作事实用于输出 / 门禁 | E6-07（R3-02 CASE A–D） |
| M6-27 | 取消见证失真：不发取消 `POST` 却报告 `TERMINAL_*_OBSERVED`；`cancel_post_attempted` 为真而代理 0 次且 `C` 不属允许集合；取消请求的 task id 不是自己的 | E6-09（代理对账 (a)–(d)） |
| M6-28 | oracle 自检变异：O2 以 `(番号, generation)` 为粒度；`K` 把 H2（仅被代理转发）的孤儿计入；`K` 在取消响应处截止——这些变异 oracle 必须在对应夹具上与期望不一致；生产侧变体：取消响应后即返回而把清理轮询留给后台 | E6-10 / E6-13 |
| M6-29 | 映射入口在校验之前解引用（先做号等价、先读 `raw[plugin].number`）；混合来源时返回 `NUMBER_MISMATCH`；畸形插件值抛出未处理异常 | E6-07（Gate A 用例与 fuzz） |
| M6-30 | 清理使用 `asyncio.shield` / `asyncio.timeout` / `asyncio.timeout_at` / `asyncio.wait_for`（3.11.0–3.11.2 缺陷）/ `create_task` / `ensure_future`，或在取消返回之后仍有 P6 清理 task 存活；对 task 无界 `await`；Response 关闭用 `shield` | E6-03 / E6-09 / E6-17 |
| M6-31 | 溢出后由保留记录重新求和（计数 / 峰值）；`peak_in_flight` 被窗口峰值取代；丢弃记录时回改累计状态 | E6-10（19999 / 20000 / 20001） |
| M6-32 | `CONFIRMED` 缺 `task_known_event` 仍被接受；事件顺序 / 类型不被校验；`attempt_id` 与 `seq` 不一致或可复用；pre-proxy `POST = 0` 被无条件接受或无条件拒绝 | E6-08 / E6-10 |
| M6-33 | E6-28 在宿主展示 poster 没有实际改变时仍报告 PASS，或只用 `MockTransport` 的 P4 图片获取证明 | E6-28 |
| M6-34 | 取消请求**未确认**却报告 `UNCERTAIN_NOT_TERMINAL`（把 `NO_RESPONSE` 与 `NOT_TERMINAL` 合并）；确认后没有任何成功观察却报告 `NOT_TERMINAL`（应为 `OBSERVATION_FAILED`）；优先级被打乱（先于 `NO_RESPONSE` 判终态） | E6-08 / E6-09 |
| M6-35 | 谓词用字符串比较或 `dict` 查表（真实枚举 ⇒ `KeyError`）；接受字符串替身枚举；非严格 `bool` 的 `cancel_post_attempted` / `cancel_request_confirmed` / `nonterminal_observed`；`cancel="BOGUS"`、`outcome="CANARY-SECRET"`、`TERMINAL_FAILED_OBSERVED` 搭配 `terminal_status="done"` 被接受；可产生状态集合被硬编码为固定数字 | E6-08 |
| M6-36 | H3 已送达而 H4 缺席的记录被判非法，或实现据 H3 向未确认的 id 发送取消 / 轮询请求；`cancel_post_attempted` 在 `S = UNKNOWN` 为真 | E6-10 |
| M6-37 | 对在途快照断言“静止”不变量（`Z.submitted` 与记录求和）；`submitted` 在完成时才递增；`peak_in_flight` 在完成时更新；在途明细缺失 | E6-10 |
| M6-38 | 收集器以 `seq` 连续性判缺口（乱序完成时漏记录 / 误报）；窗口按 `seq` 而非 `completion_seq` 丢弃；`seq > last_seq` 的记录被接受；不可恢复缺口仍报 PASS | E6-10 |
| M6-39 | `map_host_result` 第 7 步不做 URL 卫生；`dropped_url_count` 与实际删除数不符；把宿主展示 poster 的裁剪计入 `dropped_url_count` | E6-07 / E6-28 |
| M6-40 | 清理依赖 `asyncio.timeout` 的取消计数语义，在 3.11.0–3.11.2 上把到期报告为 `CancelledError`；E6-25 不含 3.11 最低小版本 | E6-09 / E6-25 |
| M6-41 | `_transport` 没有 catch-all：非 `httpx` 异常带着含 token 的 `httpx` 帧逃出；或在 `except` 块内构造并抛出 `HostCallError`（`__context__` 携带原异常） | E6-17 |
| M6-42 | 公共构造面保留或新增可注入的传输 / HTTP 客户端 / mounts / event hooks / `_sleep` / `_clock`，并仍声称有界取消已被证明；或在发现取消失败之后把注入传输排除出支持范围而不经授权（R5-11） | E6-03 / E6-05 / E6-09 |
| M6-43 | 去掉总 deadline，只依赖每次 I/O 的 `httpx.Timeout`：响应头 / 响应体 slowloris 使请求远超 `request_timeout`（R5 附加 B） | E6-09（D1 / D2 红孪生） |
| M6-44 | 定时器没有在**每条**退出路径上 `cancel()`（无 `finally`），随后取消一个无辜的 task；或 `fired` 时没有 `uncancel()` 自己的请求、或错误地撤销了调用方的取消计数、或调用方取消与到期竞速时吞掉了调用方取消 | E6-03 / E6-09（D4–D9） |
| M6-45 | 致命异常不做净化（第三方帧保留）；或异常链没有整条切断（含 `httpx` 异常 / 含 token 文本 / 内置异常 C 级槽位的 `__context__` 仍可达）；或净化后的 traceback 仍引用第三方帧 | E6-09 / E6-17（F3 红孪生） |
| M6-46 | 净化抛出的普通异常遮盖了原致命异常；净化期间的第二个致命异常被吞掉；或 `except BaseException` 吞掉了致命异常 | E6-17 |
| M6-47 | 致命路径替换了异常实例 / 改写 `args` / `__dict__` / `__notes__` / 类型 / 添加 note，或发出额外 HTTP 请求 / 创建 P6 task，或改变 `TaskGroup` 对致命异常的处理类别 | E6-09 / E6-17 |
| M6-48 | 内部 deadline 只按 `fired` 判定超时，把外部取消转换成 `HOST_TIMEOUT`；或 `fired` 时不 `uncancel`（取消计数泄漏）；或无条件 `uncancel`（抹掉调用方取消）（治理 Gate C-Final-01） | E6-09（R1–R11 红孪生） |
| M6-49 | 故障网络（`faultnet`）导入或引用被测的生产状态机 / 谓词 / 合同类型，或判定规则写在被测代码里（测试与被测不独立）；或接缝撤销后仍保留 `_clock` / `_sleep` / `transport=` 的等价后门 | E6-03 / E6-05（C3-2 / C3-3） |
| M6-50 | 包内保留测试钩子、模块级可变回调、`TRACE` 开关或环境变量开关，使生产路径可被外部改变取消 / 超时行为 | E6-03 |
| M6-51 | 致命异常的净化只放在 `try` 体的兄弟 `except` 里（够不到 `except Exception` / `finally` / try 之后的窗口）；`_transport` 保留自己的致命处理体而边界帧缺失；公共 client 出口缺边界；边界致命处理体在 `try` 之前调用函数；边界局部持有 `Request`；净化失败遮盖 / 吞掉致命异常；记账不幂等致使致命异常被 `KeyError` 取代（R5-C-01） | E6-03 / E6-09 / E6-17（窗口探针；R5 草案红） |
| M6-52 | 异常链按“允许名单”保留成员（含内置异常的 C 级槽位）；审计器不覆盖 C 级槽位（`gc.get_referents` 之类缺失）；只因为 canary 文本没出现就忽略带 `Authorization` 的 `Request`（R5-C-02） | E6-17（C 级槽位红绿孪生） |
| M6-53 | 取消分类依赖一次 `await asyncio.sleep(0)` 是否抛出，或在 `except CancelledError` 里就地分类：内层把取消转换 / 吞掉时调用方取消丢失或被分类为 `HOST_TIMEOUT` / `HOST_NETWORK`；响应关闭层吞掉外部取消后不再检查计数（R5-C-03） | E6-09（RC10 系列；`race_c_revised.py old`） |
| M6-54 | deadline 定时器武装在受保护区域之外，或回调没有 `active` 标志，或该标志只有 `_transport` 一个所有者（`_call` 的 `finally` 不清除它；Python 3.14 任一字节码探针红），使致命异常落在武装前后任一字节码处留下活跃的定时器去取消无辜 task；`finally` 内先做别的事再撤销 | E6-09 / E6-17（窗口探针 + 泄漏定时器检测） |
| M6-55 | 缺少受支持依赖矩阵守卫：安装版本不在已验证矩阵内仍声称 X-NARROW 的“受支持运行时”；X-NARROW 应用于来源于当前 P6 请求的凭据；或把四个植入用例改名为 PASS / 移出测试 | E6-17 / E6-25（`dep_matrix.py`、矩阵守卫） |
| M6-56 | F3 生产路径对任何帧调用 `frame.clear()`（Python 3.11 / 3.12 上运行了别人的生成器 / 协程 `finally`），或用 `gc.get_referrers` / `gc.get_objects` / `gc.collect` / 全堆扫描判断帧是否结束（`gc.freeze()` 下失效），或为取得通过而 `except RuntimeError` 后忽略，或为避免 `clear()` 而保留敏感的第三方 traceback | E6-03 / E6-09 / E6-17（`fatal_path_guard.py`；`frame_safety.py` ×（正常 GC / `gc.freeze()`）；Reviewer C `frameclear.py` / `liveness.py`） |
| M6-57 | 审计器只在头部含测试 canary 时才报告 `Request`（对非 canary 的 `Authorization` 失明），或不检查 `Response.request` | E6-17（`reach_selftest.py` 变异） |
| M6-58 | F3 生产路径调用 `sys._getframe` / `gc.get_referrers`（二者的审计事件把带 `Authorization` 的 `Request` 的帧作为参数交给审计钩子） | E6-17（`audit_f3.py`；Reviewer C `audit_getframe.py`；`fatal_path_guard.py`） |
| M6-59 | 拥有响应数据的边界帧（`_call` 的 `body` / `obj`）的致命处理体不重绑这些局部，或致命处理体没有脱离 `__traceback__` / `__context__` / `__cause__`（敏感引用经异常到达调用方），或边界帧在入口检查点留下的 traceback 条目持有敏感局部 | E6-09 / E6-17（`ownership_proof.py`，变异 `FATAL_MODE=F1`；另：边界入口检查点留下的边界帧持有敏感局部必须判红） |
| M6-60 | `terminal_status`（或其它 `str` 字段）接受 `UserString` 等可变别名；`record_is_legal` 对 `None` / 错误对象 / 未初始化实例抛出异常、接受鸭子类型，或错误里回显字段内容；只改测试 oracle 而不改模型构造边界（R1-04 / x-01） | E6-08（Gate B：`x01_strict_types.py`） |
| M6-61 | 验证器把 H3 当作 H4（迟到的 `202` 使合法的 `UNKNOWN` / `TIMEOUT` 被判红，或使 `CONFIRMED` / 拒绝类 outcome 被接受）；不检查 `UNKNOWN` 之后的请求或经代理获知的 id 的使用；允许 P6 从代理账本补救未知 id（R1-05 / x-02） | E6-10（Gate D：H3 / H4 矩阵） |
| M6-62 | 由 `W`（仅完成记录）求全历史 `Z.submitted`（在途时误红、溢出后误绿），或缺少 `Z` 内部恒等式 / 把“静止”或“未溢出”不变量当作任何时刻都成立（R1-06 / x-03） | E6-10 |
| M6-63 | 归属用序号水位（`highest_dropped_*`）而不是身份，混用 `seq` 与 `completion_seq` 空间，或静默忽略代理账本里早期的 `POST`（应为 `NOT_VERIFIED`）（R1-07 / x-04） | E6-10 |
| M6-64 | 收集器用 `setdefault` 等方式吞掉冲突；缺少 `seq > last_seq`、`completion_seq` 唯一 / 稠密、计数器单调等全局守卫；要求单条 `record_is_legal` 取代跨记录验证（R1-08 / x-05） | E6-10 |
| M6-65 | `cancel_request_confirmed` 或 `TERMINAL_*` 在没有独立代理事实（已送达的 `200`、精确 id、其后的终态 `GET`）时被接受；伪造的自报告字段被当作网络事实（R1-09 / x-06） | E6-09 |

---

## 25. Live Network Smoke（冻结）

P5-C2 把真实公网 scrape 留给 Phase 6（L-C2-10）。P6-C1 的 evidence 必须包含一次 **live-network smoke 尝试**，且**不得**把外部站点可用性混进确定性正确性门。

* 载体：`tools/run_amane_batch_gate.py --live`，对一个**一次性**的 source host（plugin 使用**默认**公网 base_url，route 为 `["ffcc.fc2-metadata"]`），对
  `docs/acceptance/PHASE3_50_ID_SET.md` 中**按文件顺序的前 3 个号**运行完整的 `preview_root` 链（图片使用真实 `HttpxImageClient`，不用 MockTransport）。
* 记录（`P6_C1_LIVE_SMOKE.json`，允许含时间戳）：状态词表如下。

| 状态 | 条件 |
|---|---|
| `VERIFIED` | 至少 1 个号到达 METADATA 阶段成功（宿主任务 DONE、归属为 plugin、最低成功），并记录 P4 下游条目状态 |
| `UNVERIFIED_ENVIRONMENT` | 宿主已启动，但 0 个号成功；**无法区分**站点 / 网络不可用与缺陷；对应的 live 支持声明**不得扩大** |
| `NOT_RUN` | 无法启动 live 宿主（无网络 / 缺 Python 3.14 / 端口等）；必须写明原因 |

* 禁止：没跑 → PASS；用回环 deterministic 测试冒充公网证据。缺失的 live 证据必须写进 HANDOFF 的 evidence gaps 与 known limitations。
* live smoke 不是 correctness gate：其结果不改变 E6-11..E6-21 的判定。

---

## 26. 不变量（冻结）

```text
I6-01  零 diff：第 5.2 节的闭合范围；本包 import 白名单（6.4）
I6-02  不 import amane / fc2_amane_adapter；不读 Amane 源码、SQLite、日志；不 monkeypatch Amane
I6-03  宿主表面 == 表 H1（5 个操作）；请求体键集精确；绝不含本地路径 / media_id / hash
I6-04  number 在提交前已是 canonical；echo 校验（type / number / content_type）
I6-05  每个进入提交阶段的 aggregate 最多发送一次 POST，POST 永不自动重试；仅 202 + 严格 schema 才是 CREATION_CONFIRMED，其余 CREATION_UNKNOWN 不折算为 0 / 1，也不得成为重新提交的理由
I6-06  每个 active aggregate 最多一个 active 宿主任务；无 fan-out、无隐藏 worker；P6 正在等待的宿主任务数 peak_in_flight ≤ M（不推广为宿主全部存活任务 ≤ M）
I6-07  取消只针对已知 id 的自己的任务；请求体绝不含 status / type；绝不使用 delete / retry
I6-08  取消有界（cancel_budget_seconds）；无分离后台 task；请求已发送（L1）≠ 数据库终态已观察（L2）≠ 执行已停止（L3，永远 UNVERIFIED，无 CONFIRMED_STOPPED）；UNCERTAIN_* 与 abandoned_attempts 显式暴露
I6-09  成功必须同时满足第 11.2 节八项校验（含 raw 中的插件原始记录）；缺一 fail closed，且失败种类唯一
I6-10  唯一 SourceResult source_id == "ffcc.fc2-metadata"；永不产生 PARTIAL；永不伪造 trace / 内部来源 provenance
I6-11  field_sources 值 ⊆ contributing_source_ids == ("ffcc.fc2-metadata",)；输出的每个字段值只来自 raw["ffcc.fc2-metadata"]（值级证据），不来自展示列；source_urls / external_ids 恒为空
I6-12  所有控制逻辑只基于 HTTP 状态码 / 枚举 / 结构化 schema / 异常类型；绝不基于文本
I6-13  error_detail 是封闭词汇；不含 URL / 宿主文本 / token / 任务 id
I6-14  凭据：显式注入、redacted、不可序列化、不落盘；整个 src/fc2_amane_batch/** 抛出的异常及输出文本（保护面 P1–P3）不新引入禁入内容 F（token 及其子串、httpx Request/Response/HTTPError、UnicodeError.object、响应体），经 __cause__ / __context__ / args / __notes__ / 本包帧 f_locals 浅层均不可达（from None 不算证明）；承诺不涵盖调用方持有的 credential/config/client/engine 对象自身所含的认证状态（所有权状态）；无 cookie jar 持久化；无环境代理 / netrc；无重定向；TLS 不可降级
I6-15  响应流式读取且字节、深度、节点数、集合项数均有上限（MAX_RESPONSE_BYTES / MAX_JSON_DEPTH / MAX_JSON_NODES / MAX_JSON_COLLECTION_ITEMS）；严格 reader；未知额外键容忍但同样受结构上限约束、必需键缺失 fail closed；超限为封闭结构化失败
I6-16  语义输出确定；运维输出（task id / 时间 / 计数 / 随机标识）永不进入语义输出
I6-17  P6 只拥有重试 eligibility / 子集选择，P4 独占重试执行 / 调度 / 并发；retry_failed 仅选择子集并调用 P4 preview；永不重跑成功条目；无自动重试循环
I6-18  无 durable resume / checkpoint / 持久化 / 跨进程锁；审计账本有界
I6-19  不执行：S6-1..S6-5
I6-20  不修改用户 Amane 配置；生产代码零 /api/config 访问
I6-21  门面 preflight 在任何任务被创建之前失败（整批前置条件）；“零副作用”仅指不创建 SCRAPE / 其它任务、不修改业务数据（宿主访问日志不在声明内）
I6-22  本包零 logging、零文件 API、零环境变量读取
I6-23  AmaneBatchPreview 不可变；其轮次中的 BatchPreview 是 P4 原对象（不复制、不改写）
I6-24  普通条目失败不拖垮其它条目；致命 / 取消保持 P4 现有语义
I6-25  值级内容来源：输出字段值只由 raw["ffcc.fc2-metadata"] 确定性派生（展示列、持久化 field_sources / locked_fields / 时间戳都不是内容证据）；保证范围仅为“读取那一刻的插件原始记录”，不声称任务独占或不可变快照（11.3.4）；timestamp_relation / display_title_diverged 只是审计提示
I6-28  审计记录的 S/T/C/R 四维组合及事件 / 标识必须满足第 10.3.1 节的谓词 `record_is_legal`（唯一定义）；abandoned_attempts / uncertain_cancellations / creation_unknown 按第 10.3 节口径精确计数，正常成功与未取消的失败不计入
I6-29  并发 oracle 区分 A / K / H：|A| ≤ M，|K| ≤ |A|；不要求 |H| ≤ M；独立 POST 账本以 attempt_id 证明每个 aggregate attempt 至多一个 POST（不是每个 (番号, generation)）
I6-30  成功的 raw 键集合恰好是 {ffcc.fc2-metadata}；缺失 / 只有外来 / 混合 / 语言后缀 / 未知键 → HOST_ATTRIBUTION_FOREIGN
I6-31  attempt_id = e{engine_index}-a{seq}，随该 aggregate 的全部宿主请求发送（X-FFCC-Attempt）；已知 id 的事件 H1–H4 不得混用，K = [task_known_event, end_event)，取消响应不是退出事件
I6-32  _transport / _call 在所有退出路径（含 CancelledError 与致命 BaseException）上本包帧不持有 httpx 对象 / 响应体 / token；CancelledError 出口为同类型新实例；致命异常原样传播（同一对象），经异常不可达任何敏感引用（F3，第 10.5 节；L6-21）
I6-33  timestamp_relation 只是两个时间戳字符串的比较标签，不得由事件先后推断，不得改变语义输出
I6-34  映射入口只有一个定义（11.2 代码块）：校验顺序 reader → 键集合 → PluginRaw → 号等价 → 映射 → 最低成功；任何字段在前置校验通过前不被解引用；任何输入恰有一个分类且不抛异常
I6-35  清理在 aggregate 自己的 task 内联执行；包内无 shield / create_task / ensure_future / gather / TaskGroup / run_in_executor / to_thread / threading；每个等待有界；二次取消停止一切后续 I/O；致命异常零清理 I/O 且原对象原样传播
I6-36  任务基数由独立调用脚本的实际操作历史 calls(N) 决定；重复显式重试合法；单 aggregate 自动重复 POST 非法
I6-37  审计分累计状态 Z（在线更新、精确）与保留窗口 W（≤ MAX_AUDIT_RECORDS）；溢出后只有 Z 权威；全历史验证靠分段流式取走，缺口 ⇒ NOT_VERIFIED
I6-38  HostAttemptRecord 的合法性只有 record_is_legal 一个定义；其接受集合等于独立参考模拟器产生的记录集合（63 条，由模拟器计算，不预设）；谓词对任意输入返回 bool，不抛出，接受真实枚举
I6-39  审计 Z 在 begin / POST 交给传输层之前 / 完成三个更新点在线更新；在途快照与静止快照的不变量分开；窗口按 completion_seq FIFO；乱序完成下收集器以 completion_seq 为游标，缺口 ⇒ NOT_VERIFIED
I6-40  CancelOutcome 共 10 个成员；NO_RESPONSE ⇒ 取消请求未确认；NOT_TERMINAL ⇒ 已确认且见过非终态；OBSERVATION_FAILED ⇒ 已确认且无成功观察；严格优先级
I6-41  map_host_result 第 7 步做 P5 I22 URL 卫生并精确计 dropped_url_count；展示 poster 裁剪不进入该计数
I6-42  _transport 的异常分类封闭完备：非 httpx 异常 ⇒ HOST_NETWORK，只在 except 块内记枚举值，块外抛出，无 cause / context；包内不使用 asyncio.timeout / timeout_at / wait_for
I6-43  每个宿主请求有定时器强制的总墙钟 deadline（loop.call_at，finally 撤销；fired 时恰好 uncancel 一次；调用方取消永远胜出且计数不被改动）；不依赖 asyncio.timeout 的内部计数
I6-44  致命 BaseException 保持同一对象（F3）：只切断暴露面（traceback 与异常链的引用全部脱离，经异常不可达任何敏感引用；至多留下无敏感局部的边界帧；生产路径不访问任何帧）；args / __dict__ / __notes__ / 类型不被读取或修改；净化失败不遮盖、不吞掉致命异常；公共构造面没有任何传输 / 客户端 / sleep / clock 注入点
I6-45  致命异常由边界帧的内联致命处理体处理（持有响应数据的边界先重绑局部，再 try 引用脱离，失败时内联属性赋值，再裸 raise）；_transport 没有致命处理体；边界局部不持有凭据；异常链整条切断；取消归属在一处按计数分类（cancelling() > base ⇒ 外部取消，即使内层转换 / 吞掉）；定时器武装在受保护的 try 内且回调受 active 标志约束
I6-26  门面调用顺序冻结（9.5）：本地校验 → preflight → P4 公开 preview；busy claim 只在 P4 入口；门面不复制 P4 锁、不绕过 P4 并发控制、不承诺零网络访问或 busy 优先级
I6-27  每个 BatchPreview 的 READY / 冲突结论仅对本轮有效；P6 不提供跨轮全局 READY 保证；汇总区分逐轮计数与 cross_round_verified
```

---

## 27. 已知局限（如实记录；进入 E6-27）

| ID | 局限 |
|---|---|
| L6-01 | **独占来源前提**（H6-1）：P5 INSTALL 把 plugin 放在 FC2 route 最前并保留原站点；P6 需要其它站点不再贡献字段。当前统一的来源保证由三部分组成（**不是**“逐字段双侧证据”）：① 任务侧 `field_sources` 全部为插件且含 `title`（独占 route 的**必要条件**）；② `raw` 的键集合**恰好**是 `{ffcc.fc2-metadata}`（独占来源的**验收**）；③ 字段值只来自 `PluginRaw`（**内容值证据**）。展示列的 `field_sources`、字段锁、时间戳不是内容来源的证明，E1/E2/E3/R0 不得重新启用；审计里的 `failure_counts` 用于诊断 |
| L6-02 | 非回环主机必须 `https`；不支持明文局域网、自定义 CA、代理、路径前缀；回环可用 `http` |
| L6-03 | 遗留任务：`CREATION_UNKNOWN`（提交歧义，含 401 / 超时 / 响应丢失 / **取消落在 POST 在途期间**）、`abandoned_attempts`（`UNCERTAIN_*` 与 `TERMINAL_*_OBSERVED`）、进程退出，都可能在宿主上留下仍在运行或排队的 SCRAPE 任务，**它们的执行协程可能继续写 Metadata 并占用宿主 worker 并发**。R4 取消了“取消后等待在途 POST 的响应以取得 id”这一步（它需要游离 task），因此 POST 在途期间被取消必然记为 `CREATION_UNKNOWN`，孤儿概率上升——这是不使用 detached 清理 task 的、据实接受的代价；P6 不找回、不跨进程清理（无持久化） |
| L6-04 | **取消只证明数据库记录，不证明执行停止**（R1-04）：DIFF-P6-01 / DIFF-P6-05 —— v0.15.0 在“已认领、协程尚未登记”（含信号量等待）的窗口内取消会把记录改成 `FAILED` 而协程继续运行；v0.15.0 的无条件 `fail_task` 还可把“恰好完成”的任务改写成 FAILED（“Cancelled by user”），此时 Metadata 可能已被写入；v0.18.0 窗口更小但无法证明不存在。P6 的 `TERMINAL_FAILED_OBSERVED` / `TERMINAL_DONE_OBSERVED` 因此都不是“已停止”，每次放弃的 L3 都是 `UNVERIFIED`，晚到的 Metadata 写入不可排除 |
| L6-05 | 无法区分“番号在所有来源都不存在”与“来源 / 宿主故障”（宿主只给 `failed` + 文本；不解析文本）；统一 `HOST_TASK_FAILED` |
| L6-06 | **用户的 Amane 配置与手工编辑不流入结果**（R2-01）：LLM 翻译、FacetRule 规范化、Resource 物化 / 海报裁剪、用户在 Amane 里手工编辑、字段锁、merge 选择都只作用于展示列，P6 的输出只来自插件的原始记录 `raw["ffcc.fc2-metadata"]`；若用户期望“Amane 中编辑后的标题”进入 NFO，P6-C1 不支持。展示列与 `raw` 的 `title` 不同时只在审计里置 `display_title_diverged`，不失败也不改变输出 |
| L6-07 | 宿主排队时间计入 `aggregate_deadline_seconds`；Amane 宿主 worker 并发的**缺省是 10**（`WorkerConfig.concurrency`，两个版本；验收宿主若明确配置其它值则以实际配置为准）；M 大于宿主实际并发、或被遗弃的孤儿任务占用并发时，任务会排队；P4 并发 M 与宿主并发是两个独立的数。**P6 只保证 `\|A\| ≤ M` 与 `\|K\| ≤ \|A\|`，不保证宿主上与本批相关的全部任务数 `\|H\| ≤ M`**（孤儿任务可使 `\|H\| > M`，第 14 节） |
| L6-08 | SCRAPE 会 **upsert 宿主 Metadata 库**：P6 的 preview 对用户**媒体 / library 文件系统**只读，但对 **Amane 数据库不是只读**；宿主可能扇出 `ACTOR_SCRAPE` 后继任务（`actor_scraping.auto_scrape` 缺省 True），P6 不跟踪也不取消 |
| L6-09 | 重试只覆盖 METADATA 阶段失败；图片候选级部分失败是警告，不重试 |
| L6-10 | **宿主展示裁剪与 P6 无关**（R3-08 / R5-09）：Amane 的 `crop_poster` / Resource 物化只改展示列，不改 `raw`；P6 的图片候选来自 plugin `raw` 的原始 URL，同一上游内容在不同宿主裁剪 / 物化配置下候选集合相同；展示 poster 的裁剪**不**进入 P6 的 URL 过滤，`dropped_url_count` 只计 `PluginRaw` 里被第 11.2 节第 7 步删除的元素。P4 的 `POSTER_ABSENT` / `FANART_ABSENT` / 候选级警告只可能由原始 URL 缺失、不合法或图片获取失败引起，不得归因于宿主展示列的裁剪 |
| L6-11 | 公网证据可能是 `UNVERIFIED_ENVIRONMENT` / `NOT_RUN` |
| L6-12 | SC-01 / SC-02（冻结桌面）可选；macOS / Linux / Docker `UNVERIFIED` |
| L6-13 | `use_cache=[]` 强制刷新：对来源站点的请求量更大，每次运行都会重写宿主 Metadata |
| L6-14 | 无 progress API，不使用 WebSocket |
| L6-15 | 号等价按 Core `normalize_fc2_number`；用户宿主里以非常规写法保存的旧行会被等价接受（映射后一律是请求的 canonical） |
| L6-16 | 重试由调用方显式驱动，最多 `MAX_RETRY_ROUNDS = 16` 轮；多轮视图不能作为单个 `BatchPreview` 执行（Phase 7 逐轮执行）；**跨轮 READY / 冲突无全局保证**（R1-06）：不同番号可共享同一个 hardlink 源文件或目标，单轮 preview 看不见别的轮次，Phase 7 若跨轮执行必须对合并范围重新验证源身份与目标冲突 |
| L6-17 | P5 已记录的局限继续成立（C1 L-01..L-15、C2 L-C2-01..16），尤其 L-C2-13（sidecar 的 admission-time integrity，不是 runtime immutability） |
| L6-18 | **内容来源的保证范围**（R2-01，第 11.3.4 节）：P6 声称“输出值完全由 Amane `raw` 中插件的原始记录确定性派生，而公开 PATCH / 字段锁 / merge 不能改写 `raw`”；**不**声称：① 该 `raw` 是刚完成的这个任务独占写入的——并发的同号插件 SCRAPE（含遗留孤儿任务）可在任务完成后整体替换 `raw`，内容仍是插件的一次独立抓取，证据上无法与本任务区分；② Amane `raw` 与插件 Core 输出逐字节相同（S1 第 0 步用确定性夹具核对，不符 ⇒ U6-6）；③ 防住对 Amane 数据库的直接篡改或 Amane 自身缺陷；④ `raw` 的形状在 v0.15.0 / v0.18.0 之外的版本上成立。`source_urls` / `external_ids` 恒为空（NFO 不读取它们） |
| L6-19 | `timestamp_relation` 只是两个时间戳字符串的比较标签，**不是**记录是否被修改的事实，也不是因果证明：墙钟回拨会使“任务之后的写入”得到 `updated_at ≤ finished_at`，同一时刻精度会掩盖先后，任务内部“写入 → 标 done”之间的极短间隔内他人的写入不可分辨；时间戳缺失 / 不可解析 / 时区或精度不一致时为 `INDETERMINATE`。它不改变语义输出，也不得被当作字段来源的唯一或充分证据 |
| L6-20 | 当 P4 已忙时，被拒绝的门面调用可能已完成本地校验与一次只读 preflight `GET`（第 9.5 节）：不声称零网络访问，也不承诺 busy 与参数错误之间的全局优先级；宿主可能记录 preflight 的访问日志 |
| L6-21 | **致命异常（F3 + X-NARROW）的边界**（R3-03 / R4-02 / R5 治理附加 / R5 安全闭合）：`CancelledError` 由包内以同类型新实例替换（C5c）；**致命 `BaseException`** 保持**同一对象**，由各层拥有者重绑自己的敏感局部，并由边界帧把 `__traceback__` / `__cause__` / `__context__` 置 `None`（确定性所有权清理 + 异常引用脱离；不访问、不清理任何帧，不终结挂起的协程；第 10.5 节）。对 **P6 自行产生与第三方帧产生**的暴露，设计探针上 **IMPLEMENTED CANDIDATE**（穷举窗口探针 + C 级槽位红绿孪生 + 5 个第三方注入点，红孪生 F1 可达 ≥ 2 条路径，F3 为 0）；**抛出方植入致命异常自身字段的当前 P6 凭据 = `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`（B1），F3 不改写，可达性保留**（L6-25）；上述都**不是**独立安全复核的 PASS。F1 与 F2 均**未被治理接受**。**不得**把本包的保证解释成“所有异常路径上都没有凭据可达”：抛出方放入 `args` / `__dict__` / `__notes__` 的内容、本包以外的帧（P4 worker、调用方）不在保护面内 |
| L6-22 | 并发 oracle 的观察范围（R3-05 / R4-05）：代理账本是**代理自己的观察**（H2 / H3），不等同于 P6 已收到的信息（H4）；O3b 只能发现经 HTTP 可见的区间重叠；20 ms 宿主采样是离散采样；`CREATION_UNKNOWN` 的孤儿 id 不归类为 `K`，也不用于 `\|H\|` 断言；全历史验证依赖测试工具在窗口丢弃前取走记录（缺口 ⇒ `NOT_VERIFIED`） |
| L6-23 | **清理有界性的证据范围**（R4-02 / R5-07；与第 10.2 节第 8 条的状态表一致，**分别标注，不混用状态词**）：生产 `httpx` 设计探针（Python 3.11.0 / 3.11.1 / 3.11.2 / 3.11.3 / 3.11.9 / 3.12.10 / 3.13.0 / 3.13.9 / 3.14.7）**PASS**；P6 实现在 3.13 上的验收 **NOT_RUN**（E6-25 在 S3 必须运行）；DNS 解析线程 **UNVERIFIED**；3.11.0–3.11.2 的 `asyncio.timeout` 缺陷**已复现并由设计规避**；任意注入的吞取消 `transport=`：**方案 A，APPROVED FOR DESIGN REVISION ONLY（治理裁决）——DESIGN UPDATED**（第 10.6 节；该参数已从公共构造面移除，反例仅可经进程级猴子补丁复现，作信息项记录）。这些项不得合并成一个无条件的 PASS |
| L6-24 | **F3 的代价与残余**（第 10.5 节）：① traceback 保真度降低——致命异常原始抛出点（第三方帧、用户钩子帧的文件 / 行号 / 局部）**以及本包的内部帧（`_transport` / `_run` / `_cleanup`）**都不再可见（到达调用方的 traceback 至多留下无敏感局部的边界帧；实测，九个解释器）；② 链保真度降低——**整条** `__context__` / `__cause__` 被切断；③ **调试器 / trace 在任意字节码处注入、数量无界的假想模型 = `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`（B1 / B2）**：公共 client 路径有两层边界，探针构造了一个具体反例（传输层第一个异常、`_call` 处理体入口第二个、`call` 处理体入口第三个），它需要 `sys.settrace` 的主动注入；真实信号只在 eval-breaker 检查点投递，内联嵌套 `try` + 原子属性赋值使保证对检查点模型成立（k ≤ 3 穷举，k > 3 为结构论证，未穷举）；真实信号 fuzz 只是旁证；**不改变进程级 `SIGINT` 策略**；④ 抛出方放入 `args` 的凭据对象不被改写（独立载荷 X-NARROW；当前 P6 凭据的植入用例 = OUT_OF_THREAT_MODEL）；⑤ 帧不被清理、不被枚举（R5-CL-01 / R5-GOV-01）：仍被第三方持有的第三方帧由其所有者管理；F3 不使用 `gc` 或 `sys._getframe`（R5-NEW-01）。缓解候选“审计记录附带封闭格式的抛出点摘要”未采用（需扩展记录与谓词）。这些是已披露的残余，不是通过项 |
| L6-25 | **致命异常的 `args` / `__dict__` / `__notes__` 由抛出方拥有——方案 X-NARROW**（R5 治理附加 / 安全闭合；第 10.5 节）：P2 对它们只断言“本包没有新增、没有修改”。Gate C 的四个植入用例（`args` 含 token 文本、`args` 含带 `Authorization` 的 `Request`、`__dict__` 含 `Request`、`__notes__` 含 token 文本）**保留**，逐项记录 payload 来源 / 凭据归属 / 注入点 / 受支持边界 / 实际可达性 / 预期裁决：它们的凭据都取自**当前 P6 请求**，条件 2 不满足，**不能按载荷豁免，不标 X-NARROW PASS**；其注入点（`httpx` `event_hooks`，需要私有属性 `_http` 或进程级补丁）要求主动的进程内篡改，**标 `OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS`（B1）**，可达性保留且不被改写。Y（只检测）与 Z（改写参数）继续 REJECTED。若将来出现任何受支持的方式让外部代码在 P6 请求路径上运行，这四个用例必须立即重新归类为 BLOCKED |
| L6-26 | **总 deadline 的上界是墙钟近似**（R5 治理附加 B）：上界 = 请求超时 + 一次事件循环迭代 + 本地套接字关闭；事件循环被同线程的阻塞代码长时间占用时不成立（这对任何 asyncio 超时都一样）；DNS 解析线程（`getaddrinfo`）仍为 UNVERIFIED。Gate 的 0.45 s 调度余量是测试容忍度，不是产品保证 |
| L6-27 | **受支持依赖矩阵**（X-NARROW 条件 3）：已验证 `httpx==0.27.2`、`httpcore==1.0.9`、`anyio==4.15.1`、`h11==0.16.0`、`sniffio==1.3.1`；`httpx>=0.27,<0.28` 不代表 `httpcore` / `anyio` 可以未经核验地变化。S1 的矩阵守卫在安装版本不在矩阵内时把 X-NARROW 的受支持运行时声明降为 `UNVERIFIED` 并要求重新运行扫描与 Gate C；本设计不修改 `pyproject.toml` |
| L6-28 | **穷举探针的覆盖范围**：探针对包内函数的每个字节码注入（任一字节码模型，比 CPython 的真实投递更强）；对第三方库内部的 C 代码 / 第三方字节码不注入（它们的帧在边界切断引用后无引用者，随引用计数释放，从不被清理）；正常路径出口在每第 4 个字节码上做 k = 2 抽样（每次运行都轮询真实宿主）。证据包保留全部脚本与原始输出，供独立复核者自行构造场景 |
| L6-29 | **B1 进程内信任边界**（第 10.5 节）：P6 不对同进程恶意代码（`gc` / 帧内省、猴子补丁、私有属性改写、trace / profile、任意异常注入）隐藏凭据——`gc.get_objects()` 即可找到飞行中的带 `Authorization` 的 `Request`（Reviewer C `inproc_reach.py`），记录为实际可达性。B1 不排除正常公共 API 使用、受支持依赖、P6 自身泄漏、普通信号、正常取消 |
| L6-30 | **B2 异步致命异常投递边界**（第 10.5 节）：保证只覆盖有运行时证据的范围（检查点模型 k ≤ 3 穷举；任一字节码模型 k = 1 穷举、更高 k 分层 / 抽样；真实信号 fuzz 旁证，不是绝对证明）；调试器 / trace 任意字节码注入 = `OUT_OF_THREAT_MODEL`；不改变进程级 `SIGINT` 策略 |

---

## 28. 升级门 / 停止条件（出现任一项必须停止并上报，不得在普通施工中自行解决）

```text
U6-1   需要修改任何 CLOSED production 语义 → AUTHORITY ESCALATION REQUIRED（列出 package / 原因 / 影响 / 兼容 / 安全 / 回归范围）
U6-2   需要调用 execute / ORGANIZE / TRASH，或修改用户文件
U6-3   需要任何持久化 / durable resume / checkpoint / 跨进程锁
U6-4   需要表 H1 之外的 endpoint，或需要版本分支 / feature detection
U6-5   需要读取 / 修改 Amane 配置，或解析宿主日志 / 错误文本 / 异常消息
U6-6   真实宿主观测与第 7 节的事实不一致（出现 DIFF-P6-01..05 之外的差异；含：`raw["ffcc.fc2-metadata"]` 缺失或与插件 Core 输出（确定性夹具）不等价、`MediaMetadata` 形状与 11.3.3 不符、公开 `PATCH` 竟能改写 `raw`、成功 SCRAPE 的任务 `field_sources` 缺 `title`、JSON 实测规模超过上限 1/4）
U6-7   HG-1 被否决，或需要修改第 5.4 节所列之外的 CLOSED 测试
U6-8   凭据需要持久化 / 从环境或文件读取
U6-9   重试语义需要修改 P4（preview_retry / BatchScheduler）
U6-10  并发上界无法在不引入新 scheduler 的前提下证明
U6-11  取消无法被有界化（宿主取消无响应时没有放弃路径）
U6-12  三份设计文档互相矛盾，或设计冻结后出现 Contract 语义修订 / 范围修订 / 安全不变量修订（需独立 Design Review，Governance v2 第 11.2 节）
U6-13  试图在没有证据的情况下扩大支持声明（含 live smoke）
```

---

## 29. 状态

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
Phase 6 package count         : 1
HG-1 (historical gate rebind) : ACCEPTED（三份独立 Design Review 一致裁决）— NOT EXECUTED（未来 S1 test-only repair；本轮 Tests Modified = NO）
Design-R1                     : SUPERSEDED（c05c7eb）
Design-R2                     : SUPERSEDED BY DESIGN-R3 CANDIDATE（b071d14）
Design-R3                     : SUPERSEDED（85d3da8）
Design-R4                     : SUPERSEDED BY DESIGN-R5 DRAFT（6ccf7d3；独立复核 FAIL）
Design-R5                     : COMMITTED REVIEW CANDIDATE — INDEPENDENT REVIEW FAIL（Reviewer C / G / x 均 FAIL；候选内容：致命异常 F3 = 确定性所有权清理 + 异常引用脱离，生产路径禁止 gc.get_referrers / sys._getframe / frame.clear；X-NARROW 仅用于独立载荷对照，四个植入凭据用例与 trace 注入 = OUT_OF_THREAT_MODEL — ADVERSARIAL_IN_PROCESS_ACCESS（B1 / B2）；Reviewer x 的 Findings Addendum（x-01..x-07）已交付并由 R1-04..R1-10 在本地修复，R5-02..R5-07 与其编号对应由 Governance 保留，均不得视为已关闭；本状态不得改写为 PASS）
R5 Candidate                  : 22a3fa4922c655cb5ce127ee2825b1678f4855db（已提交并推送的 R5 Review Candidate；不得改写 / amend / reset）
Design-R5-R1                  : UNIFIED CLOSURE REPAIR — LOCAL DRAFT（本地未提交；R1-01..R1-10 已在本地修复并附红绿证据，待 Governance 审阅；这不是 Review Candidate，不是 CLOSED / PASS；HG-1 = ACCEPTED — NOT EXECUTED；S1 = NOT AUTHORIZED）
```

本文不得被解读为 FROZEN / DESIGN PASS / IMPLEMENTATION AUTHORIZED / CLOSED。唯一 authority 转换：独立 Design Review PASS → 该 Design Candidate SHA 成为
Design Accepted Head（Frozen Contract / Plan Head、Implementation Input）→ 才允许 Developer 开始 S1。

---

## 30. Independent Design Reviewer 的强制审查点

下一位 Independent Design Reviewer **至少**必须审：

**范围与责任边界（Design-R5-R1 / R5-R1-02）**：完整范围是 **DR-01..DR-69**。Master Plan 与 Construction Plan 引用此完整范围，**不得**只引用 DR-01..DR-10 或 DR-01..DR-35，**不得删减 DR-36..DR-69**。① 任何 Reviewer 的 PASS 只对其被指派的 DR 子集有效，不代替其它子集；整份设计的 PASS 要求 DR-01..DR-69 的**每一条**都被至少一位被指派的独立 Reviewer 明确覆盖。② 由哪位 Reviewer 审哪一段由 Governance Coordinator 指派，本文不指派具名 Reviewer。③ 分类（供指派参考）：DR-01..DR-35 = R1–R4 的权威 / 范围 / 宿主事实 / 状态机 / 并发 / 取消模型 / 映射 / 证据；DR-36..DR-47 = R5 的谓词、快照、乱序、取消结果拆分、Python 3.11、方案 A、URL 卫生；DR-48..DR-63 = R5 的安全设计（F3、总 deadline、注入点、取消归属、接缝撤销、X-NARROW、帧安全、审计、B1 / B2、逐层所有权）；DR-64..DR-69 = R5-R1 的审计模型 / 账本 / 见证（严格类型、H3 / H4、Z / W / InFlight、序号空间、收集器守卫、取消 / 终态网络见证与文档一致性）。安全类条款的裁决权属于承担安全复核职责的 Reviewer（Reviewer C 曾提出 `BLOCKED — SECURITY AUTHORITY`），其它 Reviewer 核对它们与合同其余条款的一致性，但不替代其安全裁决。④ Reviewer x 的 Findings Addendum（x-01..x-07）已交付，对应修复审查点为 DR-64..DR-69；DR-37..DR-42 仍是旧 R5-02..R5-07 的审查点，二者的编号对应由 Governance 保留，本文不推断；这些项**待独立复核，不得视为已关闭**。

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

HG-1（DR-03）的实质裁决已被三份独立 Design Review 一致接受，本轮只精确化其文字（第 5.4 节）；Design-R1 Closure Reviewer 需确认精确化后的条款与实质裁决一致。

Design-R1 追加审查点：

```text
DR-11  R1-01 / R2-01：值级来源——输出只由 raw["ffcc.fc2-metadata"] 派生；E1/E2/E3/R0 已撤销；公开 PATCH 不能写 raw 的源码依据；放弃的宿主后处理语义是否被诚实声明；保证范围（非任务独占）是否诚实
DR-12  R1-02：SubmissionState 四态；CREATION_UNKNOWN 不折算；任务账本不等式
DR-13  R1-03：异常图封闭（__cause__ / __context__ / __traceback__ 帧局部）；from None 不被当作证明
DR-14  R1-04：取消三层（L1/L2/L3）；无 CONFIRMED_STOPPED；claimed-window 与晚到写入
DR-15  R1-05：门面调用顺序；不复制 P4 锁；无法承诺的优先级已撤销
DR-16  R1-06：跨轮冲突无全局保证；AmaneBatchSummary 的 cross_round_verified
DR-17  R1-07：JSON 结构上限（MAX_JSON_*）与迭代式预扫描
DR-18  R1-08：Amane 缺省 worker concurrency = 10 的修正与三个并发数的区分
DR-19  R2-02：异常 / 凭据边界覆盖整个包；保护面 P1–P3、禁入内容 F、所有权状态例外、C1–C7、失败矩阵与红绿孪生
DR-20  R2-03：JSON 预扫描 O(B) 成本模型、辅助空间 O(MAX_JSON_DEPTH)、边界矩阵
DR-21  R2-04：A / K / H 三集合与孤儿安全的并发 oracle，ORPHAN-M1
DR-22  R2-05：S/T/C/R 正交模型、第 10.3.1 节谓词、计数口径、NOT_APPLICABLE ⇔ T=NONE
DR-23  R3-01：严格 raw 键集合（混合来源拒绝）与 H6-1 的一致性
DR-24  R3-02：TimestampRelation 只是比较标签；CASE A–D；真实宿主与替身证据不得混称
DR-25  R3-03：C5a / C5b / C5c；CancelledError 新实例（方案 A）与致命异常原样传播 + 引用脱离使敏感引用不可达（F3）是否自洽；是否存在 BLOCKED — SECURITY AUTHORITY
DR-26  R3-04 / R3-05：attempt_id / X-FFCC-Attempt；O2 的 attempt 粒度；H1–H4；K 的进入退出；oracle 自检
DR-27  R3-06 / R3-07：取消 / 致命的合法组合（见 DR-33）与取消见证的自报告 / 独立事实区分是否可满足且可观测
DR-28  R3-08：图片裁剪语义（raw-only）与 §18 / L6-10 / E6-28 一致
DR-29  R4-01：第 11.2 节映射入口的校验顺序、唯一错误分类、无前置解引用（代码块可被抽取执行）
DR-30  R4-02：第 10.2 节内联清理生命周期——无 shield / 无 task / 有界 / 二次取消 / 致命原样传播；有界性的作用域（生产传输路径）与 UNVERIFIED / NOT_RUN 项是否被诚实标注；是否需要 BLOCKED — SECURITY AUTHORITY
DR-31  R4-03 / R4-04：第 14.4 节请求账本模型（O2-1..O2-8、pre-proxy 注入清单、`calls(N)`、attempt_id 跨记录唯一）
DR-32  R4-05：第 20.5 节累计状态 Z 与保留窗口 W 的分离；分段流式验证；溢出后哪些验证仍成立
DR-33  R4-06 / R4-07：第 10.3.1 节谓词与独立参考模拟器相等（R4 为 39 条，R5 重新计算为 63 条，见 DR-37）、H4 事件有效性、事件全序；规则消融
DR-34  R4-08：L6-01 与 Master / Plan 不再声称“逐字段双侧证据”
DR-35  R4-09：E6-28 的冻结输入与非空断言；第 23.2 节证据状态词汇
DR-36  R5-01：谓词接受真实枚举与冻结数据类，任意输入不抛出（Gate B 从合同抽取并执行）
DR-37  R5-02：类型 / 见证约束齐全；63 条可产生状态由模拟器重新计算；独立性仍为 NOT ESTABLISHED
DR-38  R5-03：H3 已送达 / H4 缺席合法；H3 单独不授权取消；O2-4 的对应分支
DR-39  R5-04：在途 / 静止快照分开；Z 更新点；五个必测场景
DR-40  R5-05：乱序完成、completion_seq、FIFO 窗口、收集器游标、溢出、NOT_VERIFIED
DR-41  R5-06：NO_RESPONSE / NOT_TERMINAL / OBSERVATION_FAILED 拆分与严格优先级；第 10.2 / 10.3 节、状态表、谓词、E6-08 / E6-09、M6-34 一致
DR-42  R5-07：Master F-20 与合同安全范围措辞一致；FAIL / NOT_RUN / UNVERIFIED / BLOCKED 不混用
DR-43  R5-08：map_host_result 第 7 步 URL 卫生与精确 dropped_url_count
DR-44  R5-09：宿主展示 poster 裁剪不进入 P6 URL 过滤（Master F-8 / §18 / L6-10）
DR-45  R5-10：Python 3.11.0+；不依赖 asyncio.timeout；E6-25 / E6-08 / E6-09 / E6-17 含 3.11 最低小版本
DR-46  R5-11：方案 A 的设计修订（transport= 与衍生的 _clock / _sleep 一并移除）是否充分、故障覆盖矩阵是否保留 E6-05 / E6-09 / E6-17 的全部强制能力、反例“不可经 P6 入口触发”的论证是否成立（进程级猴子补丁属于库被篡改的威胁模型）
DR-47  R5-12：非 httpx Exception 安全分类；红绿孪生；致命 traceback 风险（第 10.5 节）披露是否精确
DR-48  治理附加 G-2：F3（同一实例、确定性所有权清理 + 异常引用脱离）是否满足全部 12 项证明要求；六个概念（对象身份 / 类型 / 参数 / traceback 保真度 / 异常链 / P4 可见行为）是否被区分；诊断能力损失是否如实记录；净化失败与第二个致命异常是否不遮盖 / 不吞掉；若不满足则必须报告 BLOCKED — SECURITY AUTHORITY，不得退回 F1 / F2
DR-49  治理附加 G-4：总 deadline 机制（loop.call_at + Task.cancel + cancelling()/uncancel() 记账）是否正确、是否在 Python 3.11.0–3.14 都成立、finally 撤销、与调用方取消的竞速、墙钟上界公式
DR-50  治理附加 G-1：公共构造面的全部注入点清单（含 image_client 属 P4 CLOSED 接缝）与 API 守卫是否完备
DR-51  治理 Gate C-Final-01：取消归属不变量 O1–O5 是否被 R1–R11 的逐步记录证明；红孪生是否真的变红；3.11 / 3.13 的差异是否只来自 asyncio 自身（控制实验）；R8b 的取舍是否可接受
DR-52  治理 Gate C-Final-02：六个概念（身份 / 类型 / 参数 / traceback 保真度 / 链 / P4 行为）是否被分开验证；抛出方植入字段按 X-NARROW 处理是否满足全部强制条件（见 DR-57）
DR-53  治理 Gate C-Final-03：接缝撤销后 E6-05 / E6-08 / E6-09 / E6-17 的确定性能力是否仍可构造；故障网络是否独立于被测代码；无隐藏 scheduler / task / 资源残留
DR-54  R5-C-01：边界所有权的生命周期设计是否对所有有效退出路径成立（try 体 / except Exception / except CancelledError / 致命处理体 / finally / try 之后 / 公共 client 出口 / engine / facade）；穷举窗口探针（任一字节码 / 检查点两种模型，k = 1 / 2 / 3）与 R5 草案红孪生；“任一字节码且数量无界”（trace 注入）模型是否被正确归入 B1 / B2 的 OUT_OF_THREAT_MODEL，且没有借此降低检查点模型的保证
DR-55  R5-C-02：链整条切断是否足以覆盖 C 级槽位；审计器（gc.get_referents）是否仍有盲区（受控遍历，不执行用户代码，不遍历整个进程对象图）；C 级槽位红绿孪生
DR-56  R5-C-03：取消归属的单点分类（cancelling() > base）是否在全部竞态上正确（外部先 / 内部先 / 同轮次 / 两次外部 / TaskGroup / 调用方 asyncio.timeout / 完成竞争 / 响应关闭 / 内层转换），Python 3.11–3.14 的差异；Reviewer C 原始 race.py 与 race_c_revised.py 的对应关系
DR-57  X-NARROW（仅独立载荷）：六个强制条件是否逐条落实；四个植入用例是否保留并标 OUT_OF_THREAT_MODEL 而非 X-NARROW PASS，“需要主动进程内篡改”的独立证据是否成立（_http 私有、无钩子 API）；Y / Z 是否仍被拒绝；受支持依赖矩阵与矩阵守卫
DR-58  R5-CL-01：F3 生产路径是否访问任何帧（`frame.clear()` / `gc.*` / `sys._getframe`）、是否依赖 `except RuntimeError`；红 / 绿孪生是否覆盖已结束帧 / 正在执行帧 / 挂起生成器 / 挂起协程 / 第三方链 / 本包拥有的挂起帧，且分别在正常 GC 与 `gc.freeze()` 下、在 3.11 / 3.12 / 3.13 / 3.14 上；公共 client 与 `aggregate` 两条路径；Reviewer C `frameclear.py` / `liveness.py` 基线
DR-59  R5-EV-01：审计器是否检测任何带 `Authorization` 的 `Request` / `Response.request`（与令牌值无关）；非 canary 正向对照与变异是否真实变红；是否未改变生产保护范围
DR-60  B1 / B2：进程内信任边界与异步致命异常投递边界的措辞是否只声明有运行时证据的保证；真实信号 fuzz 是否被当作绝对证明；是否改变了进程级 `SIGINT` 策略
DR-61  R5-GOV-01：生产实现是否仍依赖不完整的 GC 引用者枚举；静态守卫是否拒绝 `gc.get_referrers` / `sys._getframe` / `frame.clear` 及其别名、字符串形式、替代手段（`gc.collect` / `gc.get_objects`）；旧版在 `gc.freeze()` 下是否确实失败、新版是否通过
DR-62  R5-NEW-01：F3 是否为清理帧而触发 `sys._getframe` / `gc.get_referrers`；是否有任何审计事件的参数能到达带 `Authorization` 的 `Request`；公共 client 与 `aggregate` 是否分别验证；是否把“审计钩子有执行权限”误当作解决方式
DR-63  逐层所有权：`_transport` / `_call` / 公共 client / `_run` / `aggregate` / 门面是否各自说明了持有什么、谁清理、处理体 / `finally` / 返回点 / 清理器失败 / 二次致命各自如何；门面一栏是否如实标注“设计要求，探针未建模”
DR-64  R1-04 / x-01：`HostAttemptRecord` 构造边界与 `record_is_legal` 是否对 `UserString` 等可变别名、`None`、错误对象、未初始化实例、鸭子类型一律拒绝并返回 `bool`；错误是否不回显字段内容；63 个抽象状态与原有 Enum / 严格 bool / 事件 / `HostFailureKind` 约束是否不变；红绿孪生是否使用真实枚举与真实冻结数据类
DR-65  R1-05 / x-02：第 14.4 节 O2-4 的 H3 / H4 时序矩阵是否承认“代理完成 H3 ≠ P6 已建立 H4”；`late` 写入、重置、中断、取消 / 致命、reader 拒绝、正常 H4 六种情形是否都有判定；是否保留“不伪造 H4、不从代理补救 id、不自动重复 POST、UNKNOWN 之后无请求”；合法歧义绿、违反边界变异红
DR-66  R1-06 / x-03：`Z` / `W` / `InFlight` 三个统计域与四类不变量是否冻结且互不矛盾；`Z.submitted` 在 `in_flight > 0` 与溢出后是否都有可验证的口径；强制用例与旧变体红
DR-67  R1-07 / x-04：O2-3 是否不再使用 `highest_dropped_seq`、`seq` 与 `completion_seq` 两个序号空间是否分别证明归属与保全；已丢弃历史“已保存 ⇒ 可验证，缺失 ⇒ `NOT_VERIFIED`”，不推断、不静默忽略
DR-68  R1-08 / x-05：快照全局上界、`completion_seq` 唯一性与稠密性、收集器冲突检测（不得 `setdefault`）、保留窗口与已采集历史交叉校验、溢出前后一致；单条谓词未被要求取代跨记录验证
DR-69  R1-09 / x-06 与 R1-10 / x-07：取消确认与终态观察是否落实为网络事实约束；Contract §10.3 / §14.4 / §20.5、Master F-22 / F-25 / F-26、Construction Plan 与 E6-08 / E6-09 / E6-10、Gate B / D / E 的验收范围是否互不矛盾，且没有残留旧字段 / 旧统计域 / 未经证实的网络见证
```
