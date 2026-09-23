# Phase 4 / P4-C6 Handoff -- 原子 Artifact 落盘（Atomic Artifact Materialization）

```text
Phase        = 4
Package      = P4-C6 Atomic Artifact Materialization
Role         = Developer
Branch       = claude/phase4-c6-atomic-materialization
```

## 1. 坐标

```text
Frozen Base                  = e44790f57004825957f2212921171667e7c576cf
Substep 1 Head               = b088db8acb2c4ae47037d58546000c41543b73b1   atomic no-overwrite primitive
Substep 2 Head               = 67fb857523c59b3cd19691caedf3316171f8e0ca   artifact mapping + single-artifact materializer
Substep 2A Head              = 2016107bd33fc4de546698790acb84f3d28cc8a9   extrafanart naming boundary correction (999 cap removed)
P4-C6 Code Review Candidate  = 8f845b429b6b35f86038b393a2c98864f35a68b0   integrated synthetic gate + contract finalization (no production change)
P4-C6 Docs Head              = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C6_HANDOFF.md`>
Remote Head                  = <== Docs Head after push of this commit>

Code Review Range: e44790f57004825957f2212921171667e7c576cf..8f845b429b6b35f86038b393a2c98864f35a68b0
Docs Review Range: 8f845b429b6b35f86038b393a2c98864f35a68b0..<Docs Head>
```

历史是线性的：`e44790f -> b088db8 -> 67fb857 -> 2016107 -> 8f845b4 -> Docs Head`。每个
substep 都从一个经过验证的 `HEAD == origin/claude/phase4-c6-atomic-materialization == <parent>` 开始，
工作区干净（只有未跟踪的测试框架目录 `.claude/`）。没有 rebase、amend、squash 或 force push。Docs Head 提交只包含本文件。

## 2. 类型

**NEW PACKAGE**（`fc2_organizer.materialization`）+ 四处一行的 package 集合作用域守卫更新
（`test_{discovery,planning,publication,nfo}_architecture.py`：`+ "materialization"`）。`fc2_organizer/materialization/`
之外没有任何生产文件被触碰；`fc2_organizer/__init__.py` 没有改变。Substep 3 没有改动任何生产源码（只有门槛测试 + 合同）。

## 3. 变更文件（Code Review Range，22 个文件，+3871 / -4）

新增（18）：
```text
fc2-organizer/docs/specifications/PHASE4_ATOMIC_MATERIALIZATION_CONTRACT.md
fc2-organizer/src/fc2_organizer/materialization/__init__.py
fc2-organizer/src/fc2_organizer/materialization/errors.py
fc2-organizer/src/fc2_organizer/materialization/models.py
fc2-organizer/src/fc2_organizer/materialization/atomic.py
fc2-organizer/src/fc2_organizer/materialization/artifacts.py
fc2-organizer/src/fc2_organizer/materialization/mapping.py
fc2-organizer/tests/contract/test_materialization_architecture.py
fc2-organizer/tests/unit/materialization/__init__.py
fc2-organizer/tests/unit/materialization/_helpers.py
fc2-organizer/tests/unit/materialization/_builders.py
fc2-organizer/tests/unit/materialization/test_materialization_atomic.py
fc2-organizer/tests/unit/materialization/test_materialization_failures.py
fc2-organizer/tests/unit/materialization/test_materialization_race.py
fc2-organizer/tests/unit/materialization/test_materialization_paths_and_models.py
fc2-organizer/tests/unit/materialization/test_materialization_mapping.py
fc2-organizer/tests/unit/materialization/test_materialization_artifacts.py
fc2-organizer/tests/unit/materialization/test_materialization_synthetic_gate.py
```

修改（4，各一行 -- 只是 package 集合）：
```text
fc2-organizer/tests/contract/test_discovery_architecture.py
fc2-organizer/tests/contract/test_planning_architecture.py
fc2-organizer/tests/contract/test_publication_architecture.py
fc2-organizer/tests/contract/test_nfo_architecture.py
```

## 4. 原子原语（合同 3-5）

`materialize_atomic_bytes(target_path: str, content: bytes) -> MaterializedArtifact` -- 同步调用，两个位置参数，
没有 overwrite / exist_ok / 后缀 / mkdir / 文件系统操作旋钮。在任何 I/O 之前检查：严格的 `str` 目标（不接受 `PathLike`、
`bytes`、子类；不运行任何钩子）以及严格的 `bytes` 内容（不接受 `bytearray`、`memoryview`、子类）。只接受明确的完全限定路径：
不做 `expanduser` / `expandvars` / cwd；不允许 `.` / `..`；Windows 盘符或 UNC 根目录，不允许设备命名空间，不允许
`<>:"|?*`（NTFS 数据流），不允许结尾的点 / 空格，不允许保留设备名。父目录必须是已存在的目录（永远不会被创建）；对目标做
`lstat`，从不跟随链接。
`MaterializedArtifact(target_path, size_bytes, sha256)` -- frozen、slots，描述的是写入的字节。

