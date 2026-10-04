# P4-C10 HANDOFF —— Phase 4 最终验收（Final Acceptance）候选证据快照

```text
文档性质                         : candidate evidence snapshot（S3 时点的开发者证据 + Post-Repair Evidence Refresh（Part III））+ Phase 4 Final Closure Docs Candidate（Part IV；closure history 记录，EC-15 REVIEW REQUIRED）
Package                          : P4-C10 Phase 4 Final Acceptance（无生产代码；只有 tests/phase4_acceptance/** 与 docs）
Risk Class                       : B（升级门 U-1..U-7 均未触发，见 Part I 第 13 项）
Frozen Contract / Plan           : ACCEPTED @ fc59e2020e4df237bf3bed83a07950d67c19b475（Design Accepted Head；Independent Design-R3 Closure Review PASS，据任务指令记录）
```

## 当前状态（CURRENT —— Phase 4 Final Closure Docs Candidate；详见 Part IV 第 20 节）

```text
P4-C10 Technical Acceptance Verdict          : PASS（由 Post-Repair Evidence Refresh Incremental Independent Level 1 Closure Review 建立；本文件作为 closure history 记录）
Final Reviewed Acceptance Head               : a87b9352e384327ea452c31ad650206df87fc975
EC-14                                        : SATISFIED
Active Authority Amendment Head              : 7d1a48f6e9b9ce1ac3234487b1126b58b879bc8b
Authorized Repair Head                       : a0d491d413a96ce9f08937dd5074adcd2144439d
Formal G-T / G-P4 / PC-04 / G-FULL / Skip    : PASS / PASS / PASS / PASS / PASS（第 19 节；reviewed）
Open F1 / F2 / F3 / F4                       : NONE
C5-R1-L1 Original Authority                  : RECOVERED AND INDEPENDENTLY VERIFIED（第 20.3 节）
XD-A08（C5-R1-L1）                           : REMEDIATED — EC-15 INDEPENDENT FINAL CLOSURE REVIEW REQUIRED（EC-15 PASS 之前仍计为 OPEN）
XD-C17（新增候选）                           : C 类 OUT OF PHASE 4 SCOPE；NON-BLOCKING；EC-15 REVIEW REQUIRED
Ledger（candidate）                          : A = 8 / B = 17 / C = 16
EC-01 Final Closure Recheck                  : PASS（第 20.5 节）
EC-10                                        : REMEDIATED — EC-15 REVIEW REQUIRED
EC-15                                        : PENDING —— INDEPENDENT DOCS-ONLY REVIEW REQUIRED
Phase 4 Final Closure Docs Candidate         : 本提交（parent a87b9352e384327ea452c31ad650206df87fc975；exact SHA 由 git 在提交后确定）
Phase 4 Exit Authorization                   : BLOCKED — EC-15 REVIEW PENDING
P4-C10 / Phase 4 / Phase 5                   : NOT CLOSED（TECHNICALLY ACCEPTED；NOT FINAL-CLOSED）/ NOT CLOSED / NOT STARTED
Next                                         : PHASE 4 FINAL CLOSURE DOCS INDEPENDENT EC-15 DOCS-ONLY REVIEW
```

下文第 0..18 节是 **S3 时点的历史 candidate evidence snapshot（HISTORICAL / COMPLETED / NOT CURRENT）**，原样保留、不追溯改写其证据；其中的状态字段只描述 S3 时点。

## 0. 三层状态字段（HISTORICAL S3 快照 —— NOT CURRENT；合同第 16.1a / 17 节；开发者不得写 PASS；当前状态见文首与第 19 节）

```text
Historical S3 Candidate Status               : BLOCKED — ENVIRONMENT（HISTORICAL / COMPLETED / NOT CURRENT）
                                               （正式证据环境 Windows 11 / Python 3.12.x 在本施工会话中不可得；其余全部已知技术门的证据已收集，
                                                 见下；这不是 F2：未发现任何 CLOSED production 偏离其 Frozen Contract 的缺陷）
P4-C10 Technical Acceptance Verdict          : NOT ESTABLISHED
C10 Acceptance Head                          : 本提交（HANDOFF 自指：`git log -1 --format=%H -- fc2-organizer/docs/review/P4_C10_HANDOFF.md`；
                                               Level 1 Review Report 记录其确切 SHA）
Final Reviewed Acceptance Head               : NOT ESTABLISHED
XD-A08（C5-R1-L1）                           : OPEN —— 只阻塞 Phase 4 Exit / Closure，不阻塞 Technical Acceptance
Phase 4 Exit Authorization                   : BLOCKED — LEVEL 1 / EC-15 PENDING；XD-A08；正式证据环境证据未取得
Phase 4                                      : NOT CLOSED
Phase 5                                      : NOT STARTED
Production Modified                          : NO
Production repair                            : NOT PERFORMED
```

**（历史说明）S3 时点为什么是 `BLOCKED — ENVIRONMENT` 而不是 `READY FOR LEVEL 1 REVIEW`。** 合同第 12.1 节、EC-08 与第 8 节要求 G-T / G-P4 / G-FULL 在
Windows 11 / Python 3.12.x 上取得；本会话是一个云容器（Linux 6.18 / Python 3.11.15，见第 4 项），开发者无法提供该环境。按合同第 16.1a 节，
`READY FOR LEVEL 1 REVIEW` 要求“全部已知 technical gate 在 candidate evidence 中满足”，该条件不成立，因此如实写 `BLOCKED — ENVIRONMENT`（合同授权的取值之一）。
这个值**不表示**任何技术门失败：在本环境得到的全部证据（见下）没有出现一个 C10 失败、没有出现新的失败 / 错误 / 未解释 skip。
Level 1 Reviewer 按计划第 11 节本来就必须在正式环境独立重跑；开发者另外补充了 PC-09 的非正式（Python 3.11 / POSIX）证据。
正式环境结果、以及据此重新判定 Candidate Status，属于下一步（见第 18 节“交接点”）。该环境缺口此后已由正式 Windows 证据闭合，当前 Candidate Status 见第 19 节。

---

# Part I —— P4-C10 验收证据

## 1. 坐标与提交线性

```text
Package Frozen Base        : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c（P4-C9 Final Closure Docs Head）
Planning Parent            : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c
Governance Authority       : 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Design Candidate（最终）   : fc59e2020e4df237bf3bed83a07950d67c19b475（Design-R3 Candidate；亦为 Design Accepted Head）
Design Accepted Head       : fc59e2020e4df237bf3bed83a07950d67c19b475
S1 Head                    : f9f95567b9f6ea243e7587219404b1e258023233   test(phase4): add C10 acceptance harness and oracles
S2 Head                    : eeac4e420202031944d3d0ca8dd405c469b93537   test(phase4): add C10 final acceptance scenarios
S3 / C10 Acceptance Head   : 本提交（`git log -1 --format=%H -- fc2-organizer/docs/review/P4_C10_HANDOFF.md`）
Review Range               : fc59e2020e4df237bf3bed83a07950d67c19b475..<C10 Acceptance Head>
```

提交线性证明（命令输出）：

```text
git log --oneline --graph fc59e202..eeac4e4
* eeac4e4 test(phase4): add C10 final acceptance scenarios
* f9f9556 test(phase4): add C10 acceptance harness and oracles
git merge-base --is-ancestor fc59e202 f9f9556  -> 真        git merge-base --is-ancestor f9f9556 eeac4e4 -> 真
git rev-list --merges fc59e202..eeac4e4        -> 空（无 merge 提交）
```

没有 amend / rebase / squash / force push / 历史改写；没有创建任何 design acceptance 状态提交。

S1 开始前的 authority / 漂移机器核对（合同第 4.1 节 / 计划第 7.1 节；分支 HEAD = origin = `fc59e202…`，工作树 clean）：

```text
git rev-parse origin/claude/phase4-c9-diagnostics                      = c293ed75e6ab3160d57ab8bf1248d1ce16ec241c
git merge-base --is-ancestor <合同 4.1 节全部坐标及其引用的中间坐标 + 3b9d39e…> = 全部为真（含 P4-C1..P4-C9 的 Frozen Base / Final Reviewed Head / Final Closure Docs Head、
                                                                         E0 / S5-A / Design Accepted 等引用坐标、00dc40d、17c194a、Governance Authority）
git diff --name-only <各 package Final Reviewed Code Head> HEAD -- src/fc2_organizer/<package>   = 空（discovery / planning / publication / nfo / images / materialization / execution / orchestration / diagnostics 九个均为 0 个文件）
git diff --name-only 1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f HEAD -- src/fc2_metadata_core        = 空
git diff 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d HEAD -- CLAUDE.md docs/PROJECT_GOVERNANCE_ACCELERATION.md pyproject.toml = 空
docs/review/P4_C{1..9}_HANDOFF.md 最终状态行                               = P4-C1: CLOSED / P4-C2: CLOSED / P4-C3: CLOSED / P4-C4: CLOSED / P4-C5 = CLOSED /
                                                                             P4-C6 : CLOSED / P4-C7 : CLOSED / P4-C8 : CLOSED / P4-C9 : CLOSED
git diff --name-only c293ed75… HEAD -- src tests（S1 开始时）              = 空
```

注：容器的初始克隆是浅克隆（50 个提交），第一次祖先检查因此对较早坐标报 FAIL；`git fetch --unshallow` 之后重新执行全部检查，结果如上（这是 F0 环境问题，不是 STOP-01）。

## 2. 完整 diff scope

```text
git diff --stat fc59e202...HEAD（S3 之前；S3 另加 HANDOFF 与两处状态行）
 fc2-organizer/tests/phase4_acceptance/__init__.py                       |    0
 fc2-organizer/tests/phase4_acceptance/_corpus.py                        |  634
 fc2-organizer/tests/phase4_acceptance/_harness.py                       | 1092
 fc2-organizer/tests/phase4_acceptance/_oracles.py                       |  572
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_architecture.py|  193
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_chain.py       |  414
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_determinism.py |   90
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_diagnostics.py |  133
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_global_gate.py |  203
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_harness.py     |  609
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_mutations.py   |  483
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_real_adapters.py| 134
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_retry.py       |  286
 fc2-organizer/tests/phase4_acceptance/test_p4_acceptance_safety.py      |  487
 14 files changed, 5330 insertions(+)
git diff --name-only fc59e202...HEAD -- fc2-organizer/src                 = 空（Production Modified : NO）
git diff --name-only fc59e202...HEAD -- fc2-organizer/tests                = 只含 fc2-organizer/tests/phase4_acceptance/**
git diff --check fc59e202...HEAD                                           = 干净
git status --porcelain                                                     = 空
```

