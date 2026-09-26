# FC2 Organizer -- Phase 4 / P4-C7 安全文件系统执行合同（Safe Filesystem Execution Contract）

```text
状态           ：ESTABLISHED（E0，Docs-Only Establishment）-- 开发未开始
Package        ：fc2_organizer.execution（新顶层 package，S1 起创建）
Frozen Base    ：a0a69c71a1451232ded2c8ae8ecd514cf48ba95b（DOCS-CN Final Closure Head）
Branch         ：claude/phase4-c7-safe-filesystem-executor
施工计划       ：docs/P4_C7_CONSTRUCTION_PLAN.md（S1-S6，全部批次已在 E0 冻结）
```

本合同在 E0 一次性冻结 P4-C7 的全部规范语义。S1-S6 只能**执行**本合同，不得重新设计。
后续批次对本文件唯一允许的改动是第 32 节“实现状态”表中的状态行；任何语义改动都必须作为独立的
合同修订轮次提出，并经独立复查。

---

## 1. 范围

P4-C7 回答：“给定一个已经构建好的 `OrganizePlan` 和一组已经准备好的 artifact 写入请求，
如何把**单个**影片安全地落到真实文件系统上？”

```text
OrganizePlan (P4-C2)  +  tuple[ArtifactWriteRequest, ...] (P4-C6)  [+ ExecutionCheckpoint]
        |
preflight_execution(...)        只读：结构验证 + 文件系统快照 + 阻断原因
        |
ExecutionPreflight (sealed, immutable)
        |
execute_filesystem(preflight)   forward-only：mkdir / 媒体移动 / artifact 落盘
        |
ExecutionResult(SUCCESS | PARTIAL | FAILED, checkpoint iff PARTIAL)
```

P4-C7 **做**：OrganizePlan 执行边界加固、artifact manifest 加固、只读预检、目标目录与
`extrafanart` 目录的独占创建、同卷媒体移动、跨卷媒体复制、源删除、源 / 目标变更检测、
部分执行与进程内 checkpoint 重试、类型化失败词汇。

P4-C7 **不做**：批量编排、并发调度、预览 UI、CLI、JSON / 持久化 / 磁盘上的 resume、
数据库、NFO 渲染、图片获取、metadata 处理、FC2 番号解析、Amane 集成、回滚、覆盖、
自动加后缀、`library_root` 创建、空间预估、长路径前缀改写。批量与预览属于 P4-C8（第 30 节）。

## 2. 术语

| 术语 | 含义 |
|---|---|
| final effect | 在最终位置上可见的文件系统结果：已创建的目标目录、已发布的最终媒体、已删除的源、已发布的 artifact、已创建的 `extrafanart` 目录 |
| 临时文件 | 本次调用独占创建的同级 `.fc2tmp-<32 hex>.part`；不算 final effect |
| 快照（snapshot） | 一次 `lstat` 得到的 `EntryIdentity`（第 12 节） |
| 重新校验（revalidation） | 在修改之前再次 `lstat` 并与快照逐字段比较 |
| 执行单元（unit） | 第 9 节定义的、有固定顺序的最小执行步骤 |
| fresh execution | 没有 checkpoint 的首次执行（第 13 节） |
| resume | 携带本进程产生的 `ExecutionCheckpoint` 的继续执行（第 14 节） |

## 3. 架构与依赖方向（冻结）

```text
fc2_organizer.execution
    |-- fc2_organizer.planning          （仅公开 package：OrganizePlan、PlannedPath、PlannedOperation、PlannedOperationKind）
    |-- fc2_organizer.materialization   （仅公开 package：ArtifactKind、ArtifactWriteRequest、materialize_artifact、
    |                                    MaterializedArtifact 以及 materialization 公开错误类型）
    '-- 标准库
```

* 允许的标准库：`__future__`、`dataclasses`、`enum`、`errno`、`hashlib`、`hmac`、`ntpath`、`os`、
  `posixpath`、`re`、`secrets`、`stat`、`threading`、`typing`。
* 只 import **裸** package：`fc2_organizer.planning`、`fc2_organizer.materialization`。从不 import 它们的
  子模块（`planning.paths`、`planning.planner`、`materialization.atomic`、`materialization.mapping`……）。
* 禁止：`fc2_metadata_core`（任何子模块，直接 import）、`amane`、`httpx` 及任何网络模块、
  `fc2_organizer.discovery`、`fc2_organizer.images`（任何部分）、`fc2_organizer.nfo`、
  `fc2_organizer.publication`、aggregation / batch / resource_control、`shutil`、`tempfile`、`glob`、
  `fnmatch`、`pathlib`、`asyncio`、`subprocess`、`ctypes`、`time`、`random`。
* 不重新解析 FC2 番号：从不调用 `is_valid_fc2_number` / `normalize_fc2_number`；`canonical_number`
  只作为已由 P4-C2 验证过的字符串，按字面参与结构比较（第 6 节）。
* 传递加载说明：`fc2_organizer.planning` 会传递加载 `fc2_metadata_core`（P4-C2 合同第 1 节），
  `fc2_organizer/__init__.py` 会加载 `discovery`。这是已冻结的上游事实，不是 P4-C7 的直接依赖；
  静态 AST 扫描证明 `execution` 源码从不**引用**它们。运行时阻断器阻断
  `amane`、`httpx`、`requests`、`socket`、`ssl`、`urllib.request`、`http.client`、
  `fc2_organizer.images`、`fc2_organizer.nfo`、`fc2_organizer.publication`，并在端到端执行中证明它们从未被加载。
* 没有反向依赖：`src` 下没有任何其他模块 import `fc2_organizer.execution`；
  `fc2_organizer/__init__.py` 不急切 import 它。
* `extrafanart` 命名：P4-C7 不 import `materialization.mapping`（它会加载 `fc2_organizer.images`）。
  执行层在自己的私有常量中持有冻结格式 `"extrafanart-{:03d}.jpg"`，并由一个**测试层**的一致性测试证明
  它与 `mapping.extrafanart_filename` 对 1..10000 完全一致（第 31 节）。这是在“最小依赖”与“单一来源”
  之间的裁决：生产依赖最小，漂移由测试阻断。
* 路径词法校验：`planning.paths` 与 `materialization.atomic._validate_target_path` 都不是公开 API，
  因此 P4-C7 在 `execution/paths.py` 中持有自己的词法校验器（规则集等同 P4-C6 合同第 4 节，
  另加第 26.3 节的扩展保留名）。一个测试层一致性测试证明，对共享语料，P4-C7 校验器拒绝 P4-C6 拒绝的每一个路径。

模块划分（冻结；S1-S5 按此创建，不得增删模块名）：

| 模块 | 职责 | 允许 import |
|---|---|---|
| `__init__.py` | 公开 API 再导出 | 本 package |
| `errors.py` | 异常与拒绝原因枚举 | `__future__`、`enum` |
| `models.py` | 值模型、枚举、快照、checkpoint / preflight / result | `__future__`、`dataclasses`、`enum`、`re`、本 package `errors` |
| `paths.py` | 纯词法路径校验 / 比较 | `__future__`、`ntpath`、`os`、`posixpath`、本 package `errors` |
| `validation.py` | 计划图与 manifest 验证、执行单元推导 | 上述 + `fc2_organizer.planning`、`fc2_organizer.materialization` |
| `seal.py` | 指纹、HMAC 封印、消费注册表 | `__future__`、`hashlib`、`hmac`、`secrets`、`threading`、本 package |
| `_fs.py` | 私有文件系统接缝、`lstat` 快照、条目列举 | `__future__`、`dataclasses`、`errno`、`os`、`secrets`、`stat`、`typing`、本 package |
| `directories.py` | 独占 `mkdir` 与目录快照 | 本 package + `errno`、`os`、`stat` |
| `transfer.py` | 同卷移动 / 跨卷复制 / 源删除 | 本 package + `errno`、`hashlib`、`os`、`stat` |
| `preflight.py` | `preflight_execution` | 本 package + planning / materialization 公开 package |
| `executor.py` | `execute_filesystem`、artifact 执行 | 本 package + planning / materialization 公开 package |

## 4. 公开 API（冻结）

```python
from fc2_organizer.execution import preflight_execution, execute_filesystem

preflight: ExecutionPreflight = preflight_execution(
    plan,              # fc2_organizer.planning.OrganizePlan（严格类型）
    artifacts,         # tuple[fc2_organizer.materialization.ArtifactWriteRequest, ...]（严格 tuple）
    checkpoint=None,   # ExecutionCheckpoint | None（仅本进程由 execute_filesystem 产生）
)

result: ExecutionResult = execute_filesystem(preflight)
```

* 两个函数都是同步调用。没有 `overwrite`、`exist_ok`、`force`、`dry_run`、`rollback`、`parents`、
  后缀、并发、回调或文件系统操作参数。
* `preflight_execution` **只读**：只调用 `lstat` / `open(O_RDONLY)` + `read`（仅 resume 时对已完成 artifact
  重新计算 hash）/ `listdir`（仅 resume 时列举本执行拥有的目录）。永不创建、写入、重命名、删除任何东西。
* `execute_filesystem` 是唯一产生 final effect 的入口。
* 公开导出（`__all__`，冻结）：
  `preflight_execution`、`execute_filesystem`、
  `ExecutionPreflight`、`ExecutionResult`、`ExecutionCheckpoint`、
  `ExecutionStatus`、`ExecutionStep`、`ExecutionUnit`、`PreflightMode`、`TransferMode`、
  `EntryIdentity`、`EntryType`、`PathRole`、`EffectKind`、`CompletedEffect`、`LeftoverTemporary`、
  `PreflightBlocker`、`PreflightBlockReason`、`ExecutionFailure`、`ExecutionFailureKind`、`TransferStage`、
  `ExecutionError`、`ExecutionInputError`、`ExecutionContractError`、`PlanGraphError`、
  `PlanGraphRejectionReason`、`ArtifactManifestError`、`ManifestRejectionReason`、`CheckpointError`、
  `CheckpointRejectionReason`、`PreflightIntegrityError`、`PreflightIntegrityReason`、
  `PreflightNotReadyError`、`ExecutionModelError`。