## 5. Overwrite NEVER（合同 6）

目标位置上的任何东西 -- 文件、目录、symlink、悬空 symlink、junction -> `TargetExistsError`，保持不动。不截断 / 替换 / 删除 /
加后缀。从不调用 `os.replace`（AST 强制）。

## 6. 平台发布策略（合同 7）

| 操作系统 | 原语 | 目标已存在时 |
|---|---|---|
| Windows | `os.rename` = 不带 `MOVEFILE_REPLACE_EXISTING` 的 `MoveFileExW` | 对任何条目都以 `FileExistsError` 失败 |
| POSIX | `os.link(temp, target)`，然后 unlink 临时文件 | `EEXIST`；从不跟随目标 |

`lstat` 预检只是提前退出；不覆盖的保证来自发布原语本身，因此在检查与发布之间创建的目标永远不会被替换（用植入的文件、目录和
symlink 测试过）。在不支持 hard link 的文件系统上不会回退到 rename/replace（`ArtifactPublishError`）。文件数据已 `fsync`；
父目录条目没有。

## 7. 临时文件所有权（合同 8）

`.fc2tmp-<32 hex secrets.token_hex(16)>.part`，与目标同级，`O_CREAT|O_EXCL`（从不使用 `O_TRUNC`），从不从目标 / 标题 /
metadata / URL 推导。名称冲突 -> 换新的 token（最多 8 次），发生冲突的条目不被触碰；尝试用尽 -> `TemporaryCreateError`。

## 8. 清理语义（合同 9-10）

发生任何失败时：关闭 fd，只对**本次调用所拥有的确切临时路径** unlink 一次。不做基于 glob / 通配符 / 目录列表的清理；最终目标
永远不会被删除。类型化错误之后的清理失败 ->
`ArtifactCleanupError(target_published=False, primary=...)`；POSIX 发布后临时文件 unlink 失败
-> `ArtifactCleanupError(target_published=True)`，完整的目标被保留。`KeyboardInterrupt`、
`SystemExit`、`GeneratorExit`、任何其他 `BaseException` 以及外来异常都以同一个对象传播；清理失败永远不会掩盖它们。
错误只携带固定措辞 + errno（没有路径、临时 token 或 `OSError` 文本），并且永远不会链接到 `OSError`。

## 9. 并发竞争保证（合同 13）

N 个 writer、一个目标：恰好一个 `MaterializedArtifact`，其余全部为 `TargetExistsError`；胜出者的字节完整且永远不会被覆盖；
每个落败者只删除自己的临时文件。已测试 barrier 强制（两者都已通过预检）以及不同步（8 个 writer x 多轮）两种方式，
覆盖两种发布策略，既直接测试，也经由 `materialize_artifact` 测试。

## 10. Artifact 请求模型（合同 16）

`ArtifactKind` = NFO、POSTER、FANART、THUMB、EXTRAFANART。`ArtifactWriteRequest(kind, target_path,
content, ordinal=None)`：frozen、slots、严格类型，`content` 为严格 `bytes`（不出现在 `repr` 中），`ordinal` 为严格
`int >= 1`，当且仅当 kind 为 EXTRAFANART。不持有 `PublicationRecord`、`AcquiredImage`、计划、URL、HTTP 数据或异常。

## 11. 映射顺序（合同 17-18）

`fc2_organizer.materialization.mapping.build_artifact_requests(plan, nfo_text, images)` -- 纯函数，零文件系统访问，确定性的；
在任何属性访问之前检查严格类型的输入；从不读取 `OrganizePlan.operations`，从不重新解析规范番号。顺序：NFO、POSTER?、FANART?、
THUMB?、按 `images.extrafanart` tuple 顺序的 EXTRAFANART。伪造的计划路径 / 冲突的目标 / 角色错误的图片都会 fail closed
（`ArtifactMappingError`）。

