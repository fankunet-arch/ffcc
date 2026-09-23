# Phase 4 / P4-C3 Handoff -- Metadata 发布边界加固（Metadata Publication Boundary Hardening）

```text
Phase        = 4
Package      = P4-C3
Role         = Developer
Branch       = claude/phase4-c3-publication-boundary
```

## 1. 坐标

```text
Frozen Base                  = b44ca7a1a3ca70dddf8686d9d14a98d52b481b82
P4-C3 Code Review Candidate  = 1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f
P4-C3 Docs Head              = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C3_HANDOFF.md`>
Remote Head                  = <= Docs Head after push of this commit>

Code Review Range: b44ca7a1a3ca70dddf8686d9d14a98d52b481b82..1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f
Docs Review Range: 1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f..<Docs Head>
```

在任何改动之前已验证：`git fetch --all --tags`；
`origin/claude/phase4-c2-organize-plan` == `b44ca7a1a3ca70dddf8686d9d14a98d52b481b82`；
工作区干净（只有未跟踪的 `.claude/`）；从那个确切的提交创建了新分支
`claude/phase4-c3-publication-boundary`，并在一个隔离的 worktree 中开发。没有 rebase / amend / squash / force push。

Code Review Candidate 包含代码、测试以及冻结的合同（`PHASE4_PUBLICATION_BOUNDARY_CONTRACT.md`）。Docs Head 提交只包含本文件。

## 2. 类型

**NEW PACKAGE**（`fc2_organizer.publication`）+ `fc2_metadata_core` 中两处经授权的最小修复（C2-L2 trace 校验器、
P2-R-10 JavDB 解码）+ 两处一行的 package 集合作用域守卫更新。

## 3. 变更文件（Code Review Candidate `1e66ab4`，19 个文件，+2166 / -7）

新增（15）：
```text
fc2-organizer/docs/specifications/PHASE4_PUBLICATION_BOUNDARY_CONTRACT.md
fc2-organizer/src/fc2_organizer/publication/__init__.py
fc2-organizer/src/fc2_organizer/publication/boundary.py
fc2-organizer/src/fc2_organizer/publication/errors.py
fc2-organizer/src/fc2_organizer/publication/models.py
fc2-organizer/tests/contract/test_publication_architecture.py
fc2-organizer/tests/unit/aggregation/test_agg_c2_l2_trace_hardening.py
fc2-organizer/tests/unit/publication/__init__.py
fc2-organizer/tests/unit/publication/_builders.py
fc2-organizer/tests/unit/publication/_guards.py
fc2-organizer/tests/unit/publication/test_publication_boundary.py
fc2-organizer/tests/unit/publication/test_publication_models.py
fc2-organizer/tests/unit/publication/test_publication_no_side_effects.py
fc2-organizer/tests/unit/publication/test_publication_synthetic_gate.py
fc2-organizer/tests/unit/sources/adapters/test_javdb_p2_r10_single_unescape.py
```

修改（4）：
```text
fc2-organizer/src/fc2_metadata_core/aggregation/models.py      +42 -1  (C2-L2, section 9)
fc2-organizer/src/fc2_metadata_core/sources/adapters/javdb.py  +3 -4   (P2-R-10, section 10)
fc2-organizer/tests/contract/test_discovery_architecture.py    +1 -1   (package set, section 12)
fc2-organizer/tests/contract/test_planning_architecture.py      +1 -1   (package set, section 12)
```

没有触碰：聚合 engine / execution / retry / merge、resource_control、batch、HTTP transport、其他 adapter、discovery 与
planning 的生产代码、`fc2_organizer/__init__.py`、Amane。

## 4. 发布 API

```python
from fc2_organizer.publication import prepare_publication
prepare_publication(plan: OrganizePlan, aggregation_result: AggregationResult) -> PublicationRecord
```

按确定的顺序检查：输入类型 -> 状态 -> metadata 最低成功标准 -> 身份。第一个失败即抛出；不修复任何东西，也不做任何选择。

## 5. PublicationRecord

```python
@dataclass(frozen=True, slots=True)
class PublicationRecord:
    plan: OrganizePlan
    metadata: NormalizedMetadata
    aggregate_status: AggregateStatus   # SUCCESS | PARTIAL
    # read-only property: number -> plan.canonical_number