* 私有失败注入接缝 `fc2_organizer.execution._fs._FS` 不导出。

## 5. 输入身份边界（冻结）

在任何文件系统访问之前、按以下顺序检查；被拒绝对象的任何方法 / 属性钩子都不会运行：

1. `type(plan) is OrganizePlan`，否则 `ExecutionInputError`。
2. `type(artifacts) is tuple`，否则 `ExecutionInputError`。
3. `checkpoint is None or type(checkpoint) is ExecutionCheckpoint`，否则 `ExecutionInputError`。
4. `execute_filesystem`：`type(preflight) is ExecutionPreflight`，否则 `ExecutionInputError`。

子类（包括 `OrganizePlan`、`PlannedPath`、`PlannedOperation`、`ArtifactWriteRequest`、`tuple`、`str`、
`bytes`、`int` 的子类）一律拒绝。原因：`OrganizePlan` 的模型层校验使用 `isinstance`，且 frozen dataclass
可以被 `object.__setattr__` 在构造后改写，因此执行边界不能信任“它曾经通过了 `__post_init__`”。

## 6. OrganizePlan 执行边界加固（冻结；中和延续项“操作图模型层加固”）

`validation.validate_plan(plan)` 在 `preflight_execution` 与 `execute_filesystem`（重新计算指纹前）中执行。
全部为纯词法检查，零文件系统访问。任何违规抛出 `PlanGraphError(reason)`。

### 6.1 重新构造校验

用 `plan` 的 15 个字段重新调用 `OrganizePlan(...)` 构造一个新实例（公开 API），使 P4-C2 的
`__post_init__`（完全限定根目录、目标包含关系、字段类型）对**当前**字段值再运行一次。
构造抛出的任何 `OrganizePlanError` -> `PlanGraphError(PLAN_RECONSTRUCTION_FAILED)`（不链接原异常的消息）。
新实例必须 `==` 原实例。

### 6.2 字段严格类型

* `source_path`、`source_relative_path`、`source_extension`、`canonical_number`、`library_root`：严格 `str`、非空。
* `source_index`、`source_size`：严格 `int`（非 `bool`），`>= 0`。
* 七个路径字段：严格 `PlannedPath`，其 `absolute_path` 为严格非空 `str`。
* `operations`：严格 `tuple`，每一项为严格 `PlannedOperation`，`kind` 为严格 `PlannedOperationKind` 成员，
  `target` 为严格 `PlannedPath`，`source` 为严格 `PlannedPath` 或 `None`。

违规原因：`PATH_TYPE`、`FIELD_TYPE`、`OPERATIONS_NOT_TUPLE`、`OPERATION_TYPE`。

### 6.3 冻结的 7 步操作图

`operations` 必须**恰好** 7 项（否则 `OPERATION_COUNT`），且逐项满足：

| # | `kind` | `target` 必须 `==` | `source` |
|---|---|---|---|
| 1 | `CREATE_DIRECTORY` | `plan.target_directory` | `None` |
| 2 | `MOVE_MEDIA` | `plan.target_media_path` | `== PlannedPath(plan.source_path)` |
| 3 | `MATERIALIZE_NFO` | `plan.nfo_path` | `None` |
| 4 | `MATERIALIZE_POSTER` | `plan.poster_path` | `None` |
| 5 | `MATERIALIZE_FANART` | `plan.fanart_path` | `None` |
| 6 | `MATERIALIZE_THUMB` | `plan.thumb_path` | `None` |
| 7 | `ENSURE_EXTRAFANART_DIRECTORY` | `plan.extrafanart_directory` | `None` |

违规原因：`OPERATION_KIND_ORDER`、`OPERATION_TARGET_MISMATCH`、`OPERATION_SOURCE_MISMATCH`。
执行层**从不**遍历 `operations` 来决定做什么：执行单元由第 9 节从已验证的字段推导，`operations` 只作为
必须与之完全一致的声明被校验。

### 6.4 布局结构（字符串精确相等，按 P4-C2 planner 的构造公式）

以运行时操作系统的 `os.path.join` 计算期望值，要求**逐字符**相等：

* `target_directory == join(library_root, canonical_number)`（`TARGET_DIRECTORY_LAYOUT`）。
* `target_media_path == join(target_directory, canonical_number + source_extension.lower())`
  （`MEDIA_NAME_MISMATCH`）。
* `nfo_path == join(target_directory, b)`，`b` 以 `canonical_number` 开头，余下部分以 `.` 开头且长度 `>= 2`
  （`NFO_NAME_INVALID`）。
* `poster_path`、`fanart_path`、`thumb_path`、`extrafanart_directory` 各自 `== join(target_directory, b)`，
  `b` 为单一路径组件（`ARTIFACT_LAYOUT`）。
* 六个 basename（媒体、NFO、poster、fanart、thumb、extrafanart 目录名）两两不冲突：Windows 用
  `casefold`，POSIX 用精确比较（`BASENAME_COLLISION`）。
* `canonical_number` 与全部六个 basename 通过第 26.3 节的组件校验（`UNSAFE_COMPONENT`）。
  这是组件安全检查，不是 FC2 番号解析。

`OrganizePlan` 不携带 `OutputPolicy`（P4-C2 已知局限），因此 poster / fanart / thumb / extrafanart 目录名
只做一致性与安全性校验，不与默认值比较；媒体、目录与 NFO 前缀可精确推导，因此精确比较。

### 6.5 源路径

* `source_path` 通过第 26 节的词法校验（完全限定、无 `.`/`..`、无 NUL、Windows 非法字符等）
  （`SOURCE_PATH_REJECTED`）。
* `splitext(source_path)[1].lower() == source_extension.lower()`（`SOURCE_EXTENSION_MISMATCH`；
  P4-C1 scanner 已把扩展名转为小写，因此只做不区分大小写比较）。
* `source_path` 不等于任何目标路径，且不在 `target_directory` 之下（按路径段、Windows 不区分大小写）
  （`SOURCE_INSIDE_TARGET`）。
* `source_path` 可以位于 `library_root` 之下的其他位置（例如下载目录就在库中）；这不是错误。

### 6.6 目标路径词法校验

`library_root`、`target_directory`、`target_media_path`、`extrafanart_directory` 以及第 7 节中的每个
artifact 目标，都通过第 26 节的词法校验（`TARGET_PATH_REJECTED`）。P4-C2-R1-02（裸 `\\server`）在执行边界
被中和：Windows 上 UNC 形式的 `library_root` 必须同时有 server 与 share 两个组件（`LIBRARY_ROOT_REJECTED`）。
P4-C2-R1-02 本身作为 planning package 的 finding 仍然 CARRIED；P4-C7 不修改 planning。

## 7. Artifact manifest 加固（冻结）

`validation.validate_manifest(plan, artifacts)`，纯函数、零文件系统访问；违规抛出
`ArtifactManifestError(reason)`。

### 7.1 元素

* 每一项为严格 `ArtifactWriteRequest`（`REQUEST_TYPE`）；用其四个字段重新构造一次
  `ArtifactWriteRequest(...)` 以重新触发 P4-C6 的 `__post_init__`，任何 `MaterializationError` ->
  `REQUEST_INVALID`；新实例必须 `==` 原实例。
* `content` 为严格非空 `bytes`（`EMPTY_CONTENT`）。真实管线（P4-C4 NFO、P4-C5 JPEG）永远不会产生空内容。
  P4-C7 不校验 UTF-8 / JPEG 结构（那属于上游已关闭的边界）。

### 7.2 数量与顺序

```text
NFO                 恰好 1 个，且位于第 0 位
POSTER              0..1
FANART              0..1
THUMB               0..1
EXTRAFANART         0..N（无上限）
顺序：NFO, POSTER?, FANART?, THUMB?, EXTRAFANART...
```

原因：`NFO_MISSING`、`NFO_NOT_FIRST`、`DUPLICATE_KIND`、`ORDER`。

### 7.3 目标对齐

| kind | `target_path` 必须逐字符等于 |
|---|---|
| `NFO` | `plan.nfo_path.absolute_path` |
| `POSTER` | `plan.poster_path.absolute_path` |
| `FANART` | `plan.fanart_path.absolute_path` |
| `THUMB` | `plan.thumb_path.absolute_path` |
| `EXTRAFANART`（第 k 个） | `join(plan.extrafanart_directory.absolute_path, "extrafanart-{:03d}.jpg".format(k))` |

原因：`TARGET_MISMATCH`、`EXTRAFANART_NAME_MISMATCH`。

### 7.4 extrafanart 序号

第 k 个 EXTRAFANART（从 1 开始计）的 `ordinal` 必须 `== k`：从 1 开始、连续、无空洞、无重复
（`EXTRAFANART_ORDINAL_SEQUENCE`）。没有上限；1000 张时最后一个为 `extrafanart-1000.jpg`。

### 7.5 重复目标

全部 `target_path` 两两不同（Windows `casefold`，POSIX 精确）（`DUPLICATE_TARGET`）。任何 artifact 目标不得
等于 `target_media_path` 或 `extrafanart_directory`（`DUPLICATE_TARGET`）。

### 7.6 manifest 指纹

`manifest_fingerprint` = SHA-256（第 15.2 节编码）覆盖每一项的 `kind.value`、`target_path`、`ordinal`、
`len(content)`、`sha256(content)`。preflight 保存它；`execute_filesystem` 重新计算并比较，任何在 preflight
之后对 manifest 对象图的改写都会被检测到（`PreflightIntegrityError(FINGERPRINT_MISMATCH)`）。

## 8. 执行状态（冻结）

```python
class ExecutionStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
```

状态描述的是**该影片累计的文件系统状态**，而不仅仅是本次调用：

