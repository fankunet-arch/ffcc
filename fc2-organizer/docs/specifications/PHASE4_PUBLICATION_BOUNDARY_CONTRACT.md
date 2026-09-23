# FC2 Organizer -- Phase 4 / P4-C3 Metadata 发布边界合同（Metadata Publication Boundary Contract）

状态：**在 P4-C3 冻结**（候选；独立复查待进行）。
Package：`fc2_organizer.publication`（`errors.py`、`models.py`、`boundary.py`）。
同时在 `fc2_metadata_core` 中关闭：**C2-L2**（trace 模型加固，第 14 节）
和 **P2-R-10**（JavDB 标题被重复反转义，第 16 节）。

**范围（对本 package 冻结）：** 回答“这份聚合后的 metadata 能否安全地绑定到这个 `OrganizePlan`，并交给之后的
内容渲染层？”。它不渲染任何内容。不产出 NFO/XML/JSON，不处理图片，不做任何形式的文件系统访问，不访问网络，
不导出诊断信息，不涉及 Amane。见第 17 节。

## 1. 架构与依赖方向

```text
fc2_organizer.publication
    |-- fc2_organizer.planning          (public package only: OrganizePlan)
    |-- fc2_metadata_core.aggregation   (public package only: AggregationResult, AggregateStatus)
    '-- fc2_metadata_core.models        (public package only: NormalizedMetadata)
```

* 除标准库之外，`fc2_organizer.publication` 不 import 其他任何内容（实际上只用了 `__future__` 和
  `dataclasses`）。`errors.py` 只使用标准库。
* 禁止：`amane`、`fc2_metadata_core.sources`（adapter）、`.http`、
  `.resource_control`、`.batch`、聚合内部实现（`engine`、`execution`、`retry`、`merge` 模块）、
  `fc2_organizer.discovery`，以及任何文件系统 / 网络 / 时钟 / 随机数模块。
* 没有反向依赖：`fc2_metadata_core`、`fc2_organizer.planning` 或 `fc2_organizer.discovery` 中都没有任何内容
  import `fc2_organizer.publication`。
* `fc2_organizer/__init__.py` **不会**急切地 import `publication`（原因与 P4-C2 的 `planning` 相同：
  那样会在裸 `import fc2_organizer` 时传递加载 `fc2_metadata_core`，破坏 P4-C1 冻结的 discovery 边界测试）。
  请显式 import：`from fc2_organizer.publication import prepare_publication`。
* `fc2_organizer` 的顶层子 package 现在恰好是 `{"discovery", "planning", "publication"}`。P4-C1 / P4-C2
  的作用域守卫断言各更新了一行；它们的禁止 import 守卫没有任何改动。

由 `tests/contract/test_publication_architecture.py` 强制执行。

## 2. 公开 API

```python
from fc2_organizer.publication import prepare_publication, PublicationRecord

prepare_publication(plan: OrganizePlan, aggregation_result: AggregationResult) -> PublicationRecord
```

同时导出：`PUBLISHABLE_STATUSES` 以及第 9 节中的错误类。

## 3. `PublicationRecord` 形态（冻结）

```python
@dataclass(frozen=True, slots=True)
class PublicationRecord:
    plan: OrganizePlan
    metadata: NormalizedMetadata
    aggregate_status: AggregateStatus   # SUCCESS or PARTIAL only

    number -> str   # read-only property: plan.canonical_number
```

恰好这三个字段。没有 `to_json` / `to_dict` / `to_xml` / `render*` /
`write` / `save` / `serialize` / `dump`：这个记录是一个值，而不是序列化器。

## 4. 聚合状态门（冻结）

| `AggregationResult.status` | 发布 |
|---|---|
| `SUCCESS` | 接受 |
| `PARTIAL` | 接受 -- 冻结的 Phase 3 聚合合同保证了满足最低成功标准的 metadata；某些来源的运行性失败不会让 metadata 变得不可发布。记录中保留 `PARTIAL`（绝不升级）。 |
| `FAILED` | **拒绝**（`AggregationNotPublishableError`） |
| 任何不是 `AggregateStatus` 的值（绕过了构造） | **拒绝**（`AggregationNotPublishableError`） |

这里不重新定义聚合状态；`PUBLISHABLE_STATUSES = {SUCCESS, PARTIAL}`。

## 5. Metadata 最低成功标准门（冻结）

聚合结果的 `metadata` 必须是一个 `meets_minimum_success()` 为真的 `NormalizedMetadata`
（合法的规范 FC2 番号 + 非空标题）。该方法是唯一的成功规则；这里不存在第二条规则。否则抛出
`InvalidPublicationMetadataError`。

## 6. 身份关联门（冻结）-- 关闭 P4-C2 延续下来的身份缺口

只有满足以下条件才会生成记录

