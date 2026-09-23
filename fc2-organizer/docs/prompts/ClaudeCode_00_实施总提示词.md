# FC2 Organizer v1.0 — Claude Code 实施总提示词

> 用途：交给“实施者” Claude Code session。
> 目标：在**不修改 Amane 主程序源码**的前提下，完成一个可长期维护、支持多新片源、支持批量操作的 FC2 Organizer 方案。
> 本提示词是执行约束，不是建议。若与《FC2 Organizer v1.0 开发规格书》冲突，以规格书 + 本提示词中更严格者为准。

---

## 0. 你的角色

你是本项目的**主实施工程师**。

你负责：
- 源码勘察；
- 技术设计；
- 编码；
- 自动化测试；
- 本地集成验证；
- Git 提交；
- 生成可供独立复查者审核的 review package / handoff。

你不是产品经理，不得自行削减需求。
你不得为了“先跑起来”而绕过安全边界、吞掉错误、降低验收标准或把批量需求退化为单条处理。

---

## 1. 项目目标

构建一个“FC2 版 tinyMediaManager”能力层，最终用户仍以 Amane 作为宿主 GUI / 媒体库 / 整理器。

目标工作流：

```text
乱目录 / 下载目录
  ↓
递归扫描
  ↓
从脏文件名批量识别 FC2 番号
  ↓
标准化为 FC2-xxxxxxx
  ↓
多新片源并行 / 顺序抓取
  ↓
字段级聚合
  ↓
得到统一 Metadata
  ↓
交给 Amane
  ↓
NFO / poster / fanart / extrafanart
  ↓
批量建目录 / 重命名 / 移动 / 归档
```

**P0 硬性要求：**
1. 必须支持**新片源或多个片源**，不能依赖一个旧 FC2 站点。
2. 必须支持**批量操作**，从扫描、刮削、补刮到整理都不能退化为单条手工工作流。
3. 宿主 Amane 必须保持官方原版，**不得修改 Amane 主程序源码**。
4. 网站变化只应影响 scraper / metadata core；Amane 升级只应影响 adapter 兼容层。
5. 一个来源失败不能让整批任务失败；一部片失败不能阻断其他影片。
6. 不得覆盖或删除用户原始视频；任何移动 / 重命名前必须有可验证的目标路径策略和冲突策略。

---

## 2. 上游与基准

正式上游：

```text
Repository:
https://github.com/sqzw-x/amane.git

Baseline:
tag v0.15.0
```

工作时必须记录：

```text
AMANE_BASE_TAG=v0.15.0
AMANE_BASE_SHA=<实际解析出的 commit SHA>
AMANE_MAIN_SHA=<勘察当日 main SHA>
```

要求：
- `v0.15.0` 是当前正式兼容基线。
- `main` 只用于前瞻兼容勘察，不得在没有明确批准的情况下把实现绑定到 main-only API。
- 如果 tag 不存在、仓库不可访问、API 与规格书明显不符，立即停止并报告，不得猜。

---

## 3. 推荐工作区

```text
FC2-Organizer/
├─ upstream/
│  └─ amane/                       # 官方源码，只读参考，不提交我们的修改
│
├─ fc2-organizer/
│  ├─ amane_fc2_adapter/           # 很薄的 Amane 插件 / 适配层
│  ├─ fc2_metadata_core/           # 我们的长期核心
│  │  ├─ normalize/
│  │  ├─ models/
│  │  ├─ sources/
│  │  ├─ aggregate/
│  │  ├─ cache/
│  │  ├─ http/
│  │  └─ errors/
│  ├─ tests/
│  │  ├─ unit/
│  │  ├─ contract/
│  │  ├─ integration/
│  │  └─ fixtures/
│  ├─ tools/
│  ├─ docs/
│  └─ pyproject.toml
│
└─ specifications/
   └─ FC2_Organizer_v1.0_开发规格书.md
```

如果经 Phase 0 证据证明插件打包环境无法直接依赖独立 Python 包，则可以调整物理目录，但必须保持**逻辑三层分离**：

```text
Amane host
  ↕
thin adapter
  ↕
FC2 metadata core
```

不得把网站 scraper 直接散落进 adapter。

---

## 4. 禁止事项

以下行为禁止：

