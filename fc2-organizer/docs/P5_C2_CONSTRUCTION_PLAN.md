# P5-C2 施工计划（Construction Plan）-- Amane Compatibility & Adapter Closure

```text
Governance Mode                    : Acceleration v2
Governance Authority               : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
P5-C1 Final Closure Docs Head      : 232ece06c1d166929846bc9c63ffc7314ea3a484
P5-C1 Final Reviewed Technical Head: 0289b191659234a0e74f498e7b412c06c3d28d4a
Package                            : P5-C2 — Amane Compatibility & Adapter Closure
Package Frozen Base                : CANDIDATE — subject to Design Review（候选 = 232ece06c1d166929846bc9c63ffc7314ea3a484；本文不自行宣称已冻结）
Planning Parent                    : 232ece06c1d166929846bc9c63ffc7314ea3a484
Risk Class                         : C（Design Pre-Review R1 裁决；合同第 5 节）。理由**不是**“用了 `sys.path`”，而是 P5-C2 新建了**外部可执行 artifact 信任边界**：
                                     sidecar wheel -> 路径 / 类型校验 -> 完整性 pin（整个 wheel 的 sha256）-> 预解析 / `sys.path` -> 宿主进程内可执行代码（Design R2：准入面收窄为 **exact pinned wheel only**）；它决定哪些数据目录中的外部代码可以进入宿主进程执行
                                     = 治理定义的 security boundary。**Risk C 不自动拆分 S1/S2/S3**（security design 已在合同第 8 节完整冻结；不涉及不可逆用户数据操作；
                                     不修改 CLOSED production；无需中间 authority decision）；升级门 U2-1..U2-12
Vertical Closure                   : 一个普通用户拿官方 release bundle（plugin zip + 独立 Core wheel + 校验清单 + 安装说明），按文档在
                                     已验证支持坐标 SC-01..SC-04（Amane v0.15.0 最低版本目标 / v0.18.0 当前稳定版 × Windows x64 冻结桌面版 / 源码宿主）的真实宿主上从零安装 -> 被发现 -> 配置往返 ->
                                     构建 provider -> 一次离线 fetch -> reload -> 升级 / 替换 -> 卸载，并在两个版本目标上得到等价的 adapter 语义（支持声明是**坐标级**的，不是版本全局的）；
                                     产物确定、哈希可复核，兼容状态由机器可读见证裁决
Why not merge with P5-C1           : P5-C1 已 CLOSED（独立 Level 1 + R1 Closure Review PASS；Final Reviewed Technical Head 0289b19…）。
                                     不是“技术上不能合并”，而是治理边界：P5-C1 是已冻结的 **logic closure**（SearchQuery -> Core -> MediaMetadata /
                                     None / SourceError 的语义，对 exact v0.15.0 公共 API + 脚本化传输）；P5-C2 是 **host compatibility / release closure**
                                     （真实宿主、多版本、冻结桌面包、Core 供给、最终 artifact）。合并 = 重开已 PASS 的 logic closure 证据；两者的失败类别
                                     （逻辑缺陷 vs 环境 / 版本 / 供给缺陷）与所需 Reviewer 视角不同（合同第 4 节 Q1）
Why not split further              : 兼容矩阵、Core 供给、artifact、真实宿主见证共享同一份坐标、同一组 artifact 哈希和同一份兼容 JSON；
                                     任何一段单独都不能回答“官方包能否在已验证支持坐标上安装并等价工作”。拆成 compat / supply / artifact / integration
                                     只增加等待，不增加 correctness / safety / auditability；**不规划 P5-C3**（合同第 4 节 Q3）
Internal Stages                    : S1 Compatibility & Supply / S2 Install-Reload-Cross-Version Integration / S3 Final Artifact & Acceptance Evidence
                                     （S1 -> S2 -> S3 连续施工；无中间 Review；无 S 级状态 docs）
Independent Review Plan            : one Design Review（P5-C2 **第一次** pre-implementation Design Review，已完成：Final Verdict = FAIL，findings P5-C2-DESIGN-R-01..06）
                                     -> **ONE unified Design R2**（docs-only，一次闭合 R-01..R-06；增量审计：主体修复成立，遗留 R2-A-01..A-05）
                                     -> **Design R3**（本 docs-only 提交，窄范围一次闭合 R2-A-01..A-05；不重新设计）
                                     -> **P5-C2 Design R3 Incremental Closure Review**（只复查 R2-A-01..A-05 + R3 直接回归；不重新完整审 Amane API / 整个支持矩阵 / 整个 P5-C1 架构，
                                        除非 R2 实际改变核心 architecture；R2 的 trust-surface 收窄不是架构推翻）
                                     + **Security Review Focus**：Design Review 必须明确审合同第 8 节 locator 信任边界（exact pinned wheel only、预解析 / 回滚、威胁模型），并单独给出 security 裁决
                                     + one final C-level Review（S1-S3 全部完成之后；Independent Level 1；**必须独立执行 locator / security 证据 E31**，不得只引用 HANDOFF）
                                     + 若 FAIL：ONE unified R1 + Final Closure
                                     Incremental Closure Review PASS 之后才成立（本文**不**授权实现）：Frozen Contract / Plan = 该 Review 建立的 Design Accepted Head；Risk Class = C；S1 -> S2 -> S3 连续施工
Owner Question Gate                : BUSINESS DECISIONS ONLY（本设计未发现需要 Owner 的业务问题；支持声明为二维坐标 `(version, host_form, platform)`：
                                     SC-01 / SC-02（Windows x64 冻结桌面版）= 必需部署支持坐标，SC-03 / SC-04（源码宿主）= 必需集成兼容坐标，macOS / Linux / Docker = UNVERIFIED；属技术 / 证据裁决，
                                     可被 Design Reviewer 否决，不阻塞）
Evidence Gate                      : C2-E01..C2-E31（合同第 15 节；E31 = locator 信任边界 / security 的 PASS-FAIL 配对矩阵 E31-a..v，含 E31-u “wheel 已在 sys.path 但真实解析不是它”与 E31-v 精确 loader 类型；E01 diff scope、E02 C1 语义不变、E03 版本坐标、E04 API 矩阵、E05 Core 供给 / 安装、
                                     E06 确定性 artifact、E07-E14 安装 / 发现 / 配置 / build / reload / 升级 / 缺失 / 不兼容 Core、E15-E16 跨版本结果 / 错误等价、
                                     E17 HTTP 生命周期、E18 无 vendor、E19 无新持久化、E20 mutation、E21-E23 宿主集成、E24 平台 / 支持坐标矩阵、E25-E28 测试 / skip 对账、
                                     E29 artifact 哈希与派生 DAG、E30 gaps；E31 含 Reviewer 的 `.pyc` PoC 场景与失败回滚机械验证）
Python Runtime Authority           : 主项目 regression = 3.12.x；宿主源码见证 = 3.14.x（每个宿主版本一个独立 venv）；冻结包 = 内置 3.14.7
Production Change                  : NONE in src/**；adapters/amane/fc2_amane_adapter/** 零字节变化（U2-6）；只新增 adapters/amane/shim/** 与发布构建工具
```