```text
plan.canonical_number == aggregation_result.number == aggregation_result.metadata.number
```

并且三者都是严格的 `str`（`str` 子类可能覆盖 `__eq__`）。任何不一致都会抛出
`PublicationIdentityMismatchError`。边界永远不会在计划的番号和 metadata 的番号之间选出一个“胜者”。
`AggregationResult` 本身已经强制 `metadata.number == number`；边界仍然会重新检查它所依赖的每一项身份，
因此即使一个 `AggregationResult` 的 `__post_init__` 被绕过，它也无法被绑定到错误的计划上。

检查顺序（确定的；第一个失败即抛出）：输入类型（第 9 节）
-> 状态 (4) -> metadata (5) -> 身份 (6)。

## 7. 模型层不变量（冻结）

`PublicationRecord.__post_init__` 独立于 `prepare_publication` 强制执行以下内容
（手工构建的记录获得同样的保证），违规时抛出 `PublicationContractError`：

* `plan` 是 `OrganizePlan`；`metadata` 是 `NormalizedMetadata`；
* `aggregate_status` 是 `AggregateStatus.SUCCESS` 或 `PARTIAL`；
* `metadata.meets_minimum_success()`；
* `metadata.number` 是严格的 `str`，并且等于 `plan.canonical_number`。

## 8. 发布对象图中没有诊断信息（冻结）

记录只保存计划、metadata 和状态。它的完整对象图永远不会触及 `AggregationResult`、`SourceResult`、
`SourceExecutionTrace`、`SourceAttempt`、任何异常对象（因此也没有异常的 `args` / traceback）、任何
`error_detail` / `error_kind`、HTTP 响应、响应体、header、cookie 或凭据。
这是通过遍历实际对象图（slots、`__dict__`、tuple、mapping）验证的，被遍历的记录由*确实*携带 trace 和
看起来敏感的 `error_detail` 文本的聚合结果构建而来（`tests/unit/publication/test_publication_no_side_effects.py`）。

NFO / 内容发布与诊断信息发布仍然是分开的两层：C2-L2 的加固（第 14 节）**不会**让 trace 成为记录的一部分。

## 9. 错误分类（`errors.py`）

| 错误 | 基类 | 抛出时机 |
|---|---|---|
| `PublicationError` | `Exception` | 以下所有错误的基类 |
| `PublicationInputError` | `PublicationError`、`TypeError` | `plan` 不是 `OrganizePlan` / `aggregation_result` 不是 `AggregationResult` |
| `AggregationNotPublishableError` | `PublicationError`、`ValueError` | 状态不是 `SUCCESS`/`PARTIAL` |
| `InvalidPublicationMetadataError` | `PublicationError`、`ValueError` | metadata 缺失 / 类型错误 / 不满足最低成功标准 |
| `PublicationIdentityMismatchError` | `PublicationError`、`ValueError` | 第 6 节 |
| `PublicationContractError` | `PublicationError`、`ValueError` | 某个 `PublicationRecord` 违反第 7 节 |

消息只由规范番号、枚举值和类型名构成。它们从不包含 `SourceResult.error_detail`、异常对象 / args / traceback
或任何 HTTP 载荷；外来的（非 `str`、非枚举）值只会显示为 `<TypeName>` -- 从不调用它的 `repr`。
任何 publication 错误都不会链接到另一个异常。

## 10. 深度不可变（冻结）

`PublicationRecord` 是 `frozen=True, slots=True`（没有实例 `__dict__`，字段不能重新赋值或删除）。
`OrganizePlan`（frozen、tuple、frozen 的 `PlannedPath`）和 `NormalizedMetadata`（frozen；tuple；与调用方容器
脱离的 `MappingProxyType` 快照）本来就是深度不可变的，因此整个记录也是。

## 11. 确定性、相等性、hash（冻结）

相等的输入产生相等的记录（`==`，`repr` 相同）。不读取时钟、随机数、UUID、文件系统或网络。
hash 遵循嵌套对象现有的语义：`OrganizePlan` 可哈希，但 `NormalizedMetadata` 不可哈希（它的 mapping 是
`MappingProxyType`），因此 `hash(record)` 会抛出 `TypeError` -- 这是一致的，绝不是随机的。

## 12. 零文件系统、零网络（冻结）

`prepare_publication` 和 `PublicationRecord` 不执行任何 `exists` / `stat` /
`resolve` / `realpath` / `open` / `mkdir` / 写入 / 重命名 / 移动 / 复制 / 删除，
不使用 socket，不发起 `httpx` / `requests` / `urllib` 请求。这是通过在所有这些 API 都被拦截的情况下运行边界
（包括接受路径和拒绝路径，以及整个合成门槛），再加上前后对比文件系统快照来证明的。

## 13. 合成门槛

