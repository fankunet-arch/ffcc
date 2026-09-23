# FC2 Organizer -- Phase 4 / P4-C6 原子 Artifact 落盘合同（Atomic Artifact Materialization Contract）

状态：**P4-C6 实现已完成**（substeps 1、2、2A、3）。**独立复查
REQUIRED。P4-C6 NOT CLOSED。** P4-C6 内部没有任何待定内容（第 25 节）。
Package：`fc2_organizer.materialization`（`__init__.py`、`errors.py`、`models.py`、`atomic.py`、
`artifacts.py`、`mapping.py`）。
Frozen Base: `e44790f57004825957f2212921171667e7c576cf`
Substep 1 Head: `b088db8acb2c4ae47037d58546000c41543b73b1`
Substep 2 Head: `67fb857523c59b3cd19691caedf3316171f8e0ca`
Substep 2A Head: `2016107bd33fc4de546698790acb84f3d28cc8a9`（extrafanart 命名边界修正，第 21 节）
Final Code Review Candidate：引入这一行的那个 substep-3 提交（门槛 + 合同定稿；没有生产代码改动）。
它的 SHA 记录在 `docs/review/P4_C6_HANDOFF.md` 中（一个提交无法包含它自己的 hash）。
Branch: `claude/phase4-c6-atomic-materialization`

第 1-15 节在 substep 1 中冻结，除了标注为 *(substep 2)* 的补充说明之外，**在 substep 2 中没有改变**。
第 16-24 节 **IMPLEMENTED IN
SUBSTEP 2**（第 21 节在 2A 中修正）。第 25-27 节在 substep 3 中新增，该 substep
**没有改动任何生产源码**。

## 1. 范围

P4-C6 整体：把 artifact 的*内容*（NFO 文本、已获取的图片）安全地写到磁盘上 -- 要么完整写入，要么完全不写，
绝不覆盖任何东西。

**Substep 1 只交付**一个原语：在一个**已经存在**的目录中，以严格的 `bytes` 原子地创建**一个**文件：

```text
bytes payload
  -> exclusive temporary sibling file
  -> write all bytes, fsync, close
  -> atomic no-overwrite publish to the final path
  -> failure cleanup of exactly the owned temporary path
```

Substep 1 **不做**：执行或读取 `OrganizePlan`、移动媒体、创建任何目录（目标目录或 `extrafanart/`）、
把 NFO / 图片角色映射到路径、批量落盘、跨卷移动、预检可写性，或者编排操作。

**Substep 2 只交付**（第 16-24 节）：artifact 种类与请求模型、纯函数映射 `build_artifact_requests`
（计划 + 已渲染的 NFO `str` + 已获取的图片 -> 有序的请求）、冻结的 NFO UTF-8 规则、图片字节身份一致性、
确定性的 extrafanart 命名，以及单个 artifact 的包装器 `materialize_artifact(request)`。它仍然不创建目录、
不移动媒体、不读取或执行 `OrganizePlan.operations`、不编排多个 artifact，也不回滚任何东西。

## 2. 与 P4-C7 的划分（冻结）

| P4-C6（本 package） | P4-C7（将来，不在这里） |
|---|---|
| 把一个 artifact 的字节安全地写到磁盘上 | 整个计划的预检 |
| | 对目标 / `extrafanart` 目录执行 `mkdir` |
| | `MOVE_MEDIA`、跨卷处理 |
| | 操作图执行、文件系统编排 |

writer 的前提条件是目标的父目录已经存在。父目录缺失时 fail closed；不会创建任何东西。

## 3. 公开 API

```python
from fc2_organizer.materialization import materialize_atomic_bytes, MaterializedArtifact

materialize_atomic_bytes(target_path: str, content: bytes) -> MaterializedArtifact
```

同步调用。恰好两个位置参数；**没有** `overwrite`、`exist_ok`、后缀、mode、`mkdir`、fsync 开关或
文件系统操作参数。失败注入接缝（`atomic._FS`）是私有的，不对外导出。

这一层只接受严格的 bytes。它不接受 `PublicationRecord`、
`OrganizePlan`、`AcquiredImage` 或 NFO `str`。*(substep 2)* 把这些映射为路径 / 字节，是独立的 `mapping` 模块
的工作（第 17 节）；原语本身没有改变。

## 4. 输入边界（冻结）

