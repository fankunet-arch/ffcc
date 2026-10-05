# P5-C2 合同（Contract）-- Amane Compatibility & Adapter Closure

```text
状态                    : P5-C2 Design: CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
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
Design Pre-Review R1    : docs-only 修订（C2-DESIGN-R1-01..04；见文末“Design Pre-Review R1 修订记录”）；仍是 CANDIDATE，**不是** FROZEN / PASS / AUTHORIZED
Branch                  : claude/phase5-c2-amane-compatibility
```

> 本文是 **候选合同**。Design Review PASS 之前，本文不是 Frozen Contract，不授权实现。
> P5-C1（CLOSED）已冻结的全部语义（SearchQuery 映射、Core 调用、HTTP 桥、MediaMetadata 映射、错误映射、来源归属、契约测试、
> 插件树布局）**保持冻结，本文不重新设计其中任何一项**。P5-C2 只闭合 P5-C1 合同第 26 节表 J 中标记为 P5-C2 的项。

---

## 0. 一页结论（给 Reviewer）

| 问题 | 本合同的裁决 |
|---|---|
| 最低支持版本 | **Amane v0.15.0**（`45dff215…`） |
| 当前稳定版 | **v0.18.0**（`0a8a731d…`）：**CONDITIONALLY SUPPORTED**，条件 = 实现期 E15 / E16 / E22 在 v0.18.0 上 PASS；否则 BLOCKED 并给出根因 |
| 支持声明的坐标 | **二维：`(Amane 版本, 宿主形态, 平台)`**，不再只用版本。Windows x64 冻结桌面版 = 必需支持部署；源码宿主 / Python 3.14 = 必需集成兼容；macOS / Linux / Docker = **UNVERIFIED**，不属于本包的支持声明（第 7.2 节） |
| current main | 设计核对时 `main == v0.18.0`（同一 commit）；**INFORMATIONAL COMPATIBILITY WITNESS**，不是 release contract |
| 同一 artifact 能否同时跑在 v0.15.0 与 v0.18.0 | **能**：单一 plugin zip、单一 Core wheel、**无版本分支**、**生产代码内无 feature detection**（第 7 节） |
| Core 最终供给方式 | **Core sidecar wheel**（独立 wheel，由用户放进 `{data_dir}/plugins/_ffcc_core/`），由随包的 **shim locator** 在导入前校验 sha256 并加入 `sys.path`；`pip install` / 源码检出为等价的可选方式，但**每一种执行模式都必须证明与精确 pin 一致**（wheel 哈希或 Core 树哈希），已加载的 Core 也要重新验证，**fail closed**。**不 vendor、不把 Core 放进 plugin zip**（第 8 节） |
| 为什么不是纯 `pip install` | **设计期实测**：Amane 桌面版（Windows 冻结 PyInstaller 版）**忽略 `PYTHONPATH`**，且插件不能声明 pip 依赖；桌面用户没有可写的解释器环境（第 6 节 W2-04 / W2-05） |
| 怎样做到 P5-C1 零改动 | 插件 zip 内 **P5-C1 树按字节原样放进 `_impl/` 子包**；zip 根部新增一个很薄的 **shim**（`plugin.py` + `_ffcc_locator.py` + `_ffcc_pin.py`）。P5-C1 的树哈希、测试、证据、合同 §22 的缺失 Core 消息全部不变（第 9 节） |
| Risk Class | **C**。原因**不是**“用了 `sys.path`”，而是 P5-C2 新建了**外部可执行 artifact 信任边界**（sidecar wheel -> 路径 / 类型校验 -> 完整性 pin -> `sys.path` -> 宿主进程内可执行代码），它决定哪些数据目录中的外部代码可以进入宿主进程执行 = 治理定义的 security boundary（第 5 节）。Risk C **不**自动拆分 S1/S2/S3；仍 S1 -> S2 -> S3 连续 |
| 需要 Owner 的业务问题 | NONE |

---

## 1. 目的、范围与非范围

### 1.1 P5-C2 回答的问题

```text
一个普通用户，拿到官方发布包，按文档操作，能否在受支持的 Amane 版本上
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
       _impl/               [P5-C1 树，字节原样；无 __init__.py]
         plugin.py _core_gate.py _settings.py _number.py _bridge.py _runtime.py _outcome.py
  └─ {data_dir}/plugins/_ffcc_core/                        ← 用户放置（sidecar；不在 sources/ 之下）
       fc2_metadata_core-<ver>-py3-none-any.whl            ← 独立 Core 分发物（不含在 plugin zip 内）
```

依赖方向（冻结）：`shim -> _ffcc_locator / _ffcc_pin`；`shim -> _impl.plugin`（P5-C1，原样）；`_impl.* -> fc2_metadata_core`。
`Core / Organizer` 仍然永不 import Amane；`_ffcc_locator` 不 import Core、不 import Amane、不 import pydantic。

---

## 4. 治理四问（治理文档第 15 节；真实判断）

**Q1 为什么 P5-C2 不与 P5-C1 合并？**
不是“现在技术上不能合并”：P5-C1 已 CLOSED，其 logic closure（adapter 的映射 / 桥 / 错误 / 归属 / 契约测试）已有独立 Level 1 + R1 Closure Review 的 PASS
与冻结哈希（Final Reviewed Technical Head `0289b19…`）。把宿主兼容与发布 closure 合并回去，等于**重开一个已 PASS 的 logic closure 的证据**。
两者的裁决对象不同：P5-C1 回答“一个查询是否得到正确且安全的 Amane 结果”（语义，对 exact v0.15.0 公共 API + 脚本化传输）；
P5-C2 回答“官方发布包能否在受支持的真实宿主上安装、配置、重载、升级并产生等价语义”（兼容 / 发布）。前者的错误是逻辑缺陷，后者的错误是环境 / 版本 / 供给缺陷，
需要的证据（多宿主版本、冻结桌面包、artifact 哈希）与 Reviewer 视角不同。

**Q2 当前边界降低了什么风险？**
(a) 防止“为了让某个宿主版本通过”而回头修改已 PASS 的 adapter 语义（本合同用字节原样的 `_impl/` + 树哈希把它变成可机检的不变量）；
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
数据目录中的 sidecar wheel（或已安装 / 源码形态的 Core）
  -> 路径 / 类型校验（普通文件、非符号链接、大小上限、文件名 == pin）
  -> 完整性 pin（wheel sha256 或 Core 树 sha256 == pin）
  -> sys.path
  -> 在 Amane 宿主进程内作为可执行代码被导入