`tests/unit/publication/test_publication_synthetic_gate.py`：400 个互不相同的计划 + 聚合结果对
（6 位和 7 位数字的番号；SUCCESS / PARTIAL 混合；单次 attempt、重试过的、NOT_FOUND、BLOCKED、NETWORK_ERROR、
PARSE_ERROR 等来源组合；Unicode 标题；集合 / mapping 类型的 metadata），全部在文件系统 / 网络拦截下运行。
每一个匹配的对都被接受；800 个不匹配项（每个计划与其相邻条目的聚合结果配对 + 每个条目一个伪造的 metadata 番号
不匹配）以及 50 个 FAILED 聚合结果都被拒绝；第二遍运行的结果逐条相等；每条记录都是 frozen 的，其对象图中
不含任何诊断信息。

## 14. 关闭 C2-L2：`SourceExecutionTrace` / `SourceAttempt` 拒绝 engine 不可能产生的状态

选定的关闭方式：在 `fc2_metadata_core/aggregation/models.py` 中**加固校验器**
（而不是发布一条“可信生产者”声明）。engine（`execution.py`）没有被修改。
以下规则由 engine 的实际行为推导而来：

* 只有 `_run_source` 的 deadline 路径会记录 `completed=False` 的 attempt，而且总是
  `NETWORK_ERROR` / `SOURCE_DEADLINE`；
* 只有当 `RetryPolicy.should_retry` 为真时，engine 才会开始另一次 attempt -- 或在其之前进行退避，
  即该次 attempt 的 `error_kind` 在策略的 `retryable_error_kinds` 中，而后者总是
  `retry.RETRY_ELIGIBLE_KINDS`（`NETWORK_ERROR`、`TIMEOUT`、`CONNECTION_ERROR`、
  `DECODE_ERROR`、`HTTP_SERVER_ERROR`）的子集。

新增不变量（抛出 `AggregationContractError`）：

| # | 不变量 | 它所关闭的历史状态 |
|---|---|---|
| 1 | `SourceAttempt(completed=False)` 必须是 `NETWORK_ERROR` / `SOURCE_DEADLINE` | 未完成的 `SUCCESS` attempt |
| 2 | （同一条规则） | 其他 kind 的未完成 attempt（`PARSE_ERROR`、`NOT_FOUND`、`CONNECTION_ERROR`、...） |
| 3 | 除最后一次之外的每次 attempt，其 `error_kind` 都必须可重试 | 在 `NOT_FOUND` 之后重试（以及在 `SUCCESS`、`BLOCKED`、`RATE_LIMITED`、`PARSE_ERROR`、`SOURCE_DEADLINE`、`CIRCUIT_OPEN`、... 之后重试） |
| 4 | 当 `deadline_during == "backoff"` 时，最后一次（已完成的）attempt 的 `error_kind` 必须可重试 | 在终态 `SUCCESS`（或任何不可重试的结果）之后的退避期间出现 deadline |

仍然被接受的情况（真实 engine 产生的每一种形态，通过运行真实的 `execute_sources_traced` 固定下来）：
单次 `SUCCESS` / `NOT_FOUND` / 失败；可重试失败 -> `SUCCESS`；可重试失败 -> 任何 kind 的最终失败；
3-attempt 链；在某个可重试 kind 上停止的收窄策略；deadline 发生在第 1 次 attempt 或某次重试 attempt 期间；
deadline 发生在重试退避期间；零次 attempt 的 `CIRCUIT_OPEN`（C5）；C5 的过期准入情况（没有进行重试，
之前的可重试失败保持为最终结果）。已完成的 attempt 沿用原有规则（`ALLOWED_ERROR_KINDS` 允许的任何状态 / kind 组合）
-- 刻意没有进一步收紧。

这两项检查是模块级函数（`_check_incomplete_attempt`、`_check_retry_shape`）；一个变异式测试恰好撤销它们，
并证明四种历史非法状态中的每一种都会重新变得可以构造。

**P2-R-07 说明（仍然延续，这里没有修复）：** adapter 返回的 `SourceResult.elapsed_ms` 在某些失败路径上
可能为 `0`。将来任何需要 attempt 计时的诊断信息发布，**必须**使用 engine 测量的
`SourceAttempt.elapsed_ms`，绝不能把 adapter 失败结果中的 `elapsed_ms == 0` 当作真实耗时。

## 15. C2-L2 与发布的关系

trace 永远不是 `PublicationRecord` 的一部分（第 8 节）。之所以进行这项加固，是为了让将来一个有独立合同、
会显式读取 trace 的诊断 / 报告层，拿到的是一个无法表达 engine 不可能状态的公开模型。

## 16. 关闭 P2-R-10：JavDB 标题只解码一次