按以下顺序检查，在任何文件系统访问之前进行，并且不调用参数的任何方法：

1. `type(target_path) is str` -- 否则抛出 `MaterializationInputError`。`pathlib.Path`、任何 `os.PathLike`、
   `bytes` 路径以及 `str` 子类都会被拒绝；
   `__fspath__` / `__str__` 钩子永远不会运行。
2. `type(content) is bytes` -- 否则抛出 `MaterializationInputError`。`bytearray`、
   `memoryview`、`bytes` 子类（钩子永远不会运行）、`str` 都会被拒绝。
3. 词法路径校验（`InvalidTargetPathError`，`.reason`），依据运行时操作系统：
   * `EMPTY`、`NUL_CHARACTER`；
   * `NOT_ABSOLUTE`：Windows 要求带根目录的盘符（`C:\x`、`C:/x`）或 UNC 共享（`\\server\share\x`）；
     有根但无盘符（`\x`）、相对于盘符（`C:x`）以及相对形式都会被拒绝。POSIX 要求
     `os.path.isabs`。`~`、`$VAR`、`%VAR%` 永远不会被展开（因此它们只是非绝对路径）；不参考任何 cwd。
   * 仅限 Windows：`DEVICE_NAMESPACE`（`\\?\`、`\\.\`）、`ILLEGAL_CHARACTER`
     （`<>:"|?*`、控制字符 -- `:` 会指向 NTFS 的备用数据流）、`TRAILING_DOT_OR_SPACE`、
     `RESERVED_NAME`（`CON`、`NUL`、`COM1`...）。
   * `NO_BASENAME`（以分隔符结尾）、`DOT_SEGMENT`（任何位置出现 `.` / `..`）。

路径永远不会被规范化、解析或转为绝对路径。这并不是重新实现 P4-C2 的 planner；它只是拒绝有歧义的输入。

## 5. 父目录 / 目标的前提条件（冻结）

* 对父目录（`dirname(target_path)`）做 `stat`：不存在（或路径中经过了一个文件）-> `ParentDirectoryMissingError`；
  存在但不是目录 -> `ParentNotDirectoryError`；任何其他操作系统错误 -> `ParentDirectoryError`
  （`reason=INACCESSIBLE`）。**永远不会创建。**
* 对目标做 `lstat`（从不跟随链接）：只要存在*任何东西* -- 文件、目录、symlink、悬空 symlink、junction ->
  `TargetExistsError`。除“不存在”以外的 `lstat` 操作系统错误 -> `TargetInaccessibleError`。

这项预检只是提前退出；保证由第 7 节承担。

## 6. Overwrite = NEVER（冻结，继承自 P4-C2）

已存在的最终目标永远不会被覆盖、截断、替换、删除、重命名或加后缀（`(1)`、`_copy`、...）。没有任何旋钮可以改变这一点。
从不使用 `os.replace`；不存在“检查是否存在 -> 替换”的路径。

## 7. 原子的不覆盖发布（冻结的平台策略）

Python 标准库没有一个跨平台的“不替换的重命名”操作。冻结的按操作系统策略（`atomic._publish_no_replace`）：

| 操作系统 | 原语 | 目标已存在时 | 之后的临时文件 |
|---|---|---|---|
| Windows（`os.name == "nt"`） | `os.rename` = **不带** `MOVEFILE_REPLACE_EXISTING` 的 `MoveFileExW` | 对任何条目（文件、目录、symlink、junction）都以 `FileExistsError` 失败；在同一个卷内是原子的 | 被 rename 消耗掉 |
| POSIX | `os.link(temp, target)`（`link(2)`） | 以 `EEXIST` 失败；从不跟随已存在的目标 symlink | 由本次调用 unlink 自己的临时文件名 |

推论（冻结）：

* 在预检与发布之间由任何人创建的目标，**永远不会被替换**：发布本身会失败，并报告为 `TargetExistsError`。
* 目标要么完整出现（全部字节，已 fsync），要么根本不出现。
* 如果发布因其他操作系统错误失败，而此时目标已经存在，则报告 `TargetExistsError`；否则报告
  `ArtifactPublishError(errno)`。这次探测只用于对错误分类；它从不触发任何动作。