| 状态 | 条件 | `checkpoint` | `failure` |
|---|---|---|---|
| `SUCCESS` | 第 9 节全部执行单元都已完成（含源删除） | `None` | `None` |
| `PARTIAL` | 失败发生时，累计至少存在一个 final effect（包括 checkpoint 中已有的） | 非 `None`，新签发 | 非 `None` |
| `FAILED` | 失败发生时，累计不存在任何 final effect | `None` | 非 `None` |

推论：resume 执行的结果永远不会是 `FAILED`（checkpoint 至少记录了目标目录已创建）；
fresh execution 在 `mkdir` 成功之前的任何失败都是 `FAILED`；`mkdir` 成功之后的任何失败都是 `PARTIAL`。
遗留的临时文件不是 final effect，不会把 `FAILED` 变成 `PARTIAL`（但会记录在 `leftover_temporaries` 中）。

## 9. 执行单元与顺序（冻结）

执行单元由已验证的 `plan` 与 manifest 推导，顺序固定：

```text
U1  CREATE_DIRECTORY                 -> effect TARGET_DIRECTORY_CREATED
U2  MOVE_MEDIA                       -> effect MEDIA_PUBLISHED，随后 SOURCE_REMOVED
U3  MATERIALIZE_NFO                  -> effect ARTIFACT_PUBLISHED(NFO)
U4  MATERIALIZE_POSTER    （iff manifest 含 POSTER） -> ARTIFACT_PUBLISHED(POSTER)
U5  MATERIALIZE_FANART    （iff manifest 含 FANART） -> ARTIFACT_PUBLISHED(FANART)
U6  MATERIALIZE_THUMB     （iff manifest 含 THUMB）  -> ARTIFACT_PUBLISHED(THUMB)
U7  ENSURE_EXTRAFANART_DIRECTORY     -> effect EXTRAFANART_DIRECTORY_CREATED（即使没有 extrafanart 图片也执行）
U8.. MATERIALIZE_EXTRAFANART(k=1..N) -> ARTIFACT_PUBLISHED(EXTRAFANART, k)
```

* manifest 中缺失的可选图片：该单元为 `SKIPPED_ABSENT`，不是失败，也不是 effect；在
  `ExecutionPreflight.skipped_steps` 中列出。
* extrafanart 文件没有独立的 `PlannedOperation`；它们是第 7 步的内容，排在第 7 步之后按序号执行。
* **期望 effect 序列** `E(plan, manifest)` 由上表确定性推导。任何合法的累计 effect 集合都必须是
  `E` 的**前缀**（第 14.3 节）。
* 遇到第一个失败立即停止；之后的单元不执行（forward-only、确定性）。

```python
class ExecutionStep(Enum):
    CREATE_DIRECTORY = "create_directory"
    MOVE_MEDIA = "move_media"
    MATERIALIZE_NFO = "materialize_nfo"
    MATERIALIZE_POSTER = "materialize_poster"
    MATERIALIZE_FANART = "materialize_fanart"
    MATERIALIZE_THUMB = "materialize_thumb"
    ENSURE_EXTRAFANART_DIRECTORY = "ensure_extrafanart_directory"
    MATERIALIZE_EXTRAFANART = "materialize_extrafanart"

class EffectKind(Enum):
    TARGET_DIRECTORY_CREATED = "target_directory_created"
    MEDIA_PUBLISHED = "media_published"
    SOURCE_REMOVED = "source_removed"
    ARTIFACT_PUBLISHED = "artifact_published"
    EXTRAFANART_DIRECTORY_CREATED = "extrafanart_directory_created"
```

`ExecutionUnit(step, role: PathRole, artifact_kind: ArtifactKind | None, ordinal: int | None)` 用于 preview。

## 10. library_root 安全（冻结）

* `library_root` 必须**预先存在**。P4-C7 永远不创建它，也不创建它的任何祖先。
* 预检：`lstat(library_root)`：
  * 不存在 / 路径经过文件 -> `LIBRARY_ROOT_MISSING`；
  * 不是目录 -> `LIBRARY_ROOT_NOT_DIRECTORY`；
  * 是 symlink（`S_ISLNK`）或 Windows reparse point（`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`，
    包括 junction）-> `LIBRARY_ROOT_IS_LINK`；
  * 其他 `OSError` -> `LIBRARY_ROOT_INACCESSIBLE`（带 `errno`）；
  * `st_ino == 0` -> `IDENTITY_UNAVAILABLE`。
* 理由（fail closed）：快照记录的是 `lstat` 身份；如果根本身是链接，快照只能看到链接自身，链接目标被替换
  无法检测。因此链接形式的根被拒绝。`library_root` 的**祖先**组件不做链接检查（例如 macOS 的 `/var`）；
  这属于第 25 节声明的边界。
* 在 `mkdir` 之前立即重新校验 `library_root` 的身份（`LIBRARY_ROOT_CHANGED`）。

## 11. 源身份快照（冻结）

* `lstat(source_path)`（从不跟随链接）：
  * 不存在 -> `SOURCE_MISSING`；
  * symlink 或 reparse point -> `SOURCE_IS_LINK`；
  * 不是普通文件 -> `SOURCE_NOT_REGULAR_FILE`；
  * `st_size != plan.source_size` -> `SOURCE_SIZE_MISMATCH`（发现与执行之间文件发生了变化）；
  * 其他 `OSError` -> `SOURCE_INACCESSIBLE`；
  * `st_ino == 0` -> `IDENTITY_UNAVAILABLE`。
* 快照 `EntryIdentity(device, inode, FILE, size, mtime_ns)` 写入 preflight 与 checkpoint。
* 源父目录不做链接检查；源路径的所有者由 P4-C1 发现结果给出（P4-C1-R-02..R-05 仍然 CARRIED，
  P4-C7 通过重新校验而不是信任发现结果来中和“发现结果过期”的风险）。

## 12. EntryIdentity 与比较（冻结）

```python
class EntryType(Enum):
    FILE = "file"
    DIRECTORY = "directory"

@dataclass(frozen=True, slots=True)
class EntryIdentity:
    device: int          # st_dev
    inode: int           # st_ino
    entry_type: EntryType
    size: int | None     # 仅 FILE：st_size
    mtime_ns: int | None # 仅 FILE：st_mtime_ns
```

* 文件：五个字段全部相等才算“未变化”。
* 目录：只比较 `device`、`inode`、`entry_type`（向目录中添加条目会改变目录的 size / mtime）。
* `lstat` 得到的条目若是链接或 reparse point，永远不构成合法身份（直接判为变化）。
* 不比较 `st_nlink`、`st_ctime`、`st_atime`（POSIX `link` 会改变 nlink / ctime；读取会改变 atime）。

## 13. Fresh execution 语义（冻结）

* 没有 checkpoint 时，`target_directory` 必须**不存在**：对它 `lstat` 得到 `FileNotFoundError`。
  任何已存在条目（文件、目录、**空目录**、symlink、悬空 symlink、junction）-> `TARGET_DIRECTORY_EXISTS`。
  P4-C7 从不“接管”已有目录，也从不从磁盘内容推测“以前做过一部分”。
* `lstat(target_directory)` 的非 `FileNotFoundError` 错误 -> `TARGET_DIRECTORY_INACCESSIBLE`。
  其中 `NotADirectoryError`（路径中某个组件是文件）归入 `LIBRARY_ROOT_NOT_DIRECTORY`。
* 预检不检查目标目录的子路径：目录不存在即意味着子路径不存在。

## 14. Retry / Checkpoint 语义（冻结）

### 14.1 只有进程内、不可变的 checkpoint

* checkpoint 只由 `execute_filesystem` 在 `PARTIAL` 结果中签发。
* 没有持久化、没有 JSON / pickle resume、没有磁盘上的状态文件、没有从磁盘猜测历史完成状态。
  进程退出后，checkpoint 失效；之后的执行只能是 fresh execution，而它会因目标目录已存在而被阻断
  （fail closed；人工处理属于 P4-C8 报告范围）。
* checkpoint 是 frozen、`slots=True` 的 dataclass，只含内置类型、枚举与本 package 的值模型。

### 14.2 checkpoint 字段（冻结）

```text
checkpoint_id                  : str   32 位小写 hex（secrets.token_hex(16)）
plan_fingerprint               : str   64 位小写 hex
manifest_fingerprint           : str   64 位小写 hex
library_root_identity          : EntryIdentity (DIRECTORY)
source_identity                : EntryIdentity (FILE)       源快照（fresh preflight 时采集）
transfer_mode                  : TransferMode               实际使用的传输模式（未执行 U2 时为预测值）
target_directory_identity      : EntryIdentity (DIRECTORY)
extrafanart_directory_identity : EntryIdentity | None
completed_effects              : tuple[CompletedEffect, ...]  E 的前缀
leftover_temporaries           : tuple[LeftoverTemporary, ...]
seal                           : str   64 位小写 hex HMAC；不出现在 repr 中
```

`CompletedEffect(kind, role: PathRole, path: str, identity: EntryIdentity | None, size: int | None,
sha256: str | None, artifact_kind: ArtifactKind | None, ordinal: int | None)`：
`SOURCE_REMOVED` 的 `identity` 为 `None`；媒体的 `sha256` 仅在跨卷复制时存在；artifact 的 `sha256`
总是存在。

`LeftoverTemporary(directory_role: PathRole, name: str)`：`name` 必须匹配 `^\.fc2tmp-[0-9a-f]{32}\.part$`。

### 14.3 checkpoint 验证（`preflight_execution(..., checkpoint=cp)`）

契约层（抛出 `CheckpointError(reason)`，零文件系统访问）：

1. 严格类型（第 5 节）。
2. `seal` 用本进程密钥重新计算并用 `hmac.compare_digest` 比较（`SEAL_INVALID`）——伪造、字段被
   `object.__setattr__` 改写、来自其他进程的 checkpoint 全部被拒绝。
