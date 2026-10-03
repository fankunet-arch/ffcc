# Phase 4 / P4-C9 Handoff -- 结构化诊断（Diagnostics）

```text
Phase        = 4
Package      = P4-C9 Diagnostics（fc2_organizer.diagnostics）
Role         = Developer（S1 -> S2 -> S3 连续施工执行者）
Branch       = claude/phase4-c9-diagnostics
规范合同     = docs/specifications/PHASE4_DIAGNOSTICS_CONTRACT.md（Frozen Contract = dbb0c138…）
施工计划     = docs/P4_C9_CONSTRUCTION_PLAN.md（Frozen Construction Plan = dbb0c138…）
Risk Class   = B
```

**当前状态**：`P4-C9 implementation: COMPLETE — INDEPENDENT LEVEL 1 REVIEW REQUIRED`；`P4-C9 Independent Level 1 Review: NOT STARTED`；
`P4-C10: NOT STARTED`；`Phase 4: NOT CLOSED`。

本文件是 reviewer 证据文档，不是验收结论：Developer 没有自我 Review，没有修复任何 Review finding，也没有开始 P4-C10。

## 1. 坐标

```text
Repo                        = https://github.com/fankunet-arch/ffcc.git
Branch                      = claude/phase4-c9-diagnostics
Package Frozen Base         = a662659dfd6e801531b14af7913d84a5f9f859e2   P4-C8 Final Closure Docs Head
Governance Authority        = 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Original Design Candidate   = b5e98314eb64101b9da3b8c12a52c9044d73a60d   FAIL
Design-R1 Candidate         = ea32b37bab4c3440b83254466193212ae4be5ba8   FAIL
Design-R2 Candidate         = 00e5be38e7232e6dc34f3c194472e58470ceadd0   FAIL
Design-R3 Candidate         = 9f04e4f4baefdd4309f1bd34cb0c31ea5ba04f42   FAIL
Design-R4 Candidate         = dbb0c13809fbba698c56f00bfa47a1c1fe5bd9cf   PASS
Design Accepted Head        = dbb0c13809fbba698c56f00bfa47a1c1fe5bd9cf   (= Frozen Contract = Frozen Construction Plan = Implementation Input)
S1                          = 0be5201                                    feat(diagnostics): S1 models, errors, constants and architecture guards
S2                          = 6f01348                                    feat(diagnostics): S2 local validation and read-only projection
S3 内容提交                 = 8911617（render.py、S3 测试、HANDOFF 初版、状态行同步）
C9 Implementation Head      = 本提交（git log -1 --format=%H -- fc2-organizer/docs/review/P4_C9_HANDOFF.md；仅修正本文件中的 diff stat 表述，不含代码 / 测试改动）
Code Review Candidate       = C9 Implementation Head
Review Range                = dbb0c13809fbba698c56f00bfa47a1c1fe5bd9cf..<C9 Implementation Head>
```

实现提交线性（`0be5201^ == dbb0c13`、`6f01348^ == 0be5201`、`8911617^ == 6f01348`、C9 Implementation Head 的父提交 `== 8911617`）；没有 rebase、amend、squash、force push。
S1 / S2 没有修改合同、施工计划、HANDOFF 或任何状态行；只有 S3（`8911617`；本提交仅修正本文件的 diff stat 表述）新增本文件，并在同一提交中同步合同第 32 节与施工计划
第 10 节的状态行（仅状态文字，无语义改动）。

## 2. 变更范围与 diff scope 核对（施工计划第 5 节）

`git diff --stat dbb0c138 HEAD`：46 个文件、约 +1.2 万行 / -30 行（构成：3 个 docs + 7 个 production + 8 个 contract 测试文件〔1 个新增 diagnostics architecture test + 7 个已有 architecture guard 修改〕+ 28 个 tests/unit/diagnostics 新增文件 = 46；精确行数以在 C9 Implementation Head 上执行该命令的结果为准，本文件自身计入其中）。

```text
src（只含 diagnostics，7 个新增模块）
A src/fc2_organizer/diagnostics/{__init__,errors,models,validation,projection,build,render}.py

tests/contract
A tests/contract/test_diagnostics_architecture.py
M tests/contract/test_{discovery,planning,publication,nfo}_architecture.py            顶层集合加入 "diagnostics"（合同第 27.3 节）
M tests/contract/test_{execution,materialization,orchestration}_architecture.py        exempt / 跳过 diagnostics + 更严格的 import 名称断言（合同第 27.3 节）

tests/unit/diagnostics（28 个新增文件 = 26 个 test_*.py + __init__.py + _builders.py）

docs
A docs/review/P4_C9_HANDOFF.md
M docs/specifications/PHASE4_DIAGNOSTICS_CONTRACT.md    仅第 32 节状态行
M docs/P4_C9_CONSTRUCTION_PLAN.md                       仅第 10 节状态行
```

核对结果：

