# P5-C2 施工计划（Construction Plan）-- Amane Compatibility & Adapter Closure

```text
Governance Mode                    : Acceleration v2
Governance Authority               : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
P5-C1 Final Closure Docs Head      : 232ece06c1d166929846bc9c63ffc7314ea3a484
P5-C1 Final Reviewed Technical Head: 0289b191659234a0e74f498e7b412c06c3d28d4a
Package                            : P5-C2 — Amane Compatibility & Adapter Closure
Package Frozen Base                : CANDIDATE — subject to Design Review（候选 = 232ece06c1d166929846bc9c63ffc7314ea3a484；本文不自行宣称已冻结）
Planning Parent                    : 232ece06c1d166929846bc9c63ffc7314ea3a484
Risk Class                         : B / C（候选 B；带强制升级门 U2-1..U2-10；合同第 5 节；本次设计调查未触发 B -> C；
                                     请 Design Reviewer 重点裁决合同第 5.3 节“sidecar 是否构成 security boundary change”，若是则升为 C）
Vertical Closure                   : 一个普通用户拿官方 release bundle（plugin zip + 独立 Core wheel + 校验清单 + 安装说明），按文档在
                                     受支持的 Amane 版本（最低 v0.15.0；当前稳定版 v0.18.0）的真实宿主上从零安装 -> 被发现 -> 配置往返 ->
                                     构建 provider -> 一次离线 fetch -> reload -> 升级 / 替换 -> 卸载，并在两个版本上得到等价的 adapter 语义；
                                     产物确定、哈希可复核，兼容状态由机器可读见证裁决
Why not merge with P5-C1           : P5-C1 已 CLOSED（独立 Level 1 + R1 Closure Review PASS；Final Reviewed Technical Head 0289b19…）。
                                     不是“技术上不能合并”，而是治理边界：P5-C1 是已冻结的 **logic closure**（SearchQuery -> Core -> MediaMetadata /
                                     None / SourceError 的语义，对 exact v0.15.0 公共 API + 脚本化传输）；P5-C2 是 **host compatibility / release closure**
                                     （真实宿主、多版本、冻结桌面包、Core 供给、最终 artifact）。合并 = 重开已 PASS 的 logic closure 证据；两者的失败类别
                                     （逻辑缺陷 vs 环境 / 版本 / 供给缺陷）与所需 Reviewer 视角不同（合同第 4 节 Q1）
Why not split further              : 兼容矩阵、Core 供给、artifact、真实宿主见证共享同一份坐标、同一组 artifact 哈希和同一份兼容 JSON；
                                     任何一段单独都不能回答“官方包能否在受支持版本上安装并等价工作”。拆成 compat / supply / artifact / integration
                                     只增加等待，不增加 correctness / safety / auditability；**不规划 P5-C3**（合同第 4 节 Q3）
Internal Stages                    : S1 Compatibility & Supply / S2 Install-Reload-Cross-Version Integration / S3 Final Artifact & Acceptance Evidence
                                     （S1 -> S2 -> S3 连续施工；无中间 Review；无 S 级状态 docs）
Independent Review Plan            : one Design Review（本候选之后，实现之前，必需）
                                     + one final C-level Review（S1-S3 全部完成之后；Independent Level 1）
                                     + 若 FAIL：ONE unified R1 + Final Closure
Owner Question Gate                : BUSINESS DECISIONS ONLY（本设计未发现需要 Owner 的业务问题；支持集“精确坐标 + 有见证的平台”为技术 / 证据裁决，
                                     可被 Design Reviewer 否决，不阻塞）
Evidence Gate                      : C2-E01..C2-E30（合同第 15 节；E01 diff scope、E02 C1 语义不变、E03 版本坐标、E04 API 矩阵、E05 Core 供给 / 安装、
                                     E06 确定性 artifact、E07-E14 安装 / 发现 / 配置 / build / reload / 升级 / 缺失 / 不兼容 Core、E15-E16 跨版本结果 / 错误等价、
                                     E17 HTTP 生命周期、E18 无 vendor、E19 无新持久化、E20 mutation、E21-E23 宿主集成、E24 平台矩阵、E25-E28 测试 / skip 对账、
                                     E29 artifact 哈希、E30 gaps）
Python Runtime Authority           : 主项目 regression = 3.12.x；宿主源码见证 = 3.14.x（每个宿主版本一个独立 venv）；冻结包 = 内置 3.14.7
Production Change                  : NONE in src/**；adapters/amane/fc2_amane_adapter/** 零字节变化（U2-6）；只新增 adapters/amane/shim/** 与发布构建工具
```