3. `checkpoint_id` 未被消费（`CONSUMED`，第 15.4 节）。
4. `plan_fingerprint` 等于当前 plan 的指纹（`PLAN_MISMATCH`）。
5. `manifest_fingerprint` 等于当前 manifest 的指纹（`MANIFEST_MISMATCH`）——resume 时换了 artifact
   （哪怕只换了一个字节）一律拒绝。
6. `completed_effects` 是 `E(plan, manifest)` 的前缀，且每个 effect 的 `path` / `role` / `artifact_kind` /
   `ordinal` 与 `E` 的对应位置一致（`EFFECTS_NOT_PREFIX`）。
7. `completed_effects` 不等于完整的 `E`（`ALREADY_COMPLETE`；已完成的影片不再执行）。

文件系统层（只读；结果为 `PreflightBlocker`，不抛异常）：

* `library_root` 身份等于 `library_root_identity`（`LIBRARY_ROOT_CHANGED`）。
* `target_directory`：存在、是目录、不是链接、身份相等（`TARGET_DIRECTORY_CHANGED`）。
* 列举 `target_directory` 的条目名：必须**恰好**等于“已完成 effect 在该目录中的名称”∪
  “该目录的 leftover 临时文件名”（Windows `casefold`）。多出 -> `UNEXPECTED_ENTRY`；缺少 ->
  `COMPLETED_EFFECT_MISSING`。
* 若 `EXTRAFANART_DIRECTORY_CREATED` 已完成：对 `extrafanart_directory` 做同样的身份与列举检查。
* 每个已完成的文件 effect：`lstat` 身份与记录相等（`COMPLETED_EFFECT_CHANGED`）。
  * artifact：额外以只读方式重新读取全部内容并计算 SHA-256，必须等于记录值与 manifest 中的内容
    hash（`COMPLETED_EFFECT_CHANGED`）。artifact 很小（受 P4-C5 上限约束），重新读取的成本可接受。
  * 媒体：只比较身份（device、inode、size、mtime_ns），**不**重新 hash（媒体可达数十 GB）。
* 源：
  * `MEDIA_PUBLISHED` 未完成：源身份必须等于 `source_identity`（`SOURCE_CHANGED` / `SOURCE_MISSING`）。
  * `MEDIA_PUBLISHED` 已完成、`SOURCE_REMOVED` 未完成：源身份必须仍等于 `source_identity`；
    若源已不存在 -> `SOURCE_MISSING`（P4-C7 没有删除它，因此不会记录一个虚假的 `SOURCE_REMOVED`；
    fail closed，交由 P4-C8 报告）。
  * `SOURCE_REMOVED` 已完成：不检查源路径；该路径上出现的任何新东西都不属于本执行，永不触碰。

### 14.4 已完成 effect 的重试

* 已完成的 effect **永不重做、永不覆盖、永不删除**：只校验（第 14.3 节），然后跳过。
* 待执行单元从第一个未完成 effect 开始，按第 9 节顺序继续。
* `MEDIA_PUBLISHED` 已完成而 `SOURCE_REMOVED` 未完成时，resume 只执行“源路径重新校验 -> unlink 源”
  （POSIX 同卷模式下先对目标目录 `fsync`，第 18.3 节）。
* 遗留临时文件在 resume 中被容忍（列举检查中视为已知条目），**永不**被自动删除；它们继续出现在新
  checkpoint 与结果的 `leftover_temporaries` 中。

### 14.5 checkpoint 的签发

每次 `PARTIAL` 结果都签发一个新的 checkpoint（新 `checkpoint_id`、新 `seal`），其
`completed_effects` 是本次结束时的累计前缀（包括输入 checkpoint 中的 effect）。输入 checkpoint 在
`execute_filesystem` 开始时即被消费（第 15.4 节），此后只能使用新 checkpoint。

## 15. 指纹、封印与消费（冻结）

### 15.1 plan 指纹

`plan_fingerprint` = SHA-256（第 15.2 节编码）覆盖：域分隔符 `"fc2-organizer/p4-c7/plan/v1"`、
五个 `source_*` 字段、`canonical_number`、`library_root`、七个路径字段的 `absolute_path`、
七个操作的 `(kind.value, target, source)`。

### 15.2 规范编码

每个值编码为：一个类型标签字节 + 8 字节大端长度 + 内容字节。`str` 以
`value.encode("utf-8", "surrogatepass")` 编码（POSIX 上以 `surrogateescape` 解码的文件名也可稳定编码），
`int` 以十进制 ASCII 编码，`None` 为零长度的专用标签。编码是单射的（长度前缀），不依赖 `repr` / `hash()`。

### 15.3 封印

* 本进程在 `seal.py` 模块导入时生成一次 32 字节密钥：`secrets.token_bytes(32)`，从不导出、从不记录、
  从不写入任何模型或错误消息。
* `ExecutionPreflight.seal` 与 `ExecutionCheckpoint.seal` = `hmac.new(key, 规范编码(除 seal 外全部字段),
  sha256).hexdigest()`。
* 验证使用 `hmac.compare_digest`。任何字段被改写、对象被伪造、或来自其他进程，都会导致封印不匹配。
* `seal` 字段 `repr=False`。

### 15.4 一次性消费

* 进程内注册表：一个 `set[str]`，由一个 `threading.Lock` 保护。
* `execute_filesystem(preflight)` 在任何文件系统访问之前，在锁内原子地检查并登记 `preflight_id`；
  若 preflight 带有 checkpoint，同样登记 `checkpoint_id`。已登记 -> `PreflightIntegrityError(CONSUMED)`
  或 `CheckpointError(CONSUMED)`。
* `preflight_execution` 本身不消费任何东西（P4-C8 preview 可以多次 preflight，不影响之后的执行），
  但它会拒绝已经被消费的 checkpoint。
* 同一个 preflight 被两个线程并发执行：恰好一个进入执行，另一个在零文件系统访问的情况下被拒绝。

### 15.5 execute 前的完整性检查

`execute_filesystem` 在任何文件系统访问之前：验证 preflight 封印（`SEAL_INVALID`）；
`preflight.ready is True`（否则 `PreflightNotReadyError`，不消费、不访问文件系统）；对 `preflight.plan` /
`preflight.artifacts` 重新执行第 6、7 节验证并重新计算两个指纹，必须等于 preflight 中封存的值
（`FINGERPRINT_MISMATCH`）；以上全部通过之后才登记消费（第 15.4 节）。被拒绝的 preflight 不会被消费。

检查顺序（冻结）：严格类型 -> 封印 -> `ready` -> 结构重新验证与指纹 -> 消费登记 -> 文件系统。

## 16. ExecutionPreflight（冻结）

```text
preflight_id           : str   32 位小写 hex
mode                   : PreflightMode   FRESH | RESUME
plan                   : OrganizePlan    输入对象本身（执行前重新验证 + 指纹比较）
artifacts              : tuple[ArtifactWriteRequest, ...]
checkpoint             : ExecutionCheckpoint | None
plan_fingerprint       : str
manifest_fingerprint   : str
ready                  : bool            iff blockers == ()
blockers               : tuple[PreflightBlocker, ...]
library_root_identity  : EntryIdentity | None
source_identity        : EntryIdentity | None
transfer_mode          : TransferMode | None   预测值（第 17 节）；U2 已完成时为 checkpoint 中的实际值
completed_units        : tuple[ExecutionUnit, ...]
pending_units          : tuple[ExecutionUnit, ...]
skipped_steps          : tuple[ExecutionStep, ...]
seal                   : str（repr=False）
```

* 结构 / 类型 / 伪造 / checkpoint 契约问题 -> **抛异常**（调用方 bug 或篡改，不是可预览的状态）。
* 文件系统状态问题 -> **返回** `ready=False` 的 preflight，`blockers` 按固定检查顺序列出**全部**可检测到的
  阻断原因（不在第一个处停止），使 P4-C8 preview 能一次显示所有问题。检查顺序：library_root -> 源 ->
  目标目录（fresh）/ checkpoint 状态（resume）。依赖关系：library_root 不可用时，不再检查目标目录
  （其结果无意义），但仍检查源。
* `PreflightBlocker(reason: PreflightBlockReason, role: PathRole, errno: int | None, ordinal: int | None)`：
  不含路径字符串、`OSError` 文本或异常对象（调用方持有 plan，可自行映射 role -> 路径）。

```python
class PreflightMode(Enum):
    FRESH = "fresh"
    RESUME = "resume"

class PathRole(Enum):
    LIBRARY_ROOT = "library_root"
    SOURCE = "source"
    TARGET_DIRECTORY = "target_directory"
    TARGET_MEDIA = "target_media"
    NFO = "nfo"
    POSTER = "poster"
    FANART = "fanart"
    THUMB = "thumb"
    EXTRAFANART_DIRECTORY = "extrafanart_directory"
    EXTRAFANART_FILE = "extrafanart_file"

class PreflightBlockReason(Enum):
    LIBRARY_ROOT_MISSING = "library_root_missing"
    LIBRARY_ROOT_NOT_DIRECTORY = "library_root_not_directory"
    LIBRARY_ROOT_IS_LINK = "library_root_is_link"
    LIBRARY_ROOT_INACCESSIBLE = "library_root_inaccessible"
    LIBRARY_ROOT_CHANGED = "library_root_changed"
    SOURCE_MISSING = "source_missing"
    SOURCE_IS_LINK = "source_is_link"
    SOURCE_NOT_REGULAR_FILE = "source_not_regular_file"
    SOURCE_SIZE_MISMATCH = "source_size_mismatch"
    SOURCE_INACCESSIBLE = "source_inaccessible"
    SOURCE_CHANGED = "source_changed"
    TARGET_DIRECTORY_EXISTS = "target_directory_exists"
    TARGET_DIRECTORY_INACCESSIBLE = "target_directory_inaccessible"
    TARGET_DIRECTORY_CHANGED = "target_directory_changed"
    UNEXPECTED_ENTRY = "unexpected_entry"
    COMPLETED_EFFECT_MISSING = "completed_effect_missing"
    COMPLETED_EFFECT_CHANGED = "completed_effect_changed"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
```

