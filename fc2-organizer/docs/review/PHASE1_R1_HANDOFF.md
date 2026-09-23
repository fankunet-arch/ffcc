# PHASE1_R1_HANDOFF.md

```text
Phase: Phase 1 R1 — Incremental Closure Fix (R1-01 / R1-02)

Previous Reviewed-Failed Code Head:
1e2f4d753aad9050a79589776abda74f2e063e7b

Previous Docs Head:
30396dfefdd62aa4dbe3e9044c8ff056ac25c369

R1 Fix Base:
30396dfefdd62aa4dbe3e9044c8ff056ac25c369

R1 Code Review Candidate:
051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8

Current Docs Head:
reported externally after this docs commit
```

## 关闭声明

### R1-01（复查者 F1 — NormalizedMetadata 运行时合同 / 全谓词漏洞）

**修复的是根因，而不是绕过问题打补丁。** `NormalizedMetadata.__post_init__`
现在会在实例被视为构造完成之前，校验每个字段的运行时类型：

- `number`/`title`/`studio`/`publisher`/`release`/`plot`：必须是 `str` 或
  `None`。
- `runtime`：必须是 `int` 或 `None`，并且明确排除 `bool`（在 Python 中 `bool` 是 `int` 的子类，
  但在这里不是合法的 runtime 值），而且不能为负数。
- `actors`/`tags`/`poster_urls`/`thumb_urls`/`fanart_urls`/`extrafanart`/
  `source_urls`：必须是每个元素都为 `str` 的序列；裸的 `str`/`bytes` 值会被明确拒绝（而不是被悄悄地
  逐字符迭代），不可迭代的值也会被拒绝。
- `external_ids`：必须是 `str` key 到 `str` value 的 mapping。
- `field_sources`：必须是 `str` key 到 `str` 序列的 mapping。

任何违规都会**在构造时**抛出 `MetadataContractError`，实现位于
`fc2_metadata_core/models/metadata.py`。直接的结果是，
`has_valid_canonical_number()`、`has_non_empty_title()` 和
`meets_minimum_success()` 现在都是**全谓词**：对于任何已成功构造的实例，它们保证返回 `bool`，
永远不会抛出 `AttributeError`/`TypeError`/`KeyError`。

`SourceResult.__post_init__` 现在还会在接触 `metadata.meets_minimum_success()` 之前，校验 `metadata`
是 `None` 或真正的 `NormalizedMetadata` 实例。例如传入 `metadata=123` 或
`metadata={"number": ..., "title": ...}` 的调用方，会立即以 `SourceResultContractError` 被拒绝，
对每一种状态都是如此（而不仅仅是 `SUCCESS`）。

### R1-01 回归测试

`tests/unit/core/test_metadata.py`：
- `TestScalarTypeValidation`（包括 `test_original_f1_reproduction_title_int_is_rejected_at_construction`
  — 复查者的原始复现 — 以及一个覆盖全部六个标量 `str` 字段的参数化检查）。
- `TestCollectionTypeValidation`（对全部七个序列字段的非 `str` 元素做参数化检查，另加：裸 str 当作序列、
  不可迭代的值、`external_ids` 的 key / value 错误 / 非 mapping、`field_sources` 的 key / value 元素错误 /
  value 不是序列）。
- `test_meets_minimum_success_never_raises_for_any_constructed_instance`
  （在一批已构造的实例上检查全谓词性）。

`tests/unit/core/test_source_result.py`：
- `TestMetadataTypeGuard`（包括
  `test_original_f1_reproduction_int_metadata_is_rejected` — 复查者在 `SourceResult` 一侧的原始复现 —
  以及 dict 类型的 metadata、失败状态上类型错误的 metadata、metadata 为 None 仍然合法等用例）。

### R1-02（复查者 F2 — 可通过可变 metadata 破坏 SourceResult 的生命周期不变量）