```

模型层不变量（包括手工构建的记录，`PublicationContractError`）：类型；状态在 `{SUCCESS, PARTIAL}` 之中；
`metadata.meets_minimum_success()`；`metadata.number` 是严格的 `str` 且 == `plan.canonical_number`。没有序列化器 / 渲染器方法。

## 6. 身份关联（P4-C2 的 metadata 身份缺口）

`plan.canonical_number == aggregation_result.number == aggregation_result.metadata.number`，
全部为严格的 `str`，否则抛出 `PublicationIdentityMismatchError`。不选出任何“胜者”。即使 `AggregationResult` 自己已经强制
`metadata.number == number`，这里也会重新检查（测试使用通过 `object.__new__` 绕过构造的聚合结果，证明边界并不依赖它）。
带有撒谎的 `__eq__` 的 `str` 子类会被拒绝。

```text
P4-C2 metadata identity gap = CLOSED AT P4-C3 BOUNDARY
```

## 7. SUCCESS / PARTIAL / FAILED

SUCCESS -> 生成记录（状态为 SUCCESS）。PARTIAL -> 生成记录（状态保持为 PARTIAL）。
FAILED -> `AggregationNotPublishableError`（对于一个绕过构造、携带 metadata 的 FAILED 结果，以及对于任何非 `AggregateStatus`
的值，也是如此）。最低成功标准只通过 `NormalizedMetadata.meets_minimum_success()` 判断（否则抛出 `InvalidPublicationMetadataError`）。

## 8. 诊断信息排除

记录的实际对象图（slots、`__dict__`、tuple、mapping；通过遍历检查，而不是按名称检查）中不含任何 `AggregationResult`、
`SourceResult`、`SourceExecutionTrace`、`SourceAttempt` 或异常对象，不含任何 `error_detail` / `error_kind` / `args` /
traceback / response / headers / cookie 属性，不含任何包含输入的 `error_detail` 文本的字符串，也不引用输入的聚合结果、
其结果或 trace。输入刻意携带了 trace 以及一段看起来敏感的 `error_detail`
（`cookie=... Authorization: Bearer ... <html>`），并且有一个配套测试证明该遍历器能在原始聚合结果中找到它们全部（非空洞）。
错误消息只包含规范番号 / 枚举值 / 类型名；外来对象被渲染为 `<TypeName>`，不调用 `repr`；任何错误都不做异常链接。

## 9. C2-L2 关闭细节

关闭方式：**收紧校验器**（`aggregation/models.py`）；engine 没有被修改。依据 `execution.py` 推导：`completed=False`
只由 `_run_source` 的 deadline 路径以 `NETWORK_ERROR/SOURCE_DEADLINE` 写入；只有当 `RetryPolicy.should_retry` 为真，
即 `error_kind in retryable_error_kinds ⊆
RETRY_ELIGIBLE_KINDS` 时，才会发生另一次 attempt / 退避。

| engine 不可能产生的历史状态 | 现在 |
|---|---|
| 未完成的 SUCCESS attempt | 被 `SourceAttempt` 拒绝（`_check_incomplete_attempt`） |
| 非 `SOURCE_DEADLINE` 的未完成 attempt（`PARSE_ERROR`、`NOT_FOUND`、`CONNECTION_ERROR`，以及其他所有允许的组合） | 被 `SourceAttempt` 拒绝 |
| 在 `NOT_FOUND` 之后重试（以及在任何不可重试 kind 之后，包括 `SUCCESS`、`BLOCKED`、`RATE_LIMITED`、`PARSE_ERROR`、`SOURCE_DEADLINE`、`CIRCUIT_OPEN`） | 被 `SourceExecutionTrace` 拒绝（`_check_retry_shape`） |
| 在终态 `SUCCESS`（或任何不可重试的结果）之后的退避期间出现 deadline | 被 `SourceExecutionTrace` 拒绝 |

仍然被接受的情况，针对**真实的** `execute_sources_traced` 固定下来：单次 SUCCESS /
NOT_FOUND / BLOCKED / PARSE_ERROR；可重试 -> SUCCESS；可重试 -> NOT_FOUND；可重试 -> 最终失败；3-attempt 链；
收窄策略下的停止；deadline 发生在第 1 次 attempt 期间；deadline 发生在某次重试 attempt 期间；deadline 发生在重试退避期间；
通过 `SourceResourceGovernor` 产生的真实 `CIRCUIT_OPEN` 零 attempt trace。完整的原有 Phase 3 聚合 / 资源控制 / 批处理测试集
（它们通过加固后的 `__post_init__` 构造每一个 engine trace）全部通过。

变异式证明：`test_mutation_reverting_the_c2_l2_checks_makes_each_invalid_state_constructible_again`
把两个新增的模块级检查 monkeypatch 回空操作；四种历史非法状态随后都能被构造，也就是说，这些拒绝确实来自新逻辑。

```text
C2-L2 = CLOSED (implemented; pending independent review)
```

P2-R-07 仍然延续；合同（第 14 节）记录了：将来任何诊断信息发布都必须使用 engine 测量的 `SourceAttempt.elapsed_ms`，
绝不能使用 adapter 失败结果中的 `elapsed_ms == 0`。trace **没有**被加入 `PublicationRecord`。

## 10. P2-R-10 关闭细节

`javdb.py`：`clean_text(html.unescape(attrs.get("title", "")))` ->
`clean_text(attrs.get("title", ""))`（删除了未使用的 `import html`）。结果：
`A &amp; B` -> `A & B`；`A &amp;amp; B` -> `A &amp; B`；`&#38;amp;` -> `&amp;`；
`&amp;lt;tag&amp;gt;` -> `&lt;tag&gt;`。固定为不变的部分：文本标题回退（只解码一次）、空白折叠 / 修剪、文本标题的标签去除、
带近似未命中的番号精确匹配、只有近似未命中时的 `NOT_FOUND`、标题为空时的 `PARSE_ERROR`；所有现有的 JavDB 测试集
（包括对抗性 / 总开销测试）都通过。还有一个测试表明，旧公式在嵌套的情况下会得到 `A & B`。P2-R-05 / 06 / 07 没有被触碰。

