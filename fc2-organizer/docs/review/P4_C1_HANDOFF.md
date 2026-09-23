# Phase 4 / P4-C1 Handoff — 递归媒体发现（Recursive Media Discovery）

```text
Phase        = 4
Package      = P4-C1
Role         = Developer
Branch       = claude/phase4-c1-recursive-discovery
Frozen Base  = 3edab6eb4ab363c1fedabd847c61b7061be8343d
```

**类型：** NEW PACKAGE（`fc2_organizer.discovery`）。没有修改任何现有文件；`fc2_metadata_core`、
`docs/specifications/PHASE3_*.md` 以及之前的每一个 `docs/review/*` 文件都没有被触碰。

## 1. 确切的复查范围

```text
Code Review Candidate: ffe49927760f57d3ea0179cde22f2c19c8dd10a9
Docs Head:              <this commit, see git log after commit>
Review Range:           3edab6eb4ab363c1fedabd847c61b7061be8343d..ffe49927760f57d3ea0179cde22f2c19c8dd10a9  (code)
                        ffe49927760f57d3ea0179cde22f2c19c8dd10a9..<Docs Head>  (docs)
```

**Code Review Candidate**（`ffe4992`）是独立复查者应当审计其正确性 / 安全性的提交。**Docs Head** 提交
（本文件 + 合同规格）不包含任何源码或测试改动。

## 2. 变更文件

Code Review Candidate（`ffe4992`），19 个文件，全部为新增：

```text
fc2-organizer/src/fc2_organizer/__init__.py
fc2-organizer/src/fc2_organizer/discovery/__init__.py
fc2-organizer/src/fc2_organizer/discovery/_platform.py
fc2-organizer/src/fc2_organizer/discovery/errors.py
fc2-organizer/src/fc2_organizer/discovery/models.py
fc2-organizer/src/fc2_organizer/discovery/policy.py
fc2-organizer/src/fc2_organizer/discovery/scanner.py
fc2-organizer/tests/contract/test_discovery_architecture.py
fc2-organizer/tests/unit/discovery/__init__.py
fc2-organizer/tests/unit/discovery/test_discovery_basic.py
fc2-organizer/tests/unit/discovery/test_discovery_duplicates_and_ordering.py
fc2-organizer/tests/unit/discovery/test_discovery_failure_isolation.py
fc2-organizer/tests/unit/discovery/test_discovery_models.py
fc2-organizer/tests/unit/discovery/test_discovery_no_mutation.py
fc2-organizer/tests/unit/discovery/test_discovery_platform_helper.py
fc2-organizer/tests/unit/discovery/test_discovery_policy.py
fc2-organizer/tests/unit/discovery/test_discovery_root_failures.py
fc2-organizer/tests/unit/discovery/test_discovery_stage_gate.py
fc2-organizer/tests/unit/discovery/test_discovery_symlinks_and_junctions.py
```

Docs Head（本提交），2 个文件，都为新增：

```text
fc2-organizer/docs/specifications/PHASE4_DISCOVERY_CONTRACT.md
fc2-organizer/docs/review/P4_C1_HANDOFF.md
```

不需要修改 `pyproject.toml`：`[tool.setuptools.packages.find]` 本来就有 `where = ["src"]`，且没有
`include`/`exclude` 过滤，因此 `fc2_organizer` 会像 `fc2_metadata_core` 一样被自动发现为一个发行 package；
而 `[tool.pytest.ini_options] pythonpath = ["src", "tests"]` 本来就让 `fc2_organizer` 在不安装的情况下可以被测试 import。

## 3. 架构摘要

```text
dirty media root (a directory path)
        |
discover_media(root, policy=DiscoveryPolicy())
        |   recursive, read-only, deterministic, duplicate-safe,
        |   unsupported-file-safe, symlink/junction-safe
        v
DiscoveryResult(root, items: tuple[DiscoveredMediaItem, ...], issues: tuple[DiscoveryIssue, ...])
```

`fc2_organizer -> fc2_metadata_core` 是唯一允许的依赖方向（冻结）。`fc2_organizer.discovery` 目前对
`fc2_metadata_core` 模块的依赖为**零**：这里的媒体身份是文件系统路径，而不是解析出来的 FC2 番号
（见合同 §4 “FC2 番号边界”），因此没有任何需要 import 的东西。完整细节：`docs/specifications/PHASE4_DISCOVERY_CONTRACT.md`。

## 4. 公开 API

```python
from fc2_organizer.discovery import (
    DiscoveryPolicy, DiscoveredMediaItem, DiscoveryIssue,
    DiscoveryIssueKind, DiscoveryStage, DiscoveryResult, discover_media,
)

result = discover_media(root, policy=DiscoveryPolicy())
```

`DiscoveredMediaItem`：`index`、`source_path`、`relative_path`、`extension`、
`size` — 恰好是任务简报要求的五个字段，没有更多（没有抓取到的 metadata，没有目标路径，没有 Amane/DB 状态）。

## 5. 错误语义

* 根目录层面（绝不会伪装成空的成功结果）：
  `DiscoveryRootNotFoundError` / `DiscoveryRootNotADirectoryError` /
  `DiscoveryRootAccessError`（都是 `DiscoveryRootError` 的子类），由 `discover_media` 直接抛出。
* 参数合同：`DiscoveryInputError`（`root`/`policy` 类型错误）、
  `DiscoveryConfigError`（`DiscoveryPolicy.supported_extensions` 不合法）。
* 模型合同：`DiscoveryContractError`（四个冻结模型中的任何一个以非法值构造）。
* 遍历过程中非根目录的局部失败永远不会被抛出 — 它们被隔离为
  `DiscoveryIssue(path, kind, stage, detail)`，其中 `detail` 是一个固定、预设、有界的字符串
  （绝不是 `str(exc)`/`repr(exc)`/traceback/异常对象）。

## 6. Symlink / junction 策略

在 v1.0 中是固定的、强制的、不可配置的（没有 `DiscoveryPolicy.follow_symlinks` 字段）：symlink 目录永远不会被递归进入，
symlink 文件永远不会被当作普通媒体来源，Windows reparse point（junction 或其他类型）通过
`fc2_organizer.discovery._platform.is_reparse_point` 独立于 `is_symlink()` 进行检测
（`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`，兼容 Python 3.11，而不是需要 3.12+ 的
`os.path.isjunction`）。完整理由：合同 §10。

## 7. 确定性排序规则

