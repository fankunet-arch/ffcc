# Phase 4 / P4-C7 Handoff -- 安全文件系统执行器（Safe Filesystem Executor）

```text
Phase        = 4
Package      = P4-C7 Safe Filesystem Executor（fc2_organizer.execution）
Role         = Developer（S6 执行者）
Branch       = claude/phase4-c7-safe-filesystem-executor
规范合同     = docs/specifications/PHASE4_SAFE_FILESYSTEM_EXECUTION_CONTRACT.md
施工计划     = docs/P4_C7_CONSTRUCTION_PLAN.md
```

本文件是 reviewer 证据文档，不是验收结论。S6 与 P4-C7 均须经过独立 S6 closure review；
本文件不宣布 S6 ACCEPTED、P4-C7 CLOSED 或 Phase 4 CLOSED。

## 1. 坐标

```text
P4-C7 E0 Frozen Base              = a0a69c71a1451232ded2c8ae8ecd514cf48ba95b   DOCS-CN Final Closure Head
E0 Establishment Head             = 8f18ec67a4da830831a1ce2ed020eb36c256afe5   合同 + 施工计划（docs-only）
S1 Final Reviewed Code Head       = 416d69ae1af5b5d374a70a9d483ceb14e73ab50d   S1-R1
S2 Final Reviewed Code Head       = edac3b675c50ca3cd20ca81543fc7728ca44b69f   S2-R1
S3 Final Reviewed Code Head       = b0b79e0cbba6507dca8f06c06678b22a0f051f0b   S3-R2
S4 Final Reviewed Code Head       = aef025450217521707916c59dbaa121d665512b7   S4-R1
S5 Final Reviewed Code Head       = 3a2d737286723ecc399813bb4da8dfb40ffbe104   S5-R2
S6 Frozen Base                    = f0ffb942da63a65562027ec2b5cf162b11f161a9   S5 Final Governance Docs（S5 final closure R1）
S6 Code Review Candidate          = ae1ace96c86874b3f33ec59819e4aa065136e521   只含 S6 测试
S6 Docs Head                      = 本提交（`git log -1 --format=%H -- fc2-organizer/docs/review/P4_C7_HANDOFF.md`）
Remote Head                       = S6 Docs Head（本提交 push 之后）

S6 Code Review Range : f0ffb942da63a65562027ec2b5cf162b11f161a9..ae1ace96c86874b3f33ec59819e4aa065136e521
S6 Docs Review Range : ae1ace96c86874b3f33ec59819e4aa065136e521..<S6 Docs Head>
```

关系：`S6 Code Review Candidate^ == f0ffb942da63a65562027ec2b5cf162b11f161a9`；`S6 Docs Head^ == ae1ace96c86874b3f33ec59819e4aa065136e521`。
开始前已验证 `HEAD == origin/claude/phase4-c7-safe-filesystem-executor == f0ffb94` 且工作区干净。没有 rebase、amend、
squash、force push 或改写历史。

**Code Review Candidate 与 Docs Head 严格区分**：代码复查对象是 `ae1ace9`（测试）；Docs Head 只追加本文件与合同第 32 节
S6 状态行，不含任何代码或测试。

## 2. 变更范围

### 2.1 S6 Code Review Candidate（`ae1ace9`，2 个文件，+1951 / -0）

```text
A fc2-organizer/tests/unit/execution/test_execution_synthetic_gate.py      （1234 行）
A fc2-organizer/tests/unit/execution/test_execution_platform_semantics.py  （717 行）
```

* `tests/unit/execution/_helpers.py`、`_builders.py`：**未修改**（既有 helper 已足够，无需追加）。
* Production Files Changed：**NONE**（`src/**` 相对 S6 Frozen Base 零差异）。
* 未触碰：施工计划、合同第 1-31 / 33 / 34 节、S1-S5 任何生产或测试文件、P4-C1..P4-C6 文档、DOCS-CN、CLI / UI / JSON /
  持久化 / 数据库 / Amane、任何 P4-C8 文件。

### 2.2 S6 Docs Head（本提交，2 个文件）

```text
A fc2-organizer/docs/review/P4_C7_HANDOFF.md
M fc2-organizer/docs/specifications/PHASE4_SAFE_FILESYSTEM_EXECUTION_CONTRACT.md   仅第 32 节 S6 状态行
```

S6 状态行：`NOT STARTED` -> `S6 IMPLEMENTED — INDEPENDENT REVIEW REQUIRED`。S1-S5 行不变。

### 2.3 S6 期间的生产缺陷

S6 门槛**没有**发现任何生产正确性缺陷；没有 `fix(execution)` 提交，没有 production-fix 任务。

## 3. 合同章节映射

“既有测试”指 S1-S5 已闭合批次的测试文件（`tests/unit/execution/test_execution_*.py`、
`tests/contract/test_execution_architecture.py`）；“S6 门槛”指本批两个新文件（下称 `synthetic_gate`、`platform`）。