S3 提交本身相对 S2 只新增 `docs/review/P4_C10_HANDOFF.md` 并同步合同第 20 节、计划第 15 节的状态行（见第 18 节的最终命令输出）。

## 3. Contract → 测试映射

全部测试在 `fc2-organizer/tests/phase4_acceptance/`（下表只写文件后缀与测试名；`test_p4_acceptance_` 前缀省略）。一个自动化的完备性门
（`safety::test_every_contract_id_appears_in_the_acceptance_tests`、`safety::test_every_safety_invariant_has_a_named_evidence_test_that_exists`）
机械地检查：S-01..S-22、L-01..L-14、SI-01..SI-22、M-01..M-14、G-500 每个 ID 都至少被一个 C10 测试按名引用，并且 SI 证据表里的每个测试函数真实存在。

| 合同条目 | 测试（文件::测试名） |
|---|---|
| S-01 + L-01..L-11 | chain::test_s01_legal_success_chain_over_fx1_with_links_l01_to_l11 |
| S-02 | chain::test_s02_metadata_partial_is_not_a_filesystem_partial |
| S-03 | chain::test_s03_one_source_failing_does_not_fail_the_film |
| S-04 | chain::test_s04_field_level_aggregation_agrees_with_the_nfo_and_the_diagnostics |
| S-05 | chain::test_s05_all_sources_fail_then_recover_through_the_phase3_retry |
| S-06 | chain::test_s06_unrecognized_number_never_reaches_the_engine_or_the_client |
| S-07 | chain::test_s07_image_partial_and_failure_are_reported_and_only_good_roles_are_written |
| S-08 | chain::test_s08_nfo_is_parseable_round_trips_and_an_invalid_date_fails_closed |
| S-09 | chain::test_s09_planning_rejection_creates_no_directory；chain::test_s09_windows_rooted_library_root_without_a_drive_is_rejected（仅 Windows） |
| S-10 | safety::test_s10_in_batch_conflicts_block_every_member_and_select_no_winner |
| S-11 | safety::test_s11_preflight_blocker_leaves_user_entries_untouched_and_rechecks_after_removal |
| S-12 | chain::test_s12_execution_success_variants[same-volume-native / cross-volume-seam] |
| S-13 | retry::test_s13_execution_partial_resumes_to_the_one_success_layout |
| S-14 | retry::test_s14_execution_failure_without_effect_re_executes_fresh |
| S-15 | safety::test_s15_a_foreign_exception_aborts_one_item_and_not_the_batch |
| S-16 | retry::test_s16_unselected_items_are_deferred_and_retry_to_success；retry::test_s16_cancellation_stops_admission_only_and_the_cancelled_items_retry |
| S-17 | retry::test_s17_retry_chain_over_fx2_with_exact_counts_and_one_time_consumption |
| S-18 + FX-5 | diagnostics::test_s18_canaries_never_leak_and_the_default_output_has_no_canary_at_all；diagnostics::test_s18_diagnostics_of_every_generation_consume_nothing_and_are_deterministic |
| S-19 | determinism::test_s19_two_fresh_trees_with_reversed_completion_order_give_identical_results；determinism::test_s19_a_third_ordinary_run_is_also_identical |
| S-20（FX-6） | real_adapters::test_s20_real_adapters_chain_crosses_every_boundary；real_adapters::test_s20_a_cloudflare_challenge_page_makes_the_aggregate_partial_not_failed |
| S-21 | safety::test_s21_user_entries_and_case_variants_are_never_overwritten_or_renamed；safety::test_s21_junction_library_root_is_refused_and_nothing_is_followed（仅 Windows） |
| S-22 | determinism::test_s22_peaks_equal_the_budget_and_never_exceed_it[2 / 3]；determinism::test_s22_a_budget_of_one_serializes_every_stage |
| G-500 | global_gate::test_g500_cross_package_global_gate_with_exact_frozen_counts_and_deterministic_rerun |
| M-01..M-14 | mutations::test_m01..test_m14（共 16 个测试函数，M-08 与 M-09 各有两个变体） |
| L-14 | diagnostics::test_l14_diagnostics_models_agree_with_the_models_they_describe |
| SI-01..SI-22 | safety 的 `SI_EVIDENCE` 表（逐项指向真实测试）；第 8 项给出逐项结果 |
| PC-01 | architecture::test_every_module_satisfies_the_architecture_rules[*]（含 3.12+ 名称 AST 禁用）及其 planted-violation 对照 |
| harness 正 / 负向对照 | harness::* 共 39 个测试（每个共享门在干净输入通过、在植入违规时失败；sandbox guard、socket 陷阱、写观察、故障注入、强制跨卷、并发 / 反转门） |

## 4. 环境记录（合同第 12.1 节）

```text
python -VV                          : Python 3.11.15 (main, Mar  3 2026, 09:26:23) [GCC 13.3.0]
platform.platform()                 : Linux-6.18.44-fc-v64-x86_64-with-glibc2.39
sys.getwindowsversion()             : 不可用（非 Windows；hasattr(sys, "getwindowsversion") == False）
httpx.__version__                   : 0.27.2（容器预装的是 0.28.1，超出 pyproject 的 >=0.27,<0.28；为符合 PC-03 已在环境中安装 httpx 0.27.2，pyproject 零改动）
pytest --version                    : pytest 9.1.1（容器内原先没有 pytest，已在环境中安装；不属于仓库）
basetemp 所在卷                     : /var/tmp/c10job/…（ext4，与系统盘同卷，位于仓库工作树之外；每次运行使用唯一的、运行前不存在的 basetemp）
运行身份                            : 证据运行以非特权用户 ubuntu（uid 1000）执行（会话本身是 root，没有用 root 跑任何证据命令）；不提权、不改系统安全设置
symlink 权限                        : 可用（POSIX），因此 Windows 的 symlink skip 在本环境是“执行”而不是 skip（与正式环境相反）
FC2_EXECUTION_CROSS_VOLUME_ROOT     : 未设置
网络                                : 测试不访问网络（SI-20：socket 陷阱零触发）
正式证据环境（Windows 11 / Python 3.12.x、NTFS、普通用户）: NOT OBTAINED（F0 环境限制）。本文件所有数字都来自上面的 Linux / Python 3.11 环境。
```

## 5. 测试数字

### 5.1 基线（S1，Design Accepted Head，加入 C10 tests 之前）

冻结命令（计划第 7.2 节）：`python -m pytest -q -p no:cacheprovider -rs --basetemp=<JOB_TMP>/c10-base-full --junitxml=<JOB_TMP>/c10-base-full.xml`

```text
结果：Interrupted: 2 errors during collection（7.66 s）—— 无 passed / failed 数字。
原因（F0，环境）：tests/unit/nfo/test_nfo_xml_safety.py 与 tests/unit/planning/test_planning_synthetic_gate.py 在 import 期用 `C:\downloads\...` 字面量构造
DiscoveredMediaItem，而 P4-C1 要求 source_path 为绝对路径；在 POSIX 上 `C:\…` 不是绝对路径。这是 Windows 主机上才成立的既有测试写法，不是被验收代码的缺陷。
```

补充基线（**非正式**；同一命令加上 `--continue-on-collection-errors`，仅为取得 Linux 上的集合数字；不改 production、不改测试、不加 skip / xfail / deselect / -k）：

```text
baseline passed  = 7195     baseline failed = 339     baseline errors = 26（含 2 个 collection error）
baseline skipped = 94       baseline collected（junit testcase 数）= 7654     耗时 138.75 s
SKIP_BASE        = 94 个 nodeid（见第 6 项）
失败 / 错误的构成：全部是 Windows 原生路径 / 语义的既有测试在 POSIX 上失败（例如 nfo_render 88、image_acquisition 83、planning_planner 57、publication_boundary 32、publication_models 25、image_synthetic_gate 17、publication_no_side_effects 15；完整分布见 junit）；
                   按合同第 13 节归类为 F0（环境），不是 F2；没有修改任何东西使其“变好看”。
```

对照：P4-C9 最终 Windows 验收为 `7767 passed / 0 failed / 40 skipped / 0 errors`（Windows 11 10.0.26200 / Python 3.12.10）。本环境的基线与它不同是预期的，**不能**用本环境的数字替代正式基线。

### 5.2 G-T（`tests/phase4_acceptance`）—— 连续运行三次，全部相同

```text
命令：python -m pytest tests/phase4_acceptance -q -p no:cacheprovider --basetemp=<JOB_TMP>/c10-gt-<run> --junitxml=<JOB_TMP>/c10-gt-<run>.xml
run 1：140 passed / 0 failed / 2 skipped / 0 errors（24.36 s）     run 2：同（23.97 s）     run 3：同（23.69 s）
两个 skip：S-09 的“Windows 有根无盘符 `\lib`”组、S-21 的“junction library root”组（合同第 8.1 节允许这两类 Windows 原生断言在非 Windows 的补充运行中 skip；
           在正式环境它们必须执行，0 skipped）。
测试构成：architecture 39、chain 11、determinism 5、diagnostics 3、global_gate 1、harness 39、mutations 16、real_adapters 2、retry 5、safety 19（共 140 passed）。
在任意顺序下稳定（合同第 12.7 节）：`tests/contract tests/phase4_acceptance` 与 `tests/phase4_acceptance tests/contract` 两种收集顺序下 C10 测试全部通过
（contract 目录中 3 个 `C:\` 路径写法的既有测试在 Linux 上失败，与基线相同）。
```

### 5.3 G-P4

```text
冻结命令（一个进程）：在本环境 INTERNALERROR 中止（见第 15 项 OBS-03）：`tests/unit/orchestration/test_orchestration_recognition.py::test_source_key_is_exact_on_posix`
  在 G-P4 的收集顺序下失败；该测试的 `no_io` fixture 把 `os.path.abspath` 变成陷阱，失败报告需要 abspath → pytest 内部崩溃。该测试单独运行或按目录运行都通过。
  这是既有测试的 POSIX / 顺序相关问题（测试在函数内 import 被 contract 守卫清理 sys.modules 后的第二份模块），与 C10 无关（C10 文件不在 G-P4 范围内）。
补充（非正式）：按目录分别运行同一命令的各个目录（--continue-on-collection-errors），合计：
  passed = 4777   failed = 338   errors = 26   skipped = 94
  与补充基线逐 nodeid 比较：新增失败 / 错误 = 0；不在 SKIP_BASE 中的 skip = 0。
```