## 17. 传输模式判定（冻结）

```python
class TransferMode(Enum):
    SAME_VOLUME = "same_volume"
    CROSS_VOLUME = "cross_volume"
```

* 预测：`source_identity.device == library_root_identity.device` -> `SAME_VOLUME`，否则 `CROSS_VOLUME`。
* 执行时，在 U1 之后以新建目标目录的 `st_dev` 再判定一次（覆盖 `library_root` 本身是挂载点等情况）；
  以执行时判定为准。
* `SAME_VOLUME` 原语以 `EXDEV` 失败（此时没有任何 effect）-> 回退到跨卷流程一次，结果中
  `transfer_mode = CROSS_VOLUME`。这是唯一的回退；其他任何错误都不回退。
* `CROSS_VOLUME` 从不尝试 `rename` / `link` 源文件。

## 18. 同卷媒体移动（冻结）

### 18.1 公共前置

U2 开始时：重新校验目标目录身份（`TARGET_DIRECTORY_CHANGED`）、`lstat(target_media_path)` 必须不存在
（`TARGET_CONFLICT`）、重新校验源身份（`SOURCE_CHANGED` / `SOURCE_MISSING`）。这些检查只是提前退出；
不覆盖保证来自原语本身。

### 18.2 Windows（`os.name == "nt"`）

```text
os.rename(source_path, target_media_path)   # MoveFileExW，无 MOVEFILE_REPLACE_EXISTING、无 MOVEFILE_COPY_ALLOWED
```

* 目标已存在（任何条目）-> `FileExistsError` -> `TARGET_CONFLICT`，无 effect。
  其他错误时若 `lstat(target)` 显示已有条目，同样归类为 `TARGET_CONFLICT`（沿用 P4-C6 第 7 节的分类规则）。
* `EXDEV`（`ERROR_NOT_SAME_DEVICE`）-> 回退跨卷（第 17 节）。
* 其他 `OSError`（共享冲突、权限等）-> `MEDIA_TRANSFER_FAILED(errno)`，无 effect。
* 成功：同一个原子操作同时产生 `MEDIA_PUBLISHED` 与 `SOURCE_REMOVED`。随后 `lstat(target)` 必须等于源快照
  （device、inode、size、mtime_ns；rename 保留文件 ID）；不等 -> `PUBLISHED_MEDIA_MISMATCH`
  （`PARTIAL`，不回滚：P4-C7 移动的是那一刻位于源路径上的条目，没有删除任何东西）。
* 不使用 `os.replace`，也不使用可覆盖的 `MoveFileEx` 标志。

### 18.3 POSIX

```text
os.link(source_path, target_media_path)     # link(2)：目标存在时 EEXIST，从不跟随目标
lstat(target) 身份 == 源快照               -> MEDIA_PUBLISHED
fsync(target_directory 的目录 fd)          # 使新名称持久化后再移除旧名称
lstat(source) 身份 == 源快照               # 源路径重新校验
os.unlink(source_path)                      -> SOURCE_REMOVED
```

* **从不**使用可覆盖的 POSIX `rename(2)`。
* `link` 失败：`EEXIST` -> `TARGET_CONFLICT`；`EXDEV` -> 回退跨卷；其他 errno（包括不支持 hard link 的
  `EPERM` / `ENOTSUP` / `EOPNOTSUPP` / `EMLINK`）-> `MEDIA_TRANSFER_FAILED`，无 effect。不回退到 `rename`，
  与 P4-C6 在不支持 hard link 的文件系统上 fail closed 的冻结边界一致（这类目标卷上 artifact 发布本来也会失败）。
* `link` 之后目标身份不等于源快照 -> `PUBLISHED_MEDIA_MISMATCH`（`PARTIAL`；源不删除）。
* 目录 `fsync` 失败 -> `TARGET_DIRECTORY_FSYNC_FAILED`（`PARTIAL`；最终媒体保留，源保留；resume 时重做
  `fsync` 再删源）。
* 删源前源身份不等 / 源不存在 -> `SOURCE_CHANGED` / `SOURCE_MISSING`（`PARTIAL`；最终媒体保留，
  源路径上的条目**不**删除）。
* `unlink` 失败 -> `SOURCE_UNLINK_FAILED`（`PARTIAL`；最终保留，源保留，两者是同一 inode 的两个名称，
  不存在数据丢失）。

## 19. 跨卷媒体复制（冻结）

```text
1  fd_src = open(source_path, O_RDONLY | O_BINARY | O_NOINHERIT | O_CLOEXEC | O_NOFOLLOW*)
   fstat(fd_src) 身份 == 源快照                                   (* 仅 POSIX 有 O_NOFOLLOW)
2  在 target_directory 中独占创建同级临时文件
   .fc2tmp-<secrets.token_hex(16)>.part，O_WRONLY|O_CREAT|O_EXCL(+O_BINARY/O_NOINHERIT/O_CLOEXEC)，
   从不 O_TRUNC，mode 0o666（受 umask 影响），名称冲突换 token，最多 8 次
3  流式复制：每次 read 至多 1 MiB，写满为止（短写入续写；零字节写入 = EIO）
4  复制过程中对读到的字节计算 SHA-256；读到的总字节数超过快照 size 立即中止
5  EOF 时总字节数必须 == 快照 size；fsync(temp)；fstat(temp) 记录 inode；close(temp)
6  源 fd 重新校验：fstat(fd_src) 身份 == 源快照；close(fd_src)
7  无覆盖发布：Windows os.rename(temp, final)；POSIX os.link(temp, final) + unlink(temp)
   发布后 lstat(final)：普通文件、非链接、size == 快照 size、inode == 第 5 步记录的 temp inode
                                                                      -> MEDIA_PUBLISHED
8  POSIX：fsync(target_directory 目录 fd)
9  源路径重新校验：lstat(source_path) 身份 == 源快照
10 unlink(source_path)                                                -> SOURCE_REMOVED
```

* 只有在第 7 步最终目标**完整发布**之后，才可能删除源（第 10 步）。
* 第 1-6 步的任何失败：关闭仍打开的 fd，对**确切的**本次临时路径 unlink 一次；源完好；无媒体 effect。
  临时文件清理失败 -> 失败类型为原失败，同时在 `leftover_temporaries` 中记录该名称（此时 P4-C7 知道确切名称）。
* 第 7 步发布失败：目标已存在 -> `TARGET_CONFLICT`；其他 -> `MEDIA_PUBLISH_FAILED(errno)`；清理本次临时文件；
  源完好。
* POSIX 第 7 步 `link` 成功而 `unlink(temp)` 失败 -> 最终媒体已完整发布：记录 `MEDIA_PUBLISHED`，
  记录遗留临时名称，失败类型 `MEDIA_TEMP_CLEANUP_FAILED`（`PARTIAL`，源保留，resume 继续删源）。
* 发布后校验失败 -> `PUBLISHED_MEDIA_MISMATCH`（`PARTIAL`；源保留）。
* 第 9 步源身份不等 / 不存在 -> `SOURCE_CHANGED` / `SOURCE_MISSING`（`PARTIAL`；最终保留；源路径上的条目不删除）。
* 第 10 步 `unlink` 失败 -> `SOURCE_UNLINK_FAILED`：**最终保留、源保留、状态 PARTIAL**；
  **禁止**回滚（不删除最终媒体）。
* 结果记录 `media_sha256`（第 4 步的值）与 `media_size`。发布后不重新读取临时 / 最终文件做第二次 hash
  （避免对大文件加倍 I/O）；完整性由“同一批缓冲区既参与 hash 又被写入 + 大小相等 + fsync”保证。
* 没有空间预检：`ENOSPC` 在第 3 步表现为 `MEDIA_WRITE_FAILED`，清理临时文件，源完好。
* 零字节源：合法；第 3 步不写入任何字节，SHA-256 为空串的 hash。

`TransferStage`（冻结，用于 `ExecutionFailure.stage`）：

```text
SOURCE_OPEN, SOURCE_FD_VALIDATE, TEMP_CREATE, READ, WRITE, FSYNC, CLOSE,
SOURCE_FD_REVALIDATE, PUBLISH, PUBLISH_VERIFY, TEMP_CLEANUP, DIRECTORY_FSYNC,
SOURCE_PATH_REVALIDATE, SOURCE_UNLINK, SAME_VOLUME_PRIMITIVE
```

## 20. 临时文件所有权（冻结）

* P4-C7 只拥有它自己在第 19 节第 2 步独占创建的那一个临时路径；所有权在 Windows rename 消耗它、或在
  POSIX 发布后唯一一次 unlink 尝试之后结束。
* 失败时（包括 `BaseException`）：关闭 fd，若仍拥有，则对**确切路径** unlink 一次。
* 永不：基于 glob / 通配 / 目录列举删除任何东西；删除其他 `.fc2tmp-*` / `.part` / `.tmp` 文件（包括
  P4-C6 在 artifact 失败中遗留的临时文件、之前运行的遗留、用户或其他进程植入的文件）；删除任何目录；
  删除或修改任何最终目标。
* artifact 的临时文件由 P4-C6 原语拥有与清理（P4-C6 合同第 8-10 节）。当 `materialize_artifact` 以
  `ArtifactCleanupError` 失败时，P4-C7 列举该 artifact 的父目录，把“执行前不存在、且匹配临时文件名模式”的
  新条目记录为 `LeftoverTemporary`（该目录是本执行独占创建的，因此新出现的临时文件名可归属于本次失败）；
  这些条目永不被 P4-C7 删除。

## 21. 目标目录所有权（冻结）

* U1：`os.mkdir(target_directory, 0o777)`（受 umask 影响）——**独占**：已存在即 `FileExistsError`。
  从不 `makedirs`、从不 `parents=True`、从不 `exist_ok=True`。
