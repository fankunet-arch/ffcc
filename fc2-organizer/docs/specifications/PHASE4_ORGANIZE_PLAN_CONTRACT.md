# FC2 Organizer -- Phase 4 / P4-C2 不可变整理计划合同（Immutable Organize Plan Contract）

状态：**在 P4-C2 冻结**（候选；独立关闭复查待进行）。
Package：`fc2_organizer.planning`（`errors.py`、`models.py`、`policy.py`、`paths.py`、`planner.py`）。

**范围（对本 package 冻结）：** 回答“如果执行整理，针对一个已经发现的媒体条目，会得到哪些目标路径和操作？”
不做任何形式的文件系统修改，不写 NFO / 图片，不依赖 Amane，不做持久化，没有 CLI / UI，不执行任何计划中的操作。
完整的范围外清单见第 13 节。

## 1. 架构与依赖方向

```text
fc2_organizer
    |
    v
fc2_metadata_core
```

`fc2_metadata_core` 从不 import `fc2_organizer`。`fc2_organizer` 下的任何内容都不得 import `amane`。
`fc2_organizer.planning` 只消费：

* `fc2_organizer.discovery` 的**公开** package（`DiscoveredMediaItem`）-- 从不直接使用其内部模块
  （`scanner`、`models`、`policy`、`errors`、`_platform`），也不重新扫描 / 重新发现任何内容。
* `fc2_metadata_core.models`（`NormalizedMetadata`）和
  `fc2_metadata_core.normalize`（`is_valid_fc2_number`）-- 这是已关闭的 Phase 1/3 公开边界。它从不 import
  `fc2_metadata_core.sources`、`.aggregation`、`.resource_control`、`.http` 或 `.batch`。

由 `tests/contract/test_planning_architecture.py` 强制执行：对每个 `planning/*.py` 文件做静态 AST 扫描
（能发现埋在函数体或 `try`/`except` 中的 import）；检查只 import 了 `fc2_metadata_core.models` /
`fc2_metadata_core.normalize`；检查只 import 了裸的 `fc2_organizer.discovery` package（从不 import 其子模块）；
以及一个动态 meta-path-finder 阻断，在端到端实际调用 `build_organize_plan` 的同时，证明即使是惰性 import
也无法加载 `amane`。

**关于动态阻断作用范围的说明：** 该阻断只防止 `amane` 在运行时被加载（不防止
`fc2_metadata_core.aggregation` / `.sources` / `.http` / `.batch` 被加载）。这是有意为之，并非缺口：
`fc2_metadata_core` 自身（已冻结、不在本次修改范围内）的 `__init__.py` 只要*任何*一个子模块被 import
— 包括允许使用的 `models`/`normalize` — 就会无条件地 import *所有*子模块。在 meta-path 层面阻断这些特定子模块，
会让 `fc2_metadata_core.models` 本身无法通过其受支持的接口 import，这并不是对
`fc2_organizer.planning` 自身架构有意义的测试。证明本 package 自己的源码从不*引用*这些子模块的，是静态 AST 扫描
— 而且它以最严格的方式运行（见测试文件中的 `_FORBIDDEN_PREFIXES`）。

`fc2_organizer/__init__.py` 刻意**不**像 `discovery` 那样急切地 import `planning`，原因正如上文所述：
从 `fc2_organizer/__init__.py` 急切地 import `planning`，会让仅仅 import `fc2_organizer` 或
`fc2_organizer.discovery` 就触发 `fc2_metadata_core` 的传递加载 — 这会破坏 P4-C1 自己已经冻结的
`test_discover_media_runs_end_to_end_with_forbidden_modules_blocked_at_runtime`
（这是在 P4-C2 开发过程中发现并修复的；见 P4-C2 handoff 的 “Known limitations” 一节）。调用方通过
`from fc2_organizer import planning` 或
`from fc2_organizer.planning import build_organize_plan` 使用本 package。

## 2. 公开 API

```python
from fc2_organizer.planning import (
    OutputPolicy,
    OrganizePlan,
    PlannedPath,
    PlannedOperation,
    PlannedOperationKind,
    build_organize_plan,
)

plan: OrganizePlan = build_organize_plan(
    media_item,       # fc2_organizer.discovery.DiscoveredMediaItem
    canonical_number,  # exact str, already FC2-<digits>
    metadata,          # fc2_metadata_core.models.NormalizedMetadata
    library_root,      # str | os.PathLike, fully-qualified absolute (section 11a)
    policy=None,       # OutputPolicy | None
)
```

