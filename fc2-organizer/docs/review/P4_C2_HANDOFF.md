# Phase 4 / P4-C2 Handoff -- 不可变整理计划（Immutable Organize Plan）

```text
Phase        = 4
Package      = P4-C2
Role         = Developer
Branch       = claude/phase4-c2-organize-plan
```

## 1. 坐标

```text
Frozen Base                = 51933a81382d7922a61b5fcdddc54b17b5293e6f
P4-C2 Code Review Candidate = 1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8
P4-C2 Docs Head             = <this commit; see git log after commit>
Remote Head                 = <set after push; see "Push" section below>

Code Review Range: 51933a81382d7922a61b5fcdddc54b17b5293e6f..1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8
Docs Review Range: 1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8..<Docs Head>
```

在任何改动之前已验证：`git fetch --all --tags`，
`origin/claude/phase4-c1-recursive-discovery` == `51933a81382d7922a61b5fcdddc54b17b5293e6f`，
工作区干净（只有未跟踪的 `.claude/`），从那个确切的提交创建了新分支
`claude/phase4-c2-organize-plan`，并在一个隔离的 worktree 中开发。

## 2. 类型

**NEW PACKAGE**（`fc2_organizer.planning`），外加对现有文件的两处最小改动 -- 见第 4 节。

## 3. 变更文件

**Code Review Candidate（`1a4ca88`），16 个文件：**

新增（14）：
```text
fc2-organizer/src/fc2_organizer/planning/__init__.py
fc2-organizer/src/fc2_organizer/planning/errors.py
fc2-organizer/src/fc2_organizer/planning/models.py
fc2-organizer/src/fc2_organizer/planning/paths.py
fc2-organizer/src/fc2_organizer/planning/planner.py
fc2-organizer/src/fc2_organizer/planning/policy.py
fc2-organizer/tests/contract/test_planning_architecture.py
fc2-organizer/tests/unit/planning/__init__.py
fc2-organizer/tests/unit/planning/test_planning_models.py
fc2-organizer/tests/unit/planning/test_planning_no_mutation.py
fc2-organizer/tests/unit/planning/test_planning_paths.py
fc2-organizer/tests/unit/planning/test_planning_planner.py
fc2-organizer/tests/unit/planning/test_planning_policy.py
fc2-organizer/tests/unit/planning/test_planning_synthetic_gate.py
```

修改（2）：
```text
fc2-organizer/src/fc2_organizer/__init__.py             (M -- see section 8)
fc2-organizer/tests/contract/test_discovery_architecture.py  (M -- see section 4)
```

**Docs Head（本提交），2 个文件，都为新增：**
```text
fc2-organizer/docs/specifications/PHASE4_ORGANIZE_PLAN_CONTRACT.md
fc2-organizer/docs/review/P4_C2_HANDOFF.md
```

不需要修改 `pyproject.toml`：`fc2_organizer.planning` 与 `fc2_organizer.discovery` 以同样的方式被识别
（`[tool.setuptools.packages.find]
where = ["src"]`、`[tool.pytest.ini_options] pythonpath = ["src", "tests"]`）。

## 4. 对 P4-C1 文件的那一处改动及其原因

`fc2-organizer/tests/contract/test_discovery_architecture.py` 中的
`test_organizer_package_has_no_other_stray_top_level_modules_yet` 断言了
`top_level_dirs == {"discovery"}`。它自己的 docstring 本来就写着 *"the
only subpackage under fc2_organizer is discovery **yet**"* -- 这是一个明确预见到下一个 package 的作用域守卫，而不是关于
discovery 自身内部的声明。把 `fc2_organizer.planning` 作为同级 package 加入（从不修改 `discovery/**`），必然会让这个特定断言
不成立；如果保持不变，就会把一个原本通过的 P4-C1 测试变成一次虚假的失败。该断言已更新为
`top_level_dirs == {"discovery", "planning"}`，并扩充了 docstring 来说明这一改动并指向本 handoff。**该文件中的其他任何一行，
以及 `src/fc2_organizer/discovery/**` 或 `src/fc2_metadata_core/**` 下的任何文件，都没有被触碰。** `discover_media` 的行为、
模型和错误语义都没有改变。

这一点在编写代码之前的报告中（依照任务简报的 Context Handshake 步骤）就已提出，而不是事后才发现的。

## 5. 架构摘要

```text
DiscoveredMediaItem (P4-C1, closed)
+ canonical FC2 number
+ NormalizedMetadata (fc2_metadata_core, closed)
+ library_root
+ OutputPolicy (optional)
        |
build_organize_plan(...)
        |   pure, deterministic, side-effect-free, ZERO FILESYSTEM MUTATION
        v
OrganizePlan(source identity, canonical number, target paths, planned operations)
```

`fc2_organizer -> fc2_metadata_core` 是唯一允许的依赖方向（未改变，冻结）。`fc2_organizer.planning` 依赖
`fc2_organizer.discovery` 的公开 package（只用 `DiscoveredMediaItem`）以及
`fc2_metadata_core.models` / `fc2_metadata_core.normalize`（从不依赖
`.sources`/`.aggregation`/`.resource_control`/`.http`/`.batch`，也从不依赖 discovery 的内部模块）。完整细节：
`docs/specifications/PHASE4_ORGANIZE_PLAN_CONTRACT.md`。

## 6. 公开 API

```python
from fc2_organizer.planning import (
    OutputPolicy, OrganizePlan, PlannedPath, PlannedOperation,
    PlannedOperationKind, build_organize_plan,
)

plan = build_organize_plan(media_item, canonical_number, metadata, library_root, policy=None)
```

## 7. 默认目录布局

```text
<library_root>/
  FC2-1234567/
    FC2-1234567.<original-extension, lowercased>
    FC2-1234567.nfo
    poster.jpg
    fanart.jpg
    thumb.jpg
    extrafanart/
```

标题从不参与；由
`test_title_does_not_alter_default_target_path` 和
`test_unicode_metadata_does_not_alter_default_target_path` 直接验证，外加 400-item 合成门槛中的
`test_synthetic_gate_unicode_titles_never_leak_into_target_paths`。

## 8. 目标包含关系的策略

**结构性的，不探测文件系统。** 每一个由调用方控制的路径组件（目录名、媒体 / NFO basename、artifact 文件名）在通过
`os.path.join` 拼接到 `library_root`/`target_directory` 之上*之前*，都被校验为不含路径分隔符、不含 `..` -- 因此无论
`library_root` 本身的字符串内容是什么，结果在构造上就嵌套在根目录之下。`OrganizePlan.__post_init__` 还会通过一个纯词法的、
Windows 下不区分大小写的包含关系检查（`fc2_organizer.planning.paths.is_contained_within`）独立地再次检查每一个目标字段，
一旦失败即抛出 `TargetEscapesLibraryRootError` -- 这是模型层上冗余的纵深防御不变量，与 P4-C1-R-01 针对
`DiscoveredMediaItem.source_path` 的双层（scanner + 模型）模式相同。
本 package 中任何地方都没有 `exists()`/`resolve()`/`realpath()` 调用。