**修复的是根因，而不是绕过问题打补丁；没有采用被否决的“把它作为注意事项写进文档”这种做法。**
`NormalizedMetadata` 现在是一个**深度不可变的值对象**，而不仅仅是一个包着可变容器的浅层
`frozen=True` dataclass：

- dataclass 为 `frozen=True` — 对标量（重新）赋值会抛出
  `dataclasses.FrozenInstanceError`（`AttributeError` 的子类）。
- 每个序列字段都在 `__post_init__` 中快照为 `tuple` — 存储的值上根本没有
  `.append`/`.remove`/条目赋值可用（尝试时抛出 `AttributeError`/`TypeError`，而不是一条写进文档的
  “请不要这样做”）。
- `external_ids` 和 `field_sources` 快照为包在新建私有 `dict` 副本外面的
  `types.MappingProxyType` — 条目赋值 / 删除会抛出 `TypeError`。
- `field_sources` 的 value 本身也快照为 `tuple`，关闭了复查者专门指出的嵌套修改路径
  （`field_sources["title"].append(...)`）。
- 调用方持有的输入容器（传给构造函数的 `list`、`dict`）在构造时被逐个元素复制，因此构造之后修改
  调用方的原始对象，无法影响已经构建好的 `NormalizedMetadata`（没有别名共享）。

由于 `SourceResult` 本来就是 frozen 的，其 `metadata` 字段不能被重新赋值，而 `NormalizedMetadata`
现在也无法通过任何公开 API 在任何深度上被修改，一个已构造的 `SourceResult` 的不变量（在
`__post_init__` 中一次性建立）现在在整个对象图的**整个生命周期**内都成立，关闭了复查者指出的
“构造时为真”与“永远为真”之间的缺口。

`FC2_METADATA_CORE_CONTRACT.md` §2.3 正式撤回了早先 Phase 1
HANDOFF 中让 `NormalizedMetadata` 保持可变的理由（“Phase 3 可能需要增量的原地合并”），
并冻结了方向：Phase 3 的聚合必须是函数式 / 写时复制（读取不可变的输入，产出新的实例），
绝不原地修改已发布的 `NormalizedMetadata`。

### R1-02 回归测试

`tests/unit/core/test_metadata.py`：
- `TestImmutability`（拒绝对标量重新赋值；序列字段以 `tuple` 存储且无法原地修改；
  `external_ids`/`field_sources` 以 `MappingProxyType` 存储且不可修改；嵌套的 `field_sources`
  tuple 值不可修改）。
- `TestCallerOwnedInputAliasSafety`（构造之后修改传入构造函数的原始 `list`/`dict`，包括
  `field_sources` 中的嵌套 list，都不会影响已构建的实例）。

`tests/unit/core/test_source_result.py`：
- `TestSuccessLifetimeInvariant` — 构建一个 `SUCCESS` 的 `SourceResult`，然后攻击标量、序列、mapping、
  嵌套 `field_sources` 的修改路径以及 `metadata` 字段的重新赋值；断言每次尝试之后
  `result.metadata.meets_minimum_success()` 仍然为 `True`，并且每次尝试本身都抛出了异常。
- `TestPartialFailureLifetimeInvariant` — 在
  `PARSE_ERROR`/`INVALID_RESPONSE` 上参数化；构建一个带部分 metadata 的结果，尝试把它修改成满足最低成功标准，
  确认该尝试失败且 `meets_minimum_success()` 仍为 `False`。
- `TestCallerOwnedAliasSafetyThroughSourceResult` — 在用原始的 `NormalizedMetadata` 引用或其原始输入 `list`
  构建 `SourceResult` 之后再修改它们，无法影响该结果。

## 变更文件

Diff 范围 `30396df` → `051d6c9`（5 个文件被修改，新增 / 删除 0 个）：