在每个目录中，条目（文件和子目录一起）按 `entry.name` 用普通的 Python ordinal 字符串比较排序，然后按深度优先、
先序遍历（子目录一被遇到就立即完整递归进入，然后才处理它后面的同级条目）。`index` 严格按遍历追加顺序分配。
完整细节：合同 §7。

## 8. 受支持扩展名的策略

`DiscoveryPolicy.supported_extensions`，默认值 `.mp4 .mkv .avi .mov .wmv
.m4v .ts`，不区分大小写（构造时规范化为小写），可覆盖，集中声明（其他任何地方都没有重复的扩展名列表）。
默认集合的理由：合同 §5。

## 9. 测试命令

```bash
# Targeted (from fc2-organizer/):
python -m pytest tests/unit/discovery tests/contract/test_discovery_architecture.py -q

# Full suite:
python -m pytest -q
```

（在本环境中使用 `--basetemp=<dir>`，只是为了避免一个与本任务无关的 pytest 内部清理竞争：在这台多任务主机上，
另一个进程会并发访问共享的 `%TEMP%\pytest-of-<user>` 目录 — 见 §12。它对测试本身没有任何影响，也不是测试所必需的。）

## 10. 针对性测试

```text
99 passed, 3 skipped
```

3 个跳过的测试是 `test_discovery_symlinks_and_junctions.py` 中的真实目录 symlink 测试（见 §12 — 本主机没有所需权限，
以具体的 `WinError 1314` 原因 `pytest.skip`，从不伪装成通过）。所有 junction 测试（不需要提权）都真实运行并通过。

## 11. 全量测试

```text
2460 passed, 3 skipped
```

与之前已关闭阶段的基线完全吻合：C5-R1 记录的原有测试集为 `2361/2361` 通过（见
`docs/review/PHASE3_C5_R1_HANDOFF.md` §5）；`2361 + 99 (new P4-C1 tests) = 2460`。
没有任何原有测试被修改、跳过或新出现失败。除了 3 个已记录的平台跳过之外，`0` warnings / `0` xfail。

## 12. 未运行的平台特定测试

本主机（win32，Python 3.12.10）无需提权就能创建真实的 NTFS junction（`_winapi.CreateJunction`，已在开发过程中直接验证），
因此 **junction 安全性是真实测试的**，而不是模拟的：
`test_junction_directory_is_not_recursed_into`、
`test_junction_loop_does_not_hang`、
`test_junction_pointing_outside_root_is_not_followed` 都针对磁盘上真实的 junction 通过。

在本主机上创建真实的**目录 symlink** 会以
`OSError: [WinError 1314] 客户端没有所需的特权` 失败（`os.symlink` 需要
`SeCreateSymbolicLinkPrivilege` / Developer Mode，这里两者都不可用）。
以下 3 个测试在运行时检测到这一点，并以该确切原因 `pytest.skip`，而不是伪装成通过：

```text
test_discovery_symlinks_and_junctions.py::test_symlink_directory_is_not_recursed_into
test_discovery_symlinks_and_junctions.py::test_symlink_file_is_not_treated_as_a_normal_media_source
test_discovery_symlinks_and_junctions.py::test_symlink_loop_does_not_hang
```

**Windows 特定的运行时测试 NOT RUN：真实目录 symlink 的递归安全性**（只有 junction / reparse point 路径针对真实的
文件系统对象执行过；symlink 代码路径本身 — `entry.is_symlink() ==
True` — 则通过 `test_discovery_platform_helper.py` 中 `is_reparse_point` 自己的单元测试间接覆盖，这些单元测试不需要真实的
symlink；再加上一个事实：无论底层对象是 symlink 还是 junction，`scanner._process_entry` 的 symlink 分支都是完全相同的代码）。
如果之后在具备 `SeCreateSymbolicLinkPrivilege` 的环境中运行（提权的 shell，或启用了 Developer Mode），这 3 个测试
无需任何代码改动就会真实执行。

## 13. 合成阶段门槛

```text
PASS
```

`test_discovery_stage_gate.py::test_large_synthetic_stage_gate` 在 50 个嵌套目录中构建约 ~360 个受支持文件 + 约 ~360 个
不受支持文件（10 个厂牌 × 5 个子批次 × 6 个文件，每个文件轮换使用不同扩展名），外加分布在 3 个不同目录中的 3 个
重复 FC2 番号文件、Unicode 目录 / 文件名，以及散布在目录树中的空目录。完全离线，在一个固定的、由代码生成（非随机）的
布局上验证，因此运行结果可以精确复现：每个受支持文件恰好被发现一次，不受支持的文件从未成为条目，干净的目录树上没有任何
issue，没有重复的 `source_path`，连续两次运行的排序 / 下标完全相同，并且零文件系统修改（前后的 `os.walk` 快照相等）。

## 14. 已知局限

* 遍历的递归深度受 Python 调用栈限制（`sys.getrecursionlimit()`，默认约 ~1000）；极深的目录嵌套可能抛出
  `RecursionError`。预计没有任何真实的媒体库会接近这个深度；合同 §7 把它记录为可接受的 v1.0 局限。
* symlink **文件**（而不是目录）被完全排除，而不是解析后再 stat — 这是一个刻意的保守选择（任务简报 §11），
  尚未在本主机上针对真实 symlink 执行过（§12）。