## 9. Windows 文件名安全策略

集中在一个函数中，`fc2_organizer.planning.paths.validate_path_component`
（合同规格第 10 节）：非法字符（`< > : " / \ | ? *`）、ASCII 控制字符、结尾的点 / 空格，以及 Windows 保留设备名
（`CON`/`PRN`/`AUX`/`NUL`/`COM1`-`9`/`LPT1`-`9`，不区分大小写，依据第一个点之前的部分判断）全部以
`UnsafeTargetComponentError` 拒绝。`planner.py` 和 `models.py` 都调用这一个函数 -- 没有重复的净化逻辑。冻结的
v1.0 默认值永远不会触发它。

## 10. 冲突策略

**Fail closed，冻结，不是旋钮。** 如果一个计划自己生成的任意两个 basename 在 Windows 不区分大小写的语义下会冲突，
则抛出 `InternalTargetCollisionError`。不自动加后缀（`(1)`/`_2`/`-copy`），也不悄悄重命名。`OutputPolicy` 没有冲突策略字段；
`build_organize_plan` 没有 `on_collision=` 参数。

## 11. 覆盖策略

**永不覆盖，适用于源媒体、目标媒体以及每一个生成的 artifact。**
这是冻结的常量，在本 package 中任何地方都没有表示为字段 / 参数（已直接验证：
`test_overwrite_policy_is_frozen_never_and_not_a_caller_knob` 检查 `OutputPolicy` 没有 `overwrite`/`overwrite_policy`
属性，并且 `build_organize_plan` 的签名中没有 `overwrite` 参数）。不做任何真实的文件系统预检（检测已存在的文件）--
P4-C2 不做任何形式的文件系统访问；针对磁盘上实际存在内容的真实预检被明确推迟到将来的执行 package。

## 12. 不可变性策略

每个公开模型（`OutputPolicy`、`PlannedPath`、`PlannedOperation`、
`OrganizePlan`）都是 `@dataclass(frozen=True, slots=True)`。
`OrganizePlan.operations` 是真正的 `tuple[PlannedOperation, ...]`（不是 list）；对象图中任何地方都没有调用方持有的可变容器。
`test_planning_models.py::TestOrganizePlanImmutability` 证明：对标量重新赋值会抛出 `dataclasses.FrozenInstanceError`，
`operations[i] = x` 会抛出 `TypeError`（tuple 条目赋值），`operations` 是真正的 `tuple`（不是 `isinstance(..., list)`），
并且公开接口上不存在任何修改方法（`append`/`extend`/...）。

## 13. 确定性策略

`build_organize_plan` 不读取随机数，不读取墙钟，不依赖文件系统枚举顺序，也不生成 UUID -- 每个目标路径都是由其五个输入
计算出来的纯字符串。`test_identical_input_produces_identical_plan`
以及合成门槛中的 `test_synthetic_gate_all_plans_deterministic_on_replay`
（400 个条目，重放两次）都断言：在相同输入下多次调用，`OrganizePlan.__eq__` 完全相等
（dataclass 逐字段比较，包括 `operations` tuple 的顺序）。

## 14. 不修改文件系统的证据

两个独立的证明（`test_planning_no_mutation.py`），因为简报明确要求“看起来不写入”不是充分的证据：

1. **前后目录快照。** 对一个包含现有文件的真实目录，在针对一个本身不存在于磁盘上的库根目录构建五个计划之前和之后分别做快照
   （路径 -> 内容）；断言两份快照逐字节相同，并断言那个（从未被创建的）库根目录仍然不存在。
2. **修改类 API 陷阱。** 每一个常见的修改类 API 都被 monkeypatch 为一旦被调用就抛出异常：`os.mkdir`/`makedirs`/`rename`/
   `replace`/`remove`/
   `unlink`/`rmdir`/`removedirs`/`chmod`/`utime`/`symlink`/`link`、
   `shutil.move`/`copy`/`copy2`/`copyfile`/`copytree`/`rmtree`、
   `pathlib.Path.mkdir`/`write_text`/`write_bytes`/`touch`/`rename`/
   `replace`/`unlink`/`rmdir`/`symlink_to`，以及任何可写模式下的内置 `open()`。在所有这些陷阱之下反复调用
   `build_organize_plan`，它必须运行完成而不触发其中任何一个。一个自测（`test_blocked_mutation_trap_is_itself_effective`）
   证明陷阱机制本身确实能捕获真实的修改调用（沿用 C4 中 P4-C1 的 `UnguardedScheduler` 风格自测模式）。

## 15. 架构边界的证据

`test_planning_architecture.py`：对每个 `planning/*.py` 文件做静态 AST 扫描，禁止 `amane` 以及合同规格第 1 节中列出的
`fc2_metadata_core`/discovery 内部前缀；一个明确的允许列表检查，确认只 import 了 `fc2_metadata_core.models`/`.normalize`
以及裸的 `fc2_organizer.discovery` package；一个动态 meta-path 阻断，在该阻断下端到端运行 `build_organize_plan` 的同时，
证明即使是惰性 import 也无法加载 `amane`（关于该动态阻断为什么只覆盖 `amane` 而不覆盖 `fc2_metadata_core` 的内部实现，
见合同规格第 1 节 -- 那个边界改由静态检查覆盖，原因在于 `fc2_metadata_core` 自身的 `__init__.py` 的结构）；确认 `amane`
实际上没有安装在本环境中（确认阻断是有意义的）；以及一个作用域守卫，确认 `fc2_organizer` 现在恰好有 `{discovery, planning}`
这两个子 package。

## 16. 针对性测试

```bash
# From fc2-organizer/:
python -m pytest tests/unit/planning tests/contract/test_planning_architecture.py -q
```

```text
179 passed
```

（同时还重新运行了 `tests/contract/test_discovery_architecture.py` --
所有原有的 P4-C1 架构测试在那一处更新过的断言下仍然通过，见第 4 节。）

## 17. 全量测试

```bash
python -m pytest -q
```

```text
2659 passed, 4 skipped
```

`2480 (P4-C1 final-closure baseline) + 179 (new P4-C2 tests) = 2659`。除了第 4 节中的那一个断言之外，没有任何原有测试被修改，
没有任何原有测试新出现失败，4 个跳过项与 P4-C1 中已有的 Windows symlink 权限跳过相同（不受影响，原因未变）。

