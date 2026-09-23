# FC2 Organizer — Phase 4 / P4-C1 递归媒体发现合同（Recursive Media Discovery Contract）

状态：**在 P4-C1 冻结**（候选；独立关闭复查待进行）。
Package：`fc2_organizer.discovery`（`errors.py`、`policy.py`、`models.py`、`_platform.py`、`scanner.py`）。

**范围（对本 package 冻结）：** 只做媒体*发现* --
`dirty media root -> recursive read-only discovery -> deterministic
discovered media items`。不解析 FC2 番号，不抓取 metadata，不处理 NFO / 图片，不生成整理计划，
不做任何形式的文件系统修改，不依赖 Amane，不做持久化，没有 CLI / UI。任务简报中延续下来的完整
范围外清单见第 9 节。

## 1. 架构与依赖方向

```text
fc2_organizer
    |
    v
fc2_metadata_core
```

`fc2_metadata_core` 从不 import `fc2_organizer`。`fc2_organizer` 下的任何内容都不得 import `amane`。

`fc2_organizer.discovery` 目前对 `fc2_metadata_core` 模块的依赖为**零** -- 连 `normalize` 都不依赖。
本 package 中的媒体身份是文件系统路径（`source_path` + `index`），绝不是解析出来的 FC2 番号
（第 4 节），因此这里没有任何需要 `normalize` 做的事情。这一点由
`tests/contract/test_discovery_architecture.py` 强制执行（而不仅仅是观察到），该测试还通过静态 AST
扫描，以及在一次真实的端到端 `discover_media` 调用上运行的、阻断 import 的动态 meta path finder，
额外禁止以下内容：

* `amane`（任何子模块），
* `fc2_metadata_core.sources`（adapter、HTTP 来源框架），
* `fc2_metadata_core.aggregation`（多来源执行内部实现），
* `fc2_metadata_core.resource_control`（governor / 熔断器 / host 限流器内部实现），
* `fc2_metadata_core.http`（HTTP transport）。

## 2. 公开 API

```python
from fc2_organizer.discovery import (
    DiscoveryPolicy,
    DiscoveredMediaItem,
    DiscoveryIssue,
    DiscoveryIssueKind,
    DiscoveryStage,
    DiscoveryResult,
    discover_media,
)

result: DiscoveryResult = discover_media(root, policy=DiscoveryPolicy())
```

* `root: str | os.PathLike` -- 一个目录路径。类型错误（不是 `str`/`os.PathLike`，或是空字符串）
  会在任何文件系统访问之前抛出 `DiscoveryInputError`（`TypeError` 的子类）。
* `policy: DiscoveryPolicy | None` -- 省略时默认为 `DiscoveryPolicy()`（内置扩展名集合，第 5 节）。
  非 `DiscoveryPolicy` 的值会抛出 `DiscoveryInputError`。
* 成功时返回 `DiscoveryResult`。如果根目录本身无法扫描，则抛出 `DiscoveryRootError` 的子类
  （第 8 节）-- 对于根目录层面的问题，绝不会返回一个看起来为空的成功结果。

全部四个结果模型（`DiscoveryPolicy`、`DiscoveredMediaItem`、`DiscoveryIssue`、
`DiscoveryResult`）都是带 `slots=True` 的 frozen dataclass：不可变，构造后既不能新增属性也不能重新赋值，
每个字段都是普通的 `str`/`int`/`Enum`/`tuple`（便于序列化；从不保存异常对象、traceback、打开的句柄
或调用方持有的可变容器）。

## 3. `DiscoveredMediaItem`

字段（frozen，全部在 `__post_init__` 中校验，违规时抛出 `DiscoveryContractError`）：
`index: int`（>= 0）、`source_path: str`（绝对路径，使用操作系统原生分隔符，非空）、
`relative_path: str`（相对于被扫描的根目录，无论宿主操作系统是什么，**都使用 `Path.as_posix()` 的
POSIX 风格正斜杠** -- 这样选择是为了得到稳定、可序列化且与平台无关的表示）、
`extension: str`（小写，以点开头，例如 `.mp4`）、`size: int`（字节数，>= 0，来自
`os.stat(..., follow_symlinks=False)`）。

按照设计（任务简报第 6 节），这里不包含抓取到的标题、演员、厂牌、NFO / 图片状态、目标路径、移动状态、
Amane 状态或数据库状态 -- 这些属于后续阶段。