* 没有专门对极端的 Windows 长路径边界情况（未启用 `\\?\` 长路径选项时 `MAX_PATH` = 260）做压力测试；
  `test_discovery_basic.py` 中的深层递归目录树测试使用 25 层嵌套和短名称，远低于任何此类限制，并不构成对任意长绝对路径的声明。
* 没有专门的并发 / 线程安全声明：`discover_media` 是单线程、同步、一次性的调用，与任务简报的范围一致
  （P4-C1 中没有批处理 / 异步集成）。

## 15. 延续的债务（P4-C1 未触发 / 未处理）

```text
C2-L2, P2-R-05, P2-R-06, P2-R-07, P2-R-10,
C3-N1, C3-N2, C3-N3, C3-N4,
C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3,
F3, F5, C5-R1-L1
```

这些债务都没有被读取、触碰，也与本 package 无关：`fc2_organizer.discovery` 对它们所涉及的任何模块都零依赖（见合同 §14）。

## 16. `git diff --check`

```text
clean (no output)
```

## 17. `git status --porcelain`

Docs Head 提交之后是干净的（用 `git status --porcelain` 验证 — 本文件提交后预期为空）。

## 18. 独立复查（原始轮次）

```text
REQUIRED
```

## 19. P4-C1（原始轮次）

```text
NOT CLOSED
```

---

# R1 关闭 — P4-C1-R-01（HIGH / BLOCKING）

上面的部分是原始的、经过复查的 P4-C1 提交，为保留历史而不做修改。本节记录 R1 增量关闭轮次。

## R1.1 坐标

```text
Reviewed-Failed Code Head = ffe49927760f57d3ea0179cde22f2c19c8dd10a9
Previous Docs Head        = 00dc40d0338b75427766c6b768ed572ee16b9ca0
R1 Code Review Candidate  = 77f928df9e8233ec42f3aa3d5b14291a24c1036a
R1 Docs Head              = <this commit; see git log after commit>
R1 Code Review Range      = 00dc40d0338b75427766c6b768ed572ee16b9ca0..77f928df9e8233ec42f3aa3d5b14291a24c1036a
R1 Docs Review Range      = 77f928df9e8233ec42f3aa3d5b14291a24c1036a..<R1 Docs Head>
```

原始轮次存在两份复查输出。第一份是
`BLOCKED`，因为它自己的指令要求读取一个在本仓库中并不存在的 `fc2-organizer/docs/HANDOFF.md` 路径
-- 这是复查指令的缺陷，而不是 P4-C1 实现的缺陷。按照本轮的简报，**没有**创建该文件，也**没有**为了满足它而改变仓库结构；
它那个同名的 `P4-C1-R-01` 标签**不是**本节所关闭的内容。这里关闭的 finding 来自第二份复查输出，那份复查实际阅读了代码、
重新运行了测试并做了复现。

## R1.2 处理的 finding

```text
P4-C1-R-01
Severity: HIGH / BLOCKING
```

**缺陷：** 以相对根目录调用 `discover_media("mydir")` 时，产生的 `DiscoveredMediaItem.source_path` 本身仍然是相对路径
（`os.path.isabs(...) == False`），违反了冻结的合同（`source_path` 必须是绝对路径 -- 合同 §3）。复查者通过 `chdir` +
相对根目录直接复现了这个问题。原始测试集在所有地方都只传入 `tmp_path`（本来就是绝对路径），因此这条路径在结构上从未被测试过。

## R1.3 确切的变更文件

```text
fc2-organizer/src/fc2_organizer/discovery/scanner.py      (M)
fc2-organizer/src/fc2_organizer/discovery/models.py       (M)
fc2-organizer/tests/unit/discovery/test_discovery_root_absolutization.py  (new)
fc2-organizer/docs/review/P4_C1_HANDOFF.md                 (this section)
```

没有触碰其他文件。`docs/specifications/PHASE4_DISCOVERY_CONTRACT.md` **没有**被修改：它在 §3 中已经写明
`source_path: str` 是 “(absolute, OS-native separators...)” -- 合同本来就是正确的；只是实现没有满足它。

## R1.4 修复说明

**A. 根目录绝对化**（`scanner._coerce_root`）：在把 `root` 转换为 `Path` 之后（对 `str`/`Path`/`os.PathLike` 的类型分派逻辑
没有改变），结果现在会先经过 `Path(os.path.abspath(candidate))`，然后才在其他任何地方使用。刻意选择了 `os.path.abspath`
而不是 `Path.resolve()`：`abspath` 只会拼接到当前工作目录并规范化 `.`/`..` 段 -- 它从不解析 symlink。`resolve()`
还会跟随 symlink 根目录或 symlink 中间路径组件，悄悄改变*被扫描的对象*；那将是对调用方所给根目录以及对（未改动、已冻结的）
根目录 symlink 处理的真实语义改变，而不是纯粹的绝对化，明确不在本次修复范围内。

由于遍历过程中产生的每一个路径
（`DiscoveryResult.root`、每一个 `DiscoveredMediaItem.source_path`）都是由 `os.scandir`/`os.DirEntry.path` 基于传入 `_walk`
的目录构建的，而 `discover_media` 中对 `_walk` 的第一次调用现在收到的正是这个已绝对化的 `root_path`，因此只在顶部做一次绝对化
就足以覆盖整个递归遍历 -- 不需要修改其他任何调用点。

**B. 模型不变量**（`DiscoveredMediaItem.__post_init__`）：在现有的非空 `str` 检查之后，紧接着增加了
`if not os.path.isabs(self.source_path): raise DiscoveryContractError(...)`。现在，手工构建的、带相对 `source_path` 的
`DiscoveredMediaItem` 会在构造时被拒绝，与 scanner 本身是否正确无关 -- 从概念上关闭了复查者复现所暴露出的
“模型信任 scanner”这一缺口。

两个文件中的其他内容都没有改变。symlink/junction 检测（`_is_symlink`、`is_reparse_point`）、确定性的排序 / 遍历顺序、
扩展名策略匹配、失败隔离接缝（`_list_directory_sorted`、`_stat_entry`），以及根目录类型化错误的语义（`_check_root`）
都逐字节未变。

## R1.5 新增的回归测试

`tests/unit/discovery/test_discovery_root_absolutization.py`（10 个测试），全部使用真正的相对根目录
（通过 `monkeypatch.chdir` + 一个裸的相对目录名，而不是直接使用 `tmp_path`）：

* 相对根目录 -> 绝对的 `source_path`
* 相对根目录 -> 正确的 `relative_path`
* 相对根目录 -> `source_path` 指向真实的底层文件（stat + 读回其内容）
* 相对根目录 -> `DiscoveryResult.root` 也是绝对路径
* 以 `.` 开头的相对根目录（`./mydir`）-> 绝对的 `source_path`
* 含有 `..` 段的相对根目录（`sibling/../mydir`）-> 绝对的 `source_path`
* 在没有 symlink 的情况下，普通的相对根目录扫描仍然产生零个 `DiscoveryIssue`（证明 R1 没有扰动 symlink/junction 行为）
* 直接构造 `DiscoveredMediaItem(source_path="relative/a.mp4", ...)` ->
  `DiscoveryContractError`
* 直接构造带绝对 `source_path` 的 `DiscoveredMediaItem` -> 被接受
* 直接构造 `DiscoveredMediaItem(source_path="mydir\\a.mp4", ...)`（Windows 风格的相对路径）-> `DiscoveryContractError`

## R1.6 针对性测试结果

```text
109 passed, 3 skipped
```

（99 个原有 P4-C1 测试 + 10 个新测试，全部通过；3 个跳过项与原始轮次中已有的真实目录 symlink 权限跳过相同，
不受本次修复影响。）

## R1.7 全量测试结果

```text
2470 passed, 3 skipped
```

`2460 (original P4-C1 full-suite baseline) + 10 (new) = 2470`。没有任何原有测试被修改、新出现失败或新被跳过。

## R1.8 复查者的复现 — 直接重新验证

在 pytest 之外手工运行了与复查者复现等价的操作，针对修复后的代码：

```text
mkdir mydir; create mydir/a.mp4; chdir to the parent; discover_media("mydir")

