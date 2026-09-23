# PHASE1_R2_HANDOFF.md

```text
Phase: Phase 1 R2 — Incremental Closure Fix (R2-01 / R2-02)

Previous Reviewed-Failed R1 Code Head:
051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8

Previous R1 Docs Head:
83158027bc5dbc11e35cbecfaf2ba98ee809dffd

R2 Fix Base:
83158027bc5dbc11e35cbecfaf2ba98ee809dffd

R2 Code Review Candidate:
090e9b7f19a6268c5cb8a95f9a2b2cdbb2b853c9

Current Docs Head:
reported externally after this docs commit
```

## 关闭声明

### R2-01（R1 增量复查 finding F1 — PARTIAL：在本应是 `Sequence[str]` 合同的地方接受了 `Iterable`）

**修复的是根因，而不是绕过问题打补丁。** `fc2_metadata_core/models/metadata.py` 中的 `_coerce_str_tuple`
以前在排除 `str`/`bytes` 之后接受任何 `collections.abc.Iterable`。这让 `dict` 得以通过（Python 迭代 `dict`
时遍历的是它的 key，因此 `actors={"Alice": 1, "Bob": 2}` 会悄悄变成 `("Alice", "Bob")` 而不报任何错误，
value 被完全丢弃），也让 `set`/`frozenset` 得以通过（可迭代但无序，因此生成的 tuple 的元素顺序取决于
hash seed / 插入历史，而不是调用方的意图）。

七个序列字段（`actors`/`tags`/`poster_urls`/`thumb_urls`/`fanart_urls`/`extrafanart`/
`source_urls`）以及每个 `field_sources` value 的输入合同，现在被明确冻结为
`collections.abc.Sequence[str]`：

- `list[str]` / `tuple[str, ...]` / 任何真正的 `Sequence`：**接受**，快照为 `tuple[str, ...]`，严格保持顺序。
- `str` / `bytes`：**拒绝**（与 R1 相同）。
- `Mapping`（`dict` 之类）：用单独的检查**明确拒绝**，尽管 `dict` 本身就无法通过 `Sequence` 检查 —
  保留这条检查，是为了给出明确、措辞清晰的拒绝原因，也是为了对一个假想中同时注册为两者的类型做纵深防御。
- `set` / `frozenset`：**拒绝**。刻意*不*排序后接受 — 本项目的决定是：Core 不得替调用方发明一个顺序，
  因为字段顺序可能携带来源 / 展示上的含义。
- 生成器 / 迭代器 / 任何其他只是 `Iterable`、而非 `Sequence` 的对象：**在消费它之前就拒绝** — 这项检查
  从不触碰一次性可迭代对象，因此不存在部分消费的风险，也不会因一个本来就不是合法输入的东西而在中途抛出异常。

`field_sources` 的 value 走的是完全相同的 `_coerce_str_tuple` helper（没有单独 / 分叉的逻辑），因此同样的规则
被统一应用 — 这是同一个共同的根因，在一处修复。

### R2-01 回归测试

`tests/unit/core/test_metadata.py::TestSequenceContractRejectsNonSequenceIterables`：
- `test_original_r1_reviewer_reproduction_dict_as_actors_is_rejected` —
  `actors={"Alice": 1, "Bob": 2}` 的原始复现。
- `test_original_r1_reviewer_reproduction_set_as_actors_is_rejected` /
  `..._frozenset_as_actors_is_rejected` — set/frozenset 的原始复现。
- `test_original_r1_reviewer_reproduction_generator_as_actors_is_rejected`
  — 使用一个会记录其函数体是否运行过的生成器；断言函数体从未执行（在消费之前就被拒绝）。
- `test_list_and_tuple_are_still_accepted_with_stable_order` — 正向对照，严格保持顺序。
- `test_dict_set_frozenset_generator_rejected_for_every_sequence_field` —
  对全部七个序列字段参数化。
- `test_field_sources_value_rejects_mapping_as_sequence` /
  `..._rejects_set` / `..._rejects_frozenset` / `..._rejects_generator` —
  同样四种非法形态作为 `field_sources` 的 value。
- `test_field_sources_value_accepts_list_with_stable_order` — `field_sources` 的正向对照。

### R2-02（行为异常的*已接受* Sequence 不得泄漏其异常）