`build_organize_plan` 是一个纯函数：相同的输入总是产生相等的 `OrganizePlan`（第 9 节），并且它执行
**零文件系统访问** -- 连读取都没有（第 10-11 节）。

## 3. `OutputPolicy`

frozen dataclass（`policy.py`），是*唯一*可由调用方配置的旋钮：

```text
nfo_extension: str = ".nfo"
poster_filename: str = "poster.jpg"
fanart_filename: str = "fanart.jpg"
thumb_filename: str = "thumb.jpg"
extrafanart_dirname: str = "extrafanart"
```

目录命名（总是裸的规范 FC2 番号）以及媒体 / NFO 的 basename（总是 `<canonical><ext>` /
`<canonical><nfo_extension>`）**永远**不可配置 -- 没有命名策略字段，标题也从不参与（第 5 节）。
冲突策略（fail closed）和覆盖策略（never）是冻结的常量，而不是本策略上的字段（第 7-8 节）--
`OutputPolicy` 没有 `overwrite`/`collision` 旋钮，`build_organize_plan` 也没有 `overwrite=`/`on_collision=` 参数。

`__post_init__` 只校验字段的*形态*（非空 `str`，`nfo_extension` 以点开头）；Windows 路径组件的*安全性*
由 `paths.validate_path_component` 在 `build_organize_plan` 内部把这些值转换成实际路径组件时，
统一在一处集中校验 -- 绝不重复实现（第 6 节）。

## 4. 默认 v1.0 布局（冻结）

```text
<library_root>/
  FC2-1234567/
    FC2-1234567.<original-extension>
    FC2-1234567.nfo
    poster.jpg
    fanart.jpg
    thumb.jpg
    extrafanart/
```

`downloads/random-name.MP4` + 规范番号 `FC2-1234567` -> 目标媒体
`<library_root>/FC2-1234567/FC2-1234567.mp4`。扩展名被规范化为小写（`.MP4` -> `.mp4`），但**容器从不改变**
（`.mp4` 永远不会变成 `.mkv`）：`build_organize_plan` 只把 `media_item.extension` 转成小写，从不替换成
另一个扩展名。`OrganizePlan.source_extension`（来源身份，第 8 节）保留*原始*、未修改的扩展名，
以便之后与真实文件进行校验；只有*目标* basename 会被规范化。

## 5. 标题从不参与路径生成（冻结）

即使 `metadata.title` 是 `"Example Title"`，目标目录也总是 `FC2-1234567`，目标媒体也总是 `FC2-1234567.mp4`
-- 绝不会是 `FC2-1234567 Example Title`。默认的路径生成逻辑不读取任何 `NormalizedMetadata` 字段
（`title`、`actors`、`studio`、`genre`、...）。这是一项刻意的 v1.0 冻结（并非疏忽），目的是避免标题漂移、
Unicode / 特殊字符带来的路径风险，以及来源优先级变化导致的重命名漂移；也没有可以选择启用
按标题命名的 `OutputPolicy` 命名策略旋钮。

## 6. 规范番号边界（没有第二个解析器）

`canonical_number` 必须是严格的 `str`（`str` 子类会被拒绝 -- `OrganizePlanInputError` -- 这与批处理 package
自己的 C4-R1-05 先例一致：在拒绝路径上，恶意子类的任何方法都不会被调用），并且满足
`fc2_metadata_core.normalize.is_valid_fc2_number`（否则抛出 `InvalidCanonicalNumberError`）。本 package
没有实现第二个 FC2 识别器，也从不猜测 / 修复脏输入 -- 它 fail closed，与 `BatchScheduler`
（`PHASE3_BATCH_CONTRACT.md` 第 4 节）在其规范番号边界上的做法完全一致。

## 7. 来源媒体身份（不重新发现）

`media_item` 必须是真正的 `fc2_organizer.discovery.DiscoveredMediaItem` 实例（否则抛出
`OrganizePlanInputError`）。本 package 从不重新扫描目录，从不重新推导媒体身份，也从不为了校验
`media_item` 的字段而访问文件系统 -- 它只读取 P4-C1 已经校验过的五个字段：`source_path`、`relative_path`、
`extension`、`index`、`size`。这五个字段都原样带入 `OrganizePlan.source_*`，以便将来的执行层在动手之前
可以对照真实文件系统重新校验（这种重新校验明确不在本范围内 -- P4-C2 完全不产生副作用）。

## 8. `OrganizePlan` 字段（冻结形态）