## 12. NFO 编码（合同 19）

严格为 `nfo_text.encode("utf-8", errors="strict")`，写入 `plan.nfo_path`：不加 BOM，不改变换行，不 strip，不规范化，
不改写 XML。空 -> `NFO_EMPTY`；无法编码 ->
`NFO_NOT_UTF8_ENCODABLE`（不做异常链接）。

## 13. 图片字节身份一致性（合同 20）

poster -> `poster_path`，fanart -> `fanart_path`，thumb -> `thumb_path`；缺失的图片 = 不产生请求，也不算失败；
没有跨角色回退。`request.content is AcquiredImage.content`（不重新编码 / 缩放 / 转码 / 复制）。重复的字节不去重。

## 14. Extrafanart 命名（合同 21）

`<plan.extrafanart_directory>/extrafanart-{ordinal:03d}.jpg`，ordinal = 从 1 开始的 tuple 位置，可以是任何严格的正 `int`；
`03d` 只是最小宽度（`1000 -> extrafanart-1000.jpg`）。没有最大值：substep 2 自行发明的 999 上限已在 substep 2A 中移除，
因为 P4-C5 的 `max_extrafanart` 没有上限。0 / 负数 / bool / float / str / int 子类 -> `INVALID_EXTRAFANART_ORDINAL`。
永远不从 URL、标题、hash、`candidate_index` 或随机数推导。

## 15. 单个 Artifact 的落盘器（合同 22）

`materialize_artifact(request)`：严格的 `ArtifactWriteRequest`（子类会在不运行钩子的情况下被拒绝），然后只调用
`materialize_atomic_bytes(request.target_path, request.content)`。一次调用 = 一个 artifact；没有
`materialize_all` / `execute_plan` / `apply_operations` / `transaction` / `rollback_all`；之前的成功永远不会因为之后的失败
而被回滚。

## 16. 不创建目录 / 没有 MOVE_MEDIA（合同 23、27）

任何地方都没有 `mkdir` / `makedirs`（AST 强制）；目标目录或 `extrafanart/` 缺失 ->
`ParentDirectoryMissingError`，不会被创建。不读取也不执行任何 `PlannedOperation`；没有 `MOVE_MEDIA`。完全不属于 P4-C6 的：
对目标 / extrafanart 目录执行 mkdir、MOVE_MEDIA、源媒体校验、跨卷移动、整个计划的预检、操作图执行、回滚事务、CLI/UI、持久化、
Amane 集成（P4-C7 及之后）。

## 17. 架构（合同 14、23）

* `__init__`、`errors`、`models`、`atomic`、`artifacts`：只使用标准库 + 本 package 自身。
* `mapping.py`：另外还可以使用 `fc2_organizer.planning` 和 `fc2_organizer.images` 这两个**公开** package（只用模型）以及
  `os.path.join`。从不直接依赖 `httpx`、Amane、`fc2_metadata_core`，也不依赖 `images.transport`、`images.acquisition`、
  `nfo`、`publication`、`discovery`。
* `planning` 会传递加载 `fc2_metadata_core`，因此 `mapping` **不会**被 package 的 `__init__` import；
  `import fc2_organizer.materialization` 不加载任何 planning / images / core 模块。
* 没有 `executor.py` / `move.py` / `orchestrator.py` / `planner.py`；没有反向依赖；`os.rename` / `os.link` 只出现在不替换的
  发布中，`unlink` 只能通过所拥有临时文件的 helper 到达。
* 运行时阻断器证明：原语在 core / 网络 / Amane 被阻断的情况下可以工作，`mapping` 在 Amane / httpx / transport / acquisition /
  nfo / publication 被阻断的情况下可以工作。

## 18. 集成门槛（合同 26）

`tests/unit/materialization/test_materialization_synthetic_gate.py` -- 35 个测试，只是测试层的编排：