| 合同节 | 实现模块 | 既有测试 | S6 门槛 | 实际证据 |
|---|---|---|---|---|
| §3 架构与依赖方向 | 全部 11 个模块；`_fs.py` 为唯一 syscall 接缝 | `test_execution_architecture.py`（模块集合、import 白名单、禁用前缀、禁用调用名、反向依赖、运行时阻断器） | `synthetic_gate::test_architecture_regression_scan_of_the_mutation_sites`：模块集合精确；`mkdir` 只在 `_mkdir_exclusive`，`rename`/`link` 只在 `_same_volume_primitive`/`_publish_no_replace`，`unlink` 只在 `_remove_owned_temp`/`_unlink_verified_source`；无 `replace`/`makedirs`/`rmtree`/`remove`/`chmod`/`truncate`/`utime` 调用、无 `exist_ok`、无 `O_TRUNC`、`directories.py` 无捕获 `FileExistsError` 的 handler；接缝默认值 `_FS.rename is os.rename` 等 | 执行 PASS；变异 A1/A2/C 使其 FAIL（第 7 节） |
| §4 公开 API | `__init__.py`、`preflight.py`、`executor.py` | `test_execution_architecture.py`（`__all__` 精确集合）、`test_execution_executor.py`（严格类型、顺序、消费） | 两个门槛只经 `preflight_execution` + `execute_filesystem` 驱动全部用例 | 500 + 7 对 + 1000 张用例全部经公开 API |
| §5-7 输入 / 计划图 / manifest | `validation.py`、`paths.py` | `test_execution_graph.py`（伪造全集、400 计划零误报）、`test_execution_manifest.py`（伪造全集、8×{0,1,13}、1000 张内存验证、1..10000 命名一致） | `synthetic_gate` 每个用例先断言 manifest 的 kind/目标/序号/字节与用例定义逐项相等，再执行 | 1000 张实际落盘（第 5.4 节） |
| §8-9 状态 / 执行单元 | `executor.py`、`validation.py` | `test_execution_executor.py`（SUCCESS/FAILED/PARTIAL 各类）、`test_execution_models.py` | 每个用例断言累计 effect 序列 == 静态推导的 E（种类、路径、artifact kind、序号），PARTIAL 为 E 前缀 | 500 SUCCESS；50 故障首次失败全部 PARTIAL，完成数 == 设计的 p |
| §10-17 library root / 源 / 身份 / fresh / checkpoint / 封印 / 消费 / preflight / 传输模式 | `preflight.py`、`seal.py`、`models.py`、`_fs.py` | `test_execution_preflight.py`、`test_execution_checkpoint.py`、`test_execution_seal.py`、`test_execution_resume.py`、`test_execution_race.py`（源所有权占用 ACTIVE/RESERVED/POISONED、token） | 故障用例一律用**上一执行返回的 checkpoint** RESUME（断言 `mode is RESUME`、前缀追加、旧 checkpoint 已消费）；每次失败断言占用状态（发布且保留源 -> `RESERVED(新 checkpoint_id)`，否则无条目）；成功后占用释放；语料运行结束无遗留占用；原生/硬链接用例断言媒体 inode 保持、跨卷断言 `CROSS_VOLUME` + `media_sha256` | 全部 PASS |
| §18-20 媒体传输 / 临时文件 | `transfer.py` | `test_execution_transfer_same_volume.py`、`test_execution_transfer_cross_volume.py`（边界尺寸、64 MiB+3 流式按块）、`test_execution_transfer_failures.py`（每个 `TransferStage`） | 200 原生 + 100 link 策略 + 150 强制跨卷；故障覆盖每个媒体失败种类；`platform` 覆盖顺序与平台原语 | 全部 PASS |
| §21-22 目录所有权 | `directories.py` | `test_execution_directories.py`（8 线程争同一目标、post-mkdir 替换） | mkdir 窗口竞争对（确定性交错）；U7 `EACCES` / `EEXIST` 注入 | PASS；变异 C 被杀死 |
| §23 overwrite NEVER | `transfer.py`、`directories.py`、P4-C6 原语 | S3/S4 冲突测试、架构 AST | 真实占用物在早期探测之后出现（fault 451 原生、497 跨卷；`platform` Windows 精确名 / 大小写变体 × 同卷 / 跨卷、link EEXIST）；占用物字节 / inode / mtime 不变 | PASS；变异 A1/A2 下占用物被覆盖 -> FAIL |
| §24 artifact 执行 | `executor._execute_artifact_unit` | `test_execution_artifacts.py`（映射表每行、leftover 归属、1000 单元） | 故障覆盖 `ARTIFACT_*` 全部种类、`PUBLISHED_ARTIFACT_MISMATCH`、两种 `ArtifactCleanupError`；leftover 名称 / 目录角色 / 数量精确 | PASS |
| §25 TOCTOU | 全部（快照 + 重新校验） | S3/S5 窗口测试 | `platform`：发布后源路径被替换 -> `SOURCE_CHANGED`、替换物不删（同卷 / 跨卷）；open 前换入另一文件 -> fstat 身份拒绝；故障 `source_changed_before_unlink` / `source_missing_before_unlink` | PASS；变异 B1 下替换物被删 -> FAIL |
| §26 平台 | `_fs.is_link`、`transfer._SAME_VOLUME_STRATEGY` / `_DIRECTORY_FSYNC`、`paths.same_entry_name`、`directories.compare_inventory` | S1 词法（`test_execution_paths.py`）、S3 原生 Windows 用例 | `platform` 逐条（第 6 节） | Windows 原生 EXECUTED；POSIX 原生 NOT EXECUTED（证据缺口） |
| §27 失败词汇 | `models.py`、`errors.py` | `test_execution_models.py`（枚举集合精确） | 27 个 `ExecutionFailureKind` 全部实际注入并观测（`NON_INJECTABLE = {}`） | 覆盖 27 / 27 |
| §28-29 无回滚 / 致命异常 | `executor.py`、`transfer.py` | `test_execution_executor.py`（每个单元边界 `KeyboardInterrupt`）、`test_execution_transfer_failures.py`（第 k 块 `BaseException`）、`test_execution_race.py`（POISONED） | 每次失败后核心不变量；已完成 effect 在 resume 中保留（前缀追加） | PASS |
| §30 P4-C8 边界 | `executor.py`（单影片） | `test_execution_race.py`（spawn 多进程不同目标） | 门槛只调用公开 API 的 preview / execute / retry 形态，不含批量编排 | 见第 10 节已知局限 |
| §31 / §31.1 测试总设计 | -- | 第 4 节审计表 | 两个 S6 文件 | 见第 4、5 节 |