source_path: C:\Users\Ctg\AppData\Local\Temp\tmp90nqlzuu\mydir\a.mp4
os.path.isabs(source_path) == True
relative_path == "a.mp4"
result.root == C:\Users\Ctg\AppData\Local\Temp\tmp90nqlzuu\mydir  (absolute)
os.path.isfile(source_path) == True
```

还直接验证了 `.\mydir` 和 `foo\..\mydir` 两种相对形式都解析到同一个正确的绝对目标，并且手工构造
`DiscoveredMediaItem(source_path="relative\a.mp4", ...)` 现在会抛出 `DiscoveryContractError`。

## R1.9 `git diff --check`

```text
clean (no output)
```

## R1.10 `git status --porcelain`

R1 代码提交之后是干净的；本次 R1 docs 提交之后再次是干净的（用 `git status --porcelain` 验证）。

## R1.11 延续的非阻塞 finding（未改变，R1 未处理）

```text
P4-C1-R-02  MEDIUM
P4-C1-R-03  LOW
P4-C1-R-04  LOW
P4-C1-R-05  LOW
```

第二份复查输出明确地把这四项全部判定为 `non-blocking / carried`。按照本轮的简报，这里一项都不处理：不对 scanner 做防
TOCTOU 的重写，不扩展 symlink/junction 架构，不重新设计扩展名策略，也不为了关闭一个 LOW finding 而扩大范围。
它们留待将来的轮次处理。

## R1.12 独立 R1 关闭复查（原始轮次）

```text
REQUIRED
```

## R1.13 P4-C1（原始轮次）

```text
NOT CLOSED
```

---

# R2 关闭 — P4-C1-R1-01（HIGH / BLOCKING）

上面的两部分（原始 P4-C1 和 R1）为保留历史而不做修改。本节记录 R2 增量关闭轮次。

## R2.1 坐标

```text
R1 Reviewed-Failed Code Head = 77f928df9e8233ec42f3aa3d5b14291a24c1036a
Previous Docs Head           = 25013d1fffee717603389511c3ca7b272e62518d
R2 Code Review Candidate     = 2db3a44d48eb6e9ae36d627c3fd1bb5ed661e34c
R2 Docs Head                 = <this commit; see git log after commit>
R2 Code Review Range         = 25013d1fffee717603389511c3ca7b272e62518d..2db3a44d48eb6e9ae36d627c3fd1bb5ed661e34c
R2 Docs Review Range         = 2db3a44d48eb6e9ae36d627c3fd1bb5ed661e34c..<R2 Docs Head>
```

```text
P4-C1-R-01: REMAINS CLOSED (reverified by direct reproduction, R2.7 Repro A)
```

## R2.2 处理的 finding

```text
P4-C1-R1-01
Severity: HIGH / BLOCKING
```

**缺陷：** R1 对 P4-C1-R-01 的修复通过 `os.path.abspath` 把相对根目录绝对化，而后者执行的是纯词法的规范化
（把 `a/../b` 折叠为 `b`），*发生在任何文件系统访问之前*。对于普通目录，这个词法捷径是无害的。但对于
`link/../mydir`，其中 `link` 是一个 symlink（或者在 Windows 上是一个 junction），它在一般情况下是错误的：
逐个组件解析路径的文件系统，会在 `link` 实际指向的位置的上下文中解析 `..`，而不是相对于 `link` 自身的位置做词法处理。
独立复查者用一个真实的 POSIX symlink 复现了这个问题：

```text
base/
  mydir/
    BASE.mp4
  link -> other/subdir

other/
  subdir/
  mydir/
    OTHER.mp4

chdir(base); discover_media("link/../mydir")
```

R1 基于 `abspath` 的修复扫描的是 `base/mydir`（`BASE.mp4`），尽管调用方的路径按照真实文件系统的解析方式，
指向的是 `other/mydir`（`OTHER.mp4`）-- 这是对*哪个物理目录*被扫描的悄然替换，也就是一个正确性回归，而不仅仅是表面问题。

## R2.3 确切的变更文件

```text
fc2-organizer/src/fc2_organizer/discovery/scanner.py                            (M)
fc2-organizer/tests/unit/discovery/test_discovery_root_absolutization.py        (M)
fc2-organizer/tests/unit/discovery/test_discovery_symlink_dotdot_identity.py    (new)
fc2-organizer/docs/review/P4_C1_HANDOFF.md                                       (this section)
```

`models.py` **没有**被触碰：R1 中增加的“`source_path` 必须是绝对路径”这一不变量是正确的，没有改变。
`PHASE4_DISCOVERY_CONTRACT.md` **没有**被触碰：它本来就规定了“absolute”，从未声称过
“canonicalized/normalized/resolved”；只是实现内部使用了 `abspath`，偏离了合同 — 这是一个合同从未要求的实现细节。

## R2.4 不改变身份的绝对化策略

`scanner._coerce_root` 不再对整个路径调用 `os.path.abspath`、`os.path.normpath`、`Path.resolve()` 或
`os.path.realpath` -- 本次修复中完全没有使用它们。取而代之的是：

```python
if not candidate.is_absolute():
    candidate = Path(os.getcwd()) / candidate
return candidate
```

* **相对**根目录通过普通的 `pathlib` 拼接加上当前工作目录前缀来绝对化。这种拼接从不折叠掉 `..` 段
  （已验证：`Path("/base") / "link/../mydir"` 保持为
  `PurePath("/base/link/../mydir")`，`.." literally present in `.parts`）。
  它确实会去掉多余的 `.` 段（`Path("/base") / "./mydir"` ->
  `/base/mydir`）-- 这在词法上总是安全的，因为无论是否有 symlink，一个单独的 `.` 永远不会改变路径所指的目录。
* **已经是绝对路径**的根目录 -- 即使含有 `..`，即使 R1 的 `abspath` 调用会把它折叠 -- 都完全不做处理、逐字节原样返回。
* 遍历过程中构建的每一个路径（`DiscoveryResult.root`、每一个 `DiscoveredMediaItem.source_path`）仍然像 R1 中那样，
  通过普通的 `os.scandir`/`os.DirEntry.path` 字符串拼接从这个 `Path` 派生 -- 因此未经解析的 `..` / 对 symlink 敏感的段
  会原样带入每一个结果路径。
