# P4-C7 施工计划（Construction Plan）-- 安全文件系统执行器

```text
Phase          = 4
Package        = P4-C7 Safe Filesystem Executor（fc2_organizer.execution）
Frozen Base    = a0a69c71a1451232ded2c8ae8ecd514cf48ba95b（DOCS-CN Final Closure Head）
Branch         = claude/phase4-c7-safe-filesystem-executor
规范合同       = docs/specifications/PHASE4_SAFE_FILESYSTEM_EXECUTION_CONTRACT.md
状态           = E0 ESTABLISHED；S1-S6 NOT STARTED
```

本计划在 E0 一次性冻结 P4-C7 的全部施工批次。之后的开发**只能执行本计划**：不得重新设计下一批，
不得调整批次边界，不得把本计划中的任何设计项推迟到“开发时再决定”。凡本计划或合同未写明的实现细节
（内部 helper 命名、测试 fixture、断言写法），由开发者按以下优先级自行裁决并在该批的 commit message 中记录理由：

```text
1. Frozen Contract   2. no data loss   3. overwrite NEVER   4. fail closed
5. deterministic     6. minimal dependency   7. testability
```

## 0. 全局规则（适用于每一批）

### 0.1 Git 纪律

* 每一批开始前验证：`HEAD == origin/claude/phase4-c7-safe-filesystem-executor == 上一批的 Head`，工作区干净
  （只允许未跟踪的 `.claude/`）。
* 禁止 rebase、amend、squash、force push、改写已复查的历史。只追加新提交。
* 每一批结束时 push，并记录 Head SHA。
* 除本计划明确列出的文件外，不得修改任何文件。

### 0.2 测试命令

```text
python -m pytest -q -p no:cacheprovider --basetemp=<job tmp>/pt tests/unit/execution tests/contract/test_execution_architecture.py
python -m pytest -q -p no:cacheprovider --basetemp=<job tmp>/pt
git diff --check
git status --porcelain
```

`--basetemp` 与 `-p no:cacheprovider` 在开发主机上是必需的（共享 pytest 临时根目录权限被拒绝）。
全量基线（Frozen Base，引自 P4-C6 / DOCS-CN 记录）：`4172 passed, 19 skipped, 0 failed`。
每一批的全量结果必须是 `0 failed`，且 passed 数不得低于上一批；新增 skip 必须逐项说明原因（仅允许：主机无 symlink 权限、
非 Windows 主机上的 junction、非 POSIX 主机上的原生 POSIX、未配置 `FC2_EXECUTION_CROSS_VOLUME_ROOT` 的真实跨卷）。
skip 不计为通过。

### 0.3 全局禁止范围

* 不修改 `src/fc2_metadata_core/**`、`src/fc2_organizer/{discovery,planning,publication,nfo,images,materialization}/**`、
  `src/fc2_organizer/__init__.py`、`pyproject.toml`、任何 JSON、`upstream/**`、Amane。
* 不修改已冻结的 Phase 4 合同（P4-C1..P4-C6）与已有 HANDOFF。
* 不新增第三方依赖。
* 不创建 CLI、UI、持久化、批量编排或 P4-C8 的任何占位文件。
* 不在测试中访问网络、读取用户文件或写入 `tmp_path` 之外的位置（`FC2_EXECUTION_CROSS_VOLUME_ROOT` 除外，
  且只在其下创建本测试专属的随机子目录）。
* 不要求关闭 Windows Defender 或任何系统安全功能。

### 0.4 每批的 commit 结构

每一批恰好一个代码提交（生产 + 测试 + 允许的测试守卫更新 + 合同第 32 节状态行），消息格式：

```text
feat(execution): <本批标题> (P4-C7 S<n>)

<实现摘要；自行裁决的实现细节及理由；测试数字>

Co-Authored-By: ...
```

S6 另有一个 docs 提交（handoff）。任何批次如需修正上一批的缺陷，只能作为新提交 `fix(execution): ... (P4-C7 S<n>)`
追加在本批内，并在 commit message 中说明。

### 0.5 通用测试辅助（S1 创建，之后各批只追加）

```text
tests/unit/execution/__init__.py
tests/unit/execution/_builders.py   # 通过 build_organize_plan + build_artifact_requests 构造真实 plan / manifest；
                                    # 伪造 helper（object.__setattr__ 改写、子类、重排操作）
tests/unit/execution/_helpers.py    # _FS 注入、策略切换（native / hardlink / cross-volume）、
                                    # 目录快照、源不变量断言 assert_source_not_lost(...)、
                                    # try_symlink / try_junction（与 materialization 测试同形）
```

`assert_source_not_lost(source_path, final_path, original_sha256)`：源路径或最终路径上至少一个是字节相同的普通文件。
S3 起每个失败注入测试都必须调用它。

---

## E0 -- Docs-Only Establishment