（在本环境中使用 `--basetemp=<dir>`，只是为了避免 P4-C1 handoff 中记录过的同一个 pytest 内部清理竞争（见那里的第 9 节），
即共享的 `%TEMP%\pytest-of-<user>` 目录问题 -- 与测试本身无关。）

## 18. 合成计划门槛

```text
PASS
```

`test_planning_synthetic_gate.py` 在一个固定的（非随机）布局上完全离线地构建 400 个合成的
`DiscoveredMediaItem`，覆盖 7 种扩展名、400 个不同的规范 FC2 番号以及 5 个 Unicode / emoji 标题。验证：完整的重放确定性
（构建两次，断言 `==`）、每一个生成路径的完整目标包含关系、全部 400 个唯一番号计划的媒体目标之间零内部冲突、Unicode 标题
零泄漏到任何目标路径、在自定义 `OutputPolicy` 下的正确性（包含关系 + 确定性仍然成立）、零文件系统修改（库根目录从未被创建），
以及（通过对 `planning/` 源码树的专门 AST 扫描）不存在任何可达的 `socket`/`httpx`/
`urllib`/`requests`/`asyncio` import。

## 19. 已知局限

* **`fc2_organizer/__init__.py` 不会急切地 import `planning`。** 这是在开发过程中发现的一个真实回归（而不仅仅是事先做出的
  设计选择）：该文件的第一个版本写的是 `from fc2_organizer import discovery, planning`，这破坏了 P4-C1 自己冻结的
  `test_discover_media_runs_end_to_end_with_forbidden_modules_blocked_at_runtime` 测试，因为 `fc2_metadata_core` 自己的
  `__init__.py` 只要它的*任何*一个子模块（包括允许使用的 `models`）被 import，就会急切地 import
  `aggregation`/`batch`/`http`/`sources` -- 因此从 `fc2_organizer/__init__.py` 急切地 import `planning`，会让仅仅 import
  `fc2_organizer.discovery` 就触发那次传递加载。修复方式是不急切地 import `planning`；通过
  `from fc2_organizer import planning`（一个普通的、显式的子 package import）使用它。这一点记录在合同规格第 1 节和本文件中，
  以免将来的 package 重新引入同样的回归。
* 没有交叉检查 `metadata.number == canonical_number`。v1.0 默认的路径推导根本不读取 `metadata.number`（只检查
  `meets_minimum_success()`），因此调用方理论上可以传入与 `canonical_number` 番号不同的 metadata；P4-C2 不把这视为计划错误，
  因为简报中没有任何内容要求这样做，而且生成的计划仍然是内部一致的（它针对 `canonical_number` 正确地做出计划，而它就是这里的
  权威身份）。是否应将其变为错误，留待将来的轮次决定。
* `OrganizePlan` 不携带用于构建它的 `OutputPolicy`。简报中“至少包括”的字段列表（任务第 6 节）并不要求它；刻意省略，
  以避免把计划的职责扩大到超出要求的范围。
* 不做任何形式的真实文件系统预检（检测已存在的文件、探测可写性）-- 按照设计，这是 P4-C2 的核心约束
  （ZERO FILESYSTEM MUTATION），而不是疏忽；按简报推迟到将来的执行 package。

## 20. 延续的债务（P4-C2 未触发 / 未处理）

```text
P4-C1-R-02, P4-C1-R-03, P4-C1-R-04, P4-C1-R-05,
C2-L2, P2-R-05, P2-R-06, P2-R-07, P2-R-10,
C3-N1, C3-N2, C3-N3, C3-N4,
C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3,
F3, F5, C5-R1-L1
```

这些债务都没有被读取、触碰，也与本 package 无关：`fc2_organizer.planning` 对它们所涉及的任何模块都没有运行时依赖（它对
`fc2_metadata_core` 的唯一依赖是只读的 `models`/`normalize` 边界；它对 `batch`、`aggregation`、
`resource_control`、`sources` 或 `http` 零依赖）。开发过程中没有触发任何一项；也没有修复、升级或重新打开任何一项。

## 21. `git diff --check`

```text
clean (no output)
```

## 22. `git status --porcelain`

代码提交之后是干净的；本次 docs 提交之后再次是干净的（用 `git status --porcelain` 验证 -- 本文件提交后预期为空）。

## 23. 推送

在 docs 提交之后推送到 `origin/claude/phase4-c2-organize-plan`；推送后会在上面记录 Remote Head。

## 24. 独立复查

```text
REQUIRED
```

## 25. P4-C2

```text
NOT CLOSED
```

## 26. Phase 4

```text
NOT CLOSED
```

---

# R1 关闭 -- P4-C2-GOV-01、P4-C2-GOV-02、P4-C2-GOV-03

上面的部分是原始的、经过复查的 P4-C2 提交，为保留历史而不做修改。本节记录 R1 增量关闭轮次。

## R1.1 坐标

```text
Reviewed-Failed Code Head = 1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8
Previous Docs Head        = e8ebd153b2160f3dfc812668c34cc8e382614ee4
R1 Code Review Candidate  = d43608645a960401c0cf0cc03d56418bdfa760be
R1 Docs Head              = <this commit; see git log after commit>
R1 Code Review Range      = e8ebd153b2160f3dfc812668c34cc8e382614ee4..d43608645a960401c0cf0cc03d56418bdfa760be
R1 Docs Review Range      = d43608645a960401c0cf0cc03d56418bdfa760be..<R1 Docs Head>
```

## R1.2 治理背景

两份独立的 Level 1 复查在 finding 的严重程度上存在冲突。按照下发的指示，本轮不以任何一位复查者自己的 finding 编号为依据；
只以指示本身规定为经过裁决的、权威关闭范围的三个 GOV finding 为依据：

```text
P4-C2-GOV-01   HIGH / BLOCKING            -- vacuous synthetic-gate network-isolation test
P4-C2-GOV-02   MEDIUM / CLOSURE-REQUIRED  -- legitimate absolute roots wrongly judged "escaped"
P4-C2-GOV-03   MEDIUM / CLOSURE-REQUIRED  -- ambiguous Windows rooted-but-driveless library_root
```

## R1.3 处理的 finding

### P4-C2-GOV-01 -- CLOSED

**缺陷：** `test_planning_synthetic_gate.py::test_synthetic_gate_no_network_import_reachable`
把它的生产源码目录计算为
`Path(__file__).resolve().parents[2] / "src" / "fc2_organizer" / "planning"`。
该文件位于 `tests/unit/planning/test_planning_synthetic_gate.py`；从那里算起的 `parents[2]` 是 `tests/`（浅了一层 -- 数值
`2` 是从 `tests/contract/test_planning_architecture.py` 复制过来的，那个文件*确实*浅一层，在那里 `parents[2]` 正确地解析到
仓库根目录）。因此计算出的路径是不存在的 `tests/src/fc2_organizer/planning`；`rglob("*.py")` 悄悄返回了空列表，
`for path in ...: assert ...` 的循环体从未执行 -- 这是一个无论生产代码实际 import 了什么都总是通过的空洞测试。