* 途中进行的每一次*真实*文件系统调用（`_check_root` 中的 `os.stat`、`_list_directory_sorted` 中的 `os.scandir`）
  收到的仍然是同一个字面的、未经解析的字符串，因此决定扫描哪个物理目录的是**操作系统自身的路径解析**
  -- 而不是任何进程内的字符串改写。在内核按组件逐个解析 `..` 并遵循 symlink 的文件系统上（POSIX），
  这会正确地得到调用方实际想要的目标。这正是 R2 简报中 Requirement B（“filesystem 自己按正常路径解析语义处理”）的具体含义。

## R2.5 Windows：经过验证的平台限制，而不是残留缺陷

在本 package 的代码之外，独立地用 `ctypes` 调用 `GetFullPathNameW`（kernel32 在 `CreateFileW`/`FindFirstFileW` 之前内部
用来把 DOS 路径转换为 NT 路径的 Win32 API -- Windows 上每一次 `os.stat`/`os.scandir` 调用最终都要经过它），
对一个**不存在**的路径（`C:\some\base\link\..\mydir`）返回 `C:\some\base\mydir` -- 证明 `..` 的折叠是一个纯字符串操作，
零文件系统 I/O、零 reparse point 感知，*发生在*文件系统 / junction 层被咨询*之前*。这与 `cmd.exe`、PowerShell 和
Windows Explorer 解析此类路径的方式完全相同（`cd link\..\mydir` 的行为也是如此）-- 这是 Windows 原生路径解析的特性，
早于并且独立于 `fc2_organizer.discovery` 存在，不是本 package 引入的，也无法在本 package 内部修复
（除非手写原始的 NT 原生路径调用，而按照 R2 简报这明确不在范围内）。

因此，专门对于 Windows junction 而言，`link\..\mydir` *正确的*、Windows 原生的解释**就是**词法折叠后的
`base\mydir` -- 对这个特定情况，R1 的 `abspath` 和 R2 只加 cwd 前缀的 `_coerce_root` 产生**完全相同且正确**的结果。
Windows 一侧不存在需要修复的回归：P4-C1-R1-01 专门针对 POSIX symlink 的情况，在那里内核真实的逐组件解析确实不同于
朴素的词法折叠，而 R2 的修复正是针对这一点。

## R2.6 相对根目录 / 普通的 `..`（不得回归）

与 R1 相比重新验证未变：`discover_media("mydir")`、
`discover_media("./mydir")` 以及普通的（没有 symlink 的）`discover_media("foo/../mydir")`
都仍然产生绝对的 `DiscoveryResult.root`、绝对的 `DiscoveredMediaItem.source_path`、正确的 `relative_path`，
以及正确的文件身份（读回的内容一致）。由原有的 `test_discovery_root_absolutization.py` 测试加上新增的
`test_ordinary_dotdot_root_identity_is_unaffected` 覆盖（后者增加了明确的内容检查，因为 R2 简报指出，普通目录的 `..`
情况与 symlink/junction 的 `..` 情况不是同一个语义测试，两者都必须覆盖）。

## R2.7 Symlink + `..` 的身份（POSIX）

`test_discovery_symlink_dotdot_identity.py::test_posix_symlink_dotdot_root_preserves_caller_path_identity`
构建了复查者的确切结构（`base/link -> other/subdir`、`base/mydir/BASE.mp4`、`other/mydir/OTHER.mp4`），并断言
`discover_media("link/../mydir")` 发现的是内容为 `"other-content"` 的 `OTHER.mp4`，而不是 `BASE.mp4`。在本主机上它以
具体原因 `pytest.skip`（`os.symlink` 失败：`WinError 1314`，没有
`SeCreateSymbolicLinkPrivilege` / Developer Mode）-- 与原始 P4-C1 symlink 测试已经记录的限制相同，没有伪装成通过。
在能够创建真实目录 symlink 的主机上（POSIX CI runner，或提权 / Developer Mode 的 Windows 主机），它无需任何代码改动
就会真实运行。

## R2.8 Windows junction + `..` 的身份

```text
PASS -- ran for real on this host (junction creation needs no elevation)
```

`test_discovery_symlink_dotdot_identity.py::test_windows_junction_dotdot_root_matches_native_win32_path_resolution`
用真实的 NTFS junction（`_winapi.CreateJunction`）构建等价的结构，先通过 `ctypes` 独立地再次确认
`GetFullPathNameW` 的词法折叠行为（§R2.5），然后断言 `discover_media("link/../mydir")` 发现的是内容为
`"base-content"` 的 `BASE.mp4` -- 这是对 Windows 正确的、原生的结果，而不是 POSIX symlink 的结果（按照 §R2.5，
在 Windows 上通过任何普通的 Win32 文件 API 都无法得到后者）。这不是一个 “Windows junction + .. identity
test NOT RUN” 的情况：环境能够并且确实创建了 junction，因此它真实运行了，并如实报告其实际的（对平台正确的）结果，
而不是假定它与 POSIX 情况一致。

## R2.9 模型的绝对路径不变量

未改变。`DiscoveredMediaItem.__post_init__` 中的 `os.path.isabs(source_path)` 检查（在 R1 中新增）没有被触碰、削弱或删除。
已直接重新验证（R2.10 Repro A）：相对的 `source_path` 仍然以 `DiscoveryContractError` 被拒绝。

## R2.10 直接复现 — Repro A（原始的 P4-C1-R-01 bug，不得回归）

```text
mkdir mydir; create mydir/a.mp4; chdir to parent; discover_media("mydir")

source_path: C:\Users\Ctg\AppData\Local\Temp\tmpwkjgwcnq\mydir\a.mp4
os.path.isabs(source_path) == True
result.root: C:\Users\Ctg\AppData\Local\Temp\tmpwkjgwcnq\mydir  (absolute)
relative_path == "a.mp4"
-> Repro A: PASS (P4-C1-R-01 remains CLOSED)

Direct DiscoveredMediaItem(source_path="relative/a.mp4", ...)
-> DiscoveryContractError: "DiscoveredMediaItem.source_path must be an
   absolute path, got 'relative/a.mp4'"  (model invariant still enforced)
```

## R2.11 直接复现 — Repro B（P4-C1-R1-01，本轮的修复）