**修复的是根因，而不是绕过问题打补丁。** 把输入类型限制为 `Sequence`，并不能保证实现本身行为正常 —
自定义的 `Sequence` 子类仍然可能在迭代中途抛出异常（例如 `__getitem__` 有缺陷）。`_coerce_str_tuple`
现在把读取元素的循环包在 `try/except` 中：我们自己的元素类型 `MetadataContractError` 被原样重新抛出
（`except MetadataContractError: raise`，排在前面检查，因此永远不会被其下方更宽泛的处理器捕获），
而在读取已接受的 `Sequence` 时抛出的任何其他异常都会被捕获，并通过
`raise MetadataContractError(...) from exc` 以 `MetadataContractError` 重新抛出，同时链接原始异常。

### R2-02 回归测试

`tests/unit/core/test_metadata.py::TestBrokenAcceptedSequenceIsWrapped`，
使用一个 `_BrokenSequence(collections.abc.Sequence)` 测试替身，其
`__getitem__(0)` 返回 `"Alice"`，`__getitem__(1)` 抛出
`RuntimeError("boom")`：
- `test_broken_sequence_raises_metadata_contract_error_with_chained_cause`
  — 断言抛出的是 `MetadataContractError`，且其 `__cause__` 是带有原始消息的原始 `RuntimeError`。
- `test_broken_sequence_is_not_a_bare_runtime_error` — 断言原始的 `RuntimeError` 从不原样传播出来。
- `test_broken_sequence_in_field_sources_value_is_also_wrapped` — 同一个替身用作 `field_sources` 的 value。
- `test_own_element_type_error_is_not_double_wrapped` — 断言我们自己的 `MetadataContractError`
  （来自 `actors=[123]`）的 `__cause__ is
  None`，即它被原样重新抛出，而不是被处理缺陷 Sequence 的处理器再包装一次。

## R1-02 保持不变的证据

R1-02（深度不可变、`SourceResult` 生命周期不变量、调用方持有对象的别名隔离）在本轮**没有被修改**：
`fc2_metadata_core/models/source_result.py` 没有被触碰（见下文的变更文件 — 它根本没有出现在本次提交的 diff 中）。
全部原有的 R1-02 回归测试都被重新运行，并且原样继续通过：

```text
tests/unit/core/test_metadata.py::TestImmutability             (7 tests, all PASSED)
tests/unit/core/test_metadata.py::TestCallerOwnedInputAliasSafety (4 tests, all PASSED)
tests/unit/core/test_source_result.py::TestSuccessLifetimeInvariant (5 tests, all PASSED)
tests/unit/core/test_source_result.py::TestPartialFailureLifetimeInvariant (2 tests, all PASSED)
tests/unit/core/test_source_result.py::TestCallerOwnedAliasSafetyThroughSourceResult (2 tests, all PASSED)
```

`NormalizedMetadata` 在任何时候都没有被恢复为可变；修复只涉及在既有的 tuple/`MappingProxyType` 快照运行之前，
什么样的输入会被*接受*为合法。

## 变更文件

Diff 范围 `83158027` → `090e9b7`（3 个文件被修改，新增 / 删除 0 个）：

```text
fc2-organizer/docs/specifications/FC2_METADATA_CORE_CONTRACT.md   (modified: +§2.1a, updated §2.1 table, revision note)
fc2-organizer/src/fc2_metadata_core/models/metadata.py            (modified: _coerce_str_tuple tightened to Sequence + exception wrapping, module docstring)
fc2-organizer/tests/unit/core/test_metadata.py                    (modified: +2 new test classes, +Sequence import)
```

`models/source_result.py`、`normalize/fc2_number.py`、`errors/__init__.py`、
`tests/unit/core/test_source_result.py`、
`tests/unit/core/test_normalize_fc2_number.py` 和
`tests/contract/test_core_independent_of_amane.py` **没有被触碰** — R2
只关闭 R2-01/R2-02。

## 确切命令

```bash
cd fc2-organizer
python3 --version
# Python 3.11.15

python3 -m pytest --collect-only -q
# 167 tests collected in 0.03s

python3 -m pytest -v
# ... 167 passed in 0.14s

python3 -m pytest -q
# 167 passed in 0.15s
```

单独运行 R2 专属的新测试：

```bash
python3 -m pytest tests/unit/core/test_metadata.py -v \
  -k "TestSequenceContractRejectsNonSequenceIterables or TestBrokenAcceptedSequenceIsWrapped"
# 21 passed in 0.04s
```

完整的 F-02/F-03/R1-02/合同回归复查：