* 不支持 hard link 的 POSIX 文件系统会以 `ArtifactPublishError` fail closed；不存在回退到 `rename` / `replace` 的做法。
* 临时文件与目标位于同一目录，因此发布永远不会跨卷。
* 持久性：文件数据在发布之前已 `fsync`；substep 1 中不对父目录条目执行 `fsync`。

## 8. 临时文件（冻结）

* 名称：`.fc2tmp-<32 lowercase hex from secrets.token_hex(16)>.part`，拼接到目标自己的父目录下 -- 与目标同级。
  它从不包含目标名称、metadata、标题、URL 或任何 secret，也从不影响最终内容。
* 以 `O_WRONLY | O_CREAT | O_EXCL`（外加可用时的 `O_BINARY` / `O_NOINHERIT` /
  `O_CLOEXEC`）创建，从不使用 `O_TRUNC`，mode 为 `0o666`（受 umask 影响）。
  独占创建永远不会打开已存在的条目，也永远不会跟随植入的 symlink。
* 与目标同名（在 Windows 上不区分大小写）的名称会被跳过。遇到 `FileExistsError` 时换一个新的 token 重试，
  最多 8 次尝试；发生冲突的那个条目**不属于我们**，永远不会被触碰。尝试用尽或任何其他操作系统错误
  -> `TemporaryCreateError(errno)`。

## 9. 所有权与失败清理（冻结）

* 本次调用恰好拥有一个路径：它成功独占创建的那个临时文件。当 Windows 的 rename 消耗掉它，或在 POSIX 上发布后
  唯一的那次 unlink 尝试之后，所有权即告结束。
* 发生任何失败（写入、flush、close、发布，或一个 `BaseException`）时，本次调用会关闭仍然打开的描述符
  （忽略错误），并且如果仍然拥有该路径，就对**那个确切路径** unlink 一次。“已经不在了”也算作已清理。
* 从不：基于 glob / 通配符 / 目录列表的清理，删除其他 `.tmp` / `.part` / `.fc2tmp-*` 文件，删除或修改最终目标
  （即使本次调用刚刚发布了它），删除任何目录。
* 短写入会继续写完；零长度写入是 `ArtifactWriteError(WRITE, EIO)`。

## 10. 清理失败与致命控制流（冻结）

| 主结果 | 清理 | 抛出 |
|---|---|---|
| 无（成功） | -- | 返回 `MaterializedArtifact` |
| POSIX：发布成功，临时文件 unlink 失败 | 失败 | `ArtifactCleanupError(target_published=True, primary=None)`；目标完整并被保留 |
| 一个 `MaterializationError` | 成功 | 主错误 |
| 一个 `MaterializationError` | 失败 | `ArtifactCleanupError(target_published=False, primary=<primary>)`，`__cause__` = 主错误 |
| `KeyboardInterrupt`、`SystemExit`、`GeneratorExit`、任何其他 `BaseException`，或外来的 `Exception` | 成功或失败 | **同一个对象**，原样抛出；清理失败永远不会掩盖它 |

在文件系统调用周围只拦截 `OSError`；清理过程本身抛出的 `BaseException` 会继续传播。

## 11. 类型化错误（`errors.py`）

```text
MaterializationError(Exception)
+-- MaterializationInputError(MaterializationError, TypeError)
+-- InvalidTargetPathError(MaterializationError, ValueError)     .reason: TargetPathRejectionReason
+-- MaterializationModelError(MaterializationError, ValueError)
+-- ParentDirectoryError                                          .reason: ParentRejectionReason, .errno
|   +-- ParentDirectoryMissingError
|   +-- ParentNotDirectoryError
+-- TargetExistsError
+-- TargetInaccessibleError                                       .errno
+-- TemporaryCreateError                                          .errno
+-- ArtifactWriteError                                            .stage: ArtifactWriteStage (WRITE|FLUSH|CLOSE), .errno
+-- ArtifactPublishError                                          .errno
+-- ArtifactCleanupError                                          .target_published, .primary, .errno
+-- ArtifactMappingError(MaterializationError, ValueError)        .reason: MappingRejectionReason   (substep 2)
```

*(substep 2)* `MappingRejectionReason`：`NFO_EMPTY`、`NFO_NOT_UTF8_ENCODABLE`、
`PLAN_PATH_INVALID`、`IMAGE_INVALID`、`INVALID_EXTRAFANART_ORDINAL`、`DUPLICATE_TARGET`
（substep 2A 替换了原先的 `EXTRAFANART_LIMIT`；见第 21 节）。
`MaterializationModelError` 也用于非法的 `ArtifactWriteRequest`；
`MaterializationInputError` 也用于类型错误的映射 / 包装器输入。