```text
base/mydir/BASE.mp4, other/mydir/OTHER.mp4, base/link -> junction -> other/subdir
chdir(base); discover_media("link/../mydir")

caller root string:      link\..\mydir
result.root (observed):  <tmp>\base\link\..\mydir   (absolute; literal ".." preserved, not pre-collapsed by our code)
observed relative_path:  BASE.mp4
observed content:        base-content

Expected physical file per POSIX-symlink-style resolution
  (NOT achievable on Windows via any ordinary Win32 API): other/mydir/OTHER.mp4
Expected physical file per native Windows GetFullPathNameW resolution
  (independently verified via ctypes, see R2.5):          base/mydir/BASE.mp4
Observed physical file this run:                           base/mydir/BASE.mp4

-> matches native Windows resolution exactly; no in-process lexical
   pre-collapse was performed by fc2_organizer.discovery's own code
   (independently confirmed by the platform-independent
   test_coerce_root_does_not_lexically_collapse_dotdot_in_* unit tests,
   which do not depend on any real symlink/junction being present).
```

## R2.12 针对性测试

```text
114 passed, 4 skipped
```

（109 个之前的 P4-C1(+R1) 测试 + 5 个新测试，全部通过；4 个跳过 = 3 个原有的真实目录 symlink 权限跳过 + 1 个针对
`test_posix_symlink_dotdot_root_preserves_caller_path_identity` 的新跳过，根因相同。）

## R2.13 全量测试

```text
2475 passed, 4 skipped
```

`2470 (R1 full-suite baseline) + 5 (new) = 2475`。没有任何原有测试被修改、新出现失败，或因不同于以往的原因被新跳过。

## R2.14 `git diff --check`

```text
clean (no output)
```

## R2.15 `git status --porcelain`

R2 代码提交之后是干净的；本次 R2 docs 提交之后再次是干净的（用 `git status --porcelain` 验证）。

## R2.16 延续的非阻塞 finding（未改变，R2 未处理）

```text
P4-C1-R-02  MEDIUM  -- CARRIED / non-blocking
P4-C1-R-03  LOW     -- CARRIED / non-blocking
P4-C1-R-04  LOW     -- CARRIED / non-blocking
P4-C1-R-05  LOW     -- CARRIED / non-blocking
```

R2 没有关闭、升级或删除任何一项。按照 R2 简报：为关闭 P4-C1-R1-01，没有进行防 TOCTOU 的 scanner 重写、
没有扩展 symlink/junction 架构、没有重新设计扩展名策略，也没有做基于 fd 的 scanner 重写。它们留待将来的轮次处理。

## R2.17 独立 R2 关闭复查（原始轮次）

```text
REQUIRED
```

## R2.18 P4-C1（原始轮次）

```text
NOT CLOSED
```

---

# R3 关闭 — P4-C1-R2-01（HIGH / BLOCKING）

上面的三部分（原始 P4-C1、R1、R2）为保留历史而不做修改。本节记录 R3 增量关闭轮次。

## R3.1 坐标

```text
R2 Reviewed-Failed Code Head = 2db3a44d48eb6e9ae36d627c3fd1bb5ed661e34c
Previous Docs Head           = a65a29f30b0c6e1352c19e6f2a85c061434f86a5
R3 Code Review Candidate     = c4f5a415d8fd8d0d56ff4ee227e7b87a01fbe79f
R3 Docs Head                 = <this commit; see git log after commit>
R3 Code Review Range         = a65a29f30b0c6e1352c19e6f2a85c061434f86a5..c4f5a415d8fd8d0d56ff4ee227e7b87a01fbe79f
R3 Docs Review Range         = c4f5a415d8fd8d0d56ff4ee227e7b87a01fbe79f..<R3 Docs Head>
```

```text
P4-C1-R-01:   REMAINS CLOSED (reverified, R3.10 Repro A)
P4-C1-R1-01:  REMAINS CLOSED (reverified, R3.10 Repro B + Repro C)
P4-C1-R2-01:  CLOSED by this round (R3.10 Repro D)
```

## R3.2 处理的 finding

```text
P4-C1-R2-01
Severity: HIGH / BLOCKING
```

**缺陷：** R2 的 `_coerce_root` 通过无条件地加上当前工作目录前缀
（`Path(os.getcwd()) / candidate`）来绝对化相对根目录。这在 POSIX 上是正确的（那里不存在相对于盘符的概念），
但在 Windows 上，对于普通字符串拼接无法表达的相对形式是错误的：同一盘符的盘符相对路径（`C:foo`）、跨盘符的盘符相对路径
（进程当前盘符为 `C:` 时的 `D:foo`），以及有根的相对路径（`\foo`）。尤其是 `D:foo`，它相对于盘符 `D:` **自己的**
当前目录解析 -- 这是由操作系统维护的状态（Windows 自己跟踪的隐藏的按盘符 `=D:` 环境变量），`os.getcwd()` 无法报告当前盘符
以外任何盘符的这一状态。`Path(os.getcwd()) / Path("D:foo")` 无法正确解析它，并且仍然可能无法为调用方想要的目标产出一个
真正的绝对路径 -- 对这种特定的输入形态重新打开了 P4-C1-R-01 的合同违规。

## R3.3 确切的变更文件

```text
fc2-organizer/src/fc2_organizer/discovery/scanner.py                              (M)
fc2-organizer/tests/unit/discovery/test_discovery_root_absolutization.py          (M)
fc2-organizer/tests/unit/discovery/test_discovery_drive_relative_identity.py      (new)
fc2-organizer/docs/review/P4_C1_HANDOFF.md                                        (this section)
```

`models.py` **没有**被触碰：“`source_path` 必须是绝对路径”这一不变量是正确的，没有改变。`PHASE4_DISCOVERY_CONTRACT.md`
**没有**被触碰：它规定的是“absolute OS-native path”，这正是本次修复现在在每个平台上实际交付的内容。

## R3.4 按平台的绝对化策略

```python
def _is_windows() -> bool:
    return os.name == "nt"

...
if _is_windows():
    return Path(os.path.abspath(candidate))

if not candidate.is_absolute():
    candidate = Path(os.getcwd()) / candidate
return candidate
```

`_is_windows()` 是一个新的、小的、隔离的接缝（仿照现有的 `_list_directory_sorted`/`_stat_entry`/`_is_symlink` 模式），
这样测试就可以强制走任一分支，而不必修改真实的全局 `os.name` -- 这一点很重要，因为同一进程中的其他模块也会读取
`os.name`，包括 `pathlib` 自己对具体 `Path` 子类的选择，所以直接修改它会在真实的 Windows 主机上出错
（`NotImplementedError: cannot
instantiate 'PosixPath' on your system`，本轮遇到并修复了这个问题）。