### 5.4 G-FULL（含 C10）

```text
命令：python -m pytest -q -p no:cacheprovider -rs --continue-on-collection-errors --basetemp=<JOB_TMP>/c10-full-1 --junitxml=<JOB_TMP>/c10-full-1.xml（非正式环境）
结果：passed = 7335   failed = 339   skipped = 96   errors = 26   耗时 164.91 s
      passed = 7195（补充基线）+ 140（C10）= 7335；failed / errors 的 nodeid 集合与补充基线逐项相同（新增失败 = 0，被修复 = 0）。
```

### 5.5 瞬时失败

合同第 8.4 节的已知瞬时失败候选 `tests/unit/aggregation/test_agg_retry_execution.py::test_17_total_deadline_covers_attempt_backoff_and_retry_not_deadline_times_attempts`
在补充基线与 G-FULL 中均 passed；没有任何失败被按“瞬时”处理。

## 6. skip 基线对账（合同第 8.3 节；按 nodeid 比较）

```text
SKIP_BASE（补充基线，本环境）：94 个 nodeid                SKIP_C10（G-FULL，本环境）：96 个 nodeid
SKIP_C10 − SKIP_BASE = 2 个 nodeid（逐项）：
  tests.phase4_acceptance.test_p4_acceptance_chain::test_s09_windows_rooted_library_root_without_a_drive_is_rejected
  tests.phase4_acceptance.test_p4_acceptance_safety::test_s21_junction_library_root_is_refused_and_nothing_is_followed
  —— 合同第 8.1 节授权的平台门控（Windows 原生断言，只在非 Windows 补充运行中 skip）；正式环境必须 0 skipped。
SKIP_BASE − SKIP_C10 = ∅（没有基线 skip 被变成执行；可选原生跨卷证据未启用）
unexplained new skips = NONE
```

SKIP_BASE 的构成（本环境；与合同第 8.3 节第 2 项预期的 Windows 正式基线 40 项**不同**，因为这里 Windows 原生测试 skip、symlink 测试执行）：

| 目录 | 个数 | skip 原因（摘要） | 对应 Ledger |
|---|---|---|---|
| tests/unit/discovery | 9 | Windows 盘符相对路径 3、junction 3、Windows 原生路径解析 2、Win32 路径语义 1 | XD-B02（POSIX 主机证据：本环境恰是 POSIX 方向的证据；Windows 方向属正式环境） |
| tests/unit/execution | 43 | junction 18、“非 Windows 主机上未执行（仅接缝证据）”13、UNC 3、管理共享 1、大小写冲突 1、非法源组件 1、原生跨卷 2（`FC2_EXECUTION_CROSS_VOLUME_ROOT` 未配置）、Windows rename 策略 1、目录 fsync 1、共享冲突 1、只读源 unlink 1 | XD-B02 / XD-B04（原生跨卷）/ XD-B07（UNC） |
| tests/unit/materialization | 1 | junction | XD-B01 / XD-B02 |
| tests/unit/orchestration | 5 | junction 3、Windows 大小写不敏感键 2 | XD-B02 |
| tests/unit/planning | 36 | Windows 盘符 / UNC / 有根无盘符 / 点相对路径形式 | XD-B02 |

正式环境（Windows）的 40 个 skip 的逐项对账仍须在正式环境重新测量（`SKIP_BASE` 必须来自 Design Accepted Head、加入 C10 tests 之前；本环境测得的集合不能代替它）。

## 7. Cross-package acceptance summary（L-01..L-14；全部 Blocking）

| Link | 真实链路证据（本环境：通过） |
|---|---|
| L-01 文件系统 → P4-C1 | 每个场景与 G-500 的输入都由真实 `discover_media` 产生（S-01 断言 index 0..11、绝对路径、文件名集合；G-500 断言 500 个物理文件全部被发现） |
| L-02 P4-C1 → P4-C8 | `BatchOrchestrator.preview(DiscoveryResult.items)`；S-01 断言 `preview.items[i].media_item is items[i]`（身份）；S-10 的“同一对象两次” |
| L-03 P4-C8 → Phase 1 | 番号只来自文件 basename：S-01（含 CJK / emoji / NFC / NFD / 大小写扩展名）、S-06（无番号：engine / client 调用 0）、G-500 GE |
| L-04 P4-C8 → Phase 3 batch | 真实 `MultiSourceEngine` 下的 S-05（Phase 3 retry 恢复）与 G-500 GC（30 个全失败、20 个在第二次聚合恢复） |
| L-05 Phase 3 batch → aggregation | 真实 `MultiSourceEngine.aggregate → execute_sources_traced → SourceAdapter.fetch → merge_source_results`：S-01..S-05、S-20（真实 adapter + fixture HTML）、G-500 GA / GB / GC |
| L-06 P4-C8 → P4-C2 | 布局 oracle（S-01、S-12、`gate_library_exact`）；S-09 规划拒绝 |
| L-07 P4-C8 → P4-C3 | 真实 `AggregationResult → PublicationRecord`：S-02（partial）、S-04 |
| L-08 P4-C8 → P4-C4 | NFO oracle：独立序列化器的逐字节比较 + `xml.dom.minidom` 结构检查（S-04、S-08、S-20、M-09b） |
| L-09 P4-C8 → P4-C5 | 真实 `HttpxImageClient(transport=httpx.MockTransport)`：S-07、S-01 的 60 次图片请求精确匹配、G-500 GD；私有重定向目标从未被请求 |
| L-10 P4-C8 → P4-C6 mapping | 图片字节身份：落盘字节 == 提供给该 URL 的字节（S-01、S-07、M-09a） |
| L-11 P4-C8 → P4-C7 preflight | S-11 preflight 阻断、S-21 case 变体 / junction root；S-01 的 `preflight.ready` |
| L-12 P4-C8 → P4-C7 / P4-C6 执行 | 全部执行场景；`execute_filesystem` 调用计数、SI 共享门每轮运行（`Chain.gate_runs`） |
| L-13 重试 / checkpoint 交接 | S-13（`retry_item.preflight.checkpoint is previous.execution.checkpoint`）、S-14、S-16、S-17、G-500 g1..g4 |
| L-14 P4-C8 → P4-C9 | S-18（FX-5）、`test_l14_*`、G-500 的 14 个模型；履行 P4-C9 合同第 30 节对 diagnostics 的跨包覆盖 |

## 8. Safety invariants summary（SI-01..SI-22；本环境逐项通过）

| SI | 证据（测试 / 门） | 结果 |
|---|---|---|
| SI-01 | `Chain.execute` 每轮对全部输入运行 `gate_source_not_lost`（S-11..S-17、S-21、G-500 每轮共 5 轮）；safety 的故障形态矩阵（5 个形态）；M-01 杀死 | PASS |
| SI-02 | S-11 / S-21 / `test_si02_*`：预置目标、case 变体、最终媒体路径上的用户文件，bytes / size / mtime / inode 不变；M-02 杀死 | PASS |
| SI-03 | 故障形态矩阵：每个形态都是类型化的 disposition / failure kind，无裸异常 | PASS |
| SI-04 | S-03、`test_si04_*`（三个 source 各自失败）、`gate_metadata_isolation` 每次主 preview 运行；M-12 杀死 | PASS |
| SI-05 | S-15、G-500 GH / GI / GK 与 GA 同批 | PASS |
| SI-06 | S-22（门控下峰值 == 预算，2 / 3 / 1，三个预算各自）；G-500 峰值 4 / 4 / 4 ≤ 4；M-11 杀死 | PASS |
| SI-07 | S-19（两棵树 + 三个阶段反转完成顺序）、G-500 两次完整运行 14 个 NONE 诊断 JSON 逐字节相等；M-10 杀死 | PASS |
| SI-08 | S-13 NFO publish 故障后 NFO 不存在；故障形态矩阵 `artifact_publish` | PASS |
| SI-09 | G-500：最终仍在原位且字节不变的源恰为 65（GE 20、GF 20、GG 5、GC 10、GK 10）；`test_si09_*`（FX-2） | PASS |
| SI-10 | S-10（重复番号 / 同对象两次 / hardlink）、G-500 GF 10 对；`gate_phase_a_conflicts`；M-03 杀死 | PASS |
| SI-11 | 故障形态矩阵 + S-13 / S-14 / S-15（状态、checkpoint 存在性、effect 前缀） | PASS |
| SI-12 | S-17：scope 子集、二次 `preview_retry` / `merge_retry` → `OrchestrationConsumedError`、身份一致；M-05 杀死 | PASS |
| SI-13 | S-13 / G-500 g1：RESUME 后已完成 artifact 与媒体 inode / mtime 不变；`gate_resume_converges`；M-06 杀死 | PASS |
| SI-14 | 每轮 `gate_no_unreported_temporaries`；S-21 预置无关 `.fc2tmp-<32hex>.part` / `unrelated.part` / `unrelated.tmp` / `user-file.txt` 不变；M-13 杀死 | PASS |
| SI-15 | 写操作观察记录每个修改性路径 ∈ 目标目录集合 ∪ 源文件集合（每轮）；M-04 杀死 | PASS |
| SI-16 | S-21 junction library root（**Windows 原生，本环境 skip**）；symlink 原生证据处置见 XD-B01 | PASS（POSIX 部分）/ **Windows 部分 NOT RUN —— 正式环境必须执行** |
| SI-17 | `test_si17_*`、S-04 / S-20：真实 producer 输出跨全部边界被接受 | PASS |
| SI-18 | S-18、G-500 14 个模型 × canary 扫描（NONE 与 BASENAME；NONE 下 `C10CANARY` 完全不出现）；M-08 两个变体杀死 | PASS |
| SI-19 | 写观察 + 仓库只读摘要（`src`、`tests/support`、`tests/fixtures`、`pyproject.toml` 全部文件 sha256 前后相同）+ 诊断期间零写入 | PASS |
| SI-20 | socket 陷阱每轮零触发；陷阱非空洞性对照（harness 自检：四个原语逐一触发并被门报告） | PASS |
| SI-21 | 每次 preview / preview_retry 前后全树快照相等（`Chain` 内置，S-01..G-500 每次）；M-14 杀死 | PASS |
| SI-22 | 每轮 `gate_result_accounting`（summary 恒等式 + outcome 真值表独立重算）与 `gate_merge_composition`；G-500 / S-17；M-07 杀死 | PASS |