| 项 | 内容 |
|---|---|
| 输入 | Frozen Base `a0a69c7` |
| 允许改动文件 | `docs/specifications/PHASE4_SAFE_FILESYSTEM_EXECUTION_CONTRACT.md`（新增）、`docs/P4_C7_CONSTRUCTION_PLAN.md`（新增） |
| 禁止范围 | `src/**`、`tests/**`、JSON、`pyproject.toml`、任何其他文档 |
| 实现要求 | 冻结合同第 1-34 节与本计划 S1-S6 |
| 测试矩阵 | 无（docs-only）；`git diff --check` 干净 |
| 验收标准 | 只有上述两个新文件；正文简体中文；无未决技术决策 |
| commit | `docs(p4-c7): establish safe filesystem execution contract and construction plan` |

---

## S1 -- Foundation / graph / manifest / read-only preflight

### 输入

E0 Head；合同第 3-7、9-13、16、17、26、27 节。

### 允许改动文件

新增：

```text
src/fc2_organizer/execution/__init__.py
src/fc2_organizer/execution/errors.py
src/fc2_organizer/execution/models.py
src/fc2_organizer/execution/paths.py
src/fc2_organizer/execution/validation.py
src/fc2_organizer/execution/seal.py
src/fc2_organizer/execution/_fs.py
src/fc2_organizer/execution/preflight.py
tests/contract/test_execution_architecture.py
tests/unit/execution/__init__.py
tests/unit/execution/_builders.py
tests/unit/execution/_helpers.py
tests/unit/execution/test_execution_models.py
tests/unit/execution/test_execution_paths.py
tests/unit/execution/test_execution_graph.py
tests/unit/execution/test_execution_manifest.py
tests/unit/execution/test_execution_seal.py
tests/unit/execution/test_execution_preflight.py
```

修改（授权的最小守卫更新，每处只改所列内容）：

```text
tests/contract/test_discovery_architecture.py      顶层 package 集合 + "execution"（一行）
tests/contract/test_planning_architecture.py       顶层 package 集合 + "execution"（一行）
tests/contract/test_publication_architecture.py    顶层 package 集合 + "execution"（一行）
tests/contract/test_nfo_architecture.py            顶层 package 集合 + "execution"（一行）
tests/contract/test_materialization_architecture.py
    test_no_reverse_dependency_on_materialization：扫描时排除 ORGANIZER_SRC_ROOT / "execution"，
    并新增断言：execution 中对 materialization 的 import 只能是裸 "fc2_organizer.materialization"
    （理由：P4-C7 合同第 3 节授权的唯一消费者；其余反向依赖守卫不变）
docs/specifications/PHASE4_SAFE_FILESYSTEM_EXECUTION_CONTRACT.md   仅第 32 节 S1 状态行
```

S1 不创建 `directories.py`、`transfer.py`、`executor.py`；`__init__` 在 S1 只导出已实现的名称，
`execute_filesystem` 在 S5 加入（`__all__` 的最终集合由合同第 4 节冻结，S5 的架构测试断言等于该集合）。

### 禁止范围

任何修改性 syscall（`mkdir`、`rename`、`link`、`unlink`、`open` 写模式）；目录 / 媒体 / artifact 执行；
checkpoint 签发（S2）。

### 实现要求

1. `errors.py`：合同第 27 节全部异常类与四个拒绝原因枚举；固定措辞消息。
2. `models.py`：合同第 8、9、12、14.2、16、17、19、27 节全部枚举与 frozen/slots 模型；严格类型 `__post_init__`
   （`ExecutionModelError`）；`seal` 字段 `repr=False`；`ExecutionCheckpoint` 在 S1 只定义模型与校验，不签发。
3. `paths.py`：合同第 26.3 节词法校验器（`validate_absolute_path`、`validate_created_component`、
   `same_entry_name`、`is_under`），纯函数，按 `os.name` 选择规则，支持测试传入 `windows=` 参数以便两平台规则都在
   任一主机上测试。
4. `validation.py`：`validate_plan`（合同第 6 节全部检查，含重新构造）、`validate_manifest`（第 7 节）、
   `expected_units` / `expected_effects`（第 9 节）、私有常量 `_EXTRAFANART_FORMAT = "extrafanart-{:03d}.jpg"`。
5. `seal.py`：规范编码（第 15.2 节）、`plan_fingerprint`、`manifest_fingerprint`、进程密钥、`seal_of` /
   `verify_seal`、消费注册表（`register_consumption`，S5 才被执行器调用，S1 完成并单测）。
6. `_fs.py`：`_FsOps` frozen dataclass 私有接缝（`lstat`、`fstat`、`open`、`read`、`write`、`fsync`、`close`、
   `mkdir`、`rename`、`link`、`unlink`、`listdir`、`token`、`device_of`），模块级 `_FS`；
   `snapshot(path) -> EntryIdentity | OSError`、`is_link(stat_result)`（`S_ISLNK` 或 reparse 属性位）、
   `list_names(directory)`。S1 只有读操作被调用。