```text
- 直接修改 upstream/amane 源码
- 在 Amane fork 上实现核心功能
- 把主程序内置 crawler 当成唯一数据源
- 只做单番号 CLI 后宣布完成批量需求
- 把“循环调用单条接口”但没有任务隔离 / 失败恢复 / 并发治理的实现称为批量完成
- 网络异常时裸 except Exception 后返回 None
- 一个来源 403/429/5xx 时让整部片立即失败
- 一个影片失败时终止整个 batch
- 使用硬编码下载目录
- 覆盖目标已存在文件
- 为通过测试而删除失败断言
- 测试只 mock 自己的代码、不验证 adapter 契约
- 将 Cookie / token / API key 写入仓库
- 关闭 Windows Defender 或要求用户全局降低安全防护
```

---

# Phase 0 — 只读源码勘察

**本阶段禁止修改业务代码。**

完成以下勘察并写入：

```text
fc2-organizer/docs/PHASE0_AMANE_INTEGRATION_REPORT.md
```

必须回答：

### 0.1 插件接口

定位并引用实际文件 / 类 / 方法：
- `FilmSourcePlugin`
- `FilmSourceProvider`
- `PluginContext`
- `SearchQuery`
- `FetchOptions`
- `MediaMetadata`
- `SourceDescriptor`
- `SourceError`
- `FailureReason`
- 插件 API version

说明：
- 插件如何发现；
- zip 如何安装；
- 是否热加载；
- 插件第三方依赖限制；
- 插件可使用哪些 HTTP client；
- 是否共享宿主代理 / 重试 / 限速；
- 插件配置如何持久化；
- 内容路由如何加入第三方 source id。

### 0.2 FC2 番号链

确认：

```text
FC2-PPV-1234567
FC2PPV-1234567
FC2-1234567
[广告]FC2PPV-1234567
xxx@FC2PPV-1234567
```

分别如何解析。

必须给出：
- 当前 parser 的源码位置；
- 现有单测；
- 是否能从文件 basename 中提取；
- 是否递归扫描；
- 无法识别时如何记录。

### 0.3 批量任务链

确认：
- REFRESH / SCAN 如何发现多个文件；
- SCRAPE 如何提交多个任务；
- 是否一影片一任务；
- 一个失败是否会阻断其余；
- retry failed 如何工作；
- concurrency / rate limit 在哪里控制；
- 是否已经有 batch UI / task queue，可否直接复用。

### 0.4 资源与整理链

确认：
- poster / fanart / extrafanart 下载由谁执行；
- NFO 由谁写；
- path template 如何生成目录；
- organize 如何 move / copy / hardlink / symlink；
- 默认视频模板；
- 目标碰撞策略；
- 整理是否手动触发；
- 我们是否真的只需返回 metadata 即可复用上述能力。

### 0.5 v0.15.0 vs main

只做插件 API / metadata contract / task contract 的兼容性差异分析。
不要自由审计整个 Amane。

### Phase 0 退出条件

在编码前，必须明确给出：

```text
GO
```

或：

```text
BLOCKED
```

GO 必须有证据证明：
- 外部插件可提供 Film Metadata；
- FC2 parser 可复用或可在 adapter 层补足；
- batch task queue 可复用；
- NFO / images / organize 可由 Amane 负责；
- 无需修改 Amane 核心。

如果任一条件不成立，停止并提交报告，不得进入 Phase 1。

**Phase 0 单独 commit：**

```text
docs: complete Amane v0.15.0 integration reconnaissance
```

---

# Phase 1 — 冻结公共数据契约

目标：先建立我们的独立 FC2 Metadata Core，不接真实网站。

建立统一模型，至少包括：

```python
NormalizedMetadata:
    number
    title
    studio
    publisher
    release
    runtime
    actors
    tags
    plot
    poster_urls
    thumb_urls
    fanart_urls
    extrafanart
    source_urls
    external_ids
    field_sources
```

建立 source 结果模型：

```python
SourceResult:
    source_id
    status
    metadata
    elapsed_ms
    error_kind
    error_detail
```

状态至少：

```text
success
not_found
blocked
rate_limited
network_error
parse_error
invalid_response
```

不得把所有失败都压成 `None`。

定义最低成功条件：

```text
最低成功 = number + 非空 title
```

其余字段可以 partial。

实现番号标准化模块，要求：

```text
FC2PPV-1234567       -> FC2-1234567
FC2-PPV-1234567      -> FC2-1234567
FC2_1234567          -> FC2-1234567（若规则允许）
脏前缀/后缀           -> FC2-1234567
```

严格避免把其它数字误识别成 FC2。

本阶段必须 100% 离线可测试。

**Phase 1 commit：**

```text
feat(core): define FC2 metadata contracts and number normalization
```

---