```text
P2-R-10 = CLOSED (implemented; pending independent review)
```

## 11. 不访问文件系统 / 不访问网络的证据

* `test_prepare_publication_runs_with_every_filesystem_and_network_api_trapped`（x3 种）
  以及 `test_rejections_also_run_...`：`os.stat/lstat/listdir/scandir/open/mkdir/makedirs/
  rename/replace/remove/unlink/rmdir/removedirs/chmod/utime/symlink/link/access/readlink/walk`、
  `os.path.exists/lexists/isfile/isdir/islink/realpath/getsize/getmtime/samefile`、
  `pathlib.Path.exists/stat/lstat/resolve/is_file/is_dir/open/read_*/write_*/mkdir/touch/
  rename/replace/unlink/rmdir/iterdir/glob/rglob/samefile/symlink_to`、`shutil.*`、
  `builtins.open`、`io.open`、`socket.socket/create_connection/getaddrinfo`、
  `urllib.request.urlopen`、`httpx.Client/AsyncClient.send/request` 全部被拦截；`test_traps_are_effective` 证明这些拦截确实有效。
* 整个 400-item 合成门槛在同样的拦截下运行。
* 前后文件系统快照没有变化；计划的库根目录从未被创建。
* 时钟 / `random` / `uuid` / `os.urandom` 都被拦截：输出仍然相等（`test_prepare_publication_uses_no_clock_random_or_uuid`）。
* 静态检查：publication 源码不做任何 I/O 类调用，只 import `__future__`、`dataclasses` 以及三个允许的项目 package。

## 12. 架构边界

`tests/contract/test_publication_architecture.py`：只允许特定的 import（`fc2_organizer.planning`、
`fc2_metadata_core.aggregation`、`fc2_metadata_core.models` 这些 package、自己的模块、`__future__`、`dataclasses`）；
`errors.py` 只使用标准库；`fc2_metadata_core` / planning / discovery 没有反向依赖；`fc2_organizer/__init__.py` 不 import
publication，`import fc2_organizer` 也不会加载它；在 meta path 上阻断 `amane` 的情况下端到端运行；Amane 没有安装；
恰好有 `{"discovery", "planning", "publication"}` 这些子 package。

作用域守卫的修改：`test_discovery_architecture.py` 和 `test_planning_architecture.py` 各恰好改了一行，
`{"discovery", "planning"}` -> `{"discovery", "planning", "publication"}`。**偏差说明：** 简报只点名了 discovery 文件需要做这一更新；
planning 文件带有完全相同的冻结 package 集合断言，否则会失败，因此在那里也应用了同样的一行更新。两个文件中的禁止 import
守卫都没有改动。

## 13. 合成发布门槛