* 执行前：`lstat(library_root)` 身份重新校验；`lstat(target_directory)` 必须不存在。
* `mkdir` 失败：`FileExistsError` -> `TARGET_CONFLICT`（`FAILED`：没有任何 effect，那个目录不是本执行创建的，
  永不触碰）；`FileNotFoundError` / `NotADirectoryError` -> `LIBRARY_ROOT_CHANGED`；其他 ->
  `DIRECTORY_CREATE_FAILED(errno)`。
* 成功后立即 `lstat(target_directory)`：必须是目录、非链接；记录 `target_directory_identity`，effect
  `TARGET_DIRECTORY_CREATED`。若快照不合法（例如在 mkdir 与 lstat 之间被替换为 junction）->
  `TARGET_DIRECTORY_CHANGED`，状态 `PARTIAL`（mkdir 已成功，effect 已发生）。
* 之后每个写入目标目录的单元（U2-U7）在修改前重新校验目标目录身份。
* 本执行“拥有”目标目录的含义仅是：它是由本执行的独占 mkdir 创建的，其条目集合受第 14.3 节列举检查约束。
  所有权**不**授予任何删除权限：P4-C7 从不删除目标目录或其中任何条目。

## 22. extrafanart 目录所有权（冻结）

* U7 在 U1-U6 之后执行，**即使 manifest 中没有 extrafanart 图片**。
* 修改前：重新校验目标目录身份；`lstat(extrafanart_directory)` 必须不存在（`TARGET_CONFLICT`）。
* `os.mkdir(extrafanart_directory, 0o777)` 独占创建；成功后 `lstat` 快照（目录、非链接），effect
  `EXTRAFANART_DIRECTORY_CREATED`。
* U8.. 每个 extrafanart 文件写入前重新校验 `extrafanart_directory` 身份。
* 与目标目录相同：所有权不授予删除权限。

## 23. Overwrite = NEVER（冻结；执行覆盖语义延续项在执行层实施）

* 目录：独占 `mkdir`。
* 媒体：Windows 无替换 rename；POSIX `link`；跨卷发布同样是无替换原语。
* artifact：只通过 `materialize_artifact`（P4-C6 原语，overwrite NEVER）。
* P4-C7 源码中不存在 `os.replace`、`shutil.*`、`O_TRUNC`、`truncate`、`chmod`、`utime`、`rmdir`、`rmtree`、
  `remove`、`removedirs`、`makedirs`（AST 强制）。
* 已存在的最终目标永远不会被覆盖、截断、替换、删除、重命名或加后缀；没有任何旋钮可以改变这一点。

## 24. Artifact 执行（冻结）

对每个 artifact 单元（U3-U6、U8..）：

1. 重新校验父目录（目标目录或 `extrafanart_directory`）身份（`TARGET_DIRECTORY_CHANGED`）。
2. `lstat(target)` 必须不存在（`TARGET_CONFLICT`；提前退出，保证来自原语）。
3. 调用 `materialize_artifact(request)`，其中 `request` 是 manifest 中的**原对象**（P4-C7 不复制、
   不重新编码、不改写内容）。
4. 成功：返回的 `MaterializedArtifact` 必须满足 `target_path == request.target_path`、
   `size_bytes == len(request.content)`、`sha256 == sha256(request.content)`；随后 `lstat(target)`：普通文件、
   非链接、size 相等 -> effect `ARTIFACT_PUBLISHED`（记录身份与 sha256）。任何不符 ->
   `PUBLISHED_ARTIFACT_MISMATCH`（`PARTIAL`）。
5. `MaterializationError` 映射（按异常类型，绝不按消息文本）：

| P4-C6 错误 | `ExecutionFailureKind` | effect |
|---|---|---|
| `TargetExistsError` | `TARGET_CONFLICT` | 无 |
| `ParentDirectoryError` 系列 | `TARGET_DIRECTORY_CHANGED` | 无 |
| `TargetInaccessibleError` | `ARTIFACT_TARGET_INACCESSIBLE` | 无 |
| `TemporaryCreateError` | `ARTIFACT_TEMP_CREATE_FAILED` | 无 |
| `ArtifactWriteError` | `ARTIFACT_WRITE_FAILED`（`stage` 记录 WRITE/FLUSH/CLOSE） | 无 |
| `ArtifactPublishError` | `ARTIFACT_PUBLISH_FAILED` | 无 |
| `ArtifactCleanupError(target_published=False)` | `ARTIFACT_CLEANUP_FAILED` | 无；记录遗留临时文件 |
| `ArtifactCleanupError(target_published=True)` | `ARTIFACT_CLEANUP_FAILED` | `ARTIFACT_PUBLISHED`（按第 4 步校验，且重新读取内容比较 sha256）；记录遗留临时文件 |
| `InvalidTargetPathError` / `MaterializationInputError` / `MaterializationModelError` | 不可能（manifest 已验证）；若出现 -> `ARTIFACT_PATH_REJECTED` | 无 |

6. 任何失败 -> 停止；已发布的 artifact 保留（无回滚）。

## 25. Filesystem TOCTOU 边界（冻结，诚实声明）

P4-C7 基于标准库的**字符串路径 API**（`os.lstat` / `os.mkdir` / `os.rename` / `os.link` / `os.unlink` /
`os.open`）。它不使用 `openat` / `dir_fd` 相对操作、句柄相对的 Windows API 或 `renameat2(RENAME_NOREPLACE)`
（标准库没有可移植的等价物，且会引入 `ctypes`）。因此：

* **快照 + 重新校验**显著降低了“计划过期”（stale plan）的风险：发现与执行之间源被修改 / 替换 / 删除、
  目标被他人占用、目录被替换为链接、checkpoint 之后磁盘被人工改动——这些在普通（非恶意）并发下都会被检测到并
  fail closed。
* 但是，P4-C7 **不能**声称能完全防御一个恶意的本地行为者：它可以在“重新校验”与紧随其后的修改 syscall
  之间（例如 `lstat(source)` 与 `unlink(source)` 之间，或目录身份检查与 `materialize_artifact` 之间）
  替换路径组件。这是基于字符串路径 API 的固有限制，不是缺陷，也不在 v1.0 的威胁模型内。
* 在上述窗口内，P4-C7 仍然保证：
  * **fail closed**：检测到的任何不一致都停止执行；
  * **no overwrite**：不覆盖保证来自无替换原语本身，而不是来自检查（第 23 节），因此即使在窗口内被植入条目，
    也不会被替换；
  * **no silent source loss**：源只会在“最终目标已完整存在并通过发布后校验”之后才被 unlink；Windows 同卷
    rename 是原子的；POSIX 同卷在 unlink 源之前最终名称已指向同一 inode；
  * **revalidate before mutation**：每个修改性 syscall 之前都有一次重新校验。
* 剩余风险（明确声明）：恶意行为者在 `lstat(source)` 与 `unlink(source)` 之间把源路径替换为另一个文件，
  可能导致那个替换文件被删除；恶意行为者在目录校验与写入之间把父目录替换为链接，可能导致 artifact 被写到别处
  （但仍然不覆盖任何已存在的文件）。

## 26. 平台规则（冻结）

### 26.1 Windows（`os.name == "nt"`）

* 同卷移动：`os.rename`（`MoveFileExW`，无替换、无复制）。跨卷判定：`st_dev`（卷序列号）。
* 链接判定：`S_ISLNK` 或 `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`（junction、symlink 以及任何其他
  reparse tag 一律视为链接）。不依赖 `os.path.isjunction`（3.12+）。
* 名称比较：`casefold`（重复目标、基名冲突、列举检查、源是否位于目标之下）。
* 没有目录 `fsync`（Windows 上 `os.open` 不能打开目录；NTFS 元数据有日志）。文件数据 `fsync` = `FlushFileBuffers`。
* 删除只读属性的源 / 被其他进程打开的源：`unlink` 可能以 `PermissionError` 失败 -> `SOURCE_UNLINK_FAILED`；
  P4-C7 从不 `chmod`、从不强制关闭句柄。
* 不添加 `\\?\` 前缀（P4-C6 拒绝设备命名空间）；超过 `MAX_PATH` 且系统未启用长路径时，相应 syscall 的
  `OSError` 被归类为类型化失败。
* 被打开的源在同卷 rename 时出现共享冲突 -> `MEDIA_TRANSFER_FAILED`，无 effect。

### 26.2 POSIX

* 同卷移动：`os.link` + 校验 + 目录 `fsync` + `os.unlink`；从不 `rename(2)`。
* 源打开使用 `O_NOFOLLOW`；链接判定 `S_ISLNK`。
* 名称比较：精确（区分大小写）。
* 在发布之后、删除源之前，对目标目录 `fsync`（`os.open(dir, O_RDONLY | O_DIRECTORY)`）。
* 不支持 hard link 的目标文件系统：fail closed（第 18.3 节），与 P4-C6 一致。

### 26.3 词法校验（`execution/paths.py`，纯函数）

对 P4-C7 触碰的每个路径：`EMPTY`、`NUL_CHARACTER`、`NOT_ABSOLUTE`（Windows：盘符 + 根，或 UNC
`\\server\share` 且 server、share 都非空；POSIX：`isabs`）、`DEVICE_NAMESPACE`（`\\?\`、`\\.\`）、
`DOT_SEGMENT`、`NO_BASENAME`；Windows 另有 `ILLEGAL_CHARACTER`、`TRAILING_DOT_OR_SPACE`、`RESERVED_NAME`。

对 P4-C7 **创建**的每个组件（目标目录名、媒体 basename、extrafanart 目录名、每个 artifact basename），
在两个平台上都额外应用 Windows 组件规则与**扩展保留名**（中和延续项“扩展的 Windows 保留名”）：
`CON`、`PRN`、`AUX`、`NUL`、`COM1`-`COM9`、`LPT1`-`LPT9`、`COM¹`、`COM²`、`COM³`、`LPT¹`、`LPT²`、`LPT³`、
`CONIN$`、`CONOUT$`，按第一个点之前的部分、不区分大小写判断。默认 v1.0 布局永远不会触发（回归测试）。
该延续项作为 planning package 的 finding 仍然 CARRIED；P4-C7 只在执行边界 fail closed。

## 27. 类型化失败词汇（冻结）

```python
@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    step: ExecutionStep
    kind: ExecutionFailureKind
    stage: TransferStage | None
    write_stage: str | None          # 仅 ARTIFACT_WRITE_FAILED："write" | "flush" | "close"
    errno: int | None
    artifact_kind: ArtifactKind | None
    ordinal: int | None
    target_published: bool | None    # 仅 ARTIFACT_CLEANUP_FAILED / MEDIA_TEMP_CLEANUP_FAILED