# Phase 2 — Source Adapter 框架 + 至少两个“当前可用新源”

目标不是先写很多站点，而是证明“可插拔多源架构”。

要求：
- 每个 source 独立模块；
- source 只负责：
  - 接收 normalized FC2 number；
  - 构造请求；
  - 解析站点；
  - 返回 `SourceResult`；
- 不允许 source 自己决定整部影片成功 / 失败；
- 不允许 source 直接写数据库 / NFO / 文件。

候选源需要先做**可用性验证**，再纳入代码。

至少验证以下类型：
- 一个当前可访问的 FC2 聚合 / 索引源；
- FC2 官方源；
- 第二个当前可访问的 FC2 聚合 / 索引源。

可以研究但不得未经验证就写死：
- FC2CMADB
- FD2PPV
- FC2DB
- JavTen
- JavDB
- FC2 Official
- 其他 2026 当前可用新源

对每个候选源先写：

```text
docs/SOURCE_VIABILITY_<source>.md
```

内容包括：
- 当前 URL 形态；
- `FC2-4825061` / `FC2-4824605` / 其它测试番号是否有页面；
- 是否需要 cookie；
- 是否 Cloudflare；
- HTTP 状态；
- 页面中可取得字段；
- 是否允许稳定批量抓取；
- 失败模式；
- 采用 / 淘汰结论。

**P0：至少两个经过真实验证的 source 才能进入 Phase 3。**

不得因为“代码能写”就认为 source 可用。

---

# Phase 3 — 多源聚合引擎

实现多源 Metadata Aggregator。

要求：

### 3.1 Source 调度

支持：
- source 列表；
- enable / disable；
- priority；
- per-source timeout；
- per-host concurrency；
- per-source cooldown / backoff；
- 单 source 熔断但不得永久禁用整个 batch。

### 3.2 字段级聚合

不得仅做：

```text
A 成功 -> 返回 A -> 不再看其它来源
```

必须允许：

```text
title       <- A
release     <- B
studio      <- FC2 Official
tags        <- A + C
poster      <- C
extrafanart <- B + C
```

需要明确 field policy：
- 标量字段：按优先级取第一个非空值（scalar first-non-empty / priority）；
- 列表字段：合并 + 规范化 + 去重（list union + normalize + dedupe）；
- 图片 URL 去重（image URLs dedupe）；
- source_urls 全保留；
- field_sources 记录最终字段来源。

### 3.3 错误隔离

例如：

```text
A -> 403
B -> success
C -> parse_error
D -> success
```

影片应当仍然成功。

只有所有 source 都未达到最低成功条件时，该影片才失败。

---

# Phase 4 — 批量引擎

这不是可选项，是 P0。

实现 `BatchRequest`：

```text
N 个号码
→ 创建 N 个独立 item
→ 每个 item 独立跑 multi-source aggregator
→ 结果独立落盘 / 返回
```

Batch 状态至少：

```text
pending
running
success
partial
failed
cancelled
```

要求：
- 单片失败不影响其它；
- 支持只 retry failed；
- 支持断点 / cache；
- 支持 bounded concurrency；
- 支持 batch summary；
- 支持每个 item 的 source outcomes；
- 支持取消尚未开始的 item；
- 不允许无界并发。

最少建立 100-item 离线模拟批量测试。

---

# Phase 5 — Amane Thin Adapter

仅在 core 稳定后接 Amane。

Adapter 必须尽量薄：

```text
Amane SearchQuery
        ↓
normalize number
        ↓
FC2 Metadata Core
        ↓
NormalizedMetadata
        ↓
Amane MediaMetadata
```

Adapter 不允许：
- 包含具体网站 XPath / CSS selector；
- 包含 FC2CMADB / FD2PPV 等站点业务规则；
- 自己做字段合并；
- 自己做 batch orchestration；
- 自己写 NFO / poster / move 文件。

插件必须有稳定 ID，例如：

```text
fc2org.metadata
```

ID 一经确定不得随意更改。

支持 Amane 配置：
- endpoint / local mode（若采用 service）
- enabled sources
- source priorities
- timeout
- cache
- optional cookie / token fields

敏感字段必须脱敏，不能进日志 / Git。

---

# Phase 6 — Amane 批量集成验证

必须验证：

```text
至少 10 个 FC2
→ 扫描入库
→ 批量 SCRAPE
→ 我们的插件被调用
→ 多源结果
→ Metadata 入 Amane
→ poster / fanart / extrafanart
→ NFO
→ 预览整理路径
```