```text
source_path: str            (absolute; from media_item, unmodified)
source_relative_path: str   (from media_item, unmodified)
source_extension: str       (from media_item, unmodified -- NOT lowercased)
source_index: int           (from media_item, unmodified)
source_size: int            (from media_item, unmodified)

canonical_number: str

library_root: str            (fully-qualified absolute, section 11a)

target_directory: PlannedPath
target_media_path: PlannedPath
nfo_path: PlannedPath
poster_path: PlannedPath
fanart_path: PlannedPath
thumb_path: PlannedPath
extrafanart_directory: PlannedPath

operations: tuple[PlannedOperation, ...]
```

这里从不存放任何聚合 trace、`SourceExecutionTrace` 或错误诊断对象（第 12 节）-- `OrganizePlan` 不是
trace 的发布边界。`metadata` 本身（`NormalizedMetadata` 对象）同样不存放在计划中；只存放已提取出的
`canonical_number`（metadata 在 P4-C2 中的作用只是校验，见第 9 节）。

## 9. Metadata 边界：仅用于校验，fail closed

`metadata` 必须是真正的 `NormalizedMetadata` 实例（否则抛出 `OrganizePlanInputError`），并且满足
`meets_minimum_success()`（`FC2_METADATA_CORE_CONTRACT.md` 第 2 节 -- 规范番号 + 非空标题）。
达不到这一点就会抛出 `InvalidMetadataForPlanningError` -- **绝不会根据部分 / 失败的 metadata 生成计划**，
尽管 v1.0 默认的路径推导实际上并不读取 `metadata.title`/`.actors` 等字段。本 package 不重新定义
“metadata 成功”；它完全沿用冻结的 `NormalizedMetadata.meets_minimum_success()` 谓词。

## 10. Windows 路径组件安全（集中处理）

`fc2_organizer.planning.paths.validate_path_component` 是路径组件净化逻辑所在的**唯一**位置
（`planner.py` 和 `models.py` 都调用它；没有重复的逻辑）。每个生成的 basename / 目录名
（`FC2-1234567`、`FC2-1234567.mp4`、`FC2-1234567.nfo`、`poster.jpg`、
`fanart.jpg`、`thumb.jpg`、`extrafanart`，以及 `OutputPolicy` 对后四者和 NFO 扩展名的任何覆盖值）都要校验：

* 非空 `str`；不能恰好是 `"."` 或 `".."`
* 不含嵌入的路径分隔符（`/` 或 `\`）-- 单个组件永远不能夹带额外的路径段（这同时也是对目录穿越 /
  绝对路径覆盖 / 盘符替换的防御：`../../evil.jpg`、`C:\other\evil.jpg` 和 `D:evil.jpg` 都在这里被拒绝，
  因为它们各自都包含被禁止的字符或分隔符）
* 不含其他 Windows 非法字符（`< > : " | ? *`），也不含 ASCII 控制字符
* 不能以点或空格结尾
* 不能是 Windows 保留设备名（`CON`、`PRN`、`AUX`、`NUL`、
  `COM1`-`COM9`、`LPT1`-`LPT9`），不区分大小写，依据*第一个*点之前的部分判断
  （`CON.txt` 被拒绝，`CONFIG.txt` 被接受）

违规时抛出 `UnsafeTargetComponentError`。冻结的 v1.0 默认值永远不会触发它（有回归测试）；它只会因为
`OutputPolicy` 覆盖值或手工构建的模型而触发。

## 11. 目标包含关系（结构性的，不探测文件系统）

由于每个调用方可控的组件在用 `os.path.join(target_directory, basename)` 拼接*之前*都已被校验为不含
分隔符 / `..`，拼接结果在**结构上**就保证嵌套在 `library_root` 之下 -- 这是字符串构造的性质，而不是通过
解析 / stat 文件系统检查出来的（`build_organize_plan` 从不调用 `exists`/`resolve`/`realpath`）。
`OrganizePlan.__post_init__` 还会通过 `fc2_organizer.planning.paths.is_contained_within`
（纯词法的、Windows 下不区分大小写的路径段比较）对每个目标字段**再次检查**，一旦失败即抛出
`TargetEscapesLibraryRootError` -- 这是模型层上冗余的纵深防御不变量，与构建该计划的 planner 是否正确无关，
与 P4-C1-R-01 针对 `DiscoveredMediaItem.source_path` 的双层（scanner + 模型）模式相同。