```text
Package               = P5-C2 Amane Compatibility & Adapter Closure
Branch                = claude/phase5-c2-amane-compatibility（自 232ece0… 创建）
规范合同              = docs/specifications/PHASE5_C2_AMANE_COMPATIBILITY_CONTRACT.md
P5-C2 Design          = CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Contract              = CANDIDATE
Construction Plan     = CANDIDATE（本文件）
Implementation        = NOT STARTED
```

坐标规则：本候选的 Design Base = `232ece0…`。**Package Frozen Base 只有在独立 Design Review 建立后才存在**；Design Review 通过之前，本文任何位置都不得被读作 FROZEN / DESIGN PASS / IMPLEMENTATION AUTHORIZED。
唯一 authority 转换：独立 Design Review PASS -> 该 Review 建立 Design Accepted Head -> Frozen Contract / Construction Plan -> 才允许进入 S1。不创建纯状态的 design closure docs 提交（治理文档第 11.1 节）。

Design PASS 之后，开发者只能**执行**本计划：不得重新设计、不得调整 S 边界、不得把设计项推迟到“开发时再决定”。合同与本计划未写明的实现细节（helper 命名、文件内部组织、fixture 写法、断言写法）
按以下优先级裁决，并在 commit message 记录理由：

```text
1. Governance 与 Frozen Contract（P5-C1 与 P5-C2）  2. fail closed  3. 宿主 HTTP 生命周期不被绕过  4. 不改变 CLOSED package（含字节）
5. deterministic  6. 不写用户文件  7. 最小依赖（构建器 / locator 仅标准库）  8. testability
```

---

## 1. 治理四问与 C 粒度

完整四问见**合同第 4 节**，此处只记录与施工粒度相关的结论。

* **Q1** 不与 P5-C1 合并：已冻结的 logic closure vs host compatibility / release closure（不是“技术上不能合并”）。
* **Q2** 边界降低的风险：防止为迁就宿主而回改已 PASS 的 adapter 语义（用字节原样 `_impl/` + 树哈希变成机检不变量）；把宿主漂移隔离在兼容矩阵；把 Core 供给这一未闭合 authority 决策单独暴露。
* **Q3** 不值得再多一个边界：只有一次 Design Review + 一次 C 级 Review（+ 必要时统一 R1）；S1-S3 连续。
* **Q4** 取消边界影响 auditability / safety（不影响 P5-C1 已验证的 correctness）。
* **P5-C2 内部不再拆分**：S1-S3 共享同一 Frozen Contract、同一矩阵 JSON、同一组 artifact 哈希、同一次 Review。

---

## 2. 风险与升级门

Risk Class 候选 = **B**。升级门 U2-1..U2-10 见合同第 5.2 节，任一触发 = 立即 STOP，不得自行按 B 继续。
另：**真实宿主观测与合同第 6 节设计期实证不一致**（例如冻结宿主开始读取 `PYTHONPATH`、`install_plugin_zip` 不再先导入插件、v0.18.0 的 `PluginContext` 字段变化）= 设计前提失效（U2-5），STOP 回到 Design Review。

---

## 3. 内部施工模型（S1 -> S2 -> S3，连续）

**连续施工**：S1 -> S2 -> S3 之间不停止、不等待 Owner、不自动 Review、不写状态 docs。每个 S 结束：相关测试全绿、独立 commit（可 push）、commit message 记录重要裁决。S 级 checkpoint 不是 Review 触发点。

### S1 —— Compatibility & Supply（兼容矩阵 + Core 供给 + 确定性构建）

目标：把坐标、API 指纹、shim locator、Core wheel、plugin zip、release bundle 的**纯逻辑与构建**做完并在主进程（3.12）上全绿；不需要真实宿主。

1. **Authority 机器核对与基线**（输出写入 HANDOFF）：`HEAD` 是 `232ece0…` 的后代；`git diff 232ece0..HEAD -- fc2-organizer/src fc2-organizer/adapters/amane/fc2_amane_adapter fc2-organizer/tests fc2-organizer/pyproject.toml` 为空（S1 开始时）；
   3.12 上记录 `pytest tests -q` 的 collected / passed / skipped 与 skip nodeid 清单（E27 / E28 基线，应等于 P5-C1 终点 8448 / 40 / 0）。