7. `preflight.py`：`preflight_execution(plan, artifacts, checkpoint=None)` 的 FRESH 路径完整实现（第 5、10、11、13、
   16、17 节）；RESUME 路径在 S1 中对任何非 `None` checkpoint 先完成契约层验证第 1-3 步（类型、封印、消费），
   之后抛出 `CheckpointError(SEAL_INVALID)`——因为 S1 无法签发合法 checkpoint，这一行为在 S2 被完整 RESUME 路径替换
   （S2 的允许文件中包含 `preflight.py`）。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_execution_models.py` | 每个模型的严格类型、枚举成员集合精确、`repr` 不含 seal / content、深度不可变 |
| `test_execution_paths.py` | 合同 26.3 全部拒绝原因 × Windows / POSIX 规则；扩展保留名（`COM¹`、`CONIN$`……）；裸 `\\server` 拒绝；与 `materialization.atomic._validate_target_path` 的共享语料一致性（P4-C6 拒绝的 P4-C7 必拒绝） |
| `test_execution_graph.py` | 合同第 31 节 “graph forgery” 全部条目；真实 `build_organize_plan` 计划（默认与自定义 `OutputPolicy`）全部通过；`object.__setattr__` 改写每个字段各一次均被拒绝；400 个合成计划零误报 |
| `test_execution_manifest.py` | 合同第 31 节 “manifest forgery” 全部条目；8 种可选主图组合 × extrafanart {0,1,13} 的真实 `build_artifact_requests` manifest 全部通过；1000 张 extrafanart 在内存中通过；`_EXTRAFANART_FORMAT` 与 `mapping.extrafanart_filename` 对 1..10000 一致 |
| `test_execution_seal.py` | 规范编码单射（构造前缀冲突反例）、`surrogatepass`、指纹对任意字段 / 单字节内容变化敏感、封印伪造 / 改写 / 换密钥被拒、`compare_digest` 使用（AST）、消费注册表并发（16 线程争同一 id，恰好一个成功） |
| `test_execution_preflight.py` | FRESH：全部 `PreflightBlockReason`（library root 缺失 / 是文件 / junction / symlink（可 skip）/ 无法访问 / inode 0 模拟；源缺失 / 链接 / 目录 / size 不符 / 无法访问；目标目录已存在的 5 种形态 / 无法访问）；多个阻断同时列出且顺序确定；`ready` 语义；传输模式预测（`device_of` 接缝）；`pending_units` / `skipped_steps` 精确；**零修改**：所有修改性接缝被替换为抛出 `AssertionError` 的函数后 preflight 仍正常完成；输入严格类型（子类钩子零调用） |
| `test_execution_architecture.py` | 合同第 3 节：模块集合精确；每模块 import 白名单；禁止 import 前缀；只 import 裸 planning / materialization；禁止调用名集合（`replace`、`makedirs`、`rmdir`、`rmtree`、`remove`、`removedirs`、`truncate`、`ftruncate`、`chmod`、`utime`、`copy*`、`move`、`glob`、`walk`、`scandir`、`expanduser`、`expandvars`、`getcwd`、`chdir`、`abspath`、`realpath`、`resolve`、`normpath`、`rollback`、`undo`、`revert`）；不引用 `is_valid_fc2_number` / `normalize_fc2_number` / `extrafanart_filename`；`_FS` 之外不直接调用 `os.<syscall>`；`fc2_organizer/__init__` 不导入 execution；无反向依赖；运行时阻断器下 import 与一次 preflight 端到端成功且被阻断模块未加载 |

### 验收标准

* 目标测试全部通过；全量 `0 failed`，passed 数 > 4172。
* preflight 零修改被测试证明。
* 四个 package 集合守卫与 materialization 反向依赖守卫的修改精确限于上面所列内容（handoff 中列出 diff）。
* `git diff --check` 干净。

### commit

`feat(execution): add P4-C7 foundation, plan graph and manifest hardening, read-only preflight (P4-C7 S1)`

---

## S2 -- Directory ownership + checkpoint / resume foundation

### 输入

S1 Head；合同第 13-15、21、22 节。

### 允许改动文件

新增：

```text
src/fc2_organizer/execution/directories.py
tests/unit/execution/test_execution_directories.py
tests/unit/execution/test_execution_checkpoint.py
```

修改：

```text
src/fc2_organizer/execution/preflight.py      完整 RESUME 路径
src/fc2_organizer/execution/seal.py           checkpoint 签发 helper（issue_checkpoint）
src/fc2_organizer/execution/models.py         仅在不改变合同字段的前提下补充内部校验
src/fc2_organizer/execution/_fs.py            仅新增 mkdir / listdir 包装
tests/unit/execution/_helpers.py、_builders.py（追加）
tests/unit/execution/test_execution_preflight.py（追加 RESUME 用例）
tests/contract/test_execution_architecture.py（追加 directories.py 规则）
合同第 32 节 S2 状态行
```

### 禁止范围

媒体传输、artifact 执行、`execute_filesystem`、任何删除调用。

### 实现要求

1. `directories.py`：
   * `create_target_directory(plan, library_root_identity) -> (EntryIdentity | None, ExecutionFailure | None)`：
     重新校验 library root -> `lstat` 目标必须不存在 -> `_FS.mkdir(path, 0o777)` -> `lstat` 快照；
     错误映射严格按合同第 21 节。
   * `create_extrafanart_directory(plan, target_directory_identity)`：合同第 22 节。
   * `revalidate_directory(path, identity) -> bool`。
   * `mkdir` 只出现在一个私有函数 `_mkdir_exclusive` 中（AST 断言）；从不 `makedirs` / `exist_ok`。
2. `seal.issue_checkpoint(...)`：生成 `checkpoint_id`、计算封印、返回 `ExecutionCheckpoint`。
   仅供 `executor.py`（S5）与测试调用；公开 API 不导出。
3. `preflight.py` RESUME 路径：合同第 14.3 节全部契约层与文件系统层检查，含 artifact 重新 hash（只读 `open` +
   `read`）、目录列举精确比较、leftover 临时文件容忍、源按阶段检查、`completed_units` / `pending_units` 推导。
4. 测试中通过 `issue_checkpoint` + 真实 `directories` 函数 + P4-C6 `materialize_artifact` 手工推进出“部分状态”，
   以便在 S5 之前验证 RESUME preflight（这是测试层编排，不是执行器）。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_execution_directories.py` | 独占创建成功与快照；已存在的文件 / 空目录 / symlink / 悬空 symlink / junction -> `TARGET_CONFLICT` 且不被触碰；library root 在 preflight 后被删除 / 替换为 junction -> `LIBRARY_ROOT_CHANGED`；mkdir 与 lstat 之间目标被替换（接缝）-> `TARGET_DIRECTORY_CHANGED`；权限错误 -> `DIRECTORY_CREATE_FAILED(errno)`；extrafanart 目录同样全套；并发：8 线程对同一目标 mkdir，恰好一个成功；`library_root` 永不被创建（缺失时 mkdir 接缝零调用） |