```text
Package               = P5-C2 Amane Compatibility & Adapter Closure
Branch                = claude/phase5-c2-amane-compatibility（自 232ece0… 创建）
Design Candidate      = 8870df0ea42e60dd142a5878ea7c0abc6ca3c4b5（未经 Independent Review 即被 Owner 快速审计修订为 R1）
Design Pre-Review R1  = 5dac181f3b948ed0bcdfcedf34100ab1536e41ee（Parent = 8870df0…；C2-DESIGN-R1-01..04；**经独立 Full Design Review：FAIL**）
Design R2             = 01182642eccbed299577b35d4e9f88efe1b36f06（Parent = 5dac181…；P5-C2-DESIGN-R-01..06；增量审计：主体修复成立，直接引入 / 遗留 R2-A-01..A-05）
Design R3             = 本 docs-only 提交（Parent = 01182642…；R2-A-01..A-05；`git log -1 --format=%H -- fc2-organizer/docs/P5_C2_CONSTRUCTION_PLAN.md`）
规范合同              = docs/specifications/PHASE5_C2_AMANE_COMPATIBILITY_CONTRACT.md
P5-C2 Design R3       = CANDIDATE — INCREMENTAL DESIGN CLOSURE REVIEW REQUIRED
Contract              = CANDIDATE
Construction Plan     = CANDIDATE（本文件）
Implementation        = NOT STARTED
```