2. **Amane 坐标核对（E03）**：重新从 upstream 读取 tag / tag 对象 / peeled commit / release / `requires-python` / `PLUGIN_API_VERSION`；GitHub Release 元数据确认“当前稳定版”（合同第 6.1 节定义）；记录 main 是否 == 稳定版。**此刻冻结矩阵坐标**；与设计期不同（出现更新的 `v*` release）时：以 S1 时刻为准，在 HANDOFF 记录差异，不是 blocker。
3. **API 指纹（E04）**：复用 C1 `tools/amane_api_manifest.py`（不改）为 v0.18.0 生成 `adapters/amane/api_manifest/amane_v0.18.0_api_manifest.json`；新增 `tools/compare_amane_api.py`：读取各清单，输出“适配器可控子集指纹”并断言两个必需版本相等；对合同第 6.2 节每一行差异产生机检断言。
4. **shim**：`adapters/amane/shim/plugin.py`（合同第 9.1 节三行，不得增加逻辑）与 `adapters/amane/shim/_ffcc_locator.py`（合同第 8.3 节；纯 stdlib；3.11-3.14 语法；`ensure_core(pin, module_file)` 的 4 步与 4 个固定模板）。
5. **Core wheel 构建器** `tools/build_core_wheel.py`（合同第 10.2 节）+ **发布台账** `adapters/amane/release/core_release_ledger.json`（同版本不同 tree 哈希 -> 构建失败）。
6. **plugin zip / bundle 构建器** `tools/build_amane_release.py`（合同第 9.1、10 节）：生成 `_ffcc_pin.py`（只含字面量）；从 `adapters/amane/fc2_amane_adapter/*.py` 字节原样（LF 规范化）放入 `_impl/`；拒绝 id != `PLUGIN_ID`；allow-list / forbidden 扫描；`ZIP_STORED`；输出 plugin zip、wheel、`SHA256SUMS`、`COMPATIBILITY.json`（S3 才填入见证派生内容，S1 先生成结构占位并有 schema 测试）、`INSTALL.zh-CN.md`（S3 定稿）、`VERSION`、bundle zip。**不 import C1 构建器**。
7. **主进程纯逻辑测试**（3.12；`tests/amane_compat/test_amane_compat_*.py`；pytest 文件名全局唯一）：
   * locator：4 步全部分支、每个模板、哈希篡改 1 字节 / 符号链接 / 超大文件 / 目录同名 / 多 wheel / 无 sidecar / `module_file` 为 staging 路径与正式路径；**纯函数 + `tmp_path`**，不依赖 Amane；
   * 确定性（E06）：两个解释器（subprocess 3.12 与 3.14）× 两个输出目录 × CRLF 检出副本 -> 哈希相等；allow-list / forbidden；
   * 无 vendor（E18）；`_impl` 字节 == C1 树（E02）；shim / locator AST 守卫（无写 API、无网络、无 amane / pydantic / Core import）；
   * 兼容 JSON schema 与自洽规则（E23 / E24 / M2-16）。
8. 不修改 `pyproject.toml`（测试通过 `importlib` 加载 shim 文件，不新增 pythonpath）。

### S2 —— Install / Reload / Cross-Version Integration（真实宿主）

目标：在真实宿主上跑 HC-01..HC-18（合同第 11.2 节）。

1. **宿主准备工具** `tools/prepare_amane_hosts.py`：为每个 `--host` 创建独立 venv（3.14.x）并安装该 Amane 检出的依赖（记录 `pip freeze` 哈希；联网仅限依赖安装，属环境前提，写入 HANDOFF）；下载 / 校验官方冻结包（比较 SHA256 与 Release 资产；解压到临时目录）。
2. **见证运行器** `tools/run_amane_compat_gate.py`（顶层只依赖标准库）：对每个 host 启动**真实 Amane 服务进程**（随机空闲端口、临时 `AMANE_DATA_DIR`、固定 `AMANE_TOKEN`、`AMANE_HOST=127.0.0.1`），通过真实 HTTP API 执行 HC 场景；HC-04 / HC-17 / HC-07 等需要进程内对象的场景用 C1 同法的 subprocess 脚本（`tests/amane_compat/host_scripts/`；pytest 从不导入）。
   场景脚本只依赖宿主公共 API（`amane.plugin`）与 `amane.plugins.packaging` / `PluginManager` / `CrawlerFactory` 的**真实**对象，**不 mock** 它们。