## 9. Scenario 与 G-500 结果

S-01..S-22：本环境全部通过（S-09 有根无盘符组、S-21 junction 组为 Windows 原生，本环境 skip，见第 3、6 项）。

G-500（两次完整运行，各约 9.3 s，含全部断言）。冻结计数同时对照“合同表的字面量”与“由组大小推导的值”（`G500_FROZEN` vs `mixed_expectations`，二者在 harness 自检中被证明相等）：

```text
配置                : OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=4), image_in_flight_items=4, filesystem_workers=4)
输入                : 500 个物理文件，由真实 discover_media 发现（500 个逻辑输入）
g0 preview          : total 500 / ready 410 / blocked 40 / unprepared 50
g0 result           : success 350 / partial 20 / failed 20 / aborted 10 / not_selected 10 / not_ready 90；outcome PARTIAL；
                      retryable 90（RESUME 20、FRESH_REEXECUTE 20、METADATA_REFETCH 30、PREFLIGHT_RECHECK 20）/ deferred 10 / non_retryable 50
g1 {RESUME}         : 20 READY → 20 SUCCESS；轮 outcome SUCCESS；合并 success 370
g2 {METADATA_REFETCH, FRESH_REEXECUTE, PREFLIGHT_RECHECK}：70 条 → ready 55 / blocked 5 / unprepared 10 → 55 SUCCESS；合并 success 425
g3 {DEFERRED}       : 10 READY → 10 SUCCESS；轮 outcome SUCCESS；合并 success 435
g4 scope=None       : 15 条（GC 10 + GG 5）→ ready 0、执行 0；轮 outcome FAILED
最终（合并）        : success 435 / blocked 25 / unprepared 30 / aborted 10；outcome PARTIAL；retryable 15
SI-09               : 最终仍在下载目录原位且字节不变的源恰为 65
最终 library        : 435 个成功影片目录（媒体字节 == 源字节；NFO 逐字节 == 独立序列化且可解析；图片字节 == 该 URL 被提供的字节；extrafanart 名称与顺序）、
                      5 个用户阻断目录（`user-note.txt` 不变）、10 个 ABORTED 条目的空目标目录、用户影片目录不变、无未报告临时文件
峰值                : metadata 条目 4、图片请求 4、文件系统 worker 4（均 ≤ 4）
诊断模型            : 14 个（主 preview、主结果、4 × {重试 preview、重试轮结果、合并结果}）全部以 NONE 构建并渲染；`json.loads` 可解析；主 preview 与最终合并结果另以 BASENAME 渲染；
                      全部 JSON canary 扫描通过；渲染文档大小 28 KB .. 1.4 MB
确定性重跑          : 第二棵全新树中完整再运行一次，14 个 NONE 诊断 JSON 逐字节相等
写操作观察 / 网络   : 全部修改性路径 ∈ 允许集合；网络陷阱零触发
故障注入            : GH 20（10 个 NFO publish 失败 + 10 个 poster publish 失败）、GI 20（源重验 lstat EIO）、GK 10（U2 `RuntimeError`）全部一次性触发并被证明已触发
```

另做的稳定性压力验证（开发者诊断，不入库）：S-19 路径 40 次、M-10 对照路径 6 进程 × 150 次并行（共 900 次）两棵树 NONE 诊断逐字节比较，0 次不一致。

## 10. Mutation / non-vacuity（M-01..M-14）

每个 mutant 只存在于测试进程内（`pytest.MonkeyPatch.context`），不写任何生产源文件；每个测试断言 (1) 同一场景不植入 mutant 时通过，(2) 植入后抛出 `AcceptanceGateViolation` 且消息指出的正是下表的门，(3) 被替换的绑定名恢复为原对象（`is`）。
失败数 = 每个 mutant 一个测试函数 1 个失败用例（M-08、M-09 各两个变体）。

| ID | mutant / 表面 | 杀死它的门（消息节选） | 测试 |
|---|---|---|---|
| M-01 | 包装 `orchestration.execute.execute_filesystem`：SUCCESS 后删除最终媒体 | SI-01 “the source media was lost” | mutations::test_m01_… |
| M-02 | 传输原语（Windows `_FS.rename` / POSIX 链接原语）替换为 `os.replace`；用户文件在执行器自身“最终路径不存在”检查之后出现在最终路径 | SI-02 “user entry … was modified” | mutations::test_m02_… |
| M-03 | 包装 `orchestration.preview.recognize`，去掉冲突标记 | SI-10 “Phase A member … was processed past the conflict check” | mutations::test_m03_… |
| M-04 | 包装 `execute_filesystem`：在 library 之外（tmp 树内）创建文件 | SI-15 “… neither an allowed target directory nor a source file” | mutations::test_m04_… |
| M-05 | `ItemExecution.retry_kind` 对调 RESUME / FRESH_REEXECUTE | SI-12 “item 17 has retry_kind fresh_reexecute, the frozen table says resume” | mutations::test_m05_… |
| M-06 | 包装 `execute_filesystem`：第二个 PARTIAL 的 checkpoint 换成第一个的 | SI-13 “the RESUME retry of item 1 does not converge on its own checkpoint” | mutations::test_m06_… |
| M-07 | 场景所用的 `merge_retry` 绑定：用旧代条目替换一个重试条目 | SI-22 “merged item 0 is not the retry item” | mutations::test_m07_… |
| M-08 | (a) 渲染绑定附带 `C10CANARY-AUTH`；(b) 预览构建器默认策略改为 `BASENAME` | SI-18 “the canary … leaked” / “the default diagnostics output contains canary text” | mutations::test_m08_…（2 个） |
| M-09 | (a) 包装 `stages.build_artifact_requests` 交换 poster / fanart 内容；(b) 包装 `stages.render_movie_nfo` 渲染另一条目的记录 | layout（图片字节身份 L-10 / NFO oracle L-08） | mutations::test_m09_…（2 个） |
| M-10 | 渲染绑定按 engine 阶段的完成顺序排列条目 | SI-07 “two runs over equal inputs produced different results” | mutations::test_m10_… |
| M-11 | 包装 `execute._execute_threaded`：每条目一个 worker | SI-06 “observed concurrency 8 exceeds the budget 2” | mutations::test_m11_… |
| M-12 | 真实 `MultiSourceEngine.aggregate` 在任一 source 未成功时返回 FAILED | SI-04 “… metadata status failed, the source outcomes give partial” | mutations::test_m12_… |
| M-13 | 包装 `execute_filesystem`：在目标目录留下未报告的 `.fc2tmp-<32hex>.part` | SI-14 “an unreported temporary file was left behind” | mutations::test_m13_… |
| M-14 | 包装 `preview.preflight_stage`：在只读阶段创建目录 | SI-21 “the tree changed (added=[…created-by-a-preview-stage…])” | mutations::test_m14_… |

恢复证明：每个测试结束断言绑定 `is` 原对象；harness 的 `PatchSet.restore` 在恢复时检查没有被他人替换；S3 的 `git hash-object --no-filters` 对比（下）：

```text
对 git ls-files -- fc2-organizer/src 的 104 个文件逐一比较 `git hash-object --no-filters <文件>` 与 `git rev-parse HEAD:<文件>`：104 个文件，0 个不一致
git status --porcelain：空
```

## 11. Platform / compatibility evidence（PC-01..PC-09）

| ID | 结果 |
|---|---|
| PC-01 Python 运行时权威 | PASS（静态）：`pyproject.toml` 零差异；架构守卫 AST 禁用 `isjunction` / `batched` / `override` / `Path.walk` / PEP 695 等；C10 测试在 Python 3.11.15 上全部通过（实际 3.11 运行证据） |
| PC-02 正式证据环境 | **NOT OBTAINED**（本会话为 Linux / Python 3.11；这是 Candidate Status = BLOCKED — ENVIRONMENT 的唯一原因） |
| PC-03 依赖 | httpx 0.27.2、pytest 9.1.1；`pyproject.toml` 零差异；未新增依赖 |
| PC-04 既有架构守卫 | `tests/contract` 在 Frozen Base 有 10 个测试模块（合同文字写 11 个，见 OBS-02）；全部未修改（`git diff --name-only fc59e202...HEAD -- fc2-organizer/tests/contract` 为空）；Linux 上 3 个 `C:\` 写法的既有测试失败（F0，与基线相同） |
| PC-05 Windows 路径语义 | S-09 / S-12 / S-21 的 POSIX 方向在本环境执行并通过；**Windows 原生组（有根无盘符、junction、NTFS case 变体阻断）NOT RUN —— 正式环境执行** |
| PC-06 文件系统语义 | S-12 / S-13：同卷（POSIX link + unlink）、接缝强制跨卷、0 字节、1 MiB + 1 流式；**NTFS 同卷原子 rename 方向 NOT RUN（正式环境）** |
| PC-07 平台证据缺口 | 既有相关测试在本环境的实际状态见第 6 项（Windows 原生 skip、POSIX 执行）；XD-B01..XD-B07 不在 P4-C10 关闭 |
| PC-08 可选原生跨卷证据 | NOT RUN（无 Owner 授权；XD-B04 accepted evidence gap，非阻塞）；未扫描任何第二块盘、未选择任何现存目录 |
| PC-09 补充证据 | **EXECUTED（本环境）**：Python 3.11.15 + POSIX：G-T 140 passed / 2 platform-gated skips；G-FULL / G-P4 的失败集合与基线逐 nodeid 相同（无新增）。对 XD-B02 / XD-B08 提供了第一份实际运行证据，但不能关闭它们 |

## 12. Exit Debt Ledger 最终状态（合同第 10 节；A = 8 / B = 17 / C = 15）

```text
A 类（8）：XD-A01 G-500                         : 证据已产出（第 9 项），随 EC-14 一并 CLOSED（若 Level 1 PASS）
          XD-A02 diagnostics 跨包覆盖            : 证据已产出（S-18、L-14、G-500 诊断模型）
          XD-A03 真实引擎 + 真实图片 transport    : 证据已产出（L-04 / L-05 / L-09；S-01..S-07、S-20、G-500）
          XD-A04 Phase 4 级正式回归证据          : **部分**——G-T / G-P4 / G-FULL 的正式环境运行未取得（BLOCKED — ENVIRONMENT）
          XD-A05 40 个基线 skip 逐项对账          : **部分**——机制与 nodeid 对账已在本环境演示；正式环境 SKIP_BASE 须重新测量
          XD-A06 Package Authority Matrix 机器核对 : 证据已产出（第 1 项）
          XD-A07 v1.0 关键验收的 Phase 4 层面     : 证据已产出（G-500、S-13 / S-14 / S-17、S-12 接缝跨卷、S-14 接缝 EACCES、S-21）；真实环境部分仍为 XD-B04 / XD-B05
          XD-A08 C5-R1-L1 未决 authority 债务     : OPEN（见第 15 项）
