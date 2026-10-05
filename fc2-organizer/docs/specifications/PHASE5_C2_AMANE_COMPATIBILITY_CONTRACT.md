# P5-C2 合同（Contract）-- Amane Compatibility & Adapter Closure

```text
状态                    : P5-C2 Design R3: CANDIDATE — INCREMENTAL DESIGN CLOSURE REVIEW REQUIRED
Contract                : CANDIDATE
Construction Plan       : CANDIDATE（docs/P5_C2_CONSTRUCTION_PLAN.md）
Implementation          : NOT STARTED
Governance Mode         : Acceleration v2
Governance Authority    : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
P5-C1 Final Closure Docs Head       : 232ece06c1d166929846bc9c63ffc7314ea3a484
P5-C1 Final Reviewed Technical Head : 0289b191659234a0e74f498e7b412c06c3d28d4a
Package Frozen Base     : CANDIDATE = 232ece06c1d166929846bc9c63ffc7314ea3a484（是否冻结由独立 Design Review 建立；本文不自行宣称）
Design Base             : 232ece06c1d166929846bc9c63ffc7314ea3a484（Design 起始基线，不等于已冻结的 Package Frozen Base）
Risk Class              : C（Design Pre-Review R1 裁决：P5-C2 新建“外部可执行 artifact 信任边界”= security boundary；第 5 节。Risk C 不自动拆分 S1/S2/S3）
Design R3               : docs-only 窄范围收口（R2-A-01..A-05；Parent = 01182642eccbed299577b35d4e9f88efe1b36f06；见文末“Design R3 修订记录”）；仍是 CANDIDATE，**不是** FROZEN / PASS / AUTHORIZED / CLOSED
Design R2               : docs-only 统一修订（P5-C2-DESIGN-R-01..06；Parent = 5dac181f3b948ed0bcdfcedf34100ab1536e41ee；见文末“Design R2 修订记录”）；仍是 CANDIDATE，**不是** FROZEN / PASS / AUTHORIZED
Design Pre-Review R1    : docs-only 修订（C2-DESIGN-R1-01..04；见文末“Design Pre-Review R1 修订记录”）；仍是 CANDIDATE，**不是** FROZEN / PASS / AUTHORIZED
Branch                  : claude/phase5-c2-amane-compatibility
```

```text
—— 以下状态块（Pre-L1 Authority Amendment A1）取代上方 Design 阶段头部中关于 Implementation / 状态的历史表述；上方头部保留为设计历史 ——
P5-C2 PRE-L1 AUTHORITY AMENDMENT : CANDIDATE（A1；docs-only；见文末“Pre-L1 Authority Amendment A1 修订记录”与第 11.7 节）
Previous Frozen Contract         : f358aca1ff6e056f28c3b9b2d0fcaa2f608ac124（Design Accepted Head）
Implementation Head              : 4358b3df3353d634e4c2e8b1ee6b71c0a07b5ace（本 amendment 的 Parent）
Implementation                   : COMPLETE CANDIDATE — NOT TECHNICALLY ACCEPTED
U2-5                             : TRIGGERED — AUTHORITY CORRECTION IN PROGRESS
Authority Status                 : CANDIDATE（尚无独立 Authority Amendment Review 结论；本文不自行宣称）
```

> 本文是 **候选合同**。Design Review PASS 之前，本文不是 Frozen Contract，不授权实现。
> P5-C1（CLOSED）已冻结的全部语义（SearchQuery 映射、Core 调用、HTTP 桥、MediaMetadata 映射、错误映射、来源归属、契约测试、
> 插件树布局）**保持冻结，本文不重新设计其中任何一项**。P5-C2 只闭合 P5-C1 合同第 26 节表 J 中标记为 P5-C2 的项。

---

## 0. 一页结论（给 Reviewer）

| 问题 | 本合同的裁决 |
|---|---|
| 版本兼容目标（version compatibility target） | **Amane v0.15.0（最低版本目标）与 v0.18.0（当前稳定版）**。**支持声明是坐标级的（coordinate-scoped），不是版本全局的**：只能按第 7.2 节的坐标 SC-01..SC-09 表述，**不得**单独写“v0.18.0 SUPPORTED / CONDITIONALLY SUPPORTED”或“支持 v0.15.0 / v0.18.0” |
| 当前稳定版 v0.18.0 的坐标状态 | `(v0.18.0, frozen desktop, Windows x64)` = **SC-02** 与 `(v0.18.0, source host, Windows x64)` = **SC-04**：设计期默认 **CONDITIONALLY_SUPPORTED**，条件 = 实现期 E15 / E16 / E22 在**该坐标**上 PASS，否则该坐标 BLOCKED 并给出根因；v0.18.0 在 macOS / Linux / Docker 上仍为 UNVERIFIED（SC-07..SC-09） |
| 支持声明的坐标 | **二维：`(Amane 版本, 宿主形态, 平台)`**，不再只用版本。Windows x64 冻结桌面版 = 必需支持部署；源码宿主 / Python 3.14 = 必需集成兼容；macOS / Linux / Docker = **UNVERIFIED**，不属于本包的支持声明（第 7.2 节） |
| current main | 设计核对时 `main == v0.18.0`（同一 commit）；**INFORMATIONAL COMPATIBILITY WITNESS**，不是 release contract |
| 同一 artifact 能否同时跑在 v0.15.0 与 v0.18.0 | **能**：单一 plugin zip、单一 Core wheel、**无版本分支**、**生产代码内无 feature detection**（第 7 节） |
| Core 最终供给方式 | **Core sidecar wheel**（独立 wheel，由用户放进 `{data_dir}/plugins/_ffcc_core/`）。随包 **shim locator** 只接受 **exact pinned wheel**（文件名 == pin、整个 wheel 的 sha256 == pin、普通文件、非符号链接、大小有界、同根 origin），已加载的 Core 也必须证明来自**同一个** exact pinned wheel，否则 fail closed。**pip 安装 / 已解压 / editable / 源码 / `PYTHONPATH` 目录等目录形态的 Core 一律不被接受**（`UNVERIFIABLE`）——因为目录形态存在 `.pyc` 等未被 `*.py` 哈希覆盖的可执行字节（第 8.3 节 / W2-12）。**不 vendor、不把 Core 放进 plugin zip**（第 8 节） |
| 为什么不是 `pip install` / 目录形态 | (1) 设计期实测：Windows 冻结桌面版**忽略 `PYTHONPATH`**，且插件不能声明 pip 依赖，桌面用户没有可写的解释器环境（W2-04 / W2-05）；(2) **目录形态不可证明 exact pin**：复现了 `.pyc` 替换攻击（`*.py` 树哈希不变而 payload 执行，W2-12）。wheel 形态由整文件 sha256 覆盖全部可执行字节（W2-13）。源码宿主同样使用 sidecar wheel；`pip` 只可用于**准备宿主 venv 依赖**，**不是** locator 的信任来源 |
| 怎样做到 P5-C1 零改动 | 插件 zip 内把 **P5-C1 树的 LF 规范化字节**（派生自 `adapters/amane/fc2_amane_adapter/*.py`）放进 `_impl/` 子包；zip 根部新增一个很薄的 **shim**（`plugin.py` + `_ffcc_locator.py` + `_ffcc_pin.py`）。P5-C1 的树哈希、测试、证据、合同 §22 的缺失 Core 消息全部不变（第 9 节） |
| Risk Class | **C**。原因**不是**“用了 `sys.path`”，而是 P5-C2 新建了**外部可执行 artifact 信任边界**（sidecar wheel -> 路径 / 类型校验 -> 完整性 pin -> `sys.path` -> 宿主进程内可执行代码），它决定哪些数据目录中的外部代码可以进入宿主进程执行 = 治理定义的 security boundary（第 5 节）。Risk C **不**自动拆分 S1/S2/S3；仍 S1 -> S2 -> S3 连续 |
| 需要 Owner 的业务问题 | NONE |

---

## 1. 目的、范围与非范围

### 1.1 P5-C2 回答的问题

```text
一个普通用户，拿到官方发布包，按文档操作，能否在已验证的支持坐标（SC-01..SC-04：v0.15.0 / v0.18.0 × Windows x64 冻结桌面版 / 源码宿主）上
从零安装 -> 被发现 -> 配置 -> 构建 provider -> 取到一次（离线）结果 -> reload -> 升级 -> 卸载，
且在 v0.15.0 与当前稳定版上得到等价的 adapter 语义？
```

### 1.2 Scope（做）

1. 直接从 Amane upstream 核实 v0.15.0 / 当前稳定版 / main 的坐标与公共 API，冻结兼容矩阵（第 6、7 节）。
2. 冻结兼容策略：最低版本、当前稳定版、main 的地位；feature detection 的允许与禁止（第 7 节）。
3. 冻结 Core 的**最终供给方式**与 plugin / Core 的版本配对关系（第 8 节）。
4. 冻结最终分发物（plugin zip、Core wheel、校验清单、版本元数据、安装文档、兼容清单）与其**确定性**（第 10 节）。
5. 冻结安装 / 升级 / reload / 卸载 / 配置往返的**真实宿主**验收（第 11、12 节）。
6. 冻结跨版本语义等价与允许差异（第 13 节）。
7. 冻结机器可读的兼容见证与版本漂移门（第 14 节）。
8. 冻结 Evidence Gate、Mutation 与测试环境（第 15-17 节）。

### 1.3 Non-Scope（不做；任何一项出现 = 越权）

```text
修改 src/**（Core / Organizer）                         修改 P5-C1 CLOSED 的 adapter 树、测试、证据、合同
把 Core 源码复制 / vendor / 打包进 plugin zip           Phase 6 批处理工作流 / 真实用户媒体 / Organizer UI / scheduler
真实公网 FC2 站点验收（公网可用性不得成为 acceptance blocker）   持久化 / 数据库 / 缓存 / 用户文件移动或覆盖
新的 HTTP 客户端 / 绕过宿主 HTTP 生命周期                使用 Amane 浏览器回退 / check_connectivity / max_attempts / traits
修改 pyproject.toml / 依赖
```

---

## 2. Authority 与坐标

| 坐标 | 值 |
|---|---|
| P5-C1 Final Closure Docs Head | `232ece06c1d166929846bc9c63ffc7314ea3a484`（P5-C2 Design 起始基线） |
| P5-C1 Final Reviewed Technical Head | `0289b191659234a0e74f498e7b412c06c3d28d4a` |
| Governance Authority | `3b9d39e9adbcc8a009707486eebbb8736a5b1c4d` |
| P5-C1 Frozen Contract | `docs/specifications/PHASE5_C1_AMANE_ADAPTER_CONTRACT.md`（本文不修改） |
| P5-C1 Frozen Construction Plan | `docs/P5_C1_CONSTRUCTION_PLAN.md`（本文不修改） |
| P5-C1 HANDOFF | `docs/review/P5_C1_HANDOFF.md`（本文不修改） |

**Authority 优先级（领域化；与 Acceleration v2 第 4 节冻结的“Frozen Contract > Frozen Construction Plan > Governance > Task Prompt”一致，不再写“Governance > Frozen Contract”）**：

```text
1. P5-C1 Frozen Contract / Frozen Construction Plan
     —— 对 P5-C1 **CLOSED semantics**（SearchQuery 映射、Core 调用、HTTP 桥、MediaMetadata 映射、错误映射、来源归属、插件树布局、缺失 Core §22）继续具有约束力
2. P5-C2 Accepted Contract
     —— 只 governing P5-C2 的 compatibility / supply / release scope（兼容矩阵、Core 供给、artifact、安装 / 升级 / reload、跨版本等价、兼容见证）
3. P5-C2 Accepted Construction Plan        —— 服从 P5-C2 Contract
4. Acceleration v2 Governance（docs/PROJECT_GOVERNANCE_ACCELERATION.md）
5. Task Prompt
```

* **P5-C2 不得通过新合同静默 override P5-C1 CLOSED semantics。** 本合同与 P5-C1 合同在 P5-C1 CLOSED 语义上冲突时，一律以 P5-C1 合同为准。
* 若 P5-C2 的实现必须改变 P5-C1 CLOSED semantics（任何字节改动 adapter 树 = U2-6；任何 CLOSED 测试 / 证据改动 = U2-7；任何 `src/**` = U2-1）：**STOP，需要 authority amendment**，不得自行继续。
* 上述“Accepted”指：独立 Design Review PASS 之后冻结的版本；在此之前本合同与施工计划只是 CANDIDATE，**不具备**上述约束力。

**与 P5-C1 合同第 26 节表 J 的对应**：本合同逐项闭合表 J 的 P5-C2 列（真实运行的 Amane 安装 / 重载 / 启停；配置往返；当前发布线兼容矩阵；
Core 最终供给与最终分发包；3.14 证据集回归；P5-C2 HANDOFF）。**真实网络冒烟**表 J 写“P5-C2 或 Phase 6”：本合同裁决为 **Phase 6**（理由：公网可用性不得成为 acceptance blocker；
本合同以本机回环 + 脚本化传输提供离线真实宿主证据，见第 11 节）。

---

## 3. 冻结架构（只新增，不改动）

```text
Amane host（v0.15.0 / v0.18.0；Python >= 3.14）
  └─ {data_dir}/plugins/sources/ffcc.fc2-metadata/        ← 宿主落盘（目录名 = descriptor.id）
       plugin.py            [C2 新增 shim]  ensure_core() -> from ._impl.plugin import Plugin
       _ffcc_locator.py     [C2 新增，纯 stdlib]  Core 定位 / 校验 / sys.path
       _ffcc_pin.py         [C2 构建期生成]  Core 版本 + wheel sha256 + 配对元数据
       _impl/               [P5-C1 树的 LF 规范化字节；无 __init__.py]
         plugin.py _core_gate.py _settings.py _number.py _bridge.py _runtime.py _outcome.py
  └─ {data_dir}/plugins/_ffcc_core/                        ← 用户放置（sidecar；不在 sources/ 之下）
       fc2_metadata_core-<ver>-py3-none-any.whl            ← 独立 Core 分发物（不含在 plugin zip 内）
```

依赖方向（冻结）：`shim -> _ffcc_locator / _ffcc_pin`；`shim -> _impl.plugin`（P5-C1 树，未做任何内容修改）；`_impl.* -> fc2_metadata_core`。
`Core / Organizer` 仍然永不 import Amane；`_ffcc_locator` 不 import Core、不 import Amane、不 import pydantic。

---

## 4. 治理四问（治理文档第 15 节；真实判断）

**Q1 为什么 P5-C2 不与 P5-C1 合并？**
不是“现在技术上不能合并”：P5-C1 已 CLOSED，其 logic closure（adapter 的映射 / 桥 / 错误 / 归属 / 契约测试）已有独立 Level 1 + R1 Closure Review 的 PASS
与冻结哈希（Final Reviewed Technical Head `0289b19…`）。把宿主兼容与发布 closure 合并回去，等于**重开一个已 PASS 的 logic closure 的证据**。
两者的裁决对象不同：P5-C1 回答“一个查询是否得到正确且安全的 Amane 结果”（语义，对 exact v0.15.0 公共 API + 脚本化传输）；
P5-C2 回答“官方发布包能否在已验证支持坐标（SC-01..SC-04）的真实宿主上安装、配置、重载、升级并产生等价语义”（兼容 / 发布）。前者的错误是逻辑缺陷，后者的错误是环境 / 版本 / 供给缺陷，
需要的证据（多宿主版本、冻结桌面包、artifact 哈希）与 Reviewer 视角不同。

**Q2 当前边界降低了什么风险？**
(a) 防止“为了让某个宿主版本通过”而回头修改已 PASS 的 adapter 语义（本合同用 LF 规范化字节同一的 `_impl/` + 树哈希把它变成可机检的不变量）；
(b) 把宿主漂移（`multi_language -> traits`、`raw_results` 移除、`WebClient.request` 的 `max_attempts` 与 `max_retries=0` 语义、浏览器回退、`FailureReason.API_ERROR`）隔离在兼容矩阵里，由机器可读见证裁决；
(c) 把 Core 供给这个唯一尚未闭合的 authority 决策（含“不 vendor”）单独暴露给 Design Review。

**Q3 额外边界是否值得额外 stop / review / closure？**
**不值得再多一个。** 本包只有 **一次 Design Review + 一次 C 级 Level 1 Review**（必要时一次统一 R1）；内部 S1/S2/S3 连续施工，无中间 Review，无 S 级状态文档。
没有 P5-C3。拆得更细（compat / supply / artifact / integration 各一个 C）只增加等待，不增加 correctness / safety / auditability（它们共享同一份矩阵与同一组 artifact 哈希）。

**Q4 移除 P5-C2 边界是否影响 correctness / safety / auditability？**
影响 **auditability 与 safety**：没有它，“官方包能不能装上”“Core 怎么来”“新版 Amane 是否还支持”没有 authority 来源，P5-C1 的“Core 必须可 import”会变成口头约定（L-08）。
不影响 P5-C1 已验证的 correctness（逻辑不变）。故边界保留，规模最小化。

---

## 5. Risk Class 与升级门

### 5.1 裁决：Risk Class = C（Design Pre-Review R1；取代原 B 候选）

**理由（精确）**：不是因为单纯使用了 `sys.path`。而是 P5-C2 **新建了一条外部可执行 artifact 的信任边界**：

```text
数据目录中的 sidecar wheel
  -> 路径 / 类型校验（普通文件、非符号链接、大小上限、文件名 == pin）
  -> 完整性 pin（整个 wheel 的 sha256 == pin）
  -> 预解析验证 + sys.path（单次 locator-owned 插入，失败回滚）
  -> 在 Amane 宿主进程内经 zipimport 作为可执行代码被导入
```

这条边界决定“**哪些数据目录中的外部代码可以进入宿主进程执行**”，属于 Acceleration v2 第 8.3 节 C 类定义中的 **security boundary**。
Amane 文档明示插件本身是进程内可信任意代码，这**不**使新增的加载路径变成“无边界”：恰恰相反，需要有明确冻结、可审、可测的准入规则（第 8.3 节），
否则“任意写入数据目录的 wheel / 任意已预装的同名包”会成为进入宿主进程的未经校验的路径。

**其余 B→C 触发项逐项检查**：

| 触发项 | 结论 | 依据 |
|---|---|---|
| 外部可执行 artifact 信任边界（security boundary） | **触发 -> Risk C** | 本节上文；第 8.3 节冻结准入规则；E31 / M2-14..M2-22 专项证据 |
| 修改 CLOSED P5-C1 semantics | 未触发 | `_impl/` = P5-C1 树的 LF 规范化字节（normalized-byte identity）；P5-C1 测试 / 证据 / 合同 / HANDOFF 零 diff；§22 缺失 Core 消息不变（第 9.3 节） |
| 修改 Core production | 未触发 | `src/**` 零 diff；Core wheel 由未修改的 `src/fc2_metadata_core/**` 构建 |
| 持久化 / 不可逆 migration | 未触发 | adapter / locator 不写任何文件；构建产物只写 `--out`（第 12 节） |
| 用户数据 source-loss / 覆盖或移动用户文件 | 未触发 | 验收只用临时目录与自建 Amane 数据目录；不碰用户影片；第 11.6 节 |
| 大规模 public contract change | 未触发 | 发布包格式是**新增**的、可版本化的 public artifact；不改 P5-C1 的任何公共语义 |

### 5.2 Risk C 对施工颗粒度的影响（冻结）

```text
Risk C DOES NOT automatically split S1 / S2 / S3.
```

仍允许 **S1 -> S2 -> S3 连续施工**（一个 C），因为：(1) security design（准入规则、模板、不变量、证据、mutant）已在本合同第 8 节**完整冻结**，实现不再做 authority 决策；
(2) 实现不涉及不可逆的用户数据操作；(3) 不修改 CLOSED production（`src/**`、P5-C1 树 / 测试 / 证据均零 diff）；(4) 不需要中间 authority decision。
Risk C 带来的**增量治理**只有两项（不增加包、不增加中间 stop）：

1. **Security Review Focus（Design Review）**：独立 Design Review 必须**明确审**第 8 节 locator 信任边界（准入规则的完备性、fail-closed、已加载 Core 的处理、目录形态的删除与 exact pinned wheel 单一准入面、模板与不变量、mutant 覆盖），并在结论中单独给出 security 裁决。
2. **Final C-level Review 必须独立执行 locator / security 证据**：Reviewer 在自己的 checkout 上**独立重跑**第 8.3 节全部准入分支（E31）与 M2-14..M2-22，不得仅引用 HANDOFF。

### 5.3 强制升级门（任一触发 = 立即 STOP；不得自行继续）