3. **回环 fixture**：`127.0.0.1` 上的 HTTP 服务器（线程；随机端口；记录请求；脚本化响应）；`base_url` 覆盖指向它。公网零访问。
4. **配置往返一致性守卫（E09）**：对合同第 12.2 节每个样本，同时取 PATCH 状态、`validate_plugin_config`、`parse_settings`、`build_plugin_provider` 四个布尔值并断言全真或全假。
5. **跨版本等价（E15 / E16）**：同一请求集在 v0.15.0 / v0.18.0 上产生规范化 JSON，比较 sha256；对宿主 `FailureReason` 全部成员做桥分类的全函数枚举测试。
6. **冻结包见证**：HOST-A-WIN / HOST-B-WIN 在 Windows 上运行同一 HC 集合（服务进程 = `onedir/Amane.Server.exe`，环境变量同设计期探针；**不**设置 `PYTHONPATH`）。macOS / Linux / Docker 不可得 -> 标 `UNVERIFIED`，不伪造。
7. HOST-C-MAIN：若 main == 稳定版 commit -> `IDENTICAL_TO_STABLE`，不重复运行；否则运行，**失败不阻塞**，记录为信息差异。HOST-MID 可选。
8. S2 结束的 checkpoint：HC 全集在两个必需源码宿主 + 两个冻结包上通过（或 BLOCKED + 根因，不得绕过）；JSON 初稿生成。

### S3 —— Final Artifact & Acceptance Evidence

1. 在最终提交的树上构建**最终** bundle，并确认：pin 中的 wheel 哈希 == 实际 wheel 哈希；`COMPATIBILITY.json` 由兼容见证派生；`SHA256SUMS` 通过 `sha256sum -c`；E06 在最终树上重做。
2. `INSTALL.zh-CN.md` 定稿（简体中文，遵循《文档语言规范》）并 **“文档即测试”**（E05）：脚本按文档的每一步操作真实宿主（含第 8.6 节升级与第 8.7 节故障分支）。
3. `adapters/amane/README.md` 状态行更新（仅文档；不改 C1 树）。
4. **提交** `docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json`（确定性；同一环境重跑逐字节相同；测试重算 artifact 哈希并与之核对）。
5. **Mutation / 非空洞（E20）**：M2-01..M2-16 以补丁脚本作用于**临时副本**，断言 killer 失败。
6. **回归**：P5-C1 `tests/amane_adapter/**` 在 3.12 上全绿；P5-C1 要求的 3.14 证据集 A / B 在 3.14 上重跑，数字与 C1 终点一致（A 1833、B 520）；`pytest tests -q`（3.12）全量，skip 对账（E27 / E28）。
7. 写 `docs/review/P5_C2_HANDOFF.md`（实现完成后；**不是**本设计阶段产物）：逐条 E01..E30、坐标、哈希、局限、`Next`。
8. 只在 S3 末尾提交 HANDOFF 后停止，等待**一次**独立 Level 1 Review。

---

## 4. 文件范围（allow-list；E01 逐条核对）