```

```python
class ExecutionFailureKind(Enum):
    # 重新校验
    LIBRARY_ROOT_CHANGED = "library_root_changed"
    SOURCE_CHANGED = "source_changed"
    SOURCE_MISSING = "source_missing"
    TARGET_DIRECTORY_CHANGED = "target_directory_changed"
    UNEXPECTED_ENTRY = "unexpected_entry"
    TARGET_CONFLICT = "target_conflict"
    # 目录
    DIRECTORY_CREATE_FAILED = "directory_create_failed"
    # 媒体
    MEDIA_TRANSFER_FAILED = "media_transfer_failed"
    MEDIA_SOURCE_OPEN_FAILED = "media_source_open_failed"
    MEDIA_READ_FAILED = "media_read_failed"
    MEDIA_TEMP_CREATE_FAILED = "media_temp_create_failed"
    MEDIA_WRITE_FAILED = "media_write_failed"
    MEDIA_FSYNC_FAILED = "media_fsync_failed"
    MEDIA_CLOSE_FAILED = "media_close_failed"
    SOURCE_CHANGED_DURING_COPY = "source_changed_during_copy"
    MEDIA_PUBLISH_FAILED = "media_publish_failed"
    MEDIA_TEMP_CLEANUP_FAILED = "media_temp_cleanup_failed"
    PUBLISHED_MEDIA_MISMATCH = "published_media_mismatch"
    TARGET_DIRECTORY_FSYNC_FAILED = "target_directory_fsync_failed"
    SOURCE_UNLINK_FAILED = "source_unlink_failed"
    # artifact
    ARTIFACT_TARGET_INACCESSIBLE = "artifact_target_inaccessible"
    ARTIFACT_TEMP_CREATE_FAILED = "artifact_temp_create_failed"
    ARTIFACT_WRITE_FAILED = "artifact_write_failed"
    ARTIFACT_PUBLISH_FAILED = "artifact_publish_failed"
    ARTIFACT_CLEANUP_FAILED = "artifact_cleanup_failed"
    ARTIFACT_PATH_REJECTED = "artifact_path_rejected"
    PUBLISHED_ARTIFACT_MISMATCH = "published_artifact_mismatch"
```

`ExecutionResult`（冻结）：

```text
status                : ExecutionStatus
preflight_id          : str
mode                  : PreflightMode
transfer_mode         : TransferMode | None     U2 实际执行时的模式
completed_effects     : tuple[CompletedEffect, ...]   累计（含输入 checkpoint 的 effect）
new_effect_count      : int                            本次调用新增的 effect 数
failure               : ExecutionFailure | None        iff status != SUCCESS
checkpoint            : ExecutionCheckpoint | None     iff status is PARTIAL
leftover_temporaries  : tuple[LeftoverTemporary, ...]
media_sha256          : str | None                     仅跨卷复制
skipped_steps         : tuple[ExecutionStep, ...]
```

模型层不变量（`ExecutionModelError`）：严格类型、`status` 与 `failure` / `checkpoint` 的对应关系、
`FAILED` 时 `completed_effects == ()`、`SUCCESS` 时 effect 序列完整（由执行器保证，模型只检查非空）。

错误层次（冻结，`errors.py`）：

```text
ExecutionError(Exception)
+-- ExecutionInputError(ExecutionError, TypeError)
+-- ExecutionModelError(ExecutionError, ValueError)
+-- ExecutionContractError(ExecutionError, ValueError)
|   +-- PlanGraphError                     .reason: PlanGraphRejectionReason
|   +-- ArtifactManifestError              .reason: ManifestRejectionReason
|   +-- CheckpointError                    .reason: CheckpointRejectionReason
|   '-- PreflightIntegrityError            .reason: PreflightIntegrityReason
'-- PreflightNotReadyError(ExecutionError)
```

```text
PlanGraphRejectionReason : PLAN_RECONSTRUCTION_FAILED, FIELD_TYPE, PATH_TYPE, OPERATIONS_NOT_TUPLE,
                           OPERATION_COUNT, OPERATION_TYPE, OPERATION_KIND_ORDER, OPERATION_TARGET_MISMATCH,
                           OPERATION_SOURCE_MISMATCH, TARGET_DIRECTORY_LAYOUT, MEDIA_NAME_MISMATCH,
                           NFO_NAME_INVALID, ARTIFACT_LAYOUT, BASENAME_COLLISION, UNSAFE_COMPONENT,
                           SOURCE_PATH_REJECTED, SOURCE_EXTENSION_MISMATCH, SOURCE_INSIDE_TARGET,
                           TARGET_PATH_REJECTED, LIBRARY_ROOT_REJECTED
ManifestRejectionReason  : REQUEST_TYPE, REQUEST_INVALID, EMPTY_CONTENT, NFO_MISSING, NFO_NOT_FIRST,
                           DUPLICATE_KIND, ORDER, TARGET_MISMATCH, EXTRAFANART_NAME_MISMATCH,
                           EXTRAFANART_ORDINAL_SEQUENCE, DUPLICATE_TARGET
CheckpointRejectionReason: SEAL_INVALID, CONSUMED, PLAN_MISMATCH, MANIFEST_MISMATCH,
                           EFFECTS_NOT_PREFIX, ALREADY_COMPLETE