```text
U2-1  任何 src/** 改动                                        U2-6  需要改变 adapters/amane/fc2_amane_adapter/** 的任何字节
U2-2  Core 源码出现在 plugin zip 内（vendor / 复制 / 内嵌）     U2-7  需要改变任何已 CLOSED 测试 / 证据（P5-C1 与 Phase 1-4）
U2-3  新增持久化 / adapter 写文件 / 用户文件被写入或移动        U2-8  需要 pyproject.toml / 依赖改动（含新增 pythonpath）
U2-4  需要绕过宿主 HTTP 生命周期（自建客户端 / 浏览器回退）      U2-9  生产代码出现按版本字符串 / 异常文本 / 私有模块 monkeypatch 的分支
U2-5  真实宿主观测与本合同第 6 节设计期实证不一致              U2-10 把 Phase 6 的内容（批处理 / 真实媒体 / 公网验收）带入 C2
U2-11 locator 准入规则被放宽（接受任何非 exact-pinned-wheel 的 Core 来源——目录 / pip / editable / 源码；对已加载 Core 盲信；热切换 / purge Core；失败路径不回滚 `sys.path`）
U2-12 需要重新引入目录形态 Core 的接受路径而无法冻结并验证“覆盖全部可执行字节（.py / .pyc / 所有影响 import 的文件）”的确定性规则——必须 STOP / DESIGN BLOCKER，不得降级为只哈希 `*.py`
```

> **U2-5 的历史事实（A1 如实记录）**：U2-5 在 S2 / S3 实现期间**已经被触发**——真实宿主观测与冻结合同对宿主行为（`POST /api/plugins` 的成功状态码、非 zip 上传的 HTTP 状态）的假设不一致，
> 另有两处冻结的证据方法在实现环境中无法照写执行（真实符号链接子项；“每个 `SourceErrorKind` 一例”）。Implementation 继续施工并如实记录了这些事实，但**没有权限放宽 Frozen Contract**；
> 此前 HANDOFF 写的“U2-1..U2-12 均未触发”不成立（需在 amendment 被独立接受后由 Evidence Executor 对账更正）。
> 本 amendment（第 11.7 节与文末修订记录）在**独立 Level 1 Review 之前**偿还这笔 authority debt；它不是 production correctness 缺陷，也不能被描述成“U2-5 从未发生”。
>
> U2-6 的含义：adapter 树哈希（`tree_sha256(adapters/amane/fc2_amane_adapter)`）必须仍等于 `P5_C1_HOST_WITNESS.json` 记录的
> `adapter_tree_sha256`。若实现发现必须改 P5-C1 树才能完成兼容，**这是设计前提失效**，STOP，需要 authority amendment（第 2 节）。
> U2-12 的前置事实：R1 曾以“`*.py` 树哈希 + 允许 `__pycache__/*.pyc`”接受目录形态；Reviewer 的 `.pyc` PoC 已证明该规则不覆盖全部可执行字节（W2-12，设计期在 3.12.10 / 3.14.7 复现）。R2 因此**删除目录形态的接受**，U2-12 在设计层面**未被触发**（不存在需要降级的验证）。

### 5.4 Reviewer 的 security 复核问题（供 Design Review 的 Security Review Focus 使用）

1. 第 8.3 节的准入面是否**只有** exact pinned wheel 一种可执行形态；有无可绕过的路径（`sys.path` 中靠前的同名包、`sys.modules` 预置、同名 wheel 替换、符号链接、混合来源子模块、meta_path 抢占、目录形态的 `.pyc` / `.pyd` / `.pth`）？
2. **TOCTOU 已被明确裁决为 ACCEPTED SECURITY LIMITATION（L-C2-13 / 第 8.8 节威胁模型）**：zipimport 在进程生命周期内懒读取 wheel，校验只保证**准入时刻**的完整性，**不是**运行期不可变性；Reviewer 请复核该裁决与威胁模型的 Defended / Not Defended 划分是否诚实。
3. fail-closed 的错误模板是否有界、无路径泄漏、无秘密。

---

## 6. 设计期实证（Design-time Witness）

以下为设计者在本机直接执行的核对（2026-10-05；可复现脚本见施工计划附录）。它们是**设计期观测**，不是施工证据；施工证据由第 15 节 Evidence Gate 提供。

### 6.1 Amane 坐标（直接来自 upstream `sqzw-x/amane`，只读克隆）

| 名称 | tag | tag 对象 | peeled commit | release version | `requires-python` | `PLUGIN_API_VERSION` | 备注 |
|---|---|---|---|---|---|---|---|
| **A. v0.15.0** | `v0.15.0` | `3292c957a092f85ddde1ba7462ffe9813827f4f1` | `45dff2159369883e028a296d775a4598836c1ddd` | 0.15.0 | `>=3.14` | `"1"` | 最低版本目标（minimum version target） |
| 中间 | `v0.16.0` / `v0.16.1` | — / `85cf32fe…` | — / `786849daa4ac13a5d480b43ea60b78f1e994741b` | 0.16.x | `>=3.14` | `"1"` | 仅信息 |
| 中间 | `v0.17.0` | `65a3bd9377d2b60064164fc146acc4e8f1b5f22c` | `3c416618a9617be1c377694b1a150bf9821a7e6d` | 0.17.0 | `>=3.14` | `"1"` | 仅信息 |
| **B. 当前稳定版** | `v0.18.0` | `7d2190704fa1e3c0f7f86889111d12b9fa6701c8` | `0a8a731d7746bde5e8828d1eb74c7bd9752b42e4` | 0.18.0 | `>=3.14` | `"1"` | GitHub Release：非 draft、非 prerelease，`published_at = 2026-10-04T14:44:36Z`；带 Windows x64 / macOS 桌面包资产 |
| **C. 当前 main** | `origin/main` | — | `0a8a731d7746bde5e8828d1eb74c7bd9752b42e4` | 0.18.0 | `>=3.14` | `"1"` | 设计核对时**与 v0.18.0 同一 commit**（`git describe` = `v0.18.0-0-g0a8a731`） |
| `app-1.0.0` / `app-1.0.1` | `app-*` | `d45476e6…` / `8d3b0652…` | `2cc19dfd…` / `5556b8a6…` | 0.16.0 / 0.17.0 | `>=3.14` | `"1"` | **Android 客户端 APK 发布线**，不是插件宿主形态；**不是**“当前稳定版”的候选，排除出支持集 |

**“当前稳定版”的定义（冻结）**：GitHub Release 中**最新的、非 draft、非 prerelease、tag 形如 `v<semver>` 的** release；`app-*` 与 main 不参与。
实现期在 S1 开始时**重新核对一次**坐标并写入矩阵；矩阵在 S1 冻结，之后出现的新 release 不属于本包（由版本漂移门 §14 处理），不构成 blocker。

> C1 合同 §29 记录的“main = `e1a43d1…`”是当时的观察；本合同以设计时直接核对的 `0a8a731…` 为准，且**不依赖**“main 与稳定版不同”。
> 若实现期 main 与稳定版是同一 commit，E23 记为 `IDENTICAL_TO_STABLE`（见第 14 节），不得伪造为独立见证。

### 6.2 公共 API 差异（v0.15.0 -> v0.18.0；`git diff v0.15.0 v0.18.0 -- src/amane/{plugin,plugins,crawlers/models.py,net/errors.py,net/http.py}`；已读 diff）

| 项 | v0.15.0 | v0.18.0（= 当前 main） | 对 adapter 的影响（P5-C1 只用公共子集，I26） |
|---|---|---|---|
| `amane.plugin` 导出 | 基线 | 新增 `ConnectivityOutcome` / `ConnectivityStatus` / `SkipReason` / `SourceTrait` | 无：adapter 不使用 |
| `SourceDescriptor` | `multi_language: bool` | **`multi_language` 被 `traits: frozenset[str]` 取代**（含 `SourceTrait.{NEEDS_PARTIAL, MULTI_LANGUAGE, USES_FILE_HASH}`；未知 trait 被忽略并告警） | 无：adapter 两者都**不传**（C1 I26） |
| `FilmSourcePlugin` | `descriptor / configuration_model / build` | 同 | 无 |
| `FilmSourceProvider` | `fetch` | `fetch` + 非抽象 `check_connectivity()`（默认 `None`，宿主改为探测 `descriptor.urls[0]`） | 无：adapter **不覆盖**（避免 v0.15.0 缺类型；L-C2-06） |
| `PluginContext` | `source_id / http_client / web_client / data_dir` | **字段完全相同**；Factory 仍传共享 `HttpClient` 与 `HttpClient.web_client` | 无（共享 HTTP 生命周期保持，I3） |
| `SearchQuery` | 含 `raw_results` | **`raw_results` 被移除**；`partial_result` 注释语义更新 | 无：adapter 不读 |
| `FetchOptions` / `MediaMetadata` / `FilmActor` | 基线 | **字段无变化**（diff 仅 `SearchQuery`） | 无 |
| `FailureReason` | 基线 | 新增成员 `API_ERROR = "api_error"`；`CRAWLER_UNAVAILABLE` 注释扩展 | 桥按**结构化** `RequestError.reason` 分类；新成员落入“其它 -> `HttpTransportError`”桶（确定性）；由 E16 的枚举守卫覆盖 |
| `RequestFailure` | 基线 | 新增可选 `reason` | 无：adapter 不构造 `RequestFailure` |
| `net/errors._classify_text` | Cloudflare 判定为 `ray-id`+`cf-` -> `CLOUDFLARE_BLOCKED` | 先判 `_cf_chl_opt` -> `CLOUDFLARE_CHALLENGE` | 无：adapter **不解析宿主文本**（I8），映射走 Core 的结构化结果 |
| `WebClient.request` | 无 `max_attempts`；`max_retries` 次循环；**`max_retries=0` 时一次请求都不发**（L-04） | 新增 `max_attempts`；`max_retries` 明确为**总尝试次数**；**`0` 视为 1 次** | **允许的宿主差异 DIFF-02**（第 13.3 节）：L2 上界 `S×H` 在两版均成立（`H>=1`）；`H=0` 单列 |
| `WebClient` | — | 新增 `acquire(url)`、`same_origin_referer_hosts`（宿主按配置域名补 `Referer`）、`resolve_final_url`；移除 `BrowserClient` | 无：adapter 不用；请求头 `Referer` 差异属允许差异 DIFF-03 |
| `HttpClient` | 基线 | 新增按来源的浏览器回退（`get_html`）与 `for_source` | 无：桥直接用 `WebClient.request`，**不经** `HttpClient.get_html`（L-13） |
| `CrawlerFactory` 插件构建 | `_plugin_instances` 缓存；`PluginContext(source_id, http_client=self._http, web_client=self._http.web_client, data_dir)` | 统一 `_instances` 缓存；`PluginContext` 构造**相同**；provider 经 `_PluginProviderAdapter` 包装并新增 `check_connectivity` 转发 | 无 |
| `PluginManager` | `discover / validate_* / build_plugin_provider`；`multi_language_sources` 属性 | `multi_language_sources` **移除**；`builtin_descriptors()` 取代内联构造；未知 trait 告警 | 无：adapter 不调用宿主 `PluginManager` |
| `plugins/packaging.py`（`install_plugin_zip / install_plugin_path / purge_imported_plugin_modules / inspect_plugin_id / uninstall_plugin_tree`） | 基线 | **`git diff` 为空（逐字节相同）** | 安装 / 卸载 / purge 语义不变，是本合同第 8 / 11 节的宿主前提 |
| `api/routes/plugins.py`（install / reload / PATCH / DELETE） | 基线 | **`git diff` 为空** | 同上 |
| `app/runtime.py` | 基线 | 243 行变化（重建内部实现） | reload / install / uninstall 的**外部**行为（锁、`discover` + rebuild）不变；由 E11 / E12 真实验证 |
| `config/manager.py` | 基线 | +70 行（`BrowserConfig` / `use_browser` 迁移） | `PluginConfig`（`enabled`、`config: dict`、`extra="forbid"`）**不变** |
| Python 要求 | `>=3.14` | `>=3.14` | 同；宿主解释器一律 3.14.x |

### 6.3 其它设计期观测

| ID | 观测 | 方法 / 结果 |
|---|---|---|
| W2-01 | 宿主安装前会**导入**插件 | `install_plugin_zip` -> `inspect_plugin_id` 加载 staging 副本并调用 `candidate().descriptor()`；`ImportError` -> `ValueError("插件导入失败: …")`。因此 **Core 缺失时插件 zip 本身无法安装**（未提交到 `sources/`）；用户必须**先**让 Core 可被定位，再安装插件 |
| W2-02 | `purge_imported_plugin_modules` 只清 `amane_ext*` | `sys.modules` 中 `fc2_metadata_core*` **不会**被 reload 清理；Core 一经加载，同进程内常驻到重启（决定第 8.6 节的升级规则） |
| W2-03 | 插件文档明示 | “插件不能声明自己的 pip 依赖”；桌面版“第三方包不可用”（`docs/dev/plugins.md`）。即：zip **不能**声明依赖，宿主 **不会**安装依赖 |
| W2-04 | **冻结桌面宿主忽略 `PYTHONPATH`** | 在 Windows 解压的官方 `Amane-v0.18.0-windows-x64.zip`（`onedir/Amane.Server.exe`，Python 3.14.7，`sys.frozen == True`）上，用 `AMANE_DATA_DIR` 指向临时目录、放一个探针插件，启动时设 `PYTHONPATH=<dir>`：探针在发现期报告 `os.environ["PYTHONPATH"]` 已设置，但 `sys.path` **不含**该目录，`import ffcc_probe_dep` -> `ModuleNotFoundError` |
| W2-05 | **冻结桌面宿主上 wheel-on-`sys.path` 可用** | 同一探针改为 `sys.path.insert(0, <fc2_metadata_core-0.1.0-py3-none-any.whl>)`（zipimport）后 `import fc2_metadata_core` 与 `fc2_metadata_core.aggregation` 成功，且 `"httpx" in sys.modules == False`。**v0.18.0 与 v0.15.0 两个冻结 Windows 包均复现** |
| W2-06 | 现有 `pip wheel .` 产物**不是**“Core only” | 以 3.12 在 `fc2-organizer/` 上 `pip wheel . --no-deps`：wheel 含 `fc2_metadata_core`（40 个文件）**和 `fc2_organizer`（63 个文件）**——因为 `[tool.setuptools.packages.find] where=["src"]` 取到两个包。因此**不能把它当作 Core 分发物**；本合同要求专用的确定性构建器（第 10.2 节）。`pyproject.toml` 本身不改（U2-8） |
| W2-07 | Core 无资源文件 / 无 `__file__` 依赖 | `grep` `__file__ / importlib.resources / pkgutil / pkg_resources / get_data` 在 `src/fc2_metadata_core` 为空；Core 目录无非 `.py` 文件 -> 可 zipimport |
| W2-08 | Core import 面不需要第三方包 | 沿用 C1 W-03（`httpx` 等被阻断时 import 成功）；W2-05 在冻结宿主上再次确认（`httpx` 未被加载） |
| W2-09 | 现有 `pip wheel` 的 zip 字节依赖构建环境 | setuptools 产物含文件 mtime 与 deflate 流；不满足“同输入 -> 同字节”，需自建构建器并用 `ZIP_STORED`（第 10.3 节） |
| W2-10 | C1 见证测试把 adapter 树哈希与 Core 树哈希焊在 CLOSED 测试里 | `tests/amane_adapter/test_amane_host_witness_log.py` 断言 `adapter_tree_sha256 == tree_sha256(adapter tree)` 与 `core_tree_sha256 == tree_sha256(src/fc2_metadata_core)`；因此**任何对 adapter 树的字节改动都会破坏一个 CLOSED 测试**（决定第 9 节的 shim + LF 规范化字节同一的 `_impl/` 设计，U2-6 / U2-7） |
| W2-11 | （观察，**R2 不再依赖**）`pip install --target` 安装出的目录形态 Core 的 `*.py` 树哈希与 source tree 哈希及 C1 witness 的 `core_tree_sha256` 逐字相等（`6077cd6739424848137f2b8a1d6c37d20cc9cb3185cc94df07774169b3fda026`） | 该观察曾支撑 R1 的目录形态准入；R2 因 W2-12 删除目录形态准入，仅保留其作为构建期 traceability（E31-q） |
| W2-12 | **Reviewer 的 `.pyc` 绕过 PoC 在设计期复现** | 取设计期 wheel 的 `fc2_metadata_core/` 解压为目录形态 Core；Python 先生成真实的 `__pycache__/__init__.cpython-3x.pyc`（时间戳型）；用 `importlib._bootstrap_external._code_to_timestamp_pyc(code, 源文件 mtime, 源文件 size)` 生成**携带相同 mtime / size** 的恶意 pyc 覆盖之（payload = 写 sentinel 文件后继续原代码）。结果（**3.12.10 与 3.14.7 均**）：`tree_sha256`（C1 算法，仅 `*.py`）**前后相同**（前 12 位 `6077cd673942`）；新解释器 `import fc2_metadata_core` 后 **sentinel 存在，payload 已执行**。即 R1 的“`*.py` 树哈希 + 允许 `.pyc`”**不覆盖全部可执行字节** |
| W2-13 | wheel-only 准入原型（**不入库**）：zipimport 语义与拒绝 / 遮蔽 / 回滚（3.12.10 与 3.14.7 均通过） | 原型实现第 8.3 节算法：(a) 目录形态 Core（含恶意 pyc）在 `sys.path` 上、无 sidecar -> `UNVERIFIABLE`，`fc2_metadata_core` 不在 `sys.modules`，`sys.path` / `sys.modules` 不变；(b) 同目录 + 有效 sidecar -> wheel 被插入 `sys.path[0]` 且 `find_spec` 解析到 wheel（目录形态未被执行）；重复调用幂等（wheel 条目 1 个）；(c) 被篡改的同名 wheel -> `WHEEL_HASH`，状态不变；(d) `sys.meta_path` 上抢占的 finder -> 预解析即拒绝，`sys.path` 未被修改；(e) 仅在 wheel 进入 `sys.path` 后才抢占的有状态 finder -> 回滚，`sys.path[:] = before`，状态不变；(f) 本账户无权限创建符号链接（`OSError`）-> 实现测试须用 `os.lstat` 替身并记录 `symlink_privilege=false`。zipimport 语义：`spec.loader` 为 `zipimporter`，`loader.archive` == wheel 路径，`loader.prefix == ""`，`spec.origin == <archive>\fc2_metadata_core\__init__.py`，`spec.submodule_search_locations == [<archive>\fc2_metadata_core]`（归档内路径，非文件系统目录） |
| W2-14 | artifact 派生 DAG 无环且确定（**不入库**探针） | 以 `ZIP_STORED` 确定性 zip 实现 L0..L4：同输入两次构建的 bundle 字节相同；`COMPATIBILITY.json` 不含自身 / `SHA256SUMS` / bundle 哈希；`sha256sum -c` 通过且 `SHA256SUMS` 不列自身；改变 Part A 的状态只改变 L2–L4、不改变 L0 / L1（无回边）；若 `COMPATIBILITY.json` 内嵌 `SHA256SUMS` 哈希则重新计算后该哈希立即过期（不动点不可达），证明原设计的环 |
| W2-15 | R3 防御性探针（**不入库**；惰性 sentinel fixture，不执行任何 payload；3.12.10 与 3.14.7 均通过） | 原型实现第 8.3 节 2A..2E：(A) wheel **已在** `sys.path`、更靠前有惰性的不受支持 Core 目录包 -> 预解析（wheel-first）通过但**最终真实解析**命中惰性包 -> `REJECT`；`sys.path` 与入口相同、verified-wheel cache 条目被清除、惰性包未被导入；(B) wheel 已在 `sys.path[0]` -> 成功且未插入；(C) wheel 不在 -> 一次插入；重复调用幂等（wheel 条目恰好 1 个，第二次仍走 2E）；(D) 插入后才抢占的有状态 finder、入口无 cache 条目 -> 回滚后 `sys.path` 与 cache 均回到入口；(E) 同上但入口已有 cache 条目 -> 回滚后仍是**原对象**；(F) 惰性 `zipimporter` 子类 loader double -> `type(loader) is zipimporter` 拒绝，而 `isinstance` 会接受（探针同时打印两者） |

---

## 7. 兼容矩阵与兼容策略

### 7.1 兼容矩阵（冻结；`P5_C2_COMPATIBILITY_MATRIX.json` 的结构依据，第 14 节）

| 能力 | v0.15.0 | 当前稳定版 v0.18.0 | 当前 main | P5-C2 策略 |
|---|---|---|---|---|
| plugin discovery（`plugin.py` + `Plugin` + id==目录名 + `api_version == "1"`） | 基线 | 相同（`discover` 逻辑只增加未知 trait 告警） | 同稳定版 | **同一路径**；E08 在两版真实 `PluginManager.discover` 上验证 |
| descriptor | `multi_language: bool` | `traits: frozenset[str]` | 同稳定版 | adapter 只传 C1 §9 冻结字段，**不传** `multi_language` / `traits`；E08 断言 descriptor 的**适配器可控子集**两版逐字段相等 |
| FilmSource API | `fetch(query, options)` | 相同 + 非抽象 `check_connectivity` | 同稳定版 | 只实现 `fetch`；**不覆盖** `check_connectivity` |
| SearchQuery | 含 `raw_results` | 无 `raw_results` | 同稳定版 | 只读 C1 §10 冻结的字段；E15 在两版上驱动同一请求集 |
| MediaMetadata / FilmActor / FetchOptions | 基线 | 字段相同 | 同稳定版 | C1 §19 冻结映射不变；E15 逐字段字节等价 |
| config model | `PluginConfig{enabled, config}`；`configuration_model().model_validate(config.config)` | 相同 | 同稳定版 | 往返矩阵见第 12 节；两版**同一**期望 |
| install zip（`install_plugin_zip`） | 基线 | **逐字节相同的 `packaging.py`** | 同稳定版 | 单一 plugin zip；E07 / E12 |
| reload / purge | `purge_imported_plugin_modules` 清 `amane_ext*` | 相同 | 同稳定版 | E11：reload 后执行的是新代码；Core 不被 purge（第 8.6 节） |
| WebClient.request | 无 `max_attempts`；`max_retries=0` 零请求 | `max_attempts`；`0` -> 1 次 | 同稳定版 | adapter **只用** `method, url, headers, timeout, ok_statuses` 等 C1 已用关键字；**不传** `max_attempts`；差异 DIFF-02 |
| shared HTTP lifecycle | `PluginContext.web_client` = 共享 | 相同 | 同稳定版 | I3 / I4 不变；E17 在两版真实宿主上证明 provider 持有的是宿主的 `web_client` 对象（同一性） |
| Python requirement | `>=3.14` | `>=3.14` | `>=3.14` | 宿主验收一律 3.14.x（单一解释器版本，**每个宿主版本一个 venv**，因依赖锁不同） |
| 宿主形态 / 平台 | 见第 7.2 节二维支持坐标 | 同左 | — | 版本状态**不得**覆盖平台状态；平台状态由各自坐标的见证决定 |