在一个 `DiscoveryResult` 内部，身份是 `(source_path, index)`，**绝不**是解析出来的 FC2 番号：
`A/FC2-1234567.mp4` 和 `B/FC2-1234567.mp4` 是两个独立的条目（见下文第 6 节）。

## 4. FC2 番号边界

本 package 没有实现第二个 FC2 识别器。它不调用
`fc2_metadata_core.normalize.normalize_fc2_number`，也不需要调用：它唯一的工作是判断
“这个路径上是否是一个受支持的媒体文件”，完全依据扩展名决定（第 5 节）。文件名是否恰好看起来像 FC2 番号，
与发现过程无关，完全是后续阶段关心的事情。

## 5. `DiscoveryPolicy` 与受支持的扩展名

`supported_extensions: frozenset[str]`，默认值：

```text
.mp4  .mkv  .avi  .mov  .wmv  .m4v  .ts
```

选择时优先考虑覆盖面而不是精确度 -- 这些是用户的 FC2 媒体库实际可能使用的常见视频容器；
漏掉一个少见容器（false-negative）比误收一个带有这类扩展名的非视频文件（false-positive）更糟糕
（v1.0 中没有内容嗅探）。可以通过 `DiscoveryPolicy(supported_extensions=...)` 覆盖。

* 在构造时规范化：条目转为小写，并且必须以 `.` 开头、点之后非空；裸 `str`/`bytes` 参数（它是*字符*的
  可迭代对象，而不是扩展名的可迭代对象）会被明确拒绝，而不是被悄悄误解。
* 通过构造时的规范化，匹配**不区分大小写**：`VIDEO.MP4` 和 `video.mp4` 匹配同一个策略条目。
* 扩展名是判断“是不是媒体”的**唯一**信号 -- 不对任何文件名惯例（`~prefix`、`.part`、时间戳、...）
  做特殊处理。`.part`/`.tmp` 这类伴随文件之所以被排除，是因为它们不是受支持的扩展名，而不是因为任何
  “看起来像未下载完的文件”的启发式判断。
* 这是声明扩展名的唯一集中位置；package 中的其他地方都不硬编码扩展名列表。

## 6. 重复项安全（冻结）

同一个 FC2 番号（或同一个普通文件名）出现在两个不同的目录下时，总是产生两个独立的
`DiscoveredMediaItem`。scanner 中任何地方都没有按番号去重，也没有 `dict[number, ...]`。
`DiscoveryResult.__post_init__` 强制执行与之互补的不变量：任何两个条目都不能有相同的 `source_path`
（真正在物理上重复发现同一个文件，是 scanner 的 bug，而不是合法结果）。

## 7. 确定性排序（冻结）

遍历从不依赖操作系统原始的目录枚举顺序
（`os.scandir()`/`Path.iterdir()` 的顺序在不同平台上没有规定，在某些文件系统上甚至在多次调用之间
也不一致）。取而代之的是：

1. 在同一个目录中，所有直接条目（文件和子目录一起）按 `entry.name` 用普通的 Python 字符串比较
   （Unicode 码点 / ordinal）排序 -- 与 locale 无关，不是“自然”排序，只求稳定且可复现。
   由于文件系统本身保证同一目录中的条目名称唯一，这种排序不存在需要打破的并列情况。
2. 目录树按**深度优先、先序**遍历：在每个目录中，按上述排序顺序访问条目；遇到子目录条目时，
   立即递归进入（完整访问其整个子树），然后才访问父目录中排在下一个的同级条目。
3. 每个 `DiscoveredMediaItem.index` 严格按遍历过程中追加媒体文件的顺序分配（一个按调用计数、
   从 0 开始的计数器）。

推论：对于同一棵未改变的目录树，重复调用 `discover_media` 会产生逐字节相同的 `relative_path` 排序和
`index` 分配。新增、删除或重命名任何文件 / 目录都可能改变后续的下标（下标是位置性的，不是在树结构变化
前后保持稳定的标识符 -- 这是预期行为：v1.0 的发现是一次性快照，不是 diff 引擎）。

已知局限：遍历使用 Python 调用栈进行递归（每层目录深度占一个栈帧）。极深的目录树（接近
`sys.getrecursionlimit()`，默认约 ~1000）可能抛出 `RecursionError`。预计没有任何真实的 FC2 媒体库会
嵌套到接近这样的深度；这不在 v1.0 的范围内（见 P4-C1 handoff 中的“Known Limitations”）。

## 8. 根目录失败语义（冻结）

