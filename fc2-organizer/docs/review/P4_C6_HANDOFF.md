# Phase 4 / P4-C6 Handoff -- Atomic Artifact Materialization

```text
Phase        = 4
Package      = P4-C6 Atomic Artifact Materialization
Role         = Developer
Branch       = claude/phase4-c6-atomic-materialization
```

## 1. Coordinates

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

History is linear: `e44790f -> b088db8 -> 67fb857 -> 2016107 -> 8f845b4 -> Docs Head`. Every
substep started from a verified `HEAD == origin/claude/phase4-c6-atomic-materialization == <parent>`
with a clean working tree (only the untracked harness `.claude/`). No rebase, amend, squash or force
push. The Docs Head commit contains only this file.

## 2. Type

**NEW PACKAGE** (`fc2_organizer.materialization`) + four one-line package-set scope-guard updates
(`test_{discovery,planning,publication,nfo}_architecture.py`: `+ "materialization"`). No production
file outside `fc2_organizer/materialization/` was touched; `fc2_organizer/__init__.py` is unchanged.
Substep 3 changed no production source (gate test + contract only).

## 3. Changed files (Code Review Range, 22 files, +3871 / -4)

New (18):
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

Modified (4, one line each -- package set only):
```text
fc2-organizer/tests/contract/test_discovery_architecture.py
fc2-organizer/tests/contract/test_planning_architecture.py
fc2-organizer/tests/contract/test_publication_architecture.py
fc2-organizer/tests/contract/test_nfo_architecture.py
```

## 4. Atomic Primitive (contract 3-5)

`materialize_atomic_bytes(target_path: str, content: bytes) -> MaterializedArtifact` -- synchronous,
two positional parameters, no overwrite / exist_ok / suffix / mkdir / fs-ops knob. Exact `str`
target (no `PathLike`, `bytes`, subclass; no hook runs) and exact `bytes` content (no `bytearray`,
`memoryview`, subclass) checked before any I/O. Explicit fully-qualified path only: no
`expanduser` / `expandvars` / cwd; no `.` / `..`; Windows drive or UNC root, no device namespace, no
`<>:"|?*` (an NTFS stream), no trailing dot/space, no reserved device name. Parent must be an
existing directory (never created); target `lstat`-ed, never followed.
`MaterializedArtifact(target_path, size_bytes, sha256)` -- frozen, slots, of the written bytes.

## 5. Overwrite NEVER (contract 6)

Anything at the target -- file, directory, symlink, dangling symlink, junction -> `TargetExistsError`,
untouched. No truncate / replace / delete / suffix. `os.replace` is never called (AST-enforced).

## 6. Platform Publish Strategy (contract 7)

| OS | primitive | existing target |
|---|---|---|
| Windows | `os.rename` = `MoveFileExW` without `MOVEFILE_REPLACE_EXISTING` | `FileExistsError` for any entry |
| POSIX | `os.link(temp, target)` then unlink temp | `EEXIST`; never follows the target |

The `lstat` pre-check is only an early exit; the no-overwrite guarantee is the publish primitive's
own, so a target created between check and publish is never replaced (tested with a planted file,
directory and symlink). No fallback to rename/replace on a filesystem without hard links
(`ArtifactPublishError`). File data is `fsync`ed; the parent directory entry is not.

## 7. Temp Ownership (contract 8)

`.fc2tmp-<32 hex secrets.token_hex(16)>.part`, sibling of the target, `O_CREAT|O_EXCL` (never
`O_TRUNC`), never derived from target / title / metadata / URL. Name clash -> new token (max 8), the
clashing entry is not touched; exhaustion -> `TemporaryCreateError`.

## 8. Cleanup Semantics (contract 9-10)

On any failure: close the fd, unlink **only the exact owned temp path**, once. No glob / wildcard /
listing cleanup; the final target is never deleted. Cleanup failure after a typed error ->
`ArtifactCleanupError(target_published=False, primary=...)`; POSIX post-publish temp-unlink failure
-> `ArtifactCleanupError(target_published=True)` with the complete target kept. `KeyboardInterrupt`,
`SystemExit`, `GeneratorExit`, any other `BaseException` and foreign exceptions propagate as the same
object; a cleanup failure never masks them. Errors carry fixed wording + errno only (no path, temp
token or `OSError` text) and are never chained to an `OSError`.