### 7.2 兼容策略与支持坐标（冻结；Design Pre-Review R1：C2-DESIGN-R1-04）

**版本策略**（不变）：

```text
版本兼容目标                 = v0.15.0（最低版本目标，45dff215…）与 v0.18.0（当前稳定版，0a8a731d…）；**以下均为坐标级状态，不是版本全局状态**
(v0.18.0, frozen desktop | source host, Windows x64) = CONDITIONALLY_SUPPORTED（SC-02 / SC-04）  条件：E15 / E16 / E22 在该坐标 PASS（实现期）；否则该坐标 BLOCKED + 根因
current main                 = INFORMATIONAL COMPATIBILITY WITNESS（设计时 main == v0.18.0；不是 release contract）
中间版本 v0.16.x / v0.17.0   = UNVERIFIED（可选信息见证，E23b）；只可声明“适配器可控子集的 API 指纹与 v0.15.0 / v0.18.0 之一相同”
app-1.0.x（Android 客户端）  = OUT OF SCOPE（不是插件宿主）
```

**支持声明的坐标 = `(amane_version, host_form, platform)`（二维：版本 × 宿主形态 / 平台）。** 版本级状态**不得**覆盖、继承或替代平台 / 形态级状态：

| 坐标 ID | Amane 版本 | 宿主形态 | 平台 | 声明类别 | 角色 / 状态规则 |
|---|---|---|---|---|---|
| SC-01 | v0.15.0 | frozen desktop（官方 `Amane-v0.15.0-windows-x64.zip`） | Windows x64 | **deployment** | **必需**；E21 PASS -> `SUPPORTED` |
| SC-02 | v0.18.0 | frozen desktop（官方 `Amane-v0.18.0-windows-x64.zip`） | Windows x64 | **deployment** | **必需**；E22 PASS -> `SUPPORTED`，未 PASS -> `BLOCKED` |
| SC-03 | v0.15.0 | source host（`python -m amane.server`，Python 3.14.x venv） | Windows x64 | integration | **必需**；E21 PASS -> `SUPPORTED`（仅表示“集成兼容”，不是部署承诺） |
| SC-04 | v0.18.0 | source host（Python 3.14.x venv） | Windows x64 | integration | **必需**；E22 PASS -> `SUPPORTED`（同上） |
| SC-05 | main（`0a8a731d…`） | source host | Windows x64 | informational | 若 == 稳定版 commit -> `IDENTICAL_TO_STABLE`；否则 `INFORMATIONAL`，失败不阻塞 |
| SC-06 | v0.16.1 / v0.17.0 | source host | Windows x64 | informational（可选） | `UNVERIFIED` 或 `INFORMATIONAL` |
| SC-07 | v0.15.0 / v0.18.0 | frozen desktop（macOS `.app.zip`） | macOS | — | **`UNVERIFIED`**；不属于本包支持声明 |
| SC-08 | v0.15.0 / v0.18.0 | source host | Linux | — | **`UNVERIFIED`**；不属于本包支持声明 |
| SC-09 | v0.15.0 / v0.18.0 | Docker 镜像 | Linux | — | **`UNVERIFIED`**；本环境无 Docker，无法可靠建立证据，**不为扩大声明而增加环境依赖**；不属于本包支持声明 |

* **SC-01 / SC-02（Windows x64 frozen desktop）= 必需的部署支持坐标**；**SC-03 / SC-04（source host）= 必需的集成兼容坐标**；**macOS / Linux / Docker（SC-07..SC-09）= UNVERIFIED，不在 P5-C2 支持声明内**（不得被任何顶层“SUPPORTED”字样覆盖）。
* 声明用语冻结：`COMPATIBILITY.json`、`INSTALL.zh-CN.md`、HANDOFF 对外只能说“在 `SC-01..SC-04` 上经验证兼容”；**不得**写“支持 v0.15.0 / v0.18.0”“v0.18.0 SUPPORTED”“v0.18.0 CONDITIONALLY SUPPORTED”这类脱离平台 / 形态的概括，也不得写“支持 Docker / macOS / Linux”。顶层摘要可以写“version compatibility target = v0.15.0 and v0.18.0”，但必须**紧接着**写明“support claim is coordinate-scoped, not version-global”。
* 状态词表：`SUPPORTED` / `CONDITIONALLY_SUPPORTED`（设计期默认，仅 SC-02 / SC-04）/ `BLOCKED` / `UNVERIFIED` / `INFORMATIONAL` / `IDENTICAL_TO_STABLE`；一致性规则由 E24 的 JSON 自洽测试机检（第 14 节）。
* 若日后有可靠的 Docker / Linux / macOS 证据，经新的见证加入对应坐标并重新运行版本漂移门（第 14.2 节），不需要改本合同的其它部分。

### 7.3 同一 artifact 与版本分支

* **同一 artifact 同时跑在 v0.15.0 与 v0.18.0：是。** 单一 plugin zip、单一 Core wheel；**不需要 version-specific branch / 不允许**（U2-9）。
* **生产代码内不使用 feature detection。** 原因：C1 I26 已把 adapter 限定为 v0.15.0 与 main 的**公共子集**；矩阵表明无需分支。
* **允许 feature detection 的场景与依据**：仅在**见证 / 测试工具**内，用于**记录**宿主 API 指纹（不是改变行为）；依据必须是**公共 API 的结构**：
  `amane.plugin` 的导出名、`inspect.signature(WebClient.request).parameters`、`dataclasses.fields(SearchQuery)`、`SourceDescriptor.model_fields`、`FailureReason` 成员枚举。
* **将来若确实需要在生产代码里分支**：只允许依据上述公共 API 的**属性 / 签名存在性**，并走合同 amendment（U2-9）；本包不引入。
* **禁止**依据：异常文本 / `error_detail` 解析；`amane.__version__` / `pyproject` 版本字符串比较；对私有模块（`amane.plugins.packaging` 以外的内部、`_session`、`_limiters` 等）的 monkeypatch / 读取；`sys.modules` 嗅探宿主形态。

### 7.4 机器检查的宿主 API 指纹

`tools/amane_api_manifest.py`（C1，不改）输出 v0.15.0 清单；P5-C2 为 **v0.18.0**（及可选的中间 / main 坐标）生成同格式清单，并新增比较工具输出**“适配器可控子集指纹”**：
adapter 实际使用的名字 / 关键字（由 C1 `test_amane_api_manifest.py` 的使用清单决定）在各宿主版本上的存在性与签名。**该子集指纹在两个必需版本上必须相等**，否则兼容声明失效（E04）。

---

## 8. Core 最终供给（冻结；P5-C2 最重要的 authority 决策）

### 8.1 必须回答的问题与答案

| 问题 | 答案 |
|---|---|
| 插件 zip 自身能否声明 pip 依赖？ | **不能**（宿主文档明示；W2-03） |
| Amane `install_plugin_zip` 会不会安装依赖？ | **不会**：只解压并**导入**（W2-01） |
| 最终安装流程？ | 第 8.4 节（先放 Core wheel，再装插件 zip；两者都由同一个官方 release bundle 提供） |
| missing Core 的用户体验？ | 第 8.7 节（固定模板、无部分注册、无回退到 Amane 内置 FC2 爬虫） |
| 升级 Core 的流程？ | 第 8.6 节 |
| plugin 与 Core 的版本兼容关系？ | **精确配对**（lockstep）：每个 plugin 版本固定一个 Core `(version, wheel sha256)`（第 8.3 节） |
| 是否 vendor？ | **否**（U2-2）。Core wheel 是**独立文件**，不在 plugin zip 内 |

### 8.2 候选方案与裁决（审计记录）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. 独立 `pip install fc2-metadata-core` 到宿主解释器 | **否（R2：不作为被接受的 Core 来源）** | 目录形态无法用简单、确定、跨环境的规则覆盖全部可执行字节（`.pyc` PoC，W2-12）；桌面冻结包没有可写 / 可用的解释器环境，且忽略 `PYTHONPATH`（W2-04）；宿主文档不承诺。`pip` 仅用于准备宿主 venv，不是信任来源 |
| B. 项目 wheel（现有 `pip wheel .`） | **否** | 产物含 `fc2_organizer`（W2-06），不是 Core only；字节不确定（W2-09）；改 `pyproject.toml` 违反 U2-8 |
| C. installer-assisted（自动 pip） | **否** | 引入新的可执行安装器 / 网络 / 包管理器依赖，扩大攻击面；冻结宿主无 pip |
| D. 把 Core 目录放进 plugin zip（vendor） | **否（U2-2）** | 违反“不 vendor”；需要 authority amendment，本包不申请 |
| E. 向 `{data_dir}` 写入时由插件自行解压 Core | **否** | adapter 写文件违反 I14 / U2-3 |
| **F. Core sidecar wheel + 随包 shim locator（zipimport）** | **采纳** | 唯一在冻结桌面宿主上被实测可行的方式（W2-05）；Core 保持独立分发物；adapter 不写文件；pin 做到精确配对与完整性校验；同一 artifact 适配所有宿主形态 |
| G. 允许 pip / 源码 / editable 与 sidecar 并存 | **否（R2）**：目录形态 Core 即使字节完全正确也 `UNVERIFIABLE`；有效 sidecar 存在时 sidecar 优先，目录形态 Core **不被执行** | 避免为目录形态引入 pyc / `sys.pycache_prefix` / 优化级别 / `co_filename` 等验证体系；源码宿主同样使用 sidecar wheel（host form 与 Core supply form 是两个维度） |

### 8.3 shim locator 的冻结行为（`_ffcc_locator.py`；纯 stdlib；3.11-3.14 语法；Risk C 信任边界的**准入规则**；Design R2：exact pinned wheel only）

**总原则**：Core 唯一被接受的执行形态是 **exact pinned wheel**（以 zipimport 加载的那一个 `.whl` 文件）。其它一切来源——pip 安装 / 已解压（含 `pip install --target`）/ editable / 源码检出 / `PYTHONPATH` 与 `sys.path` 上的目录 / `.pth` / 任何非 zipimport loader——
一律是 **UNSUPPORTED CORE ORIGIN -> fail closed（`UNVERIFIABLE_TEMPLATE`）**，**即使其字节恰好完全正确**，且在**任何 import 之前**拒绝。禁止“已经导入 / 有发行元数据 / 是源码检出”而免于校验；禁止 purge / 热切换 Core。

**为什么删除目录形态（P5-C2-DESIGN-R-01）**：R1 以“`*.py` 树哈希 + 允许 `__pycache__/*.pyc`”接受目录形态。Reviewer 证明了：把 `__pycache__/*.pyc` 替换为携带**源文件相同 mtime / size** 的恶意 pyc，`*.py` 树哈希不变，payload 在 import 时执行。
设计期已**复现**（W2-12：3.12.10 与 3.14.7，树哈希前 12 位 `6077cd673942` 不变，payload 被执行）。要覆盖目录形态的全部可执行字节，必须设计 pyc 验证体系（timestamp / hash-based pyc、`sys.pycache_prefix`、优化级别、`co_filename` 规范化、3.12 / 3.14 差异、懒导入、已加载模块），复杂且易遗漏。
wheel 形态不需要：整个 `.whl` 文件的 sha256 覆盖其中**每一个字节**；zipimport 既不读写 `__pycache__`，也不加载 `.pyd`；构建器只会产出 `*.py` + dist-info（E31-q）。

`_ffcc_pin.py`（构建期生成，**只含字面量**）：

```text
PIN_SCHEMA_VERSION = 1
CORE_DIST_NAME     = "fc2-metadata-core"
CORE_VERSION       = "<pyproject [project].version>"
CORE_WHEEL_NAME    = "fc2_metadata_core-<CORE_VERSION>-py3-none-any.whl"
CORE_WHEEL_SHA256  = "<64 hex>"                                   # 准入的唯一完整性依据
CORE_TREE_SHA256   = "<tree_sha256(src/fc2_metadata_core)>"       # 仅用于构建期 traceability 与 E31-q；locator 不使用、不实现树哈希
SIDECAR_DIRNAME    = "_ffcc_core"
```

**Verified root（只有 wheel 形态；R-06 的 zipimport 精确语义，W2-13 在 3.12.10 / 3.14.7 实测）**：verified root = **那一个 `.whl` 归档文件的路径**。对被验证的 wheel：`type(spec.loader) is zipimport.zipimporter`（**精确类型判据，不是 `isinstance`**；zipimporter 的子类或任何其它 loader 实现一律不被信任；本合同**不**支持任何其它具体标准库 loader，若将来必须支持须经合同 amendment 逐个列出），其 `archive` 规范化（`os.path.normcase(os.path.realpath(·))`）后等于 verified wheel 的规范化路径，`prefix == ""`；
`spec.origin = <archive><os.sep><归档内成员路径>`（如 `…\fc2_metadata_core-0.1.0-py3-none-any.whl\fc2_metadata_core\__init__.py`）；包的 `spec.submodule_search_locations` 是**归档内**路径列表 `[<archive><os.sep>fc2_metadata_core]`（**不是文件系统目录**，不得用“恰好一个目录”描述）。
所有 `fc2_metadata_core` / `fc2_metadata_core.*` 的模块必须满足：`__spec__` 存在，`type(__spec__.loader) is zipimport.zipimporter`（精确类型）且 `archive` 规范化后**等于同一个 verified wheel**，`__spec__.origin` 以 `<archive><os.sep>` 开头（**同一 verified root**）。任何不满足（目录来源 / 非 zipimport loader / 缺失 `__spec__` / 命名空间包 / 不同 archive）= 不同根 / 无法验证。

**wheel 证明（对 sidecar wheel 与对已加载 Core 所属 wheel 使用同一证明）**：`os.lstat` 为**普通文件**（非目录 / 非符号链接 / 非其它特殊文件）；文件名 == `CORE_WHEEL_NAME`；大小 `<= 16 MiB`；`sha256(整个文件) == CORE_WHEEL_SHA256`。

`ensure_core(pin, module_file)` 按固定顺序执行（**无网络、无写文件、无子进程、不 import Core**；只做 `lstat` / 读 wheel 做哈希 / 读 `sys.modules` / `sys.meta_path` / 修改 `sys.path`）：

0. **入口快照（A-01 / A-02；先于一切 probe）**：`ensure_core` 一进入就取得 `entry_sys_path = list(sys.path)`；在**已确定 sidecar wheel 路径之后、第一次 `find_spec` / `PathFinder` probe 之前**取得 `entry_cache`
   = `sys.path_importer_cache` 中所有规范化路径等于该 wheel 的键及其值（路径推导只做字符串与 `lstat`，**不**触发任何 probe）。**不得**等预解析之后再取快照。
1. **已加载**：`sys.modules` 已含 `fc2_metadata_core`：取其 `__spec__.loader.archive` 作为候选 wheel（要求 `type(__spec__.loader) is zipimport.zipimporter`），执行**wheel 证明**，并要求所有 `fc2_metadata_core*` 模块同根（见上）。通过 -> 接受（**不修改任何状态**）；不通过（含目录形态 / 非精确 zipimporter / 错误版本 / 被篡改的同名 wheel / 混合来源 / 无法定位）-> `ImportError(RESTART_TEMPLATE)`。
   **措辞冻结（A-03）**：已加载 Core 的证明 = **current-origin + current-artifact proof**——当前模块 origin 指向那个确切的 wheel 路径，且该 wheel 文件的**当前**字节符合 pin；它**不是** historical executed-byte proof，**不**证明此前已执行过的全部字节就是当前 wheel 的字节（这属于已接受的运行期可变性限制，见威胁模型 N-03 / L-C2-13；不改变准入算法）。
   loaded Core != pinned Core 一律是 RESTART / PIN MISMATCH；**不 purge、不热切换**。
2. **sidecar**：由 `module_file`（shim 的 `__file__`）向上逐级查找第一个满足 `p.name == "sources" and p.parent.name == "plugins"` 的目录 `p`，`data_dir = p.parent.parent`
   （同时覆盖 `sources/.staging/<x>/` 的安装前检查阶段与 `sources/ffcc.fc2-metadata/` 的正式加载阶段；找不到 -> “无 sidecar”，不报错）。`sidecar = data_dir / "plugins" / "_ffcc_core"`：
   * 目录不存在 -> “无 sidecar”；
   * 存在但**不含**名为 `CORE_WHEEL_NAME` 的条目：若含其它 `fc2_metadata_core-*.whl` -> `ImportError(WHEEL_VERSION_MISMATCH_TEMPLATE)`，否则“无 sidecar”；
   * 含名为 `CORE_WHEEL_NAME` 的条目 -> 依次执行 2A..2E（**唯一成功规则：NO SUCCESS RETURN UNTIL ACTUAL CURRENT RESOLUTION PROVES THE EXACT PINNED WHEEL**；无论 wheel 原本是否已在 `sys.path`，都必须执行 2E）：
     * **2A 入口快照**：已在第 0 步取得（`entry_sys_path`、`entry_cache`）。
     * **2B wheel 证明**：精确文件名、普通文件、非符号链接、大小上限、整个 wheel 的 `sha256 == CORE_WHEEL_SHA256`；失败 -> `ImportError(WHEEL_HASH_MISMATCH_TEMPLATE)`。
     * **2C 预解析（防御性；不修改 `sys.path`）**：按 `sys.meta_path` 的顺序逐个询问：`importlib.machinery.PathFinder` 以 `find_spec("fc2_metadata_core", [wheel] + list(sys.path))` 解析（“假设 wheel 位于最高优先级时会得到什么”），其它 finder 以 `find_spec("fc2_metadata_core", None)` 询问；取**第一个**非 `None` 的 spec。
       该 spec 必须满足 verified root 条件（`type(loader) is zipimporter`、`archive` == 该 wheel、origin 与包的 `submodule_search_locations` 均在该归档内）；否则 `ImportError(UNVERIFIABLE_TEMPLATE)`。**预解析通过不是最终准入。**
     * **2D 建立优先级（**唯一冻结行为：不重排、不移动、不删除任何已存在的 `sys.path` 条目**）**：
       若该 wheel（规范化路径）**不在** `sys.path` 中 -> `sys.path.insert(0, wheel)`（**至多一次**）；
       若该 wheel **已**在 `sys.path` 中（无论位置）-> **不插入、不重排、不提升**。**不得**因“wheel 已在 `sys.path` 中”而返回成功——直接进入 2E。
     * **2E 最终真实解析（A-01；两个分支都必须执行）**：用**实际的当前 import 解析** `importlib.util.find_spec("fc2_metadata_core")`（此时的真实 `sys.meta_path` 与真实 `sys.path`）独立确认：`type(spec.loader) is zipimport.zipimporter`；`spec.loader.archive` 规范化后 == 该 verified wheel；`spec.origin` 在该归档内；包的 `spec.submodule_search_locations` 的每一项都等于 `<archive><os.sep>fc2_metadata_core`（归档内路径）。
       任一不满足（例如已存在于 `sys.path` 的 wheel 之前还有一个不受支持的 Core 来源）-> **回滚（见下）并 `ImportError(UNVERIFIABLE_TEMPLATE)`**；**不**尝试把 wheel 提升到更高优先级（唯一行为 = fail closed，不留给 Developer 选择）。
     * 只有 2E 通过才返回成功。
3. **无有效 sidecar 且 Core 未加载**：`importlib.util.find_spec("fc2_metadata_core")`：`None` -> **什么也不做，不抛出**（随后 `_impl.plugin` 顶层 import 失败，由 **P5-C1 `_core_gate` 产生 §22 冻结消息**，第 8.7 节）；
   非 `None`（目录 / pip / editable / 源码 / 其它 loader）-> `ImportError(UNVERIFIABLE_TEMPLATE)`，**在任何 import 之前**拒绝（`find_spec` 对目录 finder 不执行包代码）；**不修改任何状态**。
4. 成功路径的副作用上限：**至多一次 locator-owned `sys.path` 插入**（仅当 wheel 原本不在 `sys.path`）；重复调用幂等（wheel 已在 `sys.path` 时不插入，但**仍执行 2E**）；已加载且证明通过的 Core **不修改 `sys.path`**；locator **永远不**触碰 `sys.modules`。**任何成功返回之前都必须有 2E（或第 1 步）的最终证明；不存在“wheel 在 `sys.path` 中 -> 立即成功”的路径。**