任何失败都不会以裸 `OSError` / `ValueError` 的形式泄漏出来。消息是固定措辞：不含目标路径、不含临时路径 /
token、不含载荷，也不含 `OSError` 的文本。类型化错误都在任何 `except` 块之外抛出，因此任何 `OSError`
（其 `filename` 是临时路径）都永远不会被附加为 `__cause__` 或 `__context__`；唯一的异常链接是
`ArtifactCleanupError` 链接到其类型化的主错误。

## 12. 结果模型

```python
@dataclass(frozen=True, slots=True)
class MaterializedArtifact:
    target_path: str   # the exact input string
    size_bytes: int    # len(content)
    sha256: str        # hashlib.sha256(content).hexdigest(), i.e. of the bytes written
```

按严格类型校验（`MaterializationModelError`）。不保存任何临时路径、句柄、异常或文件系统对象。

## 13. 并发保证（冻结）

N 个 writer 争抢同一个最终目标（线程或进程，同一主机的文件系统）：最多只有一个返回 `MaterializedArtifact`；
其他每一个都得到 `TargetExistsError`（或一个 `primary` 就是这种错误的 `ArtifactCleanupError`）；
胜出者的字节是完整的，并且永远不会被覆盖；每个落败者只删除它自己的临时文件。即使所有竞争者都通过了预检，
这一点也成立，因为保证来自发布原语本身（第 7 节）。

## 14. 架构（对 substep 1 冻结）

* 只使用标准库：`__future__`、`dataclasses`、`enum`、`errno`、`hashlib`、
  `ntpath`、`os`、`posixpath`、`re`、`secrets`、`stat`、`typing`。
* 从不 import `fc2_metadata_core`、`amane`、`httpx` 或任何网络模块、
  `shutil` / `tempfile` / `glob` / `fnmatch` / `pathlib`，也不 import 任何其他
  `fc2_organizer` package（`planning`、`nfo`、`images`、`publication`、
  `discovery`）。
* 不调用 `replace`、`mkdir` / `makedirs`、`rmdir` / `rmtree` / `remove`、
  `listdir` / `scandir` / `walk` / `glob`、`expanduser` / `expandvars`、
  `getcwd`、`abspath` / `realpath` / `resolve` / `normpath`、`truncate`。
  `os.rename` / `os.link` 只出现在 `_publish_no_replace` 中；只能通过 `_remove_owned_temp` 到达 `unlink`。
* 没有反向依赖：`src` 下没有其他任何内容 import 它；
  `fc2_organizer/__init__.py` 不会急切地 import 它。
* 没有 `executor.py`、`planner.py`、`move.py`、`orchestrator.py`。
* *(substep 2)* 上面“只使用标准库”的规则适用于除 **`mapping.py` 以外**的每个模块（第 23 节）。
  `artifacts.py` 只使用标准库 / 本 package 自身。
* `fc2_organizer` 的顶层子 package 现在是
  `{"discovery", "planning", "publication", "nfo", "images", "materialization"}`；
  现有的四个 package 集合作用域守卫各更新了一行。

由 `tests/contract/test_materialization_architecture.py` 强制执行。

## 15. 测试矩阵（substep 1）