```text
fc2-organizer/docs/specifications/FC2_METADATA_CORE_CONTRACT.md   (modified: +§2.1/§2.2/§2.3, updated §3 table)
fc2-organizer/src/fc2_metadata_core/models/metadata.py            (modified: runtime validation + deep immutability)
fc2-organizer/src/fc2_metadata_core/models/source_result.py       (modified: metadata isinstance guard + docstring)
fc2-organizer/tests/unit/core/test_metadata.py                    (modified: +4 new test classes, updated collection-equality assertions to tuple)
fc2-organizer/tests/unit/core/test_source_result.py               (modified: +4 new test classes)
```

`normalize/fc2_number.py`、`errors/__init__.py`、
`tests/unit/core/test_normalize_fc2_number.py` 和
`tests/contract/test_core_independent_of_amane.py` **没有被触碰** — R1
只关闭 R1-01/R1-02，不处理 F3/F4/F5，也不重新打开 FC2 番号规范化。

## 新增 / 修改的测试

测试数量从 100（最初的 Phase 1 提交）增加到本轮 R1 的 146：
- `test_metadata.py`：保留 8 个原有测试（其中两个集合相等断言从 `list` 字面量改为 `tuple` 字面量，
  以匹配现在不可变的存储表示，例如
  `md.tags == ("a", "b")` 取代 `md.tags == ["a", "b"]`），新增 1 个
  `bool`-runtime 测试，另加 4 个新测试类（`TestScalarTypeValidation`、
  `TestCollectionTypeValidation`、`TestImmutability`、
  `TestCallerOwnedInputAliasSafety`），取代旧的
  `TestMutableDefaultIsolation`（它断言的是旧的可变 list 共享行为，一旦字段变成 tuple 就不再适用）。
- `test_source_result.py`：全部 32 个原有测试保持不变，另加 4 个
  新测试类（`TestMetadataTypeGuard`、`TestSuccessLifetimeInvariant`、
  `TestPartialFailureLifetimeInvariant`、
  `TestCallerOwnedAliasSafetyThroughSourceResult`）。
- `test_normalize_fc2_number.py`（43 个测试）和
  `test_core_independent_of_amane.py`（9 个测试）：没有改变，全部仍然通过。

## 确切命令

```bash
cd fc2-organizer
python3 --version
# Python 3.11.15

python3 -m pytest -v
# ... 146 passed in 0.14s

python3 -m pytest -q
# 146 passed in 0.12s

python3 -m pytest --collect-only -q
# 146 tests collected in 0.04s
```

## 通过 / 失败计数

```text
Python version: 3.11.15
Collected:      146
Passed:         146
Failed:         0
Skipped:        0
```

## 原始复现的验证

按照要求，两个复查者复现都被直接重新运行（而不只是通过 pytest）：

**原始 F1 复现：**

```python
NormalizedMetadata(number="FC2-4825061", title=123)
```

结果：在构造时立即抛出 `MetadataContractError: title must be a str or None, got
<class 'int'>`。**不会**构造成功；**不会**拖延到之后才出现 `AttributeError`。

**原始 F2 复现：**

```python
md = NormalizedMetadata(number="FC2-4825061", title="valid")
r = SourceResult(source_id="x", status=SourceStatus.SUCCESS, metadata=md, elapsed_ms=1)
```

通过直接执行脚本（而不只是 pytest）验证：每一条可用的公开修改路径都会失败，不变量得以保持：
- `md.title = ""` → `FrozenInstanceError: cannot assign to field 'title'`
- `r.metadata.title = ""` → 同上
- `r.metadata.actors.append("x")` → `AttributeError: 'tuple' object has no
  attribute 'append'`
- `r.metadata = NormalizedMetadata(title="other")` →
  `FrozenInstanceError: cannot assign to field 'metadata'`
- 四次尝试全部完成之后：`r.status == SourceStatus.SUCCESS` 且
  `r.metadata.meets_minimum_success() == True`，保持不变。

另外验证了 `SourceResult(source_id="x", status=SUCCESS,
metadata=123, elapsed_ms=1)` 会在构造时抛出 `SourceResultContractError`，而不是拖延到 `AttributeError`。