## 9. Concurrent Race Guarantee (contract 13)

N writers, one target: exactly one `MaterializedArtifact`, all others `TargetExistsError`; winner
bytes complete and never overwritten; every loser removes only its own temp. Tested barrier-forced
(both past the pre-check) and unsynchronised (8 writers x rounds), under both publish strategies,
directly and through `materialize_artifact`.

## 10. Artifact Request Model (contract 16)

`ArtifactKind` = NFO, POSTER, FANART, THUMB, EXTRAFANART. `ArtifactWriteRequest(kind, target_path,
content, ordinal=None)`: frozen, slots, exact types, `content` exact `bytes` (not in `repr`),
`ordinal` exact `int >= 1` iff EXTRAFANART. Holds no `PublicationRecord`, `AcquiredImage`, plan,
URL, HTTP data or exception.

## 11. Mapping Order (contract 17-18)

`fc2_organizer.materialization.mapping.build_artifact_requests(plan, nfo_text, images)` -- pure,
zero filesystem, deterministic; exact-type inputs checked before any attribute access; never reads
`OrganizePlan.operations`, never re-parses the canonical number. Order: NFO, POSTER?, FANART?,
THUMB?, EXTRAFANART in `images.extrafanart` tuple order. Forged plan paths / colliding targets /
wrong-role images fail closed (`ArtifactMappingError`).

## 12. NFO Encoding (contract 19)

Exactly `nfo_text.encode("utf-8", errors="strict")` to `plan.nfo_path`: no BOM, no newline change,
no strip, no normalization, no XML rewrite. Empty -> `NFO_EMPTY`; unencodable ->
`NFO_NOT_UTF8_ENCODABLE` (unchained).

## 13. Image Byte Identity (contract 20)

poster -> `poster_path`, fanart -> `fanart_path`, thumb -> `thumb_path`; absent image = no request,
not a failure; no cross-role fallback. `request.content is AcquiredImage.content` (no re-encode /
resize / transcode / copy). Duplicate bytes are not de-duplicated.

## 14. Extrafanart Naming (contract 21)

`<plan.extrafanart_directory>/extrafanart-{ordinal:03d}.jpg`, ordinal = 1-based tuple position, any
exact positive `int`; `03d` is a minimum width only (`1000 -> extrafanart-1000.jpg`). No maximum:
substep 2's self-invented 999 cap was removed in substep 2A because P4-C5 `max_extrafanart` is
unbounded. 0 / negative / bool / float / str / int subclass -> `INVALID_EXTRAFANART_ORDINAL`. Never
from URL, title, hash, `candidate_index` or randomness.

## 15. Single Artifact Materializer (contract 22)

`materialize_artifact(request)`: exact `ArtifactWriteRequest` (subclass rejected without hooks),
then only `materialize_atomic_bytes(request.target_path, request.content)`. One call = one artifact;
no `materialize_all` / `execute_plan` / `apply_operations` / `transaction` / `rollback_all`; an earlier
success is never rolled back by a later failure.

## 16. No Directory Creation / No MOVE_MEDIA (contract 23, 27)

No `mkdir` / `makedirs` anywhere (AST-enforced); missing target directory or `extrafanart/` ->
`ParentDirectoryMissingError`, not created. No `PlannedOperation` is read or executed; no
`MOVE_MEDIA`. Out of P4-C6 entirely: mkdir of target / extrafanart directories, MOVE_MEDIA, source
media verification, cross-volume move, whole-plan preflight, operation-graph execution, rollback
transaction, CLI/UI, persistence, Amane integration (P4-C7 and later).

## 17. Architecture (contract 14, 23)

* `__init__`, `errors`, `models`, `atomic`, `artifacts`: standard library + own package only.
* `mapping.py`: additionally the `fc2_organizer.planning` and `fc2_organizer.images` **public**
  packages (models only) and `os.path.join`. Never `httpx`, Amane, `fc2_metadata_core` directly,
  `images.transport`, `images.acquisition`, `nfo`, `publication`, `discovery`.