| `test_execution_checkpoint.py` | 签发 / 验证往返；合同第 31 节 “checkpoint mismatch” 全部条目；effect 非前缀的 6 种构造；`ALREADY_COMPLETE`；RESUME 文件系统层：每种 `PreflightBlockReason` 至少一次（`LIBRARY_ROOT_CHANGED`、`TARGET_DIRECTORY_CHANGED`、`UNEXPECTED_ENTRY`（文件 / 目录 / 植入的 `.fc2tmp-*.part` / 大小写变体）、`COMPLETED_EFFECT_MISSING`、`COMPLETED_EFFECT_CHANGED`（同尺寸改写 artifact、替换 inode、mtime 改变）、`SOURCE_CHANGED`、`SOURCE_MISSING`）；leftover 临时文件被容忍且不被删除；resume preflight 零修改 |
| `test_execution_architecture.py` | `mkdir` 只在 `_mkdir_exclusive`；`listdir` 只在 `_fs.list_names`；preflight 模块中无修改性调用 |

### 验收标准

目标测试全过；全量 `0 failed`；RESUME preflight 在所有构造出的部分状态上给出确定的 `pending_units`；
没有任何删除调用存在于生产代码中（AST）。

### commit

`feat(execution): add exclusive directory ownership and in-process checkpoint resume validation (P4-C7 S2)`

---

## S3 -- Same-volume + cross-volume media transfer

### 输入

S2 Head；合同第 17-20、25、26、29 节。

### 允许改动文件

新增：

```text
src/fc2_organizer/execution/transfer.py
tests/unit/execution/test_execution_transfer_same_volume.py
tests/unit/execution/test_execution_transfer_cross_volume.py
tests/unit/execution/test_execution_transfer_failures.py
```

修改：

```text
src/fc2_organizer/execution/_fs.py            仅新增 open/read/write/fsync/close/rename/link/unlink 包装
tests/unit/execution/_helpers.py（追加）
tests/contract/test_execution_architecture.py（追加 transfer.py 规则）
合同第 32 节 S3 状态行
```

### 禁止范围

artifact 执行、`execute_filesystem`、checkpoint 签发的调用方逻辑（S5）、任何回滚、`os.replace`、`shutil`。

### 实现要求

1. `transfer.transfer_media(plan, source_identity, target_directory_identity, mode, *, resume_phase)` 返回
   `TransferOutcome`（内部 frozen 模型：新增 effects、失败、实际模式、`media_sha256`、leftover 临时文件）。
   `resume_phase ∈ {FULL, SOURCE_REMOVAL_ONLY}`，后者只执行“（POSIX 目录 fsync）-> 源路径重新校验 -> unlink 源”。