`test_publication_synthetic_gate.py`：400 个互不相同的对（6-/7-位数字的番号；SUCCESS 134 / PARTIAL 266，涵盖单次 attempt、
重试过的、NOT_FOUND、BLOCKED、NETWORK_ERROR、PARSE_ERROR 等组合；Unicode 标题；集合 / mapping 类型的 metadata），
在文件系统 / 网络拦截下运行：400/400 被接受，第二遍逐条相等，每条记录都是 frozen 且不含诊断信息；800/800 个不匹配项被拒绝
（相邻条目的聚合结果 + 每个条目一个伪造的 metadata 番号）；50/50 个 FAILED 被拒绝。PASS。

## 14. 测试

环境说明：本主机共享的 pytest 临时根目录（`pytest-of-Ctg/pytest-current`）权限被拒绝，因此每次运行都在任务临时目录下使用
`--basetemp`，并加上 `-p no:cacheprovider`。普通的 `python` 会通过一个已安装的 `.pth` 把这些 package 解析到主检出目录；
pytest 的 `pythonpath = ["src", "tests"]` 会让它使用本 worktree 的 `src`（下面的直接复现使用了 `PYTHONPATH=src`）。

Frozen Base `b44ca7a` 处的基线（干净导出）：**2703 passed, 14 skipped, 0 failed**。

针对性测试（在 `1e66ab4` 上）：
```text
python -m pytest tests/unit/publication tests/contract/test_publication_architecture.py \
  tests/unit/aggregation/test_agg_c2_l2_trace_hardening.py \
  tests/unit/aggregation/test_agg_low1_result_invariants.py \
  tests/unit/aggregation/test_agg_retry_execution.py \
  tests/unit/resource_control/test_rc_breaker_execution.py \
  tests/unit/sources/adapters/test_javdb_p2_r10_single_unescape.py \
  tests/unit/sources/adapters/test_adapter_javdb.py \
  tests/unit/sources/adapters/test_adapter_javdb_semantics.py \
  tests/unit/sources/adapters/test_javdb_total_cost.py -q
-> 411 passed, 0 failed, 0 skipped
```

全量测试（在 `1e66ab4` 上）：`python -m pytest -q` -> **2924 passed, 14 skipped, 0 failed**
（+221 个新测试；P4-C1、P4-C2、Phase 3 的聚合 / 韧性 / 批处理 / 资源控制以及所有来源 adapter 测试集都通过）。14 个跳过是原有的
平台跳过（planning 测试中仅限 POSIX 的路径形式；一个 discovery 测试中的目录 symlink 权限），与基线完全相同。

直接复现（`PYTHONPATH=src`）：
```text
A  plan FC2-1234567 vs aggregate FC2-7654321 -> PublicationIdentityMismatchError (fail closed)
B  PARTIAL + valid metadata + matching plan  -> PublicationRecord(number=FC2-1234567, status=partial)
C  NOT_FOUND attempt then attempt 2           -> AggregationContractError
D  completed=False with PARSE_ERROR / NOT_FOUND / CONNECTION_ERROR / SUCCESS -> AggregationContractError (each)
E  JavDB title="A &amp;amp; B"                -> 'A &amp; B' (not 'A & B')
```

## 15. 已知局限

* `hash(PublicationRecord)` 会抛出 `TypeError`，因为 `NormalizedMetadata` 不可哈希（它的 mapping 是 `MappingProxyType`）--
  这是既有的语义，记录在合同第 11 节；相等性是完全确定的。
* trace 校验器固定的是 engine 的*形态*规则；它们不会重新推导一个仍有剩余 attempt 的可重试最终失败，究竟是被收窄的策略停止的，
  还是被一次过期的 C5 准入停止的（两者都合法，并且仅凭 trace 无法区分），也不会对照策略检查 `backoff_before_seconds` 的值
  （trace 不携带策略）。
* 在 planning 的模型层，`OrganizePlan.canonical_number` 仍然只检查是否为非空 `str`；发布时的规范性由传递关系保证
  （它必须等于满足最低成功标准的 metadata 番号）。

## 16. 延续的 finding

由本 package 关闭（等待独立复查）：
```text
P4-C2 metadata.number != canonical_number identity gap -- CLOSED AT P4-C3 BOUNDARY
C2-L2 -- CLOSED
P2-R-10 -- CLOSED
```

仍然延续、未改变：
```text
P4-C2-R1-02 -- LOW (bare "\\server" root)
OrganizePlan operation-graph model-level hardening
overwrite executor semantics -- frozen NEVER
extended Windows reserved-name edge cases
P4-C1-R-02, P4-C1-R-03, P4-C1-R-04, P4-C1-R-05
P2-R-05, P2-R-06, P2-R-07 (timing note recorded, contract section 14)
C3-N1, C3-N2, C3-N3, C3-N4, C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3, F3, F5, C5-R1-L1
```