| 要求 | 测试文件 |
|---|---|
| 严格 bytes、零字节、二进制、多块写入；大小 / sha256；不残留临时文件；同级随机临时文件 | `tests/unit/materialization/test_materialization_atomic.py` |
| 已存在的文件 / 目录 / symlink / 悬空 symlink / junction -> `TargetExistsError`，保持不动；预检使用 `lstat`（与主机无关）；没有覆盖旋钮 / 后缀 | `test_materialization_atomic.py` |
| 父目录缺失 / 是文件 / 路径经过文件 / 无法访问；目标无法探测 | `test_materialization_atomic.py` |
| 拒绝 `bytearray` / `memoryview` / 恶意 `bytes` 子类 / `PathLike` / 恶意 `str` 子类，钩子调用为零，I/O 为零 | `test_materialization_atomic.py` |
| 写入（中途）、短写入、零写入、flush、close、发布失败 -> 没有目标文件，所拥有的临时文件被删除 | `test_materialization_failures.py` |
| 在预检与发布之间植入的目标 / 目录 / symlink -> 永远不会被替换 | `test_materialization_failures.py` |
| 类型化的清理失败（`target_published` False / True）、植入的无关临时文件保留、临时文件名冲突与尝试用尽、不含 secret 且不做异常链接的错误 | `test_materialization_failures.py` |
| `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / 自定义 `BaseException` 以同一个对象传播；清理失败永远不会掩盖它们 | `test_materialization_failures.py` |
| 同一目标的竞争：barrier 强制（两者都已通过预检）以及不同步的 8-writer 多轮竞争 | `test_materialization_race.py` |
| Windows + POSIX 路径规则（纯函数）、结果模型 | `test_materialization_paths_and_models.py` |
| 架构边界 | `tests/contract/test_materialization_architecture.py` |

依赖发布的测试在开发主机上以两种策略运行：
`native` 和 `hardlink`（POSIX 的 `link` + unlink 策略，通过私有接缝在支持 hard link 的 NTFS 上执行）。
创建真实 symlink 的测试在没有 symlink 权限的主机上（未开启 Developer Mode 的 Windows）会跳过；
junction 以及 `lstat` 模拟覆盖了这类主机。

## 16. Artifact 种类与请求模型（IMPLEMENTED IN SUBSTEP 2）

```python
class ArtifactKind(Enum):
    NFO = "nfo"; POSTER = "poster"; FANART = "fanart"; THUMB = "thumb"; EXTRAFANART = "extrafanart"

@dataclass(frozen=True, slots=True)
class ArtifactWriteRequest:
    kind: ArtifactKind
    target_path: str          # non-empty exact str
    content: bytes            # exact bytes, excluded from repr
    ordinal: int | None = None  # exact int >= 1 iff kind is EXTRAFANART, else None
```

按严格类型校验（`MaterializationModelError`；`bool` 不算 `int`，子类永远不能通过）。它**不**保存
`PublicationRecord`、`AcquiredImage`、
`OrganizePlan`、URL、HTTP 数据或异常 -- 只保存一个路径和一段字节。两者都从
`fc2_organizer.materialization` 导出。

## 17. 纯函数映射 API（IMPLEMENTED IN SUBSTEP 2）

```python
from fc2_organizer.materialization.mapping import build_artifact_requests