正式 move 只允许在测试目录中的文件副本执行。

测试目录：

```text
E:\FC2-Organizer-Test\Input
E:\FC2-Organizer-Test\Output
```

或平台等价路径。

不得用用户正式库做第一次 move 验收。

---

# Phase 7 — 整理验收

目标输出示例：

```text
Output/
  FC2-4825061/
    FC2-4825061.mp4
    FC2-4825061.nfo
    poster.jpg
    fanart.jpg
    extrafanart/
      01.jpg
      02.jpg
```

最终模板以规格书为准。

必须验证：
- mkdir；
- rename；
- move；
- collision；
- subtitle pairing（如有）；
- NFO path；
- poster/fanart path；
- partial metadata；
- failed scrape 不被 move 到错误目录。

---

# Phase 8 — 升级兼容与发布

建立兼容测试矩阵：

```text
Amane v0.15.0  = REQUIRED
Amane latest release = SHOULD
Amane main = CANARY
```

每次 Amane 升级只允许修改 adapter / compatibility layer。
如果必须改 core，必须在报告中解释为什么存在跨层耦合。

产物：
- `amane-fc2-adapter.zip`
- core package / service
- install guide
- compatibility matrix
- release notes
- source status matrix
- SECURITY.md
- troubleshooting.md

---

# Git 纪律

必须使用独立 Git 仓库保存我们的代码。

每个 Phase：
1. 先完成代码；
2. 跑全套相关测试；
3. 生成 review handoff；
4. commit；
5. 不把下一 Phase 混入当前 commit。

Commit message 示例：

```text
docs: complete Amane integration reconnaissance
feat(core): add normalized metadata contracts
feat(source): add source A adapter
feat(aggregate): add field-level multi-source merge
feat(batch): add isolated batch execution
feat(amane): add film metadata plugin adapter
test(integration): verify batch scrape through Amane
```

不要 squash 掩盖审查边界，除非最终发布时另有要求。

---

# 每阶段 HANDOFF 必须包含

创建：

```text
docs/review/PHASE<N>_HANDOFF.md
```

至少包含：

```text
Phase:
Review Base:
Review Head:
Scope:
Files changed:
Requirements addressed:
Tests run:
Exact commands:
Pass/fail counts:
Known limitations:
Known external-source instability:
Security considerations:
Windows run:
Amane integration run:
What reviewer should focus on:
Out of scope:
Next phase NOT started:
```

必须明确：
- 真实 Code Head；
- 文档提交如果在 Code Head 之后，必须分别给出 Docs Head；
- 不能把未运行测试写成通过；
- Windows 没跑就写 `Windows NOT run`；
- 外部站点当前不可用要写出来，不得伪造成功。

---

# 独立复查门槛

任何 Phase 不得自行宣布“正式通过”。

实施者只能写：

```text
READY FOR INDEPENDENT REVIEW
```

独立 reviewer 给出：
- PASS
- PASS WITH NON-BLOCKING NOTES
- FAIL

如果 FAIL：
- 形成 R1 / R2 / ... 修复；
- 每轮给出新的 Code Review Candidate SHA；
- reviewer 只复查该轮 closure + regression；
- 不允许用“作者解释”代替证据。

---

# 最终验收硬指标

v1.0 不满足以下任一条不得发布：

```text
[ ] 不修改 Amane 主程序源码
[ ] 至少 2 个经当前真实验证的 FC2 source
[ ] source 可独立启停和替换
[ ] 多源字段级聚合
[ ] 单 source 失败不使影片失败
[ ] 单影片失败不使 batch 失败
[ ] 支持失败项批量重试
[ ] 支持目录递归批量扫描
[ ] 脏文件名 FC2 识别
[ ] 批量 metadata 获取
[ ] NFO / poster / fanart / extrafanart
[ ] 批量建目录 / rename / move
[ ] collision 不覆盖
[ ] 测试副本完成真实整理
[ ] Amane v0.15.0 兼容测试通过
[ ] source / adapter / core 分层测试通过
[ ] 无密钥 / Cookie 泄漏
[ ] review findings 全闭合
```

---

# 现在开始

你现在只执行 **Phase 0**。

不要开始编码 Phase 1。

完成 Phase 0 后：
1. commit；
2. 输出 `Review Base / Review Head`；
3. 给出 `PHASE0_AMANE_INTEGRATION_REPORT.md`；
4. 给出 `PHASE0_HANDOFF.md`；
5. 停止；
6. 等待独立 Claude Code reviewer 审查。

不得提前进入下一阶段。