**按路径段比较，而不是 `str.split(os.sep)`（R1，P4-C2-GOV-02）。** 最初的实现在 `os.sep` 上切分每个规范化后的
路径。一个本身就是裸盘符（`C:\`）或裸 UNC 共享（`\\server\share\`）的根目录，规范化后得到的字符串*以*分隔符
结尾，因此 `str.split(os.sep)` 会产生一个多余的结尾空段，抬高根目录的段数 -- 一个真正的子路径
（`C:\FC2-1234567`）于是会被错误地判为“不包含”（即使该候选路径确实嵌套在根目录之下，也会触发
`len(candidate_parts) <= len(root_parts)`）。`is_contained_within` 现在改用 `pathlib.Path(...).parts` 切分：
盘符加根目录、或 UNC 共享加根目录，会合并为一个锚点段（`('C:\\',)` /
`('\\\\server\\share\\',)`），不存在上述伪影，仍然完全不访问文件系统（`Path` 的构造和 `.parts` 都是纯词法的），
并且继续拒绝字符串前缀相同的同级目录（`C:\library2` 不在 `C:\library` “之下”），同时从不使用
`str.startswith`。

## 11a. 完全限定的库根目录边界（冻结，P4-C2-GOV-03）

`library_root` 必须是一个**无歧义、完全限定的绝对路径**，以*当前运行时操作系统*自身的语义为准 --
`fc2_organizer.planning.paths.is_fully_qualified_absolute_root` 是唯一的集中边界；`planner.py` 和 `models.py`
都调用它，而不是各自用裸的 `os.path.isabs()` 去猜测。

* **Windows**（`os.name == "nt"`）：只有当 `os.path.splitdrive` 找到带根目录的真实盘符（`C:\lib`、`C:/lib`）
  或 UNC 共享（`\\server\share`、`\\server\share\lib`，带或不带结尾分隔符）时才接受。**拒绝：**
  普通相对名称（`lib`）、点开头的相对形式（`.\lib`、`..\lib`）、相对于盘符的形式（`C:lib`），以及 --
  本项所关闭的那个 finding -- **有根但无盘符**的形式（`\lib`、`/lib`）。`os.path.isabs()` 对有根但无盘符
  形式的处理在不同 Python 版本之间有过差异；它本身就有歧义（“当前所在盘符的根目录”），本 package 从不猜测它。
* **POSIX**（其他所有情况）：普通的 `os.path.isabs(path)` -- POSIX 没有盘符 / UNC 歧义，因此 `/lib`
  本来就是无歧义的，仍然合法。分支按*当前运行时操作系统*选择，绝不根据字符串本身的形态去猜测，
  因此真正的 POSIX 绝对路径永远不会被 Windows 专属规则拒绝（反之亦然）。

违规时，`build_organize_plan` 抛出 `InvalidLibraryRootError`；对于手工构建的计划，`OrganizePlan.__post_init__`
还会（在模型层冗余地）抛出 `OrganizePlanContractError` -- 与第 11 节包含关系再检查相同的双层模式。

## 12. 冲突与覆盖策略（冻结，不是旋钮）

**冲突 = fail closed。** 如果一个计划自己生成的任意两个目标 basename 在 Windows 不区分大小写的文件名语义下会
发生冲突（例如 `poster.jpg` 与同样被设为 `"poster.jpg"` 的 `OutputPolicy.fanart_filename`，或者把
`nfo_extension` 设成与来源自身扩展名相同），`build_organize_plan` 会抛出 `InternalTargetCollisionError`。
没有自动加后缀（`(1)`、`_2`、`-copy`），也没有悄悄重命名目录。

**覆盖 = never**，适用于源媒体、目标媒体以及每一个生成的 artifact。这是一项冻结的语义，本 package 生成的计划
都与之保持一致；P4-C2 不会对真实文件系统做任何检查或删除（完全没有文件系统访问）-- 针对磁盘上已有文件的
真实预检被明确推迟到将来的执行阶段（第 13 节）。

两个不同的 `DiscoveredMediaItem` 恰好规范化为同一个 FC2 番号时（例如同一部影片在两个不同的源目录下被
真实地重复下载），P4-C2 **不会**去重或解决：每个条目都产生自己合法的、独立计算的 `OrganizePlan`，
这两个计划会指向*同一个*目标 -- P4-C2 把这一情况暴露出来（两个计划都可以被调用方检查和比较），而不是替调用方
解决它，这正是 `InternalTargetCollisionError` / 冲突策略冻结的本意。

## 13. P4-C2 范围之外

不做任何形式的 `mkdir`/重命名/移动/复制/删除，不渲染 / 写入 NFO，不下载 poster/fanart/thumb/extrafanart，
也不校验图片，没有文件系统执行器，没有预览 UI，没有 CLI，没有 JSON 诊断信息，没有持久化的任务 / 数据库 / 恢复，
没有 Amane adapter，没有 HTTP 服务 / REST API / GUI，没有真实文件系统预检（检测已存在的文件、探测权限 /
可写性）。针对磁盘上实际内容的真实文件系统预检和冲突解决，被明确推迟到将来的执行 package。

## 14. 不可变性与确定性（冻结）

每个公开模型（`OutputPolicy`、`PlannedPath`、`PlannedOperation`、
`OrganizePlan`）都是 frozen、`slots=True` 的 dataclass。`OrganizePlan.operations`
是 `tuple[PlannedOperation, ...]`；整个对象图中任何地方都没有调用方持有的可变容器。`build_organize_plan`
不读取随机源，不读取墙钟，不依赖文件系统枚举顺序，也不生成 UUID -- 相同的输入总是产生相等的
（可用 `==` 比较的）`OrganizePlan`，包括相同的 `operations` 顺序：
`CREATE_DIRECTORY`、`MOVE_MEDIA`、`MATERIALIZE_NFO`、`MATERIALIZE_POSTER`、
`MATERIALIZE_FANART`、`MATERIALIZE_THUMB`、`ENSURE_EXTRAFANART_DIRECTORY`。

## 15. 计划中的操作纯属描述

`PlannedOperationKind` 有七个成员（上面的列表）。`PlannedOperation` 只携带 `kind` + `target: PlannedPath`
（+ `source: PlannedPath | None`，当且仅当 `kind is MOVE_MEDIA` 时设置 -- 这是唯一有两个路径的操作）。
`PlannedOperation`/`OrganizePlan` 的任何方法都不会执行它所描述的动作 -- 本 package 中任何地方都没有
`run()`/`apply()`/`execute()`。

## 16. 错误分类（`errors.py`）

```text
OrganizePlanError(Exception)
+-- OrganizePlanInputError(OrganizePlanError, TypeError)
|      media_item not a DiscoveredMediaItem; canonical_number not an
|      exact str; metadata not a NormalizedMetadata; library_root not a
|      str/os.PathLike; policy neither None nor an OutputPolicy
+-- InvalidCanonicalNumberError(OrganizePlanError, ValueError)
+-- InvalidLibraryRootError(OrganizePlanError, ValueError)
|      empty / whitespace-only / not a fully-qualified absolute path
|      (section 11a -- includes a Windows rooted-but-driveless form)
+-- InvalidMetadataForPlanningError(OrganizePlanError, ValueError)
+-- InvalidOutputPolicyError(OrganizePlanError, ValueError)
+-- UnsafeTargetComponentError(OrganizePlanError, ValueError)
+-- InternalTargetCollisionError(OrganizePlanError, ValueError)
+-- OrganizePlanContractError(OrganizePlanError, ValueError)
       (hand-built model violates its own structural contract)
       +-- TargetEscapesLibraryRootError(OrganizePlanContractError)