**失败路径的状态保证（P5-C2-DESIGN-R-03 + R2-A-02；由 E31-l / E31-n 机械验证）**：从**入口快照**起，任何 FAIL（含 2B / 2C / 2D / 2E 的失败，以及 2C 的 probe 可能已经造成的 importer-cache 变化）都执行**回滚**：

```text
sys.path[:] = entry_sys_path                 # 同一个 list 对象，逐元素还原；不触碰原本就存在的相同条目
对 sys.path_importer_cache 中规范化路径 == verified wheel 的键（仅此一类，不承诺恢复全局缓存的其它条目）：
    入口时不存在 -> 失败后删除（由 locator / probe 新创建）
    入口时已存在 -> 失败后保持入口时的原对象 / 原状态（若被替换或移除则还原）
sys.modules：locator 从未触碰；失败后 fc2_metadata_core* 的键集合与对象身份 == 入口
```

即每一个 FAIL 之后：`sys.path` **逐元素等于**入口状态（同一 list 对象）；`sys.modules` 中 `fc2_metadata_core*` 的对象身份不变；verified-wheel 的 importer-cache 条目 == 入口状态；Core 未被导入。
**不承诺**恢复整个解释器的 `sys.path_importer_cache`（与本 locator 无关的任意条目不在保证范围内）。预解析使绝大多数 FAIL 在尚未修改 `sys.path` 时发生；2E 失败（含“wheel 已在 `sys.path` 但真实解析不是它”）同样走上述回滚。

shim 的固定模板（有界、无密钥、无绝对路径、无外部数据的 `repr`；`<>` 内为构建期固定字面量）：

```text
RESTART_TEMPLATE                : "FC2 Metadata Core 已加载的版本与插件不配对（或无法验证）：请先卸载旧版插件并重启 Amane，再安装与之配对的新版（需要 Core <CORE_VERSION>）"
UNVERIFIABLE_TEMPLATE           : "FC2 Metadata Core 的来源不受支持或无法验证（已拒绝加载）：请把官方发布包中的 <CORE_WHEEL_NAME> 放入 <Amane 数据目录>/plugins/_ffcc_core/，不要使用 pip / 源码 / editable 形态的 Core"
WHEEL_VERSION_MISMATCH_TEMPLATE : "FC2 Metadata Core 随附包版本与插件不配对：请在 <Amane 数据目录>/plugins/_ffcc_core/ 中放入 <CORE_WHEEL_NAME>"
WHEEL_HASH_MISMATCH_TEMPLATE    : "FC2 Metadata Core 随附包校验失败（sha256 与插件配对记录不一致）：请重新获取官方发布包中的 <CORE_WHEEL_NAME>"
```

**host form 与 Core supply form 是两个维度**：源码运行的 Amane（SC-03 / SC-04）**并不要求** Core 以 editable 形式存在，同样使用 sidecar wheel（`AMANE_DATA_DIR/plugins/_ffcc_core/`）。`pip` 只可用于准备宿主 venv 依赖 / 构建工具，**不是** locator 的信任来源。

**设计期证据**：W2-12（`.pyc` PoC 复现）、W2-13（wheel-only 准入原型：zipimport 语义、拒绝目录形态、遮蔽、回滚）。原型与探针**不进入仓库**，复现命令见施工计划附录。

### 8.4 最终安装流程（普通用户，按文档可从零成功）

官方 **release bundle**（第 10 节）同时包含 plugin zip、Core wheel、校验清单与安装说明。

```text
1. 打开 Amane 的数据目录（桌面版托盘「打开数据目录」）。（Docker 的 `/data` 卷同理，但 **Docker 为 UNVERIFIED / informational：不在本发布验收覆盖范围内**，见第 7.2 节 SC-09。）
2. 在其下创建文件夹 plugins/_ffcc_core/（若 plugins/ 不存在则一并创建），把 bundle 中的
   fc2_metadata_core-<ver>-py3-none-any.whl 复制进去。（核对 SHA256SUMS 为可选建议，locator 会在加载时强制校验。）
3. 在 Amane「管理 → 插件」上传 bundle 中的 ffcc.fc2-metadata-<ver>.zip。成功后插件即出现在列表，无需重启。**运行期间不要替换或删除 sidecar wheel**（见第 8.8 节：校验只保证准入时刻的完整性）。
4. 在「设置 → 影片刮削 → 内容路由」中，把 ffcc.fc2-metadata 加入 FC2 内容类型的来源列表（P5-C1 / Amane 的既有机制）。
5. 在「管理 → 插件」中按需修改配置（第 12 节）。
```

* **不要用 `pip install` / 解压 / editable / 源码目录提供 Core**：这些目录形态不被接受（`UNVERIFIABLE_TEMPLATE`）。源码宿主（SC-03 / SC-04）同样使用 sidecar wheel；`pip` 只可用于准备宿主 venv 依赖。Docker 步骤（若出现在文档中）为 **UNVERIFIED / informational — 不在本发布验收覆盖范围内**。
* 顺序要求来自 W2-01：**Core 必须先到位，再装插件**；否则第 3 步以可读的 422（见第 8.7 节）失败，**不会**留下半装状态（宿主在 `inspect` 失败时不提交目录）。

### 8.5 plugin 与 Core 的配对关系

* plugin 版本 = C1 `PLUGIN_VERSION`（由构建器从 `_settings.py` 以 AST 读取，**不 import**）。
* Core 版本 = `pyproject.toml [project].version`（`tomllib` 读取，不改文件）。
* **Core 发布台账** `adapters/amane/release/core_release_ledger.json`：`{version -> core_tree_sha256, wheel_sha256}`。构建器**拒绝**“同一 Core 版本、不同 tree 哈希”（即：改了 Core 源码就必须 bump Core 版本）——这使“以版本判断配对”可靠（第 8.3 节；真正的完整性依据是**整个 wheel 的 sha256**，版本只是人类可读的配对标签；`CORE_TREE_SHA256` 仅用于构建期 traceability）。
* 一个 plugin zip 只配对**一个** Core wheel（精确 pin）。要同时支持多个 Core 版本不在本包范围。

### 8.6 升级流程

| 变更 | 流程 | 重启？ |
|---|---|---|
| 仅 plugin 升级（pin 不变） | 「管理 → 插件」覆盖上传新 zip（宿主整棵替换并 rebuild） | **否**（W2-02：`amane_ext*` 被 purge；Core 常驻且配对相同） |
| Core 升级（pin 变化） | 先在「管理 → 插件」卸载旧插件 -> **重启 Amane**（清掉内存中的旧 Core） -> 把新 wheel 放入 `plugins/_ffcc_core/`（旧 wheel 可保留或删除；locator 只认 pin 指定的文件名） -> 上传新 plugin zip | **是** |
| 误操作：新 plugin 但旧 Core 在内存 | 安装被拒绝并给出 `RESTART_TEMPLATE`（422）；按上一行流程操作 | 是 |
| 误操作：新 plugin 但 sidecar 里只有旧 wheel | `WHEEL_VERSION_MISMATCH_TEMPLATE` | 否 |

> 设计者**拒绝**“locator 在检测到 pin 变化时自行 purge `fc2_metadata_core*` 并热切换”：会在同进程内并存两代 Core 对象（在途任务仍持旧代），收益（Core 极少升级）小于风险。作为拒绝方案记录，Reviewer 可否决。

### 8.7 缺失 Core 的用户体验（冻结）

| 情形 | 行为 |
|---|---|
| 无 sidecar、Core 不可 import（桌面用户忘记第 2 步） | locator 不抛；`_impl.plugin` 顶层 import 失败；**P5-C1 §22 冻结消息**经宿主呈现：安装时 `ValueError("插件导入失败: FC2 Metadata Core 未安装或版本不兼容：请在 Amane 所在的 Python 环境中安装 fc2-metadata-core（缺失模块：fc2_metadata_core）")`（HTTP 422）；发现期进入 `failures`；**无部分注册**；**不回退**到 Amane 内置 FC2 爬虫 |
| sidecar 版本 / 哈希不配对 | 第 8.3 节固定模板（`WHEEL_VERSION_MISMATCH_TEMPLATE` / `WHEEL_HASH_MISMATCH_TEMPLATE`；比 P5-C1 消息更具体） |
| 目录形态 Core（pip / 已解压 / editable / 源码 / `PYTHONPATH` 目录；**即使字节完全正确**）且无有效 sidecar | `UNVERIFIABLE_TEMPLATE`（fail closed，在任何 import 之前；**不**回退到“反正能导入就接受”） |
| 进程内已加载的 Core 不是（或无法证明是）来自同一个 exact pinned wheel（含目录形态 / 混合来源 / 被篡改的同名 wheel） | `RESTART_TEMPLATE`（fail closed；不 purge、不热切换） |
| Core 以 exact pinned wheel 加载但缺少 P5-C1 要求的公共名字（按 exact pin 不应发生） | P5-C1 §22（`ImportError` 同一模板，作为安全网保留） |

> 取舍（如实）：桌面用户在“忘记第 2 步”时看到的是 P5-C1 冻结消息（“请在 Amane 所在的 Python 环境中安装”），对桌面用户不够友好。
> 这是为了**不改动** P5-C1 的 `_core_gate` 与其 CLOSED 测试（U2-6 / U2-7）所做的有意取舍；`INSTALL.zh-CN.md` 第 1 节以显著位置写明“桌面版请使用 sidecar 目录，不要 pip”。记为 L-C2-03。

### 8.8 Threat Model（冻结；P5-C2-DESIGN-R-02）

**保证的性质（精确）**：**admission-time integrity guarantee**——在 locator 准入的那一刻，将被导入的 Core 是 pin 指定的那一个 wheel 的全部字节；**不是** runtime immutability guarantee。

**Defended（本设计防御）**：

```text
D-01 wrong release artifact          用错发布物（plugin 与 Core 不是同一 bundle）
D-02 wrong Core version              wheel 文件名 / 版本与 pin 不符
D-03 wrong Core artifact             任意一个字节与 pin 的 wheel 不同（整个 wheel 的 sha256）
D-04 static tampering before admission  准入之前对 wheel 的静态篡改
D-05 same-name wrong wheel           文件名相同、内容不同的 wheel
D-06 symlink substitution            符号链接冒充 wheel
D-07 directory substitution          目录冒充 wheel；以及任何目录形态 Core（pip / 解压 / editable / 源码 / PYTHONPATH）——**不接受、不执行**
D-08 shadowing                       sys.path 上更靠前的同名包 / sys.meta_path 上抢占的 finder（预解析与再验证拒绝）
D-09 mixed module roots              已加载的 fc2_metadata_core.* 来自不同根 / 不同 wheel / 目录
D-10 unverifiable preloaded Core     进程内预先加载的、来源无法证明为 exact pinned wheel 的 Core（RESTART）
D-11 executable bytes outside *.py   目录形态中的 .pyc / .pyd / .so / .pth 等：通过“不接受目录形态”整体消除
D-12 accidental / malicious replacement detectable by pinned bytes  在准入时刻可由 pin 的字节检测到的替换
```

**Not Defended（本设计不声称防御；如实）**：

```text
N-01 attacker who can modify the plugin tree + the pin + the sidecar wheel together（同一信任域；pin 不是发布者身份）
N-02 attacker who already controls the Amane process memory / interpreter / sys.meta_path hooks installed earlier
N-03 attacker who modifies the ADMITTED wheel AFTER verification —— 包括此后整个进程生命周期内的 lazy import
     （zipimport 在进程生命周期内按需读取该 wheel；这不是“哈希与导入之间的一个很小的窗口”；**因此已加载 Core 的证明是 current-origin + current-artifact proof，不是 historical executed-byte proof**，A-03）
N-04 compromise of the release publishing channel / supply chain（无签名）
N-05 Python 启动期钩子（sitecustomize / .pth / PYTHONSTARTUP 类）与同进程内的其它插件（均为同一信任域内的任意代码）
N-06 恶意的 Amane 宿主本身
```

**Non-claims（不得被文档 / 测试 / HANDOFF 暗示）**：

* **SHA-256 pin = integrity / exact-pairing evidence**，**不是** publisher authenticity，**不是**数字签名，**不是** runtime anti-tamper。
* 若未来需要 publisher authenticity：signed manifest / 签名属于**未来增强，不在本包范围**。
* **loaded-Core proof = current-origin + current-artifact proof**（当前 origin 指向确切 wheel 路径 + 该 wheel 的**当前**字节符合 pin），**不是** historical executed-byte proof；不声称已执行过的全部历史字节等于当前 wheel 字节（N-03 / L-C2-13 的组成部分，不改变准入算法）。
* **L-C2-13 = ACCEPTED SECURITY LIMITATION**（裁决：接受，不设计消除方案；理由：zipimport 懒读取是宿主 / 语言机制，消除它需要把 Core 载入内存后自定义 loader，等于重写导入体系，且对已拥有数据目录写权限的攻击者收益有限——其本已可修改插件树与 pin，N-01）。
* 因此：官方安装文档**必须**写明“**不要在 Amane 运行期间替换或删除 sidecar wheel**”；Core 升级**严格**按 `uninstall -> restart -> replace artifact -> install`（第 8.6 节）。**不声称** locator 能阻止运行期间 wheel 被替换。

---

## 9. 最终 Artifact 的包结构（冻结）

### 9.1 plugin zip

```text
ffcc.fc2-metadata/                        ← 唯一顶层文件夹（= 插件 id）
  plugin.py                               ← shim（C2 新增；adapters/amane/shim/plugin.py）
  _ffcc_locator.py                        ← C2 新增（adapters/amane/shim/_ffcc_locator.py）
  _ffcc_pin.py                            ← 构建期生成（只含字面量）
  _impl/
    plugin.py _core_gate.py _settings.py _number.py _bridge.py _runtime.py _outcome.py
                                          ← LF 规范化字节，派生自 adapters/amane/fc2_amane_adapter/*.py，无 __init__.py
```

shim `plugin.py` 的全部内容（冻结形状；Developer 不得增加逻辑）：

```text
from ._ffcc_locator import ensure_core
from . import _ffcc_pin
ensure_core(_ffcc_pin, __file__)
from ._impl.plugin import Plugin   # noqa: E402  —— 宿主要求模块字典中存在名为 Plugin 的类
```

### 9.2 不变量

* **I-C2-1（normalized-byte identity）**：`_impl/` 内 7 个文件的内容是 `adapters/amane/fc2_amane_adapter/*.py` 的 **LF 规范化字节**（`\r\n -> \n`，与 P5-C1 见证使用同一规范化）；`tree_sha256(_impl)`（与 P5-C1 witness 的 `tree_sha256` 使用同一 `CRLF -> LF` 规范化）`== P5_C1_HOST_WITNESS.json.adapter_tree_sha256`。**这是“规范化字节同一”，不是“磁盘原始字节逐位相同”**（autocrlf 不同的检出得到同一结果）。
* **I-C2-2**：zip **不含** `fc2_metadata_core` 的任何文件；zip 中任何 `.py` 内容不得含 Core 的源码文件之一的字节（对 Core 每个文件做“整文件包含”扫描，E18）。
* **I-C2-3**：shim 只含上述三个 C2 文件；`_ffcc_locator.py` 不 import `amane`、`pydantic`、`fc2_metadata_core`、`httpx`、`requests`、网络 / 子进程模块；无 `open(..., "w")` / `Path.write_*` / `os.makedirs` / `shutil` 写入。
* **I-C2-4**：宿主要求的唯一入口契约不变：`plugin.py` 顶层存在 `Plugin`，`descriptor().id == "ffcc.fc2-metadata"`，`api_version` 默认 `"1"`。
* **I-C2-5**：`_impl` 以 namespace 子包（无 `__init__.py`）形式随根包 `amane_ext_ffcc_d_fc2_h_metadata` 加载；`purge_imported_plugin_modules` 清理 `amane_ext*` 即清理全部 shim 与 `_impl` 模块（E11 / E12 验证无陈旧模块）。

### 9.3 P5-C1 缺失 Core 合同在 artifact 中的有效性

P5-C1 §22 的消息、`translate_core_import_error` 与 H-05 的断言**原样保留**；shim 的新模板只在 sidecar 存在却不配对 / Core 以另一版本在内存这两类**P5-C1 没有覆盖**的情形出现。
H-05 的等价物（Core 完全缺失）在 artifact 上产生与 P5-C1 **相同**的消息，由 E13 断言。

---

## 10. 最终分发物（Release Bundle）

### 10.1 清单

| 文件（bundle 内） | 内容 |
|---|---|
| `ffcc.fc2-metadata-<plugin_version>.zip` | plugin zip（第 9.1 节） |
| `fc2_metadata_core-<core_version>-py3-none-any.whl` | Core 独立 wheel（第 10.2 节） |
| `SHA256SUMS` | 按文件名排序、LF、`<sha256>␣␣<name>`；覆盖 plugin zip、Core wheel、`COMPATIBILITY.json`、`INSTALL.zh-CN.md`、`VERSION`；**不含自身**（第 10.5 节 DAG） |
| `COMPATIBILITY.json` | 兼容清单：支持**坐标**（`(version, host_form, platform)`；tag / peeled commit）、逐坐标状态、pin、**Level-0/1 artifact 哈希**、已知局限编号；与 `INSTALL.zh-CN.md`、E24 使用同一份支持坐标表；**只**由兼容见证的 Part A 与 Level-0/1 哈希**纯函数投影**得到；**不含**自身 / `SHA256SUMS` / release bundle / `P5_C2_COMPATIBILITY_MATRIX.json` 的哈希；**无时间戳**（第 10.5 节） |
| `INSTALL.zh-CN.md` | 第 8.4 / 8.6 / 8.7 / 8.8 节的用户文档（简体中文，遵循《文档语言规范》）；**静态文本，不含任何 artifact 哈希**（用户用 `SHA256SUMS` 自行核对） |
| `VERSION` | 单行：`bundle <plugin_version>+core<core_version>`（无时间戳、**无哈希**） |

bundle 本身是**一个确定性 zip**（第 10.3 节），文件名 `ffcc-amane-release-<plugin_version>.zip`。

### 10.2 Core wheel（专用构建器 `tools/build_core_wheel.py`）

* 输入：**仅** `src/fc2_metadata_core/**/*.py`；输出：`fc2_metadata_core-<ver>-py3-none-any.whl`。**不含** `fc2_organizer`、测试、`__pycache__`、非 `.py` 文件（遇到非 `.py` -> 构建失败）。
* 元数据由 `pyproject.toml [project]` 派生（`name / version / requires-python / dependencies / description`）；`.dist-info/{METADATA, WHEEL, RECORD, top_level.txt}` 为固定格式；`WHEEL`：`Wheel-Version: 1.0`、`Generator: ffcc-build-core-wheel (1)`、`Root-Is-Purelib: true`、`Tag: py3-none-any`。
* `RECORD` 以 `sha256=<urlsafe-b64-no-padding>` 记录每个文件；`RECORD` 自身行 `,,`。
* 构建内容的 **tree 哈希 == `tree_sha256(src/fc2_metadata_core)`**（与 C1 witness 同一算法），写入 pin 与台账（E06 / E29）。
* 依赖元数据保留 `Requires-Dist: httpx<0.28,>=0.27`（pip 方式会装 `httpx`；sidecar 方式不需要，W2-08）。

### 10.3 确定性（“同输入树 -> 同 artifact 字节”）

