# DOCS-CN 全仓 Markdown 简体中文化迁移报告

本报告记录 DOCS-CN 文档治理任务的执行结果。DOCS-CN 属于 docs-only 治理任务：只把项目 Markdown 文档中的英文说明正文翻译为简体中文，不改变任何合同语义、requirement、finding ID、severity、SHA、测试数字、状态、日期或 frozen boundary。

本报告**不**宣布 DOCS-CN CLOSED。DOCS-CN 的关闭只能由独立文档复查作出。

## 1. 基线与提交链

| 项目 | 值 |
|---|---|
| 分支 | `claude/docs-cn-migration` |
| DOCS-CN Frozen Base | `947949ab077c1e288b2d9244c625363d443ffb87` |
| Batch 1 Head（核心规格与项目指引） | `a7ebcec` — `docs(cn): translate core specifications and project guidance` |
| Batch 2 Head（复查与交接历史） | `80e3ec1` — `docs(cn): translate review and handoff history` |
| Translation Candidate（验收与来源文档） | `a94b961c1446dceb4d7c67bc7d60e6a0ae3579e0` — `docs(cn): translate acceptance and source documentation` |
| DOCS-CN Docs Head | 仅包含本报告的提交（SHA 见最终 HANDOFF 回复） |

所有提交均为新增提交；没有 rebase、amend、squash 或 force push。947949a 不再作为 P4-C7 的最终 Frozen Base；只有 DOCS-CN 经独立复查后形成的 Final Closure Head 才能成为 P4-C7 base。

## 2. 文件统计

| 统计项 | 数量 |
|---|---|
| 扫描的 Markdown 文件（`git ls-files '*.md'`，不含本报告） | **67** |
| 本次迁移修改的 Markdown 文件（Batch 1 + 2 + 3） | **55**（13 + 21 + 21） |
| 无需修改的 Markdown 文件 | **12** |
| 新增文件 | 1（本报告 `docs/DOCS_CN_MIGRATION_REPORT.md`） |
| 重命名文件 | 0 |

### 2.1 各批次修改范围

- **Batch 1（13 个）：** `docs/specifications/` 下全部 11 份英文合同（中文开发规格书除外）；`src/README.md`（标题）；`docs/prompts/ClaudeCode_00_实施总提示词.md`（三条英文政策条目）。
- **Batch 2（21 个）：** `docs/review/*.md` 全部复查 / 交接文档。
- **Batch 3（21 个）：** `docs/PHASE2_PROBE_SET.md`、`docs/SOURCE_STATUS_MATRIX.md`、`docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md`、`docs/acceptance/PHASE3_50_ID_SET.md`、`docs/acceptance/PHASE3_CANDIDATE_POOL.md`、`docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`、`docs/sources/SOURCE_VIABILITY_*.md`（15 个）。

### 2.2 无需修改的 12 个文件

| 文件 | 原因 |
|---|---|
| `CLAUDE.md` | 已是中文 |
| `README.md` | 已是中文 |
| `UPLOAD_AND_START.md` | 已是中文 |
| `docs/文档语言规范.md` | 已是中文 |
| `docs/PHASE0_AMANE_INTEGRATION_REPORT.md` | 已是中文；残留英文仅为代码标识符、版本号与治理标题 |
| `docs/prompts/ClaudeCode_10_独立复查提示词模板.md` | 已是中文 |
| `docs/prompts/ClaudeCode_20_最终验收提示词.md` | 已是中文 |
| `docs/prompts/ClaudeCode_使用顺序.md` | 已是中文 |
| `docs/specifications/FC2_Organizer_v1.0_开发规格书.md` | 已是中文 |
| `tests/README.md` | 已是中文 |
| `upstream/README.md` | 空文件 |
| `docs/acceptance/evidence/PHASE3_50_ID_GATE_PRIMARY_20260920T232140Z.md` | **有意保留英文**，见第 4.1 节 |

## 3. 翻译方法与校验

1. 每个文件翻译后，用脚本与 Frozen Base `947949a` 逐文件对比，要求：
   - fenced code block 逐字节一致；
   - inline code、SHA、finding 类 ID、URL、状态词（PASS / FAIL / FAILED / BLOCKED / CLOSED / OPEN / NOT CLOSED / NOT STARTED / ACCEPTED / REQUIRED）以及数字记号的多重集合完全一致。
   55 个修改文件全部通过；唯一的 WARN 来自 `PHASE3_AGGREGATION_CONTRACT.md` 中原文自带的奇数反引号字面量，已人工核对一致。
2. 较大的文件按段落抽取、翻译、回填，fenced code block 不经过翻译流程。
3. 每批提交前运行 `git diff --check`，并确认变更只涉及 `*.md`。
4. 英文数词未改写为阿拉伯数字；`non-200`、`still-100%-green` 等带数字的英文复合词保留原形，以免改变数字记号。

## 4. 保留的英文及原因

### 4.1 机器生成且哈希冻结的验收证据（整文件保留）