## 4. 第 31 节既有覆盖审计

S6 先运行既有 execution 套件（`tests/unit/execution` + `tests/contract/test_execution_architecture.py`：1054 passed /
21 skipped / 0 failed，含 S6 新文件），并逐类确认第 31 节要求已有实际覆盖，未机械复制：

| 第 31 节类别 | 既有覆盖（文件::代表性测试） | S6 追加 |
|---|---|---|
| graph forgery | `test_execution_graph.py`（30 个测试） | -- |
| manifest forgery | `test_execution_manifest.py`（16） | -- |
| optional images | `test_execution_executor.py::test_success_matrix`（8 × {0,1,13} × 3 传输） | 8 × 0..13 全部 112 组合 |
| 1000 extrafanart | 内存验证 + 命名一致（manifest）、单元级执行（artifacts） | 集成执行 1000 张（第 5.4 节） |
| source mutation / replacement | `test_execution_preflight.py`、`test_execution_transfer_failures.py`、`test_execution_executor.py::test_stale_state_after_preflight_fails_before_any_mutation` | 故障用例 + `platform` 换入测试 |
| target conflict / replacement | `test_execution_directories.py`、`test_execution_transfer_same_volume.py`、`test_execution_artifacts.py` | 真实占用物（第 3 节 §23 行） |
| directory symlink/reparse | `test_execution_preflight.py`（junction / symlink library root） | `platform` junction 原生、目标目录单元间被换成 junction |
| same-source race | `test_execution_race.py`（19 个测试函数，31 个用例） | 回归运行：31 passed |
| same-target race | `test_execution_race.py`、`test_execution_directories.py` | 7 个冲突对 |
| same-volume / cross-volume | S3 三个文件 | 450 集成用例 |
| copy interruption / short write / fsync / publish / unlink failure | `test_execution_transfer_failures.py` | 故障用例 |
| unrelated temp preservation | S3/S4 植入测试 | 全局植入 + 1/5 成功用例在自有目录中执行期间植入 |
| checkpoint mismatch / artifact mismatch on resume / unexpected entry | `test_execution_checkpoint.py`、`test_execution_resume.py` | resume 链中注入 `UNEXPECTED_ENTRY` 等 |
| resume after each partial point | `test_execution_resume.py`（2 形态 × 每个 p） | 24 个 resume 点，含故障种类多样化 |
| Unicode paths / zero-byte media | `test_execution_executor.py`、S3 文件 | 语料覆盖 |
| large streamed media | `test_execution_transfer_cross_volume.py::test_exact_bytes_and_sha256_for_boundary_sizes`（3 MiB+17 >= 3 块）、`::test_64_mib_generated_media_is_streamed_in_blocks_of_at_most_one_mib`（64 MiB+3，按块断言每次读写 <= 1 MiB） | 已存在，**未复制**；语料另含 3 MiB+17 集成用例 |
| Windows / POSIX semantics | S3 部分原生用例 | `platform` 最终门槛 |
| architecture / no-mutation of preflight | `test_execution_architecture.py`、`test_execution_preflight.py::test_preflight_performs_zero_mutation_and_never_opens_content` | 架构回归扫描 |

审计结论：第 31 节每一类在 S1-S5 中均已有实际测试；没有发现“此前完全无测试”的冻结要求。

## 5. 500-item synthetic gate（`test_execution_synthetic_gate.py`）