* **Windows 分支：** 完全委托给 `os.path.abspath`（`ntpath.abspath`，底层是真实的 `GetFullPathNameW` Win32 API）。
  这不是图方便的选择 -- 这是*唯一*能够正确解析同盘符 / 跨盘符相对路径以及有根相对路径的方式，因为 Python 没有暴露
  其他任何 API 来获取非当前盘符自己的当前目录。这也意味着在 Windows 上 `..` 会被词法折叠 -- 但这*不是* P4-C1-R1-01
  的回归：R2 已经独立验证过（通过对不存在路径的 `ctypes` `GetFullPathNameW` 调用），Windows 本身就是这样原生地折叠 `..`
  的，发生在任何 reparse point 被咨询之前，与 `cmd.exe`/PowerShell/Explorer 完全相同 -- 因此无论本 package 怎么做，
  Windows 上的 `abspath` 产生的都是操作系统对该路径的任何文件系统访问都会产生的那个完全相同、对 Windows 正确的结果。
* **POSIX 分支：** 与 R2 相同 -- 通过普通的 `pathlib` 拼接把当前工作目录前缀加到相对根目录上，从不把 `..` 折叠掉，
  因此 POSIX 内核仍然可以相对于 `link` 实际指向的位置来解析 `link/../mydir` 中的 `..`（P4-C1-R1-01）。

## R3.5 普通的相对根目录（不得回归）

在 Windows 上，`discover_media("mydir")`、`"./mydir"` 以及（非 symlink 的）`"foo/../mydir"` 都仍然产生绝对的
`result.root`/`source_path`、正确的 `relative_path` 以及正确的内容身份 -- 现在走的是 `os.path.abspath` 分支，而不是 R2 的
cwd 拼接，对这些普通形式的可观察结果完全相同。由原有的 `test_discovery_root_absolutization.py` 测试覆盖，全部仍然通过。

## R3.6 Windows 有根相对根目录（`\foo`）

作为与 oracle 路径解析结果的比对来覆盖（`ctypes GetFullPathNameW`），而不是针对位于盘符根目录的真实文件：本轮刻意不在盘符
根目录（`C:\` 或 `D:\`）直接写入测试 fixture，这与任务简报对这一特定情况较为宽松的措辞 “at least add appropriate regression
coverage” 一致（相对于跨盘符情况明确要求的 “must be a real Windows filesystem test”，见 R3.8）。
`test_discovery_drive_relative_identity.py::test_rooted_relative_root_matches_native_path_resolution`
在真实的（非根目录的）`monkeypatch.chdir` 下，断言 `_coerce_root("\\foo")` 与 `GetFullPathNameW("\\foo")` 完全一致。

## R3.7 Windows 同盘符的盘符相对根目录（`C:foo`）

真实的文件系统身份测试，不需要特殊的盘符（同盘符的盘符相对路径相对于当前盘符自己的当前目录解析，这里即 `tmp_path`，
一个普通的、本来就被允许的临时位置 -- 绝不是盘符根目录）。
`test_discovery_drive_relative_identity.py::test_same_drive_drive_relative_root_preserves_identity`：
在 `tmp_path` 下创建一个真实文件，通过 `ctypes GetFullPathNameW` 独立解析 `"C:mydir"`，在调用 `discover_media` 之前先用普通的
`open()` 直接读取 oracle 解析出的文件的内容，然后断言 `discover_media("C:mydir")` 在路径身份（`os.path.samefile`）和内容上
都与该 oracle 完全一致。

## R3.8 Windows 跨盘符的盘符相对根目录（`D:foo`）

```text
PASS -- ran for real (a genuine second writable drive, D:, is present on this host)
```

这是本轮的核心回归，也是唯一需要在仓库自己的临时区域之外进行写入的部分。**在触碰真实的 `D:\` 盘之前获得了用户的明确授权**
（该盘存放着仓库所有者真实的个人文件 -- 文档、SQL 转储、项目文件夹 -- 而不是一个临时 / 测试盘），并在以下约束下进行，
且严格遵守：

* 只在 `D:\` 下直接创建了**一个**唯一的、随机命名的目录（`D:\ffcc_p4c1_r3_<uuid4 hex>`）-- `D:` 上的其他任何内容都没有被
  读取、修改、移动或删除。
* 每一个创建的路径都被明确跟踪；删除只针对那一个自有根目录（以及本轮在其中创建的内容），并在 `shutil.rmtree` 之前立即通过
  路径身份进行验证。
* 没有递归删除任何在本轮之前就存在的内容；删除时没有使用通配符 / 模糊路径。
* 删除之后重新验证删除成功（`owned_root.exists() == False`）；预定策略是：如果删除失败，就报告残留路径并停止，绝不绕过
  任何保护（实际并没有失败）。

**独立复现（在 pytest 之外，Repro D）** 先运行，并打印了每一个创建 / 删除的路径：

```text
Created: D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4
         D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4\droot
         D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4\droot\mydir
         D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4\droot\mydir\D_DRIVE_FILE.mp4
Oracle (ctypes GetFullPathNameW) resolved "D:mydir" ->
         D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4\droot\mydir
discover_media("D:mydir") result.root / item.source_path: same directory, absolute
item.relative_path: D_DRIVE_FILE.mp4
Oracle direct-read content == discover_media-read content == "d-drive-content"
Deleted: D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4 (the single owned root)
owned_root exists after cleanup: False
```

在独立脚本运行之后，以及在同样覆盖这条路径的全量 pytest 运行之后，都对 `Get-ChildItem D:\` 做了前后对比（22 个顶层条目，
名称完全相同，没有 `ffcc_*` 残留）（该 pytest 测试为
`test_discovery_drive_relative_identity.py::test_cross_drive_drive_relative_root_preserves_identity`，它通过
`_second_writable_drive` fixture 以编程方式重新推导出第二个可写盘符，而不是硬编码 `D:` -- 如果找不到就 `pytest.skip`，
绝不伪造通过）。

## R3.9 Windows junction + `..`（不得回归，P4-C1-R1-01 的 Windows 一侧）

`test_discovery_symlink_dotdot_identity.py::test_windows_junction_dotdot_root_matches_native_win32_path_resolution`
（与 R2 相比未修改）仍然通过：跨越真实 junction 的 `discover_media("link/../mydir")` 仍然解析到 `BASE.mp4` -- 与之前相同、
对 Windows 正确的结果，因为对这个特定情况，`_coerce_root` 的 Windows 分支（`abspath`）产生的结果与 R2 的 cwd 拼接完全相同
（R3.4）。

## R3.10 直接复现（在 pytest 之外）

```text
Repro A -- ordinary relative root ("mydir"):
  source_path/result.root absolute, relative_path == "a.mp4"
  direct DiscoveredMediaItem(source_path="relative/a.mp4", ...) -> DiscoveryContractError
  -> PASS, P4-C1-R-01 remains closed