2. 同卷：合同第 18 节，按 `os.name` 选择 Windows rename 或 POSIX link 策略；私有策略接缝
   `transfer._SAME_VOLUME_STRATEGY`（`"rename"` / `"link"`）供测试在 NTFS 上执行 POSIX 策略。
   `EXDEV` 回退跨卷一次。
3. 跨卷：合同第 19 节 10 步，严格按该顺序；1 MiB 块；SHA-256 边读边算；超长 / 过短立即中止；
   临时文件名 `.fc2tmp-<32 hex>.part`、`O_EXCL`、最多 8 次；发布使用无替换原语（Windows `rename`，POSIX `link` +
   unlink 临时文件）；发布后校验；POSIX 目录 fsync；源路径重新校验；最后 unlink 源。
4. `unlink` 只出现在两个私有函数：`_remove_owned_temp` 与 `_unlink_verified_source`；`rename` / `link` 只出现在
   `_same_volume_primitive` 与 `_publish_no_replace`（AST 断言）。
5. 只捕获 `OSError`；`BaseException` 与外来异常：关闭 fd、删除仍拥有的临时文件一次、原样传播同一对象。
6. 错误不含路径 / token / `OSError` 文本，不链接 `OSError`。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_execution_transfer_same_volume.py` | Windows 原生 rename 成功（effect 同时含 MEDIA_PUBLISHED + SOURCE_REMOVED，身份保留）；POSIX link 策略（接缝，NTFS 上执行；真实 POSIX 主机上原生执行，否则 skip 记录）：link -> 校验 -> 目录 fsync（POSIX 主机）-> 源重新校验 -> unlink 的调用顺序被记录并断言；目标被植入（文件 / 目录 / junction）-> `TARGET_CONFLICT`，植入物不变，源不变；`EXDEV` 注入 -> 回退跨卷且结果正确；共享冲突 / `EPERM` / `ENOTSUP` -> `MEDIA_TRANSFER_FAILED` 无 effect；发布后身份不符 -> `PUBLISHED_MEDIA_MISMATCH` 且源不删；unlink 前源被替换 -> `SOURCE_CHANGED` 且替换物不被删除；unlink 失败 -> `SOURCE_UNLINK_FAILED`，两个名称都在；零字节；Unicode 路径 |
| `test_execution_transfer_cross_volume.py` | 通过 `device_of` 接缝强制跨卷：0 B / 1 B / 1 MiB-1 / 1 MiB / 1 MiB+1 / 3 MiB+17 精确字节与 sha256；64 MiB 生成文件流式复制（按块断言每次读写 <= 1 MiB）；无残留临时文件；源最后才被删除（调用顺序断言）；真实跨卷（`FC2_EXECUTION_CROSS_VOLUME_ROOT`，否则 skip 并记录） |
| `test_execution_transfer_failures.py` | 每个 `TransferStage` 注入 `OSError`：open、源 fd 校验、临时创建（冲突重试成功 / 用尽）、读（首块 / 中间块）、写（错误 / 短写入续写 / 零写入）、fsync、close、源 fd 重新校验（复制中追加 / 截断 / mtime 变化）、发布（目标被抢占 / 其他 errno）、发布校验、临时 unlink（POSIX 策略，最终已发布）、目录 fsync、源路径重新校验、源 unlink；每一项断言：结果类型、effect 集合、临时文件已删除（或按合同记录为 leftover）、植入的无关 `.fc2tmp-*.part` / `.part` / `.tmp` 不变、**`assert_source_not_lost`**；在第 k 块注入 `KeyboardInterrupt` / `SystemExit` / 自定义 `BaseException` / `RuntimeError` -> 同一对象传播、临时文件被删除、源完好；清理失败不掩盖 `BaseException` |
| `test_execution_architecture.py` | rename / link / unlink 调用点精确集合；无 `os.replace`；`O_TRUNC` 不出现；临时文件标志含 `O_CREAT|O_EXCL` |

### 验收标准

目标测试全过；全量 `0 failed`；每一个失败注入测试都调用了 `assert_source_not_lost`（由一个元测试扫描
`test_execution_transfer_failures.py` 的 AST 断言每个测试函数都引用它）；删除源之前最终目标已发布且通过校验
（调用顺序断言）。

### commit

`feat(execution): add no-overwrite same-volume move and verified cross-volume copy for media (P4-C7 S3)`

---

## S4 -- Artifact execution + retry verification

### 输入

S3 Head；合同第 14.4、20、24 节。

### 允许改动文件

新增：

```text
tests/unit/execution/test_execution_artifacts.py
```

修改：

```text
src/fc2_organizer/execution/_fs.py            仅在需要时新增只读包装
src/fc2_organizer/execution/validation.py     仅新增 artifact 单元 -> 父目录角色映射 helper
新增 src/fc2_organizer/execution/executor.py  中的 artifact 部分：
    _execute_artifact_unit(request, parent_identity, ...) -> (CompletedEffect | None, ExecutionFailure | None,
                                                               leftovers)
    （executor.py 在 S4 创建，只包含 artifact 单元执行与 MaterializationError 映射；execute_filesystem 在 S5 加入）