```text
新增（允许）
  fc2-organizer/adapters/amane/shim/plugin.py
  fc2-organizer/adapters/amane/shim/_ffcc_locator.py
  fc2-organizer/adapters/amane/release/core_release_ledger.json
  fc2-organizer/adapters/amane/release/INSTALL.zh-CN.md            （构建器复制进 bundle 的源文档）
  fc2-organizer/adapters/amane/api_manifest/amane_v0.18.0_api_manifest.json   （+ 可选 v0.16.1 / v0.17.0 / main 的信息清单）
  fc2-organizer/tools/build_core_wheel.py
  fc2-organizer/tools/build_amane_release.py
  fc2-organizer/tools/compare_amane_api.py
  fc2-organizer/tools/prepare_amane_hosts.py
  fc2-organizer/tools/run_amane_compat_gate.py
  fc2-organizer/tests/amane_compat/**                              （test_amane_compat_*.py + host_scripts/ + 回环 fixture）
  fc2-organizer/docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json
  fc2-organizer/docs/review/P5_C2_HANDOFF.md                      （S3 末尾）

修改（允许，仅文档）
  fc2-organizer/adapters/amane/README.md                          （状态行 / 指向 C2；不涉及 C1 树）

零 diff（任何改动 = 升级门）
  fc2-organizer/src/**                         U2-1
  fc2-organizer/adapters/amane/fc2_amane_adapter/**   U2-6（树哈希 == C1 witness）
  fc2-organizer/tests/**（既有，含 tests/amane_adapter/**）  U2-7
  fc2-organizer/tools/amane_api_manifest.py、build_amane_plugin_zip.py、run_amane_host_witness.py   U2-7
  fc2-organizer/pyproject.toml                 U2-8
  docs/specifications/PHASE5_C1_*.md、docs/P5_C1_CONSTRUCTION_PLAN.md、docs/review/P5_C1_HANDOFF.md、docs/PROJECT_GOVERNANCE_ACCELERATION.md
  docs/acceptance/evidence/P5_C1_HOST_WITNESS.json
```

> 新测试目录取 `tests/amane_compat/`（既有 tests 目录无 `__init__.py`，**pytest 文件名必须全局唯一**，一律 `test_amane_compat_*.py`）。
> 既有的 P5-ENTRY-CLOSURE-OBS-01 隔离规则（主进程从不 import `amane`、不操纵 `sys.modules`）继续适用：宿主相关场景只在 subprocess / 外部进程内执行。

---

## 5. 测试与证据执行（exact）

```text
主进程（3.12.x）   : python -m pytest tests/amane_compat tests/amane_adapter -q          （targeted）
                     python -m pytest tests -q                                           （full；E27）
3.14 证据集 A / B  : 沿用 P5-C1 计划第 5.3 节的 exact 命令与 allow-list（回归；数字对账 C1）
宿主见证           : <py3.14> tools/run_amane_compat_gate.py --host a=<v0.15.0 检出+venv> --host b=<v0.18.0 检出+venv>
                     --frozen a-win=<官方 v0.15.0 zip> --frozen b-win=<官方 v0.18.0 zip> [--host main=…] --out docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json
构建               : python tools/build_core_wheel.py --out <dir>
                     python tools/build_amane_release.py --core-wheel <whl> --out <dir>
```

PASS 条件：E01..E30 全部有证据或有被接受的 `UNVERIFIED` / gap 记录；`failed = 0`；新增 skip = 0；两个必需宿主版本与两个冻结包上 HC-01..HC-18 全通过。

---

## 6. 证据映射（Contract -> 实现 -> 测试 / 见证）

| 合同 | 实现 | 证据 |
|---|---|---|
| 第 6 / 7 节 矩阵 | `compare_amane_api.py`、两份 API 清单 | E03 / E04：`test_amane_compat_api_matrix.py`、JSON `hosts[]` |
| 第 8.3 节 locator | `shim/_ffcc_locator.py` | E05 / E13 / E14 / M2-03 / M2-14 / M2-15：`test_amane_compat_locator.py` + HC-10 / HC-11 / HC-16 |
| 第 9 节 包结构 | `build_amane_release.py` | E02 / E18 / M2-01 / M2-02 / M2-04：`test_amane_compat_release_layout.py` |
| 第 10 节 artifact | `build_core_wheel.py`、`build_amane_release.py` | E06 / E29 / M2-09 / M2-10：`test_amane_compat_determinism.py` |
| 第 11 节 HC | `run_amane_compat_gate.py`、`host_scripts/` | E07-E12 / E21 / E22 / E17 / E19 |
| 第 12 节 config | 同上 | E09 / M2-06 / M2-12：HC-05 / HC-08 + 一致性守卫 |
| 第 13 节 parity | 同上 | E15 / E16 / M2-07 / M2-08 |
| 第 14 节 JSON | `run_amane_compat_gate.py` | E23 / E24 / E29 / M2-16：`test_amane_compat_matrix_json.py` |
| 第 16 节 mutation | `test_amane_compat_mutation_nonvacuity.py` | E20 |

---

## 7. 自审清单（设计者在提交候选前核对）