**修复：** 把下标修正为 `parents[3]`（已直接验证，R1.5 Repro A）。新增
`test_synthetic_gate_planning_src_root_resolves_and_has_production_files`，断言解析出的目录存在、`rglob("*.py")`
返回非空的文件列表，并且该列表按名称包含每一个已知的生产模块（`__init__.py`、`errors.py`、`models.py`、`paths.py`、
`planner.py`、`policy.py`）-- 这样将来如果意外再次引入同样的差一错误，会被一个明确的断言捕获，而不仅仅依赖守卫“碰巧”扫描到了
正确的文件。把 AST 遍历扫描本身抽取为一个小的、可复用的纯函数（`_scan_forbidden_imports`），然后新增了两个植入 import 的
证明测试（`test_network_guard_fails_on_planted_import_statement`、
`test_network_guard_fails_on_planted_import_from_form`），它们把 `import
socket` / `from urllib import request` 写入一个隔离的 `tmp_path` 文件（从不是生产文件），并断言扫描器能检测到 --
证明该守卫确实能够 FAIL，而不仅仅证明它在今天恰好干净的代码上 PASSes。又新增了第四个测试
（`test_network_guard_does_not_false_positive_on_ordinary_stdlib_imports`），证明同一个扫描器不会把本 package 自己也在使用的
普通允许 import（`os`、`pathlib`、`dataclasses`、`enum`）误报出来。

**没有为了让它通过而修改任何生产代码** -- 两位原始的独立复查者都已确认 `fc2_organizer.planning` 没有真实的网络依赖；
这纯粹是测试证据层面的缺陷，正如下发的指示所定性的那样。

### P4-C2-GOV-02 -- CLOSED