### 5.1 构成（静态断言）

```text
总数 500（test_case_set_is_exactly_500_with_the_frozen_composition：len(CASES) == 500）
  native（主机原生同卷策略；本机 = Windows rename）   200
  hardlink（POSIX link 策略，经 _SAME_VOLUME_STRATEGY + P4-C6 hardlink 接缝）   100
  cross_volume（经 _FS.device_of 接缝强制；非原生跨卷证据）   150
  fault（故障 / 恢复）   50
500 个番号互不相同、500 个源路径互不相同（不以重复参数冒充覆盖）
另有：7 个冲突对（14 个影片，不计入 500）、1 个 1000 extrafanart 影片（不计入 500）
```

* 媒体尺寸：`0、1、1 MiB-1、1 MiB、1 MiB+1、3 MiB+17` 在三个传输组中**各**出现；另一个故障用例在 1 MiB+1 的第 2 块读失败。
* 媒体字节由用例定义生成（`media_bytes(case id, size)`，每 32 字节块不同），期望值不来自生产结果。
* Unicode：CJK、假名、emoji（astral）、组合字符、NFC 与 NFD 两种形式（源名、源目录、library root）；扩展名大小写
  `.mp4 .MP4 .Mp4 .mkv .MKV .avi .wmv .mOv`（目标媒体名为小写扩展）。
* manifest：成功用例覆盖 8 种 poster/fanart/thumb 组合 × extrafanart 0..13 全部 112 组合（native 与 cross_volume 各自完整）。

### 5.2 每个成功用例的断言（期望值来自定义与静态规则）

* `SUCCESS`、无 checkpoint、无 failure；effect 序列 == 静态 E；artifact effect 的 sha256 / size == 定义字节；媒体 size；
* 目标目录精确列举（相对路径集合相等）且每个文件字节相等（媒体、NFO、各图片、1..N 张 extrafanart）；
* 源路径已不存在；源目录无新增临时类条目；
* 无 `.fc2tmp-*.part` / `.part` / `.tmp` 残留（植入物与精确报告的 leftover 除外）；
* 同卷（原生 / hardlink）最终媒体 inode == 源快照 inode；跨卷 `transfer_mode == CROSS_VOLUME`、`media_sha256 == sha256(定义字节)`；
* 源所有权占用已释放。
* `SUCCESS` 数：**500**（450 直接 + 50 故障用例 resume 后）。

### 5.3 故障 / resume（50 个用例）

* 注入通过冻结接缝：`execution._fs._FS`、`materialization.atomic._FS`、执行器的 `materialize_artifact` 绑定、
  `FakeDirectoryFsync`（目录 fsync 路径）；注入按“正在执行的单元”限定作用域，只触发一次，并断言确实触发（非空洞）。
* 首次失败后断言：`PARTIAL`、失败种类 == 设计值、完成 effect 数 == 设计的 p、完成 effect == 静态 E 前缀、
  **核心不变量** `assert_source_not_lost(source, final, sha256)`、全部植入无关条目字节 / inode / mtime 不变、占用状态精确、
  leftover 名称匹配 `^\.fc2tmp-[0-9a-f]{32}\.part$` 且位于所报告的目录。
* 然后以**该执行返回的 checkpoint** RESUME（不重建 fresh plan）；4 个用例在 RESUME 中再注入一次故障
  （`LIBRARY_ROOT_CHANGED`、`UNEXPECTED_ENTRY`、`SOURCE_MISSING`、`TARGET_DIRECTORY_CHANGED`），断言零新增 effect、新
  checkpoint、旧 checkpoint 已消费，再 RESUME 至 `SUCCESS`。
* 最终布局与无故障一次成功的静态期望完全一致；唯一差异是合同允许报告的 leftover（3 个用例：
  `MEDIA_TEMP_CLEANUP_FAILED` 目标目录 1 个；两种 `ARTIFACT_CLEANUP_FAILED` extrafanart 目录各 1 个），名称 / 归属 / 数量精确。
* 2 个用例（451 原生、497 跨卷）在早期探测之后于最终路径植入**真实**占用物 -> `TARGET_CONFLICT`，占用物不变；
  随后由测试（模拟用户）删除自己植入的该文件，再 RESUME。

**失败种类覆盖**：covered **27 / required 27**（`test_gate_run_covers_every_injectable_failure_kind`：实际观测集合 ==
`set(ExecutionFailureKind) - NON_INJECTABLE`，`NON_INJECTABLE = {}`）。`ARTIFACT_PATH_REJECTED` 按合同第 24 节在真实管线中
“不可能”，只能经执行器的 `materialize_artifact` 绑定注入（与 S4 映射表测试同一接缝）；已如实注入。