```bash
python3 -m pytest tests/unit/core/test_normalize_fc2_number.py -q
# 41 passed in 0.04s

python3 -m pytest \
  tests/unit/core/test_metadata.py::TestImmutability \
  tests/unit/core/test_metadata.py::TestCallerOwnedInputAliasSafety \
  tests/unit/core/test_source_result.py::TestSuccessLifetimeInvariant \
  tests/unit/core/test_source_result.py::TestPartialFailureLifetimeInvariant \
  tests/unit/core/test_source_result.py::TestCallerOwnedAliasSafetyThroughSourceResult \
  -v
# 20 passed in 0.03s

python3 -m pytest tests/contract/ -q
# 11 passed in 0.03s
```

## 计数

```text
Python version: 3.11.15
Collected:      167
Passed:         167
Failed:         0
Skipped:        0
```

（测试数量从 R1 之后的 146 增加到 R2 的 167：+21 个新测试，删除 0 个，
`test_source_result.py` 中修改的原有测试为 0 个；
`test_metadata.py` 新增了一个 import 和两个新测试类。）

## 复查者的原始复现

按照要求，全部四个复现以及有缺陷 Sequence 的用例，都通过一个独立脚本直接重新运行（而不只是 pytest）：

```text
NormalizedMetadata(actors={"Alice": 1, "Bob": 2})
  -> MetadataContractError: actors must be an ordered Sequence[str], not a mapping

NormalizedMetadata(actors={"Alice", "Bob"})
  -> MetadataContractError: actors must be an ordered Sequence[str] (e.g. list or
     tuple), got <class 'set'>

NormalizedMetadata(actors=frozenset({"Alice", "Bob"}))
  -> MetadataContractError: actors must be an ordered Sequence[str] (e.g. list or
     tuple), got <class 'frozenset'>

NormalizedMetadata(actors=<generator>)  # body records "STARTED" on first next()
  -> MetadataContractError: actors must be an ordered Sequence[str] (e.g. list or
     tuple), got <class 'generator'>
  -> generator body executed: [] (confirmed never run)

NormalizedMetadata(actors=<Sequence test double raising RuntimeError("boom-in-sequence")
                            at index 1>)
  -> MetadataContractError: actors raised an unexpected error while being read:
     boom-in-sequence
  -> __cause__ = RuntimeError('boom-in-sequence')   (chained, not leaked raw)

Positive control:
NormalizedMetadata(actors=["Alice", "Bob"]).actors  == ("Alice", "Bob")
NormalizedMetadata(actors=("Alice", "Bob")).actors  == ("Alice", "Bob")
```

## 回归检查

- Phase 0 **F-02** / **F-03**：不受影响 — `normalize/fc2_number.py` 没有被触碰；全部 41 个
  `test_normalize_fc2_number.py` 测试通过，包括两个专门的 F-03 回归测试。
- **R1-02**：不受影响 — `source_result.py` 没有被触碰；全部 20 个相关的 R1-02 生命周期 / 不可变性 / 别名测试
  重新运行并通过（见上文）。
- `tests/contract/test_core_independent_of_amane.py`：不受影响，全部 11 个测试通过 —
  `fc2_metadata_core` 在运行时阻断 `amane` import 的情况下仍然能完整地 import 和运行。
- 7-state 的 `SourceStatus` 词汇、最低成功标准的定义，以及所有其他 Phase 1/R1 合同接口：没有改变。
- 没有发现新的阻塞性回归。

## 已知局限

1. 对 `set`/`frozenset`/生成器/其他非 `Sequence` 值的拒绝错误消息，是一条共享的消息
   （“must be an ordered Sequence[str] ...”），而不是按被拒绝的类型区分的不同消息；`Mapping` 的情况则有自己
   单独的消息。这是诊断信息质量上的一个小取舍，而不是合同缺口 — 对领域边界而言，重要的是异常类型以及确实被拒绝
   这一事实。
2. `_BrokenSequence` 的异常行为刻意设计得很简单（在读取第二个元素时抛出异常）；对于在 `__len__` 与
   `__getitem__` 之间以更奇特方式表现不一致的 `Sequence`，没有单独测试，因为包装行为（读取循环中除我们自己的
   `MetadataContractError` 之外的任何异常都会被包装）并不取决于具体是哪一种不一致触发了它。
3. F3/F4/F5 仍然刻意延后（见下文），与 R1 相同。

## 延后的非阻塞项

```text
F3
F4
F5
```

不属于 R2 的必须关闭集合（只有 `R2-01`、`R2-02`）。按照指示，仍然必须最迟在 Phase 5 集成之前关闭。
本轮**没有**触碰 `tests/contract/test_core_independent_of_amane.py` 的 `CORE_MODULES` 发现机制，
以及“已安装 Amane 的环境”断言。

## Phase 2 尚未开始（NOT started）