* **300 部确定性的影片**：100 部仅 NFO，100 部 NFO + 全部 7 种非空主图组合，
  100 部 NFO + 全部 8 种主图组合 + 1..13 张 extrafanart；CJK / 假名 / emoji / XML 特殊字符 / 分解形式 / 制表符标题，CRLF 的 NFO，
  跨角色以及 extrafanart 内部的重复字节。每部影片：请求顺序 / kind / 路径 / ordinal / 字节与根据用例推导出的预期对照、身份一致性、
  重放，然后对每个请求检查文件字节 / 大小 / sha256 / 无 BOM、精确的目录列表、没有临时文件残留。
* extrafanart 1 / 12 / 999 / 1000 的名称；在内存中完成 1000-item 映射（不写入任何内容）。
* 五种 kind 各自的 overwrite NEVER（字节、inode、mtime、目录列表都不变）。
* 部分成功（poster 得到 `TargetExistsError` 之后 NFO 被保留）。
* 失败注入 写入 / flush / close / 发布 x {native, hardlink} + 清理失败；植入的无关临时文件完好无损。
* 竞争：barrier 强制和不同步 x {native, hardlink}。
* 架构回归扫描。
* 非空洞性检查（未提交）：在 `mapping._encode_nfo` 中前置 BOM -> 5 个门槛失败；`03d` -> `02d` -> 4 个门槛失败；两者都已撤销。

## 19. 直接复现（在门槛文件中）

| id | 场景 | 观察结果 |
|---|---|---|
| A | 新的 NFO | 文件字节 == `nfo_text.encode("utf-8")` |
| B | 目标已存在 | `TargetExistsError`，原始字节不变 |
| C | 两个 writer，同一目标 | 恰好一个成功，磁盘上是胜出者的字节，落败者得到 `TargetExistsError` |
| D | 写入失败 | `ArtifactWriteError`，没有最终文件，所拥有的那一个临时文件被删除 |
| E | 植入的无关临时文件 + 发布失败 | 所有植入的文件都保留，没有其他文件 |
| F | NFO 成功，之后 poster 失败 | NFO 保持完整 |
| G | 1000 个 extrafanart 的映射 | 1001 个请求，最后一个为 `extrafanart-1000.jpg` |
| H | `extrafanart/` 缺失 | `ParentDirectoryMissingError`，目录没有被创建（mkdir 被拦截） |

## 20. 针对性测试（在 Code Review Candidate 上）

```text
tests/unit/materialization/                                   303 passed, 5 skipped, 0 failed
  of which test_materialization_synthetic_gate.py              35 passed
  of which race + failures                                     85 passed, 2 skipped
tests/contract/test_{materialization,discovery,planning,
  publication,nfo,images}_architecture.py                     97 passed, 0 skipped, 0 failed
```

## 21. 全量测试

`python -m pytest -q -p no:cacheprovider --basetemp=<job tmp>`（在本主机上两个选项都需要：共享的 pytest 临时根目录权限被拒绝）：

```text
4172 passed, 19 skipped, 0 failed
```

进展：P4-C5 关闭时 3852 / 14 -> substep 1 4052 / 19 -> substep 2 4122 / 19 -> 2A 4137 / 19 ->
substep 3 4172 / 19。substep-3 的第一次全量运行出现了 7 个失败，全部位于新的门槛文件中：这是一个测试隔离缺陷（在函数内部局部
import 的 `ArtifactWriteRequest`，在架构测试清理 / 重新 import 整个 package 之后拿到了更新一代的类）。通过在模块顶层 import
在测试中修复；没有生产代码改动。跳过的测试不算作通过。

## 22. 跳过 / 环境证据缺口（不是 PASS 声明）

```text
Windows host real symlink cases        : NOT EXECUTED (no symlink privilege) -- 5 skips
                                         (existing / dangling / planted-before-publish symlink)
Junction cases                         : EXECUTED
lstat host-independent simulation      : EXECUTED
POSIX native host                      : NOT EXECUTED
P4-C6 real POSIX-host publish          : NOT YET OBSERVED
Hard-link (POSIX) strategy             : exercised only through the private strategy seam on NTFS
Other 14 skips                         : pre-existing, outside P4-C6
```

这些是复查证据说明，而不是 finding；没有为此改动任何生产设计。

## 23. 阻塞性的已知问题

开发者所知的没有。这里没有创建任何 finding ID。

## 24. 状态

```text
P4-C6 implementation : COMPLETE
Independent Review   : REQUIRED
P4-C6                : NOT CLOSED
Phase 4              : NOT CLOSED
```

## 25. Final Closure（最终关闭）