B 类（17）XD-B01..XD-B17、C 类（15）XD-C01..XD-C13、XD-C15、XD-C16：disposition 不变；P4-C10 没有改写任何 B / C 项分类，也没有把任何历史债务擅自升级
```

## 13. 升级门 U-1..U-7 与 Production Modified

```text
U-1 修改 CLOSED package src/**        : 未触发（`git diff --name-only fc59e202...HEAD -- fc2-organizer/src` 为空；104 个 src 文件 hash-object 与 HEAD blob 一致）
U-2 可丢弃边界之外的修改性操作        : 未触发（所有修改性操作只发生在 pytest tmp_path 树内；写观察 + sandbox guard + 仓库只读摘要三重证明；仓库内文件只读：src / docs / tests/support / tests/fixtures / pyproject.toml）
U-3 新安全边界 / 公开 API 变化        : 未触发
U-4 持久化 / 跨进程 locking / durable resume : 未触发
U-5 Contract semantic amendment       : 未触发（见第 15 项对 OBS-01 的说明：未改变任何合同语义）
U-6 新增依赖 / 修改 pyproject.toml    : 未触发
U-7 其它达到 C 类定义的风险           : 未触发
Production Modified                   : NO
CLOSED package amendment record       : 无
```

## 14. Known limitations 与 evidence gaps

* 全部证据离线、合成（脚本化 `SourceAdapter`、fixture HTML + `FakeHttpClient`、`httpx.MockTransport`）；不证明线上 source 当前可用。
* **正式证据环境（Windows 11 / Python 3.12.x）证据未取得**——本文件最大的缺口；NTFS 原生语义（同卷原子 rename、junction、case 不敏感目标目录阻断、有根无盘符路径）在本环境没有被执行。
* 原生 symlink、原生跨卷、真实 ACL、长路径、UNC 不在 P4-C10 关闭（XD-B01..XD-B07）。
* mutation 是跨包边界上的定向 mutant，不是穷举式；确定性只对冻结 fixture 证明；G-500 文件很小。
* 第 15 项列出的三项观察（OBS-01..OBS-03）与一项环境注意事项（OBS-04）。
* 本施工环境的特殊点：容器初始是浅克隆（已 unshallow）；容器预装 httpx 0.28.1（已替换为 0.27.2）；会话是 root，证据运行以普通用户 ubuntu 执行。

## 15. 失败路径记录（必须逐项；无则写 NONE）

```text
XD-A08 状态                       : OPEN —— C5-R1-L1 的原始 definition / severity / deadline / scope 不在仓库内；P4-C10 没有猜测其内容、没有产生与其内容相关的测试、没有关闭它、没有修改任何历史 docs。
                                    阻塞 Phase 4 Exit / Closure（EC-10）；不阻塞 Technical Acceptance。
F2 findings                       : NONE（没有发现任何 CLOSED package 生产行为偏离其 Frozen Contract）
F2 之后收集的安全证据             : NONE（无 F2）
被 F2 阻塞的测试 / 场景           : NONE
Production repair                 : NONE（NOT PERFORMED）
三层状态字段                      : 见第 0 节
F3 / F4 / 真正的 U 门 STOP 记录   : NONE（见下方 OBS-01 的说明：候选 F4 观察，开发者未停止，原因如下）
```

**F1 —— C10 自己的测试缺陷（施工中发现并在 `tests/phase4_acceptance/**` 内修复；被测代码均符合 Frozen Contract）**

| # | root cause | 受影响测试 | 修复 | 重跑 |
|---|---|---|---|---|
| F1-1 | 我的 `expected_library` 假定没有 extrafanart 图片时不存在 `extrafanart/` 目录；P4-C7 合同第 14 节 U7 明确规定“即使没有 extrafanart 图片也创建该目录” | S-02 及所有 extrafanart = 0 的场景（G-500 GA 的 0 张组） | `expected_library` 总是包含 `<number>/extrafanart` 目录 | S2 全部通过 |
| F1-2 | S-20 的期望标题常量使用了 HTML 里的 U+3000，而 Phase 2 文本清理器（`clean_text`，空白折叠）输出 ASCII 空格 | S-20 | 常量改为折叠后的 ASCII 空格形式（保持“作者读 fixture 写常量”的做法并按冻结的空白规则书写） | 通过 |
| F1-3 | `snapshot_tree` 的键在 Windows 上带反斜杠，而测试用 `/` 书写相对路径 | S-11 / S-21 / S-13 / G-500 / M-02 在 Windows 上会 KeyError（本环境上看不出来） | 快照键统一为 `/` 分隔 | 本环境全部通过（Windows 未执行） |
| F1-4 | `gate_diagnostics_structure` 要求 `index == 0..n-1`，对只覆盖 scope 的 retry 轮诊断不成立 | S-17 / S-18 的 retry 轮诊断 | 增加 `indices=` 参数（按该模型自己的 index 列表比较） | 通过 |
| F1-5 | M-05 的初版在 `ItemExecution` 构造期就被生产校验（`FRESH_REEXECUTE material carries no checkpoint`）以 `OrchestrationContractError` 杀死，没有经过验收门 | M-05 | mutant 改为在结果产生之后激活（模型消费者与共享门读取到的就是对调后的 retry kind） | 通过（门 SI-12 杀死） |
| F1-6 | M-02 的初版把用户文件放在 U1 之后、“最终路径不存在”检查之前，被执行器自身的早退检查拦下，原语从未被执行 | M-02 | 用户文件改为在该检查通过之后出现（并发创建者） | 通过（门 SI-02 杀死） |

**观察（不是 finding；列出供 Level 1 Reviewer 裁决）**

* **OBS-01（候选 F4 观察，请 Level 1 裁定）——S-09 矩阵的 Diag 列与 P4-C9 §9 的相对路径校验。** 合同第 7.2 节 S-09 行的 Diag 列写“issue 呈现”。当 orchestrator 的 `library_root` 是**相对路径**时，
  P4-C8 按其冻结的“library_root 晚校验”（P4-C8 §37，XD-C05）把每个条目判为 `UNPREPARED / PLANNING_REJECTED`（本测试证明：零修改、没有任何目录被创建），但 P4-C9 §9 的本地校验要求
  `library_root` 为 `os.path.isabs` 的绝对路径，因此对这样的 preview / result 构建诊断会 fail closed，抛出 `DiagnosticsIntegrityError`（类型化、有意为之）。所以对**相对路径组**，
  “诊断呈现 issue”不可能；issue 由模型本身（`item.issue`）呈现，诊断层以类型化错误拒绝。Windows 有根无盘符 `\lib` 组 `os.path.isabs` 为真，诊断可以构建（该组仅 Windows，本环境未执行）。
  S-09 的 Blocking assertion（“无任何目录被创建”）已满足，且没有改变任何合同语义，因此开发者**没有**把它当作 F3 / F4 而 STOP；但这是 C10 合同的一个单元格与两个 CLOSED 合同的交互后无法满足的事实，
  留给 Level 1 Reviewer 决定：接受为 S-09 的精确表述（本测试的做法）、或判为 F4（合同冲突，须走 authority 路径）。测试对两种判读都保留了证据。
* **OBS-02——PC-04 文字与仓库事实。** 合同第 9 节 PC-04 写“`tests/contract/` 下 11 个文件”；Frozen Base 上该目录有 10 个测试模块（`ls tests/contract | wc -l` = 10）。该目录零修改；仅文字观察，非阻塞。
* **OBS-03——既有测试在 POSIX 上的顺序相关崩溃。** 见第 5.3 项：`tests/unit/orchestration/test_orchestration_recognition.py::test_source_key_is_exact_on_posix` 在 G-P4 的收集顺序下失败，其 `no_io` 陷阱使 pytest 报告机制自身崩溃（INTERNALERROR），
  该测试单独运行通过。这是既有测试（P4-C8）的 sys.modules / 函数内 import 与陷阱的相互作用，属于 P4-C5 / P4-C6 / P4-C9 HANDOFF 已记录的“既有架构守卫清理 sys.modules”测试顺序缺陷家族；
  该测试随 P4-C9 的 Windows 正式验收通过。C10 自己的测试在任意顺序下稳定（合同第 12.7 节）。
* **OBS-04——环境注意事项（不是缺陷）。** P4-C7 S5-A2 的“同进程同源占用”以源身份 `(device, inode)` 为键且在进程内持久到 checkpoint 被消费；在**同一进程内反复创建并删除临时树**的临时脚本里，
  被删除文件的 inode 复用可能使后一个无关文件被 fail closed 拒绝（SOURCE_CHANGED）。开发者在做临时压力脚本时用 `TemporaryDirectory`（会删除树）观察到一次这样的偶发失败，保留树之后 12 × 16 次运行 0 失败。
  pytest 的 `tmp_path` 在一个会话内保留所有树，因此 G-T / G-FULL 不受影响（G-T 连续三次相同）。这是冻结的进程内语义（fail closed、无安全影响），仅作记录；Phase 4 之后若要把该占用表跨很长的进程生命周期使用，应在后续阶段评估。

## 16. Known limitations（P4-C10 自身，合同第 19 节）与未做的事

不修改任何 production / 既有测试 / 历史文档；不新增依赖；不开始 Phase 5；不建立 Final Reviewed Acceptance Head；不自我宣布 PASS；不关闭 XD-A08；不创建 status-only review commit。

---

# Part II —— Phase 4 Final HANDOFF（Phase 4 = CLOSED 与 final closure coordinates 只在 Final Closure Docs 中写入；此处不写）

1. **Phase 4 Package Authority Matrix**：合同第 4.1 节的九行不变；补入 P4-C10 行：

   | Package | Capability | Frozen Base | Final Reviewed Code / Package Head | Final Closure Docs Head | Frozen Contract | Construction Plan | HANDOFF |
   |---|---|---|---|---|---|---|---|
   | P4-C10 | Phase 4 最终验收（`tests/phase4_acceptance/**`，无生产代码） | `c293ed75e6ab3160d57ab8bf1248d1ce16ec241c` | NOT ESTABLISHED（C10 Acceptance Head 为本提交；Final Reviewed Acceptance Head NOT ESTABLISHED） | NOT ESTABLISHED | `PHASE4_FINAL_ACCEPTANCE_CONTRACT.md` @ `fc59e202…` | `P4_C10_CONSTRUCTION_PLAN.md` @ `fc59e202…` | 本文件 |

2. **P4-C1..P4-C10 final heads**：P4-C1..P4-C9 按合同第 4.1 节（`src` 自各 Final Reviewed Code Head 起零漂移，第 1 项已核对）；P4-C10 的 Final Reviewed Acceptance Head / Final Closure Docs Head 尚未建立。
3. **Phase 4 能力总览**：合同第 5.1 节链路（discover_media → 真实 MultiSourceEngine → planning / publication / NFO → 真实 HttpxImageClient → mapping → P4-C7 执行 → retry / merge → diagnostics），其真实跨包证据见第 7、9 项。
4. **safety invariants / platform / 全量测试 / skip 基线 / mutation 摘要**：第 8、11、5、6、10 项。
5. **Exit Debt Ledger**：第 12 项；XD-A08 = OPEN（authority 来源与 disposition 尚未取得）。
6. **Phase 5 input boundary**：合同第 18 节不变；在 XD-A08 CLOSED、全部 Exit gate 满足且 EC-15 PASS 之前 Phase 5 不能从“已验收的 Phase 4 Frozen Base”开始。F3 / F5（XD-B11）仍是 Phase 5 入口阻塞项。

---

## 17. 施工过程命令记录（节选）

```text
python -m pytest tests/phase4_acceptance -q -p no:cacheprovider --basetemp=<JOB_TMP>/c10-gt-N --junitxml=…   ×3 -> 140 passed, 2 skipped（各 ≈24 s）
python -m pytest -q -p no:cacheprovider -rs --continue-on-collection-errors …（G-FULL，含 C10）            -> 7335 passed, 339 failed, 96 skipped, 26 errors（164.91 s）
G-P4 逐目录补充运行                                                                                          -> 4777 passed, 338 failed, 26 errors, 94 skipped（对补充基线无新增）
git ls-files -- fc2-organizer/src | git hash-object --no-filters vs HEAD:path                                -> 104 / 104 一致
```

## 18. S3 交接点（STOP）—— HISTORICAL / COMPLETED / NOT CURRENT

S3 完成。C10 Acceptance Head = 本提交。开发者不再修改本提交，不创建 Review 后状态提交。下一步**唯一**是 `P4-C10 INDEPENDENT LEVEL 1 FINAL ACCEPTANCE REVIEW`
（Review Range = `fc59e2020e4df237bf3bed83a07950d67c19b475..<C10 Acceptance Head>`）。Reviewer 需要：

1. 在正式证据环境（Windows 11 / Python 3.12.x、普通用户）独立重跑 G-T（必须 0 skipped，S-09 / S-21 的 Windows 原生组必须执行并通过）、G-P4、G-FULL，并在 Design Accepted Head（加入 C10 tests 之前）重新测量 `SKIP_BASE`；
2. 抽查 mutation 与 G-500；
3. 裁定第 15 项的 OBS-01；
4. 核对本文件的 Candidate Status / Verdict 字段符合合同第 16.1a 节（本文件没有写 PASS）。

```text
（HISTORICAL S3 快照 —— NOT CURRENT；当前状态见第 19 节）
Historical S3 Candidate Status               : BLOCKED — ENVIRONMENT
P4-C10 Technical Acceptance Verdict（S3 时） : NOT ESTABLISHED
Final Reviewed Acceptance Head（S3 时）      : NOT ESTABLISHED
XD-A08                                       : OPEN
Phase 4 Exit Authorization（S3 时）          : BLOCKED
Phase 4                                      : NOT CLOSED
Phase 5                                      : NOT STARTED
```

该 S3 交接点已经完成：原 Level 1 Review 返回 BLOCKED，之后经 AUTH-A1..AUTH-A4 / C10-R1 / 授权 test-isolation repair 与正式证据重取，形成第 19 节的 Post-Repair Evidence Refresh Candidate。

---

# Part III —— Post-Repair Evidence Refresh（HISTORICAL candidate snapshot @ a87b9352… —— 已经 Level 1 Closure Review PASS；当前状态见 Part IV 第 20 节）

（下文第 19 节原样保留为 Evidence Refresh Candidate 时点的快照；其中 `Technical Acceptance Verdict : NOT ESTABLISHED`、`Final Reviewed Acceptance Head : NOT ESTABLISHED`、
`XD-A08 : OPEN` 与 “Next” 只描述该时点，不追溯改写，合同第 16.1b 节。）

## 19. Post-Repair Evidence Refresh Candidate（当前候选证据；不是 reviewed verdict）

本节是 Evidence Refresh 作者对已完成证据的同步记录（docs-only）。本提交不修改任何测试或 `src`、不重新运行 pytest、不重新执行 repair、不修改合同第 22 节 / 计划第 18 节的 reviewed authority 语义。

### 19.1 坐标

```text
Historical Design Accepted Head        : fc59e2020e4df237bf3bed83a07950d67c19b475
Historical original C10 Acceptance Head: 1012968e3068731025d2512612fa8f85e829d3d0
C10-R1                                 : e0ee8c15d9d8d238ee76e3f142870a96d5972a60
AUTH-A4 Candidate                      : 299a821b45b6e39a9cfcc60b4537487d697715ae
Active Authority Amendment Head        : 7d1a48f6e9b9ce1ac3234487b1126b58b879bc8b（AUTH-A4-R1 reviewed head）
Authorized Repair Head                 : a0d491d413a96ce9f08937dd5074adcd2144439d（parent 7d1a48f6…）
Evidence Refresh Candidate             : 本提交（parent a0d491d413a96ce9f08937dd5074adcd2144439d；exact SHA 由 git 在提交后确定）
Final Reviewed Acceptance Head         : NOT ESTABLISHED
```

### 19.2 Authority

```text
P4-C10-AUTH-A4-R1 Incremental Independent Authority Closure Review : COMPLETED — PASS
P4-C10-AUTH-A4-R-01                    : CLOSED
P4-C10-AUTH-GP4-01                     : CLOSED
Active Authority Amendment Head        : 7d1a48f6e9b9ce1ac3234487b1126b58b879bc8b
New Authority Finding                  : NONE
```

### 19.3 Authorized Repair（合同第 22.7 节 / 计划第 18.4 节唯一 scope）

```text
Repair commit          : a0d491d413a96ce9f08937dd5074adcd2144439d   test(orchestration): isolate POSIX source-key test
唯一修改               : M fc2-organizer/tests/unit/orchestration/test_orchestration_recognition.py
唯一 target            : test_source_key_is_exact_on_posix
性质                   : TEST-ISOLATION REPAIR ONLY —— 删除 no_io 生效后的函数内 re-import；改为通过已加载的 recognize.__globals__["os"] patch os.name = "posix"
Production Modified    : NO
tests/contract Modified: NO
Assertion Semantics Changed : NO
Expected Result Changed     : NO
no_io Fixture Changed       : NO
Filesystem Trap Strength Changed : NO
```

### 19.4 Focused evidence（E-1..E-3）

```text
E-1 Focused target                       : PASS —— 1 passed
E-2 Same-process causal-order witness    : PASS —— 2 passed / 0 failed / 0 errors
    顺序：tests/contract/test_planning_architecture.py::test_planning_imports_cleanly_with_amane_blocked_at_runtime
          -> tests/unit/orchestration/test_orchestration_recognition.py::test_source_key_is_exact_on_posix
E-3 tests/unit/orchestration 全目录      : PASS —— 919 passed / 0 failed / 0 errors
```

### 19.5 正式证据环境（合同第 12.1 节）

```text
Evidence Root   : C:\Users\Ctg\AppData\Local\Temp\p4-c10-post-repair-formal-9d1f4042f8a946c6ad73656a829ce7e2
                  （evidence binary / log 不入库）
Windows         : Windows 11 Home，NT 10.0.26200
Python          : 3.12.10
httpx           : 0.27.2
pytest          : 9.1.1
Privilege       : 普通用户（non-admin）
Filesystem      : C: NTFS
SUT             : 当前 p4-c10 worktree 的 fc2-organizer/src（HEAD a0d491d4…）
命令            : 合同第 8.2 节 / 计划第 7 节的 frozen exact command（G-T / G-P4 / G-FULL），未改变目录顺序、未拆分进程、未加 skip / xfail / deselect / -k
```

### 19.6 Formal evidence（E-4..E-8）

```text
E-4 Formal G-T      : PASS —— collected 142 / passed 142 / failed 0 / errors 0 / skipped 0
                      S-09A PASS；S-09B PASS（os.path.isabs(r"\lib") = True）；S-12 same-volume-native PASS；S-21 PASS
                      C:\lib Before = ABSENT；C:\lib After = ABSENT
E-5 Formal G-P4     : PASS —— collected 5388 / passed 5348 / skipped 40 / failed 0 / errors 0
                      原 INTERNALERROR：NOT REPRODUCED；原 G-P4 constructibility blocker：CLOSED；Formal Constructibility：RESTORED
                      G-P4 skip exact nodeid 集合 = SKIP_BASE
E-6 PC-04           : PASS —— Design Accepted Head 上 tests/contract 测试模块 = 10；
                      git diff fc59e2020e4df237bf3bed83a07950d67c19b475..a0d491d413a96ce9f08937dd5074adcd2144439d -- fc2-organizer/tests/contract = EMPTY；Formal G-P4 PASS
E-7 Formal G-FULL   : PASS —— collected 7949 / passed 7909 / skipped 40 / failed 0 / errors 0
                      Frozen arithmetic：7767 + 142 = 7909 passed；7909 + 40 = 7949 collected；k = 0 —— PASS
E-8 Exact skip reconciliation : PASS
                      SKIP_BASE = 40 exact nodeids；SKIP_CURRENT = 40 exact nodeids
                      SKIP_BASE − SKIP_CURRENT = EMPTY；SKIP_CURRENT − SKIP_BASE = EMPTY
                      skip reasons 逐行相同；New unexplained skips = NONE
```

Trusted Historical Baseline（本轮未重建）：

```text
7807 collected / 7767 passed / 40 skipped / 0 failed / 0 errors
SKIP_BASE 来源 : C:\Users\Ctg\AppData\Local\Temp\p4-c10-formal-30e11fdc4604444cab2916cc939cb1de\skip-base.txt（40 exact nodeids）
```

### 19.7 平台证据缺口与 finding

```text
FC2_EXECUTION_CROSS_VOLUME_ROOT : unset
PC-08                           : NOT RUN
XD-B04                          : OPEN ACCEPTED EVIDENCE GAP —— NON-BLOCKING
Open F1                         : NONE
F2                              : NONE
F3                              : NONE
F4                              : NONE
New Authority Finding           : NONE
P4-C10-AUTH-GP4-01              : CLOSED
```

### 19.8 当前三层状态字段（CURRENT）

```text
P4-C10 Technical Acceptance Candidate Status : READY FOR LEVEL 1 REVIEW（READY != PASS）
P4-C10 Technical Acceptance Verdict          : NOT ESTABLISHED
Final Reviewed Acceptance Head               : NOT ESTABLISHED
XD-A08（C5-R1-L1）                           : OPEN —— Blocks Technical Acceptance：NO；Blocks Phase 4 Exit：YES
Phase 4 Exit Authorization                   : BLOCKED — LEVEL 1 / EC-15 PENDING；XD-A08
Production Modified                          : NO
P4-C10                                       : NOT CLOSED
Phase 4                                      : NOT CLOSED
Phase 5                                      : NOT STARTED
```

判定依据（合同第 16.1a 节）：E-1..E-8 全部 PASS；Formal G-T / G-P4 / PC-04 / G-FULL / Exact Skip Reconciliation 全部 PASS；Open F1 / F2 / F3 / F4 = NONE；
XD-A08 只阻塞 Phase 4 Exit、不阻塞 Technical Acceptance。因此全部已知 technical gate 在 candidate evidence 中满足，Candidate Status = `READY FOR LEVEL 1 REVIEW`。
原 S3 的 `BLOCKED — ENVIRONMENT` 已成为历史（第 0、18 节）。

### 19.9 交接点（STOP）

Evidence Refresh 作者在本提交 push 之后 STOP。当前唯一下一步：

```text
P4-C10 POST-REPAIR EVIDENCE REFRESH INCREMENTAL INDEPENDENT LEVEL 1 CLOSURE REVIEW
```

只有该 Reviewer 能建立 `Technical Acceptance Verdict`（PASS / FAIL / BLOCKED）；PASS 时由 Reviewer 建立 Final Reviewed Acceptance Head（EC-14）。
之后 Phase 4 Exit 仍需 EC-15 与 XD-A08 disposition（合同第 16 节）。

（第 19.9 节交接点已完成：该 Level 1 Closure Review 已返回 PASS，见第 20 节。）

---

# Part IV —— Phase 4 Final Closure Docs Candidate（CURRENT；EC-15 REVIEW REQUIRED）

## 20. P4-C10 最终闭合 / Phase 4 最终闭合 —— Final Closure Docs Candidate（计划第 13 节第 2 步；合同第 16.4、17 节）

本节由 Phase 4 Final Closure Authority Docs Author 写入（docs-only）。它（a）把已由独立 Level 1 Review 建立的 reviewed Technical Acceptance Verdict 与 Final Reviewed
Acceptance Head 记录为 closure history；（b）首次写入 XD-A08 disposition 与 Ledger 修订；（c）给出 EC-01 Final Closure 复核结果。本节**不是** reviewed closure：
XD-A08 CLOSED、EC-10 SATISFIED、EC-15 PASS、Phase 4 Exit AUTHORIZED、Phase 4 CLOSED、Phase 5 Frozen Base Candidate 只能由独立 EC-15 Docs-Only Review 建立。
本提交不修改 `src/**`、`tests/**`，不运行 pytest，不修改 production，不修改任何 Phase 3 C5 文档（C5-R1-L1 的 optional wording polish 不是 Phase 4 closure obligation），不开始 Phase 5。

### 20.1 快照声明（合同第 16.1b 节）

* 第 0..18 节是 S3 candidate evidence snapshot（C10 Acceptance Head `1012968e3068731025d2512612fa8f85e829d3d0`），第 19 节是 Post-Repair Evidence Refresh candidate snapshot
  （`a87b9352e384327ea452c31ad650206df87fc975`）。其中 `Technical Acceptance Verdict : NOT ESTABLISHED` 是各自时点的正确记录，**不被改写**。
* reviewed verdict 的 authority 是独立 Level 1 Review Report，不是本文件；本节只把该 reviewed 结论作为 closure history 记录（经 EC-15 复查）。

### 20.2 Technical Acceptance —— reviewed（closure history）

```text
Review                                       : P4-C10 POST-REPAIR EVIDENCE REFRESH INCREMENTAL INDEPENDENT LEVEL 1 CLOSURE REVIEW —— COMPLETED — PASS（据任务指令记录）
Reviewed head                                : a87b9352e384327ea452c31ad650206df87fc975
P4-C10 Technical Acceptance Verdict          : PASS
Final Reviewed Acceptance Head               : a87b9352e384327ea452c31ad650206df87fc975
EC-14                                        : SATISFIED
Active Authority Amendment Head              : 7d1a48f6e9b9ce1ac3234487b1126b58b879bc8b
Authorized Repair Head                       : a0d491d413a96ce9f08937dd5074adcd2144439d
Formal G-T                                   : PASS —— 142 / 142
Formal G-P4                                  : PASS —— 5348 passed / 40 skipped
PC-04                                        : PASS
Formal G-FULL                                : PASS —— 7909 passed / 40 skipped
Exact Skip Reconciliation                    : PASS —— 40 exact nodeids
Open F1 / F2 / F3 / F4                       : NONE / NONE / NONE / NONE
Production Modified                          : NO
XD-A01 .. XD-A07                             : CLOSED（技术性 A 类项，随 EC-14 一并 CLOSED，合同第 10.1 / 16.2 节）
本轮重跑                                     : NONE（historical technical evidence 沿用；不重跑）
```

Review 历史（摘要；详见合同第 20 节）：Design Review FAIL -> DESIGN-R1 / R2 / R3 -> Design Accepted `fc59e202…` -> S1..S3（`1012968e…`）-> 原 Level 1 Review BLOCKED ->
AUTH-A1（FAIL）/ AUTH-A2（FAIL）/ AUTH-A3（PASS）-> C10-R1 `e0ee8c15…` -> AUTH-A4（BLOCKED，review 环境）/ AUTH-A4-R1（PASS，`7d1a48f6…`）-> Authorized Repair `a0d491d4…`
-> Evidence Refresh `a87b9352…` -> Incremental Level 1 Closure Review PASS。

### 20.3 C5-R1-L1 recovered authority 与 XD-A08 disposition（合同第 10.1 节 Required closure；第 17 节 Part I 第 15 项）

完整 disposition 记录（含原文精确引用）在合同第 10.1 节 “XD-A08 Disposition Record”。本节按合同第 17 节要求附 authority 字段：

```text
Exact source                 : C:\Users\Ctg\.claude\projects\C--Users-Ctg-Projects-ffcc\b7881a4d-fbb8-48ae-bdd2-a5d4bfb343c0.jsonl（不入库）
Source SHA-256               : 59e365e07fc48d3f162744151422601fc210311a29204e27b2dea9030a4f2dcf
Source size                  : 453584 bytes
Session ID                   : b7881a4d-fbb8-48ae-bdd2-a5d4bfb343c0
Original Review              : Phase 3 C5-R1 — Docs-Only Independent Closure Review
Review timestamp             : 2026-09-22T10:47:13.245Z
Repo lineage / branch        : fankunet-arch/ffcc / claude/phase3-c5-resource-control
C5 Code Head                 : fb4dddaf4ef00ed201c94d9a7e29d1e86a20f17d
C5-R1 Base                   : caf1655336b96a02a64cfdd515932c594d86da0a
Reviewed Head                : 3edab6eb4ab363c1fedabd847c61b7061be8343d
Original Review Verdict      : PASS WITH NON-BLOCKING NOTES；C5-R-01 CLOSED；Phase 3 C5 may be CLOSED
Definition                   : "Breaker coupling" not explicitly disclaimed alongside permit-leak/budget-coupling disclaimers
                               （Phase 3 资源控制合同 §5 与 C5-R1 HANDOFF §2 解释 HoL 延迟时排除了 host-permit leak 与 cross-host budget coupling，
                                 但未在同处显式排除 breaker coupling；breaker 独立性已在 HANDOFF 其它位置写明；无 overclaim / 矛盾 / 行为缺陷）
Severity                     : LOW
Blocking                     : NO
Scope                        : documentation completeness
Original status              : OPEN informational；non-blocking
Closure requirement          : OPTIONAL WORDING POLISH ONLY（"None required for C5-R-01; optional wording polish for a future docs pass."）
Deadline                     : NONE / NOT PRESENT
Phase assignment             : NONE / NOT PRESENT
Phase 4 obligation           : NONE（无 production / test / safety obligation；无 contract behavior correction；无额外 acceptance evidence requirement）
Original source supports Phase 4 blocking : NO
Impact on Technical Acceptance PASS       : NONE（不重开）

Verification authority       : Independent Authority Recovery Review —— C5-R1-L1 Original Authority : RECOVERED AND INDEPENDENTLY VERIFIED；
                               Authority Sufficiency : SUFFICIENT；Phase 4 Obligation : NONE；Original Source Supports Phase 4 Blocking : NO；
                               Impact on Technical Acceptance PASS : NONE（据任务指令记录；它是验证 authority，不是原始来源）
Author 只读复核              : sha256 / size 与上方一致；文件中 "C5-R1-L1" 恰出现 1 次（第 127 行，0 起计，type = assistant，timestamp 如上）；
                               原文字段与合同第 10.1 节引用一致；3edab6eb… 是本分支 HEAD 的祖先
```

**Disposition（candidate）**：

```text
XD-A08 unresolved-authority condition : REMEDIATED（authority 已取得并经独立验证）
XD-A08                       : REMEDIATED — EC-15 INDEPENDENT FINAL CLOSURE REVIEW REQUIRED
                               （EC-15 PASS 之前按合同第 10.1 节仍计为 OPEN；行保留在 A 类表中作为 unresolved-authority wrapper，不是 C5-R1-L1 的实质分类）
承接条目                     : XD-C17 —— C5-R1-L1 — breaker-coupling disclaimer wording completeness（新 ID）
承接分类                     : C 类 OUT OF PHASE 4 SCOPE（Phase 4 之前阶段的债务；non-blocking）
不选 B 类的理由              : B 类含“目标阶段的规划性指派”；来源中无 target phase / deadline / 强制后续工作，不得发明
XD-C14                       : RETIRED / NOT REUSED
其它 Ledger 项分类           : 未修改
fail-closed 检查（合同第 16.4 节）: C5-R1-L1 不要求 Phase 4 内 production repair、safety work、contract change 或额外 acceptance evidence -> fail-closed 条件不成立；
                               不需要 F2 / F3 / F4 / F5 / authority amendment 路径
```

### 20.4 Exit Debt Ledger（candidate；合同第 10 节）

```text
Ledger Counts Before（冻结，Design-R1） : A = 8 / B = 17 / C = 15
Ledger Counts Candidate                : A = 8 / B = 17 / C = 16
A 类（8）  XD-A01 .. XD-A07 : CLOSED（随 EC-14）
           XD-A08           : REMEDIATED — EC-15 INDEPENDENT FINAL CLOSURE REVIEW REQUIRED（实质 disposition 由 XD-C17 承接）
B 类（17） XD-B01 .. XD-B17 : disposition 不变（均 NON-BLOCKING for Phase 4；XD-B04 OPEN ACCEPTED EVIDENCE GAP；XD-B11 F3 / F5 仍为 Phase 5 入口阻塞项）
C 类（16） XD-C01 .. XD-C13、XD-C15、XD-C16 : disposition 不变
           XD-C17           : 新增候选（C5-R1-L1；NON-BLOCKING；EC-15 REVIEW REQUIRED）
XD-C14                     : RETIRED / NOT REUSED
未处置的阻塞性 evidence gap : NONE
```

第 12 项（S3 快照）中的 “A = 8 / B = 17 / C = 15” 与 “XD-A08 : OPEN” 是 S3 时点记录，不追溯改写；当前计数以本节与合同第 10 节为准。

### 20.5 EC-01 Final Closure Recheck（合同第 16.3 节；只读机器复核，@ a87b9352…，本 docs 提交之前）

```text
Context                       : branch claude/phase4-c10-final-acceptance；HEAD = origin = ls-remote = a87b9352e384327ea452c31ad650206df87fc975；worktree CLEAN；untracked NONE
P4-C1 .. P4-C9 状态行         : 九个 HANDOFF 均为 CLOSED（P4_C1_HANDOFF.md:921、P4_C2:931、P4_C3:420、P4_C4:425、P4_C5:584、P4_C6:354、P4_C7:402、P4_C8:391、P4_C9:310）
合同第 4.1 节坐标祖先关系     : 19 个 package 坐标（各 Frozen Base / Final Reviewed Code Head / Final Closure Docs Head，含 DOCS-CN a0a69c71…）+ c293ed75…、3b9d39e9…、fc59e202…、
                                1012968e…、e0ee8c15…、7d1a48f6…、a0d491d4… 全部 `git merge-base --is-ancestor <sha> HEAD` 为真（26 / 26）
origin/claude/phase4-c9-diagnostics : c293ed75e6ab3160d57ab8bf1248d1ce16ec241c
src 漂移（各 Final Reviewed Code Head..HEAD）:
                                discovery 0 / planning 0 / publication 0 / nfo 0 / images 0 / materialization 0 / execution 0 / orchestration 0 / diagnostics 0；
                                src/fc2_metadata_core（自 1e66ab40…）0；src/**（自 Frozen Base c293ed75…）0
治理 / CLAUDE.md / pyproject.toml（自 3b9d39e9…）: 0 差异
c293ed75..HEAD 线性           : 16 commits，0 merge commits
c293ed75..HEAD 既有测试改动   : 仅 tests/unit/orchestration/test_orchestration_recognition.py（AUTH-A4 授权 repair @ a0d491d4…；合同第 22.7 节）；tests/contract / support / fixtures 0
EC-01 Final Closure Recheck   : PASS
```

### 20.6 Phase 4 Exit Criteria（candidate 状态）

```text
EC-14  : SATISFIED（reviewed；第 20.2 节）
EC-01  : PASS（Final Closure 复核，第 20.5 节；由 EC-15 确认）
EC-10  : REMEDIATED — EC-15 REVIEW REQUIRED
         （XD-A01..XD-A07 CLOSED via EC-14；XD-A08 authority 已取得并提出 Ledger disposition；B / C 全部有 disposition；无未处置阻塞性 evidence gap；
           SATISFIED 只由 EC-15 Reviewer 建立）
EC-15  : PENDING —— INDEPENDENT DOCS-ONLY REVIEW REQUIRED
Phase 4 Exit Authorization : BLOCKED — EC-15 REVIEW PENDING
```

### 20.7 Phase 4 Final HANDOFF（合同第 17 节 Part II；candidate）

1. **Phase 4 Package Authority Matrix**：合同第 4.1 节九行不变（第 20.5 节已复核）；P4-C10 行：

   | Package | Capability | Frozen Base | Final Reviewed Code / Package Head | Final Closure Docs Head | Frozen Contract | Construction Plan | HANDOFF |
   |---|---|---|---|---|---|---|---|
   | P4-C10 | Phase 4 最终验收（`tests/phase4_acceptance/**`，无生产代码） | `c293ed75e6ab3160d57ab8bf1248d1ce16ec241c` | Final Reviewed Acceptance Head `a87b9352e384327ea452c31ad650206df87fc975` | 本提交 = CANDIDATE（EC-15 PASS 后才成为 Phase 4 Final Closure Docs Head） | `PHASE4_FINAL_ACCEPTANCE_CONTRACT.md` @ `fc59e202…`（+ AUTH-A1 / AUTH-A4 / AUTH-A4-R1） | `P4_C10_CONSTRUCTION_PLAN.md` @ `fc59e202…`（同上） | 本文件 |

2. **P4-C1..P4-C10 final heads**：P4-C1..P4-C9 按合同第 4.1 节；P4-C10 Final Reviewed Acceptance Head = `a87b9352…`；Final Closure Docs Head = 本提交（candidate）。
3. **Phase 4 能力总览**：合同第 5.1 节链路；真实跨包证据见第 7、9 项与第 19 节正式证据。
4. **safety / platform / 全量测试 / skip 基线 / mutation**：第 8、11、5、6、10 项与第 19 节（正式环境 reviewed 证据）。
5. **Exit Debt Ledger**：第 20.4 节；XD-A08 disposition 与 authority 来源见第 20.3 节与合同第 10.1 节。
6. **Phase 5 input boundary**：合同第 18 节不变。XD-B11（F3 / F5）仍是 Phase 5 入口阻塞项（定义不在本仓库）；XD-B16 适用条件不变；第 18.4 节所列能力 Phase 5 不得假定存在。
7. **final closure coordinates（candidate）**：

   ```text
   Final Reviewed Acceptance Head        : a87b9352e384327ea452c31ad650206df87fc975（ESTABLISHED；reviewed）
   Technical Acceptance Verdict          : PASS（reviewed；closure history）
   Phase 4 Final Closure Docs Candidate  : 本提交（parent a87b9352…；exact SHA 由 git 在提交后确定）
   Phase 4 Final Closure Docs Head       : NOT ESTABLISHED（EC-15 PASS 后 = 本提交）
   Phase 5 Frozen Base Candidate         : NOT ESTABLISHED（EC-15 PASS 后 = Phase 4 Final Closure Docs Head）
   ```

**只在 EC-15 PASS 之后才生效的 closure 效果（条件性；当前均未生效；由 EC-15 Reviewer 建立）**：XD-A08 -> CLOSED；XD-C17 -> 确认；EC-10 -> SATISFIED；EC-15 -> PASS；
Phase 4 Exit Authorization -> AUTHORIZED；P4-C10 -> CLOSED；Phase 4 -> CLOSED；本提交 -> Phase 4 Final Closure Docs Head 与 Phase 5 Frozen Base Candidate。
计划第 13 节第 2 步所列的 `P4-C10 : CLOSED` / `Phase 4 : CLOSED — EFFECTIVE UPON PHASE 4 FINAL CLOSURE DOCS-ONLY REVIEW PASS` 在本 Candidate 中**没有**作为字段值写入，
因为合同第 16.6 节禁止在 EC-15 满足之前、且 XD-A08 仍计为 OPEN 时写入任何 `Phase 4 = CLOSED`；改以本段条件性效果表述，供 EC-15 审查。

### 20.8 EC-15 Reviewer 重点（合同第 16.4 节；不得只审格式 / 状态）

1. authority source：exact source、SHA-256、size、session、timestamp、reviewed head 与原文引用是否与原始 JSONL 一致；该来源（仓库外会话记录，经 SHA-256 绑定并在合同中原文引用）是否满足第 10.1 节 Required closure 第 1 项与第 10 节“可审计”要求。
2. disposition legitimacy：LOW / non-blocking / documentation completeness / 无 deadline / 无阶段指派 / 无 Phase 4 obligation 是否全部由来源支持；fail-closed 条件是否确实不成立。
3. Ledger change：XD-C17 的 C 类归属（而非 B 类）、新 ID、XD-C14 不重用、计数 A = 8 / B = 17 / C = 16 与全文 current summary 一致、其它项分类未变；XD-A08 wrapper 与合同第 18.3 节的一致性。
4. Phase 4 Exit Criteria：EC-01 复核（第 20.5 节）、EC-10、对 EC-14 的承接。
5. scope：本提交只修改合同第 10 节 / 第 20 节、计划第 15 节、本文件（追加 Part IV 与当前状态头）；`src/**`、`tests/**` 零修改。

### 20.9 交接点（STOP）

```text
P4-C10 Technical Acceptance Verdict : PASS
Final Reviewed Acceptance Head      : a87b9352e384327ea452c31ad650206df87fc975
EC-14                               : SATISFIED
XD-A08                              : REMEDIATED — EC-15 REVIEW REQUIRED
EC-10                               : REMEDIATED — EC-15 REVIEW REQUIRED
EC-15                               : PENDING
Phase 4 Exit Authorization          : BLOCKED — EC-15 REVIEW PENDING
P4-C10                              : NOT CLOSED（TECHNICALLY ACCEPTED；NOT FINAL-CLOSED）
Phase 4                             : NOT CLOSED
Phase 5                             : NOT STARTED
Next                                : PHASE 4 FINAL CLOSURE DOCS INDEPENDENT EC-15 DOCS-ONLY REVIEW
```

Final Closure Authority Docs Author 在本提交 push 之后 STOP。