* `planning` loads `fc2_metadata_core` transitively, so `mapping` is **not** imported by the
  package `__init__`; `import fc2_organizer.materialization` loads no planning / images / core module.
* No `executor.py` / `move.py` / `orchestrator.py` / `planner.py`; no reverse dependency;
  `os.rename` / `os.link` only in the no-replace publish, `unlink` only via the owned-temp helper.
* Runtime blockers prove the primitive works with core / network / Amane blocked and `mapping`
  works with Amane / httpx / transport / acquisition / nfo / publication blocked.

## 18. Integrated Gate (contract 26)

`tests/unit/materialization/test_materialization_synthetic_gate.py` -- 35 tests, test-layer
orchestration only:

* **300 deterministic films**: 100 NFO-only, 100 NFO + all 7 non-empty main-art combinations,
  100 NFO + all 8 main-art combinations + 1..13 extrafanart; CJK / kana / emoji / XML-special /
  decomposed / tab titles, CRLF NFOs, duplicate bytes across roles and within extrafanart. Per film:
  order / kind / path / ordinal / bytes vs. case-derived expectation, identity, replay, then per
  request file bytes / size / sha256 / no BOM, exact directory listing, no temp residue.
* extrafanart 1 / 12 / 999 / 1000 names; 1000-item mapping in memory (nothing written).
* overwrite NEVER for all five kinds (bytes, inode, mtime, listing unchanged).
* partial success (NFO kept after poster `TargetExistsError`).
* failure injection write / flush / close / publish x {native, hardlink} + cleanup failure; planted
  unrelated temps intact.
* race: barrier-forced and unsynchronised x {native, hardlink}.
* architecture regression scan.
* Non-vacuity check (not committed): prefixing a BOM in `mapping._encode_nfo` -> 5 gate failures;
  `03d` -> `02d` -> 4 gate failures; both reverted.

## 19. Direct Reproductions (in the gate file)

| id | scenario | observed |
|---|---|---|
| A | new NFO | file bytes == `nfo_text.encode("utf-8")` |
| B | existing target | `TargetExistsError`, original bytes unchanged |
| C | two writers, same target | exactly one success, winner bytes on disk, loser `TargetExistsError` |
| D | write failure | `ArtifactWriteError`, no final file, the one owned temp removed |
| E | planted unrelated temps + publish failure | all planted files remain, nothing else |
| F | NFO success then poster failure | NFO remains complete |
| G | 1000 extrafanart mapping | 1001 requests, last `extrafanart-1000.jpg` |
| H | missing `extrafanart/` | `ParentDirectoryMissingError`, directory not created (mkdir trapped) |

## 20. Targeted Tests (at the Code Review Candidate)

```text
tests/unit/materialization/                                   303 passed, 5 skipped, 0 failed
  of which test_materialization_synthetic_gate.py              35 passed
  of which race + failures                                     85 passed, 2 skipped
tests/contract/test_{materialization,discovery,planning,
  publication,nfo,images}_architecture.py                     97 passed, 0 skipped, 0 failed
```

## 21. Full Suite

`python -m pytest -q -p no:cacheprovider --basetemp=<job tmp>` (both flags needed on this host:
the shared pytest temp root is permission-denied):

```text
4172 passed, 19 skipped, 0 failed
```

Progression: P4-C5 close 3852 / 14 -> substep 1 4052 / 19 -> substep 2 4122 / 19 -> 2A 4137 / 19 ->
substep 3 4172 / 19. The first substep-3 full run showed 7 failures, all in the new gate file: a
test-isolation defect (function-local imports of `ArtifactWriteRequest` picked up a newer class
generation after the architecture tests purge/re-import the package). Fixed in the test by
importing at module level; no production change. Skipped tests are not counted as passed.

## 22. Skipped / Environment Evidence Gaps (not PASS claims)

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

These are review evidence notes, not findings; no production design was changed for them.

## 23. Blocking Known Issues

None known to the developer. No finding IDs are created here.

## 24. Status

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