本节起正文使用简体中文；代码名、SHA、API、命令与枚举保留英文原文。

### 25.1 关闭坐标

```text
Phase                     = 4
Package                   = P4-C6 Atomic Artifact Materialization
Status                    = CLOSED
Final Reviewed Code Head  = 8f845b429b6b35f86038b393a2c98864f35a68b0
Previous Docs Head        = a059c08a976c6585534aca195546d6081c9f9fd9
P4-C6 Closure Docs Head   = 本提交（见 `git log -1 -- fc2-organizer/docs/review/P4_C6_HANDOFF.md`）
```

### 25.2 独立复查 A

结论：**PASS**。

Reviewer A 在候选代码上独立执行并得到：

```text
materialization          : 303 passed / 5 skipped
architecture             : 97 passed / 0 skipped
full suite               : 4172 passed / 19 skipped / 0 failed
Direct reproductions     : PASS
Windows barrier race     : PASS
multi-process race       : 20 rounds × 6 processes PASS
mutation                 : 12 / 12 mutants killed
Findings                 : NONE
Blocking Findings        : NONE
```

Reviewer A 记录的证据缺口：Windows 真实 symlink 用例因权限不足未执行；POSIX 原生主机未执行（该缺口已由 Reviewer B 补足，见 25.3）。

### 25.3 独立复查 B

结论：**BLOCKED — 仅限证据环境**。

需要明确说明，这**不是实现层面的 FAIL**：

```text
Implementation correctness findings : NONE
P4-C6-R-*                           : NONE
```

BLOCKED 的原因只有复查环境的限制：没有可执行的候选 checkout，因此无法独立运行 targeted pytest、full pytest 和本地 `git diff --check`。这些缺失的证据已由 Reviewer A 的独立执行补足。

同时，Reviewer B 提供了开发阶段缺少的重要独立证据，即 Linux/POSIX 原生主机执行：

```text
Linux/POSIX native                  : EXECUTED
POSIX os.link no-replace            : PASS
existing regular target             : EEXIST / PASS
existing symlink                    : EEXIST / preserved / PASS
dangling symlink                    : EEXIST / preserved / PASS
native POSIX barrier race           : exactly one winner / PASS
```

因此两份复查报告是互补证据，彼此不构成否决。

### 25.4 合并关闭判断

两份复查的证据合并后满足关闭条件（Combined Evidence: **SATISFIED**）。各项裁决如下：

```text
Atomic primitive                   : ACCEPTED
Overwrite NEVER                    : ACCEPTED
Windows no-replace strategy        : ACCEPTED
POSIX link+unlink strategy         : ACCEPTED
Temp ownership                     : ACCEPTED
Failure cleanup                    : ACCEPTED
Cancellation / fatal propagation   : ACCEPTED
Concurrent race                    : ACCEPTED
Path boundary                      : ACCEPTED
Artifact mapping                   : ACCEPTED
NFO encoding                       : ACCEPTED
Image byte identity                : ACCEPTED
Extrafanart naming                 : ACCEPTED
Single-artifact materializer       : ACCEPTED
Partial-success semantics          : ACCEPTED
Architecture                       : ACCEPTED
Integrated synthetic gate          : ACCEPTED

New Findings                       : NONE
Blocking Findings                  : NONE
```

### 25.5 保留的证据说明（非阻塞）

1. **Windows 真实 symlink**：开发者与复查者的主机均缺少 symlink 权限，未执行。junction 用例与不依赖主机的 `lstat` 模拟已执行。
2. **POSIX 原生主机**：Reviewer B 已独立执行，结果 PASS（见 25.3）。第 22 节中“NOT YET OBSERVED”的开发阶段记录由此补足。
3. **不支持 hard link 的 POSIX 文件系统**：在这类文件系统上，发布步骤会以 `ArtifactPublishError` fail closed（不会回退到 `rename` / `replace`）。这是已冻结的设计与兼容性边界，不属于当前的正确性问题。

### 25.6 最终状态

```text
Independent Review A   : PASS
Independent Review B   : BLOCKED due environment/evidence only
                         No implementation finding
Combined Evidence      : SATISFIED
New Findings           : NONE
Blocking Findings      : NONE
P4-C6                  : CLOSED
Phase 4                : NOT CLOSED
```

后续 P4-C7 不在本包范围内，尚未开始。