PreflightIntegrityReason : SEAL_INVALID, CONSUMED, FINGERPRINT_MISMATCH
```

错误消息只含固定措辞与枚举值：不含路径、临时 token、内容字节、`OSError` 文本、密钥或封印。
类型化错误在任何 `except` 块之外抛出，不以 `OSError` 作为 `__cause__` / `__context__`（沿用 P4-C6 第 11 节）。
`ExecutionFailure` / `PreflightBlocker` 同样只携带枚举与 `errno`。

## 28. No Rollback（冻结）

* 整个 P4-C7 是 **forward-only**。已成功的目录、媒体、artifact、源删除，**永不**因后续失败被自动删除、
  移回或恢复。
* 部分状态由 `PARTIAL` + checkpoint 表达；恢复由 resume 向前推进完成。
* 源代码中不存在 `rollback`、`undo`、`revert`、`transaction`、`cleanup_all` 之类的函数（AST 强制）。
* 唯一的删除动作：本次调用拥有的确切临时路径（失败清理 / POSIX 发布后）、以及“已完整发布并通过校验之后”的
  源媒体。

## 29. 取消与致命异常（冻结）

* 只有来自文件系统接缝的 `OSError` 与来自 `materialize_artifact` 的 `MaterializationError` 被翻译为
  类型化失败。
* `KeyboardInterrupt`、`SystemExit`、`GeneratorExit`、`asyncio.CancelledError`、任何其他 `BaseException`
  以及外来的 `Exception`（例如 `MemoryError`、`RuntimeError`）：关闭本次打开的 fd，若仍拥有临时文件则对确切路径
  unlink 一次（忽略清理错误），然后以**同一个对象**原样传播；清理失败永不掩盖它。不返回结果、不签发 checkpoint、
  不回滚。
* 在任何中断点上都成立的不变量（由第 18-19 节的顺序保证）：源媒体至少以一个完整副本存在于源路径或最终路径上。

| 中断点 | 磁盘状态 |
|---|---|
| U1 之前 | 无变化 |
| U1 之后、U2 之前 | 空目标目录 |
| 跨卷复制中 | 源完好；临时文件已尝试删除（可能遗留） |
| 跨卷发布之后、删源之前 | 源与最终都完整 |
| POSIX 同卷 link 之后、unlink 之前 | 同一 inode 的两个名称 |
| Windows 同卷 rename | 原子：要么源在，要么最终在 |
| artifact 写入中 | 由 P4-C6 保证：最终目标要么完整、要么不存在 |

* 中断后进程内没有 checkpoint：下一次 fresh preflight 会因 `TARGET_DIRECTORY_EXISTS` 被阻断（fail closed）。
  这是 v1.0 的明确边界：进程内 resume 只覆盖类型化失败。

## 30. 与 P4-C8 的接口（冻结）

* **preview** 只调用 `preflight_execution`，读取 `ready`、`blockers`、`mode`、`transfer_mode`、
  `pending_units`、`completed_units`、`skipped_steps`；preview 从不调用 `execute_filesystem`。
* **execution** 对每个 `ready` 的 preflight 调用一次 `execute_filesystem`。
* **retry** 携带 `ExecutionResult.checkpoint`：`preflight_execution(plan, artifacts, checkpoint)`，
  `plan` 与 `artifacts` 必须与原执行相同（指纹绑定）。
* manifest 由 P4-C8 通过已关闭的 `fc2_organizer.materialization.mapping.build_artifact_requests` 构建；
  P4-C7 不构建 manifest。
* P4-C7 是单影片执行器：它不调度、不并发、不去重。多个影片可以在不同线程中并发执行各自的 preflight
  （不同目标目录）；同一目标目录的竞争由独占 `mkdir` 决出唯一胜者，失败者得到 `TARGET_CONFLICT`
  （`FAILED`）或 preflight 阶段的 `TARGET_DIRECTORY_EXISTS`。

## 31. 测试总设计（冻结）

全部测试离线、只在 pytest `tmp_path` 下创建文件、不读取用户文件、不访问网络。失败注入通过私有接缝
`execution._fs._FS`（P4-C7 自己的 syscall）与 `materialization.atomic._FS`（artifact 路径）完成。
测试文件与分批见施工计划；此处冻结覆盖要求：

| 类别 | 必须覆盖 |
|---|---|
| graph forgery | 缺失 / 多余 / 重排 / kind 替换 / target 替换 / source 替换 / 子类操作 / 非 tuple / `object.__setattr__` 改写字段后的 plan / 目录不是 root 的直接子目录 / 媒体名不符 / NFO 名不符 / artifact 不在目标目录下 / 基名冲突 / 扩展保留名 / 源在目标之下 / 源扩展名不符 / 裸 `\\server` 根 |
| manifest forgery | 非 tuple / 子类请求 / 改写后的请求 / 空内容 / 无 NFO / 两个 NFO / NFO 不在首位 / 重复 POSTER / 顺序错误 / 目标不符 / extrafanart 序号从 0 或 2 开始、跳号、重复 / 名称不符 / 重复目标（含 Windows 大小写折叠）/ 与媒体或 extrafanart 目录同名 |
| optional images | 8 种 poster/fanart/thumb 组合 × extrafanart {0, 1, 13}；缺失图片不产生单元、不算失败、U7 总是执行 |
| 1000 extrafanart | 1000 张的 manifest 验证在内存中通过（`extrafanart-1000.jpg`）；执行层命名常量与 `mapping.extrafanart_filename` 对 1..10000 一致；S6 实际执行 1000 张 |
| source mutation | preflight 与 execute 之间：size 改变、mtime 改变、内容同尺寸改写、删除；复制过程中：追加字节、截断、mtime 改变 |
| source replacement | 同名新文件（不同 inode）、替换为 symlink / junction / 目录 |
| target conflict | preflight 前已存在（文件 / 空目录 / symlink / 悬空 symlink / junction）；preflight 后、执行前植入；U2-U8 每个目标在单元开始前植入；植入者字节 / inode / mtime 不变 |
| target replacement | 目标目录 / extrafanart 目录在单元之间被替换为 junction / symlink / 另一个目录 -> `TARGET_DIRECTORY_CHANGED` |
| directory symlink/reparse | library_root 为 junction / symlink -> 阻断；祖先链接不检查（声明）|
| same-target race | 两个 preflight 同一目标：barrier 强制两者都通过 preflight 后并发执行，恰好一个 `SUCCESS`，另一个 `FAILED(TARGET_CONFLICT)`，失败者零 effect；8 线程多轮不同步；两个线程执行同一个 preflight -> 恰好一个被 `CONSUMED` 拒绝 |
| same-volume move | Windows 原生 rename；POSIX link 策略（通过接缝在 NTFS 上执行 + 在真实 POSIX 主机上原生执行）；`EXDEV` 回退；共享冲突；发布后身份不符 |
| cross-volume copy | 通过 `_FS.device_of` 接缝强制 `CROSS_VOLUME`；可选真实跨卷（环境变量 `FC2_EXECUTION_CROSS_VOLUME_ROOT` 指向另一卷上的目录，否则 SKIP 并记录为证据缺口） |
| copy interruption | 读失败、写失败、在第 k 个块抛出 `KeyboardInterrupt`（同一对象传播、临时文件被删除、源完好） |
| short write | 短写入续写成功；零字节写入 -> `MEDIA_WRITE_FAILED(EIO)` |
| fsync failure | 临时文件 fsync 失败；POSIX 目录 fsync 失败（最终保留、源保留、resume 完成） |
| publish failure | 目标被抢占（`TARGET_CONFLICT`）、其他 errno；POSIX 临时文件 unlink 失败（`MEDIA_TEMP_CLEANUP_FAILED`，最终已发布）|
| source unlink failure | 最终保留、源保留、`PARTIAL`、resume 后 `SUCCESS` |
| unrelated temp preservation | 目标目录 / extrafanart 目录 / 源目录中植入的 `.fc2tmp-*.part`、`.part`、`.tmp` 在所有失败路径后字节不变（resume 时植入 -> `UNEXPECTED_ENTRY`，但仍不删除）|
| checkpoint mismatch | 伪造 checkpoint、`object.__setattr__` 改写、复制后二次使用、换 plan、换 manifest（单字节差异）、effect 非前缀、已完成 checkpoint、来自“其他进程”（重置密钥模拟）|
| resume after each partial point | 对 `E` 的每一个前缀长度 p（0 < p < |E|），在第 p+1 个 effect 处注入失败，得到 `PARTIAL`，然后 resume -> `SUCCESS`；最终布局与一次成功完全相同 |
| artifact mismatch on resume | 已完成 artifact 被改写 / 删除 / 替换 -> `COMPLETED_EFFECT_CHANGED` / `COMPLETED_EFFECT_MISSING`；resume 时 manifest 内容改变 -> `MANIFEST_MISMATCH` |
| unexpected directory entry | resume 前在目标目录 / extrafanart 目录中植入任何条目 -> `UNEXPECTED_ENTRY`；植入物不被触碰 |
| Unicode paths | CJK、假名、emoji、组合字符、NFC/NFD 两种形式的源路径与 library_root；Windows 大小写折叠冲突 |
| zero-byte media | 同卷与跨卷，`SUCCESS`，sha256 为空串 hash |
| large streamed media | 至少跨越 3 个 1 MiB 块的源（例如 3 MiB + 17 字节），sha256 精确；对 >= 64 MiB 的稀疏 / 生成文件做一次流式复制（内存峰值不随文件大小线性增长：按块断言）|
| Windows semantics | rename 无替换、reparse point 判定、`casefold` 列举、无目录 fsync、只读源 unlink 失败 |
| POSIX semantics | link 无替换、`O_NOFOLLOW`、目录 fsync 顺序（在 unlink 源之前）、区分大小写；在 Windows 主机上通过接缝模拟策略，在真实 POSIX 主机上原生执行（否则记录为证据缺口）|
| architecture | 第 3 节全部静态与运行时规则 |
| no-mutation of preflight | preflight 在全部接缝上零修改性调用（mkdir/rename/link/unlink/open-for-write 被拦截并断言零次）|

**核心不变量（每个失败注入测试都必须断言）：** 任何失败注入下，源视频不得被静默丢失——
在失败之后，源路径上存在与原始字节相同的文件，或者最终路径上存在与原始字节相同的文件（或两者都有）；
任何已存在的非本执行条目的字节、inode 与 mtime 不变。

### 31.1 500-item 集成文件系统门槛（S6）

`tests/unit/execution/test_execution_synthetic_gate.py`：

* 500 个确定性合成影片，全部位于 `tmp_path` 下：
  * 200 个同卷原生策略；100 个 POSIX link 策略（接缝）；150 个强制跨卷（接缝）；50 个故障 / 恢复用例。
  * 媒体大小覆盖 0 字节、1 字节、1 MiB - 1、1 MiB、1 MiB + 1、3 MiB + 17；Unicode 名称；多种扩展名大小写。
  * manifest 覆盖 8 种可选主图组合 × extrafanart 0..13；另有 1 个影片执行 1000 张 extrafanart。
* 期望值来自用例定义而不是生产结果：最终目录的精确列举、每个文件的字节与 sha256、源路径不存在、
  没有临时文件残留、`SUCCESS` 数量。
* 故障用例：每个 `ExecutionFailureKind` 中可注入的种类至少一次，每个 resume 点至少一次；每次失败后断言核心不变量；
  随后 resume 至 `SUCCESS`。
* 冲突用例：同目标的影片对（重复番号）——恰好一个 `SUCCESS`，另一个 `FAILED`，零 effect。
* 植入的无关临时文件与用户文件在全部 500 个影片处理完后逐字节不变。
* 架构回归扫描；非空洞性检查（临时改动生产代码使门槛失败，例如把 `os.link` 换为可覆盖的调用、
  在 unlink 源之前去掉发布后校验、把 `mkdir` 改为 `exist_ok`），改动撤销、不提交，失败数记录在 handoff 中。

## 32. 实现状态

| 批次 | 内容 | 状态 |
|---|---|---|
| E0 | 本合同 + 施工计划（docs-only） | ESTABLISHED |
| S1 | Foundation / graph / manifest / read-only preflight | NOT STARTED |
| S2 | directory ownership + checkpoint/resume foundation | NOT STARTED |
| S3 | same-volume + cross-volume media transfer | NOT STARTED |
| S4 | artifact execution + retry verification | NOT STARTED |
| S5 | integrated single-item executor | NOT STARTED |
| S6 | synthetic/fault/concurrency gate + final handoff | NOT STARTED |

## 33. 延续项处理

| 延续项 | P4-C7 的处理 |
|---|---|
| OrganizePlan 操作图模型层加固（P4-C2 入口门槛） | 在执行边界实施（第 6 节）；planning 模型本身不改 |
| overwrite 执行器语义（冻结为 NEVER） | 在执行层对真实文件系统实施（第 23 节） |
| 扩展的 Windows 保留名 | 在执行边界对 P4-C7 创建的组件 fail closed（第 26.3 节）；planning finding 仍 CARRIED |
| P4-C2-R1-02（裸 `\\server`） | 在执行边界拒绝（第 6.6 节）；planning finding 仍 CARRIED |
| P4-C1-R-02..R-05 | 通过源快照重新校验中和“发现结果过期”；scanner finding 仍 CARRIED |
| P4-C3-R-01、P4-C3-R-02、P4-C4-R-01、P2-R-05、P2-R-06、P2-R-07、C3-N1..N4、C4-N1、C4-R1-N1..N3、F3、F5、C5-R1-L1 | 不触及、不相关（P4-C7 不依赖相应模块） |

## 34. P4-C7 范围之外（冻结）

批量编排、预览 UI、CLI、JSON / 诊断导出、持久化 / 磁盘 resume、数据库、回滚、覆盖、自动加后缀、
`library_root` 创建、祖先链接检查、空间预检、长路径前缀改写、`openat` / 句柄相对 API、`ctypes`、
权限修改、源父目录清理（空的下载目录不会被删除）、Amane 集成、metadata / NFO / 图片处理。
