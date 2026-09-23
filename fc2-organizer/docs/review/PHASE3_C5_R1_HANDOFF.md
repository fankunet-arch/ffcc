# Phase 3 / C5-R1 Handoff — 纯文档关闭（Docs-Only Closure）

**类型：** DOCS-ONLY CLOSURE（没有源码、测试或工具改动）

**C5 Code Head:** `fb4dddaf4ef00ed201c94d9a7e29d1e86a20f17d`（本轮未改变 / 冻结）
**Reviewed C5 Docs Head / C5-R1 Base:** `caf1655336b96a02a64cfdd515932c594d86da0a`

**独立 Level 2 复查结果（上一轮）：** PASS WITH NON-BLOCKING NOTES

## 1. 本轮关闭的 finding

**C5-R-01** — 严重程度：MEDIUM — 范围：文档 / 冻结合同的措辞

**根因：** 合同和 handoff 把一个真实但更窄的保证（按 `HostKey` 的许可*容量*独立性）拔高成了一个关于调度器层面*延迟*
独立性的、不加限定的绝对说法（“different hosts ... never block each other”；“a saturated host never delays a different
host”）。独立的 Level 2 复查者复现了这样一个场景：`AggregationConfig.max_concurrency = 2`，目标为
`A1 -> host-a`、`A2 -> host-a`、`B1 -> host-b`（每个 host 的限制为 1），当 `A1`/`A2` 为争用 `host-a` 而占用了仅有的两个
`max_concurrency` 槽位时，`B1` 无法获得聚合来源槽位 — 尽管 `host-b` 自己的许可容量在整个过程中完全空闲。

**代码行为：** 未改变（UNCHANGED）。这是预期中的、原本就存在的 C1（`AggregationConfig.max_concurrency`）架构，
而不是 C5 的缺陷：host 许可容量*确实*像声明的那样按 `HostKey` 相互独立；缺少的是明确承认：聚合本地的来源槽位准入
（C1，未改变）位于该保证*之外*，仍然可能跨 host 地让来源串行化。

**源码 / 测试改动：** 无（NONE）。

## 2. 正确的冻结语义（现已记录在合同和 handoff 中）

- host 许可预算按 `HostKey` 相互独立。
- 一个 host 饱和不能消耗或减少另一个 host 的许可容量。
- 只要有聚合来源槽位可用，不同的 host 就可以各自在自己的限制内并发执行。
- `AggregationConfig.max_concurrency`（C1）仍然是外层的、未改变的按 `aggregate()` 调用的调度预算。
- 正在等待 host 许可的来源，在整个等待期间持续占用它在聚合本地的来源槽位。
- 因此，当 `max_concurrency` 小于一次查找中可运行来源的数量时，一个 host 上的争用可能间接推迟另一个面向*不同*、
  且原本空闲的 host 的后续来源的准入。
- 这**不是** host 许可泄漏，也**不是**跨 host 的预算耦合 — 这是在未改变的 C1 semaphore 下普通的聚合层队头调度，
  与 host 限流器自身的记账相互正交。
- **C5 提供跨 host 的容量隔离。C5 不提供跨 host 的延迟隔离。**

## 3. 本轮变更的文件

```
docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md   (amended: §2, §5 — capacity- vs latency-isolation wording)
docs/review/PHASE3_C5_HANDOFF.md                            (amended: §9 — two-hosts claim re-worded, 2+3 peak result preserved)
docs/review/PHASE3_C5_R1_HANDOFF.md                          (new: this file)
```

没有触碰任何 `src/`、`tests/`、`tools/` 或 `pyproject.toml` 文件。没有触碰其他任何规格文件。

## 4. Finding 关闭声明

**C5-R-01: CLOSED**（文档已修订，写明了精确的“容量隔离 vs. 延迟隔离”语义；在 `PHASE3_RESOURCE_CONTROL_CONTRACT.md` 或
`PHASE3_C5_HANDOFF.md` 中没有再发现不加限定的调度器层面延迟保证 — 通过搜索 "never block each other" /
"never delays a different host" / "no cross-host delay" / "cannot delay another host" 验证）。

这只是一项关于文档正确性的声明。除了为留档而复述上一轮的代码证据之外（§5），它不重新运行也不重新断言那些证据。

## 5. 独立 Level 2 代码证据（保留自上一轮，本轮未重新验证）

本轮只涉及文档，没有重新运行完整的产品测试集（按照指示，因为没有代码改动）。留档记录：上一轮的独立 Level 2 复查发现：

- 完整离线测试集：**2361/2361** 通过，0 failed，0 skipped（`tests/contract` ↔
  `tests/unit/resource_control` 两种 import 顺序都通过）。
- 独立的 200-item 混合压力门槛（复查者自己构造，独立于 `test_rc_stage_gate_200.py`）：**PASS**。
- 独立的 10,000-item 大 N 门槛（单个调度器 M=16、host 限制 3，以及两个调度器 × 5,000 共享一个 governor）：**PASS**。
- 6 个针对性的变异探测（去掉 epoch 检查、去掉 host 等待后的重新校验、跨退避持有许可、把 `NOT_FOUND` 重新归类为失败、
  让 `CIRCUIT_OPEN` 可重试、去掉“授予后取消”时的交还）：全部 6 个都被测试集捕获。
- 没有 BLOCKER / HIGH 级别的 finding。C5-R-01（MEDIUM，文档）是唯一未关闭的项目，现已由本轮关闭。

## 6. 待办（未改变，延续）

- **C2-L2** — LOW / OPEN，未改变：C5 不读取任何 trace 字段（合同 §10 / handoff §8，不受本轮文档修订影响）。
- 其他所有 C4-N1、C4-R1-N1/N2/N3、C3-N1…N4、P2-R-05/06/07/10、F3/F5 项：未改变，与本轮之前一样延续。

## 7. 状态

**C5 代码：** 未改变 / 冻结于 `fb4dddaf4ef00ed201c94d9a7e29d1e86a20f17d`。
**下一阶段：** NOT STARTED。

READY FOR C5-R1 DOCS-ONLY INDEPENDENT CLOSURE REVIEW