1. 没有修改 `src/**`、P5-C1 树 / 测试 / 证据 / 文档、`pyproject.toml`：本候选只新增两份设计文档。
2. 没有宣称 FROZEN / DESIGN PASS / IMPLEMENTATION AUTHORIZED；`Package Frozen Base` 标为 CANDIDATE。
3. Amane 坐标直接来自 upstream（`git rev-parse` / `git show` / GitHub Release API），v0.15.0、当前稳定版（v0.18.0）、main 三者分开记录；main 与稳定版同 commit 被如实标注，未当作独立见证。
4. 设计期实证（W2-04 / W2-05）在**真实官方冻结包**上执行并记录；对未验证的平台（macOS / Linux / Docker）明确 `UNVERIFIED`。
5. Core 供给方案满足“不 vendor / 普通用户可从零安装”，并回答了合同第 8.1 节的全部问题。
6. 每个 mutant 有 killer；每个 E 项有判据。

---

## 附录 A —— 设计期探针（复现 W2-04 / W2-05；**探针不进入仓库**）

在临时目录 `P`：

```text
1. 解压官方 Amane-v0.18.0-windows-x64.zip（及 v0.15.0）到 P/win18、P/win15。
2. 建 P/probe/data/plugins/sources/ffcc.probe/plugin.py（探针），P/probe/deps/ 放被测物。
3. 环境：AMANE_DATA_DIR=P/probe/data  AMANE_LOG_DIR=P/probe/logs  AMANE_PORT=18765  AMANE_HOST=127.0.0.1
         AMANE_SAFE_DIRS=ALLOW_ALL  AMANE_TOKEN=probe  AMANE_WEB_DIST=P/win18/Amane/web
4. 启动 P/win18/Amane/onedir/Amane.Server.exe，等待就绪后
   curl -H "Authorization: Bearer probe" http://127.0.0.1:18765/api/plugins
   探针在导入时 raise RuntimeError("PROBE " + repr(结果))，结果出现在响应的 failures[].error。
```

* **W2-04 探针**：设 `PYTHONPATH=P/probe/deps`；探针记录 `sys.frozen`、`sys.version`、`os.environ["PYTHONPATH"]`、`sys.path`、`import ffcc_probe_dep` 的结果。
  观测：`frozen=True`、`3.14.7`、`PYTHONPATH` 在环境中、**不在** `sys.path`、`ModuleNotFoundError`。
* **W2-05 探针**：不设 `PYTHONPATH`；探针 `sys.path.insert(0, <P/probe/deps/fc2_metadata_core-0.1.0-py3-none-any.whl>)` 后 `import fc2_metadata_core` 与 `from fc2_metadata_core import aggregation`，记录 `"httpx" in sys.modules`。
  观测（v0.18.0 与 v0.15.0 均）：`core` 路径位于 wheel 内、`httpx_loaded=False`。
* 设计期用的 wheel 来自 `python -m pip wheel . --no-deps`（3.12；产物含 `fc2_organizer`，见 W2-06）；**这只是探针**，正式 Core wheel 由 `tools/build_core_wheel.py` 构建。
* 探针运行后：终止服务进程，删除 `P`；不触碰任何用户的 Amane 数据目录。

## 附录 B —— 设计期 API 差异复现命令

```text
git clone https://github.com/sqzw-x/amane.git <dir> && cd <dir>
git rev-parse v0.15.0 v0.15.0^{commit} v0.18.0 v0.18.0^{commit} origin/main
git show <tag>:pyproject.toml | grep -E 'requires-python|^version'
git grep -h 'PLUGIN_API_VERSION *=' <tag> -- src
git diff --stat v0.15.0 v0.18.0 -- src/amane/plugin src/amane/plugins src/amane/crawlers/models.py src/amane/net
git diff v0.15.0 v0.18.0 -- src/amane/plugins src/amane/crawlers/models.py src/amane/net/errors.py src/amane/net/http.py src/amane/crawlers/factory.py
git diff --stat v0.15.0 v0.18.0 -- src/amane/plugins/packaging.py src/amane/api/routes/plugins.py     # 期望：空（逐字节相同）
curl -s https://api.github.com/repos/sqzw-x/amane/releases?per_page=8                                   # 稳定版 = 最新非 draft / 非 prerelease 的 v* release
```

## 附录 C —— 状态

```text
P5-C2 Design         : CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Contract             : CANDIDATE
Construction Plan    : CANDIDATE
Implementation       : NOT STARTED
```