tests/unit/execution/_helpers.py（追加）
tests/contract/test_execution_architecture.py（追加 executor.py 规则：artifact 只经 materialize_artifact）
合同第 32 节 S4 状态行
```

### 禁止范围

直接写 artifact 字节（必须经 `materialize_artifact`）；复制 / 改写 `request.content`；`execute_filesystem`；回滚。

### 实现要求

1. 合同第 24 节 1-6 步，映射表逐行实现（按异常类型分派，绝不看消息）。
2. `ArtifactCleanupError` 路径：列举父目录，记录“执行前不存在且匹配 `^\.fc2tmp-[0-9a-f]{32}\.part$` 的新条目”为
   `LeftoverTemporary`；`target_published=True` 时只读重新读取最终文件比较 sha256 后记录 effect。
3. 发布后校验：`MaterializedArtifact` 三字段与 `lstat`。
4. resume 中已完成的 artifact 不再调用 `materialize_artifact`（由 S2 的 `pending_units` 保证；本批用测试证明
   对已完成 artifact 的调用次数为零）。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_execution_artifacts.py` | NFO / POSTER / FANART / THUMB / EXTRAFANART 各自成功，字节精确、sha256、身份；`request.content` 身份一致（`is`，通过包装 `materialize_artifact` 捕获参数）；映射表每一行各一次（通过 `materialization.atomic._FS` 注入：write / flush / close / publish 失败、临时创建失败、目标无法 lstat、父目录消失、两种 `ArtifactCleanupError`，两种发布策略）；目标在单元开始前被植入 -> `TARGET_CONFLICT`，植入物不变；父目录在单元之间被替换为 junction -> `TARGET_DIRECTORY_CHANGED`；无关临时文件保留；leftover 记录名称精确；前一个 artifact 保留（无回滚）；已完成 artifact 零次重写；1000 个 extrafanart 单元顺序执行（名称、序号精确） |

### 验收标准

目标测试全过；全量 `0 failed`；AST 断言 execution 中写 artifact 的唯一路径是 `materialize_artifact`。

### commit

`feat(execution): add verified artifact unit execution with typed failure mapping (P4-C7 S4)`

---

## S5 -- Integrated single-item executor

### 输入

S4 Head；合同第 4、8、9、14.5、15.4、15.5、27-30 节。

### 允许改动文件

修改：

```text
src/fc2_organizer/execution/executor.py        新增 execute_filesystem
src/fc2_organizer/execution/__init__.py        导出集合 == 合同第 4 节冻结集合
src/fc2_organizer/execution/seal.py            （仅在必要时）消费登记的调用点
src/fc2_organizer/execution/models.py          （仅在必要时）ExecutionResult 不变量补充
tests/contract/test_execution_architecture.py（追加公开 API 精确集合）
tests/unit/execution/_helpers.py（追加）
合同第 32 节 S5 状态行
```

新增：

```text
tests/unit/execution/test_execution_executor.py
tests/unit/execution/test_execution_resume.py
tests/unit/execution/test_execution_race.py
```

### 禁止范围

批量编排、多影片 API、持久化、回滚、在失败后继续执行后续单元。

### 实现要求

1. `execute_filesystem(preflight)`：合同第 15.5 节冻结检查顺序 -> 消费登记 -> 执行前整体重新校验
   （library root、源（若 U2 未完成）、目标目录不存在（FRESH）或身份 + 列举（RESUME））-> 按第 9 节顺序执行
   待执行单元：U1 `directories`、U1 后按目标目录 `st_dev` 重新判定传输模式、U2 `transfer`（RESUME 且
   `MEDIA_PUBLISHED` 已完成时为 `SOURCE_REMOVAL_ONLY`）、U3-U6 artifact、U7 `directories`、U8.. artifact。
2. 首个失败即停止；计算累计 effect；按第 8 节确定状态；`PARTIAL` 时签发新 checkpoint（含累计 effect、
   leftover、各快照、实际传输模式）。