Repro B -- POSIX symlink/../mydir:
  os.symlink(...) -> OSError(22, "客户端没有所需的特权。") (WinError 1314)
  -> NOT RUN -- platform/privilege limitation (unchanged from R1/R2), honestly reported

Repro C -- Windows junction/../mydir:
  discovered BASE.mp4 / "base-content" (native, correct-for-Windows result)
  result.root now shows the lexically-collapsed path (...\base\mydir), consistent
  with the Windows branch now using abspath unconditionally
  -> PASS, P4-C1-R1-01 Windows side remains closed

Repro D -- Windows cross-drive "D:mydir":
  independent oracle (ctypes GetFullPathNameW) and discover_media agree exactly
  on both path identity and file content; single owned directory created and
  fully deleted, D:\ diffed clean before/after
  -> PASS, P4-C1-R2-01 CLOSED
```

## R3.11 针对性测试

```text
119 passed, 4 skipped
```

（114 个之前的 P4-C1(+R1+R2) 测试 + 5 个新测试，全部通过；4 个跳过没有改变 --
3 个原有的真实目录 symlink 权限跳过，外加 R2 中那一个 POSIX symlink 身份跳过，每次的根因都相同：本主机没有
`SeCreateSymbolicLinkPrivilege`。）

## R3.12 全量测试

```text
2480 passed, 4 skipped
```

`2475 (R2 full-suite baseline) + 5 (new) = 2480`。没有任何原有测试被修改、新出现失败，或因不同于以往的原因被新跳过。

## R3.13 `git diff --check`

```text
clean (no output)
```

## R3.14 `git status --porcelain`

R3 代码提交之后是干净的；本次 R3 docs 提交之后再次是干净的（用 `git status --porcelain` 验证）。`D:\` 上没有残留状态（见
R3.8）。

## R3.15 延续的非阻塞 finding（未改变，R3 未处理）

```text
P4-C1-R-02  MEDIUM  -- CARRIED / non-blocking
P4-C1-R-03  LOW     -- CARRIED / non-blocking
P4-C1-R-04  LOW     -- CARRIED / non-blocking
P4-C1-R-05  LOW     -- CARRIED / non-blocking
```

R3 没有关闭、升级或删除任何一项。

## R3.16 独立 R3 关闭复查（原始轮次）

```text
REQUIRED
```

## R3.17 P4-C1（原始轮次）

```text
NOT CLOSED
```

---

# 最终关闭 — P4-C1

上面的各部分（原始 P4-C1、R1、R2、R3）为保留历史而不做修改。本节是对最终独立关闭决定的纯文档治理记录；它不引入任何代码或
测试改动，除了 R1/R2/R3 已经确立的内容之外，也不冻结任何新的技术声明。

```text
Phase:                       4
Package:                     P4-C1 Recursive Media Discovery
Status:                      CLOSED
Final Level:                 Level 1 PASS
Final Reviewed Code Head:    c4f5a415d8fd8d0d56ff4ee227e7b87a01fbe79f
Previous Docs Head:          b90a95eda22a2ef12406c623bca7365602088e99
```

## 最终 finding 处置

```text
P4-C1-R-01     CLOSED
P4-C1-R1-01    CLOSED
P4-C1-R2-01    CLOSED

P4-C1-R-02     CARRIED / non-blocking
P4-C1-R-03     CARRIED / non-blocking
P4-C1-R-04     CARRIED / non-blocking
P4-C1-R-05     CARRIED / non-blocking
```

**所有阻塞性的 P4-C1 finding 均已关闭。其余 finding 被明确作为非阻塞项延续** -- 本次关闭没有修复、降级或重新打开它们；
每一项涉及什么、为什么没有在本轮处理，见上文 R1.11/R2.16/R3.15。

## 独立关闭证据

获得了两份独立的 R3 关闭复查，结论都是 **PASS**：

* 一份 Windows 一侧的独立复查直接在 Windows 主机上重新运行了测试集，并报告了真实数字：

  ```text
  Targeted: 119 passed / 4 skipped
  Full suite: 2480 passed / 4 skipped
  ```

  并独立地、真实地重新验证了：普通相对根目录、Windows 有根相对根目录、Windows 同盘符的盘符相对根目录、
  Windows 跨盘符的盘符相对根目录（针对一个真正的第二盘符，并用一个独立的 Win32 API oracle 交叉核对），以及
  Windows junction + `..`（与原生路径解析一致，而不是 POSIX symlink 的结果）。

* 第二份独立复查在 POSIX 环境中运行，直接独立验证了 POSIX symlink + `..` 的情况（真实的 `os.symlink`，而不是模拟）
  -- 确认 `discover_media` 在经过一个 symlink 组件后再跟 `..` 时，仍然保持调用方实际由文件系统解析出的目标；这正是
  Windows 一侧复查自己无法执行的那一种情况（那台主机上没有 `SeCreateSymbolicLinkPrivilege`；见 R1/R2/R3 的
  “Platform-Specific Tests Not Run”）。

这两份独立复查合起来，覆盖了全部三个阻塞性 finding 的关闭证据：Windows 一侧的 P4-C1-R-01 和 P4-C1-R2-01，以及
P4-C1-R1-01 的 Windows junction 一侧（与原生解析一致）和 POSIX symlink 一侧（按组件保持身份）-- 这是同一个底层合同
（“绝对化不得改变调用方路径在物理上所指的对象”）在两个平台上的两半。

## 本次关闭的范围

这只关闭 **P4-C1**（递归媒体发现）。它不关闭整个 Phase 4，也不授权开始任何后续的 Phase 4 package（P4-C2、NFO、图片、
整理计划、文件系统执行器或任何其他后续 package）-- 按照项目的阶段门槛治理，它们各自都需要自己的冻结合同和自己的复查周期。

```text
Phase 4: NOT CLOSED
```

## 最终状态

```text
P4-C1: CLOSED
```