P4-C3 没有触发任何新的冻结门槛。

## 17. git diff --check / status

```text
git diff --check b44ca7a1a3ca70dddf8686d9d14a98d52b481b82..1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f  -> clean
git status --porcelain (after the Docs Head commit)                                              -> empty
```

## 18. 状态

```text
Independent Review: REQUIRED
P4-C3:   NOT CLOSED
Phase 4: NOT CLOSED
```

没有开始任何后续 package（NFO 渲染器、图片下载、执行器、CLI、持久化、Amane adapter）。

---

# 最终关闭 -- P4-C3

```text
Phase:
4

Package:
P4-C3 Metadata Publication Boundary Hardening

Status:
CLOSED

Final Level:
Level 1 PASS

Final Reviewed Code Head:
1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f

Previous Docs Head:
3b16908a167259117140308f72e6310b216aea20
```

本节由一个纯文档的最终关闭提交追加。其上方的所有内容都是未改动的开发者 handoff 历史。本次关闭不触碰任何代码、测试或合同文件。

## 独立复查证据

```text
Independent Level 1 = PASS

Context Handshake = PASS
Scope = PASS

Publication boundary = PASS
Identity correlation = PASS
Diagnostic exclusion = PASS

P4-C2 metadata identity gap = CLOSED
C2-L2 = CLOSED
P2-R-10 = CLOSED

Targeted (reviewer's explicit review set):
246 passed / 0 failed / 0 skipped

Developer-equivalent targeted set:
411 passed / 0 failed / 0 skipped

Full Suite:
2924 passed / 14 skipped / 0 failed

Direct independent probes:
56 / 56 PASS

git diff --check:
clean
```

所有阻塞性的 P4-C3 finding 均已关闭。

P4-C3-R-01 和 P4-C3-R-02 被明确作为 LOW / 非阻塞项延续。

## 关闭目标

```text
P4-C2 metadata identity gap = CLOSED
C2-L2 = CLOSED
P2-R-10 = CLOSED
```

## 新的复查 finding（延续）

```text
P4-C3-R-01
Severity: LOW
Status: CARRIED / non-blocking
```

合同 / 本 handoff 中引用的部分测试名称与实际的 pytest 测试名称发生了漂移。实际的测试仍然被 pytest 正常收集和运行，因此正确性
不受影响。这是一个可追溯性 / 文档质量问题。本次关闭中没有修改（不修改测试或合同）。

```text
P4-C3-R-02
Severity: LOW
Status: CARRIED / non-blocking
```

publication 无副作用测试的内置正向对照，并没有逐一覆盖每一个拦截类别或每一条拒绝路径。独立复查者额外验证了全部 11 个拦截类别
确实有效，并且全部 6 条拒绝路径都不执行任何 I/O。因此当前的运行时行为是正确的；这是一个测试强度 / 抵御将来回归的能力方面的问题。
本次关闭中没有修改（不修改测试）。

## 延续的债务

```text
P4-C3-R-01 = LOW / CARRIED / non-blocking
P4-C3-R-02 = LOW / CARRIED / non-blocking

P2-R-07 = CARRIED

P4-C2-R1-02 -- LOW
OrganizePlan operation-graph hardening
overwrite executor semantics = frozen NEVER
extended Windows reserved names

P4-C1-R-02..R-05

P2-R-05
P2-R-06
P2-R-07

C3-N1..N4
C4-N1
C4-R1-N1..N3

F3
F5
C5-R1-L1
```

C2-L2、P2-R-10 以及 P4-C2 的 metadata 身份缺口已经 CLOSED，不再延续。

## 将来的入口说明（本次关闭未处理）

```text
P2-R-07 remains LOW / CARRIED.
  Future diagnostics publication must use engine-measured
  SourceAttempt.elapsed_ms rather than assuming adapter failure
  SourceResult.elapsed_ms is a trustworthy elapsed duration.

OrganizePlan operation-graph hardening
  remains an executor-entry gate.

overwrite = NEVER
  remains a frozen global executor semantic.
```

## 本次关闭的范围

这只关闭 **P4-C3**。它不关闭 Phase 4，也不开始任何后续 package；每一个后续 package 都需要自己的冻结合同和复查周期。

## 最终状态

```text
P4-C3: CLOSED
Phase 4: NOT CLOSED
Next Package: NOT STARTED
```