```

这条边界决定“**哪些数据目录中的外部代码可以进入宿主进程执行**”，属于 Acceleration v2 第 8.3 节 C 类定义中的 **security boundary**。
Amane 文档明示插件本身是进程内可信任意代码，这**不**使新增的加载路径变成“无边界”：恰恰相反，需要有明确冻结、可审、可测的准入规则（第 8.3 节），
否则“任意写入数据目录的 wheel / 任意已预装的同名包”会成为进入宿主进程的未经校验的路径。

**其余 B→C 触发项逐项检查**：

| 触发项 | 结论 | 依据 |
|---|---|---|
| 外部可执行 artifact 信任边界（security boundary） | **触发 -> Risk C** | 本节上文；第 8.3 节冻结准入规则；E31 / M2-14..M2-19 专项证据 |
| 修改 CLOSED P5-C1 semantics | 未触发 | `_impl/` = P5-C1 树字节原样；P5-C1 测试 / 证据 / 合同 / HANDOFF 零 diff；§22 缺失 Core 消息不变（第 9.3 节） |
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

1. **Security Review Focus（Design Review）**：独立 Design Review 必须**明确审**第 8 节 locator 信任边界（准入规则的完备性、fail-closed、已加载 Core 的处理、各执行模式的 pin 证明、模板与不变量、mutant 覆盖），并在结论中单独给出 security 裁决。
2. **Final C-level Review 必须独立执行 locator / security 证据**：Reviewer 在自己的 checkout 上**独立重跑**第 8.3 节全部准入分支（E31）与 M2-14..M2-19，不得仅引用 HANDOFF。

### 5.3 强制升级门（任一触发 = 立即 STOP；不得自行继续）

```text
U2-1  任何 src/** 改动                                        U2-6  需要改变 adapters/amane/fc2_amane_adapter/** 的任何字节
U2-2  Core 源码出现在 plugin zip 内（vendor / 复制 / 内嵌）     U2-7  需要改变任何已 CLOSED 测试 / 证据（P5-C1 与 Phase 1-4）
U2-3  新增持久化 / adapter 写文件 / 用户文件被写入或移动        U2-8  需要 pyproject.toml / 依赖改动（含新增 pythonpath）
U2-4  需要绕过宿主 HTTP 生命周期（自建客户端 / 浏览器回退）      U2-9  生产代码出现按版本字符串 / 异常文本 / 私有模块 monkeypatch 的分支
U2-5  真实宿主观测与本合同第 6 节设计期实证不一致              U2-10 把 Phase 6 的内容（批处理 / 真实媒体 / 公网验收）带入 C2
U2-11 locator 准入规则被放宽（接受未验证 pin 的 Core / 对已加载 Core 盲信 / unverified 模式）或出现热切换 / purge Core
U2-12 需要 pin 验证无法稳定实现（例如已安装 Core 树无法得到与 source tree 相同的哈希）而“临场降级”——必须 STOP / DESIGN BLOCKER，另找确定性指纹，不得降级
```

> U2-6 的含义：adapter 树哈希（`tree_sha256(adapters/amane/fc2_amane_adapter)`）必须仍等于 `P5_C1_HOST_WITNESS.json` 记录的
> `adapter_tree_sha256`。若实现发现必须改 P5-C1 树才能完成兼容，**这是设计前提失效**，STOP，需要 authority amendment（第 2 节）。
> U2-12 的前置事实：设计期已验证（W2-11）以 `pip install --target` 安装出的 `fc2_metadata_core` 的树哈希与 source tree 哈希及 C1 witness 的 `core_tree_sha256` 逐字相等，因此该门在设计层面**未被触发**。

### 5.4 Reviewer 的 security 复核问题（供 Design Review 的 Security Review Focus 使用）

1. 第 8.3 节的准入规则对“sidecar / pip / 源码 / 已加载”四种来源是否**无遗漏**地要求精确 pin 证明？有无可绕过的路径（`sys.path` 中靠前的同名包、`sys.modules` 预置、同名 wheel 替换、符号链接、TOCTOU）？
2. 哈希校验与实际被导入的字节之间的 TOCTOU 窗口（读文件算哈希 -> 之后 zipimport 读取）是否被接受？（设计者判断：窗口存在但信任域相同——攻击者已能写数据目录即已能改插件树；本设计通过“哈希后立刻加入 `sys.path`、并在已加载分支重验”把窗口压到最小，并记为 L-C2-13。）
3. fail-closed 的错误模板是否有界、无路径泄漏、无秘密。

---

## 6. 设计期实证（Design-time Witness）

以下为设计者在本机直接执行的核对（2026-10-05；可复现脚本见施工计划附录）。它们是**设计期观测**，不是施工证据；施工证据由第 15 节 Evidence Gate 提供。

### 6.1 Amane 坐标（直接来自 upstream `sqzw-x/amane`，只读克隆）

| 名称 | tag | tag 对象 | peeled commit | release version | `requires-python` | `PLUGIN_API_VERSION` | 备注 |
|---|---|---|---|---|---|---|---|
| **A. v0.15.0** | `v0.15.0` | `3292c957a092f85ddde1ba7462ffe9813827f4f1` | `45dff2159369883e028a296d775a4598836c1ddd` | 0.15.0 | `>=3.14` | `"1"` | 最低支持版本 |
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
| W2-10 | C1 见证测试把 adapter 树哈希与 Core 树哈希焊在 CLOSED 测试里 | `tests/amane_adapter/test_amane_host_witness_log.py` 断言 `adapter_tree_sha256 == tree_sha256(adapter tree)` 与 `core_tree_sha256 == tree_sha256(src/fc2_metadata_core)`；因此**任何对 adapter 树的字节改动都会破坏一个 CLOSED 测试**（决定第 9 节的 shim + 字节原样 `_impl/` 设计，U2-6 / U2-7） |
| W2-11 | 安装后的 Core 树哈希可复现 pin（U2-12 可行性） | 3.12 `pip install --no-deps --target <dir> <设计期 wheel>` 后，`tree_sha256(<dir>/fc2_metadata_core)` == `tree_sha256(src/fc2_metadata_core)` == `P5_C1_HOST_WITNESS.json.core_tree_sha256` == `6077cd6739424848137f2b8a1d6c37d20cc9cb3185cc94df07774169b3fda026`（逐字相等）；因此 (D1) / (D2) 的树哈希 pin 证明可行 |

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
最低支持版本                 = v0.15.0（45dff215…）
当前稳定版 v0.18.0           = CONDITIONALLY SUPPORTED     条件：E15 / E16 / E22 PASS（实现期）；否则 BLOCKED + 根因
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

* **Windows x64 desktop = 必需的受支持部署**；**source host = 必需的集成兼容**；**macOS / Linux / Docker = UNVERIFIED，不在 P5-C2 支持声明内**（不得被任何顶层“SUPPORTED”字样覆盖）。
* 声明用语冻结：`COMPATIBILITY.json`、`INSTALL.zh-CN.md`、HANDOFF 对外只能说“在 `SC-01..SC-04` 上经验证兼容”，不得写“支持 v0.15.0 / v0.18.0”这类脱离平台 / 形态的概括，也不得写“支持 Docker / macOS / Linux”。
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
| A. 独立 `pip install fc2-metadata-core` 到宿主解释器 | **保留为“可选等价方式”，不作为主路径；且同样受精确 pin 准入（版本 + Core 树哈希，第 8.3 节 (D1)）** | 桌面冻结包没有可写 / 可用的解释器环境，且忽略 `PYTHONPATH`（W2-04）；Docker 镜像重建会丢失；宿主文档不承诺 |
| B. 项目 wheel（现有 `pip wheel .`） | **否** | 产物含 `fc2_organizer`（W2-06），不是 Core only；字节不确定（W2-09）；改 `pyproject.toml` 违反 U2-8 |
| C. installer-assisted（自动 pip） | **否** | 引入新的可执行安装器 / 网络 / 包管理器依赖，扩大攻击面；冻结宿主无 pip |
| D. 把 Core 目录放进 plugin zip（vendor） | **否（U2-2）** | 违反“不 vendor”；需要 authority amendment，本包不申请 |
| E. 向 `{data_dir}` 写入时由插件自行解压 Core | **否** | adapter 写文件违反 I14 / U2-3 |
| **F. Core sidecar wheel + 随包 shim locator（zipimport）** | **采纳** | 唯一在冻结桌面宿主上被实测可行的方式（W2-05）；Core 保持独立分发物；adapter 不写文件；pin 做到精确配对与完整性校验；同一 artifact 适配所有宿主形态 |
| G. 允许 pip / 源码 / editable 与 sidecar 并存 | **采纳（locator 的优先级：已加载 -> 有效 sidecar -> 预装；每种形态都必须证明精确 pin）** | 已有环境（开发者 / 源码形态）无需 sidecar；但**不**因“已经安装 / 已经导入 / 是源码检出”而免于校验 |

### 8.3 shim locator 的冻结行为（`_ffcc_locator.py`；纯 stdlib；3.11-3.14 语法；Risk C 信任边界的**准入规则**）

**总原则（C2-DESIGN-R1-03）：每一种执行模式都必须证明与精确 pin 一致；证明不了就 fail closed（`ImportError`），不因“已经导入”“有发行元数据”“是源码检出”而接受。**
**禁止** `unverified-path -> ACCEPT`；**禁止**对已加载 Core 盲信；**禁止** purge / 热切换 Core。

`_ffcc_pin.py`（构建期生成，**只含字面量**）：

```text
PIN_SCHEMA_VERSION = 1
CORE_DIST_NAME     = "fc2-metadata-core"
CORE_VERSION       = "<pyproject [project].version>"
CORE_WHEEL_NAME    = "fc2_metadata_core-<CORE_VERSION>-py3-none-any.whl"
CORE_WHEEL_SHA256  = "<64 hex>"
CORE_TREE_SHA256   = "<tree_sha256(src/fc2_metadata_core)>"   # 与 C1 witness 的 core_tree_sha256 同一算法（见下）
SIDECAR_DIRNAME    = "_ffcc_core"
```

**树哈希算法（冻结；与 C1 `tools/run_amane_host_witness.tree_sha256` 逐字相同，由测试对拍）**：对包目录 `root` 下全部 `*.py`（排除路径含 `__pycache__` 的），按相对 posix 路径排序；
`digest = sha256()`；每个文件 `data = 文件字节.replace(b"\r\n", b"\n")`；`digest.update(相对路径.encode("utf-8") + b"\0" + sha256(data).hexdigest().encode("ascii") + b"\n")`；结果取 `hexdigest()`。
locator 以纯 stdlib **重新实现**该算法（不 import C1 工具），并由测试断言与 C1 实现、`P5_C1_HOST_WITNESS.json.core_tree_sha256`（设计期值 `6077cd67…a026`）相等。

**目录形态的附加准入（防止“哈希只覆盖 `*.py`”被绕过）**：Core 包目录内**只允许** `*.py` 与 `__pycache__/*.pyc`；出现任何其它文件（尤其 `.pyd` / `.so` / `.pth` / `__pycache__` 之外的 `.pyc`）、符号链接、文件数 `> 2000` 或总字节数 `> 16 MiB` -> 拒绝（`TREE_MISMATCH_TEMPLATE`）。

**定位（不导入 Core）**：已加载则取 `sys.modules["fc2_metadata_core"].__spec__`；未加载则 `importlib.util.find_spec("fc2_metadata_core")`。
`spec is None`（未加载时）= 无预装 Core；`spec` 缺失 / `submodule_search_locations` 不是恰好 1 个目录 / `origin` 无法归类为下面 (W) 或 (D) = **无法验证 -> 拒绝**。

**准入分类（对“已加载”与“将被导入”的 Core 使用**同一套**证明）**：

| 形态 | 判定 | 必须满足（否则 fail closed） |
|---|---|---|
| **(W) wheel / sidecar** | `origin` 位于某个 `*.whl` 文件内部 | wheel 文件名 == `CORE_WHEEL_NAME`；是**普通文件**（非目录 / 非符号链接）；大小 `<= 16 MiB`；`sha256(整个 wheel) == CORE_WHEEL_SHA256` |
| **(D1) pip / 已解压 site-packages** | `origin` 为文件系统目录下的 `__init__.py`，且 `importlib.metadata.version("fc2-metadata-core")` 可得 | `version == CORE_VERSION` **且** 该包目录的 `tree_sha256 == CORE_TREE_SHA256`（含上面的附加准入） |
| **(D2) editable / 源码检出** | 同 (D1) 但**没有**发行元数据 | **不得**因缺少元数据而接受：该包目录的 `tree_sha256 == CORE_TREE_SHA256`（含附加准入）才接受；可在见证中记录 `origin = source/editable`，但 **integrity 必须是 VERIFIED** |

**已加载的 Core 不能盲信**：`sys.modules` 中已有 `fc2_metadata_core` 时，按其 `__spec__.origin / __file__` 定位 (W) 或 (D)，执行与上表**完全相同**的证明；**另外**要求 `sys.modules` 中所有名为 `fc2_metadata_core` 或以 `fc2_metadata_core.` 开头的条目，其 `__spec__.origin / __file__` 都位于**同一个已验证根**（同一 wheel 或同一包目录）之内（拒绝被预置 / 混合来源的子模块）。
不能证明 -> `ImportError(RESTART_TEMPLATE)`。**不尝试 purge / 热切换**：loaded Core != pinned Core 一律是 RESTART / PIN MISMATCH。特别覆盖：**预先加载了错误的 pip Core / 错误的 editable Core / 被篡改的同名 sidecar wheel**。

`ensure_core(pin, module_file)` 按固定顺序执行（**无网络、无写文件、无子进程**；只做 `stat` / 读文件做哈希 / 读 `sys.modules` / `sys.path` 修改）：

1. **已加载**：若 `sys.modules` 已含 `fc2_metadata_core` -> 按上述“已加载”规则证明；通过 -> 接受（同一配对的重复发现 / reload 是常态路径，幂等；**不**修改 `sys.path`）；不通过 -> `ImportError(RESTART_TEMPLATE)`。
2. **sidecar（优先于未验证的预装 Core）**：由 `module_file`（shim 的 `__file__`）向上逐级查找第一个满足 `p.name == "sources" and p.parent.name == "plugins"` 的目录 `p`，`data_dir = p.parent.parent`
   （同时覆盖 `sources/.staging/<x>/` 的安装前检查阶段与 `sources/ffcc.fc2-metadata/` 的正式加载阶段；找不到 -> 视为“无 sidecar”，不报错）。`sidecar = data_dir / "plugins" / "_ffcc_core"`：
   * 目录不存在 -> “无 sidecar”；
   * 存在但**不含** `CORE_WHEEL_NAME`：若含其它 `fc2_metadata_core-*.whl` -> `ImportError(WHEEL_VERSION_MISMATCH_TEMPLATE)`（升级 plugin 而未换 Core 的典型错误），否则“无 sidecar”；
   * 含 `CORE_WHEEL_NAME`：按 (W) 证明（普通文件 / 非符号链接 / 大小 / sha256），失败 -> `ImportError(WHEEL_HASH_MISMATCH_TEMPLATE)`；通过后若该路径**不在** `sys.path` 则 `sys.path.insert(0, str(wheel))`（幂等）；
     随后**再次**用 `find_spec` 确认将被导入的 Core 的 `origin` 位于该已验证 wheel 内（防被更靠前的同名包遮蔽），否则 `ImportError(UNVERIFIABLE_TEMPLATE)`。
3. **预装（pip / 源码 / editable）**：无有效 sidecar 时，若 `find_spec("fc2_metadata_core")` 非 `None` -> 按 (D1) / (D2)（或 (W)）证明；版本不符 -> `ImportError(PIN_MISMATCH_TEMPLATE)`；树不符 / 附加准入不通过 -> `ImportError(TREE_MISMATCH_TEMPLATE)`；无法归类 -> `ImportError(UNVERIFIABLE_TEMPLATE)`；通过 -> 接受（**不**修改 `sys.path`）。
4. **都没有**：**什么也不做，不抛出**。随后 `_impl.plugin` 的顶层 import 失败，由 **P5-C1 `_core_gate` 产生 P5-C1 §22 冻结的固定消息**（第 8.7 节）。

shim 的固定模板（有界、无密钥、无绝对路径、无 `repr` of 外部数据；`<>` 内为构建期固定字面量）：

```text
RESTART_TEMPLATE                : "FC2 Metadata Core 已加载的版本与插件不配对（或无法验证）：请先卸载旧版插件并重启 Amane，再安装与之配对的新版（需要 Core <CORE_VERSION>）"
PIN_MISMATCH_TEMPLATE           : "FC2 Metadata Core 版本与插件不配对：需要 <CORE_VERSION>"
TREE_MISMATCH_TEMPLATE          : "FC2 Metadata Core 安装内容与插件配对记录不一致（树校验失败）：需要 Core <CORE_VERSION>"
UNVERIFIABLE_TEMPLATE           : "FC2 Metadata Core 的来源无法验证（已拒绝加载）：请使用官方发布包的 sidecar 方式，或安装与插件配对的 Core <CORE_VERSION>"
WHEEL_VERSION_MISMATCH_TEMPLATE : "FC2 Metadata Core 随附包版本与插件不配对：请在 <Amane 数据目录>/plugins/_ffcc_core/ 中放入 <CORE_WHEEL_NAME>"
WHEEL_HASH_MISMATCH_TEMPLATE    : "FC2 Metadata Core 随附包校验失败（sha256 与插件配对记录不一致）：请重新获取官方发布包中的 <CORE_WHEEL_NAME>"
```

**设计期可行性验证（W2-11）**：以 3.12 对设计期 wheel 做 `pip install --no-deps --target <dir>`，安装出的 `fc2_metadata_core` 的 `tree_sha256` 与 `src/fc2_metadata_core` 的 `tree_sha256` 及 `P5_C1_HOST_WITNESS.json.core_tree_sha256` **逐字相等**（`6077cd6739424848137f2b8a1d6c37d20cc9cb3185cc94df07774169b3fda026`）。因此 (D1) / (D2) 的 pin 证明在设计层面可行（U2-12 未触发）。

**不属于本准入规则的内容（如实）**：哈希校验与随后 zipimport / import 实际读取之间存在 TOCTOU 窗口（L-C2-13）；locator 不尝试防御“已能改写宿主进程内存 / 数据目录且能同时改写插件树与 pin”的攻击者（其已拥有同等执行权限）。

### 8.4 最终安装流程（普通用户，按文档可从零成功）

官方 **release bundle**（第 10 节）同时包含 plugin zip、Core wheel、校验清单与安装说明。

```text
1. 打开 Amane 的数据目录（桌面版托盘「打开数据目录」）。（Docker 的 `/data` 卷同理，但 **Docker 为 UNVERIFIED / informational：不在本发布验收覆盖范围内**，见第 7.2 节 SC-09。）
2. 在其下创建文件夹 plugins/_ffcc_core/（若 plugins/ 不存在则一并创建），把 bundle 中的
   fc2_metadata_core-<ver>-py3-none-any.whl 复制进去。（核对 SHA256SUMS 为可选建议，locator 会在加载时强制校验。）
3. 在 Amane「管理 → 插件」上传 bundle 中的 ffcc.fc2-metadata-<ver>.zip。成功后插件即出现在列表，无需重启。
4. 在「设置 → 影片刮削 → 内容路由」中，把 ffcc.fc2-metadata 加入 FC2 内容类型的来源列表（P5-C1 / Amane 的既有机制）。
5. 在「管理 → 插件」中按需修改配置（第 12 节）。
```

* 若已有可用的 `pip` 环境（源码宿主）：可改为 `pip install <wheel>`，**无需**第 2 步；locator 走第 8.3 节第 3 步，**同样校验** `version == CORE_VERSION` 与 Core 树哈希，校验不过则 fail closed。两种方式二选一。Docker 自建镜像同理，但 **UNVERIFIED / informational**。
* 顺序要求来自 W2-01：**Core 必须先到位，再装插件**；否则第 3 步以可读的 422（见第 8.7 节）失败，**不会**留下半装状态（宿主在 `inspect` 失败时不提交目录）。

### 8.5 plugin 与 Core 的配对关系

* plugin 版本 = C1 `PLUGIN_VERSION`（由构建器从 `_settings.py` 以 AST 读取，**不 import**）。
* Core 版本 = `pyproject.toml [project].version`（`tomllib` 读取，不改文件）。
* **Core 发布台账** `adapters/amane/release/core_release_ledger.json`：`{version -> core_tree_sha256, wheel_sha256}`。构建器**拒绝**“同一 Core 版本、不同 tree 哈希”（即：改了 Core 源码就必须 bump Core 版本）——这使“以版本判断重启 / 配对”可靠（第 8.3 节；真正的完整性由 wheel 哈希 / Core 树哈希保证，版本只是人类可读的配对标签）。
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
| 预装 / 源码 / editable 的 Core 版本或树哈希与 pin 不符、来源无法验证、含非 `.py` 文件 | `PIN_MISMATCH_TEMPLATE` / `TREE_MISMATCH_TEMPLATE` / `UNVERIFIABLE_TEMPLATE`（fail closed；**不**回退到“反正能导入就接受”） |
| 进程内已加载的 Core 不是（或无法证明是）pin 指定的 Core | `RESTART_TEMPLATE`（fail closed；不 purge、不热切换） |
| Core 已安装但版本不兼容（缺公共名字） | P5-C1 §22（`ImportError` 同一模板） |

> 取舍（如实）：桌面用户在“忘记第 2 步”时看到的是 P5-C1 冻结消息（“请在 Amane 所在的 Python 环境中安装”），对桌面用户不够友好。
> 这是为了**不改动** P5-C1 的 `_core_gate` 与其 CLOSED 测试（U2-6 / U2-7）所做的有意取舍；`INSTALL.zh-CN.md` 第 1 节以显著位置写明“桌面版请使用 sidecar 目录，不要 pip”。记为 L-C2-03。

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
                                          ← adapters/amane/fc2_amane_adapter/*.py 字节原样（LF 规范化后），无 __init__.py
```

shim `plugin.py` 的全部内容（冻结形状；Developer 不得增加逻辑）：

```text
from ._ffcc_locator import ensure_core
from . import _ffcc_pin
ensure_core(_ffcc_pin, __file__)
from ._impl.plugin import Plugin   # noqa: E402  —— 宿主要求模块字典中存在名为 Plugin 的类
```

### 9.2 不变量

* **I-C2-1**：`_impl/` 内 7 个文件的字节 == `adapters/amane/fc2_amane_adapter/*.py`（LF 规范化）；`tree_sha256(_impl) == P5_C1_HOST_WITNESS.json.adapter_tree_sha256`。
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
| `SHA256SUMS` | 按文件名排序、LF、`<sha256>␣␣<name>`；覆盖 zip、wheel、`COMPATIBILITY.json`、`INSTALL.zh-CN.md` |
| `COMPATIBILITY.json` | 兼容清单：支持**坐标**（`(version, host_form, platform)`；tag / peeled commit）、逐坐标状态（SUPPORTED / CONDITIONALLY_SUPPORTED / BLOCKED / UNVERIFIED / INFORMATIONAL）、pin、artifact 哈希、已知局限编号；与 `INSTALL.zh-CN.md`、E24 使用同一份支持坐标表；由兼容见证（第 14 节）派生，**无时间戳** |
| `INSTALL.zh-CN.md` | 第 8.4 / 8.6 / 8.7 节的用户文档（简体中文，遵循《文档语言规范》） |
| `VERSION` | 单行：`bundle <plugin_version>+core<core_version>`（无时间戳） |

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
| HC-01 | clean install：空数据目录 + sidecar 已放置 -> HTTP 上传 plugin zip | 200；`/api/plugins` 的 `items` 含 `ffcc.fc2-metadata`；`failures == []`；磁盘上 `plugins/sources/ffcc.fc2-metadata/` 的文件集合 == plugin zip 的文件集合（字节相等） |
| HC-02 | discover：重启服务进程（restart persistence） | 重启后插件仍被发现；`descriptor` 的适配器可控子集与 HC-01 相同；配置仍生效（HC-05 之后执行） |
| HC-03 | descriptor / capabilities | `id`、`name`、`version`（= `PLUGIN_VERSION`）、`capabilities == {film_metadata}`、`content_types == {fc2}`、`urls`、`api_version == "1"` 与 C1 §9 相等；`configuration_model().model_json_schema()` 与 C1 记录的 schema 相等 |
| HC-04 | provider build（真实 `CrawlerFactory`）+ 一次**离线** fetch | 子进程内：真实 `PluginManager.discover` + 真实 `CrawlerFactory`（`PluginContext(web_client=真实 WebClient)`）；`WebClient._session` 为脚本化会话（C1 H 系列同法）或**本机回环 HTTP fixture**（`base_url` 指向 `127.0.0.1`）；得到与 C1 冻结映射一致的 `MediaMetadata`；`provider` 的 `web_client` 与 `PluginContext.web_client` 是同一对象（E17） |
| HC-05 | 配置往返 | 第 12 节矩阵全部行 |
| HC-06 | reload：不改任何文件 `POST /api/plugins/reload` | 200；插件仍在；`sys.modules` 中 `amane_ext*` 被重建为新对象（模块 `id` 与 reload 前不同），`fc2_metadata_core` 对象 **未**被重建（W2-02） |
| HC-07 | reload 执行新代码（stale-module 守卫） | 在 `sources/ffcc.fc2-metadata/_impl/_settings.py` 里改写一个只在测试副本中存在的哨兵常量（**仅在临时数据目录的副本上**）-> reload 后 provider 读到新值 |
| HC-08 | 配置变更触发 rebuild | `PATCH` 改 `source_deadline_seconds` / `sources` 后，新构建的 provider 行为反映新配置（回环请求日志 / 超时观测） |
| HC-09 | 插件替换 / 升级（pin 不变） | 构造“版本 +1、其它字节相同”的第二个 plugin zip（临时副本；`PLUGIN_VERSION` 常量改写仅在测试副本）-> 上传 -> `descriptor.version` 更新；旧模块不残留（stale-module 守卫） |
| HC-10 | Core 缺失 | sidecar 目录不存在且 Core 不可 import：上传 -> 422，消息 == P5-C1 §22 冻结模板；`/api/plugins` 的 `items` 不含该插件；`sources/` 下无目录残留（无半装）；**无回退**到内置 FC2 爬虫 |
| HC-11 | Core 不兼容 | (a) sidecar 放入文件名正确但内容被篡改的 wheel -> `WHEEL_HASH_MISMATCH_TEMPLATE`；(b) 放入另一版本文件名的 wheel -> `WHEEL_VERSION_MISMATCH_TEMPLATE`；(c) 预装一个缺少公共名字的假 Core -> P5-C1 `ImportError` 模板；均 422 且无半装 |
| HC-12 | 畸形 plugin zip | 非 zip、含 `..` 路径、无 `plugin.py`、多顶层文件夹、超大（> 20 MiB）-> 422，`sources/` 无残留 |
| HC-13 | 错误 plugin id | zip 内 shim 的 `descriptor().id` 被改成 `other.id`（临时副本）-> 宿主按目录名 / id 校验失败（安装时落盘为 `other.id`；发现期无冲突，但 **`content_routes` / config 不引用**）——判据见第 11.3 节 |
| HC-14 | 重复 plugin | 同一 zip 连续上传两次 -> 第二次**整棵替换**（宿主语义），`/api/plugins` 仍只有一个条目；与手工把同一目录放两个目录名（`descriptor.id != 目录名`）-> 发现期 `failures` 记录 |
| HC-15 | 卸载 | `DELETE` -> 204；`sources/` 目录消失；`plugins/ffcc.fc2-metadata/`（运行时数据，若存在）保留；sidecar 目录**不被触碰** |
| HC-16 | Core 升级（pin 变化）流程 | 按第 8.6 节：卸载 -> 重启 -> 放新 wheel -> 上传新 plugin zip；以及误操作（旧 Core 在内存时直接上传新 zip）得到 `RESTART_TEMPLATE` |
| HC-17 | HTTP 生命周期保持 | 回环 fixture 记录请求：全部来自宿主 `WebClient`（`User-Agent` / TLS 指纹策略 / 代理由宿主决定；adapter 不设）；每个来源 L1 / L2 / L3 计数符合 C1 §15.2 |
| HC-18 | 无副作用 | 运行前后对**临时数据目录之外**的文件系统做快照（`sidecar` 之外）：adapter 无新增 / 修改；插件树写入全部来自宿主（`sources/` 之下） |
| HC-19 | Core 来源准入矩阵（Risk C 信任边界；第 8.3 节） | 在宿主**子进程**内、用真实 `install_plugin_zip` / `PluginManager.discover` 驱动 artifact，对每个执行模式做 PASS / FAIL 配对（见 E31）：**源码宿主**上覆盖 pip / `--target` 解压 / editable-source 的正确与错误 Core、预加载（`sys.modules` 与 `sys.path` 预置）的正确与错误 Core、被篡改的同名 sidecar wheel；**冻结包**上覆盖 sidecar 的正确 / 错误版本 / 篡改 / 符号链接 / 超大。每个 FAIL 必须是 422 / `failures`、固定模板、**无半装**，且失败路径**不改变** `sys.modules` 中 `fc2_metadata_core*` 的对象身份与 `sys.path` |

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

同一请求在受支持的 Amane 版本上必须产生**等价的 adapter 语义**；P5-C1 冻结的映射**不因宿主版本改变**。

### 13.2 必须字节 / 语义相等（E15、E16）

对固定请求集（成功全字段、PARTIAL、未命中、每个 Core `SourceErrorKind` 一例、非法 `SearchQuery`、取消、`base_url` 回环、多来源冲突、复数窄化各一）在两个必需宿主上执行；
以**规范化 JSON（排序键、`ensure_ascii`）**记录并比较下列字段的 sha256：

```text
number、title、actors（含性别 / 顺序）、tags、release、runtime、source_url（poster / thumb / extrafanart 同）、external_id
结果类别：MediaMetadata | None | SourceError
FailureReason 值（逐 kind）、SourceError.detail 全文
descriptor 的适配器可控子集（id、name、version、capabilities、content_types、languages、urls、metadata_fields、api_version、rate_limit）
configuration_model().model_json_schema()
```

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
artifacts             : {plugin_zip_sha256, core_wheel_sha256, core_tree_sha256, adapter_tree_sha256, shim_sha256,
                         release_bundle_sha256, sha256sums_sha256, pin_sha256}
parity                : {required_pairs[{a, b, fields[…], equal(bool), sha256_a, sha256_b}], allowed_diffs_observed[DIFF-nn…]}
status                : [{coordinate_id, amane_version, host_form, platform, status(SUPPORTED|CONDITIONALLY_SUPPORTED|BLOCKED|UNVERIFIED|INFORMATIONAL|IDENTICAL_TO_STABLE), reason}]
                         —— **key = 坐标 `(version, host_form, platform)`，不得只以版本为 key**；版本级状态不得覆盖 / 继承平台级状态
platforms_unverified  : [macos, linux, docker]（= SC-07 / SC-08 / SC-09）
core_admission        : {sidecar_wheel_sha256, core_tree_sha256, cases[{id, mode, expected(PASS|FAIL), observed, template}]}   # E31
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
| C2-E02 | P5-C1 冻结语义不变 | `tree_sha256(adapters/amane/fc2_amane_adapter) == P5_C1_HOST_WITNESS.json.adapter_tree_sha256`；`_impl/` 与之相等（I-C2-1）；P5-C1 的 `tests/amane_adapter/**` 全部原样通过 |
| C2-E03 | Amane 版本坐标 | tag / tag 对象 / peeled commit / release 版本 / `requires-python` / `PLUGIN_API_VERSION` 在 S1 重新核对并写入 JSON；`git rev-parse` 与 GitHub Release 元数据一致；`app-*` 排除理由记录 |
| C2-E04 | API 兼容矩阵 | v0.15.0 与 v0.18.0 的清单（AST）生成；“适配器可控子集指纹”两版相等；第 6.2 节每一行差异都有机检断言 |
| C2-E05 | Core 最终供给 / 安装 | HC-01 / HC-10 / HC-11 / HC-16 / HC-19 在两个必需宿主 + 冻结包上通过；每种执行模式（sidecar / pip / 源码 / 已加载）都证明精确 pin（E31）；`INSTALL.zh-CN.md` 的每一步被脚本化执行（“文档即测试”） |
| C2-E06 | 确定性 artifact | 两个解释器 × 两个输出目录 × CRLF 检出的 plugin zip / wheel / bundle 哈希全相等；允许 / 禁止清单机检 |
| C2-E07 | clean install | HC-01、HC-03；`descriptor().id` 恒为 `ffcc.fc2-metadata` |
| C2-E08 | discovery | HC-02 / HC-03 / HC-14；真实 `PluginManager.discover` |
| C2-E09 | config round-trip | HC-05 / HC-08；一致性守卫（四布尔全真或全假） |
| C2-E10 | provider build | HC-04；真实 `CrawlerFactory` |
| C2-E11 | reload | HC-06 / HC-07；无陈旧模块 |
| C2-E12 | upgrade / replacement | HC-09 / HC-16；旧模块不残留 |
| C2-E13 | missing Core | HC-10；消息 == P5-C1 §22；无半装；无回退 |
| C2-E14 | incompatible Core | HC-11 / HC-19；wrong-version / tampered / wrong-tree / unverifiable / already-loaded-wrong 全部 fail closed 且无半装（细节见 E31） |
| C2-E15 | 跨版本结果等价 | 第 13.2 节全部字段哈希在两个必需宿主上相等 |
| C2-E16 | 跨版本错误等价 | 每个 `SourceErrorKind` -> `FailureReason` / `detail` 相等；对宿主 `FailureReason` **全部成员**枚举，桥的分类是全函数且确定 |
| C2-E17 | HTTP 生命周期保持 | provider 持有宿主 `web_client` 的**同一对象**；adapter 树无第二个 HTTP 客户端（AST，C1 守卫仍绿）；HC-17 |
| C2-E18 | 无 vendoring | plugin zip 不含 Core 文件（文件名 + 整文件字节包含扫描）；`fc2_metadata_core` 仅出现在 `_impl` 的 import 语句与 `_core_gate` 常量中；Core wheel 与 plugin zip 为两个独立文件 |
| C2-E19 | 无新持久化 / 无用户文件改动 | `_ffcc_locator` 与 shim 的 AST 守卫（无写 API）；HC-18 文件系统快照；用户目录零接触 |
| C2-E20 | mutation / 非空洞 | 第 16 节 M2-01..M2-20 全部 KILLED |
| C2-E21 | v0.15.0 宿主集成 | HOST-A-SRC 与 HOST-A-WIN：HC-01..HC-19 全通过 |
| C2-E22 | 当前稳定版宿主集成 | HOST-B-SRC 与 HOST-B-WIN：HC-01..HC-19 全通过（或 BLOCKED + 根因） |
| C2-E23 | current main 信息见证 | HOST-C-MAIN：若 commit == 稳定版 -> `IDENTICAL_TO_STABLE`（不重复计作独立见证）；否则运行并记录，**失败不阻塞**，记为信息差异。E23b：中间版本（可选） |
| C2-E24 | Python / 平台 / 支持坐标矩阵 | 3.14.x（源码宿主）、冻结包内置 3.14.7、主套件 3.12.x、Windows 11；**逐坐标** SC-01..SC-09 的状态与见证一一对应，SC-07 / SC-08 / SC-09 = `UNVERIFIED`；`COMPATIBILITY.json` / `INSTALL.zh-CN.md` / 本 E 项同一份坐标表；JSON 的 `status` 以坐标为 key，不得出现“版本级 SUPPORTED 覆盖未验证平台” |
| C2-E25 | targeted tests | `tests/amane_compat/**` 全绿，列出 collected / passed / skipped |
| C2-E26 | 既有契约 | P5-C1 `tests/amane_adapter/**`、Phase 1-4 `tests/contract/**` 与架构守卫全绿 |
| C2-E27 | full suite | `pytest tests -q` 在 3.12 上：passed / skipped / failed 全部记录；failed = 0；与 P5-C1 基线（8448 passed / 40 skipped）对账，差额 = 新增 targeted 测试数 |
| C2-E28 | skip / xfail 对账 | skip nodeid 清单与基线逐条对账；新增 skip = 0（宿主依赖的 skip 必须有显式、可审计的原因，且不得出现在 targeted 集合） |
| C2-E29 | artifact 哈希 | plugin zip / Core wheel / `_ffcc_pin` / bundle / `SHA256SUMS` / tree 哈希全部记录在 JSON 与 HANDOFF，且互相一致（pin 中的 wheel 哈希 == 实际 wheel 哈希） |
| C2-E30 | evidence gaps / limitations | 如实列出：macOS / Linux / Docker `UNVERIFIED`；哈希与导入之间的 TOCTOU 窗口（L-C2-13）；Core 升级需重启；PATCH 浅合并；Phase 6 范围；以及任何未能完成的 E 项 |
| C2-E31 | **locator 信任边界 / security 证据（Risk C 专项）** | 第 8.3 节准入规则的 **PASS / FAIL 配对矩阵全部通过**（下表）；在单元层（3.12，`tmp_path`，真实 Core 树 / 真实构建的 wheel）与真实宿主（HC-19）各执行一遍；**Final C-level Review 必须在自己的 checkout 上独立重跑**，不得仅引用 HANDOFF |

**E31 PASS / FAIL 配对矩阵（最低集合；可增不可减）**：

| 子项 | 场景 | 期望 |
|---|---|---|
| E31-a | already-loaded：正确的 sidecar（文件名 + sha256 == pin） | **PASS** |
| E31-b | already-loaded：错误版本的 sidecar（文件名 != `CORE_WHEEL_NAME`） | **FAIL**（`RESTART_TEMPLATE`） |
| E31-c | already-loaded：被篡改的同名 sidecar wheel（文件名相同、sha256 不同） | **FAIL**（`RESTART_TEMPLATE`） |
| E31-d | already-loaded：错误的 pip 安装 Core（版本或树哈希不符） | **FAIL**（`RESTART_TEMPLATE`） |
| E31-e | already-loaded：错误的 editable / 源码 Core（树哈希不符） | **FAIL**（`RESTART_TEMPLATE`） |
| E31-f | 正确的 pip 安装 Core（`version == CORE_VERSION` 且树哈希 == pin） | **PASS** |
| E31-g | 正确的 editable / 源码 Core（无发行元数据，树哈希 == pin） | **PASS**（`origin = source/editable`，integrity = VERIFIED） |
| E31-h | 未加载：错误的 pip Core / 错误的 editable Core | **FAIL**（`PIN_MISMATCH_TEMPLATE` / `TREE_MISMATCH_TEMPLATE`）；**不得** `unverified-path -> ACCEPT` |
| E31-i | 未加载：sidecar 篡改 1 字节 / 符号链接 / 大于 16 MiB / 同名目录 / 仅有其它版本 wheel | **FAIL**（`WHEEL_HASH_MISMATCH_TEMPLATE` / `WHEEL_VERSION_MISMATCH_TEMPLATE`） |
| E31-j | 正确树但含额外 `.pyd` / `.so` / `.pth` / `__pycache__` 之外的 `.pyc` / 符号链接 | **FAIL**（`TREE_MISMATCH_TEMPLATE`） |
| E31-k | 已加载的 `fc2_metadata_core.*` 子模块来自与顶层包**不同**的根（混合 / 预置来源） | **FAIL**（`RESTART_TEMPLATE`） |
| E31-l | 有效 sidecar 被更靠前的同名（错误）包遮蔽 | **FAIL**（`UNVERIFIABLE_TEMPLATE`） |
| E31-m | namespace 包 / 多个 `submodule_search_locations` / `origin` 无法归类 / 无 `__spec__` 的 `sys.modules` 条目 | **FAIL**（`UNVERIFIABLE_TEMPLATE` / `RESTART_TEMPLATE`） |
| E31-n | 失败路径的副作用 | 失败后 `sys.modules` 中 `fc2_metadata_core*` 的对象身份与 `sys.path` 与调用前**完全相同**（不 purge、不热切换、不留下半插入的 `sys.path`） |
| E31-o | 无 Core、无 sidecar | locator 不抛；随后产生 **P5-C1 §22 冻结消息**（E13） |
| E31-p | 树哈希算法 | locator 的 stdlib 实现与 C1 `tree_sha256` 对拍相等；与 `P5_C1_HOST_WITNESS.json.core_tree_sha256` 相等；CRLF 检出的 Core 树得到相同哈希 |
| E31-q | 错误模板 | 全部固定、有界、无绝对路径、无外部数据的 `repr` |

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
| M2-14 | locator 不校验 sha256 / 接受任意 wheel / 接受符号链接 / 接受被篡改的同名 wheel | HC-11(a) / HC-19；E31-c / E31-i（篡改 1 字节、替换为符号链接、超大文件、同名目录） |
| M2-15 | locator 把 pin 变化当成功（旧 Core 在内存仍放行） | HC-16 误操作分支：必须 `RESTART_TEMPLATE`；E31-b |
| M2-16 | 兼容 JSON 里把 `IDENTICAL_TO_STABLE` 的 main 伪装成独立见证 / 把 UNVERIFIED 平台写成 SUPPORTED / 以版本为 key 使版本状态覆盖平台状态 | E23 / E24 的 JSON 自洽性测试（schema + 规则）；`COMPATIBILITY.json` 派生测试 |
| M2-17 | **already loaded -> blindly trust**（`fc2_metadata_core` 已在 `sys.modules` 就接受，不核对来源） | E31-b / c / d / e / k（HC-19 的预加载分支）：错误的已加载 Core 必须 FAIL |
| M2-18 | 无发行元数据（源码 / editable）-> `unverified-path` ACCEPT；或 pip 模式只比版本、不比 Core 树哈希 | E31-g / h：错误树必须 FAIL；版本相同但树被篡改的 pip 安装必须 FAIL；正确树必须 PASS（防过度拒绝） |
| M2-19 | 树哈希只覆盖 `*.py` 而放过额外 `.pyd` / `.so` / `.pth` / 符号链接 / 混合来源子模块；或树哈希算法与 C1 不一致 | E31-j / k / p |
| M2-20 | locator 在失败或 pin 变化时 purge `fc2_metadata_core*` / 热切换 / 留下半插入的 `sys.path` | E31-n；U2-11 的 AST 守卫（locator 无 `del sys.modules[...]` / `sys.modules.pop`） |

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

P5-C2 结束时：Amane adapter **可安装、可发现、可配置、可 reload、受支持版本兼容、最终 artifact 可交付**。
P5-C2 **不做**：Phase 6 批处理工作流；真实用户媒体批量运行；Organizer UI；批处理 scheduler；真实大规模公网验收；**真实 scrape 任务端到端**（需要媒体库 / 任务系统，属 Phase 6）。

---

## 19. 不变量（P5-C2 新增；P5-C1 I1-I26 全部继续有效）

```text
I-C2-1  _impl/ 字节 == P5-C1 树（LF 规范化）；adapter 树哈希 == C1 见证记录
I-C2-2  plugin zip 不含 Core 的任何文件（不 vendor）
I-C2-3  shim / locator 纯 stdlib；不写文件；不联网；不 import amane / pydantic / Core
I-C2-4  宿主入口契约不变（Plugin、id、api_version）
I-C2-5  reload / 升级后 shim 与 _impl 模块无陈旧残留
I-C2-6  生产代码无版本分支、无异常文本解析、无私有 monkeypatch、无 feature detection
I-C2-7  Core 与 plugin 精确配对；Core 变更必须 bump 版本（发布台账）；**每一种执行模式（sidecar / pip / 源码 / editable / 已加载）都必须证明与精确 pin 一致，否则 fail closed**
I-C2-8  sidecar 仅在 wheel 哈希相等时加载；pip / 源码 / editable 仅在版本（若有元数据）与 Core 树哈希都等于 pin 时接受；未配对 / 篡改 / 符号链接 / 超大 / 额外可执行文件 -> fail closed 且不半注册
I-C2-9  不覆盖、不移动、不写入用户文件；验收只用临时目录
I-C2-10 兼容见证 JSON 确定、自洽；UNVERIFIED 不得声明为 SUPPORTED；IDENTICAL_TO_STABLE 不计作独立见证
I-C2-11 宿主差异只允许白名单 DIFF-01..DIFF-07
I-C2-12 已加载的 Core 不得被盲信：按其来源重新证明 pin；证明不了 -> RESTART / PIN MISMATCH；不 purge、不热切换
I-C2-13 没有 `unverified-path` 接受路径；完整性 VERIFIED 是接受的必要条件
I-C2-14 支持声明以 `(version, host_form, platform)` 为坐标；版本状态不得覆盖平台状态；UNVERIFIED 坐标不得出现在支持声明里
```

---

## 20. 已知局限（如实记录；进入 E30）

| ID | 局限 |
|---|---|
| L-C2-01 | macOS 冻结包 / Linux / Docker：设计环境无对应宿主，`UNVERIFIED`；纯 Python 且无平台相关代码，但**不声称已验证** |
| L-C2-02 | 当前稳定版为 `CONDITIONALLY SUPPORTED`：设计期只完成 API 差异阅读与冻结包 sidecar 探针，**尚未**在 v0.18.0 上跑 adapter 全场景 |
| L-C2-03 | 桌面用户忘记放置 sidecar 时看到的是 P5-C1 冻结消息（“请在 Amane 所在的 Python 环境中安装”）；为不改 CLOSED 的 `_core_gate` 而接受 |
| L-C2-04 | **（旧的弱保证已取消）** pip / 源码 / editable 模式**同样**校验 `CORE_TREE_SHA256`（并在有元数据时校验版本）；不再存在“仅版本、无哈希”或 `unverified-path` 接受路径。若技术上无法稳定得到与 source tree 相同的树哈希 = U2-12 STOP / DESIGN BLOCKER（设计期 W2-11 已验证可行） |
| L-C2-05 | Core 升级需重启（W2-02）；热切换被拒绝 |
| L-C2-06 | 宿主 v0.18.0 的网络检测页将按 `descriptor.urls[0]` 探测（adapter 不覆盖 `check_connectivity`）；v0.15.0 无此功能 |
| L-C2-07 | 宿主 `PATCH` 对 `config` 做顶层浅合并，无法通过省略键恢复默认 |
| L-C2-08 | `WebClient.request` 在 v0.15.0 `max_retries=0` 时零请求（C1 L-04）；v0.18.0 已修复（DIFF-02） |
| L-C2-09 | Amane 官方不承诺插件可依赖外部代码；sidecar 是本项目为冻结宿主选择的受控方式，不等于 Amane 的官方支持 |
| L-C2-10 | 真实站点网络冒烟与真实 scrape 任务端到端不在本包（Phase 6） |
| L-C2-11 | C1 L-01..L-15 继续成立 |
| L-C2-12 | 宿主「选择服务器路径」安装（`install_plugin_path`）若指向数据目录**之外**的插件目录，locator 无法由 `__file__` 推出数据目录，sidecar 不会被找到；官方安装流程只使用「上传 zip」，`INSTALL.zh-CN.md` 明示，且 HC 不把该路径作为必需场景 |
| L-C2-13 | 哈希校验与随后的 zipimport / import 读取之间存在 TOCTOU 窗口；能在该窗口改写数据目录者已能改写插件树与 pin（同一信任域）。locator 在校验后立即 `sys.path.insert` 并在已加载分支重验，把窗口压到最小，但不声称消除 |

---

## 21. 状态

```text
P5-C2 Design         : CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Contract             : CANDIDATE（本文；含 Design Pre-Review R1 修订）
Construction Plan    : CANDIDATE（docs/P5_C2_CONSTRUCTION_PLAN.md）
Risk Class           : C
Implementation       : NOT STARTED
Package Frozen Base  : CANDIDATE — subject to Design Review
```

本文不得被解读为 FROZEN / DESIGN PASS / IMPLEMENTATION AUTHORIZED。唯一 authority 转换：独立 Design Review PASS -> 该 Review 建立 Design Accepted Head -> Frozen Contract / Construction Plan -> 才允许进入 S1。
若 PASS：Frozen Contract / Plan = R1 Head；Risk Class = C；S1 -> S2 -> S3 连续施工（Risk C 不自动拆分）。

### Design Pre-Review R1 修订记录（docs-only；不是重新设计；Parent = `8870df0ea42e60dd142a5878ea7c0abc6ca3c4b5`）

| ID | 问题 | 修订 |
|---|---|---|
| C2-DESIGN-R1-01 | 第 2 节写了“Governance > P5-C1 Frozen Contract”，与 Acceleration v2 第 4 节冻结的 authority priority 冲突 | 改为领域化 authority：P5-C1 Frozen Contract / Plan（CLOSED semantics）> P5-C2 Accepted Contract（compatibility / supply / release）> P5-C2 Accepted Plan > Acceleration v2 > Task Prompt；P5-C2 不得静默 override P5-C1 CLOSED semantics，必须改变则 U2-1 / U2-6 / U2-7 STOP + authority amendment |
| C2-DESIGN-R1-02 | Risk Class B 候选 | 升为 **C**；理由 = 新建外部可执行 artifact 信任边界（sidecar -> 校验 -> pin -> `sys.path` -> 宿主进程内可执行），不是“用了 `sys.path`”；Risk C 不自动拆分 S1/S2/S3；增加 Security Review Focus（Design Review 必审第 8 节）与 Final C-level Review 独立执行 locator / security 证据（E31）；第 5 节重写 |
| C2-DESIGN-R1-03 | 已加载 Core 可能被直接接受；无发行元数据的源码 / editable `unverified-path -> ACCEPT`；pip 只比版本 | 第 8.3 节重写：**每种执行模式都必须证明精确 pin**（sidecar = 文件名 + wheel sha256；pip = 版本 + Core 树哈希；editable / 源码 = Core 树哈希；已加载 = 按来源重新证明 + 子模块同根）；删除 `unverified-path`；增加目录形态附加准入（防 `.pyd` / `.so` / `.pth` / 符号链接）；loaded != pinned 一律 RESTART / PIN MISMATCH，不 purge、不热切换；新增 U2-11 / U2-12、不变量 I-C2-12 / 13、模板 `TREE_MISMATCH` / `UNVERIFIABLE`；设计期 W2-11 验证了安装树哈希可复现 pin |
| （R1-03 证据） | 需要 PASS / FAIL 配对证据与 mutant | 新增 **C2-E31**（E31-a..q）、HC-19、M2-17..M2-20；扩展 M2-14 / M2-15；E05 / E14 / E20 / E30 同步 |
| （R1-03 局限） | L-C2-04 弱保证 | 取消并改写；新增 L-C2-13（TOCTOU，如实） |
| C2-DESIGN-R1-04 | 支持声明只以 `{v0.15.0, v0.18.0}` 版本集表达 | 第 7.2 节冻结**二维支持坐标** `(version, host_form, platform)`：SC-01..SC-09；Windows x64 desktop = 必需受支持部署；source host = 必需集成兼容；macOS / Linux / Docker = UNVERIFIED（本环境无 Docker，不为扩大声明增加环境依赖）；版本状态不得覆盖平台状态；`COMPATIBILITY.json.status`、`INSTALL.zh-CN.md`、E24 共用同一份坐标表；Docker 安装步骤若保留必须标 `UNVERIFIED / informational`；I-C2-14、M2-16 扩展 |
| （不变） | — | 当前稳定版坐标不变（v0.18.0 / `0a8a731d…`；main == stable，Owner 已独立核实）；P5-C1 映射 / 桥 / SearchQuery / MediaMetadata / 错误 / 归属不动；`_impl` 字节原样；无 vendor；无 `src/**`；无 `pyproject.toml` 改动；无自动 pip 安装器；无热切换 Core |

### 设计者希望复查者重点质疑的决定

1. **Security Review Focus — 第 8.3 节 locator 信任边界**（Risk C）：准入规则对 sidecar / pip / 源码 / 已加载四类是否无遗漏地要求精确 pin 证明；有无可绕过路径（同名遮蔽、`sys.modules` 预置、混合来源子模块、额外可执行文件、符号链接、TOCTOU）；fail-closed 与模板；E31 矩阵与 M2-17..M2-20 的完备性（第 5.4 节）。
2. **第 9 节**：shim + 字节原样 `_impl/` 是否是满足“P5-C1 零改动”的最小设计；有无更简单且不破坏 CLOSED 测试 / 证据的做法。
3. **第 8.7 节 / L-C2-03**：为不改 `_core_gate` 而让桌面用户在“忘记 sidecar”时看到较不友好的 P5-C1 消息，是否可接受。
4. **第 7.2 节**：对 v0.18.0 采用 `CONDITIONALLY_SUPPORTED`（条件为实现期 E15/E16/E22）的表述是否足够；是否应要求设计阶段就跑一遍真实全场景。
5. **第 8.6 节**：拒绝热切换 Core、要求“卸载 -> 重启 -> 放 wheel -> 安装”的升级流程是否过于繁琐。
6. **第 10.3 节**：用 `ZIP_STORED` 换取跨平台字节确定性，是否可接受（产物体积略大）。
7. **第 7.2 节坐标表**：Windows x64 desktop 为必需部署、source host 为集成兼容、macOS / Linux / Docker 为 UNVERIFIED，是否符合“受支持版本兼容”的要求。
8. **第 8.3 节树哈希的 `2000` 个文件 / `16 MiB` 上限与“只允许 `*.py` 与 `__pycache__/*.pyc`”的目录附加准入**是否会误拒合法的 pip 安装（设计期 W2-11 的 `--target` 安装通过；其它 pip 布局由 E31-f 覆盖）。