**resume 点覆盖**：covered **24 / required 24**（`test_gate_run_covers_every_resume_point`：`full_13`（|E| = 21）p = 1..20、
`nfo_only`（|E| = 5）p = 1..4；故障用例只使用这两种 manifest，因此所用每个 E 的每个合法前缀都被覆盖）。
在 Windows 主机上，原生 rename 的发布后校验失败用例 p = 3（原子 rename 同时记录 `MEDIA_PUBLISHED` + `SOURCE_REMOVED`）；
POSIX 主机上为 p = 2；两种主机上覆盖集合都完整。

### 5.4 1000 extrafanart（实际执行）

`test_one_film_really_materializes_1000_extrafanart`：一个独立影片执行 1000 张 extrafanart：effect 序号 1..1000 依序；
effect 路径名 `extrafanart-001.jpg` .. `extrafanart-1000.jpg`；目录列举恰好这 1000 个名称（无缺失、无重复、无多余）；
每个文件字节等于定义字节，1000 份内容互不相同；目标目录整体精确。PASS。

### 5.5 冲突（同目标 / 重复番号）

7 对（每对两个不同源、同一番号）：3 对 mkdir 窗口竞争（native / hardlink / cross_volume：B 已通过只读重新校验与 U1 缺失探测，
A 在 B 的独占 `mkdir` 之前完整执行；确定性交错、无线程）、3 对重新校验（A 先完成，B 的执行时重新校验看到目标已存在）、
1 对 `threading.Barrier` 并发（只断言与调度无关的结果）。每对：恰好一个 `SUCCESS`、另一个 `FAILED(TARGET_CONFLICT)`、
step `CREATE_DIRECTORY`、零 effect、无 checkpoint；目标目录内容 == 胜者的静态期望（无覆盖、只有一个最终媒体）；
败者源字节（非线程对还有 inode / mtime）不变。

### 5.6 无关文件保留

每个源目录与每个 library root 植入 `.fc2tmp-cccc….part`、`unrelated.part`、`unrelated.tmp`、`user-file.txt`；每个 library root
另有用户影片目录 `FC2-0000001-user/keep.mp4`。在**每个**用例（成功、失败、resume、冲突）之后以及语料结束时断言全部逐字节、
inode、mtime 不变。另有 90 个成功用例在目标目录与 extrafanart 目录刚被创建时植入 3 个无关条目，执行结束后同样不变
（540 次检查）。没有任何 wildcard 清理。

### 5.7 确定性

整个语料（500 + 7 对）在两个独立根目录中各执行一次（模块 fixture），`test_gate_is_deterministic_across_two_runs` 断言：
除 checkpoint_id、preflight_id、seal、私有 token 与 leftover 名称中的随机 token 外，每个用例的状态序列（状态、模式、失败
step / kind / stage / write_stage / target_published、完成数、新增数、leftover 角色）、effect 种类 / 顺序 / 相对路径 /
ordinal / size / sha256、最终布局（相对路径 -> sha256）、传输模式、`media_sha256` 全部相等；冲突对结果相等。
不依赖 sleep、线程调度概率或重试碰运气。

pytest 文件本身也连续运行两次：Run 1 16 passed（63.55 s），Run 2 16 passed（44.03 s）。

## 6. 平台语义门槛（`test_execution_platform_semantics.py`，合同第 26 节）

34 passed / 6 skipped（本机 Windows）。