```

每一种错误都可以独立捕获；没有用裸 `ValueError` 把不同的失败原因混为一谈（与项目其余部分
“没有无状态失败路径”的约定一致，`FC2_METADATA_CORE_CONTRACT.md` 第 3 节）。

## 17. 测试矩阵

| # | 要求 | 测试文件 |
|---|---|---|
| 1-12 | 标准 / 保留扩展名 / 规范化 / 字段确定的计划、相同输入重放、不同身份但同一番号 | `test_planning_planner.py` |
| 13-15 | 规范番号校验（合法 / 脏 / 子类）、拒绝不合格的 metadata | `test_planning_planner.py` |
| 16 | 拒绝空 / 仅空白 / 相对 / 非 str 的库根目录，接受 `os.PathLike`，**完全限定根目录边界（第 11a 节）：接受 Windows 盘符 / UNC，拒绝有根无盘符（`\lib`/`/lib`），接受 POSIX `/lib`** | `test_planning_planner.py`、`test_planning_paths.py`、`test_planning_models.py` |
| 17-18 | 目标包含关系（包括裸盘符根目录和 UNC 共享根目录下的子路径，第 11 节 R1 修复）、目录穿越 / 绝对路径覆盖 / 盘符替换都无法逃出根目录 | `test_planning_planner.py`、`test_planning_paths.py` |
| 19-21 | Windows 非法字符、保留设备名、结尾的点 / 空格 | `test_planning_paths.py`、`test_planning_planner.py` |
| 22-23 | 不区分大小写的冲突判断、内部冲突 fail-closed | `test_planning_paths.py`、`test_planning_planner.py` |
| 24-25 | 覆盖策略已冻结（不是旋钮），不自动加后缀 | `test_planning_planner.py` |
| 26-27 | 标题 / Unicode metadata 永远不会改变默认目标路径 | `test_planning_planner.py` |
| 28 | 计划模型深度不可变 | `test_planning_models.py` |
| 29 | 操作以确定的顺序排列 | `test_planning_planner.py`、`test_planning_synthetic_gate.py` |
| 30-33 | 不修改文件系统、不访问网络（守卫扫描真实、非空的生产源码目录，并且被证明在植入的禁止 import 上会 FAIL，而不仅仅是在今天干净的代码上 PASS -- 见下文 “Network Guard” 一节，P4-C2-GOV-01）、不依赖 Amane、没有反向依赖 | `test_planning_no_mutation.py`、`test_planning_architecture.py`、`test_planning_synthetic_gate.py` |
| 34 | P4-C1 discovery 保持不变（行为层面） | 全量回归（R1 之后 2692 passed / 8 skipped，P4-C1 关闭时的基线为 2480 passed / 4 skipped） |
| 模型 / 策略 / 路径合同 | `PlannedPath`/`PlannedOperation`/`OrganizePlan`/`OutputPolicy` 的不变量，净化 / 包含关系 / 完全限定判断等 helper | `test_planning_models.py`、`test_planning_policy.py`、`test_planning_paths.py` |
| 架构 | 依赖方向、没有 `amane`、没有被禁止的 `fc2_metadata_core`/`discovery` 子模块 | `test_planning_architecture.py` |
| 合成计划门槛 | 400 个合成条目，多种扩展名 / 番号 / Unicode 标题，确定性，包含关系，零内部冲突，零修改，非空洞且能发现植入 import 的网络守卫 | `test_planning_synthetic_gate.py` |

### Network Guard（R1，P4-C2-GOV-01）

合成门槛中的“无网络 import”扫描，以 `Path(__file__).resolve().parents[N] / "src" /
"fc2_organizer" / "planning"` 计算其生产源码目录。最初的 `N=2` 是从
`tests/contract/test_planning_architecture.py` 复制过来的（那个文件浅一层 -- 位于 `tests/contract`，
在那里 `parents[2]` 是正确的），但本文件位于 `tests/unit/planning/`，深了一层，因此 `parents[2]` 解析到了
不存在的 `tests/src/fc2_organizer/planning`：`rglob("*.py")` 悄悄返回零个文件，而遍历零个文件的
`for path in ...: assert ...` 循环会空洞地通过，什么都没检查。已修正为 `parents[3]`，
并从三个方面加以守护：(1) 一个专门的测试断言解析出的目录存在、*并且*文件数非零、*并且*按名称包含每一个已知的
生产模块；(2) 扫描函数本身（`_scan_forbidden_imports`）是一个小的、可复用的纯 AST 遍历器，直接对放在隔离的
`tmp_path` 文件中（从不是生产文件）植入的 `import socket` / `from urllib import request` 运行，并断言能检测到它们
-- 证明该守卫确实能够 FAIL，而不仅仅是在恰好干净的今天代码上 PASS；(3) 第四个测试证明同一个扫描器
*不会*对它自己也使用的普通允许 import（`os`、`pathlib`、`dataclasses`、`enum`）误报。为使其通过，
没有修改任何生产代码 -- 两位独立复查者都已确认 `fc2_organizer.planning` 没有真实的网络依赖；这纯粹是
测试证据层面的缺陷。

## 18. 延续的待办（P4-C2 未处理）

未触发 / 未处理：`P4-C1-R-02`、`P4-C1-R-03`、`P4-C1-R-04`、
`P4-C1-R-05`、`C2-L2`、`P2-R-05`、`P2-R-06`、`P2-R-07`、`P2-R-10`、`C3-N1`、
`C3-N2`、`C3-N3`、`C3-N4`、`C4-N1`、`C4-R1-N1`、`C4-R1-N2`、`C4-R1-N3`、`F3`、
`F5`、`C5-R1-L1`。这些债务没有一项被触及、读取，或与本 package 相关：
`fc2_organizer.planning` 对它们所涉及的任何模块都没有运行时依赖（它对 `fc2_metadata_core` 的唯一依赖是只读的
`models`/`normalize` 边界）。