`discover_media` 会抛出异常，绝不会悄悄降级为一个空的 `DiscoveryResult`：

| 情况 | 异常 |
|---|---|
| 根目录不存在 | `DiscoveryRootNotFoundError` |
| 根目录存在但不是目录（包括路径中某个父级组件不是目录的情况） | `DiscoveryRootNotADirectoryError` |
| 根目录存在但无法访问（对其 stat 时出现 `PermissionError` 或其他 `OSError`） | `DiscoveryRootAccessError` |
| `root` 参数类型错误，或为空字符串 | `DiscoveryInputError` |
| `policy` 参数不是 `DiscoveryPolicy` | `DiscoveryInputError` |

以上所有情况（两个 `DiscoveryInputError` 情况除外，它们属于参数合同违规）都是 `DiscoveryRootError`
的子类，而它本身又是 `DiscoveryError`。因此，一个成功返回的 `DiscoveryResult` 总是意味着
“根目录存在、是目录、可以访问” -- 对于一棵真正为空且完全可读的目录树，`items`/`issues` 仍然可能都为空，
而这种情况只会与它自己相同，绝不会与根目录失败混淆。

## 9. 子树 / 条目失败隔离（冻结）

遍历过程中遇到的非根目录问题（子目录权限被拒绝、扫描中途消失的目录或文件、stat 失败），既不会被悄悄吞掉，
也不会中止整个扫描。它会被记录为一个 `DiscoveryIssue`，然后遍历继续处理下一个同级条目 / 目录。

`DiscoveryIssue` 字段：`path: str`、`kind: DiscoveryIssueKind`、
`stage: DiscoveryStage`、`detail: str`。

`DiscoveryIssueKind`：`PERMISSION_DENIED`、`PATH_VANISHED`、`STAT_FAILED`、
`SYMLINK_SKIPPED`、`REPARSE_POINT_SKIPPED`。

`DiscoveryStage`：`LIST_DIRECTORY`、`CLASSIFY_ENTRY`、`STAT_ENTRY`。

`detail` **从不**是 `str(exc)`/`repr(exc)`，从不是 traceback，也从不是异常对象 --
`DiscoveryIssue.build(path, kind, stage)` 是 scanner 使用的唯一构造方式，它总是附上五条固定、简短、
预设消息中按 `kind` 选出的一条（例如 `"permission denied"`）。这是在构造层面做到有界和脱敏的，
而不是事后截断（不过 `DiscoveryIssue.__post_init__` 还会把长度超过 `MAX_ISSUE_DETAIL_LENGTH` = 200 个字符的
`detail` 硬截断，作为直接构造时的纵深防御后备措施）。

文件系统接缝（`scanner._list_directory_sorted`、`scanner._stat_entry`、
`scanner._is_symlink`）被隔离为小的模块级函数，目的是让测试可以通过 `monkeypatch` 在精确的位置注入
`PermissionError` / `FileNotFoundError` / `OSError`，而不必依赖不稳定、难以构造的真实操作系统竞争条件，
也不必对调用用户自己的文件制造真实的权限拒绝（这在 Windows 上尤其不可靠）。

## 10. Symlink / junction / reparse point 策略（冻结、强制、不可配置）

* 作为 symlink 的目录条目（`os.DirEntry.is_symlink()`）：如果是目录，**永远不会**递归进入；
  如果是文件，**永远不会**被当作普通媒体来源 -- 无论它指向什么。
  在 `CLASSIFY_ENTRY` 阶段记录为 `DiscoveryIssueKind.SYMLINK_SKIPPED`。
* 作为 Windows **reparse point** 的目录条目（junction 以及任何其他 NTFS reparse tag）同样永远不会被递归
  进入，尽管对于 junction，`os.DirEntry.is_symlink()` 报告的是 `False`（junction 带的是
  `IO_REPARSE_TAG_MOUNT_POINT`，而不是 `IO_REPARSE_TAG_SYMLINK`）。通过
  `fc2_organizer.discovery._platform.is_reparse_point` 检测，它读取
  `os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT` --
  刻意*不*使用 `os.path.isjunction`（仅 Python 3.12+ 提供；本项目的目标版本是 3.11+），并且刻意以属性位
  而不是具体的 reparse tag 作为判断依据，因此*任何*类型的 reparse 都被保守地视为不安全。
  在非 Windows 系统上（`os.name != "nt"`）总是返回 `False`。
  记录为 `DiscoveryIssueKind.REPARSE_POINT_SKIPPED`。