```text
zip root          : plugin zip 单一顶层文件夹 `ffcc.fc2-metadata/`；wheel 与 bundle 无外层文件夹
file allow-list   : plugin zip = shim 的 3 个文件 + `_impl/*.py`（7 个）；wheel = Core 的 *.py + 4 个 dist-info 文件；bundle = 第 10.1 节 6 个文件
forbidden files   : tests、__pycache__、*.pyc、.venv / venv、任何凭据 / token / .env、绝对路径字符串、开发者临时文件、符号链接、非 UTF-8 / 含 BOM 的 .py、CRLF
timestamps        : 1980-01-01 00:00:00
permissions       : 0o100644 << 16（zip external_attr）；create_system = 3
ordering          : 条目按 posix 路径字节序排序
line endings      : .py / .md / .json / SHA256SUMS / VERSION 统一 LF
compression       : ZIP_STORED（不压缩）——使字节不依赖 zlib 版本 / 平台
version source    : plugin = `_settings.PLUGIN_VERSION`（AST 读取，不 import）；Core = `pyproject [project].version`（tomllib）；bundle 文件名由二者派生
```

确定性验证（E06）：同一输入树在**两个不同的 Python 解释器版本**（3.12 与 3.14）上各构建一次，字节哈希必须相等；再以**不同的临时输出目录与不同的构建顺序**各构建一次，哈希必须相等；工作树换行符为 CRLF 的检出（`autocrlf`）得到相同哈希。

### 10.4 与 C1 `build_amane_plugin_zip.py` 的关系

C1 的构建器与其测试（`test_amane_zip_build.py`）**保持不变**（U2-7）；C2 的最终构建器是**新文件** `tools/build_amane_release.py`，不 import / 不修改 C1 构建器。
C1 骨架 zip 不再被称为可分发物；`adapters/amane/README.md` 的状态行更新为指向本合同（文档级变更，不影响 C1 树哈希）。

### 10.5 Artifact 派生 DAG（冻结；P5-C2-DESIGN-R-04；**严格无环**）

原设计存在环：`COMPATIBILITY.json` 含 `release_bundle_sha256` / `sha256sums_sha256`，而 `SHA256SUMS` 又哈希 `COMPATIBILITY.json`，bundle 又包含二者。R2 冻结如下**分层、无回边**的派生顺序（设计期已用脚本验证：同输入同字节、无环、`sha256sum -c` 通过，W2-14）：

| 层 | 产物 | 输入（只能来自更低层或仓库树） | 禁止包含 |
|---|---|---|---|
| **L0** | Core wheel | `src/fc2_metadata_core/**/*.py` + `pyproject [project]` | 任何其它 artifact 的哈希 |
| **L1** | plugin zip（含 `_ffcc_pin.py`）；`INSTALL.zh-CN.md`；`VERSION` | adapter 树（LF 规范化）+ shim + **L0 的哈希**（写入 `_ffcc_pin.py`）；INSTALL / VERSION 为静态文本 | plugin zip 不含 L2+ 的任何哈希；INSTALL / VERSION **不含任何哈希** |
| *（验收运行）* | 在 **L0 + L1 的确切字节**上运行兼容见证 -> **MATRIX Part A**（hosts / scenarios / parity / core_admission / status） | L0、L1 | — |
| **L2** | `COMPATIBILITY.json` | **Part A 的字段白名单投影** + L0 / L1 的哈希 + 支持坐标 + 局限编号 | **自身哈希、`SHA256SUMS` 哈希、release bundle 哈希、MATRIX 的哈希、仓库 commit 哈希、时间戳** |
| **L3** | `SHA256SUMS` | **L0、L1、L2** 的 5 个成员：plugin zip、Core wheel、`COMPATIBILITY.json`、`INSTALL.zh-CN.md`、`VERSION` | 自身 |
| **L4** | release bundle zip | L0–L3 的 6 个成员（上述 5 个 + `SHA256SUMS`） | bundle 自身哈希 |
| **L5（外部）** | **MATRIX Part B `final_artifacts`** + HANDOFF | `compatibility_json_sha256`、`sha256sums_sha256`、`release_bundle_sha256` | **这些最终外层哈希不得写回 bundle 的任何成员** |

**冻结的生成顺序（Developer 不得临场调整）**：

```text
1. build_core_wheel            -> L0 (core wheel)
2. build_amane_release stage1  -> L1 (plugin zip 以 L0 哈希生成 _ffcc_pin.py；INSTALL / VERSION)
3. run_amane_compat_gate       -> 在 L0+L1 字节上执行 HC / E31 / parity -> MATRIX Part A
4. build_amane_release finalize-> L2 (COMPATIBILITY.json = 投影(Part A, L0/L1 哈希)) -> L3 (SHA256SUMS) -> L4 (bundle)
5. 计算 compatibility_json_sha256 / sha256sums_sha256 / release_bundle_sha256 -> MATRIX Part B；写入 HANDOFF
6. 验证：extract bundle -> `sha256sum -c SHA256SUMS` 通过；成员字节 == 被验收的 L0 / L1 字节；
   在同一仓库树上**重新**执行 2、4 得到的 L1 / L2 / L3 / L4 与 Part B 记录的哈希逐字节相同
```

**MATRIX 两部分的字段边界（冻结）**：Part A = `schema_version, tool, policy, hosts[], artifacts(L0/L1), parity, status, platforms_unverified, core_admission`；Part B = `final_artifacts{compatibility_json_sha256, sha256sums_sha256, release_bundle_sha256}`。
**L2 的投影只读取 Part A 的字段白名单**；因此修改 Part B **不改变** L2–L4 的任何字节（由 E29 的测试断言）。MATRIX 是仓库侧验收证据，可以记录最终 bundle 哈希；bundle 本身不包含任何依赖该哈希的文件版本。

---

## 11. 真实宿主验收（Install / Discover / Reload / Upgrade）

### 11.1 宿主形态与见证矩阵

| 见证行 | 支持坐标（第 7.2 节） | 宿主 | 角色 | 解释器 |
|---|---|---|---|---|
| HOST-A-SRC | SC-03 | v0.15.0 源码检出（`python -m amane.server`，独立 venv） | **必需** | 3.14.x |
| HOST-B-SRC | SC-04 | v0.18.0 源码检出（独立 venv） | **必需** | 3.14.x |
| HOST-A-WIN | SC-01 | 官方 `Amane-v0.15.0-windows-x64.zip` 冻结包 | **必需（Windows）** | 内置 3.14.7 |
| HOST-B-WIN | SC-02 | 官方 `Amane-v0.18.0-windows-x64.zip` 冻结包 | **必需（Windows）** | 内置 3.14.7 |
| HOST-C-MAIN | SC-05 | `origin/main` 检出 | 信息（若 == 稳定版 commit，则 `IDENTICAL_TO_STABLE`） | 3.14.x |
| HOST-MID | SC-06 | v0.16.1 / v0.17.0 | 信息，可选 | 3.14.x |
| （无见证） | SC-07 / SC-08 / SC-09 | macOS 冻结包 / Linux 源码 / Docker | **UNVERIFIED**（无环境；不属于支持声明） | — |

每个“真实服务”见证启动**真正的 Amane 服务进程**（`python -m amane.server` 或 `Amane.Server.exe`）：`AMANE_DATA_DIR` = 临时目录，`AMANE_HOST=127.0.0.1`、随机空闲端口、`AMANE_TOKEN` 固定，通过其**真实 HTTP API**（`/api/plugins`、`/api/plugins/install`、`/api/plugins/reload`、`PATCH /api/plugins/{id}`、`DELETE /api/plugins/{id}`、`GET /api/config`）操作。
**不 mock `PluginManager / install_plugin_zip / purge / CrawlerFactory`。**

### 11.2 场景（HC-01..HC-19；每个场景在**两个必需宿主版本**上各跑；结果写入第 14 节的 JSON）

| ID | 场景 | 通过判据 |
|---|---|---|
| HC-01 | clean install：空数据目录 + sidecar 已放置 -> HTTP 上传 plugin zip | **HTTP 201 Created**（A1-1；精确 201，不是 200，也不是“任意 2xx”）；`/api/plugins` 的 `items` 含 `ffcc.fc2-metadata`；`failures == []`；磁盘上 `plugins/sources/ffcc.fc2-metadata/` 的文件集合 == plugin zip 的文件集合（字节相等） |
| HC-02 | discover：重启服务进程（restart persistence） | 重启后插件仍被发现；`descriptor` 的适配器可控子集与 HC-01 相同；配置仍生效（HC-05 之后执行） |
| HC-03 | descriptor / capabilities | `id`、`name`、`version`（= `PLUGIN_VERSION`）、`capabilities == {film_metadata}`、`content_types == {fc2}`、`urls`、`api_version == "1"` 与 C1 §9 相等；`configuration_model().model_json_schema()` 与 C1 记录的 schema 相等 |
| HC-04 | provider build（真实 `CrawlerFactory`）+ 一次**离线** fetch | 子进程内：真实 `PluginManager.discover` + 真实 `CrawlerFactory`（`PluginContext(web_client=真实 WebClient)`）；`WebClient._session` 为脚本化会话（C1 H 系列同法）或**本机回环 HTTP fixture**（`base_url` 指向 `127.0.0.1`）；得到与 C1 冻结映射一致的 `MediaMetadata`；`provider` 的 `web_client` 与 `PluginContext.web_client` 是同一对象（E17） |
| HC-05 | 配置往返 | 第 12 节矩阵全部行 |
| HC-06 | reload：不改任何文件 `POST /api/plugins/reload` | 200；插件仍在；`sys.modules` 中 `amane_ext*` 被重建为新对象（模块 `id` 与 reload 前不同），`fc2_metadata_core` 对象 **未**被重建（W2-02） |
| HC-07 | reload 执行新代码（stale-module 守卫） | 在 `sources/ffcc.fc2-metadata/_impl/_settings.py` 里改写一个只在测试副本中存在的哨兵常量（**仅在临时数据目录的副本上**）-> reload 后 provider 读到新值 |
| HC-08 | 配置变更触发 rebuild | `PATCH` 改 `source_deadline_seconds` / `sources` 后，新构建的 provider 行为反映新配置（回环请求日志 / 超时观测） |
| HC-09 | 插件替换 / 升级（pin 不变） | 构造“版本 +1、其它字节相同”的第二个 plugin zip（临时副本；`PLUGIN_VERSION` 常量改写仅在测试副本）-> 上传 -> `descriptor.version` 更新；旧模块不残留（stale-module 守卫） |
| HC-10 | Core 缺失 | sidecar 目录不存在且 Core 不可 import：上传 -> 422，消息 == P5-C1 §22 冻结模板；`/api/plugins` 的 `items` 不含该插件；`sources/` 下无目录残留（无半装）；**无回退**到内置 FC2 爬虫 |
| HC-11 | Core 不兼容 | (a) sidecar 放入文件名正确但内容被篡改的 wheel -> `WHEEL_HASH_MISMATCH_TEMPLATE`；(b) 放入另一版本文件名的 wheel -> `WHEEL_VERSION_MISMATCH_TEMPLATE`；(c) 目录形态 Core（pip / `--target` / editable / 源码，**即使字节正确**）且无 sidecar -> `UNVERIFIABLE_TEMPLATE`；均 422 且无半装 |
| HC-12 | 畸形 plugin zip（A1-2；拆分为 5 个变体，判据逐个冻结） | **HC-12a**（`.zip` 文件名、内容不是 ZIP 归档的字节）：**宿主实测 HTTP 500** AND 安装被拒绝 AND `sources/` 无残留 AND `/api/plugins` 无新注册 AND 插件代码从未被导入 / 执行 AND 在 v0.15.0 / v0.18.0（源码与冻结）上行为相同；**HC-12b** 含 `..` 路径、**HC-12c** 无 `plugin.py`、**HC-12d** 多顶层文件夹、**HC-12e** 超大（> 20 MiB）：仍要求 **HTTP 422** 且 `sources/` 无残留。HC-12a 的 500 是 pinned 宿主的已知路由缺陷，**不是**允许 plugin / artifact 返回 500，也不放宽任何其它安装失败判据 |
| HC-13 | 错误 plugin id | zip 内 shim 的 `descriptor().id` 被改成 `other.id`（临时副本）-> 宿主按目录名 / id 校验失败（安装时落盘为 `other.id`；发现期无冲突，但 **`content_routes` / config 不引用**）——判据见第 11.3 节 |
| HC-14 | 重复 plugin | 同一 zip 连续上传两次 -> 第二次**整棵替换**（宿主语义），`/api/plugins` 仍只有一个条目；与手工把同一目录放两个目录名（`descriptor.id != 目录名`）-> 发现期 `failures` 记录 |
| HC-15 | 卸载 | `DELETE` -> 204；`sources/` 目录消失；`plugins/ffcc.fc2-metadata/`（运行时数据，若存在）保留；sidecar 目录**不被触碰** |
| HC-16 | Core 升级（pin 变化）流程 | 按第 8.6 节：卸载 -> 重启 -> 放新 wheel -> 上传新 plugin zip；以及误操作（旧 Core 在内存时直接上传新 zip）得到 `RESTART_TEMPLATE` |
| HC-17 | HTTP 生命周期保持 | 回环 fixture 记录请求：全部来自宿主 `WebClient`（`User-Agent` / TLS 指纹策略 / 代理由宿主决定；adapter 不设）；每个来源 L1 / L2 / L3 计数符合 C1 §15.2 |
| HC-18 | 无副作用 | 运行前后对**临时数据目录之外**的文件系统做快照（`sidecar` 之外）：adapter 无新增 / 修改；插件树写入全部来自宿主（`sources/` 之下） |
| HC-19 | Core 来源准入矩阵（Risk C 信任边界；第 8.3 节；E31） | 在宿主**子进程**内、用真实 `install_plugin_zip` / `PluginManager.discover` 驱动 artifact，对 E31-a..v 做 PASS / FAIL 配对：**源码宿主**覆盖 exact pinned wheel（PASS）、目录形态 Core（pip `--target` / editable / 源码 / `PYTHONPATH`，**含恶意 `.pyc` PoC**）无 sidecar（FAIL，payload sentinel 不存在）与有 sidecar（PASS 且加载的是 wheel、sentinel 不存在）、预加载的正确 / 错误 / 目录形态 Core、被篡改的同名 wheel、遮蔽 finder；**冻结包**覆盖 sidecar 的正确 / 错误版本 / 篡改 / 超大，以及符号链接子项（其**真实宿主**执行按第 11.7 节 A1-3：环境允许则必须真实执行；环境不允许则记为 `ENVIRONMENTALLY_UNAVAILABLE`，并**不得**表述为真实宿主已执行 PASS）。每个 FAIL 必须是 422 / `failures`、固定模板、**无半装**，且失败路径后 `sys.path` 与入口逐元素相同、`sys.modules` 中 `fc2_metadata_core*` 对象身份不变、verified-wheel importer-cache 条目 == 入口状态。**E31-u（源码宿主）**：exact pinned wheel **已在** `sys.path`，而更靠前有一个**惰性的**（只含注释、从不执行代码的）不受支持 Core 目录包使真实解析先命中它 -> 必须 FAIL，惰性包从未被导入；**E31-v**：惰性的 `zipimporter` 子类 loader double -> FAIL。冻结包宿主上无法在宿主进程里布置 `sys.path` 夹具，HC-19 对冻结包只覆盖 sidecar 各分支；E31-u / E31-v 由源码宿主 + 单元层覆盖 |

### 11.3 HC-13 / HC-14 的判据说明

宿主在 `install_plugin_zip` 中**以 `descriptor().id` 为目录名提交**，所以“错误 plugin id”的 zip 会被安装为另一个目录，而不是被拒绝；
`discover()` 才校验 `descriptor.id == 目录名` 并拒绝内置 id 冲突。本合同的判据以**宿主行为**为准（两个版本一致），并要求：
(1) 官方 artifact 的 id 恒为 `ffcc.fc2-metadata`（E07 逐字节检查 `descriptor().id` 与 `_ffcc_pin` / `_settings.PLUGIN_ID`）；(2) 构建器**拒绝**生成 id 不等于 `PLUGIN_ID` 的 zip；
(3) 宿主对错误 id / 重复 id 的行为在两个版本上**被记录且相同**（若不同 -> 记入矩阵差异，不隐瞒）。

### 11.4 平台与解释器

* HOST-*-SRC：Python 3.14.x，**每个宿主版本一个独立 venv**（依赖锁不同）；记录 `pip freeze` 的哈希。
* HOST-*-WIN：官方冻结包，不需要本机解释器；其内置 Python 版本写入矩阵。
* **主项目回归套件**继续使用项目正式 Python（3.12.x）。
* 无 macOS / Linux / Docker 环境（设计期已核对：本环境无 Docker）：对应坐标 SC-07 / SC-08 / SC-09 记为 `UNVERIFIED`，**不得**在 `COMPATIBILITY.json`、`INSTALL.zh-CN.md` 或 HANDOFF 中声明为已支持（E24 / E30）；
  `INSTALL.zh-CN.md` 若保留 Docker 步骤，必须标注 `UNVERIFIED / informational — 不在本发布验收覆盖范围内`。
* `COMPATIBILITY.json`、`INSTALL.zh-CN.md`、E24 使用**同一份**支持坐标表（第 7.2 节）。

### 11.5 公网

所有宿主见证**不访问外部站点**：脚本化会话或 `127.0.0.1` 回环 fixture。公网可用性不是 acceptance blocker。

### 11.6 不碰用户文件

验收使用的数据目录、冻结包解压目录、venv 全部在临时目录；不扫描、不读取、不写入用户媒体库；不使用用户的 Amane 实例 / 数据目录。HC-18 与 E19 机检。

### 11.7 Pre-L1 Authority Amendment A1：宿主观测事实与证据方法（冻结；窄范围）

本节只冻结**真实宿主事实**与**证据方法**，**不改变** adapter 语义、安全边界、exact pinned wheel only、威胁模型 / TOCTOU、R3 最终解析不变量、回滚、artifact DAG、支持坐标模型、Risk Class C 与 P5-C1 CLOSED 语义。

**A1-1 `POST /api/plugins` 的成功状态码 = 201 Created（分类 A：冻结设计对宿主 API 的错误假设）**

* 事实（直接读两个 pinned 源码）：v0.15.0（`45dff2159369883e028a296d775a4598836c1ddd`）与 v0.18.0（`0a8a731d7746bde5e8828d1eb74c7bd9752b42e4`）的 `src/amane/api/routes/plugins.py` 都声明 `@router.post("", response_model=PluginListResponse, status_code=201)`；`routes/plugins.py` 与 `plugins/packaging.py` 在两版**逐字节相同**；上游自己的 `tests/api/test_plugins.py`（两版相同）对 zip 上传 / 目录路径 / zip 路径三种安装方式都断言 201；`POST /api/plugins/reload` 为默认 200、`DELETE` 为 204。四个必需宿主（含两个官方冻结包）的观测均为 201，与 plugin / shim / Core / 构建器无关。
* 冻结：HC-01 以及所有“上传 plugin zip 成功”的判据（HC-09 / HC-13 / HC-14 / HC-16 / HC-19 的 PASS 分支）的状态码 = **精确 201**。**不**泛化为“任意 2xx”（上游源码与上游测试都固定为 201）；reload = 200、DELETE = 204、PATCH = 200 按原判据不变。
* 若未来某个新坐标观测到不同的成功码：按第 14.2 节为该坐标重新见证，**不得**继承本冻结值。

**A1-2 非 zip 上传（HC-12a）的宿主行为（分类 A：冻结设计对宿主路由异常处理的错误假设）**

* “非 zip”的精确定义：以 `.zip` 文件名上传、内容不是 ZIP 归档的字节。（上游测试里的 `not_zip` 用例上传的是文件名 `plugin.py`，被**文件名检查**拒绝为 422；那是另一个变体，不属于冻结的变体集。）
* 事实：路由只捕获 `(ValueError, TypeError, OSError)`（`routes/plugins.py` 第 63 行）；`install_plugin_zip` -> `_extract_zip` 的第一步是 `zipfile.ZipFile(io.BytesIO(payload))`，对非 ZIP 字节抛出 `zipfile.BadZipFile`，其 MRO 为 `BadZipFile -> Exception`（**不是** `ValueError` / `OSError` 的子类），因此未被路由捕获，FastAPI 返回 500。该异常发生在解压与导入**之前**（`inspect_plugin_id` 从未被调用），`finally` 清理 `.staging`，无残留。两版逐字节相同，四个必需宿主观测均为 500；原因不在 plugin、shim、Core 或 release 构建器（该 payload 里根本没有它们）。
* 冻结：HC-12 拆为 12a..12e（见第 11.2 节）。12a = 宿主实测 500 + 拒绝 + 无残留 + 无注册 + 插件代码从未执行 + 两版相同；12b..12e 仍为 422 + 无残留。
* 边界：这**不是**允许 plugin / artifact 返回 500；**不**把“任意安装失败”放宽成“任意错误状态码”（HC-10 / HC-11 / HC-16 / HC-19 的失败仍是 422 + 固定模板）；仅对该 exact 变体、在这两个 pinned 宿主版本上有效，记为 L-C2-14。

**A1-3 符号链接子项的真实宿主证据（执行环境能力限制；locator 语义不变）**

* 不变：locator 只接受 `os.lstat` 判定的普通文件；符号链接冒充 wheel -> `WHEEL_HASH_MISMATCH_TEMPLATE`（D-06、I-C2-8、E31-i、M2-14）。
* 观测环境事实：4358b3d 的执行环境是非管理员的 Windows 11 账户；`os.symlink` 失败，Win32 错误 1314（“客户端没有所需的特权”）；未持有 `SeCreateSymbolicLinkPrivilege`；开发者模式未启用。创建符号链接需要提权或改变系统安全设置，而本包不得要求用户修改 / 关闭系统安全功能；因此“在不改变系统安全设置的前提下临时创建 file symlink”在该环境**不可得**。
* 冻结规则：
  1. **原要求保留为目标**：在环境所有者合法提供创建 file symlink 能力、且无需改变系统安全设置的环境里，符号链接子项必须在四个必需宿主上**真实执行**，判据同 E31-i（422 + `WHEEL_HASH_MISMATCH_TEMPLATE` + 无半装 + `sys.path` / `sys.modules` / importer-cache 状态不变）。
  2. 环境不具备该能力时，该子项的**真实宿主执行**记为 `ENVIRONMENTALLY_UNAVAILABLE`（既不是 PASS，也不是 FAIL，更不是“当作通过的 skip”），并且必须同时具备**全部**替代证据：
     (a) E31-i 的符号链接单元用例在 3.12 与 3.14 上执行，使用 `os.lstat` 替身，替身**只**把 `st_mode` 改写为符号链接，其余字段（大小 / 时间戳）保持真实——使“接受非普通文件”的变异体不会因别的原因被偶然拒绝；
     (b) M2-14 的“接受非普通文件（符号链接）”变体被 (a) 的用例杀死；
     (c) 记录 `symlink_privilege=false`。
  3. 报告规则：HC-11 / HC-19 / E31 / HANDOFF / `COMPATIBILITY.json` **不得**把该子项表述为“真实宿主已执行 PASS”。第 14.1 节 `core_admission.cases[].observed` 增加**唯一**的额外取值 `ENVIRONMENTALLY_UNAVAILABLE`，只能用于符号链接子项，并且必须与 `symlink_privilege=false` 同时出现；其它任何子项出现该值 = FAIL。HC-11 / HC-19 的 `passed` 只对**已执行**子项计算，但上述记录是必需项。
  4. **这种 Risk C 证据替代是否足够，由独立 Reviewer 单独裁决**；本文（Designer）不宣称可接受。若 Reviewer 裁定不足，补证条件 = 在由环境所有者合法提供该能力的 Windows 环境上执行真实符号链接子项（不要求能力由开发者授予或长期保留）。

**A1-4 E16 的双轨证据模型（分类 A + B；不降低语义覆盖）**：见第 13.2 节。

---

## 12. 配置往返（Config Round-trip）

### 12.1 链路（冻结）

```text
PATCH /api/plugins/ffcc.fc2-metadata {enabled?, config?}
  -> 宿主 `{**current.config, **req.config}`（顶层浅合并）-> HotSettings 预览 -> manager.validate_hot_settings(…, require_available=False)
     -> configuration_model().model_validate(config)   （Pydantic，C1 `Fc2MetadataConfig`，其 model_validator 调用 C1 `parse_settings`）
  -> 写 TOML（宿主）-> apply_rebuild -> CrawlerFactory 在首次使用时 build_plugin_provider(…) -> provider 的**有效运行配置**