* `git diff --name-only dbb0c138 HEAD -- fc2-organizer/src` 只列出 `src/fc2_organizer/diagnostics/*.py` 七个文件；
  **`src/fc2_organizer/orchestration/**` 及任何 CLOSED package 的生产代码、`CLAUDE.md`、`docs/PROJECT_GOVERNANCE_ACCELERATION.md`、
  `pyproject.toml`、`upstream/**`、任何其它合同 / 施工计划 / HANDOFF 均无改动**（`git diff --name-only dbb0c138 HEAD -- fc2-organizer/pyproject.toml` 为空）。
* `tests/unit/orchestration/_fakes.py`、`_helpers.py` 只读复用（`from orchestration._helpers import …`），未修改。
* 没有新增依赖、网络、文件写入、持久化、日志挂钩；没有 `discover_media`、上游 `revalidate` / `__post_init__` / private / dunder 校验调用。
* 测试辅助（`_builders.py`）把 hostile 输入设备（`Hostile`、`HostileInt`、`HostileTuple`、`HostileFrozenSet`、`HostileBytes`、
  `hostile_instance`、`plant_*`、`assert_fail_closed`）并入，没有新增施工计划第 4 节清单之外的文件。
* `git diff --check dbb0c138 HEAD` 干净；`git status --porcelain` 为空（`__pycache__` 由 `.gitignore` 忽略）。

生产模块（`git hash-object --no-filters`，提交后与 HEAD blob 逐字节一致，见第 9 节）：

```text
27a80fb30ca437c5e8083196f88b9e4883a9816a  src/fc2_organizer/diagnostics/__init__.py
538a560f307377c7203c0ce061aa564903ad6966  src/fc2_organizer/diagnostics/build.py
6354f7097a07dea15a185195e1ad0139d2f88496  src/fc2_organizer/diagnostics/errors.py
514f1444132d55e0430ac3cb804adc69897bc5bb  src/fc2_organizer/diagnostics/models.py
2b30e93f2d597cdbc5ef6e0194f6b34328693b8e  src/fc2_organizer/diagnostics/projection.py
d4b53498509f2ff3fe333ba75795af14c1a6edea  src/fc2_organizer/diagnostics/render.py
bb63d11d8435bad3457646565e291a222f725191  src/fc2_organizer/diagnostics/validation.py
```

## 3. 实现概览

| 模块 | 职责（合同节） |
|---|---|
| `errors.py` | 7 个错误类的层次与固定措辞（第 8.4 节）；只 import `__future__` |
| `models.py` | 4 个新枚举、13 个 frozen+slots 诊断模型及其模块级 `*_problem` 校验函数、公开 / 内部常量（`MAX_PROVENANCE_KEYS`、`MAX_TIMING_SECONDS` 仅内部）、T-1..T-4 冻结表（不可变 tuple + 查表函数）、S2 内部校验快照 dataclass（第 8、11、21、22 节） |
| `validation.py` | 输入权威：validate-before-dispatch 本地校验（M-01..M-30、第 9.6 节跨对象关系）、`field_sources` 有界单遍 key 扫描、Numeric Totality、`PathPolicy` / `TimingPolicy` 安全输出与毫秒转换、第 7 步批准 property 读取（第 9、24.2 节） |
| `projection.py` | 只读校验快照 -> 诊断模型的确定性投影（第 10-16 节） |
| `build.py` | `build_preview_diagnostics` / `build_execution_diagnostics`（第 8.2、24.2 节） |
| `render.py` | `render_diagnostics_json`（第 22、24.4、21.3 节）：本地重检诊断图 -> 显式 JSON 树（按位置的第 17.2 节白名单）-> 有界流式编码；唯一 `try`，只捕获 `ValueError` / `TypeError` / `RecursionError` / `OverflowError`，在 `except` 之外抛 `DiagnosticsSerializationError`（无链接） |
| `__init__.py` | 合同第 8.1 节最终 `__all__`（39 个名称：3 个函数 + 4 枚举 + 13 模型 + 12 常量 + 7 错误；`MAX_PROVENANCE_KEYS`、`MAX_TIMING_SECONDS` 不在任何阶段 `__all__`） |

## 4. Contract -> implementation -> test 映射

### 4.1 本地校验（第 9.5 节 M-01..M-30）