* 这是一个**固定的 v1.0 安全不变量，而不是策略旋钮** --
  `DiscoveryPolicy` 没有 `follow_symlinks` 字段。理由：防止无限递归（symlink / junction 循环），
  防止扫描到 `root` 之外（指向别处的链接），并防止通过两条不同路径重复计算同一批物理文件。
* 专门针对 symlink **文件**的保守选择（任务简报第 11 节）：不解析它、也不通过它做 stat，而是把它完全
  排除在结果之外，与 symlink 目录被排除在递归之外的做法完全一致。如果真实的使用场景需要，后续阶段可以
  通过显式的 opt-in 策略重新审视；v1.0 不做猜测。

## 11. 测试矩阵（`tests/unit/discovery/`、`tests/contract/test_discovery_architecture.py`）

| # | 要求 | 测试文件 |
|---|---|---|
| 1-7, 9-10, 12-15 | 空根目录、单个 / 嵌套 / 深层 / 混合文件、忽略不受支持的文件、不区分大小写、Unicode 名称、不常见但合法的字符 | `test_discovery_basic.py` |
| 8, 9, 23 | 跨目录重复的 FC2 番号、跨目录重复的文件名、每个文件恰好发现一次 | `test_discovery_duplicates_and_ordering.py` |
| 11 | 多次扫描之间的确定性排序 | `test_discovery_duplicates_and_ordering.py` |
| 16-18 | 权限被拒绝的子树、在 stat 之前消失的文件、扫描过程中消失的目录（通过 monkeypatch 注入） | `test_discovery_failure_isolation.py` |
| 19-21 | 不跟随 symlink 目录 / 文件、symlink 循环不会挂起、不跟随 junction、junction 循环不会挂起、不跟随逃出根目录的 junction | `test_discovery_symlinks_and_junctions.py` |
| 21（平台抽象） | `is_reparse_point` 不依赖真实 junction 的单元测试 | `test_discovery_platform_helper.py` |
| 22, 24 | 大型合成目录树阶段门槛、伴随文件永远不会成为条目 | `test_discovery_stage_gate.py` |
| 25-27 | 不修改文件系统、不依赖网络、不依赖 Amane | `test_discovery_no_mutation.py`、`tests/contract/test_discovery_architecture.py` |
| 模型合同 | `DiscoveredMediaItem`/`DiscoveryIssue`/`DiscoveryResult` 的不变量 | `test_discovery_models.py` |
| 策略合同 | 扩展名规范化 / 校验 | `test_discovery_policy.py` |
| 根目录失败语义 | `test_discovery_root_failures.py` |
| 架构 / 依赖方向 | `tests/contract/test_discovery_architecture.py` |

## 12. 性能边界（冻结）

发现过程只读取文件系统元数据（`os.scandir`、`entry.stat()`）；它从不读取文件内容，从不计算文件 hash，
也从不重新列出已经访问过的目录。内存随 `len(items) + len(issues)` 线性增长；存活的递归深度随目录嵌套深度
增长，而不随文件总数增长（同一目录中的同级条目一次处理一个，处理完即从调用栈中丢弃，而不是同时保持打开）。

## 13. 范围之外（任务简报第 16 节，此处按原意延续）

不抓取 metadata，不修改 `SourceAdapter`/`MultiSourceEngine`/重试/资源 governor/`BatchScheduler`，
没有 `OrganizePlan`，不生成输出命名或目标目录，不渲染 / 写入 NFO，不下载 poster/fanart/thumb/extrafanart，
也不校验图片，没有 artifact writer，不对整理器的源媒体做 `mkdir`/重命名/移动/复制/删除，没有文件系统执行器，
没有预览 UI，没有 CLI 报告系统，没有 JSON 诊断信息，没有持久化的任务 / 数据库 / 恢复，没有 Amane adapter，
没有 HTTP 服务 / REST API / GUI。

## 14. 延续的待办（P4-C1 未处理）

未触发 / 未处理：`C2-L2`、`P2-R-05`、`P2-R-06`、`P2-R-07`、
`P2-R-10`、`C3-N1`、`C3-N2`、`C3-N3`、`C3-N4`、`C4-N1`、`C4-R1-N1`、
`C4-R1-N2`、`C4-R1-N3`、`F3`、`F5`、`C5-R1-L1`。这些债务没有一项被触及、读取，或与本 package 相关；
`fc2_organizer.discovery` 对它们所涉及的任何模块都零依赖。