3. `BaseException` / 外来异常原样传播（下层已完成各自的临时文件清理）；不签发 checkpoint。
4. 结果模型不变量；错误与结果中不含路径文本以外的敏感信息（`CompletedEffect.path` 是合同规定的字段）。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_execution_executor.py` | 完整 `SUCCESS`：8 种可选主图组合 × extrafanart {0, 1, 13} × {native, hardlink, cross-volume}，最终目录精确列举、字节、源不存在、无临时文件；`FAILED`（U1 之前的每种失败，零 effect，checkpoint `None`）；`PARTIAL`（U1 之后每种失败）；`PreflightNotReadyError`（零文件系统访问、不消费）；封印伪造 / 字段改写 / manifest 对象在 preflight 后被改写 -> `PreflightIntegrityError`，零文件系统访问；同一 preflight 执行两次 -> 第二次 `CONSUMED`；`KeyboardInterrupt` 在每个单元边界 -> 同一对象、无 checkpoint、`assert_source_not_lost`；zero-byte media；Unicode 路径；library root 为 UNC（仅 Windows、可用时，否则 skip） |
| `test_execution_resume.py` | **resume after each partial point**：对每种 manifest 形态（仅 NFO；全主图 + 3 extrafanart），对 `E` 的每个前缀长度 p，在第 p+1 个 effect 注入失败 -> `PARTIAL` -> resume -> `SUCCESS`，最终布局与一次成功完全相同、已完成 artifact 零重写；连续两次失败再成功（checkpoint 链）；旧 checkpoint 重用 -> `CONSUMED`；resume 时换 manifest（单字节）-> `MANIFEST_MISMATCH`；resume 前改写已完成 artifact / 删除 / 植入条目 -> 对应阻断；`SOURCE_UNLINK_FAILED` 后 resume 只删源；`TARGET_DIRECTORY_FSYNC_FAILED` 后 resume；leftover 临时文件跨多次 resume 保持并被报告 |
| `test_execution_race.py` | 同目标：barrier 强制两个 preflight 都 `ready` 后并发执行 -> 恰好一个 `SUCCESS`、另一个 `FAILED(TARGET_CONFLICT)`、零 effect；8 线程 × 5 轮不同步；同一 preflight 两线程 -> 恰好一个执行；同一源两个不同库根 -> 最多一个完成媒体移动，另一个 `SOURCE_MISSING` / `SOURCE_CHANGED`，`assert_source_not_lost`；多进程（`multiprocessing`，spawn）各自执行不同目标 -> 全部 `SUCCESS` |

### 验收标准

目标测试全过；全量 `0 failed`；公开 API 集合精确等于合同第 4 节；所有 resume 点被参数化覆盖
（测试断言参数化数量 == `len(E) - 1`）。

### commit

`feat(execution): add integrated single-item filesystem executor with checkpoint retry (P4-C7 S5)`

---

## S6 -- Synthetic / fault / concurrency gate + final handoff

### 输入

S5 Head；合同第 31 节全部，尤其 31.1。

### 允许改动文件

新增：

```text
tests/unit/execution/test_execution_synthetic_gate.py
tests/unit/execution/test_execution_platform_semantics.py
docs/review/P4_C7_HANDOFF.md
```

修改：

```text
tests/unit/execution/_helpers.py、_builders.py（追加）
合同第 32 节 S6 状态行（实现完成；独立复查 REQUIRED）
```

生产代码：**不允许修改**。若门槛发现生产缺陷，必须先作为 `fix(execution): ... (P4-C7 S6)` 独立提交修复
（只改相关生产文件 + 回归测试），并在 handoff 中逐项记录；这不构成重新设计，任何修复不得改变合同语义。

### 禁止范围

新增生产功能；修改合同第 1-31、33、34 节；P4-C8 任何内容。

### 实现要求

1. `test_execution_synthetic_gate.py`：合同第 31.1 节 500-item 门槛，全部期望值来自用例定义；
   故障用例覆盖每个可注入的 `ExecutionFailureKind` 与每个 resume 点；每次失败断言核心不变量；
   冲突对；植入的无关文件最终逐字节不变；1 个影片执行 1000 张 extrafanart；架构回归扫描。
2. `test_execution_platform_semantics.py`：Windows 语义（rename 无替换、reparse 判定、`casefold` 列举、只读源 unlink
   失败、无目录 fsync 调用）与 POSIX 语义（link 无替换、`O_NOFOLLOW`、目录 fsync 在 unlink 源之前、区分大小写）；
   按主机执行原生部分，另一平台部分通过接缝执行；真实 symlink 用例在无权限主机上 skip 并记录。
3. 非空洞性检查（不提交）：至少三种生产变异——(a) 把无替换发布替换为 `os.replace`；(b) 去掉删源前的发布后校验 /
   源重新校验；(c) `mkdir` 改为容忍已存在——每种都必须使门槛失败；记录失败数后撤销。
4. `docs/review/P4_C7_HANDOFF.md`（简体中文）：坐标（Frozen Base、E0、S1-S6 Heads、Code Review Candidate、Docs Head）、
   变更文件清单、合同各节对应的实现与测试、测试数字（目标 / 全量 / skip 明细）、直接复现表、非空洞性结果、
   证据缺口（Windows 真实 symlink、POSIX 原生、真实跨卷）、延续项处理（合同第 33 节）、已知局限、状态
   `P4-C7 implementation: COMPLETE / Independent Review: REQUIRED / P4-C7: NOT CLOSED / Phase 4: NOT CLOSED`。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_execution_synthetic_gate.py` | 500 影片（200 native / 100 hardlink / 150 cross-volume / 50 fault+resume）；媒体尺寸集合；8 × extrafanart 0..13；1000 extrafanart；冲突对；核心不变量；无关文件保留；无临时残留（leftover 用例除外且名称精确）；确定性（同一用例集重跑结果相等，除 id / seal 外） |