| 行 | 生产位置（`validation.py`） | 主要测试 |
|---|---|---|
| M-01 / M-02 `BatchPreview` / `BatchExecutionResult` | `check_batch_scalars`、`build_*_snapshot`、`local_shape`、`check_scope` | `local_validation`、`tamper`、`input_integrity`、`retry_material` |
| M-03 `BatchLineage` | `check_lineage` | `tamper`（lineage）、`local_validation`（lineage token） |
| M-04 policy / checkpoint / unit 类型确认 | `check_batch_scalars`、`check_retry_material`、`check_preflight` | `local_validation`（字段覆盖扫描：type-only 字段列入“不读取”清单） |
| M-05 / M-06 `ItemPreview` / `ItemExecution` | `check_item_core`、`check_preview_item`、`check_execution_item`、`check_item_warning_relations` | `tamper`、`local_validation`、`retry_material`、`malicious_subclass` |
| M-07 `ItemIssue` | `check_issue`（T-1） | `local_validation`（T-1 逐行） |
| M-08 / M-09 summaries | 第 7 步后调用 `models.preview_summary_problem` / `execution_summary_problem` | `preview`、`execution`、`dispatch_safety`（D-28） |
| M-10..M-13 media / plan / planned path / operation | `check_media_item`、`check_planned_path`、`check_plan`（含第 9.6.5 节布局） | `tamper`、`path_policy`、`local_validation` |
| M-14 / M-15 `BatchResult` / `BatchItemResult` | `check_metadata_batch`、`check_batch_item_result` | `tamper`、`numeric_totality` |
| M-16 `AggregationResult` | `check_aggregation`（Phase V -> Phase R） | `tamper`、`dispatch_safety`、`sources` |
| M-17 / M-19 / M-20 / M-21 | `check_source_result`、`check_trace`、`check_attempt`、`check_conflict` | `sources`、`tamper`、`local_validation`（T-2） |
| M-18 `NormalizedMetadata` / provenance | `scan_field_sources`、`metadata_meets_minimum` | `provenance`、`upstream_characterization`、`resources` |
| M-22 `ImageCandidateFailure` | `check_image_failure` | `preview`、`local_validation`（字段覆盖扫描） |
| M-23 / M-24 / M-25 preflight / artifact / blocker | `check_preflight`、`check_artifact_request`、`check_artifacts`、`check_manifest_layout` | `tamper`、`retry_material`、`resources`（256 / 257） |
| M-26..M-29 execution result / effect / failure / leftover | `check_execution_result`、`check_effect`（T-3）、`check_leftover` | `tamper`、`local_validation`（T-3）、`execution` |
| M-30 `RetryMaterial` | `check_retry_material` + `check_execution_item` 的存在性 / 身份 / checkpoint 关系 | `retry_material`、`mutations` |

`tests/unit/diagnostics/test_diagnostics_local_validation.py` 的**字段覆盖扫描**（preview 与 execution 图中每个 dataclass 节点的每个字段
替换为 `object()`）证明：每个被消费字段要么 fail closed（`DiagnosticsIntegrityError`），要么属于合同第 9.5 节明文“不读取”清单（M-04
checkpoint 内容 / policy 字段、M-18 其余 metadata 字段、M-23 的 `library_root_identity` / `source_identity`、M-27 的
`path` / `identity` / `size` / `sha256`）且输出逐字节不变。

### 4.2 第 9.6 节跨对象关系

9.6.1 / 9.6.2（shape、index、generation、library_root、冲突图、retained 预算按引用计数）-> `build_preview_snapshot` /
`build_execution_snapshot`、`check_indices`、`check_conflict_graph`、`retained_preview_bytes`、`retained_retry_bytes`；9.6.3 / 9.6.4 ->
`check_item_core`、`check_preview_item`、`check_execution_item`、`expected_retry_kind`；9.6.5 ->
`check_plan` / `check_manifest_layout`；9.6.6 -> `check_aggregation`、`check_conflict_with`、`scan_field_sources`。
测试：`local_validation`、`tamper`（136 例）、`retry_material`（37 例）、`mutations`。

### 4.3 Dispatch Safety Matrix（第 9.10 节）与 Horizontal Audit（第 9.11 节）

`test_diagnostics_dispatch_safety.py`（60 例）：每个非 NOT USED 行（D-01..D-05、D-07..D-19、D-23..D-31）至少一个 docstring 以
`[D-xx]` 开头的测试，并由 `test_every_dispatch_matrix_row_has_a_tagged_test` 强制；NOT USED 行 D-06 / D-20 / D-21 / D-22 由 AST 测试
（`len` 不作用于 proxy；`sorted` / `min` / `max` / `.sort` 零调用；零 `str` / `repr` / `format` / f-string / `%` 格式化）加 sentinel 测试证明。

H-01..H-15 -> `test_diagnostics_malicious_subclass.py`（142 例）：preview 图 16 个对象植入点、execution 图 12 个对象植入点、
16 + 9 个容器 x（`Hostile` 对象 / `EvilStr` / `HostileInt`）三类元素、`tuple` / `frozenset` / `bytes` 子类容器、`retry_scope` 恶意元素；
每例断言 `DiagnosticsIntegrityError`（exact type）且全部 sentinel（`__hash__` / `__eq__` / `__ne__` / `__lt__` / `__bool__` / `__len__` / `__iter__` /
`__repr__` / `__str__` / `__format__` / `__getattribute__`）为 0。每个图先由上游公开构造器构造并先 build 成功（排除“本来就非法”的假阳性），
**在整个上游图构造完成之后、调用 builder 之前复位 sentinel**（Sentinel 复位规则）；`test_the_harness_is_not_vacuous…` 证明 hook 确实会计数。

批准 property 依赖图（第 9.3.1 节）：`dispatch_safety` 把五个批准 property 临时包成读取计数器；干净输入每个至少被读取一次，14 种依赖图
破坏在 property 被读取之前 fail closed（读取计数 0）；`retry_kind` 一致性先于 `summary` / `outcome` 的顺序也被断言。

### 4.4 R2-01 `field_sources`（key 扫描）