| 合同条目 | 测试 | 证据类别 | 结果 |
|---|---|---|---|
| 26.1 同卷 rename、无替换 | `test_windows_same_volume_publish_is_one_rename_without_replacement` | Windows 原生 | PASS |
| 26.1 已有目标绝不覆盖（精确名 / 大小写变体 × 同卷 / 跨卷发布） | `test_windows_existing_target_is_never_replaced`（4 个参数） | Windows 原生 | PASS |
| 26.1 同上（非 Windows 主机可运行的模型） | `test_rename_strategy_seam_never_replaces_on_any_host` | 接缝 | PASS |
| 26.1 reparse point：junction library root | `test_windows_junction_library_root_is_refused` | Windows 原生 | PASS |
| 26.1 reparse point：单元之间目标目录被换成 junction | `test_windows_target_directory_replaced_by_junction_between_units` | Windows 原生 | PASS |
| 26.1 reparse 属性判定 | `test_reparse_point_attribute_is_a_link_on_any_host` | 词法（任意主机） | PASS |
| 26.1 / 26.2 symlink library root | `test_symlink_library_root_is_refused` | 原生（需 symlink 权限） | **SKIP**（无权限） |
| 26.1 casefold 列举 / 26.2 精确比较 | `test_resume_inventory_uses_the_host_name_rule`（按主机规则）、`test_name_comparison_rules_casefold_on_windows_exact_on_posix` | 本机原生规则 + 词法 | PASS |
| 26.1 只读源：rename 可移动；link 策略 unlink 失败 -> `SOURCE_UNLINK_FAILED`，不 chmod，用户清除属性后 resume | `test_windows_read_only_source_is_never_chmodded`（rename / link） | Windows 原生 | PASS |
| 26.1 同上 | `test_source_unlink_permission_error_seam_never_chmods` | 接缝 | PASS |
| 26.1 无目录 fsync | `test_windows_never_fsyncs_a_directory`（同卷 / 跨卷）、`test_windows_directory_fsync_rule_through_the_seam` | Windows 原生 + 接缝 | PASS |
| 26.1 共享冲突 fail closed（同卷 -> `MEDIA_TRANSFER_FAILED`；跨卷 -> `SOURCE_UNLINK_FAILED`），关闭句柄后 resume | `test_windows_sharing_violation_fails_closed_then_resumes`、`test_sharing_violation_seam_on_any_host` | Windows 原生 + 接缝 | PASS |
| 26.2 顺序 link -> 校验 -> 目录 fsync -> 源重新校验 -> unlink（同卷 / 跨卷） | `test_posix_strategy_order_through_the_seam` | 接缝 | PASS |
| 26.2 同上，真实 `O_DIRECTORY` fsync | `test_posix_native_link_order_with_a_real_directory_fsync` | POSIX 原生 | **SKIP**（Windows 主机） |
| 26.2 发布无覆盖（EEXIST） | `test_link_publish_never_replaces_an_existing_final`（同卷 / 跨卷） | 接缝选择策略，`os.link` 为本机原生 | PASS |
| 26.2 `O_NOFOLLOW` 标志 | `test_cross_volume_source_open_flags` | 接缝观测（Windows 无 `O_NOFOLLOW`：证据缺口） | PASS |
| 26.2 `O_NOFOLLOW` 拒绝换入的 symlink（ELOOP） | `test_posix_native_symlink_swapped_in_before_open_is_refused_by_o_nofollow` | POSIX 原生 | **SKIP**（Windows 主机） |
| 19 步 1：open 前换入另一文件被 fstat 身份拒绝 | `test_file_swapped_in_before_open_is_refused_by_the_fd_identity_check` | 本机原生 | PASS |
| 25 / 18.3：发布后源被替换不删除 | `test_source_replaced_after_publish_is_never_deleted`（同卷 / 跨卷） | 接缝策略 + 真实替换 | PASS |
| 26.2 区分大小写 | `test_posix_native_case_variant_is_a_distinct_entry` | POSIX 原生 | **SKIP**（Windows 主机） |
| 26.2 不支持 hard link fail closed（EPERM / EMLINK / ENOTSUP / EOPNOTSUPP） | `test_unsupported_hardlink_fails_closed_without_rename_or_copy_fallback`（4 个参数） | 接缝 | PASS |
| 26.2 不用可覆盖 rename | `test_link_strategy_never_calls_an_overwrite_capable_rename`（同卷 / 跨卷） | 接缝 | PASS |
| 26.2 主机策略为 link | `test_posix_native_host_strategy_is_link` | POSIX 原生 | **SKIP**（Windows 主机） |
| 17 / 19 / 26.1 真实跨卷 | `test_native_cross_volume_integrated_execution` | 原生跨卷 | **SKIP**（环境变量未配置） |

## 7. 非空洞性（mutation）门槛

临时生产变异，均**未提交**；每个变异只对一个生产文件做精确的单处 / 双处文本替换，运行两个 S6 文件，然后以
`git -c core.autocrlf=false checkout -- src/fc2_organizer/execution` 恢复，并逐文件验证 `git hash-object --no-filters` ==
HEAD blob 且 `git status -- src` 干净。

| 变异 | 改动 | S6 失败测试数 | 杀死它的测试（摘要） | 用例级原因 |
|---|---|---|---|---|
| A1 覆盖式发布（接缝原语） | `_fs.py`：`rename=os.rename` -> `os.replace` | 14 | `synthetic_gate`：`test_gate_run_every_case_passes`×2、`…failure_kind`×2、`…resume_point`×2、`…deterministic…`、`test_conflict_pairs…`、架构扫描；`platform`：`test_windows_existing_target_is_never_replaced`×4、`test_rename_strategy_seam_never_replaces_on_any_host` | fault 451（原生）/ 497（跨卷）：真实占用物被覆盖，结果 `SUCCESS` 而非 `TARGET_CONFLICT` |
| A2 覆盖式发布（调用点） | `transfer.py` 两处 `_fs._FS.rename(...)` -> `os.replace(...)` | 16 | 同 A1 + `test_windows_same_volume_publish_is_one_rename_without_replacement`、`test_sharing_violation_seam_on_any_host` | 451 / 497 被覆盖；450 / 462 / 492 的 rename 接缝注入被绕过（报告为空洞注入） |
| B1 删源前不重新校验源路径 | `transfer._unlink_verified_source` 去掉 `_source_state` 检查 | 12 | `synthetic_gate` 8 个语料测试；`platform`：`test_posix_strategy_order_through_the_seam`×2、`test_source_replaced_after_publish_is_never_deleted`×2（替换物被删除） | 467 / 494：删源前的注入点消失，源被直接删除 |
| B2 发布后不校验发布目标 | `transfer.py` 同卷与跨卷发布后校验条件改为 `if False` | 8 | `synthetic_gate` 8 个语料测试 | 466（link）/ 495（原生 rename）：`SUCCESS` 而非 `PUBLISHED_MEDIA_MISMATCH` |
| C 独占 mkdir 容忍已存在 | `directories._mkdir_exclusive` 增加 `except FileExistsError: return None` | 9 | `synthetic_gate` 8 个语料测试 + 架构扫描 | 3 个 mkdir 窗口竞争对：败者接管胜者目录，结果 `PARTIAL` 而非 `FAILED` 零 effect；489（U7 `EEXIST`） |