```

“有效运行配置”的**观测 oracle**（不得读私有属性）：provider 的**可观察行为**——回环 fixture 的请求日志（哪些来源被请求、顺序、`base_url` 命中、超时）+ `fetch` 结果。

### 12.2 矩阵（HC-05；每行在两个必需宿主版本上都运行）

| 样本 | 期望（四处必须一致） |
|---|---|
| 缺省配置（`{}`） | PATCH 200；`parse_settings` 通过；provider 使用 Core 默认来源集合与顺序、`source_deadline_seconds = 20` |
| 自定义来源顺序 `sources=[…]`（C1 §11 允许的 id） | 200；回环请求顺序与列表一致；字段优先级按列表 |
| 禁用来源（`enabled=false`） | 200；该来源**无任何请求** |
| `base_url` 覆盖（安全绝对 http(s)） | 200；请求到达回环 fixture |
| `source_deadline_seconds` 合法边界（`> 0`、`<= 600`） | 200；超时按配置生效 |
| 非法：未知来源 id、重复 id、`base_url` 含凭据 / query / fragment、非 http(s)、`source_deadline_seconds` 为 0 / 负 / > 600 / NaN / inf | **PATCH 422**；`validate_plugin_config` 抛；`parse_settings` 拒绝；`build_plugin_provider` 不被到达 |
| **原始类型拒绝**（C1 L1-01 教训）：`enabled="true"`、`enabled=1`、`source_deadline_seconds="20"`、`source_deadline_seconds=True`、`sources` 为 dict、`id` 为非 str | **422**；`parse_settings` 同样拒绝（**不得**出现“Pydantic 接受但 runtime parser 拒绝，或反过来”） |
| 未知顶层键（`extra="forbid"`） | 422 |
| 顶层浅合并语义 | 只改 `source_deadline_seconds` 不丢 `sources`；改 `sources` 整体替换；**无法通过省略键恢复默认**（宿主限制，记录为 L-C2-07，由文档说明“显式写回默认值”） |

**一致性守卫（compat guard）**：对表中**每一个**样本，`{ HTTP PATCH 是否 2xx, validate_plugin_config 是否通过, parse_settings 是否通过, build 是否成功 }` 四个布尔值必须**全真或全假**；任何不一致 = FAIL（E09，且有对应 mutant M2-12）。

---

## 13. 跨版本语义（Cross-version Semantics）

### 13.1 原则

同一请求在两个必需版本目标（v0.15.0 / v0.18.0）的各必需坐标（SC-01..SC-04）上必须产生**等价的 adapter 语义**；P5-C1 冻结的映射**不因宿主版本改变**。

### 13.2 必须字节 / 语义相等（E15、E16）

对固定请求集（成功全字段、PARTIAL、未命中、非法 `SearchQuery`、取消、`base_url` 回环、多来源冲突、复数窄化各一；**每个 Core `SourceErrorKind` 的覆盖按本节末尾的 E16 双轨证据模型，A1-4**）在两个必需宿主上执行；
以**规范化 JSON（排序键、`ensure_ascii`）**记录并比较下列字段的 sha256：

```text
number、title、actors（含性别 / 顺序）、tags、release、runtime、source_url（poster / thumb / extrafanart 同）、external_id
结果类别：MediaMetadata | None | SourceError
FailureReason 值（逐 kind）、SourceError.detail 全文
descriptor 的适配器可控子集（id、name、version、capabilities、content_types、languages、urls、metadata_fields、api_version、rate_limit）
configuration_model().model_json_schema()
```

**E16 双轨证据模型（A1-4）**

* 原句“每个 `SourceErrorKind` 一例”隐含的前提——每个 kind 都能被真实 HTTP 传输自然诱发——被观测证伪：在 4358b3d，受控栈**端到端实际观测**到的 kind 集合 `K_A` = {`blocked`, `rate_limited`, `source_deadline`, `connection_error`, `http_server_error`, `parse_error`, `invalid_response`}（7 个；取自 `SourceResult` 的 `<source_id>=<kind>` detail 词汇）；其余 9 个（`adapter_exception`, `circuit_open`, `decode_error`, `network_error`, `not_found`, `redirect_error`, `response_too_large`, `result_contract_mismatch`, `timeout`）**未被观测到**。这是观测，不是“不可诱发”的证明；某个 kind 日后若能被传输层诱发，可加入 `K_A`。
* **E16-A（传输可诱发；端到端）**：对 `K_A` 中的每个 kind，受控宿主栈（真实 `PluginManager` / `CrawlerFactory` / `WebClient` -> `127.0.0.1` 回环）端到端执行；规范化的 `FailureReason` 值与 `SourceError.detail` 全文在四个必需宿主上相等。**每个用例必须记录**实际观测到的 kind（来自 detail 词汇）；用例标签**不得**声称一个未被观测到的 kind。
* **E16-B（全部 16 个成员；宿主进程内；生产映射路径）**：对**每一个** `SourceErrorKind` 成员，在**每个必需宿主进程内**（经探针；冻结包同样适用）：(1) 用 Core 的公共构造器构造 P5-C1 冻结的输入对象（`SourceResult` / `AggregationResult`），**不得**用手写字典代替；(2) 运行**生产**的结果映射路径（P5-C1 表 F / 表 G 的实现：`AggregationResult` -> 中立结果，得到 reason 与 `FC2 lookup failed: <source_id>=<kind>` 形式的 detail）；(3) 对运行性失败，再经**生产**的 provider 转换（中立失败 -> `SourceError(FailureReason(reason), detail=...)`；运行时以只返回该中立结果的桩替代）取得**宿主的** `FailureReason` 值与 `detail` 全文；(4) 非运行性 kind（`NOT_FOUND`；P5-C1 表 G 为“穷尽 `NOT_FOUND` 之外”）的期望 = 中立 no-match（宿主 `None`），不是 `SourceError`。
* 完整性与等价：`SourceErrorKind` 的每个成员（当前 16 个）都必须出现在 E16-B 的结果里，缺一 = FAIL；E16-B 的规范化结果（kind -> {结果类别, `FailureReason` 值, `detail`}）在四个必需宿主上哈希相等；期望值以 P5-C1 Frozen 表 F / 表 G 为准（独立于被测实现的转录）。**只调用叶子函数 `reason_for_kind`、或只比较一张手写映射字典，不满足本模型**（那样的证据是空洞的）。
* 保持不变：对宿主 `FailureReason` **全部成员**（v0.15.0：16 个；v0.18.0：17 个，多 `API_ERROR`），桥的分类是全函数且确定（C2-E16 原有要求）。

### 13.3 允许的差异（白名单；不在白名单的差异 = FAIL）

| ID | 差异 | 为什么允许 |
|---|---|---|
| DIFF-01 | 宿主日志文本、`structlog` 字段、记录格式 | 宿主私有；adapter 不解析（I8 / I23） |
| DIFF-02 | `network.max_retries = 0`：v0.15.0 **零请求**（L-04）-> 所有来源 `CONNECTION_ERROR` -> `FAILED/network`；v0.18.0 发出 **1 次**请求 | 宿主缺陷已在新版修复；L2 上界 `S×max(1,H)` 两版均成立；该场景在 parity 集**之外**单列，各自断言本版本行为 |
| DIFF-03 | 宿主向配置域名补 `Referer`（v0.18.0 `same_origin_referer_hosts`）；请求头集合差异 | adapter 不设置 / 不依赖 `Referer`；桥只读响应 |
| DIFF-04 | 重试退避时间、`impersonate` 随机选择 | 宿主策略（L-03） |
| DIFF-05 | `SourceDescriptor` 的宿主侧字段（`multi_language` / `traits`）；`FailureReason` 的新增成员 | adapter 不传、不依赖；E16 的枚举守卫保证新成员落入确定的桶 |
| DIFF-06 | 宿主路由文本 / 序列化格式（如 `/api/plugins` 响应的非 adapter 字段） | 宿主 API 面 |
| DIFF-07 | artifact / 安装差异：冻结包与源码形态的目录、解释器路径、`sys.path` 内容 | 形态差异；adapter 行为一致（E21 / E22） |

---

## 14. 兼容见证与版本漂移门

### 14.1 文件

`docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json`（机器可读；确定性；**不含**时间戳 / 耗时 / 端口 / 临时路径 / 主机名 / 用户名）。

```text
schema_version
tool                  : {name, sha256(tools/run_amane_compat_gate.py)}
policy                : {minimum, stable_definition, main_role, support_coordinates[{id, amane_version, host_form, platform, claim_class(deployment|integration|informational), role}]}
hosts[]               : {label, coordinate_id, role(required|informational), form(source|frozen-desktop), tag, tag_object, peeled_commit,
                         release_version, requires_python, plugin_api_version, python_version, platform,
                         api_fingerprint_sha256, adapter_used_subset_fingerprint_sha256, deps_lock_sha256,
                         identical_to_stable(bool, 仅 main), scenarios[{id, passed, observations_sha256}]}
artifacts             : {plugin_zip_sha256, core_wheel_sha256, core_tree_sha256, adapter_tree_sha256, impl_tree_sha256, shim_tree_sha256, pin_sha256}   # 仅 L0 / L1；**Part A**
final_artifacts       : {compatibility_json_sha256, sha256sums_sha256, release_bundle_sha256}   # **Part B**（L5，最后写入；不进入 bundle；第 10.5 节）
parity                : {required_pairs[{a, b, fields[…], equal(bool), sha256_a, sha256_b}], allowed_diffs_observed[DIFF-nn…]}
status                : [{coordinate_id, amane_version, host_form, platform, status(SUPPORTED|CONDITIONALLY_SUPPORTED|BLOCKED|UNVERIFIED|INFORMATIONAL|IDENTICAL_TO_STABLE), reason}]
                         —— **key = 坐标 `(version, host_form, platform)`，不得只以版本为 key**；版本级状态不得覆盖 / 继承平台级状态