* `test_diagnostics_upstream_characterization.py`（13 例）：UC-1..UC-9 固定上游事实（`EvilStr` key 经公开构造器被接受且不被规范化；构造期
  hook 确实执行；非 `str` key 被拒；`MappingProxyType` 与快照隔离；`str` 子类 id 被接受；真实 Phase 3 producer 全字段 populate 恰为 15 个 key；
  `for key in proxy` 不触发 hook 而 `"title" in proxy` 触发子类 `__eq__`）。
* `test_diagnostics_provenance.py`（54 例）：非精确 proxy / 非精确 tuple / 子类元素 / 非 contributing id；固定字段顺序（插入顺序反转 / 打乱逐字节相同）；
  unknown exact-`str` key 被计数、不投影；`EvilStr` 变体 (a) 同名 known、(b) unknown 名、(c) hash 冲突、(d) 首 / 中 / 末位置、(e) 与合法 key 同批、
  (f) value 合法、(g) V-4 先出现者决定错误类型；Normal-Key Positive Control；`MAX_PROVENANCE_KEYS` 64 通过 / 65 失败 / 10x 失败 / 第 65 个之后的
  `EvilStr` 不被读取；`validation` 命名空间 tripwire（`list` / `dict` / `sorted` / `set` / `len` 作用于 proxy 即记录）证明不物化。
* mutation：见第 5 节。

### 4.5 Numeric Totality（第 9.12 节 N-01..N-15）

| 行 | 实现 | 测试 |
|---|---|---|
| N-01 / N-04 / N-05 | `check_number`（`math.isfinite` 仅作用于 exact `float`；校验型字段无上界、不转换） | `numeric_totality` 全部 13 类 x 5 字段 x OMIT / INCLUDE |
| N-02 / N-03 / N-14 | `require_int` 等：exact int 只与 int 常量比较 | `local_validation`（范围边界表）、`numeric_totality`（巨大 int 计数 / 预算 / 下标） |
| N-06 | `publish_elapsed_ms`（先 gate 后 `int()`） | 边界值冻结表逐行 |
| N-07 / N-08 / N-09 | `publish_backoff_ms`（SAFE BOUND BEFORE MULTIPLY；int `> 604800`、float `> 604800.0` 拒绝，之后才 `* 1000` / `int()`） | 边界值冻结表逐行（含 `math.nextafter(604800.0, inf)` 与 R3 截断值 `604800.0005`） |
| N-10 | `TIMING_MS_GATE` / `BACKOFF_SECONDS_GATE` 为模块常量（导入时由小 int 常量派生；`float(int)` 从不作用于 caller 数值） | `numeric_totality`（isfinite tripwire 与“先转换”变异）、`public_api`（`MAX_TIMING_SECONDS == MAX_TIMING_MS // 1000`） |
| N-11 | `check_attempt`（`sequence == 1` 且 backoff 非零 -> Integrity，同型比较） | `numeric_totality`（含 `10**400` / `1e306`） |
| N-12 / N-13 | exact int 算术与预算比较 | `retry_material`、`numeric_totality` |
| N-15 | `render_diagnostics_json` 的单一 `try` | `render`（`sys.set_int_max_str_digits(640)` + `10**1000`：build 成功、render 抛 exact `DiagnosticsSerializationError`，无链接；`finally` 复位） |

`math.isfinite` tripwire：遮蔽 `validation` 命名空间的 `math`，实参非 exact `float` 即失败；合法与巨大 int 输入均不触发，并有非空洞性用例。
所有失败输入断言捕获到的是 `DiagnosticsError` 层次且 `type(exc) not in (OverflowError, ValueError, TypeError)`（判据是 exact type，不是 `isinstance`）。
`TimingPolicy` 语义见 `test_diagnostics_timing.py`。

## 5. mutation / non-vacuity 表（第 28.5 节）

所有变异都只存在于测试进程内，**不提交**，也不写盘：`test_diagnostics_mutations.py` 把真实 `validation.py` 源码做单点替换后，在真实模块命名空间
的副本中（丢弃 import 语句，沿用真实类对象）编译为一次性模块，换入 `build` 一个 `with` 块；块结束后断言：七个生产源文件的 SHA-256 与块前相同、
`validation` / `build` 中全部可调用对象的 `id` 与块前相同（**hash / object restore proof**）。其余变异用 `monkeypatch`（函数级）实现，撤销后同样由测试
隔离。提交后另以 `git hash-object --no-filters` 对工作树文件与 HEAD blob 逐字节比较（第 9 节）。

“杀死”的判据：未变异代码对该场景得到预期的类型化错误且 sentinel 为 0，而变异体接受输入、抛不同错误或触发 hook。