Mutants Restored：YES（每次变异后均验证字节级恢复；恢复后重新运行 S6 门槛 0 failed，见第 8 节）。

执行过程说明（如实记录）：首轮变异运行因 `--basetemp` 父目录不存在而全部在 fixture 阶段报错（无效运行，不计为证据）；
同一轮中以默认 `git checkout` 恢复时，本机 `core.autocrlf=true` 使三个生产文件的工作区换行变为 CRLF（内容与 blob 等价，
`git diff` 为空）。已以 `core.autocrlf=false` checkout 恢复为与 HEAD blob 字节一致的 LF 文件，并修正脚本后重跑全部变异，
上表为重跑结果。

## 8. 测试数字（全部在 S6 Code Review Candidate 工作树上；Python 3.12.10；`-p no:cacheprovider --basetemp=<job tmp>/…`）

```text
Synthetic gate  Run 1        16 passed, 0 failed                          （63.55 s）
Synthetic gate  Run 2        16 passed, 0 failed                          （44.03 s）
Platform semantics           34 passed, 6 skipped, 0 failed
Execution + architecture     1054 passed, 21 skipped, 0 failed            tests/unit/execution + tests/contract/test_execution_architecture.py
Same-source existing gate    31 passed, 0 failed                          tests/unit/execution/test_execution_race.py
Contract suite               177 passed, 0 failed                         tests/contract
Full suite                   5227 passed, 40 skipped, 0 failed            （154.87 s）
S6 Frozen Base baseline      5177 passed, 34 skipped, 0 failed
```

差额：passed +50 = 16（synthetic）+ 34（platform）；skipped +6 = platform 的 6 个 skip。

### 8.1 全量 skip 明细（40）

S6 新增（6）：

```text
1  test_execution_platform_semantics::test_symlink_library_root_is_refused          symlink creation not permitted on this host
1  test_posix_native_link_order_with_a_real_directory_fsync                          POSIX native evidence: NOT EXECUTED on a Windows host
1  test_posix_native_symlink_swapped_in_before_open_is_refused_by_o_nofollow         POSIX native evidence: NOT EXECUTED on a Windows host
1  test_posix_native_case_variant_is_a_distinct_entry                                POSIX native evidence: NOT EXECUTED on a Windows host
1  test_posix_native_host_strategy_is_link                                           POSIX native evidence: NOT EXECUTED on a Windows host
1  test_native_cross_volume_integrated_execution                                     FC2_EXECUTION_CROSS_VOLUME_ROOT not configured
```

既有（34，与基线相同）：execution symlink 权限 13、`test_execution_transfer_cross_volume.py:203` 原生跨卷 1、
`test_execution_transfer_same_volume.py:149` 原生 POSIX link 1、discovery symlink 权限 4、materialization symlink 权限 5、
planning 的 POSIX 路径形式 10（13 + 1 + 1 + 4 + 5 + 10 = 34）。全部属于施工计划第 0.2 节允许的 skip 类别；skip 不计为通过。

### 8.2 git diff --check

* Code Commit（`f0ffb94..ae1ace9`）：干净。
* Docs Commit（`ae1ace9..Docs Head`）：干净（提交前 `git diff --cached --check`）。

## 9. 直接复现表

| 项目 | 命令 / 测试 | 状态 | 结果 |
|---|---|---|---|
| 500-item gate | `pytest tests/unit/execution/test_execution_synthetic_gate.py` | EXECUTED | PASS（500 SUCCESS，×2 运行） |
| 每个可注入 `ExecutionFailureKind` | `…::test_gate_run_covers_every_injectable_failure_kind` | EXECUTED | PASS（27 / 27） |
| resume 点覆盖 | `…::test_gate_run_covers_every_resume_point` | EXECUTED | PASS（24 / 24） |
| same-target conflict | `…::test_conflict_pairs_have_exactly_one_success_and_a_zero_effect_failure` | EXECUTED | PASS（7 对） |
| same-source safety（既有门槛） | `pytest tests/unit/execution/test_execution_race.py` | EXECUTED | PASS（31 passed） |
| 1000 extrafanart | `…::test_one_film_really_materializes_1000_extrafanart` | EXECUTED | PASS |
| Windows native | `test_execution_platform_semantics.py` 中 `native_windows` 用例 | EXECUTED | PASS |
| POSIX seam | `test_posix_strategy_order_through_the_seam` 等接缝用例 | EXECUTED | PASS |
| POSIX native | `native_posix` 用例 | NOT EXECUTED | EVIDENCE GAP（Windows 主机） |
| real cross-volume | `test_native_cross_volume_integrated_execution` | NOT EXECUTED | EVIDENCE GAP（环境变量未配置） |
| unrelated-file preservation | 语料每个用例后 + 结束时 | EXECUTED | PASS |
| source-not-lost invariant | 每次注入失败后 `assert_source_not_lost` | EXECUTED | PASS |
| determinism rerun | `…::test_gate_is_deterministic_across_two_runs` + 文件连续两次 | EXECUTED | PASS |
| mutant A（A1 / A2） | 第 7 节 | EXECUTED | 被杀死（14 / 16 failed） |
| mutant B（B1 / B2） | 第 7 节 | EXECUTED | 被杀死（12 / 8 failed） |
| mutant C | 第 7 节 | EXECUTED | 被杀死（9 failed） |