**缺陷：** `fc2_organizer.planning.paths.is_contained_within` 通过
`os.path.normpath(candidate_or_root).split(os.sep)` 计算路径段。裸盘符根目录（`C:\`）或裸 UNC 共享根目录
（`\\server\share\`）规范化后得到的字符串*以*分隔符结尾；在 `os.sep` 上切分会产生一个多余的结尾空字符串段，抬高了根目录的段数。
包含关系检查的提前退出守卫
（`len(candidate_parts) <= len(root_parts): return False`）于是仅仅因为那个额外的幽灵段，就对一个*真正的*子路径
（`C:\` 之下的 `C:\library-child`）触发了 -- 对一个完全合法的绝对根目录给出了错误的“目标逃出根目录”判定。

**修复：** `is_contained_within` 现在通过 `pathlib.Path(...).parts` 计算路径段，而不是 `os.path.normpath(...).split(os.sep)`。
无论字符串是否带有结尾分隔符，`pathlib` 都会把盘符加根目录（`C:\` -> `('C:\\',)`）或 UNC 共享加根目录
（`\\server\share\` -> `('\\\\server\\share\\',)`）合并为*一个*锚点段，不存在结尾空段的伪影。这仍然是纯词法的
（`Path` 的构造和 `.parts` 都不做任何文件系统访问 -- 没有 `stat`/`exists`/`resolve`），并且仍然基于路径段，而不是
`str.startswith`（因此 `C:\library2` 仍然被正确地判定为*不*包含在 `C:\library` 之下 -- 已验证未变，
`test_prefix_collision_without_separator_boundary_is_not_contained` 以及新增的
`test_no_string_startswith_false_positive_on_drive_root`）。

已直接复现并修复（R1.5 Repro C）：`C:\` 现在正确地包含
`C:\FC2-1234567` 和 `C:\FC2-1234567\poster.jpg`；`D:\FC2-1234567` 被正确地排除在 `C:\` 之外；`\\server\share\` 正确地包含
`\\server\share\FC2-1234567`；`\\server\other\FC2-1234567` 被正确地排除。

### P4-C2-GOV-03 -- CLOSED

**治理决定（由本轮冻结，依据下发的指示）：** P4-C2 v1.0 的 `library_root` 必须是一个**无歧义、完全限定的绝对路径**。
Windows 的*有根但无盘符*形式（`\lib`、`/lib`）以 fail-closed 方式拒绝，绝不会被悄悄绑定到恰好处于当前状态的盘符，
也绝不依据 `os.path.isabs()` 自身在不同 Python 版本之间对这种形式的处理来判断。

**修复：** 新增 `fc2_organizer.planning.paths.is_fully_qualified_absolute_root`，作为唯一的、集中的库根目录资格边界（合同
第 11a 节）：

* **Windows**（`os.name == "nt"`）：只有当 `os.path.splitdrive` 找到带根目录的真实盘符（`C:\lib`、`C:/lib`）或 UNC 共享
  （`\\server\share`、`\\server\share\lib`，带或不带结尾分隔符 -- 裸共享本身已经无歧义，这与单独的裸盘符 `C:` 不同，后者表示
  “该盘符上的当前目录”，会被拒绝）时才接受。拒绝：`library`、`.\library`、`..\library`、`C:library`、
  `\library`、`/library`。
* **POSIX**（其他所有情况，按*当前运行时操作系统*选择，绝不根据字符串的形态猜测）：普通的 `os.path.isabs(path)` --
  `/library` 仍然合法，`library` 仍然被拒绝。

同时接入 `planner.py`（`InvalidLibraryRootError`，取代裸的 `os.path.isabs()` 调用）以及 `models.py` 中对
`OrganizePlan.library_root` 的冗余模型层检查（`OrganizePlanContractError`），与已经用于目标包含关系（第 11 节）以及 P4-C1-R-01
中 `DiscoveredMediaItem.source_path` 的双层模式一致。

已直接复现（R1.5 Repro D）：`\lib` 和 `/lib` 都被 `is_fully_qualified_absolute_root` 以及 `build_organize_plan` 本身拒绝
（抛出 `InvalidLibraryRootError`）；`C:\lib` 和 `\\server\share\lib` 都被接受；`build_organize_plan(..., library_root="C:\\")`
（GOV-02/GOV-03 的确切边界情况）端到端成功，并产生 `target_directory == "C:\\FC2-1234567"`。

## R1.4 确切的变更文件

**R1 Code Review Candidate（`d436086`），8 个文件，全部为修改（没有新文件，没有重命名）：**

```text
fc2-organizer/docs/specifications/PHASE4_ORGANIZE_PLAN_CONTRACT.md    (M)
fc2-organizer/src/fc2_organizer/planning/models.py                    (M)
fc2-organizer/src/fc2_organizer/planning/paths.py                     (M)
fc2-organizer/src/fc2_organizer/planning/planner.py                   (M)
fc2-organizer/tests/unit/planning/test_planning_models.py             (M)
fc2-organizer/tests/unit/planning/test_planning_paths.py              (M)
fc2-organizer/tests/unit/planning/test_planning_planner.py            (M)
fc2-organizer/tests/unit/planning/test_planning_synthetic_gate.py     (M)
```

`fc2_metadata_core/**` 或 `fc2_organizer/discovery/**` 下的任何文件都没有被触碰。没有新增任何源文件（简报允许“在必要时，
尽量精简地”新增一个路径 / 根目录 helper -- `is_fully_qualified_absolute_root` 是作为一个新*函数*加在本来就存在、本来就是
集中位置的 `paths.py` 中，而不是作为一个新模块）。

**R1 Docs Head（本提交），1 个文件：**

```text
fc2-organizer/docs/review/P4_C2_HANDOFF.md   (M -- this section)
```

## R1.5 直接复现（在 pytest 之外）

```text
Repro A -- network guard scans real production files:
  planning src root resolved correctly (parents[3], not parents[2])
  production file count: 6 (__init__.py, errors.py, models.py, paths.py,
  planner.py, policy.py)
  -> PASS

Repro B -- planted 'import socket' causes guard FAIL:
  planted into an isolated tempfile.TemporaryDirectory() file (never a
  repo file); _scan_forbidden_imports([planted], ...) returned one
  violation naming 'socket'
  -> PASS (guard detects a real violation, not just passes on clean code)
  temp directory auto-cleaned by the context manager; git status
  confirmed clean immediately after (no leftover modification)

Repro C -- Windows drive-root / UNC containment:
  is_contained_within(r"C:\FC2-1234567", r"C:\\")                -> True
  is_contained_within(r"C:\library-child", r"C:\\")               -> True  (exact GOV-02 repro)
  is_contained_within(r"D:\FC2-1234567", r"C:\\")                  -> False
  is_contained_within(r"\\server\share\FC2-1234567", r"\\server\share\\") -> True
  is_contained_within(r"\\server\other\FC2-1234567", r"\\server\share\\") -> False
  -> PASS

Repro D -- Windows rooted-but-driveless root fails closed:
  is_fully_qualified_absolute_root(r"\lib")          -> False
  is_fully_qualified_absolute_root("/lib")            -> False
  is_fully_qualified_absolute_root(r"C:\lib")         -> True
  is_fully_qualified_absolute_root(r"\\server\share\lib") -> True
  build_organize_plan(..., library_root=r"\lib")      -> raises InvalidLibraryRootError
  build_organize_plan(..., library_root="C:\\")       -> succeeds;
    target_directory.absolute_path == "C:\\FC2-1234567"
  -> PASS
```

本主机是 Windows（win32，Python 3.12.10），因此上面的 Repro A-D 都真实运行了。R1 中新增的 POSIX 一侧单元测试覆盖
（`is_fully_qualified_absolute_root` 的 POSIX 绝对路径接受 / 相对路径拒绝 / 点开头相对路径拒绝，以及
`build_organize_plan` 的 `test_posix_absolute_root_still_accepted`）存在且正确，但在本主机上 **NOT RUN**
（`pytest.mark.skipif(os.name
== "nt", ...)`）；依照下发指示对这种情况的明确许可，这些覆盖存在并且正确地按平台门控，而不是在这里执行。

## R1.6 针对性测试

```text
212 passed, 4 skipped
```

命令：`python -m pytest tests/unit/planning tests/contract/test_planning_architecture.py -q`
（179 个之前的 P4-C2 测试 + 33 个新增通过的测试 + 4 个新增的仅 POSIX 跳过，全部通过；这 4 个跳过是新增的 POSIX 门控测试，
在这台 Windows 主机上正确地不执行 -- 与全量测试中原有的 P4-C1 symlink 权限跳过不是同一批，见 R1.7）。

## R1.7 全量测试

```text
2692 passed, 8 skipped
```

命令：`python -m pytest -q`。`2659 (original P4-C2 submission baseline)
+ 33 (new R1 tests, passing on this host) = 2692`；`4 (pre-existing P4-C1
symlink-privilege skips) + 4 (new R1 POSIX-gated skips on this Windows
host) = 8`。没有任何原有测试被修改、新出现失败，或因不同于以往的原因被新跳过。

## R1.8 P4-C1 的冻结保护

`src/fc2_organizer/discovery/**` 或 `src/fc2_metadata_core/**` 下的任何文件都没有为了修改而被读取，也都没有被触碰。
全量测试中未改变的 P4-C1 测试数量和通过状态（第 R1.7 节）是行为层面的证明；R1 提交之后的 `git status --porcelain`
（第 R1.11 节）是文件层面的证明。

## R1.9 保持不变的行为（没有回归）

通过未修改、仍然 still-100%-green 的 R1 之前的测试文件（`test_planning_models.py` 的不可变性测试、`test_planning_planner.py` 的
规范番号 / metadata / 来源身份 / 默认布局 / 标题隔离 / 策略 / 冲突 / 覆盖 / 确定性测试、`test_planning_no_mutation.py`、
`test_planning_architecture.py` 的依赖边界测试）以及全量回归计数验证：深度不可变、规范番号边界、metadata 最低成功标准校验、
来源身份、默认布局、标题隔离、`OutputPolicy` artifact 命名、Collision = FAIL CLOSED、Overwrite = NEVER（冻结，没有新增字段 /
参数 -- 已直接重新验证，`test_overwrite_policy_is_frozen_never_and_not_a_caller_knob` 仍然原样通过）、Windows 组件校验、
不修改文件系统、与文件系统状态无关、架构边界、package import 安全、确定性 -- 全部未改变，没有任何一项被削弱或改变范围。

## R1.10 延续的 finding（本轮明确不处理）

```text
metadata.number != canonical_number identity gap
  -> CARRIED (frozen contract section 9 defines metadata as validation-only;
     no cross-check added; must close before OrganizePlan/metadata/NFO
     publication binding)

OrganizePlan operation-graph model-level hardening
  -> CARRIED (executor-entry hardening, deferred to when an executor
     actually consumes an arbitrary OrganizePlan)

overwrite executor semantics
  -> frozen NEVER (unchanged); a future executor must enforce it;
     not a P4-C2 plan-field defect, no field/parameter added this round

CON.txt / COM(super-1).jpg style contract-external Windows edge cases
  -> not addressed (out of the frozen contract's scope, per the issuing
     instruction; not touched)

All prior carried debts unchanged:
P4-C1-R-02, P4-C1-R-03, P4-C1-R-04, P4-C1-R-05,
C2-L2, P2-R-05, P2-R-06, P2-R-07, P2-R-10,
C3-N1, C3-N2, C3-N3, C3-N4,
C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3,
F3, F5, C5-R1-L1
```

## R1.11 `git diff --check`

```text
clean (no output)
```

## R1.12 `git status --porcelain`

R1 代码提交之后是干净的；本次 R1 docs 提交之后再次是干净的（用 `git status --porcelain` 验证）。没有残留文件
（开发期间使用的 `_tmp_probe*.py`、`_tmp_repro.py` 在两次提交之前都已删除，从未被暂存）。

## R1.13 独立 R1 关闭复查

```text
REQUIRED
```

## R1.14 P4-C2

```text
NOT CLOSED
```

## R1.15 Phase 4

```text
NOT CLOSED
```

---

# R2 关闭 -- P4-C2-R1-01

上面的两部分（原始 P4-C2、R1）为保留历史而不做修改。本节记录 R2 增量关闭轮次。

## R2.1 坐标

```text
R1 Reviewed-Failed Code Head = d43608645a960401c0cf0cc03d56418bdfa760be
Previous Docs Head           = bb8b78ffabf2b4a66c342813b089675b08b29d78
R2 Code Review Candidate     = f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7
R2 Docs Head                 = <this commit; see git log after commit>
R2 Code Review Range         = bb8b78ffabf2b4a66c342813b089675b08b29d78..f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7
R2 Docs Review Range         = f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7..<R2 Docs Head>
```

```text
P4-C2-GOV-01: REMAINS CLOSED (reverified, R2.5)
P4-C2-GOV-02: REMAINS CLOSED (reverified, R2.5)
P4-C2-GOV-03: REMAINS CLOSED (reverified, R2.5)
P4-C2-R1-01:  CLOSED by this round (R2.5 Repro A/C/D)
```

## R2.2 处理的 finding

```text
P4-C2-R1-01
Severity: HIGH / BLOCKING
```

**缺陷：** R1 为修复 P4-C2-GOV-02，把
`fc2_organizer.planning.paths.is_contained_within` 从
`os.path.normpath(...).split(os.sep)` 改为 `pathlib.Path(...).parts`，以修复裸盘符 / UNC 根目录上的结尾空段 bug。
然而，`pathlib.PurePath.parts` 是一个纯字符串切分操作 -- 它**不会**折叠 `.`/`..` 段。因此，一个*原始*路径段恰好以根目录的
路径段开头的候选路径，即使其实际的词法含义（把 `..` 考虑进去后解析到的位置）完全逃出了根目录，也会被判定为“包含”：

```text
root:      C:\library
candidate: C:\library\..\outside\FC2-1234567.mp4

R1's Path(...).parts comparison: ('C:\\', 'library', 'outside_wrongly_seen_as_child')
  -- wrong: raw segments ('C:\\', 'library', '..', 'outside', 'FC2-1234567.mp4')
     happen to start with the root's ('C:\\', 'library'), so the naive
     comparison said "contained" == True

actual lexical meaning: C:\outside\FC2-1234567.mp4 -- outside C:\library entirely
```

同样的风险也存在于 `C:\library\FC2-1\..\..\outside\...` 以及 POSIX 上等价的 `/library/../outside/file`。

## R2.3 确切的变更文件

```text
fc2-organizer/src/fc2_organizer/planning/paths.py                     (M)
fc2-organizer/tests/unit/planning/test_planning_paths.py              (M)
fc2-organizer/tests/unit/planning/test_planning_models.py             (M)
fc2-organizer/docs/review/P4_C2_HANDOFF.md                            (this section)
```

`planner.py`、`models.py`（测试文件除外）、`policy.py`、`errors.py` 都**没有**被触碰 -- 缺陷及其修复完全局限在
`paths.is_contained_within` 自己的路径段计算逻辑之内；公开 API、错误分类或默认布局都没有任何改变。
`PHASE4_ORGANIZE_PLAN_CONTRACT.md` 本轮**没有**被触碰：它的第 11 节本来就承诺了纯词法的包含关系检查以及独立的模型层再检查；
这两项承诺都没有改变，改变的只是实现履行它们的正确性。

## R2.4 先规范化再切分的策略

```python
candidate_parts = Path(os.path.normpath(candidate)).parts
root_parts = Path(os.path.normpath(root)).parts
```

在切分为路径段*之前*，对**两个**字符串都运行 `os.path.normpath`。这样组合起来可以同时修复两种风险，而不会重新引入其中任何一种：

* **R1-01 的风险**（未折叠的 `.`/`..`）被关闭，因为 `normpath` 会先在词法上折叠 `.`/`..` -- 仍然是纯字符串操作，零文件系统访问
  （没有 `stat`/`exists`/`resolve`/`realpath`）。
* **GOV-02 原来的风险**（裸锚点的结尾分隔符产生一个多余的空 `str.split(os.sep)` 段）*没有*被重新引入，因为修复从不回到普通的
  `str.split(os.sep)` -- 实际的切分仍然使用 `Path(...).parts`，而 `normpath` 永远不会让裸根目录的结尾分隔符以一种会破坏
  `Path.parts` 锚点合并的形式留下（`os.path.normpath("C:\\\\")` 是 `"C:\\"`，
  `Path("C:\\").parts` 是 `('C:\\',)`，与 R1 的行为相同）。

**锚点钳制已直接验证**（而不是假定）：`os.path.normpath` 在盘符或 UNC 共享锚点处钳制前导 `..` 的方式，与真实的 Windows 路径解析
完全相同 --
`os.path.normpath(r"\\server\share\..\other\x")` 得到
`\\server\share\other\x`（停留在该共享**之内**），而绝不是
`\\server\other\x`（那会是另一个共享）。这与 P4-C1-R2-01/R3 轮次通过独立的 `GetFullPathNameW` 验证为本项目已经确立的
盘符根目录 `..` 钳制先例一致（P4-C1 handoff 的 R3.5）-- 在 Windows 上，`..` 无法越过盘符或 UNC 共享的边界，这是由操作系统
自身的词法规则决定的，而不仅仅是本 package 的约定。

**对“不同共享”这一测试列表项的影响：** 因此，简报第 7 节中的 UNC 示例（`\\server\share\..\other\FC2-1234567`）被*正确地*
判定为**包含**（它真实的词法含义停留在 `share` 之内，实际上从未到达 `other`）-- 在真正的 Windows 词法语义下这是正确答案，
而不是一次逃逸被错误地接受。一个**从一开始**就指向真正不同共享的候选路径（`\\server\other\FC2-1234567`，从未经由 `..` 到达）
仍然被正确拒绝，与 GOV-02 相同（`test_different_unc_share_from_the_start_is_still_not_contained`）。

## R2.5 直接复现（在 pytest 之外）

```text
Repro A -- dot-dot escape correctly rejected:
  is_contained_within(r"C:\library\..\outside\file.mp4", r"C:\library") -> False
  -> PASS (P4-C2-R1-01 closed)

Repro B -- bare drive root still correctly contains its child (GOV-02 not regressed):
  is_contained_within(r"C:\FC2-1234567", "C:\\") -> True
  -> PASS

Repro C -- UNC root child / different share:
  is_contained_within(r"\\server\share\FC2-1234567", "\\server\share\") -> True
  is_contained_within(r"\\server\other\FC2-1234567", "\\server\share\") -> False
  is_contained_within(r"\\server\share\a\..\FC2-1234567", "\\server\share\") -> True
  is_contained_within(r"\\server\share\..\other\FC2-1234567", "\\server\share\") -> True
    (clamped at the share boundary -- see R2.4; this is the lexically
    correct verdict, not a residual defect)
  -> PASS

Repro D -- hand-built OrganizePlan with dot-dot-escaping target fails closed:
  OrganizePlan(..., target_media_path=PlannedPath(r"C:\library\..\outside\FC2-1234567.mp4"), ...)
  -> raised TargetEscapesLibraryRootError:
     "OrganizePlan.target_media_path ('C:\\library\\..\\outside\\FC2-1234567.mp4')
      is not contained under library_root ('C:\\library')"
  -> PASS (contract section 11's promised model-layer re-check verified for real)

Repro E -- POSIX /library/../outside:
  Host is Windows (os.name == 'nt') -> NOT RUN as a live filesystem-path
  reproduction on this host, honestly reported. Platform-correct pure-
  semantics unit coverage exists instead
  (TestIsContainedWithinPosixDotDot, 4 tests, @pytest.mark.skipif(os.name
  == "nt", ...)) and will execute for real with no code change required on
  a POSIX host. Sanity-checked by source inspection that
  is_contained_within's implementation calls the OS-native
  os.path.normpath (which dispatches to posixpath.normpath on a real
  POSIX host), not a Windows-only helper.
```

本主机是 Windows（win32，Python 3.12.10），因此 Repro A-D 都真实运行了；Repro E 的平台特定运行时执行如实报告为
NOT RUN，并已有等价的覆盖，依照下发指示的明确许可。

## R2.6 针对性测试

```text
223 passed, 10 skipped
```

命令：`python -m pytest tests/unit/planning tests/contract/test_planning_architecture.py -q`
（212 个之前的测试 + 11 个新增通过的测试 + 6 个新增的 POSIX 门控跳过，全部通过；10 个跳过 = R1 中已有的 4 个 POSIX 门控跳过 +
R2 新增的 6 个 POSIX 门控跳过，在这台 Windows 主机上都正确地不执行）。

## R2.7 全量测试

```text
2703 passed, 14 skipped
```

命令：`python -m pytest -q`。`2692 (R1 full-suite baseline) + 11 (new
R2 tests, passing on this host) = 2703`；`8 (R1 baseline skips) + 6 (new
R2 POSIX-gated skips) = 14`。没有任何原有测试被修改、新出现失败，或因不同于以往的原因被新跳过。

## R2.8 重新验证 GOV-01/02/03 未变

* **GOV-01（网络守卫）：** 本轮没有触碰 --
  `test_planning_synthetic_gate.py` 不在 R2 的变更文件列表中（第 R2.3 节）。全量测试的通过数确认
  `test_synthetic_gate_no_network_import_reachable` 及其植入 import 的证明测试仍然通过。
* **GOV-02（盘符 / UNC 包含关系）：** 已直接重新验证，R2.5 Repro B/C
  -- GOV-02 的确切复现（`C:\` 包含 `C:\FC2-1234567`；`\\server\share\` 包含其子路径；不同的盘符 / 共享被排除）仍然通过，
  现在与 R1-01 的点段折叠修复组合在一起，而不是被它取代。
* **GOV-03（完全限定的 library_root 边界）：** 本轮没有触碰
  -- `is_fully_qualified_absolute_root` 没有被修改；它自己的测试类（`TestIsFullyQualifiedAbsoluteRoot`）以及 planner 层面的测试
  都没有改变，并在全量运行中仍然通过。

## R2.9 保持不变的行为（没有回归）

与 R1.9 相同的检查清单，通过全量回归计数重新验证：深度不可变、规范番号边界、metadata 最低成功标准校验、来源身份、默认布局、
标题隔离、`OutputPolicy` artifact 命名、Collision = FAIL CLOSED、Overwrite = NEVER（冻结，没有新增字段 / 参数）、Windows 组件校验、
不修改文件系统、与文件系统状态无关、架构边界、package import 安全、确定性 -- 全部未改变。`build_organize_plan` 本身在本轮
没有被修改（第 R2.3 节）；相同的输入继续产生相同的计划，每个计划的目标继续被包含（现有的 planner 层面测试未经修改仍然通过）
-- R1-01 缺陷只能通过*手工构建的* `OrganizePlan` 或直接调用 `is_contained_within` 触发，从不能通过公开的
`build_organize_plan` 入口触发，因为它用来构建路径的每一个调用方可控组件，在拼接之前都已经被校验为不含分隔符 / `..`
（`validate_path_component`）。因此不需要新的 planner 层面测试来证明那里没有回归；这个缺陷实际可能出现的地方是模型层和
helper 层的测试。

## R2.10 延续的 finding（本轮明确不处理）

```text
P4-C2-R1-02
  -> CARRIED / LOW (bare "\\server" may be accepted by
     is_fully_qualified_absolute_root; not touched -- GOV-03's
     implementation was not modified this round, so this behavior is
     unchanged from R1)

metadata.number != canonical_number identity gap
  -> CARRIED (contract section 9 defines metadata as validation-only;
     must close before OrganizePlan/metadata/NFO publication binding)

OrganizePlan operation-graph model-level hardening
  -> CARRIED (executor-entry hardening, deferred to when an executor
     actually consumes an arbitrary OrganizePlan)

overwrite executor semantics
  -> frozen NEVER (unchanged); a future executor must enforce it; not a
     P4-C2 plan-field defect, no field/parameter added this round

CON.txt / COM(super-1).jpg style contract-external Windows edge cases
  -> not addressed (out of the frozen contract's scope)

All prior carried debts unchanged:
P4-C1-R-02, P4-C1-R-03, P4-C1-R-04, P4-C1-R-05,
C2-L2, P2-R-05, P2-R-06, P2-R-07, P2-R-10,
C3-N1, C3-N2, C3-N3, C3-N4,
C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3,
F3, F5, C5-R1-L1
```

## R2.11 `git diff --check`

```text
clean (no output)
```

## R2.12 `git status --porcelain`

R2 代码提交之后是干净的；本次 R2 docs 提交之后再次是干净的（用 `git status --porcelain` 验证）。没有残留文件
（开发期间使用的 `_tmp_probe_r2.py`、`_tmp_repro_r2.py` 在两次提交之前都已删除，从未被暂存）。

## R2.13 独立 R2 关闭复查

```text
REQUIRED
```

## R2.14 P4-C2

```text
NOT CLOSED
```

## R2.15 Phase 4

```text
NOT CLOSED
```

---

# 最终关闭 -- P4-C2

上面的各部分（原始 P4-C2、R1、R2）为保留历史而不做修改。本节是对最终独立关闭决定的纯文档治理记录；它不引入任何代码或测试
改动，除了 R1/R2 已经确立的内容之外，也不冻结任何新的技术声明。

```text
Phase:                       4
Package:                     P4-C2 Immutable Organize Plan
Status:                      CLOSED
Final Level:                 Level 1 PASS
Final Reviewed Code Head:    f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7
Previous Docs Head:          fa2655408f6cff8e2376d90b953cb477b16c084d
```

## 最终 finding 处置

```text
P4-C2-GOV-01   CLOSED
P4-C2-GOV-02   CLOSED
P4-C2-GOV-03   CLOSED
P4-C2-R1-01    CLOSED

P4-C2-R1-02    CARRIED / LOW / non-blocking
```

**所有阻塞性的 P4-C2 finding 均已关闭。其余 finding 被明确作为非阻塞项延续，或作为后续 package 的入口门槛保留** --
本次关闭没有修复、降级或重新打开它们；每一项涉及什么、为什么没有在本轮处理，见上文 R1.10/R1.11/R2.10 以及下文的
“Carried findings” 和 “Future entry gates”。

## 独立关闭证据

本轮 R2 获得了两份独立的 Level 1 复查输出。

**复查者 A -- PASS。** 直接运行了测试集并报告了真实数字：

```text
Targeted: 223 passed / 10 skipped
Full suite: 2703 passed / 14 skipped
```

并独立、实质性地验证了：普通根目录的点 / 点点包含关系（正是 P4-C2-R1-01 那一类缺陷）、盘符根目录的包含关系、UNC 根目录的
包含关系、修复所依赖的 Windows 词法 `normpath` 锚点钳制语义、在模型层拒绝手工构建的 `OrganizePlan` 的逃逸，以及网络守卫
（GOV-01）和完全限定根目录边界（GOV-03）仍然保持关闭且没有回归。

**复查者 B -- 实质结论 PASS，程序性结论 BLOCKED。**
这份复查自己对代码和 diff 的阅读得出了与复查者 A 相同的实质性结论：P4-C2-R1-01 已关闭，GOV-01/02/03 仍然关闭，没有新的
阻塞性代码 finding。然而，该复查者的执行环境中没有可用的本地仓库检出，因此它无法运行针对性的 pytest 测试集，无法运行完整的
pytest 测试集，也无法运行一次真正的本地 `git diff --check` -- 因此它自己的报告针对这些具体的、由环境造成的缺口，给出了一个
程序性的 `BLOCKED` 结论。

**这个 `BLOCKED` 结论是由复查者的执行环境造成的，而不是由代码或合同 finding 造成的。** 复查者 B 没有发现任何阻塞性的或必须
关闭的缺陷；该复查在代码层面的实质结论与复查者 A 相同，也是 PASS。

因此，关闭依据的是**一份具备执行能力的独立 Level 1
PASS**（复查者 A，带有真实的针对性 / 全量测试数字，并直接验证了与 R1-01 相关的每一项语义）**加上一份没有代码阻塞项的额外独立
实质性确认**（复查者 B），这与本项目针对此类轮次的阶段门槛治理一致：本轮改动范围很窄（一个函数的包含关系规范化逻辑及其回归测试），
而上一轮唯一延续下来的程序性问题（一个复查指令缺陷，关于这一类非实现性阻塞项，见 P4-C1 自己的 R1.1 先例）同样是环境性的，
而不是实质性的。

## 延续的 finding

```text
P4-C2-R1-02 -- LOW / CARRIED / non-blocking
  Bare "\\server" (no explicit share) may be accepted by
  is_fully_qualified_absolute_root. Not touched by R1 or R2 (GOV-03's
  implementation was not modified after R1). Carried forward unchanged.

metadata.number != canonical_number identity gap -- CARRIED
operation-graph model-level hardening -- CARRIED
overwrite executor semantics -- CARRIED / frozen NEVER
extended Windows reserved-name edge cases -- CARRIED
```

另外还有全部原有的项目延续债务，未改变：
`P4-C1-R-02`、`P4-C1-R-03`、`P4-C1-R-04`、`P4-C1-R-05`、`C2-L2`、`P2-R-05`、
`P2-R-06`、`P2-R-07`、`P2-R-10`、`C3-N1`、`C3-N2`、`C3-N3`、`C3-N4`、
`C4-N1`、`C4-R1-N1`、`C4-R1-N2`、`C4-R1-N3`、`F3`、`F5`、`C5-R1-L1`。

## 将来的入口门槛（必须在后续 package 之前解决，而不是由后续 package 解决）

```text
metadata.number != canonical_number identity gap
  Must be closed before the first package that actually binds OrganizePlan
  with NormalizedMetadata for NFO/artifact publication. Not a P4-C2
  defect: contract section 9 freezes metadata as validation-only for this
  package, and no cross-check was ever promised here.

OrganizePlan operation-graph model-level hardening
  Must be resolved before an executor accepts arbitrary or reconstructed
  OrganizePlan instances (as opposed to ones produced by
  build_organize_plan itself). Deferred as executor-entry hardening,
  out of scope for a pure planning package with no executor.

overwrite = NEVER
  Remains a frozen global execution semantic (contract section 12). It is
  not a caller-configurable field on OrganizePlan or OutputPolicy today,
  and P4-C2 performs no filesystem access to enforce it against. The
  future executor must enforce it fail-closed against the real
  filesystem; that enforcement does not exist yet anywhere in this
  codebase and is not claimed to.
```

## 本次关闭的范围

这只关闭 **P4-C2**（不可变整理计划）。它不关闭整个 Phase 4，也不授权开始 P4-C3 或任何其他后续的 Phase 4 package --
按照项目的阶段门槛治理，每一个都需要自己的冻结合同和自己的复查周期（与 P4-C1 自己的最终关闭所记录的边界相同）。

```text
Phase 4: NOT CLOSED
```

## 最终状态

```text
P4-C2: CLOSED
```