| 类别（合同第 28.5 节） | 变异 | 文件 | 杀死机制 / 失败用例 |
|---|---|---|---|
| fail closed / 本地校验 | 跳过 `SourceResult.metadata`、`OrganizePlan`、`ArtifactWriteRequest`、`BatchResult` 的精确类型检查 | `mutations` | hostile 对象被接受或 hook 触发（4 例） |
| 同上 | 跳过第 9.6.5 节 plan 布局检查 | `mutations` | library_root 篡改被接受 |
| 同上 | 跳过 `retry_material` 存在性 / `material.plan is item.plan` / RESUME checkpoint 身份 / FRESH 无 checkpoint（逐项） | `mutations` | 对应 `retry_material` 篡改被接受（4 例） |
| 同上 | 跳过 retained 预算（preview / execution 各一） | `mutations` | 预算为 1 的输入被接受（2 例） |
| 同上 | 信任 `retry_kind` property 而不比较本地推导 | `mutations` | 说谎的 property 被接受 |
| 同上 | 跳过条目数上限（`MAX_DIAGNOSTIC_ITEMS` -> `10**9`） | `mutations` | 2001 条得到 Integrity 而非 ResourceLimit |
| 同上 | 在第 7 步之前读取 `summary` | `mutations` | property 读取计数器 != 0 |
| 同上 | 生产代码调用上游 `__post_init__` | `mutations` + `no_upstream_validators` | tripwire 计数 != 0（并有 `gc.get_referents` sentinel） |
| 无副作用 | 投影 / 校验时 `open(...)` | `mutations` + `no_side_effects` | 陷阱抛 `AssertionError` |
| R2-01 key 扫描 | 边验边查（`name in proxy` 先于 key 验证）、跳过 `type(key) is str`、只验 known key、先物化再检查（`list` / `dict` / `sorted` / `set` / `len` 逐一）、去掉 / `>` 改 `>=` / 放宽一位的上限、计数在检查之后、unknown 不计数、第 65 个 key 之后继续读取 | `provenance` | 独立重实现 + 6 个 gate 场景（`evil_known` / `evil_unknown` / `over_limit` / `exact_limit` / `unknown_only_over` / `early_stop`）；无缺陷的参考实现通过全部 gate（harness 非空洞）；共 10 个定点变异 + 5 个物化变异被杀 |
| Phase V -> Phase R | 成员判定先于同一容器 Phase V 全部完成 | `dispatch_safety`、`mutations` | `EvilStr.__eq__` sentinel 触发 |
| R3-01 数值 | 先转换后检查（`int(s * 1000)` 在 gate 之前）、截断后比较（R3 语义）、`float(int)` / 对 exact int 调用 `math.isfinite`、去掉 / 偏移上界 gate（`604800` -> `604801`）、`OMIT` 下强加上界 | `numeric_totality`、`mutations` | 巨大 int / `1e306` 得到裸 `OverflowError`、边界值失败、`isfinite` tripwire |
| 脱敏（A 类） | 默认改为 `BASENAME`；`NONE` 下仍输出 basename；输出 absolute path / 父目录；树中附带 error_detail / 异常文本 | `redaction` | canary 扫描失败或 pipeline 抛错 |
| 控制字符 basename | 去掉禁止码点检查（validation 与 model 两层都去掉后，`U+202E` 才进入输出） | `redaction` | 两层防线均被证明有效 |
| 排序 / 确定性 | 按 `field_sources` 插入顺序输出；输出临时 id；items 反转 | `determinism` | 字节比较失败 / 模型不变量拒绝 |

## 6. 输入校验证据

* **AST 零 `_` 属性访问**：`test_no_attribute_access_starts_with_an_underscore`（所有 diagnostics 模块，含 `__post_init__` / `__dict__` / `__class__`，无豁免）PASS。
* **AST 零反射 / `gc` import**：`test_forbidden_modules_are_never_imported`（`gc`、`inspect`、`ctypes`、`sys`、`pickle`、`marshal`、`copyreg`、`weakref`、`traceback`、
  `builtins`、`copy` 等）与 `test_package_modules_expose_no_gc_or_introspection_attribute_at_runtime` PASS；`sorted` / `min` / `max` / `getattr` / `isinstance` / `str` 等被禁止
  名称零引用；`validation.py` 零 `keys` / `values` / `items` / `get` / `copy` 方法调用。
* **运行时 sentinel 计数 0**：`test_diagnostics_no_upstream_validators.py` 把 27 个上游类的 `__post_init__` 与全部公开方法 / property（批准的五个除外）以及
  `gc.get_referents` 替换为触发即失败的 sentinel（>60 个目标），合法输入的 build 全部成功、计数 0；tripwire 非空洞用例证明其会触发。
* **恶意子类植入点**：第 4.3 节清单；**篡改用例**：`tamper` 136 例（preview 88 个、execution 41 个篡改 + 6 个“不被读取”字段的输出不变用例 + 1 个非空洞用例），每例断言
  (A) 类型化失败、(B) 在 projection 之前（投影函数计数 0）、(C) 无部分结果、(D) 无 hook、(E) 输入逐字段不变且节点身份不变。
* **`RetryMaterial` / retained 预算篡改**：`retry_material` 37 例；六种 `RetryKind` 的本地推导与 P4-C8 逐条相等；`PREFLIGHT_RECHECK` / `DEFERRED` 的 `checkpoint` 为
  `None` 与精确对象均被接受；共享 bytes 按引用重复计数；输出不含 `content`。