`docs/acceptance/evidence/PHASE3_50_ID_GATE_PRIMARY_20260920T232140Z.md` 由 `tools/run_50id_coverage_gate.py` 的 `render_markdown` 机器生成。`docs/review/PHASE3_C3_HANDOFF.md` 记录了它的权威 Git blob SHA-256 `f0da1d68daebb57fb7f6b49549d154c2ed02a9d6a4c9c688676a4bc6f2ad3f8b`，并声明该证据“按生成结果逐字节提交（从未编辑）”。翻译它会改变已记录的哈希、推翻“从未编辑”的历史陈述。任务规则要求不得改变任何 SHA、不得重新解释历史文档，因此该文件保持 byte-identical，未作任何修改。

### 4.2 各文件中按规则保留的英文

- fenced code block 与 inline code（命令、路径、API / function / class / enum / field 名称、异常类、error 字面量、JSON key、正则、环境变量）；
- Git / pytest / traceback 原始输出，以及 SHA、分支名、commit range；
- 治理术语与状态字面量：Contract、HANDOFF、Review、PASS、FAIL、BLOCKED、CLOSED、OPEN、Frozen Base、Code Review Candidate、Docs Head、`READY FOR ... REVIEW` 等；
- 数据表中的原始数据：
  - `SourceStatus` 取值（`SUCCESS`、`NOT_FOUND`、`success`、`not_found` 等）；
  - 50-ID 表中的 band / origin / tier 取值；
  - 页面 `<title>` 与标题节选；
  - 已填充字段名列表；
- 外部站点、项目与品牌的正式名称（JavDB、123AV、FC2 Content Market、Cloudflare 等）；
- 原文引用：
  - 西班牙法院封锁通知的西班牙语节选；
  - 站点返回的日文 / 英文标题；
  - 搜索关键词；
- 以 source_id 或文件名构成的标题（如 `# SOURCE_VIABILITY - av123`、`# PHASE2_PROBE_SET.md`）；
- 多行 API 签名与模块名列表（出现在部分 Phase 3 / Phase 4 合同与 HANDOFF 中）。

### 4.3 残留英文正文

残留扫描之后，未发现需要翻译而未翻译的英文说明正文。扫描脚本标记的英文行都属于第 4.2 节所列类别（数据表行、状态字面量、签名、原文引用、source_id 标题），以及第 4.1 节的冻结证据文件。

## 5. 疑似历史语义问题（仅记录，未修正）

以下问题在翻译中发现，均按原文保留，未作语义修正；是否修正由后续治理决定。

1. `docs/specifications/PHASE4_DISCOVERY_CONTRACT.md` 开头 Scope 段写“完整范围外清单见 section 9”。但完整的范围外清单实际位于第 13 节；第 9 节是子树 / 条目失败隔离。翻译保留“section 9”。
2. `docs/specifications/PHASE4_ORGANIZE_PLAN_CONTRACT.md` 有若干章节交叉引用与实际编号不符，疑似历次改版重排导致：
   - §2 “pure function … (section 9)”：确定性规则实际在第 14 节；
   - §3 “Collision policy … (section 7-8)”：实际在第 12 节；
   - §3 “validated once, centrally … (section 6)”：实际在第 10 节；
   - §8 “No aggregation trace … (section 12)”：第 12 节实际是冲突 / 覆盖策略。
   翻译保留原编号。
3. `docs/review/P4_C1_HANDOFF.md` R2.4 段原文在提及 `.parts` 的句子中有一个不成对的反引号，疑为作者笔误。翻译中逐字保留，未修正。
4. `docs/specifications/PHASE3_AGGREGATION_CONTRACT.md` 原文有包含反引号的字面量 `` <>"`{}|^ ``，导致 Markdown 反引号成对关系异常。翻译中逐字保留，未修正。

## 6. 约束核对

| 检查项 | 结果 |
|---|---|
| `git diff --name-only 947949a HEAD` 仅包含 `*.md` | 是 |
| JSON 修改 | 否 |
| 生产代码（`src/**/*.py`）修改 | 否 |
| 测试（`tests/**`）修改 | 否 |
| `scripts/**`、`pyproject.toml` 修改 | 否 |
| 文件重命名 | 否 |
| SHA / finding ID / severity / 状态 / 测试数字 / 日期改变 | 否（逐文件脚本校验） |
| `git diff --check` | 通过（无输出） |
| 全量测试 | 见第 7 节 |

## 7. 全量测试

命令（本机需关闭 cacheprovider 并指定 basetemp）：

```
python -m pytest -q -p no:cacheprovider --basetemp=<job tmp>
```

结果：**4172 passed, 19 skipped**（77.24s），与 P4-C6 基线一致；0 failed。测试在 Translation Candidate `a94b961` 的工作树上运行，本报告提交不涉及任何代码或测试。

## 8. 状态

- Independent Docs Review：REQUIRED
- DOCS-CN：NOT CLOSED
- P4-C7：NOT STARTED
- Phase 4：NOT CLOSED