## 10. 证据缺口（真实情况，接缝证据不冒充原生证据）

```text
Windows native symlink        : NOT EXECUTED -- symlink creation not permitted on this host（未要求管理员 / 开发者模式 / 改策略）
POSIX native                  : NOT EXECUTED -- Windows host（link + 真实 O_DIRECTORY fsync、O_NOFOLLOW ELOOP、区分大小写、主机策略）
                                 POSIX 策略只有接缝级证据（在 NTFS 上以 os.link 执行，目录 fsync 由 FakeDirectoryFsync 观测）
O_NOFOLLOW                    : Windows 无该标志；只证明“平台定义时一定携带”；Windows 上由 reparse lstat + fstat 身份检查替代（已原生执行）
Native cross-volume           : NOT EXECUTED -- FC2_EXECUTION_CROSS_VOLUME_ROOT not configured；150 个跨卷用例全部为 device_of 接缝模拟
UNC library root（S5 既有）   : 视主机管理共享可用性（S5 用例，本批未改变）
```

## 11. 延续项（合同第 33 节，原样记录）

| 延续项 | P4-C7 的处理 |
|---|---|
| OrganizePlan 操作图模型层加固（P4-C2 入口门槛） | 在执行边界实施（第 6 节）；planning 模型本身不改 |
| overwrite 执行器语义（冻结为 NEVER） | 在执行层对真实文件系统实施（第 23 节） |
| 扩展的 Windows 保留名 | 在执行边界对 P4-C7 创建的组件 fail closed（第 26.3 节）；planning finding 仍 CARRIED |
| P4-C2-R1-02（裸 `\\server`） | 在执行边界拒绝（第 6.6 节）；planning finding 仍 CARRIED |
| P4-C1-R-02..R-05 | 通过源快照重新校验中和“发现结果过期”；scanner finding 仍 CARRIED |
| P4-C3-R-01、P4-C3-R-02、P4-C4-R-01、P2-R-05、P2-R-06、P2-R-07、C3-N1..N4、C4-N1、C4-R1-N1..N3、F3、F5、C5-R1-L1 | 不触及、不相关（P4-C7 不依赖相应模块） |

S6 不宣称修复任何 carried 项；不重新开放任何已 CLOSED 的 S1-S5 finding（S5 findings 最终状态见合同第 32.1 节）。

## 12. 已知局限

* **跨进程源所有权**：第 15.6 节的源所有权占用是进程内登记表；跨进程同源执行不在其保证之内（合同第 15.6、25 节剩余风险：
  只保证不覆盖、无静默源丢失、fail closed）。S6 没有、也不应增加跨进程同源唯一性测试；避免跨进程派发同一源属于 P4-C8。
* **TOCTOU**：基于字符串路径 API；对恶意本地行为者的“重新校验与修改 syscall 之间”窗口不提供防御（合同第 25 节声明）。
* **进程内 checkpoint**：进程退出后 checkpoint 失效，之后 fresh preflight 以 `TARGET_DIRECTORY_EXISTS` fail closed（第 14.1、29 节）。
* **真实平台证据缺口**：见第 10 节。
* **范围之外**（合同第 34 节）：批量编排、预览 UI、CLI、JSON / 诊断导出、持久化 / 磁盘 resume、数据库、回滚、覆盖、自动加后缀、
  `library_root` 创建、祖先链接检查、空间预检、长路径前缀改写、`openat` / 句柄相对 API、`ctypes`、权限修改、源父目录清理、
  Amane 集成、metadata / NFO / 图片处理。
* 本文件不产生新的产品承诺。

## 13. 未决事项

```text
未解决技术决策       : NONE
需要外部业务决策     : NONE
阻塞性已知问题       : NONE
```

## 14. 状态

```text
S6 implementation     : COMPLETE — INDEPENDENT REVIEW REQUIRED
P4-C7 implementation  : COMPLETE — INDEPENDENT REVIEW REQUIRED
合同第 32 节 S6       : S6 IMPLEMENTED — INDEPENDENT REVIEW REQUIRED
P4-C7                 : NOT CLOSED
Phase 4               : NOT CLOSED
```