* `pyproject.toml` 未改动（第 2 节）。

## 7. 其它证据

* **脱敏**（`test_diagnostics_redaction.py`，22 例，真实 `BatchOrchestrator` + `Corpus`）：A 类 canary 14 项（`C9CANARY-AUTH` / `-COOKIE` / `-TEXT` / `-URL` / `-KEY` /
  `-VAL` / `-EXC` / `-PLOT` / `-DETAIL`、`C9CANARYDIR`、`C9CANARYROOT`、`Bearer`、`session=`、`token=`）在 `NONE` x `OMIT` / `INCLUDE`、`BASENAME` x `OMIT` / `INCLUDE`
  四种组合下均不出现；默认 `NONE` 下 `Authorization-` / `Cookie-` / `token-C9CANARY` 文件名完全不出现；显式 `BASENAME` 下这些可打印 basename 出现且父目录 canary 不出现；
  8 种控制字符 basename（`\x01`、`\x1b`、`\x7f`、`\x85`、`U+2028`、`U+202E`、`U+FEFF`、孤立代理）在 `BASENAME` 下 `DiagnosticsUnsafeValueError`、在 `NONE` 下成功且不泄露。
* **确定性**（`determinism`，11 例）：两次独立真实运行（不同 tmp、不同 preview / result id、lineage token、preflight id、seal）渲染逐字节相同（`NONE` 与 `BASENAME`）；
  临时身份字符串不出现在输出；`field_sources` 插入顺序、`frozenset` 迭代顺序不影响输出；golden 输出固定；`scale_gate` 的 500 条也做临时身份替换后逐字节比较。
* **资源**（`resources` 31 例 + `scale_gate` 7 例）：12 个结构上限各有“恰为上限不是 ResourceLimit / 上限 + 1 为 `DiagnosticsResourceLimitError` 且发生在迭代之前（占位元素证明）”；
  256 blockers / 256 leftover 的合法输入 build + render 成功、257 失败；输出字节上限（精确长度成功、减 1 失败、编码在超限后停止、无部分输出）；
  2000 条 preview 渲染 3,203,664 字节（build 0.39 s + render 0.37 s）、2000 条 execution 3,189,081 字节（0.41 s + 0.44 s），远低于 64 MiB；
  2000 条 x 64 个 `field_sources` key 的上限内最坏输入仍成功；2001 条在任何逐条访问之前失败（计数 fake 证明）。
* **无副作用**（`no_side_effects` 16 例 + `integration`）：`BatchOrchestrator.preview` / `execute` / `preview_retry`、`preflight_execution`、`execute_filesystem`、`builtins.open`、
  `os.{stat,lstat,listdir,scandir,mkdir,rename,replace,unlink,remove,rmdir,makedirs,chmod,utime,symlink,link,readlink}`、`os.path.{exists,realpath,islink,isfile,isdir,getsize,getmtime,lexists,samefile}`、
  `socket.socket`、`threading.Thread.start`、`asyncio.new_event_loop` / `asyncio.run`、`logging.Logger.handle` 全部替换为抛错陷阱后，四种策略组合的两个 builder 仍成功；
  文件系统树快照（路径 / 类型 / 大小 / mtime_ns / 内容 hash）诊断前后相同；fake engine / image client 调用计数增量为 0；输入图逐字段相等且节点身份不变；诊断后 preview 仍可 `execute`、
  result 仍可 `preview_retry`、retry result 仍可 `merge_retry`。
* **集成**（`integration`，11 例，真实 P4-C8 + 脚本化 fake + `tmp_path`）：SUCCESS / PARTIAL / FAILED 批；BLOCKED、UNPREPARED（含 engine 异常与 FAILED aggregate、番号不可识别）；
  metadata partial 与图片 warning（缺失 poster / thumb、`NO_EXTRAFANART`、候选失败 404）；execution PARTIAL -> RESUME、FAILED -> FRESH_REEXECUTE、`METADATA_REFETCH`、
  `PREFLIGHT_RECHECK`、DEFERRED（`NOT_SELECTED` 与 `CANCELLED`）、ABORTED（含 `C9CANARY-EXC` 不泄露）；retry preview、retry round 与 merged result；每个场景在默认 `NONE`
  与显式 `BASENAME` 下各渲染一次并同时断言模型与 JSON。

## 8. 测试数字（本地执行证据；见 evidence gaps）

环境：Linux（沙箱）/ Python 3.11.15（项目运行时下限 `>= 3.11`）。命令均在 `fc2-organizer/` 下：
`python -m pytest -q -p no:cacheprovider --basetemp=<tmp>`（全量加 `--continue-on-collection-errors`，因为基线在本环境已有 2 个收集错误）。

| 范围 | 结果 |
|---|---|
| P4-C9 专项：`tests/unit/diagnostics` + `tests/contract/test_diagnostics_architecture.py` | **1580 passed**，0 failed，0 skipped |
| targeted organizer：`tests/unit/orchestration` + `tests/contract` | 5 failed / 1145 passed / 5 skipped（5 个失败与 `dbb0c138` 基线逐项相同） |
| contract：`tests/contract` | 3 failed / 234 passed（3 个失败与基线逐项相同） |
| 全量（含 `--continue-on-collection-errors`） | **338 failed / 7190 passed / 94 skipped / 26 errors**（collected 7645，另有 2 个基线既有的收集错误） |