| `test_execution_platform_semantics.py` | 合同第 26 节逐条 |

### 验收标准

* 门槛与全量测试 `0 failed`；skip 逐项说明。
* 三种变异全部被门槛杀死。
* handoff 完整，Code Review Candidate 与 Docs Head 分离（handoff 提交只含 handoff 文件与合同第 32 节状态行）。

### commit

```text
test(execution): add P4-C7 500-item integrated filesystem gate and platform semantics (P4-C7 S6)
docs(review): add P4-C7 handoff
```

---

## 附录 A. 合同条款 -> 批次映射

| 合同节 | 批次 |
|---|---|
| 3 架构 | S1（静态 / 运行时），S2-S5 追加 |
| 4 公开 API | S1（部分），S5（最终集合） |
| 5-7 输入 / 图 / manifest | S1 |
| 8-9 状态 / 单元 | S1（推导），S5（状态） |
| 10-13 library root / 源 / 身份 / fresh | S1 |
| 14-15 checkpoint / 封印 / 消费 | S1（封印、消费），S2（签发、RESUME），S5（执行器调用） |
| 16-17 preflight / 传输模式 | S1，S5（执行时重新判定） |
| 18-20 媒体 / 临时文件 | S3 |
| 21-22 目录所有权 | S2 |
| 23 overwrite NEVER | S2-S4（原语），S1（AST） |
| 24 artifact 执行 | S4 |
| 25 TOCTOU | S3-S6（窗口测试以接缝模拟；声明不变） |
| 26 平台 | S1（词法），S3（传输），S6（语义门槛） |
| 27 失败词汇 | S1（定义），S2-S5（产生） |
| 28-29 无回滚 / 取消 | S3-S5 |
| 30 P4-C8 接口 | S5（API 形态），S6（handoff 说明） |
| 31 测试总设计 | S1-S6（按上表），S6（500-item） |

## 附录 B. 裁决记录（E0）

| # | 裁决 | 理由 |
|---|---|---|
| 1 | 新顶层 package `fc2_organizer.execution` | materialization 冻结测试禁止 `executor.py`；职责不同 |
| 2 | 修改五个既有架构测试（四个集合守卫各一行 + materialization 反向依赖守卫豁免） | 与 P4-C3..P4-C6 新增 package 时的先例一致；豁免只针对合同授权的唯一消费者，并新增更严格的断言 |
| 3 | 不 import `materialization.mapping`；私有命名常量 + 测试一致性 | 避免加载 `fc2_organizer.images`（最小依赖），测试阻断漂移 |
| 4 | 自带词法路径校验器 + 测试一致性 | planning.paths / atomic 校验器非公开 API |
| 5 | 重新构造 `OrganizePlan` / `ArtifactWriteRequest` 以重跑模型校验 | 只用公开 API 抵御 `object.__setattr__` 改写 |
| 6 | 文件系统状态问题返回 blocker；契约问题抛异常 | preview 需要一次看到全部阻断；篡改 / bug 必须立即失败 |
| 7 | HMAC 进程密钥封印 + 一次性消费 | 保证 checkpoint / preflight 只能来自本进程且不可重放、不可改写 |
| 8 | 状态按累计 effect 判定 | resume 失败不应显示为“无影响”的 FAILED |
| 9 | 首个失败即停止 | 确定性、forward-only、resume 语义简单 |
| 10 | 链接形式的 library_root 被拒绝，祖先不检查 | 快照只能在非链接条目上有意义；祖先检查超出 v1.0 |
| 11 | inode 0 -> `IDENTITY_UNAVAILABLE` 阻断 | 删源依赖身份重新校验，无身份时 fail closed |
| 12 | 同卷 `EXDEV` 回退跨卷一次 | 此时无 effect，回退路径同样安全；避免永久卡死 |
| 13 | POSIX 同卷删源前目录 fsync | 防止崩溃后两个名称都丢失 |
| 14 | 跨卷不做第二次读取 hash | 大文件 I/O 翻倍；同缓冲区 hash + 大小 + fsync 已足够 |
| 15 | resume 时 artifact 重新 hash，媒体只比身份 | artifact 小，媒体可达数十 GB |
| 16 | 遗留临时文件只记录、容忍、永不删除 | 所有权无法在事后证明；P4-C6 同样不做基于列举的清理 |
| 17 | `BaseException` 不签发 checkpoint | 与 P4-C6 同一对象传播语义一致；数据安全由操作顺序保证 |
| 18 | 空内容 artifact 被拒绝 | 真实管线不会产生；fail closed |
| 19 | 扩展保留名、裸 `\\server` 在执行边界拒绝 | 中和延续项而不修改已关闭 package |

无需项目所有者决定的外部业务问题：以上裁决全部落在“存在明显更安全的 fail-closed 默认方案”的情形内。