## 回归检查

- Phase 0 复查者说明 **F-02**（独立的 `NOT_FC2`/`UNRECOGNIZED` 语义，不依赖 Amane 的回退）：
  不受本轮 R1 影响 —
  `normalize/fc2_number.py` 没有被触碰。全部 43 个
  `test_normalize_fc2_number.py` 测试仍然通过，包括
  `test_negative_misidentification_regression` 和
  `TestIsValidFc2Number` 类。
- Phase 0 复查者说明 **F-03**（`[广告]FC2PPV-1234567` /
  `xxx@FC2PPV-1234567` 的自动化回归）：不受影响。已单独验证：
  `python3 -m pytest tests/unit/core/test_normalize_fc2_number.py -v -k "f03"`
  → `test_f03_regression_ad_prefix_noise_closed` 和
  `test_f03_regression_xxx_at_prefix_noise_closed` 都是 `PASSED`。
- `tests/contract/test_core_independent_of_amane.py`（9 个测试，未改变）：
  全部仍然通过 — `fc2_metadata_core` 仍然没有在任何地方静态或动态地 import `amane`，并且公开 API
  （包括现在不可变的 `NormalizedMetadata`）在运行时阻断 `amane` import 的情况下仍然完全可用。
- 7-state 的 `SourceStatus` 词汇没有改变（`SUCCESS`、`NOT_FOUND`、
  `BLOCKED`、`RATE_LIMITED`、`NETWORK_ERROR`、`PARSE_ERROR`、
  `INVALID_RESPONSE`）。
- 最低成功标准的定义没有改变（`canonical FC2 number + non-empty
  title`）；改变的只是它的*执行全面性*，以及*被检查对象的不可变性*。

## 已知局限

1. 修改尝试所抛出的异常，是底层不可变 Python 类型自然抛出的那些异常（属性重新赋值抛出
   `dataclasses.FrozenInstanceError`，调用 `tuple` 上不存在的修改方法抛出 `AttributeError`，对
   `MappingProxyType` 做条目赋值抛出 `TypeError`），而不是一个统一的自定义异常类型。对于“在一个已经合法的
   不可变对象上尝试非法修改”这种情况，这是有意为之且符合惯例的做法（这与 R1-01 关注的*构造时*领域校验不同），
   但复查者可能希望改用一个统一的 `NormalizedMetadataImmutableError` 包装；这里没有这样做，是为了让 R1 的 diff
   保持最小，而且底层异常本来就会被可靠地抛出（从不会被悄悄吞掉），并且已写在合同文档和 docstring 中。
2. `field_sources` 的 value 转换接受任何由 `str` 组成的非 `str`/`bytes` 可迭代对象（例如生成器），并将其
   快照为 `tuple`；在 R1 之前，普通序列字段本来就是如此，这一点没有改变。
3. F3/F4/F5（Phase 0/R1 独立复查中的非阻塞 finding）在本轮刻意没有触碰；见下文
   “Deferred non-blocking”。

## 刻意延后的非阻塞 finding

```text
F3
F4
F5
```

不属于 R1 的必须关闭集合（只有 `R1-01`、`R1-02`）。按照指示，必须最迟在 Phase 5 集成之前关闭。

## 安全考量

没有引入新的网络访问、文件 I/O 或凭据处理。所有改动都是纯内存中的 dataclass / 校验逻辑。
没有触碰任何 secret、token 或 cookie。

## Windows 运行

Windows NOT run（与最初的 Phase 1 提交相同；本轮 R1 的改动是纯标准库 Python，没有任何平台相关行为）。

## Amane 集成运行

没有运行 / 不适用于 Phase 1 R1（与最初的 Phase 1 相同：
`fc2_metadata_core` 仍然与 `amane` 完全解耦，已由未改变且仍然通过的
`tests/contract/test_core_independent_of_amane.py` 再次验证）。

## Phase 2 尚未开始