回归判据：`dbb0c138` 干净基线在同一环境为 **338 failed / 5607 passed / 94 skipped / 26 errors**；本实现的失败 / 错误集合与基线**逐项相同**（`diff` 为空，共 364 行，其中
0 行与 diagnostics 相关）；passed 增加 1583（1580 个 P4-C9 测试 + 3 个 S1 授权守卫改动新增的 import 名称断言）；skipped 数字不变（**新增 skip = NONE**）；P4-C9 的核心测试无 skip。

## 9. mutation 撤销后的逐字节恢复

生产源码没有任何变异落盘。提交后：`git hash-object --no-filters fc2-organizer/src/fc2_organizer/diagnostics/*.py` 与 `git rev-parse HEAD:<path>` 对七个文件逐一相等（第 2 节列出的 blob）；
`git status --porcelain` 为空。

## 10. 风险升级门核对（计划第 4.1 节 A-K）

A-K 均**未触发**：未修改任何 CLOSED package 的生产语义或 `src/fc2_organizer/orchestration/**`；未新增依赖；未新增文件写入 / 网络 / 持久化 / 日志 / 线程；未读取合同第 9.9 节以外的字段；
公开 schema / `PathPolicy` / `RetryMaterial` / 资源模型 / 序列化 / S 边界无偏离；未出现需要 Contract amendment 的设计冲突。
`BLOCKED DESIGN ISSUE`：**NONE**。

## 11. Evidence gaps 与已知局限

* **验收证据环境缺口**：合同第 28.7 节的验收证据环境是 Windows 11 / Python 3.12.x；本施工在 Linux / Python 3.11.15 沙箱完成。仓库既有测试大量面向 Windows（`C:\…` 路径等），
  基线在本环境即有 338 failed / 26 errors / 2 个收集错误；因此**无法**复现“全量 passed >= 6178 / skipped = 40”的绝对数字，只能提供“与基线失败集合逐项相同、skipped 不变、
  新增测试全部通过”的相对证据。Windows / Python 3.12 的权威数字需 reviewer 在验收环境重跑（EVIDENCE GAP，未伪造 PASS）。
* POSIX 与 Windows 的 `os.path.basename` / 绝对路径语义不同：路径策略与 plan 布局测试通过 `os.path` 派生期望值，在本环境以 POSIX 语义运行；Windows 原生路径行为未在本环境验证。
* mutation 测试是**源码级单点替换**（对真实 `validation.py` 源码做文本替换后编译），目标文本须在源码中恰出现一次；生产代码重构会使其显式失败（`compile_mutant` 断言），不会静默放过。
* 测试之间的隔离：既有的七个架构守卫会 `_purge` `sys.modules` 而不恢复；为此 P4-C9 测试不使用函数内局部 `import fc2_*`（全部提升到模块顶层），变异体沿用真实模块的类对象。
  这是为在全量套件的任意顺序下保持稳定而做的测试侧防护，不涉及生产代码。
* 瞬时失败记录：全量套件首次运行（`--maxfail` 之前的 `-x` 运行）因基线既有的 2 个收集错误而中断；加 `--continue-on-collection-errors` 后第一次完整运行出现 253 个新增失败，
  根因是 `tests/unit/diagnostics/_builders.py` 的一个函数内局部 `import`（被既有守卫 `_purge` 后得到另一份枚举类）；已把全部局部 import 提升为模块级并让变异体沿用真实命名空间，
  之后的完整运行与基线失败集合逐项相同。该修复只涉及测试文件。
* 合同第 31 节已知局限保持不变（不满足安全 id 规则的 source 配置 fail closed；`BASENAME` 是披露策略而非脱敏保证；不 introspect `MappingProxyType` 隐藏 referent，第 9.0 节 C 层）。

## 12. 停止位置

```text
P4-C9 Implementation          : COMPLETE
P4-C9 Independent Level 1 Review : NOT STARTED
P4-C10                        : NOT STARTED
Phase 4                       : NOT CLOSED
```

Developer 在此 STOP：不自我 Review、不修复 Review finding、不开始 P4-C10；等待 P4-C9 Independent Level 1 Review
（Review Range = `dbb0c13809fbba698c56f00bfa47a1c1fe5bd9cf..<C9 Implementation Head>`）。

---

## P4-C9 最终闭合

**快照声明**：本文件第 1-12 节是对应历史时点（Level 1 Review 之前，Candidate `fa0946206d503ae3656e3721a1762ebb829694dd` 的上一轮 implementation）的 evidence
snapshot。其中“INDEPENDENT LEVEL 1 REVIEW REQUIRED”“NOT STARTED”“Linux 沙箱数字”“Windows 11 / Python 3.12 evidence gap”以及第 11 节的 diff stat 表述等文字，均不删除、不篡改；
它们之后的 Review、finding 与 Windows 正式验收的结论以本章节为准。P4-C9 的最终状态以本章节为准。