build_artifact_requests(
    plan: OrganizePlan,               # exact type
    nfo_text: str,                    # exact type; already rendered (P4-C4)
    images: ImageAcquisitionResult,   # exact type; already acquired (P4-C5)
) -> tuple[ArtifactWriteRequest, ...]
```

* 先检查输入身份，顺序为：`type(plan) is OrganizePlan`、
  `type(nfo_text) is str`、`type(images) is ImageAcquisitionResult`，否则抛出
  `MaterializationInputError` -- 在被拒绝对象的**任何属性或方法**被触碰之前完成（子类的钩子永远不会运行）。
* 纯函数且确定：**零文件系统访问**（只有词法层面的 `os.path.join`），没有时钟、随机数、网络、NFO 渲染或
  图片获取。相同的输入产生相等的 tuple。
* 从不读取 `OrganizePlan.operations`（行为测试与 AST 双重强制），也从不重新解析 / 重新校验
  `plan.canonical_number`。
* 读取的每个计划路径都必须是严格的 `PlannedPath`，其 `absolute_path` 为非空的严格 `str`
  （否则为 `PLAN_PATH_INVALID`，例如伪造的计划）。
* 所有请求的目标路径必须互不相同（在 Windows 上不区分大小写）；否则为 `DUPLICATE_TARGET`
  （防御伪造的计划；真实的 P4-C2 计划永远不会冲突）。

## 18. 映射顺序（冻结）

```text
NFO                                   always, exactly one
POSTER                                iff images.poster is not None
FANART                                iff images.fanart is not None
THUMB                                 iff images.thumb  is not None
EXTRAFANART x N                       images.extrafanart, in tuple order
```

extrafanart 的顺序就是 `ImageAcquisitionResult.extrafanart` 的 tuple 顺序（它本身即 P4-C5 的候选顺序），
永远不会按 `candidate_index`、大小或 hash 重新排序。

## 19. NFO -> 字节（冻结）

`nfo_text.encode("utf-8", errors="strict")` -- 仅此而已，不做其他任何事：
不添加 BOM，不改变换行（`\r\n` 保持为 `\r\n`），不做 strip，不做 Unicode 规范化，不重新解析或改写 XML，
调用方提供的前导 U+FEFF 按原样编码（不会被移除）。目标：
`plan.nfo_path`。空 `str` -> `ArtifactMappingError(NFO_EMPTY)`（空的 `.nfo` 永远不是合法的 P4-C4 渲染结果）；
孤立的代理项 -> `NFO_NOT_UTF8_ENCODABLE`，抛出时不链接任何 `UnicodeEncodeError`。

## 20. 图片映射（冻结）

| `ImageAcquisitionResult` 字段 | 要求的角色 | kind | 目标 |
|---|---|---|---|
| `poster` | `ImageRole.POSTER` | `POSTER` | `plan.poster_path` |
| `fanart` | `ImageRole.FANART` | `FANART` | `plan.fanart_path` |
| `thumb` | `ImageRole.THUMB` | `THUMB` | `plan.thumb_path` |
| `extrafanart` 中的每一项 | `ImageRole.EXTRAFANART` | `EXTRAFANART` | 第 21 节 |

* 缺失（`None`）的图片**不产生请求，也不算失败**。**没有跨角色回退**（例如 fanart 永远不会填补缺失的 poster）。
* `request.content` **就是** `AcquiredImage.content`（同一个对象）：不重新编码、缩放、裁剪、转码、复制，
  也不重新校验。
* 多个角色中相同的字节，或 extrafanart 中重复的字节，**不会**被去重；每一项都产生自己的请求和文件。
* 不是预期角色的严格 `AcquiredImage`、或内容不是严格 `bytes` 的图片（只可能来自伪造的结果）-> `IMAGE_INVALID`。

## 21. Extrafanart 命名（冻结）

此前没有任何冻结文档规定 extrafanart 文件的名称（v1.0 规格书、P4-C2 和 P4-C5 只固定了 `extrafanart/` 目录），
因此由 substep 2 冻结：

```text
<plan.extrafanart_directory>/extrafanart-001.jpg
<plan.extrafanart_directory>/extrafanart-002.jpg
...
```

* `ordinal` = 在 `images.extrafanart` 中从 1 开始计的位置；名称 =
  `f"extrafanart-{ordinal:03d}.jpg"`（`extrafanart_filename(ordinal)`）。
* 永远不从 URL basename、标题、hash、`candidate_index` 或随机数推导。
* *(substep 2A)* `ordinal` 是**任何严格的正 `int`** -- **没有最大值**。`03d` 只是*最小*宽度：
  `1 -> extrafanart-001.jpg`、
  `12 -> extrafanart-012.jpg`、`999 -> extrafanart-999.jpg`、
  `1000 -> extrafanart-1000.jpg`、`10000 -> extrafanart-10000.jpg`。`images.extrafanart` 中的每一项都产生
  一个请求；不截断、不回绕（取模）、不丢弃，名称始终唯一。P4-C5
  `ImageAcquisitionPolicy.max_extrafanart` 的默认值 12 只是该策略的默认值（该策略本身没有上限），**不是**
  P4-C6 的限制。
* `extrafanart_filename` 以 `ArtifactMappingError(INVALID_EXTRAFANART_ORDINAL)` 拒绝 `0`、负数、`bool`、`float`、
  `str` 以及 `int` 子类。
  （Substep 2 的 `MAX_EXTRAFANART_ORDINAL = 999` 上限及其 `EXTRAFANART_LIMIT` reason 已在 substep 2A 中移除：
  P4-C6 不得增加 P4-C5 本身没有的限制。）
* 这里**不创建**该目录；如果它不存在，每个 extrafanart 请求的写入都会因原语的 `ParentDirectoryMissingError` 而失败。

## 22. 单个 artifact 的落盘器（冻结）

```python
from fc2_organizer.materialization import materialize_artifact