platforms_unverified  : [macos, linux, docker]（= SC-07 / SC-08 / SC-09）
core_admission        : {core_wheel_sha256, cases[{id, mode(wheel|directory|loaded|shadow), python, expected(PASS|FAIL), observed(PASS|FAIL|ENVIRONMENTALLY_UNAVAILABLE；后者仅用于符号链接子项，见 A1-3), template, sys_path_unchanged_on_fail(bool), sys_modules_unchanged_on_fail(bool), payload_executed(bool)}]}   # E31；Part A
```

### 14.2 版本漂移门（以后出现新 Amane release）

```text
1. python tools/run_amane_compat_gate.py --host <label>=<...> ...  （新增一个 required 坐标）
2. 重新生成 JSON；与已提交 JSON 做 diff；`parity.required_pairs[*].equal` 全真且 `scenarios[*].passed` 全真 -> **该 `(version, host_form, platform)` 坐标**可升为 SUPPORTED（不影响其它坐标）。
3. 任一失败 -> 该坐标标 BLOCKED，不得改动 P5-C1 语义去迁就；开新的兼容 C（Phase 5 以外）。
```

门本身由 E04 / E15 / E22 / E23 的同一工具实现；不另设“漂移专用”代码路径。

---

## 15. Evidence Gate（C2-E01..C2-E31；一次 C 级 Review 的唯一证据集）

| ID | 证据 | 判据 |
|---|---|---|
| C2-E01 | exact diff / scope | `git diff 232ece0..HEAD --stat` 只含 allow-list（计划第 4 节）；`src/**`、`tests/**`（既有）、`adapters/amane/fc2_amane_adapter/**`、`tools/` 既有文件、`pyproject.toml`、P5-C1 文档 = **零 diff** |
| C2-E02 | P5-C1 冻结语义不变 | `tree_sha256(adapters/amane/fc2_amane_adapter) == P5_C1_HOST_WITNESS.json.adapter_tree_sha256`；`_impl/` 的 `tree_sha256`（同一 CRLF -> LF 规范化）与之相等（I-C2-1，normalized-byte identity）；P5-C1 的 `tests/amane_adapter/**` 全部原样通过 |
| C2-E03 | Amane 版本坐标 | tag / tag 对象 / peeled commit / release 版本 / `requires-python` / `PLUGIN_API_VERSION` 在 S1 重新核对并写入 JSON；`git rev-parse` 与 GitHub Release 元数据一致；`app-*` 排除理由记录 |
| C2-E04 | API 兼容矩阵 | v0.15.0 与 v0.18.0 的清单（AST）生成；“适配器可控子集指纹”两版相等；第 6.2 节每一行差异都有机检断言 |
| C2-E05 | Core 最终供给 / 安装 | HC-01 / HC-10 / HC-11 / HC-16 / HC-19 在两个必需宿主 + 冻结包上通过；**唯一被接受的 Core 形态是 exact pinned wheel**（E31）；`INSTALL.zh-CN.md` 的每一步被脚本化执行（“文档即测试”）；文档中**不出现**把 pip / 目录形态当作受支持 Core 来源的步骤 |
| C2-E06 | 确定性 artifact | 两个解释器 × 两个输出目录 × CRLF 检出的 plugin zip / wheel / bundle 哈希全相等；允许 / 禁止清单机检 |
| C2-E07 | clean install | HC-01、HC-03；`descriptor().id` 恒为 `ffcc.fc2-metadata` |
| C2-E08 | discovery | HC-02 / HC-03 / HC-14；真实 `PluginManager.discover` |
| C2-E09 | config round-trip | HC-05 / HC-08；一致性守卫（四布尔全真或全假） |
| C2-E10 | provider build | HC-04；真实 `CrawlerFactory` |
| C2-E11 | reload | HC-06 / HC-07；无陈旧模块 |
| C2-E12 | upgrade / replacement | HC-09 / HC-16；旧模块不残留 |
| C2-E13 | missing Core | HC-10；消息 == P5-C1 §22；无半装；无回退 |
| C2-E14 | incompatible Core | HC-11 / HC-19；wrong-version / tampered / directory-form / unverifiable / already-loaded-wrong / mixed-origin 全部 fail closed 且无半装（细节见 E31） |
| C2-E15 | 跨版本结果等价 | 第 13.2 节全部字段哈希在两个必需宿主上相等 |
| C2-E16 | 跨版本错误等价 | **双轨（第 13.2 节 A1-4）**：E16-A = 传输可诱发的 kind 端到端（记录实际观测 kind；标签不得虚称）；E16-B = 全部 `SourceErrorKind` 成员在**每个必需宿主进程内**经**生产**映射路径与生产 provider 转换得到 `FailureReason` / `detail`，四宿主哈希相等；对宿主 `FailureReason` **全部成员**枚举，桥的分类是全函数且确定 |
| C2-E17 | HTTP 生命周期保持 | provider 持有宿主 `web_client` 的**同一对象**；adapter 树无第二个 HTTP 客户端（AST，C1 守卫仍绿）；HC-17 |
| C2-E18 | 无 vendoring | plugin zip 不含 Core 文件（文件名 + 整文件字节包含扫描）；`fc2_metadata_core` 仅出现在 `_impl` 的 import 语句与 `_core_gate` 常量中；Core wheel 与 plugin zip 为两个独立文件 |
| C2-E19 | 无新持久化 / 无用户文件改动 | `_ffcc_locator` 与 shim 的 AST 守卫（无写 API）；HC-18 文件系统快照；用户目录零接触 |
| C2-E20 | mutation / 非空洞 | 第 16 节 M2-01..M2-23 全部 KILLED |
| C2-E21 | v0.15.0 宿主集成（坐标 SC-01 / SC-03） | HOST-A-SRC 与 HOST-A-WIN：HC-01..HC-19 全通过 |
| C2-E22 | v0.18.0 宿主集成（坐标 SC-02 / SC-04） | HOST-B-SRC 与 HOST-B-WIN：HC-01..HC-19 全通过（或 BLOCKED + 根因） |
| C2-E23 | current main 信息见证 | HOST-C-MAIN：若 commit == 稳定版 -> `IDENTICAL_TO_STABLE`（不重复计作独立见证）；否则运行并记录，**失败不阻塞**，记为信息差异。E23b：中间版本（可选） |
| C2-E24 | Python / 平台 / 支持坐标矩阵 | 3.14.x（源码宿主）、冻结包内置 3.14.7、主套件 3.12.x、Windows 11；**逐坐标** SC-01..SC-09 的状态与见证一一对应，SC-07 / SC-08 / SC-09 = `UNVERIFIED`；`COMPATIBILITY.json` / `INSTALL.zh-CN.md` / 本 E 项同一份坐标表；JSON 的 `status` 以坐标为 key，不得出现“版本级 SUPPORTED 覆盖未验证平台” |
| C2-E25 | targeted tests | `tests/amane_compat/**` 全绿，列出 collected / passed / skipped |
| C2-E26 | 既有契约 | P5-C1 `tests/amane_adapter/**`、Phase 1-4 `tests/contract/**` 与架构守卫全绿 |
| C2-E27 | full suite | `pytest tests -q` 在 3.12 上：passed / skipped / failed 全部记录；failed = 0；与 P5-C1 基线（8448 passed / 40 skipped）对账，差额 = 新增 targeted 测试数 |
| C2-E28 | skip / xfail 对账 | skip nodeid 清单与基线逐条对账；新增 skip = 0（宿主依赖的 skip 必须有显式、可审计的原因，且不得出现在 targeted 集合） |
| C2-E29 | artifact 哈希与**派生 DAG** | L0 / L1 哈希记录在 MATRIX Part A，L2–L4 记录在 Part B 与 HANDOFF，互相一致（`_ffcc_pin` 中的 wheel 哈希 == 实际 wheel 哈希）；**DAG 测试**：拓扑检查（任何成员的内容不依赖其自身或更高层的哈希）；`COMPATIBILITY.json` / `INSTALL.zh-CN.md` / `VERSION` 不含 `SHA256SUMS` / bundle 哈希；修改 Part B **不改变** L2–L4 字节；`sha256sum -c` 通过；从仓库树重建的 L1–L4 与 Part B 逐字节一致（第 10.5 节） |
| C2-E30 | evidence gaps / limitations | 如实列出：macOS / Linux / Docker `UNVERIFIED`；哈希与导入之间的 TOCTOU 窗口（L-C2-13）；Core 升级需重启；PATCH 浅合并；Phase 6 范围；以及任何未能完成的 E 项 |
| C2-E31 | **locator 信任边界 / security 证据（Risk C 专项）** | 第 8.3 节准入规则的 **PASS / FAIL 配对矩阵全部通过**（下表，含 Reviewer 的 `.pyc` PoC）；在单元层（`tmp_path`，真实构建的 wheel）与真实宿主（HC-19）各执行一遍，**3.12 与 3.14 均执行**；威胁模型（第 8.8 节）的 Defended / Not Defended 与文档措辞一致；**Final C-level Review 必须在自己的 checkout 上独立重跑**，不得仅引用 HANDOFF |

**E31 PASS / FAIL 配对矩阵（最低集合；可增不可减；R2 改写）**：

| 子项 | 场景 | 期望 |
|---|---|---|
| E31-a | already-loaded：来自 exact pinned wheel（`type(loader) is zipimporter`；文件名 + 当前 sha256 == pin；所有 `fc2_metadata_core*` 条目同根）——**current-origin + current-artifact proof** | **PASS**（`sys.path` / `sys.modules` 无任何变化） |
| E31-b | already-loaded：来自错误版本的 wheel | **FAIL**（`RESTART_TEMPLATE`） |
| E31-c | already-loaded：来自被篡改的同名 wheel（文件名相同、sha256 不同） | **FAIL**（`RESTART_TEMPLATE`） |
| E31-d | already-loaded：目录形态 Core（pip `--target` / site-packages 形态；**即使字节完全正确**） | **FAIL**（`RESTART_TEMPLATE`） |
| E31-e | already-loaded：editable / 源码形态 Core | **FAIL**（`RESTART_TEMPLATE`） |
| E31-f | 未加载：目录形态 Core 在 `sys.path` 上（pip / `--target` / editable / 源码 / `PYTHONPATH`，**即使字节完全正确**），无 sidecar | **FAIL**（`UNVERIFIABLE_TEMPLATE`），在任何 import 之前；`fc2_metadata_core` 不在 `sys.modules` |
| E31-g | 未加载：目录形态 Core 在 `sys.path` 上，同时有**有效 sidecar** | **PASS**，且加载的是 wheel（`spec.loader.archive` == wheel）；目录形态 Core **从未被执行**（其 `__init__.py` 写 sentinel，sentinel 不存在） |
| E31-h | **Reviewer 的恶意 `.pyc` PoC**：目录形态 Core，`__pycache__/__init__.cpython-3x.pyc` 被替换为携带源文件相同 mtime / size 的恶意 pyc；`*.py` 树哈希**不变** | (1) 无 sidecar：**FAIL**（`UNVERIFIABLE_TEMPLATE`），**payload sentinel 不存在**；(2) 有有效 sidecar：**PASS** 但加载的是 wheel，**payload sentinel 不存在**；(3) 已加载的目录形态（用无害 pyc 替身）：**FAIL**（`RESTART_TEMPLATE`）；**3.12 与 3.14 均执行**；**不得删除该场景** |
| E31-i | sidecar：篡改 1 字节 / 符号链接 / `> 16 MiB` / 同名目录 / 仅有其它版本 wheel | **FAIL**（`WHEEL_HASH_MISMATCH_TEMPLATE` / `WHEEL_VERSION_MISMATCH_TEMPLATE`）；无权限创建符号链接时以 `os.lstat` 替身执行并在报告中记录 `symlink_privilege=false`（**不得 skip**）；**真实宿主**的符号链接子项按第 11.7 节 A1-3：环境允许则真实执行，否则记为 `ENVIRONMENTALLY_UNAVAILABLE`（不得表述为真实宿主已执行 PASS） |
| E31-j | 混合来源：已加载的 `fc2_metadata_core.*` 子模块的 `loader.archive` 与顶层不同 / 来自目录 / 非精确 zipimporter 类型 / 无 `__spec__` / 命名空间包 | **FAIL**（`RESTART_TEMPLATE`） |
| E31-k | 遮蔽：`sys.meta_path` 上更靠前的 finder 先返回 `fc2_metadata_core` | **FAIL**（`UNVERIFIABLE_TEMPLATE`）；**预解析阶段拒绝，从未修改 `sys.path`** |
| E31-l | **locator-owned verified-wheel path / cache 效应的回滚**：(1) 插入后验证失败（有状态 finder：仅在 wheel 已进入 `sys.path` 之后才抢占），入口时 verified-wheel 的 importer-cache 条目**不存在**；(2) 同一场景，入口时该条目**已存在** | **FAIL**（`UNVERIFIABLE_TEMPLATE`）；回滚后 `sys.path` 与入口逐元素相同且是同一 list 对象；(1) 新增的 verified-wheel cache 条目被移除，(2) 条目保持入口时的**原对象**；不要求恢复全局 importer cache 的其它条目 |
| E31-m | 预装目录形态 Core 且 sidecar 同名条目是目录 / 非普通文件 | **FAIL**（`WHEEL_HASH_MISMATCH_TEMPLATE`）；目录形态 Core 不被执行 |
| E31-n | **失败路径副作用（机械验证）**：对**每一个** FAIL 用例（含 E31-u / E31-v） | 断言：`sys.path == entry snapshot`（逐元素、同一 list 对象）；`sys.modules` 中 `fc2_metadata_core*` 的键集合与对象身份 == 入口；**verified-wheel 的 importer-cache 条目 == 入口状态**（入口无 -> 无；入口有 -> 原对象）；locator **没有** import Core。**不**要求恢复整个解释器的 importer cache |
| E31-o | 无 Core、无 sidecar（`find_spec is None`） | locator 不抛；随后产生 **P5-C1 §22 冻结消息**（E13） |
| E31-p | 成功路径副作用上限与幂等 | 至多一次 locator-owned `sys.path` 插入（仅当 wheel 原本不在 `sys.path`）；重复调用幂等（`sys.path` 中该 wheel 恰好 1 个条目，**第二次调用仍执行 2E 最终真实解析**）；已加载且证明通过的 Core 不改 `sys.path`；**每一个成功返回前都有最终真实解析证明** |
| E31-q | wheel 构建内容 | 构建器产出的 wheel **仅含** `*.py` + 4 个 dist-info 文件（无 `.pyc` / `.pyd` / `.so` / `.pth`）；wheel 成员的 tree 哈希（C1 算法）== `P5_C1_HOST_WITNESS.json.core_tree_sha256`（**构建期** traceability；locator 不使用树哈希） |
| E31-r | 错误模板 | 4 个模板固定、有界、无绝对路径、无外部数据的 `repr` |
| E31-s | Python 矩阵 | 上述全部用例在 3.12（主套件）与 3.14（宿主）上执行 |
| E31-t | 威胁模型措辞守卫 | `INSTALL.zh-CN.md` 含“运行期间不要替换或删除 sidecar wheel”；`INSTALL.zh-CN.md` / `COMPATIBILITY.json` / HANDOFF 不含“publisher authenticity / 发布者认证 / 数字签名 / 防篡改”之类**未被设计支持**的承诺（字符串扫描；第 8.8 节 Non-claims） |
| E31-u | **wheel 已在 `sys.path` 但实际当前解析不是它（A-01；无副作用 sentinel fixture，不执行任何 payload）**：Core 尚未加载；exact pinned wheel **已经**位于 `sys.path`（例如在较后位置）；`sys.path` 中更靠前的位置有一个**惰性的**不受支持 Core 来源（目录形态包，`__init__.py` 只含注释，不执行任何代码；或惰性 meta_path finder）使真实解析先命中它 | **FAIL**（`UNVERIFIABLE_TEMPLATE`）——**不得**因“wheel 已在 `sys.path`”而成功；唯一冻结行为 = fail closed（不提升、不重排）。同时断言：不受支持的来源**从未被接受**（惰性包**从未被导入**）；`sys.path` 与入口逐元素相同；verified-wheel importer-cache 条目 == 入口状态；`sys.modules` 中 `fc2_metadata_core*` 对象身份不变；locator 没有 import Core；3.12 与 3.14 均执行 |
| E31-v | **意外的 loader 实现（A-04）**：惰性 test double 使真实解析返回的 spec 的 `loader` 是 `zipimporter` 的**子类实例**（`archive` 等于 verified wheel 且 origin 在归档内）；以及已加载 Core 的 `__spec__.loader` 为该类 double | **FAIL**（`UNVERIFIABLE_TEMPLATE` / 已加载分支 `RESTART_TEMPLATE`）——证明判据是 `type(loader) is zipimport.zipimporter` 而不是 `isinstance`；不需要制造实际攻击对象 |

---

## 16. Non-vacuity / Mutation（每个 mutant 必须有 killer）

| ID | Mutant | Killer |
|---|---|---|
| M2-01 | shim 里把插件 id 写错（`ffcc.fc2metadata`） | E07 逐字节 id 断言；HC-01 目录名 / `/api/plugins` 项 |
| M2-02 | shim / 打包覆盖 `api_version`（硬编码 `"2"`） | HC-03 + 宿主 `discover` 的 `unsupported plugin API version` 失败 |
| M2-03 | locator 在 Core 缺失时**静默忽略并让插件半注册**（注册空壳 / 回退内置） | HC-10：必须 422 且 `sources/` 无残留、`items` 无该插件 |
| M2-04 | 把 Core 源码打进 plugin zip | E18 的整文件字节包含扫描；HC 中 zip 文件清单断言 |
| M2-05 | reload 复用陈旧模块（构建 / 测试里缓存 `amane_ext*`） | HC-07 哨兵常量必须在 reload 后变化 |
| M2-06 | 配置变更不触发 rebuild（provider 仍用旧配置） | HC-08：`PATCH` 后回环日志必须反映新配置 |
| M2-07 | 版本相关分支改变映射（例如按 `multi_language` / `traits` 是否存在改字段） | E15 逐字段哈希在两宿主相等；AST 守卫禁止版本分支（U2-9） |
| M2-08 | 把仅新版存在的 API 泄漏到 v0.15.0 路径（`max_attempts` / `traits` / `check_connectivity`） | v0.15.0 宿主见证（HC-04 / HC-17）+ C1 I26 AST 守卫 + E04 子集指纹 |
| M2-09 | artifact 含禁止文件（`__pycache__`、测试、`.env`、绝对路径） | E06 allow-list / forbidden 扫描 |
| M2-10 | zip 时间戳 / 条目顺序 / 压缩方式不确定 | E06 的跨解释器、跨输出目录、CRLF 检出哈希相等 |
| M2-11 | 升级后旧模块残留（新 zip 覆盖后仍加载旧 `_impl`） | HC-09 / HC-16 的“旧哨兵不可见”断言 |
| M2-12 | Pydantic 接受而 runtime parser 拒绝（或反之）；浅合并丢键 | 第 12.2 节一致性守卫（四布尔全真或全假） |
| M2-13 | 绕过宿主 HTTP：provider 自建客户端 / 换成别的 `web_client` | E17 对象同一性 + AST 守卫 + HC-17 回环日志 |
| M2-14 | locator 不校验 wheel sha256 / 接受任意 wheel / 接受符号链接 / 接受被篡改的同名 wheel / 接受目录冒充 wheel | HC-11(a) / HC-19；E31-c / E31-i / E31-m（篡改 1 字节、替换为符号链接、超大文件、同名目录） |
| M2-15 | locator 把 pin 变化当成功（旧 Core 在内存仍放行） | HC-16 误操作分支：必须 `RESTART_TEMPLATE`；E31-b |
| M2-16 | 兼容 JSON 里把 `IDENTICAL_TO_STABLE` 的 main 伪装成独立见证 / 把 UNVERIFIED 平台写成 SUPPORTED / 以版本为 key 使版本状态覆盖平台状态 | E23 / E24 的 JSON 自洽性测试（schema + 规则）；`COMPATIBILITY.json` 派生测试 |
| M2-17 | **already loaded -> blindly trust**（`fc2_metadata_core` 已在 `sys.modules` 就接受，不核对其来自 exact pinned wheel） | E31-b / c / d / e / j（HC-19 的预加载分支）：错误 / 目录形态 / 混合来源的已加载 Core 必须 FAIL |
| M2-18 | **接受任何目录形态 Core**（pip / 解压 / editable / 源码 / `PYTHONPATH`），无论是否比对版本或 `*.py` 树哈希；或恢复 `unverified-path -> ACCEPT` | E31-d / e / f / h：目录形态必须 FAIL（即使字节正确）；有 sidecar 时目录形态 Core 不被执行（E31-g） |
| M2-19 | 移除遮蔽 / 同根防御（不做预解析或最终真实解析；不检查所有 `fc2_metadata_core*` 子模块同根；不检查 `loader` 是 `zipimporter` 且 `archive` 匹配） | E31-j / k / l |
| M2-20 | locator 在失败或 pin 变化时 purge `fc2_metadata_core*` / 热切换；或**失败路径不回滚 `sys.path`**（留下半插入的 wheel 条目） | E31-l / n；U2-11 的 AST 守卫（locator 无 `del sys.modules[...]` / `sys.modules.pop` / 对 `sys.modules` 的赋值） |
| M2-21 | **目录形态 Core 含有未被 `*.py` 树哈希表示的可执行 `.pyc`**（即 R1 设计：按 `*.py` 树哈希接受目录形态） | **E31-h pyc 准入场景**：恶意 pyc（相同 mtime / size）必须 FAIL / 不被执行；payload sentinel 必须不存在；3.12 与 3.14 均执行 |
| M2-22 | **artifact 派生环**：`COMPATIBILITY.json` / `INSTALL.zh-CN.md` / `VERSION` 内嵌 `SHA256SUMS` / release bundle / 自身的哈希，或 `SHA256SUMS` 列出自身，或 L2 投影读取 Part B | E29 DAG 测试：拓扑检查、禁止字段扫描、改 Part B 不改 L2–L4、`sha256sum -c`、从仓库树重建逐字节一致 |
| M2-23 | **existing-wheel 分支不做最终真实解析就返回成功**（“wheel 已在 `sys.path` -> 立即幂等成功”，不执行 2E） | **E31-u**：wheel 已在 `sys.path`、更靠前有惰性的不受支持来源 -> 必须 FAIL；变异后该用例会错误地 PASS，必须被判定为 KILLED（同时 E31-p 断言第二次调用仍执行 2E） |

> mutation 以**可复现的补丁脚本 + 测试**实施（C1 `test_amane_mutation_nonvacuity.py` 同法）：对**临时副本**应用 mutant，断言对应 killer 失败；**不修改**工作树。

---

## 17. 测试环境

| 用途 | 解释器 |
|---|---|
| 主项目 regression（含新增纯逻辑测试） | 项目正式 Python **3.12.x** |
| 宿主源码见证（HOST-A-SRC / HOST-B-SRC / HOST-C-MAIN / HOST-MID） | **3.14.x**；**两个版本各自独立 venv**（依赖锁不同），不共享 |
| 冻结包见证（HOST-*-WIN） | 包内置 3.14.7，**不使用**本机解释器 |
| 构建确定性（E06） | 3.12 与 3.14 各构建一次 |

* P5-C1 要求的 3.14 证据集 A / B 作为**回归**在 3.14 上重跑（计划第 5 节）。
* 若某个宿主版本日后要求不同 Python 版本，则该版本使用独立 venv；**不**强求单一解释器覆盖全部宿主。

---

## 18. P5-C2 与 Phase 6 的边界

P5-C2 结束时：Amane adapter **可安装、可发现、可配置、可 reload、在已验证支持坐标（SC-01..SC-04）上兼容、最终 artifact 可交付**。
P5-C2 **不做**：Phase 6 批处理工作流；真实用户媒体批量运行；Organizer UI；批处理 scheduler；真实大规模公网验收；**真实 scrape 任务端到端**（需要媒体库 / 任务系统，属 Phase 6）。

---

## 19. 不变量（P5-C2 新增；P5-C1 I1-I26 全部继续有效）

```text
I-C2-1  _impl/ 内容 = P5-C1 树的 LF 规范化字节（normalized-byte identity）；tree_sha256(_impl) == C1 见证的 adapter_tree_sha256（同一 CRLF -> LF 规范化）
I-C2-2  plugin zip 不含 Core 的任何文件（不 vendor）
I-C2-3  shim / locator 纯 stdlib；不写文件；不联网；不 import amane / pydantic / Core
I-C2-4  宿主入口契约不变（Plugin、id、api_version）
I-C2-5  reload / 升级后 shim 与 _impl 模块无陈旧残留
I-C2-6  生产代码无版本分支、无异常文本解析、无私有 monkeypatch、无 feature detection
I-C2-7  Core 与 plugin 精确配对；Core 变更必须 bump 版本（发布台账）；**唯一被接受的 Core 执行形态是 exact pinned wheel**，其它形态（目录 / pip / editable / 源码 / 已加载的非该 wheel）一律 fail closed
I-C2-8  sidecar 仅在 wheel 的文件名 == pin、整个 wheel 的 sha256 == pin、普通文件、非符号链接、大小有界、origin 同根时加载；未配对 / 篡改 / 符号链接 / 超大 / 目录冒充 -> fail closed 且不半注册
I-C2-9  不覆盖、不移动、不写入用户文件；验收只用临时目录
I-C2-10 兼容见证 JSON 确定、自洽；UNVERIFIED 不得声明为 SUPPORTED；IDENTICAL_TO_STABLE 不计作独立见证
I-C2-11 宿主差异只允许白名单 DIFF-01..DIFF-07
I-C2-12 已加载的 Core 不得被盲信：必须证明来自同一个 exact pinned wheel（`type(loader) is zipimporter`、当前 origin、当前 wheel 字节符合 pin）且所有 `fc2_metadata_core*` 同根；这是 current-origin + current-artifact proof，**不是**历史已执行字节证明；证明不了 -> RESTART / PIN MISMATCH；不 purge、不热切换
I-C2-13 没有任何目录形态 / `unverified-path` 的接受路径；locator 不实现树哈希、不验证 pyc
I-C2-14 支持声明以 `(version, host_form, platform)` 为坐标；版本状态不得覆盖平台状态；UNVERIFIED 坐标不得出现在支持声明里
I-C2-15 失败路径后 `sys.path` 与入口逐元素相同（同一 list 对象）、`sys.modules` 中 `fc2_metadata_core*` 对象身份不变、verified-wheel 的 importer-cache 条目回到入口状态（不承诺恢复全局 importer cache）；成功路径至多一次 locator-owned 插入、幂等
I-C2-16 完整性保证 = admission-time integrity，**不是** runtime immutability；SHA-256 pin 不是 publisher authenticity / 签名 / 运行期防篡改（第 8.8 节）
I-C2-17 artifact 派生 DAG 严格无环：任何成员的内容不依赖其自身或更高层 artifact 的哈希（第 10.5 节）
I-C2-18 **NO SUCCESS RETURN UNTIL ACTUAL CURRENT RESOLUTION PROVES THE EXACT PINNED WHEEL**：每一个成功返回（含 wheel 已在 `sys.path` 的分支、重复调用）之前都必须有对实际当前 import 解析的最终证明；预解析不是准入；不存在“wheel 在 `sys.path` 中 -> 立即成功”的路径
I-C2-19 受信 loader 判据 = `type(spec.loader) is zipimport.zipimporter`（精确类型）；子类 / 其它 loader 一律不被信任；本合同不支持任何其它具体 loader
```

---

## 20. 已知局限（如实记录；进入 E30）

| ID | 局限 |
|---|---|
| L-C2-01 | macOS 冻结包 / Linux / Docker：设计环境无对应宿主，`UNVERIFIED`；纯 Python 且无平台相关代码，但**不声称已验证** |
| L-C2-02 | 坐标 SC-02 / SC-04（`(v0.18.0, frozen desktop | source host, Windows x64)`）为 `CONDITIONALLY_SUPPORTED`：设计期只完成 API 差异阅读与冻结包 sidecar 探针，**尚未**在 v0.18.0 上跑 adapter 全场景 |
| L-C2-03 | 桌面用户忘记放置 sidecar 时看到的是 P5-C1 冻结消息（“请在 Amane 所在的 Python 环境中安装”）；为不改 CLOSED 的 `_core_gate` 而接受 |
| L-C2-04 | **（已由 R2 取代）** 目录形态 Core（pip / 解压 / editable / 源码）**不再被接受**，因此不存在“只比版本”“只哈希 `*.py`”或 `unverified-path` 的弱保证；代价：开发者 / 源码宿主也必须使用 sidecar wheel（由 `tools/build_core_wheel.py` 构建），不能直接使用 editable 安装的 Core |
| L-C2-05 | Core 升级需重启（W2-02）；热切换被拒绝 |
| L-C2-06 | 宿主 v0.18.0 的网络检测页将按 `descriptor.urls[0]` 探测（adapter 不覆盖 `check_connectivity`）；v0.15.0 无此功能 |
| L-C2-07 | 宿主 `PATCH` 对 `config` 做顶层浅合并，无法通过省略键恢复默认 |
| L-C2-08 | `WebClient.request` 在 v0.15.0 `max_retries=0` 时零请求（C1 L-04）；v0.18.0 已修复（DIFF-02） |
| L-C2-09 | Amane 官方不承诺插件可依赖外部代码；sidecar 是本项目为冻结宿主选择的受控方式，不等于 Amane 的官方支持 |
| L-C2-10 | 真实站点网络冒烟与真实 scrape 任务端到端不在本包（Phase 6） |
| L-C2-11 | C1 L-01..L-15 继续成立 |
| L-C2-12 | 宿主「选择服务器路径」安装（`install_plugin_path`）若指向数据目录**之外**的插件目录，locator 无法由 `__file__` 推出数据目录，sidecar 不会被找到；官方安装流程只使用「上传 zip」，`INSTALL.zh-CN.md` 明示，且 HC 不把该路径作为必需场景 |
| L-C2-13 | **ACCEPTED SECURITY LIMITATION**：校验只保证**准入时刻**的完整性；wheel 被 zipimport 在进程生命周期内懒读取，准入之后对该 wheel 的持续写入者**不被防御**（威胁模型 N-03）；已加载 Core 的证明只是 current-origin + current-artifact proof，不是历史已执行字节证明。不设计消除方案；文档要求“运行期间不要替换或删除 sidecar wheel”；Core 升级严格 `uninstall -> restart -> replace -> install`。能改写数据目录者本已能改写插件树与 pin（N-01） |
| L-C2-14 | **（A1-2）** pinned 宿主（v0.15.0 / v0.18.0，逐字节相同的路由）对 `.zip` 名、非 ZIP 字节的上传返回 HTTP 500（未捕获 `zipfile.BadZipFile`），无残留；与 plugin 无关；仅对该 exact 变体与这两个 pinned 版本冻结 |
| L-C2-15 | **（A1-3）** 真实宿主的符号链接 sidecar 子项依赖创建 file symlink 的 OS 权限；无该能力的环境里记为 `ENVIRONMENTALLY_UNAVAILABLE`，以单元层替身 + M2-14 killer 作替代证据，是否足够由 Reviewer 裁决 |
| L-C2-16 | **（A1-4）** E16-B 在宿主进程内以生产映射路径证明 `SourceErrorKind` 全部成员的 `FailureReason` / `detail`，不是端到端传输证据；端到端只覆盖 `K_A` |

---

## 21. 状态

```text
P5-C2 Design R3      : CANDIDATE — INCREMENTAL DESIGN CLOSURE REVIEW REQUIRED
Contract             : CANDIDATE（本文；含 Design Pre-Review R1、Design R2、Design R3 修订）
Construction Plan    : CANDIDATE（docs/P5_C2_CONSTRUCTION_PLAN.md）
Risk Class           : C
Implementation       : NOT STARTED
Package Frozen Base  : CANDIDATE — subject to Design Review
```

本文不得被解读为 FROZEN / DESIGN PASS / IMPLEMENTATION AUTHORIZED / CLOSED。唯一 authority 转换：独立 Design R3 Incremental Closure Review PASS -> 该 Review 建立 Design Accepted Head -> Frozen Contract / Construction Plan -> 才允许进入 S1。
S1 -> S2 -> S3 连续施工的意图保持不变；无需新增 S 级 Review。

**Pre-L1 Authority Amendment A1（本文最新状态）**：Design 已经独立 Review 并冻结（Design Accepted Head `f358aca1…`）；Implementation 完成于 `4358b3df…`，但在送独立 Level 1 Review 之前发现 U2-5 已被触发（见 11.7 与文末修订记录）。本 amendment 只冻结真实宿主事实与证据方法，状态 = **CANDIDATE**，等待独立 Authority Amendment Review；在其结论建立之前，Implementation 保持“COMPLETE CANDIDATE — NOT TECHNICALLY ACCEPTED”。

### Design Pre-Review R1 修订记录（历史；docs-only；Parent = `8870df0ea42e60dd142a5878ea7c0abc6ca3c4b5`；**其中目录形态 Core 的接受规则已被 Design R2 取代**）

| ID | 问题 | 修订 |
|---|---|---|
| C2-DESIGN-R1-01 | 第 2 节写了“Governance > P5-C1 Frozen Contract”，与 Acceleration v2 第 4 节冻结的 authority priority 冲突 | 改为领域化 authority：P5-C1 Frozen Contract / Plan（CLOSED semantics）> P5-C2 Accepted Contract（compatibility / supply / release）> P5-C2 Accepted Plan > Acceleration v2 > Task Prompt；P5-C2 不得静默 override P5-C1 CLOSED semantics，必须改变则 U2-1 / U2-6 / U2-7 STOP + authority amendment |
| C2-DESIGN-R1-02 | Risk Class B 候选 | 升为 **C**；理由 = 新建外部可执行 artifact 信任边界（sidecar -> 校验 -> pin -> `sys.path` -> 宿主进程内可执行），不是“用了 `sys.path`”；Risk C 不自动拆分 S1/S2/S3；增加 Security Review Focus（Design Review 必审第 8 节）与 Final C-level Review 独立执行 locator / security 证据（E31）；第 5 节重写 |
| C2-DESIGN-R1-03 | 已加载 Core 可能被直接接受；无发行元数据的源码 / editable `unverified-path -> ACCEPT`；pip 只比版本 | 第 8.3 节重写：**每种执行模式都必须证明精确 pin**（sidecar = 文件名 + wheel sha256；pip = 版本 + Core 树哈希；editable / 源码 = Core 树哈希；已加载 = 按来源重新证明 + 子模块同根）；删除 `unverified-path`；增加目录形态附加准入（防 `.pyd` / `.so` / `.pth` / 符号链接）；loaded != pinned 一律 RESTART / PIN MISMATCH，不 purge、不热切换；新增 U2-11 / U2-12、不变量 I-C2-12 / 13、模板 `TREE_MISMATCH` / `UNVERIFIABLE`；设计期 W2-11 验证了安装树哈希可复现 pin |
| （R1-03 证据） | 需要 PASS / FAIL 配对证据与 mutant | 新增 **C2-E31**（E31-a..q）、HC-19、M2-17..M2-20；扩展 M2-14 / M2-15；E05 / E14 / E20 / E30 同步 |
| （R1-03 局限） | L-C2-04 弱保证 | 取消并改写；新增 L-C2-13（TOCTOU，如实） |
| C2-DESIGN-R1-04 | 支持声明只以 `{v0.15.0, v0.18.0}` 版本集表达 | 第 7.2 节冻结**二维支持坐标** `(version, host_form, platform)`：SC-01..SC-09；Windows x64 desktop = 必需受支持部署；source host = 必需集成兼容；macOS / Linux / Docker = UNVERIFIED（本环境无 Docker，不为扩大声明增加环境依赖）；版本状态不得覆盖平台状态；`COMPATIBILITY.json.status`、`INSTALL.zh-CN.md`、E24 共用同一份坐标表；Docker 安装步骤若保留必须标 `UNVERIFIED / informational`；I-C2-14、M2-16 扩展 |
| （不变） | — | 当前稳定版坐标不变（v0.18.0 / `0a8a731d…`；main == stable，Owner 已独立核实）；P5-C1 映射 / 桥 / SearchQuery / MediaMetadata / 错误 / 归属不动；`_impl` 字节原样；无 vendor；无 `src/**`；无 `pyproject.toml` 改动；无自动 pip 安装器；无热切换 Core |

### Design R2 修订记录（历史；docs-only；一次统一修订；Parent = `5dac181f3b948ed0bcdfcedf34100ab1536e41ee`；其中 R-01..R-06 的主体修复经增量审计成立，R2 直接引入 / 遗留的 R2-A-01..A-05 由 Design R3 收口）

| Finding | 修订 | 状态 |
|---|---|---|
| P5-C2-DESIGN-R-01（目录形态可执行字节绕过） | **删除目录形态 Core 的接受**：唯一被接受的 Core 形态 = exact pinned wheel（文件名 + 整个 wheel 的 sha256 + 普通文件 + 非符号链接 + 大小有界 + 同根 origin）；已加载 Core 必须证明来自同一个 exact pinned wheel；pip / 解压 / editable / 源码 / `PYTHONPATH` 目录 = `UNVERIFIABLE`（即使字节正确）。locator 不再实现树哈希、不验证 pyc。设计期**复现了 Reviewer 的 `.pyc` PoC**（W2-12，3.12.10 / 3.14.7），并用 wheel-only 原型证明目录形态在任何 import 之前被拒绝（W2-13）。host form 与 Core supply form 分离：源码宿主同样使用 sidecar wheel；`pip` 仅用于准备宿主 venv。E31 / HC-19 / M2-14..M2-22 同步重写（新增 E31-h 恶意 pyc 场景与 M2-21 killer）；U2-11 / U2-12、I-C2-7 / 8 / 12 / 13、L-C2-04、W2-11 同步 | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-02（威胁模型与 TOCTOU） | 新增第 8.8 节 **Threat Model**：Defended D-01..D-12、Not Defended N-01..N-06、Non-claims；L-C2-13 裁决为 **ACCEPTED SECURITY LIMITATION**（zipimport 在进程生命周期内懒读取，不是“很小的窗口”）；保证性质冻结为 **admission-time integrity，不是 runtime immutability**；SHA-256 pin = integrity / exact-pairing evidence，**不是** publisher authenticity / 签名 / 运行期防篡改；签名清单属未来增强；INSTALL 必须写明“运行期间不要替换或删除 sidecar wheel”，Core 升级严格 uninstall -> restart -> replace -> install；新增 E31-t 措辞守卫 | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-03（失败回滚 / `sys.path` 原子性） | 第 8.3 节冻结：**预解析**（不修改 `sys.path`：按 `sys.meta_path` 顺序用 `PathFinder.find_spec(name, [wheel] + sys.path)` 与其它 finder 解析）-> 单次 locator-owned 插入 -> 插入后再验证；再验证失败则 `sys.path[:] = before` 回滚（同一 list 对象、不触碰原有相同条目、清除新增的 `sys.path_importer_cache` 条目、`sys.modules` 从未改动）；成功至多一次插入、重复调用幂等、已加载正确 Core 不改 `sys.path`；E31-l / n / p 机械验证每个 FAIL 的 `sys.path` 与 `sys.modules` 不变；原型验证（W2-13 (d)(e)） | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-04（artifact hash 环） | 新增第 10.5 节**严格无环的派生 DAG**：L0 wheel -> L1 plugin zip / INSTALL / VERSION（无哈希）-> *验收运行（Part A）* -> L2 `COMPATIBILITY.json`（Part A 白名单投影 + L0/L1 哈希；不含自身 / `SHA256SUMS` / bundle / MATRIX 哈希）-> L3 `SHA256SUMS`（5 个成员，不含自身）-> L4 bundle -> L5 外部（MATRIX Part B `final_artifacts` + HANDOFF，不写回 bundle）；冻结 6 步生成顺序与 MATRIX Part A / Part B 字段边界；14.1 schema 拆分；E29 DAG 测试与 M2-22；DAG 探针（W2-14） | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-05（支持措辞） | 全文消除无平台限定的“受支持版本 / 当前稳定版 CONDITIONALLY SUPPORTED”：顶层仅写 “version compatibility target = v0.15.0 and v0.18.0” 并紧接 “support claim is coordinate-scoped, not version-global”；状态只按坐标陈述（SC-02 / SC-04 为 `CONDITIONALLY_SUPPORTED` 等）；“最低支持版本”改为“最低版本目标”；L-C2-02 / 第 13 节 / 第 18 节 / 声明用语冻结同步 | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| P5-C2-DESIGN-R-06（术语 / zipimport 精确性） | wheel 形态的 verified root = 精确的 `.whl` 归档路径（`zipimporter.archive`），模块 origin 在**同一归档内**；包的 `submodule_search_locations` 是**归档内路径**，不再用“恰好一个目录”描述（W2-13 在 3.12.10 / 3.14.7 实测）；`_impl` 统一为 **LF 规范化字节（派生自 `adapters/amane/fc2_amane_adapter/*.py`）**，`tree_sha256` 使用与 P5-C1 witness 相同的 CRLF -> LF 规范化，即 **normalized-byte identity**，不是磁盘原始字节同一（I-C2-1、第 0 / 3 / 4 / 9 / 10 节同步） | REMEDIATED — INCREMENTAL REVIEW REQUIRED |
| （保持不变） | — | Authority model、Risk Class C、Amane 坐标、API 兼容结论、支持坐标结构、sidecar 主架构、P5-C1 映射与 `_impl` 语义、Core 不 vendor、`src/**` 零改动、`pyproject.toml` 零改动、无热切换 Core、Phase 6 边界、S1/S2/S3 连续意图 |

### Design R3 修订记录（docs-only；窄范围收口；Parent = `01182642eccbed299577b35d4e9f88efe1b36f06`）

| Finding | 修订 | 状态 |
|---|---|---|
| R2-A-01（HIGH / BLOCKING；“wheel 已在 `sys.path` -> 幂等成功”不充分） | 冻结唯一成功规则 **NO SUCCESS RETURN UNTIL ACTUAL CURRENT RESOLUTION PROVES THE EXACT PINNED WHEEL**（I-C2-18）：2A 入口快照 -> 2B wheel 证明 -> 2C 防御性预解析（**不是**最终准入）-> 2D 仅当 wheel 不在 `sys.path` 才至多一次插入（已存在则不插入、不重排、不提升）-> **2E 对实际当前 import 解析的最终证明（两个分支都必须执行）**；2E 不满足 -> 回滚 + `UNVERIFIABLE_TEMPLATE`。选定的**唯一行为** = fail closed（不提升 / 不重排），不留给 Developer。新增 E31-u（无副作用 sentinel fixture：wheel 已在 `sys.path`、更靠前有惰性的不受支持来源 -> 必须 FAIL）、HC-19 同步、M2-23（existing-wheel 分支不做最终解析 -> killer E31-u）；E31-p 要求第二次调用仍走 2E；设计期探针 W2-15（3.12.10 / 3.14.7） | REMEDIATED — REVIEW REQUIRED |
| R2-A-02（MEDIUM；importer-cache 快照晚于预解析） | 回滚快照移到函数入口、先于**任何** probe：`entry_sys_path` + 入口时 verified-wheel 的 importer-cache 状态；失败路径恢复 `sys.path`（同一 list 对象、逐元素）并恢复 verified-wheel 的 cache 条目（入口无 -> 删除；入口有 -> 原对象）；**不承诺**恢复全局 importer cache。E31-l 改为“locator-owned verified-wheel path / cache 回滚”（含入口有 / 无 cache 条目两个子场景），E31-n 统一 `sys.path` / `sys.modules` / verified-wheel cache 三项 | REMEDIATED — REVIEW REQUIRED |
| R2-A-03（LOW；已加载 Core 措辞过强） | 已加载 Core 的证明冻结为 **current-origin + current-artifact proof，不是 historical executed-byte proof**；与 N-03 / L-C2-13（ACCEPTED 运行期可变性限制）关联；准入算法不变（第 8.3 节第 1 步、I-C2-12、第 8.8 节、E31-a、L-C2-13） | REMEDIATED — REVIEW REQUIRED |
| R2-A-04（LOW；`isinstance` 过宽） | 受信 loader 判据冻结为 `type(spec.loader) is zipimport.zipimporter`（精确类型，I-C2-19）；不扩大到其它 loader；新增 E31-v（惰性 `zipimporter` 子类 double -> FAIL；探针同时证明 `isinstance` 会接受而 `type() is` 拒绝）；E31-j 措辞同步 | REMEDIATED — REVIEW REQUIRED |
| R2-A-05（LOW；文档卫生） | 清除正文残留的“字节原样 `_impl/`”（W2-10 -> LF 规范化字节同一 / normalized-byte identity）；R1 / R2 修订记录显式标为**历史**；施工计划中 R1 时代的“每一种执行模式下 fail closed（含已加载、editable、pip）”标注 **HISTORICAL — SUPERSEDED BY R2：directory forms are no longer accepted execution modes** | REMEDIATED — REVIEW REQUIRED |
| （保持不变；仅 R3 直接回归守卫） | — | exact pinned wheel only、目录形态拒绝、Risk Class C、威胁模型与 TOCTOU 接受、artifact DAG、坐标化支持声明、Amane 坐标 / API 结论、P5-C1 normalized `_impl` 语义、不 vendor、无热切换 Core、Phase 6 边界均未重新设计 |

**R3 直接回归自查（Design R3 提交前逐项核对）**：

```text
1. 不存在任何“wheel anywhere in sys.path -> immediate success”的路径（2D 只决定是否插入；成功只来自 2E / 第 1 步）
2. 每一个 success path 都有 final actual-resolution proof（2E 或已加载分支的 current-origin + current-artifact proof）
3. 每一个发生在 locator-owned path / cache 变化之后的失败都有精确回滚；且入口快照先于任何 probe
4. 目录形态仍然被拒绝（E31-d / e / f / g / h 不变；E31-u 的惰性目录包仅是被拒绝的不受支持来源，从未被导入）
5. 没有新增被接受的 Core 来源（受信 loader 仅 type(...) is zipimporter；不支持其它 loader）
6. E31-u / M2-23 / HC-19 / E31-p / I-C2-18 描述同一个不变量
```

### 设计者希望复查者重点质疑的决定（Design R3 增量复查范围：R2-A-01..A-05 + R3 直接回归）

1. **第 8.3 节 2A..2E**：唯一成功规则是否确实消除了“wheel 已存在于 `sys.path` 即成功”的盲目幂等；选定“fail closed、不提升 / 不重排”作为唯一行为是否可接受（对比“规范化提升”：会重排 / 移动既有 `sys.path` 条目，违背“不触碰原有条目”）。
2. **入口快照 / 回滚范围**：只承诺恢复 `sys.path` 与 verified-wheel 的 importer-cache 条目（不承诺全局 cache）是否诚实且足够；2C 的 probe 造成的 cache 变化是否都被覆盖。
3. **E31-u / E31-v / M2-23 / HC-19** 是否描述同一不变量，且 fixture 是否确实惰性（不执行 payload）。
4. **A-03 措辞**与 N-03 / L-C2-13 是否一致；**A-04 精确类型判据**是否在所有出现 loader 判断的位置一致。
5. 保持项仅在 R3 直接引入回归时复查。

### Pre-L1 Authority Amendment A1 修订记录（docs-only；Parent = `4358b3df3353d634e4c2e8b1ee6b71c0a07b5ace`；只改合同与施工计划）

**治理事实（如实）**：U2-5 在 S2 / S3 期间被触发——真实宿主观测与冻结合同的宿主行为假设不一致。Implementation 继续施工并记录了事实，但没有放宽 Frozen Contract 的权限；本 amendment 在独立 Level 1 Review 之前偿还该 authority debt。
这不是 production correctness 缺陷，也不是“U2-5 从未发生”。

**逐项分类（A = 冻结设计的错误假设，可 amendment；B = implementation 缺陷，不可靠改合同通过）**

| 项 | 真实事实 | 分类 | 处理 |
|---|---|---|---|
| A1-1 HC-01 状态码 | 两个 pinned 源码声明 `status_code=201`；上游测试固定 201；四宿主观测 201 | **A** | 冻结为精确 201（不是任意 2xx） |
| A1-2 HC-12a 非 zip | 路由未捕获 `zipfile.BadZipFile`（`Exception` 子类）-> 500；两版逐字节相同；在导入之前；无残留；与 plugin 无关 | **A** | HC-12 拆 12a..12e；12a 冻结“宿主实测 500 + 拒绝 + 无残留 + 无注册 + 代码从未执行”；12b..e 保持 422 |
| A1-3 符号链接 | 非管理员 Windows 账户，Win32 1314，开发者模式未启用；真实 file symlink 在不改变系统安全设置的前提下不可得 | 环境能力限制（非 A、非 B） | locator 语义不变；原要求保留为目标；不可得时 `ENVIRONMENTALLY_UNAVAILABLE` + 必需替代证据；**充分性由 Reviewer 裁决** |
| A1-4 E16 | 端到端只观测到 7 个 kind（`K_A`）；9 个未观测到。另：用例 `kind_decode_error_bad_charset` / `kind_redirect_error_loop` / `kind_response_too_large` 实际产生的是 `parse_error+invalid_response` / `connection_error` / `parse_error+invalid_response`，标签虚称了未观测的 kind；4358b3d 的宿主内枚举只调用叶子函数 `reason_for_kind`，没有运行生产的 `AggregationResult -> 中立结果` 映射，也没有运行生产 provider 转换，`detail` 未被验证 | **A + B** | A：双轨模型（E16-A 端到端 + E16-B 全部成员在宿主进程内经生产路径）；B：**只改合同不够**，amendment 被接受后必须补 implementation evidence（见施工计划附录 E） |

**明确不属于 amendment**：`prefix == ""` 仅对顶层 `fc2_metadata_core` spec 要求（合同第 8.3 节原文），子模块使用包内 importer 前缀，实现与合同一致；不为它增加 amendment。
**不重新打开**：exact pinned wheel only、Risk Class C、R3 最终解析不变量、回滚、威胁模型 / TOCTOU、artifact DAG、支持坐标模型、P5-C1 映射语义。

**未被本 amendment 修改、留给 Reviewer 的发现（不是 amendment）**：HC-11 的 (c)“目录形态 Core 无 sidecar”一行没有“冻结包除外”的限定；冻结包忽略 `PYTHONPATH`（W2-04），无法布置该夹具，合同第 11.2 节 HC-19 已写明“冻结包只覆盖 sidecar 各分支”。
实现把 (c) 的真实宿主证据放在源码宿主的 HC-19（含真实 `PYTHONPATH` 用例）。本文**不**修改 HC-11，请 Reviewer 裁决该文字是否需要在后续 amendment 中澄清。

**设计者希望 Authority Reviewer 重点质疑的决定**：

1. A1-1：“精确 201”而非“2xx”是否是最窄且正确的冻结（上游源码 + 上游测试 + 四宿主观测）。
2. A1-2：HC-12a 的判据是否足够窄，且没有把“任意错误状态码”引入其它安装失败判据；“非 zip”的精确定义（`.zip` 名 + 非 ZIP 字节）是否合适。
3. A1-3：Option B 的替代证据是否足以关闭 Risk C 对符号链接真实宿主子项的要求；`ENVIRONMENTALLY_UNAVAILABLE` 作为 `observed` 的唯一额外取值是否可接受，是否需要更强的替代（例如要求在具备权限的环境补证）。
4. A1-4：E16-B 是否确实“不降低语义覆盖”；“全部 16 个成员 × 每个必需宿主进程 × 生产映射 + 生产 provider 转换”是否足以替代“每个 kind 一例端到端”；独立期望值的来源（P5-C1 表 F / G）是否合适。
5. 上述“未被本 amendment 修改”的 HC-11(c) 文字问题是否需要澄清。