### 最终状态

```text
Final Level 1 Review          : PASS
P4-C9-L1-01                   : CLOSED
P4-C9-WIN-01                  : CLOSED
All Level 1 Findings          : CLOSED
Final Reviewed Package Head   : 9cd7bf56ba98878145cdae95456edd6ef9fb2ae9
Windows Acceptance            : PASS
P4-C9 Implementation          : REVIEWED COMPLETE
P4-C9                         : CLOSED
P4-C10                        : NOT STARTED
Phase 4                       : NOT CLOSED
Final Closure Docs Head       : 本提交（git log -1 --format=%H -- fc2-organizer/docs/review/P4_C9_HANDOFF.md）
```

最终裁决事实：已知代码 finding = NONE；已知合同 finding = NONE；已知安全 finding = NONE；剩余 evidence 阻塞 = NONE；风险升级门 A-K = NONE；Risk Class = B；
BLOCKED DESIGN ISSUE = NONE。

### 历史记录（如实保留，不改写）

| 轮次 | Candidate | 结论 |
|---|---|---|
| Original Level 1 | `fa0946206d503ae3656e3721a1762ebb829694dd` | **FAIL**。Finding `P4-C9-L1-01`（LOW / BLOCKING）：HANDOFF 把 `tests/unit/diagnostics` 的新增文件数写成 26 个（含 helpers），实际为 28 个（26 个 `test_*.py` + `__init__.py` + `_builders.py`） |
| C9-R1 | `44b9c960a943468566225879ce489983253e2e0c` | `P4-C9-L1-01` CLOSED；Implementation Code Review PASS；Final Verdict **BLOCKED**，唯一阻塞 = Windows 11 / Python 3.12 验收证据 |
| 首次 Windows 正式验收 | `44b9c960a943468566225879ce489983253e2e0c` | **FAIL**。P4-C9 专项 1578 passed / 2 failed / 0 skipped；全量 7759 passed / 2 failed / 40 skipped / 0 errors。两个失败均在 `test_diagnostics_path_policy.py` 的 `[backslash]` 用例，形成 `P4-C9-WIN-01` |
| C9-R2 | `9cd7bf56ba98878145cdae95456edd6ef9fb2ae9` | 仅测试修复（只改 `tests/unit/diagnostics/test_diagnostics_path_policy.py`）；Production UNCHANGED；Frozen Contract UNCHANGED。最终 Windows 复验全部通过；`P4-C9-WIN-01` CLOSED；Final Verdict **PASS** |

`P4-C9-WIN-01` 根因：测试契约不一致 / 平台原生 basename 语义——测试把 raw path 中的 `\` 等同于最终披露 basename 中的 `\`。Frozen Contract 第 18.1 节规定
`os.path.basename` 使用运行平台的路径语义，第 18.2 节 grammar 作用于已提取的最终 basename；因此 Windows 上 `/lib/FC2-1/a\b.mp4` 提取为合法的 `b.mp4`，当时的 production 行为符合 Frozen Contract。
**不是 production 缺陷，不是 Frozen Contract 缺陷。** C9-R2 把“最终 basename grammar（`/` 与 `\` 在所有平台均禁止）”与“native extraction（由运行平台的 `os.path.basename` 决定）”分开断言，且没有使用 skip / xfail。

### 最终验收环境与结果

```text
操作系统 : Windows 11（Microsoft Windows NT 10.0.26200.0）
Python   : 3.12.10（MSC v.1943 64 bit）
```

| 范围 | 结果 |
|---|---|
| 路径策略 fail-fast | 102 passed / 0 failed / 0 skipped / 0 errors |
| P4-C9 专项 | 1586 passed / 0 failed / 0 skipped / 0 errors |
| targeted organizer | 1156 passed / 0 failed / 0 skipped / 0 errors |
| contract | 237 passed / 0 failed / 0 skipped / 0 errors |
| 全量 | 7767 passed / 0 failed / 40 skipped / 0 errors |
| 新增 skip | NONE（diagnostics skip = 0） |

冻结 gate：`passed >= 6178`、`failed = 0`、`errors = 0`、`skipped = 40`、新增 skip = NONE —— **全部 PASS**。

Windows 路径语义：Native Windows Backslash Extraction = PASS；Final `/` Basename Grammar = PASS；Final `\` Basename Grammar = PASS；`PathPolicy.NONE` = PASS；`PathPolicy.BASENAME` = PASS；Plan Layout = PASS。

### 最终审查结论摘要

Production correctness review = PASS；Contract conformance = PASS；Dispatch Safety = PASS；Numeric Totality = PASS；Renderer = PASS；Redaction = PASS；Determinism = PASS；
Resources = PASS；No Side Effects = PASS；Architecture = PASS；Mutation / Non-Vacuity = PASS；Windows path semantics = PASS。

### 停止位置

P4-C9 已 CLOSED。P4-C10 = NOT STARTED，不在本章节范围内；Phase 4 = NOT CLOSED。