materialize_artifact(request: ArtifactWriteRequest) -> MaterializedArtifact
```

* `type(request) is ArtifactWriteRequest`，否则抛出 `MaterializationInputError`
  （子类的任何钩子都不会运行，也不会到达原语）。
* 它唯一的动作：`materialize_atomic_bytes(request.target_path, request.content)`。
  它返回该结果，并让每一个类型化错误原样通过。
* **一次调用 = 一个 artifact。** 因此它原封不动地继承第 4-13 节：
  对 NFO、poster、fanart、thumb 以及每一个 extrafanart 文件，overwrite = NEVER（`TargetExistsError`，不加后缀）；
  父目录缺失 -> `ParentDirectoryError` 系列错误，绝不 `mkdir`。

## 23. 没有多 artifact 编排、没有 mkdir、没有 MOVE_MEDIA（冻结）

* 没有 `materialize_all`、`execute_plan`、`apply_operations`、
  `transaction` 或 `rollback_all`。写入多个 artifact、它们的顺序、部分失败策略以及任何目录创建，都属于
  P4-C7 的执行器。
* 由于每次调用恰好处理一个请求，这里**不存在回滚的概念**：如果 NFO 已经写入，而之后的 poster 写入失败，
  NFO 会保留（有测试）。
* package 中任何地方都没有 `mkdir` / `makedirs`（AST 强制）；目标目录和 `extrafanart/` 必须已经存在。
* `MOVE_MEDIA`、`CREATE_DIRECTORY`、`ENSURE_EXTRAFANART_DIRECTORY` 以及所有其他 `PlannedOperation`
  都永远不会被读取或执行。

**`mapping.py` 的架构（冻结）。** 它是唯一 import 另一个 `fc2_organizer` package 的模块：恰好是
`fc2_organizer.planning` 和 `fc2_organizer.images` 这两个**公开 package**（只用模型：`OrganizePlan`、
`PlannedPath`、`AcquiredImage`、`ImageAcquisitionResult`、`ImageRole`），外加
`os`。从不 import `fc2_metadata_core`、`amane`、`httpx`、`images.transport`、
`images.acquisition`、`nfo`（不调用渲染器；只消费它输出的 `str`）、`publication`、`discovery`，也不 import
`atomic` / `artifacts`。它唯一的 `os` 调用是 `os.path.join`。由于 `fc2_organizer.planning` 会传递加载
`fc2_metadata_core`，`mapping` **不会**被 `materialization/__init__.py` import（裸 `import fc2_organizer.materialization`
仍然不加载任何 planning / images / core 模块）；请显式 import 它。一个运行时测试证明，在 `amane`、`httpx`、
`images.transport`、`images.acquisition`、`nfo` 和 `publication` 都被阻断的情况下，`mapping` 仍能被 import 并正常工作。

## 24. 测试矩阵（substep 2）

| 要求 | 测试文件 |
|---|---|
| 仅 NFO / 完整清单、缺失可选图片（7 种组合）、没有跨角色回退、固定顺序、精确目标、确定性 | `tests/unit/materialization/test_materialization_mapping.py` |
| extrafanart 顺序（按 tuple，而不是 `candidate_index`）、`extrafanart-001..012.jpg`、不使用 URL/标题/hash；*(2A)* `03d` 是最小宽度（1/12/999/1000/10000），没有最大值，1000 个 extrafanart 在内存中完成映射（最后一个为 `extrafanart-1000.jpg`，重放结果相同），拒绝 0 / 负数 / bool / float / int 子类 | `test_materialization_mapping.py` |
| 严格 UTF-8、Unicode / emoji、保留 CRLF / 空白 / U+FEFF / 分解形式、不加 BOM、空 NFO、无法编码的 NFO（不做异常链接） | `test_materialization_mapping.py` |
| 图片字节身份一致（`is`）、重复字节不去重、请求不持有外来对象 | `test_materialization_mapping.py` |
| 恶意 `str` NFO 子类、计划 / 图片子类（属性访问为零）、类型错误、伪造路径 / 冲突路径 / 角色错误的图片 | `test_materialization_mapping.py` |
| 规范番号不被重新解析、不参考 `operations`、文件系统调用为零（os / os.path / open / 原语都被拦截） | `test_materialization_mapping.py` |
| 请求模型规则、恰好五种 kind | `test_materialization_mapping.py` |
| 写入 NFO / poster / extrafanart / 完整清单，字节精确，sha256 / 大小正确 | `tests/unit/materialization/test_materialization_artifacts.py` |
| 每种 kind 的目标已存在 -> `TargetExistsError`，保持不动，不残留临时文件 | `test_materialization_artifacts.py` |
| 目标目录 / `extrafanart/` 缺失 -> `ParentDirectoryMissingError`，永远不会被创建（`mkdir` 被拦截） | `test_materialization_artifacts.py` |
| 不回滚之前的成功；包装器只做委托；拒绝非请求对象 / 子类 | `test_materialization_artifacts.py` |
| 映射 / 包装器的架构，`__init__` 从不加载 mapping | `tests/contract/test_materialization_architecture.py` |

## 25. 实现状态

**P4-C6 实现已完成。** P4-C6 内部没有任何待定内容；原先标注为
"PENDING IN LATER P4-C6 SUBSTEP" 的各项（artifact 映射、NFO / 图片 /
extrafanart 落盘、最终 handoff）已由 substeps 2、2A 和 3 交付；
handoff 为 `docs/review/P4_C6_HANDOFF.md`。独立复查
**REQUIRED**；P4-C6 **NOT CLOSED**。

## 26. 集成合成门槛（substep 3）

`tests/unit/materialization/test_materialization_synthetic_gate.py` -- 只是测试层的编排（它创建自己的临时目录，
代替 P4-C7 的角色，并对每个请求调用一次 `materialize_artifact`）。生产 package 没有新增任何多 artifact 函数。

* **300 部确定性的合成影片**，位于 pytest 的 `tmp_path` 下，不访问网络，不读取用户文件：100 部仅 NFO；
  100 部 NFO + 7 种非空 poster/fanart/thumb 组合中的每一种；100 部 NFO + 全部 8 种主图组合 +
  1..13 张 extrafanart。标题覆盖 CJK、半角假名、emoji、XML 特殊字符、Unicode 分解形式、制表符；
  每第 11 个 NFO 使用 CRLF；包含 poster/fanart 之间重复的字节以及 extrafanart 中重复的字节。
* 对每部影片，预期值来自用例定义（而不是生产结果）：请求顺序 / kind / 目标路径 / ordinal / 精确字节；
  图片内容的身份一致性；重放相等；然后对每个请求调用一次 `materialize_artifact` 之后：文件字节、
  `size_bytes`、`sha256`、NFO = 不带 BOM 的精确 UTF-8、精确的目录列表（没有多余文件，没有临时文件残留）。
* Extrafanart 边界：1 / 12 / 999 / 1000 的名称；在内存中完成 1000-item 映射
  （最后一个为 `extrafanart-1000.jpg`，不写入任何内容）；没有最大值。
* 五种 kind 各自的 Overwrite NEVER：原始字节、inode 和 mtime 不变，目录列表不变（没有后缀，没有临时文件）。
* 部分成功：NFO 已写入，之后 poster 得到 `TargetExistsError`，NFO 完好无损。
* 通过 `materialize_artifact` 做失败注入（写入 / flush / close / 发布，两种发布策略）以及清理失败：
  没有最终文件，所拥有的确切临时文件被删除（对于清理失败，则只残留自己的临时文件），植入的无关临时文件完好无损。
* 通过 `materialize_artifact` 的同一目标竞争：barrier 强制（2 个 writer）和不同步（8 个 writer x 5 轮），
  两种策略下：恰好一个胜出者，胜出者字节完整，落败者得到 `TargetExistsError`，没有残留。
* 架构回归扫描以及直接复现 A-H（见 handoff）。
* 非空洞性：临时修改 `mapping.py`（前置 BOM；`03d` ->
  `02d`）会让门槛失败（分别为 5 个和 4 个失败）；该修改已撤销，没有提交。

## 27. 不属于 P4-C6 的职责（冻结）与证据说明

P4-C6 **不**：创建目标目录；创建 `extrafanart/`；
`MOVE_MEDIA`；校验源媒体；跨卷移动媒体；执行整个计划的预检；执行操作图；提供回滚 / 事务；CLI /
UI；持久化；Amane 集成。这些属于之后的 package，尤其是 P4-C7。

给独立复查的证据说明（既不是缺陷，也不是 PASS 声明）：

* 真实 POSIX 主机上的发布（在原生 POSIX 文件系统上执行 `os.link` + unlink）：
  **NOT YET OBSERVED。** hard-link 策略只通过 NTFS 上的私有策略接缝执行过。
* Windows 真实 symlink 用例：在开发主机上 **SKIPPED**（没有 symlink 权限）。junction 用例以及与主机无关的
  `lstat` 模拟已执行。