`sources/adapters/javdb.py` 原先以
`clean_text(html.unescape(attrs.get("title", "")))` 读取详情锚点的标题。`parse_attrs` 返回的是原始的、
仍带实体编码的值，而 `clean_text` 本身会调用 `html.unescape`，因此实体被解码了两次。现在改为：
`clean_text(attrs.get("title", ""))`（并移除了未使用的 `html` import）。冻结的行为：

| 原始属性 | 标题 |
|---|---|
| `A &amp; B` | `A & B` |
| `A &amp;amp; B` | `A &amp; B`（不是 `A & B`） |
| `&#38;amp; x` | `&amp; x` |
| `&amp;lt;tag&amp;gt;` | `&lt;tag&gt;` |
| `  A \n\t  B  ` | `A B` |

未改变的部分：属性为空时回退到文本标题（本来就只解码一次）、空白折叠、去除文本标题中的标签、
番号精确匹配 / 近似未命中时的 `NOT_FOUND`，以及标题为空时的 `PARSE_ERROR`。P2-R-05、P2-R-06 和
P2-R-07 没有被触及。

## 17. P4-C3 范围之外

NFO 渲染 / XML / 写入；poster / fanart / thumb 的下载或校验；文件系统落盘（`mkdir`、移动、重命名）；
预览 UI；CLI；JSON 报告；诊断信息导出；持久化 / 恢复；Amane 集成。这些都没有任何占位实现。

## 18. 测试矩阵

| # | 要求 | 测试 |
|---|---|---|
| 1, 2, 6 | SUCCESS / PARTIAL 且匹配 -> 生成记录 | `test_publication_boundary.py::test_matching_success_or_partial_aggregate_is_published` |
| 3 | FAILED 被拒绝 | `test_failed_aggregate_is_rejected`、`test_failed_status_is_rejected_even_if_bypassed_metadata_is_present` |
| 4 | 计划番号 != 聚合番号 | `test_plan_number_differing_from_aggregate_number_is_rejected` |
| 5 | 计划番号 != metadata 番号 | `test_metadata_number_differing_from_aggregate_number_is_rejected`、`test_no_winner_is_chosen_...` |
| 7 | 最低成功标准 | `test_metadata_that_misses_minimum_success_is_rejected` |
| 8-10 | 标量 / 嵌套不可变性 | `test_publication_models.py::test_record_fields_cannot_be_reassigned_or_added`、`test_nested_plan_is_immutable`、`test_nested_metadata_is_immutable` |
| 11 | 相同输入 -> 相同记录 | `test_identical_inputs_give_equal_records` |
| 12-15 | 没有 AggregationResult / SourceResult / trace / attempt / error_detail / 异常 | `test_publication_no_side_effects.py::test_record_graph_*`、`test_record_does_not_reference_the_input_aggregate_object` |
| 16 | 保留 Unicode | `test_unicode_titles_are_preserved_exactly` |
| 17 | tuple / mapping 不可变 | `test_tuple_and_mapping_metadata_stays_immutable_and_detached_from_caller_containers` |
| 18, 19 | 零文件系统 / 网络 | `test_prepare_publication_runs_with_every_filesystem_and_network_api_trapped`、`test_rejections_also_run_...`、`test_prepare_publication_leaves_the_filesystem_unchanged` |
| 20 | 不依赖 Amane | `tests/contract/test_publication_architecture.py` |
| 21-24 | 拒绝 C2-L2 非法状态 | `tests/unit/aggregation/test_agg_c2_l2_trace_hardening.py::test_21_* .. test_24_*`（+ 覆盖所有 kind 的参数化） |
| 25-28 | 接受合法形态 | `test_25_* .. test_28_*` |
| 29 | 真实 engine 的 trace 仍然合法 | `test_29_every_real_engine_trace_shape_is_valid_under_the_hardened_model`、`test_29_real_engine_circuit_open_zero_attempt_trace_is_valid`，以及未改变的 Phase 3 聚合 / 资源控制测试套件 |
| -- | 变异证明 | `test_mutation_reverting_the_c2_l2_checks_makes_each_invalid_state_constructible_again` |
| 30-34 | P2-R-10 | `tests/unit/sources/adapters/test_javdb_p2_r10_single_unescape.py` |
| 门槛 | 合成门槛 | `test_publication_synthetic_gate.py` |

## 19. 延续的债务

由 P4-C3 关闭：**P4-C2 `metadata.number != canonical_number` 身份缺口**
（在本边界关闭，第 6 节）、**C2-L2**（第 14 节）、**P2-R-10**（第 16 节）。

仍然延续、未改变：P4-C2-R1-02（LOW）、OrganizePlan 操作图的模型层加固、覆盖执行器语义（冻结为 `NEVER`）、
扩展的 Windows 保留名边界情况；P4-C1-R-02..R-05；P2-R-05、P2-R-06、P2-R-07（见第 14 节的说明）；
C3-N1..N4；C4-N1；C4-R1-N1..N3；F3；F5；C5-R1-L1。