```text
—— Pre-L1 Authority Amendment A1（本计划侧；取代上方两个头部块中关于 Implementation / 状态的历史表述，上方保留为设计历史）——
P5-C2 PRE-L1 AUTHORITY AMENDMENT : CANDIDATE（docs-only；见附录 E 与合同第 11.7 节）
Previous Frozen Plan             : f358aca1ff6e056f28c3b9b2d0fcaa2f608ac124（Design Accepted Head）
Implementation Head              : 4358b3df3353d634e4c2e8b1ee6b71c0a07b5ace（本 amendment 的 Parent）
Implementation                   : COMPLETE CANDIDATE — NOT TECHNICALLY ACCEPTED
U2-5                             : TRIGGERED — AUTHORITY CORRECTION IN PROGRESS
Authority Status                 : CANDIDATE
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
* **Q2** 边界降低的风险：防止为迁就宿主而回改已 PASS 的 adapter 语义（用 LF 规范化字节同一的 `_impl/` + 树哈希变成机检不变量）；把宿主漂移隔离在兼容矩阵；把 Core 供给这一未闭合 authority 决策单独暴露。
* **Q3** 不值得再多一个边界：只有一次 Design Review + 一次 C 级 Review（+ 必要时统一 R1）；S1-S3 连续。
* **Q4** 取消边界影响 auditability / safety（不影响 P5-C1 已验证的 correctness）。
* **P5-C2 内部不再拆分**：S1-S3 共享同一 Frozen Contract、同一矩阵 JSON、同一组 artifact 哈希、同一次 Review。

---

## 2. 风险与升级门

Risk Class = **C**（合同第 5.1 节）；**Risk C 不自动拆分 S1/S2/S3**（合同第 5.2 节）。升级门 U2-1..U2-12 见合同第 5.3 节，任一触发 = 立即 STOP，不得自行继续。
其中 U2-11（放宽 locator 准入：接受任何非 exact-pinned-wheel 的 Core 来源 / 对已加载 Core 盲信 / 热切换 / 失败路径不回滚）与 U2-12（重新引入目录形态 Core 而无法冻结并验证覆盖全部可执行字节的规则 = DESIGN BLOCKER，不得降级为只哈希 `*.py`）是 Risk C 的专项门。

**Authority 优先级（领域化；合同第 2 节）**：P5-C1 Frozen Contract / Plan（CLOSED semantics）> P5-C2 Accepted Contract > P5-C2 Accepted Plan > Acceleration v2 > Task Prompt。
P5-C2 不得通过新合同静默 override P5-C1 CLOSED semantics；必须改变则 U2-1 / U2-6 / U2-7 STOP + authority amendment。
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
4. **shim**：`adapters/amane/shim/plugin.py`（合同第 9.1 节三行，不得增加逻辑）与 `adapters/amane/shim/_ffcc_locator.py`（合同第 8.3 节；纯 stdlib；3.11-3.14 语法；`ensure_core(pin, module_file)` 的 0..4 步、入口快照 -> wheel 证明 -> 防御性预解析 -> 至多一次插入（已存在则不插入、不重排、不提升）-> **最终真实解析证明（唯一成功规则）** / 回滚、**exact pinned wheel only** 与 4 个固定模板；**不实现树哈希、不验证 pyc、不接受任何目录形态**）。
5. **Core wheel 构建器** `tools/build_core_wheel.py`（合同第 10.2 节）+ **发布台账** `adapters/amane/release/core_release_ledger.json`（同版本不同 tree 哈希 -> 构建失败）；wheel 仅含 `*.py` + 4 个 dist-info 文件，成员 tree 哈希对拍 C1 `core_tree_sha256`（E31-q）。
6. **plugin zip / bundle 构建器** `tools/build_amane_release.py`（合同第 9.1、10 节）：生成 `_ffcc_pin.py`（只含字面量）；把 `adapters/amane/fc2_amane_adapter/*.py` 的 **LF 规范化字节**放入 `_impl/`（normalized-byte identity）；拒绝 id != `PLUGIN_ID`；allow-list / forbidden 扫描；`ZIP_STORED`；按合同第 10.5 节**严格无环的 DAG** 分两个子命令：`stage1`（L1：以 L0 wheel 的哈希生成 `_ffcc_pin.py`，输出 plugin zip、`INSTALL.zh-CN.md`、`VERSION`；INSTALL / VERSION 不含任何哈希）与 `finalize`（L2–L4：只读 MATRIX **Part A 的字段白名单**投影出 `COMPATIBILITY.json`，再生成 `SHA256SUMS`（5 个成员，不含自身）与 bundle zip）；S1 先实现并测试 `finalize` 的投影 / 顺序 / 禁止字段（以占位 Part A 作输入），S3 用真实 Part A 生成最终 bundle。**不 import C1 构建器**。
7. **主进程纯逻辑测试**（3.12；`tests/amane_compat/test_amane_compat_*.py`；pytest 文件名全局唯一）：
   * locator（E31 的**单元层**；**exact pinned wheel only**）：合同第 8.3 节 4 步全部分支、4 个模板、E31-a..v 的 PASS / FAIL 配对——含**已加载**的 exact pinned wheel（PASS）/ 错误版本 / 被篡改的同名 wheel / 目录形态（pip `--target` / editable / 源码，即使字节正确）FAIL，
      **未加载**的目录形态无 sidecar（FAIL，import 之前，`fc2_metadata_core` 不在 `sys.modules`）、目录形态 + 有效 sidecar（PASS，加载的是 wheel，目录中的 sentinel 不存在）、
      **Reviewer 的恶意 `.pyc` PoC（E31-h；复用合同 W2-12 的构造：以真实 wheel 解压的目录形态 Core，pyc 携带源文件相同 mtime / size，payload 写 sentinel；3.12 与 3.14 均执行，不得删除）**、
      sidecar 篡改 / 符号链接（无权限时 `os.lstat` 替身并记录 `symlink_privilege=false`，**不 skip**；真实宿主子项见附录 E 的 A1-3）/ 超大 / 同名目录 / 仅有其它版本 wheel、混合来源子模块、`sys.meta_path` 遮蔽（预解析即拒绝）、插入后才抢占的有状态 finder（**回滚**）、
      **每个 FAIL 机械断言 `sys.path` 与入口逐元素相同（同一 list 对象）、`sys.modules` 中 `fc2_metadata_core*` 对象身份不变、verified-wheel 的 importer-cache 条目 == 入口状态**（不要求恢复全局 importer cache）、成功路径至多一次插入且幂等（**重复调用仍执行最终真实解析**）；`module_file` 为 staging 路径与正式路径；
      **`tmp_path` + 真实构建的 wheel**，不依赖 Amane；每个用例以 subprocess 隔离（避免污染主进程 `sys.modules` / `sys.path`，遵守 P5-ENTRY-CLOSURE-OBS-01）；
   * 确定性（E06）：两个解释器（subprocess 3.12 与 3.14）× 两个输出目录 × CRLF 检出副本 -> 哈希相等；allow-list / forbidden；
   * **R3 增量（A-01..A-04）**：**E31-u**（wheel 已在 `sys.path`，更靠前有**惰性的**不受支持 Core 来源：目录包 `__init__.py` 只含注释或惰性 meta_path finder；不执行任何 payload）-> 必须 FAIL，惰性包从未被导入，状态与入口一致；**E31-v**（惰性的 `zipimporter` 子类 loader double）-> FAIL（`type(loader) is zipimporter`，非 `isinstance`）；**E31-l** 含入口有 / 无 verified-wheel cache 条目两个回滚子场景；**M2-23** 的 killer = E31-u；3.12 与 3.14 均执行；
   * 无 vendor（E18）；`_impl` 的 `tree_sha256` == C1 `adapter_tree_sha256`（E02，normalized-byte identity）；shim / locator AST 守卫（无写 API、无网络、无 amane / pydantic / Core import、无 `sys.modules` 修改、无树哈希 / pyc 逻辑）；
   * **artifact 派生 DAG 测试（E29 / M2-22）**：拓扑检查、禁止字段扫描（`COMPATIBILITY.json` / `INSTALL.zh-CN.md` / `VERSION` 不含 `SHA256SUMS` / bundle / 自身 / MATRIX 哈希）、改 MATRIX Part B 不改变 L2–L4、`sha256sum -c`、从仓库树重建逐字节一致；
   * 威胁模型措辞守卫（E31-t）：INSTALL 含“运行期间不要替换或删除 sidecar wheel”，且不含未被支持的“发布者认证 / 数字签名 / 防篡改”承诺；
   * 兼容 JSON schema 与自洽规则（E23 / E24 / M2-16）。
8. 不修改 `pyproject.toml`（测试通过 `importlib` 加载 shim 文件，不新增 pythonpath）。

### S2 —— Install / Reload / Cross-Version Integration（真实宿主）

目标：在真实宿主上跑 HC-01..HC-19（合同第 11.2 节）。

1. **宿主准备工具** `tools/prepare_amane_hosts.py`：为每个 `--host` 创建独立 venv（3.14.x）并安装该 Amane 检出的依赖（记录 `pip freeze` 哈希；联网仅限依赖安装，属环境前提，写入 HANDOFF）；下载 / 校验官方冻结包（比较 SHA256 与 Release 资产；解压到临时目录）。
2. **见证运行器** `tools/run_amane_compat_gate.py`（顶层只依赖标准库）：对每个 host 启动**真实 Amane 服务进程**（随机空闲端口、临时 `AMANE_DATA_DIR`、固定 `AMANE_TOKEN`、`AMANE_HOST=127.0.0.1`），通过真实 HTTP API 执行 HC 场景；HC-04 / HC-17 / HC-07 等需要进程内对象的场景用 C1 同法的 subprocess 脚本（`tests/amane_compat/host_scripts/`；pytest 从不导入）。
   场景脚本只依赖宿主公共 API（`amane.plugin`）与 `amane.plugins.packaging` / `PluginManager` / `CrawlerFactory` 的**真实**对象，**不 mock** 它们。
3. **回环 fixture**：`127.0.0.1` 上的 HTTP 服务器（线程；随机端口；记录请求；脚本化响应）；`base_url` 覆盖指向它。公网零访问。
4. **配置往返一致性守卫（E09）**：对合同第 12.2 节每个样本，同时取 PATCH 状态、`validate_plugin_config`、`parse_settings`、`build_plugin_provider` 四个布尔值并断言全真或全假。
5. **跨版本等价（E15 / E16）**：同一请求集在 v0.15.0 / v0.18.0 上产生规范化 JSON，比较 sha256；对宿主 `FailureReason` 全部成员做桥分类的全函数枚举测试；**E16 的覆盖按附录 E 的双轨证据模型（合同第 13.2 节 A1-4）**。
6. **冻结包见证**：HOST-A-WIN / HOST-B-WIN（坐标 SC-01 / SC-02，**必需的部署支持坐标**）在 Windows 上运行同一 HC 集合（服务进程 = `onedir/Amane.Server.exe`，环境变量同设计期探针；**不**设置 `PYTHONPATH`）。
   源码宿主 HOST-A-SRC / HOST-B-SRC（SC-03 / SC-04）= 必需的集成兼容。**macOS / Linux / Docker（SC-07 / SC-08 / SC-09）不可得 -> `UNVERIFIED`，不伪造，不进支持声明**（设计期已核对本环境无 Docker；不为扩大声明增加环境依赖）。
   **HC-19（Core 来源准入矩阵）**：真实宿主子进程内执行 E31 的 PASS / FAIL 配对；源码宿主覆盖 exact pinned wheel（PASS）、目录形态 Core（pip `--target` / editable / 源码 / `PYTHONPATH`，**含恶意 `.pyc` PoC**，无 sidecar -> FAIL，有 sidecar -> 加载 wheel 且 sentinel 不存在）、预加载的正确 / 错误 / 目录形态 Core、被篡改的同名 wheel、遮蔽 finder；冻结包覆盖 sidecar 各分支；每个 FAIL 要求 422 / `failures` + 固定模板 + 无半装 + `sys.path` 与入口逐元素相同 / `sys.modules` 中 `fc2_metadata_core*` 对象身份不变 / verified-wheel importer-cache 条目 == 入口状态；**HC-19 含 E31-u / E31-v（源码宿主；惰性 sentinel，不执行 payload）**，冻结包上无法在宿主进程里布置 `sys.path` 夹具，故只覆盖 sidecar 各分支。源码宿主**同样使用 sidecar wheel**（`AMANE_DATA_DIR/plugins/_ffcc_core/`），`pip` 只用于准备宿主 venv 依赖。
7. HOST-C-MAIN：若 main == 稳定版 commit -> `IDENTICAL_TO_STABLE`，不重复运行；否则运行，**失败不阻塞**，记录为信息差异。HOST-MID 可选。
8. S2 结束的 checkpoint：HC 全集在两个必需源码宿主 + 两个冻结包上通过（或 BLOCKED + 根因，不得绕过）；**MATRIX Part A** 初稿生成（Part B 不在此时写入）。

### S3 —— Final Artifact & Acceptance Evidence

1. 在最终提交的树上按合同第 10.5 节**冻结顺序**生成最终 artifact：`build_core_wheel`（L0）-> `build_amane_release stage1`（L1）-> `run_amane_compat_gate`（在 L0+L1 的确切字节上得到 MATRIX Part A）-> `build_amane_release finalize`（L2 `COMPATIBILITY.json` = Part A 白名单投影 -> L3 `SHA256SUMS` -> L4 bundle）-> 计算 `compatibility_json_sha256` / `sha256sums_sha256` / `release_bundle_sha256` 写入 **MATRIX Part B** 与 HANDOFF（**不写回 bundle**）；
   确认：pin 中的 wheel 哈希 == 实际 wheel 哈希；extract bundle 后 `sha256sum -c SHA256SUMS` 通过且成员字节 == 被验收的 L0 / L1 字节；在同一仓库树上重做 stage1 + finalize 得到与 Part B 逐字节一致的 L1–L4；E06 在最终树上重做。
2. `INSTALL.zh-CN.md` 定稿（简体中文，遵循《文档语言规范》）并 **“文档即测试”**（E05）：脚本按文档的每一步操作真实宿主（含第 8.6 节升级与第 8.7 节故障分支）。
3. `adapters/amane/README.md` 状态行更新（仅文档；不改 C1 树）。
4. **提交** `docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json`（Part A + Part B；确定性；同一环境重跑逐字节相同；测试重算 artifact 哈希并与之核对）；`status` 以**坐标** `(version, host_form, platform)` 为 key（合同第 14.1 节），含 `core_admission` 的 E31 用例结果；
   `COMPATIBILITY.json`、`INSTALL.zh-CN.md`、E24 使用同一份支持坐标表（合同第 7.2 节）；INSTALL 中任何 Docker 步骤标 `UNVERIFIED / informational — 不在本发布验收覆盖范围内`。
5. **Mutation / 非空洞（E20）**：M2-01..M2-23 以补丁脚本作用于**临时副本**，断言 killer 失败；其中 M2-14 / M2-15 / M2-17..M2-21 与 **M2-23（existing-wheel 分支不做最终真实解析，killer = E31-u）** 是 locator 信任边界的专项 mutant（E31；**M2-21 = 目录形态含未被 `*.py` 哈希表示的恶意 `.pyc`，killer = E31-h**），M2-22 = artifact 派生环（killer = E29 DAG 测试）。
6. **回归**：P5-C1 `tests/amane_adapter/**` 在 3.12 上全绿；P5-C1 要求的 3.14 证据集 A / B 在 3.14 上重跑，数字与 C1 终点一致（A 1833、B 520）；`pytest tests -q`（3.12）全量，skip 对账（E27 / E28）。
7. 写 `docs/review/P5_C2_HANDOFF.md`（实现完成后；**不是**本设计阶段产物）：逐条 E01..E31、坐标、哈希、局限、`Next`。
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

PASS 条件：E01..E31 全部有证据或有被接受的 `UNVERIFIED` / gap 记录；`failed = 0`；新增 skip = 0；两个必需宿主版本与两个冻结包上 HC-01..HC-19 全通过。

---

## 6. 证据映射（Contract -> 实现 -> 测试 / 见证）

| 合同 | 实现 | 证据 |
|---|---|---|
| 第 6 / 7 节 矩阵 | `compare_amane_api.py`、两份 API 清单 | E03 / E04：`test_amane_compat_api_matrix.py`、JSON `hosts[]` |
| 第 8.3 / 8.8 节 locator 与威胁模型（Risk C 信任边界） | `shim/_ffcc_locator.py` | E05 / E13 / E14 / **E31** / M2-03 / M2-14..M2-21：`test_amane_compat_locator.py`（单元层）+ HC-10 / HC-11 / HC-16 / **HC-19** |
| 第 9 节 包结构 | `build_amane_release.py` | E02 / E18 / M2-01 / M2-02 / M2-04：`test_amane_compat_release_layout.py` |
| 第 10 节 artifact | `build_core_wheel.py`、`build_amane_release.py` | E06 / E29 / M2-09 / M2-10：`test_amane_compat_determinism.py` |
| 第 11 节 HC | `run_amane_compat_gate.py`、`host_scripts/` | E07-E12 / E21 / E22 / E17 / E19 |
| 第 12 节 config | 同上 | E09 / M2-06 / M2-12：HC-05 / HC-08 + 一致性守卫 |
| 第 13 节 parity | 同上 | E15 / E16 / M2-07 / M2-08 |
| 第 10.5 节 artifact 派生 DAG | `build_amane_release.py`（stage1 / finalize） | E29 / M2-22：`test_amane_compat_artifact_dag.py` |
| 第 7.2 / 14 节 坐标与 JSON | `run_amane_compat_gate.py` | E23 / E24 / E29 / M2-16：`test_amane_compat_matrix_json.py`（坐标 key、UNVERIFIED 不得为 SUPPORTED、与 INSTALL / COMPATIBILITY 同表） |
| 第 16 节 mutation | `test_amane_compat_mutation_nonvacuity.py` | E20 |

---

## 7. 自审清单（设计者在提交候选前核对）

1. 没有修改 `src/**`、P5-C1 树 / 测试 / 证据 / 文档、`pyproject.toml`：Pre-Review R1 只修改两份 P5-C2 设计文档（docs-only）。
2. 没有宣称 FROZEN / DESIGN PASS / IMPLEMENTATION AUTHORIZED；`Package Frozen Base` 标为 CANDIDATE。
3. Amane 坐标直接来自 upstream（`git rev-parse` / `git show` / GitHub Release API），v0.15.0、当前稳定版（v0.18.0）、main 三者分开记录；main 与稳定版同 commit 被如实标注，未当作独立见证。
4. 设计期实证（W2-04 / W2-05）在**真实官方冻结包**上执行并记录；对未验证的平台（macOS / Linux / Docker）明确 `UNVERIFIED`。
5. Core 供给方案满足“不 vendor / 普通用户可从零安装”，并回答了合同第 8.1 节的全部问题。
6. 每个 mutant 有 killer；每个 E 项有判据。
7. **（HISTORICAL — SUPERSEDED BY R2：directory forms are no longer accepted execution modes；此条为 R1 时代的自审记录，其中“每一种执行模式下 fail closed（含已加载、editable、pip）”的表述已作废，目录形态 / editable / pip 不再是被接受的执行模式，现行规则见合同第 8.3 节）** Pre-Review R1：Authority 优先级已领域化（不再写 “Governance > Frozen Contract”）；Risk Class = C 且理由精确；Core pin 在**每一种**执行模式下 fail closed（含已加载、editable、pip）且无 `unverified-path`；
   支持声明为二维坐标，UNVERIFIED 平台不被版本状态覆盖；Design Review 为完整的第一次审查。
8. Design R2：删除目录形态 Core 的接受（exact pinned wheel only），`.pyc` PoC 在设计期复现并由 wheel-only 原型拒绝（3.12.10 / 3.14.7）；威胁模型（Defended / Not Defended / Non-claims）与 L-C2-13 ACCEPTED 已冻结；失败回滚（预解析 + 单次插入 + 再验证 + `sys.path` 还原）已冻结并有机械验证；artifact 派生 DAG 无环（设计期探针）；支持措辞全文坐标化；zipimport 的 verified root 与 `_impl` 的 normalized-byte identity 术语已统一。
9. **Design R3 直接回归守卫**：(1) 不存在任何“wheel anywhere in sys.path -> immediate success”的路径；(2) 每个 success path 都有最终真实解析证明；(3) 每个发生在 locator-owned path / cache 变化之后的失败都有精确回滚，且入口快照先于任何 probe；(4) 目录形态仍被拒绝；(5) 没有新增被接受的 Core 来源（受信 loader 仅 `type(...) is zipimporter`）；(6) E31-u / M2-23 / HC-19 / E31-p / I-C2-18 描述同一个不变量。
10. **Pre-L1 Authority Amendment A1**：U2-5 已被触发并如实记录（不是“从未发生”，也不是 production 缺陷）；A1-1（201）/ A1-2（HC-12a）是对宿主行为的 A 类修正；A1-3 是环境能力限制下的证据方法（locator 语义不变，充分性由 Reviewer 裁决）；A1-4 是 A + B（合同双轨模型 + 实现证据补齐）；未改变 adapter 语义 / 安全边界 / exact pinned wheel / Risk C / P5-C1 语义。

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

## 附录 C —— Design R2 设计期探针（**探针与原型不进入仓库**；以下为可复现说明）

在临时目录 `P`（用后删除）：

```text
W2-12  .pyc 绕过 PoC（3.12 与 3.14 各执行一次）
  1. 用 `python tools/build_core_wheel.py`（实现后）或设计期的 `pip wheel . --no-deps` 得到 Core wheel；把 wheel 内 `fc2_metadata_core/` 解压为目录 P/dircore/fc2_metadata_core/
  2. 在 P/dircore 上运行一次 `import fc2_metadata_core`，让 Python 生成 `__pycache__/__init__.cpython-3x.pyc`（时间戳型）
  3. 记录 `tree_sha256`（C1 的 tools/run_amane_host_witness.tree_sha256，仅 *.py）
  4. 用 `importlib._bootstrap_external._code_to_timestamp_pyc(code, 源文件 mtime, 源文件 size)` 生成携带相同 mtime / size 的恶意 pyc 覆盖原 pyc；
     payload = 写 sentinel 文件后继续原 `__init__.py` 源码
  5. 再次计算 `tree_sha256`（期望：不变）；新解释器 `import fc2_metadata_core`（期望：sentinel 存在 = payload 已执行）
  设计期结果：3.12.10 与 3.14.7 均为“树哈希不变、payload 已执行”。

W2-13  wheel-only 准入原型（合同第 8.3 节算法的最小实现，脚本不入库）
  场景 A..F：目录形态含恶意 pyc 无 sidecar（期望 UNVERIFIABLE、Core 未导入、状态不变）；目录形态 + 有效 sidecar（期望 wheel 入 sys.path[0]、find_spec 解析到 wheel、重复调用幂等）；
  被篡改同名 wheel；meta_path 抢占 finder（预解析即拒绝）；仅在 wheel 入 sys.path 之后才抢占的有状态 finder（回滚，sys.path[:] == before）；符号链接（本账户无权限 -> lstat 替身）。
  同时打印 zipimport 语义：loader 类型、loader.archive、loader.prefix、spec.origin、spec.submodule_search_locations（均为归档内路径）。设计期结果：3.12.10 / 3.14.7 全部符合期望。

W2-14  artifact 派生 DAG 探针（脚本不入库）
  以 ZIP_STORED 确定性 zip 实现 L0..L4（合同第 10.5 节）：同输入两次构建字节相同；COMPATIBILITY.json 不含自身 / SHA256SUMS / bundle 哈希；sha256sum -c 通过且 SHA256SUMS 不列自身；
  改变 Part A 只改变 L2–L4、不改变 L0 / L1；构造“COMPATIBILITY.json 内嵌 SHA256SUMS 哈希”的环形变体，证明重新计算后该哈希立即过期（不动点不可达）。设计期结果：全部符合期望。
```

实现期的正式测试（`tests/amane_compat/**`）必须覆盖上述全部场景，并满足 E31 / E29 的判据；探针本身不是实现，不得被当作测试替身提交。

## 附录 D —— 状态

```text
P5-C2 Design R3      : CANDIDATE — INCREMENTAL DESIGN CLOSURE REVIEW REQUIRED
Contract             : CANDIDATE
Construction Plan    : CANDIDATE
Risk Class           : C
Implementation       : NOT STARTED
```

### Design R2 修订记录（历史；本计划侧；与合同“Design R2 修订记录”一一对应；R-01..R-06 主体修复经增量审计成立）

| Finding | 本计划的同步内容 | 状态 |
|---|---|---|
| P5-C2-DESIGN-R-01 | S1 locator 单元层 / S2 HC-19 / S3 mutation 改为 exact pinned wheel only；恶意 `.pyc` PoC（E31-h）与 M2-21 为必做且不得删除；builder 不含树哈希 / pyc 逻辑；host form 与 Core supply form 分离（源码宿主也用 sidecar wheel） | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-02 | 威胁模型（合同第 8.8 节）进入 S1 措辞守卫测试（E31-t）；L-C2-13 ACCEPTED；INSTALL 必须含“运行期间不要替换或删除 sidecar wheel” | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-03 | S1 locator 测试机械断言每个 FAIL 的 `sys.path` / `sys.modules` 不变，含预解析拒绝与插入后回滚两条路径 | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-04 | S1 builder 分 `stage1` / `finalize`；S3 按冻结顺序生成 L0..L4 并把最终外层哈希写入 MATRIX Part B 与 HANDOFF（不写回 bundle）；新增 DAG 测试与 M2-22 | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-05 | 计划头与各节的支持措辞坐标化 | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-06 | `_impl` 统一为 LF 规范化字节 / normalized-byte identity；zipimport 的 verified root 语义写入合同第 8.3 节 | REMEDIATED — INCREMENTAL REVIEW REQUIRED |

Design R2 不改变：Authority model、Risk Class C、Amane 坐标、API 兼容结论、支持坐标结构、sidecar 主架构、P5-C1 映射与 `_impl` 语义、Core 不 vendor、`src/**` 与 `pyproject.toml` 零改动、无热切换 Core、Phase 6 边界、S1/S2/S3 连续意图。R2 不得写为 CLOSED / PASS / FROZEN / AUTHORIZED。

### Design R3 修订记录（本计划侧；与合同“Design R3 修订记录”一一对应）

| Finding | 本计划的同步内容 | 状态 |
|---|---|---|
| R2-A-01 | S1 locator 单元层新增 E31-u（wheel 已在 `sys.path`、更靠前有惰性不受支持来源 -> 必须 FAIL）；S2 HC-19 同步；S3 新增 M2-23（killer = E31-u）；重复调用仍执行最终真实解析（E31-p）；locator 实现必须遵守“NO SUCCESS RETURN UNTIL ACTUAL CURRENT RESOLUTION PROVES THE EXACT PINNED WHEEL”（I-C2-18） | REMEDIATED — REVIEW REQUIRED |
| R2-A-02 | 测试断言的回滚范围统一为 `sys.path` + verified-wheel importer-cache 条目 + `sys.modules` 的 Core 对象身份；不要求恢复全局 importer cache；入口快照先于任何 probe | REMEDIATED — REVIEW REQUIRED |
| R2-A-03 | 已加载 Core 的证明措辞 = current-origin + current-artifact proof，不是历史已执行字节证明（N-03 / L-C2-13） | REMEDIATED — REVIEW REQUIRED |
| R2-A-04 | 受信 loader 判据 = `type(loader) is zipimporter`；E31-v 以惰性 `zipimporter` 子类 double 验证 | REMEDIATED — REVIEW REQUIRED |
| R2-A-05 | 自审清单 R1 时代条目标注 HISTORICAL — SUPERSEDED BY R2；R1 / R2 修订记录标为历史；正文无“字节原样 `_impl`” | REMEDIATED — REVIEW REQUIRED |

Design R3 不改变：exact pinned wheel only、目录形态拒绝、Risk Class C、威胁模型与 TOCTOU 接受、artifact 派生 DAG、坐标化支持声明、Amane 坐标 / API 结论、P5-C1 normalized `_impl` 语义、不 vendor、无热切换 Core、Phase 6 边界。R3 不得写为 CLOSED / PASS / FROZEN / AUTHORIZED。

### Design R3 设计期探针（**不入库**；惰性 sentinel fixture，不执行任何 payload，不复现攻击链）

```text
W2-15  对第 8.3 节 2A..2E 的最小原型（3.12.10 与 3.14.7 均执行，全部符合期望）
  A  wheel 已在 sys.path，更靠前有惰性的不受支持 Core 目录包（__init__.py 只含注释）-> 预解析（wheel-first）通过，最终真实解析命中惰性包 -> REJECT；
     sys.path 与入口相同、verified-wheel cache 条目被清除、惰性包未被导入
  B  wheel 已在 sys.path[0] -> 成功，未插入
  C  wheel 不在 sys.path -> 一次插入；重复调用幂等（wheel 条目恰好 1 个，第二次仍走最终真实解析）
  D  插入后才抢占的有状态 finder，入口无 cache 条目 -> 回滚后 sys.path 与 cache 均回到入口
  E  同 D，但入口已有 cache 条目 -> 回滚后仍是原对象
  F  惰性 zipimporter 子类 loader double -> `type(loader) is zipimporter` 拒绝；`isinstance` 会接受（探针同时打印两者）
```

实现期 E31 必须在 3.12 与 3.14 上执行上述冻结不变量；探针本身不是实现，不得被当作测试替身提交。

## 附录 E —— Pre-L1 Authority Amendment A1（本计划侧）

```text
P5-C2 PRE-L1 AUTHORITY AMENDMENT : CANDIDATE
Implementation Head              : 4358b3df3353d634e4c2e8b1ee6b71c0a07b5ace
Implementation                   : COMPLETE CANDIDATE — NOT TECHNICALLY ACCEPTED
U2-5                             : TRIGGERED — AUTHORITY CORRECTION IN PROGRESS
```

### E.1 权威语义同步（与合同第 11.7、13.2 节与文末修订记录一一对应）

| 项 | 计划侧的同步内容 | 状态 |
|---|---|---|
| A1-1 HC-01 状态码 | 所有“上传 plugin zip 成功”的宿主判据 = 精确 201（HC-01 / HC-09 / HC-13 / HC-14 / HC-16 / HC-19 的 PASS 分支）；reload 200、DELETE 204、PATCH 200 不变；不泛化为 2xx | AMENDMENT CANDIDATE — AUTHORITY REVIEW REQUIRED |
| A1-2 HC-12a | HC-12 拆为 12a..12e；12a = `.zip` 名 + 非 ZIP 字节 -> 宿主实测 500 + 拒绝 + 无残留 + 无注册 + 插件代码从未执行 + 两版相同；12b..e 仍 422；不放宽任何其它安装失败判据 | AMENDMENT CANDIDATE — AUTHORITY REVIEW REQUIRED |
| A1-3 符号链接 | locator 语义不变；原要求为目标；环境不可得时 `ENVIRONMENTALLY_UNAVAILABLE` + 必需替代证据（单元层 3.12 / 3.14 替身仅改 `st_mode`、M2-14 killer、`symlink_privilege=false`）；不得表述为真实宿主已执行 PASS；**充分性由 Reviewer 裁决** | AMENDMENT CANDIDATE — AUTHORITY REVIEW REQUIRED |
| A1-4 E16 | 双轨：E16-A（传输可诱发 kind 端到端；记录实际观测 kind，标签不得虚称）+ E16-B（全部 `SourceErrorKind` 成员在每个必需宿主进程内经生产映射路径与生产 provider 转换，四宿主哈希相等） | AMENDMENT CANDIDATE — AUTHORITY REVIEW REQUIRED |

### E.2 本 amendment 不做什么

* **不**重新拆分 S1 / S2 / S3，不新增 S 级 Review，不改变 Risk Class C，不重新设计 P5-C2。
* `4358b3d` 的实现保持为 **candidate evidence**。在本 amendment 取得独立 Authority Review 的通过结论之前，**不授权**修改任何 production 代码 / 测试 / 工具 / evidence JSON / HANDOFF；
  若 Reviewer 日后要求纠正，也只允许 **evidence-only** 的修正（不得改变 adapter 语义、locator 准入规则、exact pinned wheel 政策或 P5-C1 CLOSED 语义）。
* 不重新打开：exact pinned wheel only、R3 最终解析不变量、回滚、威胁模型 / TOCTOU、artifact DAG、支持坐标模型、P5-C1 映射语义；`prefix == ""` 不是 amendment 事项（合同本来只要求顶层 spec）。

### E.3 amendment 被独立接受之后：Evidence Executor 的对账清单（本轮**不执行**）

| # | 对账项 | 说明 |
|---|---|---|
| R-1 | HC-01 等安装判据 | 网关已按 201 判定；核对 HC-09 / HC-13 / HC-14 / HC-16 / HC-19 的 PASS 分支同为 201；`INSTALL.zh-CN.md` 无需改（不含状态码） |
| R-2 | HC-12 拆分 | 网关逐个记录 12a..12e 的状态码 / 残留 / 注册 / “插件代码从未执行”；12a 明确标注为宿主缺陷变体 |
| R-3 | 符号链接 | `core_admission` 为符号链接子项记录 `observed = ENVIRONMENTALLY_UNAVAILABLE` + `symlink_privilege=false`；`validate_matrix` 只在该子项接受该取值（其它子项出现 = 问题）；补测试；HANDOFF 与 HC-19 描述不得称“真实宿主已执行 PASS”；单元层替身 / M2-14 killer 已存在（核对即可） |
| R-4 | E16 | (a) 重命名 / 标注 `kind_decode_error_bad_charset`、`kind_redirect_error_loop`、`kind_response_too_large`（它们实际产生的是 `parse_error+invalid_response` / `connection_error` / `parse_error+invalid_response`），每个用例记录**实际观测的 kind**；(b) 新增宿主内 E16-B：用 Core 公共构造器构造 `SourceResult` / `AggregationResult`，运行生产映射 `map_aggregation`，再经生产 provider 转换得到宿主 `FailureReason` / `detail`，覆盖全部 16 个成员，四宿主哈希相等（`NOT_FOUND` -> no-match）；(c) 现有 `op_enumerations` 只调用 `reason_for_kind` 叶子函数，**不满足** E16-B，必须补足；(d) parity 载荷与 matrix 校验 / 测试同步 |
| R-5 | HANDOFF 更正 | “U2-1..U2-12 均未触发 / Authority Escalation: NONE”改为如实记录 U2-5 已触发及本 amendment 的处理；E16 的“6 个不可诱发”更正为“端到端只观测到 7 个 kind，其余 9 个未观测”；HC-12 / 符号链接 / 201 的偏差改述为已冻结的 amendment 事实；不得使用“PASS / CLOSED / ACCEPTED”描述 amendment 自身 |
| R-6 | 再生成与再验证 | 网关文件哈希、`core_admission` 行与 parity 载荷会变化 -> MATRIX Part A、`COMPATIBILITY.json`（L2）、`SHA256SUMS`（L3）、bundle（L4）与 Part B 重新生成；L0 / L1 的输入文件（locator / shim / adapter / INSTALL / 构建器）**不在授权修改范围内**，其哈希应保持不变，若变化即为越权；按合同第 10.5 节顺序在最终树上重做 DAG；重跑 `tests/amane_compat`、全量、3.14 集合 A / B / C 与 skip 对账；在干净检出上再次核对 |
| R-7 | 之后 | 对账完成并经 Reviewer 同意后，才送独立 Level 1 Review |

### E.4 留给 Reviewer 的单独裁决与未修正事项

1. A1-3 的替代证据（Risk C 证据替代）是否足够；Designer 不自行宣称可接受。
2. 合同文末“未被本 amendment 修改”的 HC-11(c)（冻结包无法布置目录形态夹具）文字是否需要在后续 amendment 中澄清。
3. 若 Reviewer 要求把 A1-3 的真实宿主子项补证：条件见合同第 11.7 节 A1-3 第 4 条（环境所有者合法提供能力，不改变系统安全设置）。

### E.5 状态

```text
P5-C2 PRE-L1 AUTHORITY AMENDMENT : CANDIDATE
Implementation Head              : 4358b3df3353d634e4c2e8b1ee6b71c0a07b5ace
Implementation                   : COMPLETE CANDIDATE — NOT TECHNICALLY ACCEPTED
U2-5                             : TRIGGERED — AUTHORITY CORRECTION IN PROGRESS
Next                             : P5-C2 PRE-L1 INDEPENDENT AUTHORITY AMENDMENT REVIEW（尚未开始 Level 1；未开始 Phase 6）
```
