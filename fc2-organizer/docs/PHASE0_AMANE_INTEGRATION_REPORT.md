# Phase 0 — Amane v0.15.0 集成勘察报告

**勘察日期：** 2026-09-19
**勘察方式：** 只读克隆 `upstream/amane`（未修改任何 Amane 文件；`upstream/amane/` 已通过 `.gitignore` 排除，不会提交进本仓库）
**勘察范围：** 仅插件 API / 番号解析 / 批量任务链 / 资源整理链 / v0.15.0-vs-main 兼容性；未对 Amane 做全面审计。

```text
AMANE_BASE_TAG=v0.15.0
AMANE_BASE_SHA=45dff2159369883e028a296d775a4598836c1ddd
AMANE_MAIN_SHA=786849daa4ac13a5d480b43ea60b78f1e994741b   # origin/main, 对应 tag v0.16.1
```

`git merge-base v0.15.0 origin/main` = `45dff21`（v0.15.0 本身），`git rev-list --left-right --count v0.15.0...origin/main` = `0  14`：v0.15.0 是 main 的直接祖先，main 领先 14 个提交，无分叉。

---

## 0.1 插件接口

**类型定义位置（作者只应从这里 import）：** `src/amane/plugin/__init__.py`（1-78 行），docstring 明确：「Host code uses `amane.plugins.*` ... and must not import `amane.plugin`」。

| 契约类型 | 源码位置 |
|---|---|
| `FilmSourcePlugin` / `FilmSourceProvider` | `src/amane/plugins/api.py:333-346` / `:35-42` |
| `PluginContext` | `src/amane/plugins/api.py:297-308`（`source_id` / `http_client` / `web_client` / `data_dir`，frozen dataclass） |
| `SearchQuery` / `FetchOptions` | `src/amane/crawlers/models.py:16-30`（dataclass，非 Pydantic） |
| `MediaMetadata` | `src/amane/crawlers/models.py:44-84` |
| `SourceDescriptor` | `src/amane/plugins/models.py:56-92` |
| `SourceError` / `FailureReason` | `src/amane/net/errors.py:60-77` / `:35-58` |
| `PLUGIN_API_VERSION` | `src/amane/plugins/models.py:14`，当前值 `"1"` |

**发现机制：** `PluginManager.discover(data_dir)`（`src/amane/plugins/manager.py:99-141`）扫描 `{data_dir}/plugins/sources/` 下每个目录，要求 `plugin.py` 内存在名为 `Plugin` 的 `FilmSourcePlugin`/`PlaybackPlugin` 子类；校验 `descriptor.api_version == PLUGIN_API_VERSION`、`descriptor.id` 与目录名一致、id 不与内置站点/其它插件冲突。**单个插件加载失败只记入 `failures` 列表，不阻断其它插件**（manager.py:136-139，`except Exception` 边界内）。已有单测直接验证外部可安装性：`tests/plugins/test_plugin_system.py::test_plugin_manager_discovers_dropins`（从临时目录写入真实 `plugin.py` 再 `discover()`）。

**zip 安装：** `install_plugin_zip()`（`src/amane/plugins/packaging.py:85-108`）限制 zip ≤20MB、解压后 ≤50MB，`_extract_zip()`（:180-192）显式拒绝绝对路径与 `..` 路径穿越。安装/卸载/reload 全部**热加载**，不重启进程（`docs/dev/plugins.md` 27-31 行："进程内重建"，`purge_imported_plugin_modules()` 清理 `sys.modules` 后下次 `discover()` 重新 import）。

**第三方依赖限制：** 插件不能声明自己的 pip 依赖或原生扩展，只能用标准库 + 主机通过 `amane.plugin` 暴露的 API；import 失败在安装期报可读错误（`packaging.py:73-76`）。

**HTTP client 共享：** `CrawlerFactory._get_plugin()`（`src/amane/crawlers/factory.py:94-120`）用**同一个 `self._http`**（全工厂共享的 `HttpClient` 实例）构造 `PluginContext`，插件与内置爬虫共用代理、重试、Host 限速器（`src/amane/net/http.py::RateLimiters`，见 0.3）与任务 HTTP 记录。插件不允许自建客户端（`docs/user/plugins.md` 136 行）。

**配置持久化：** `HotSettings.plugins: dict[str, PluginConfig]`（`enabled` + `config`），插件通过 `configuration_model()` 提供 Pydantic 模型与 JSON Schema；密钥字段（`token`/`api_key`/`secret`/`password`/`cookie`/`credential`/`dsn`）在任务快照与日志中按 `src/amane/observability/redact.py:102-127` 的关键词规则自动脱敏。

**内容路由接入第三方 source id：** `PluginManager.augment_config_schema()`（manager.py:206-233）把已发现插件的 `descriptor.id` 动态加入 `content_routes` / `field_priority` / `field_blacklist` 的 Schema 枚举；`validate_hot_settings()`（:235-280）校验路由引用的 source 是否具备 `film_metadata` 能力、是否支持该 `ContentType`。

**结论：外部插件可独立安装、独立发现、独立失败，均不改动 Amane 核心代码。**

---

## 0.2 FC2 番号链

**解析入口：** `src/amane/parsing/file_info.py::parse_file_info()`（:218 起），核心分派 `_identify()`（:392）→`_match()`（:410），无匹配且允许 fallback 时走 `_fallback()`（:499-513）。

**FC2 专属逻辑（两处）：**
```python
# _prepare(), file_info.py:376-378 —— 归一化阶段
catalog = catalog.replace("FC2-PPV", "FC2-").replace("FC2PPV", "FC2-") \
    .replace("--", "-").replace("GACHIPPV", "GACHI")

# _match(), file_info.py:440-445 —— 提取阶段
if "FC2" in c:
    fc2 = c.replace("PPV", "").replace("_", "-").replace("--", "-")
    if m := re.search(r"FC2-\d{5,}", fc2):
        return m.group(), ContentType.FC2
    if m := re.search(r"FC2\d{5,}", fc2):
        return m.group().replace("FC2", "FC2-"), ContentType.FC2
```

**五种输入形态的实测结果**（`python3.13 -c "from amane.parsing import parse_file_info; ..."` 直接执行未改动的源码验证，因为 `re.search` 不锚定，前缀噪声不影响匹配）：

| 输入 | 输出 number | 输出 content_type |
|---|---|---|
| `FC2-PPV-1234567` | `FC2-1234567` | `fc2` |
| `FC2PPV-1234567` | `FC2-1234567` | `fc2` |
| `FC2-1234567` | `FC2-1234567` | `fc2` |
| `[广告]FC2PPV-1234567` | `FC2-1234567` | `fc2` |
| `xxx@FC2PPV-1234567` | `FC2-1234567` | `fc2` |

**现有单测：** `tests/parsing/test_file_info.py`，含 FC2 相关行：155（`FC2-PPV-1234567.mp4`）、156（`FC2PPV1234567.mp4`，无短横线）、230（番号在父目录名而非文件名）、240（文件名优先于看似 FC2 的父目录）、379/445（自由文本）、455（裸 `"FC2 配信開始"` 关键字无数字时正确返回 `None`，不会捏造番号）。**`[广告]…` 与 `xxx@…` 两种前缀形态目前没有专门回归测试**，行为是通过直接执行源码验证得出，不是从已有测试读出——这是 Phase 1 补充回归测试时的明确缺口。

**基名提取与递归扫描：** 文件名优先于父目录名（`file_info.py:234-236`，先 `p.stem` 后 `_dir_names`）。递归扫描存在：`scan_library()`（`src/amane/handlers/_common.py:38-51`）用 `"**/*" if recursive else "*"` glob，`RefreshHandler`（`src/amane/handlers/refresh.py:60-62`）默认 `recursive=True`。

**无法识别时如何记录：** 路径解析总是 `fallback=True`，`_fallback()` 保证非 `None`（最差情形返回清理后的原文 + `ContentType.WESTERN`），因此 `parse_file_info(path=...)` 对真实文件不会产出 `number=None`；`refresh.py:105-106` 甚至用 `assert parsed.number is not None`。**没有独立的「无法识别」结构化日志/状态**——一个语义上错误的番号会正常流入 `ScrapePayload`，直到刮削阶段才以通用错误出现（`scrape.py:84` `"No crawlers available for {number}"`、`scrape.py:129` `"No metadata found for {number}"`，`structlog` warning 级别），不是作为解析失败上报。

### 重要背景发现（超出 0.2 字面提问，但直接影响 GO 判断）

Amane **已经内置三个 FC2 站点爬虫**并注册进核心 registry：`src/amane/crawlers/sites/fc2.py`（`SiteName.FC2`，官方电子市场 `adult.contents.fc2.com`）、`fc2club.py`（`SiteName.FC2CLUB`）、`fc2ppvdb.py`（`SiteName.FC2PPVDB`）。`ContentType.FC2` 的**默认** `content_routes`（`src/amane/config/manager.py:70-75`）已经是 `[JAVDB, FC2PPVDB, FC2, FREEJAVBT]` 四源，且 Amane 核心的 `src/amane/aggregate/` 已经实现**字段级多源聚合**（`AggregatedMetadata.field_sources` / `extrafanart_urls: dict[str, list[str]]`，`src/amane/aggregate/models.py:14-39`）与**单源失败隔离**（`invoke_source()`，`src/amane/observability/source.py:10-34`，捕获 `SourceError` 与任意 `Exception`，写入 `SiteOutcomeRecord` 后返回 `None`，不冒泡）。

但 Amane 自己的开发文档明确记录这些内置 FC2 源不可靠：`docs/dev/content-routes.md:54` 「`fc2ppvdb.com` — FC2 专用索引，**可能被 Cloudflare Access denied**」；`:56` 「`fc2club.top` — 打开后跳转镜像，**不稳定，不纳入默认表**」（`fc2club` 虽有注册爬虫，却因不稳定被排除在默认路由外）。这与规格书「实测番号识别正确，但 10/10 FC2 刮削失败，缺口集中在数据源」的判断完全吻合——**缺口不在聚合框架，而在具体站点的当前可达性**。这意味着本项目通过插件 API 补充的价值是「提供当前可用的新/替代 FC2 源」，而不是重造聚合引擎；但这是否要收敛为 Phase 5 里"每个新源各自作为独立 Amane 插件直接进入 content_routes"还是"仍按总提示词要求先经过独立 FC2 Metadata Core 再由薄 adapter 转一次"，属于 Phase 1/5 的架构判断，Phase 0 不代为决定，仅作为既有冻结决策（"FC2 能力拆为 amane-fc2-adapter + 独立 FC2 Metadata Engine"）之外的背景事实提请复查者与后续实施者注意。

---

## 0.3 批量任务链

**REFRESH 如何发现多文件：** `RefreshHandler.handle()`（`src/amane/handlers/refresh.py:30-123`）经 `scan_library()` 递归 glob，`LibraryScan.classify()`（`src/amane/library/scan.py:45-64`）按黑名单/预告片/体积/扩展名规则分类，新文件逐个 `register_media_file()` 注册。

**SCRAPE 提交：一影片一任务，已确认。** `refresh.py:101-119` 对每个扫描到的文件构造一个 `FollowupTask`（`key=f"scrape:{f.id}"`，`TaskType.SCRAPE`），作为 REFRESH 任务的 `TaskResult.followups` 返回，由 `Repository.complete_task_with_followups` 在同一事务内落成独立任务行（`docs/dev/task-system.md:27-30`）。

**单片失败是否阻断其它：不阻断。** `AsyncWorker._execute()`（`src/amane/scheduler/worker.py:136-276`）把每个已认领任务包成独立 `asyncio.create_task`，外层 `try/except Exception`（:226-236）调用 `fail_task()` 后继续主循环；一个任务的异常不会取消或影响兄弟任务。站点级失败隔离另有 `invoke_source()` 边界（见 0.2 背景发现），双层隔离。

**retry failed 如何工作：** `POST /tasks/batch`（`src/amane/api/routes/tasks.py:183-206`）→`execute_task_batch()`（`src/amane/api/support/task_batch.py`），`TaskBatchAction.RETRY` 只允许对 `TaskStatus.FAILED` 生效（`_RETRYABLE = frozenset({TaskStatus.FAILED})`），可按 `task_ids` 或 `status`/`type` 过滤批量重试；底层 `Repository.retry_tasks()`（`src/amane/db/repos/tasks.py:413-430`）把失败任务克隆为**无根裸任务**重新入队。**这正是规格书要求的「失败项独立批量重刮」，可直接复用，无需我们自建。**

**concurrency / rate limit 控制位置：**
- 任务级并发：`WorkerConfig.concurrency`（`src/amane/config/manager.py:466`，默认 **10**，校验范围 1-64），经 `hot.worker.concurrency` 注入 `AsyncWorker`（`src/amane/app/runtime.py:195-208`）用 `asyncio.Semaphore` 限流（`AsyncWorker.__init__` 里 `concurrency=3` 只是未显式传参时的构造函数兜底默认值，不是实际运行值，实际运行值来自 HotSettings）。
- 站点级限流：`src/amane/net/http.py::RateLimiters`（:53-117），基于 `aiolimiter.AsyncLimiter(1, 1/rate)`，桶容量 1、无突发；优先级 `network.rate_limits`（全局覆盖）> `site_config.rate_limit`（内置站点）> 插件 descriptor 提供的 source 级速率 > `default_rate_limit`（默认 5 req/s）。本地地址固定 300 req/s。

**已有批量 UI / 任务队列，可直接复用：** 前端 `web/src/routes/tasks.tsx` + `task-tree.tsx` / `task-submit-modal.tsx` / `task-detail-panel.tsx` / `task-report-panel.tsx`；后端 `GET /tasks`、`GET /tasks/{id}`、`GET /tasks/{id}/children`、`POST /tasks`、`POST /tasks/batch`（cancel/delete/retry）、`POST /tasks/worker/{pause,resume}`、`GET /tasks/{id}/report`。任务支持父子链（`TaskLink`）与 `EventBus` 实时进度上报（`task.progress` 事件）。**批量扫描、批量刮削、失败重试、进度可视化均已是 Amane 现成能力，无需重新实现。**

---

## 0.4 资源与整理链

**图片下载分两个阶段，均由 Amane 核心执行：**
- 刮削期：`materialize_images()`（`src/amane/media/pipeline.py:84-192`），由 `ScrapeHandler.handle()`（`src/amane/handlers/scrape.py:142-158`）调用，把 poster/thumb/trailer/extrafanart 下载进内容寻址的 `ResourceStore`，并做海报裁剪与可选超分；此阶段与是否整理无关。
- 整理期：`_place_library_images()` / `_download_images_via_store()`（`src/amane/handlers/file.py:264-374`），把 `ResourceStore` 里已有文件 `shutil.copy2` 复制到库内最终路径，并按需叠加封面水印。

**NFO：Amane 确实写经典 Kodi `<movie>` NFO**（不是只有数据库）。`src/amane/media/nfo.py::write_nfo()`（:34-127），docstring 明确「供 Emby / Jellyfin / Kodi 读取」，由 `execute_file_operations()`（`src/amane/handlers/file.py` 内，ORGANIZE 任务专用）调用；受 `Library.write_nfo: bool`（`src/amane/db/models.py:307`，默认 `True`）与 `OrganizePayload.write_nfo` 逐任务覆盖控制。

**路径模板：** `src/amane/organize/path_templates.py` 定义占位符模板系统（`{studio}` `{number}` `[-CD{cd?}]` `[-{sub?}]` 等，`?` 表示可选段），渲染逻辑在 `template.py`。默认视频模板（`path_templates.py:33`）：
```text
VIDEO_TEMPLATE_DEFAULT = "{studio}/{number}/{number}[-CD{cd?}][-{sub?}].{ext}"
```
thumb/poster/fanart/extrafanart/NFO/trailer 默认都在同一 `{link_dir}` 下，与规格书期望的输出结构（`FC2-4825061/{FC2-4825061.mp4, .nfo, poster.jpg, fanart.jpg, extrafanart/}`）一致，且模板本身可配置到不带 `{studio}` 分层。

**move/copy/hardlink/symlink 与碰撞策略：** `execute_organize()`（`src/amane/organize/file.py:20-60`）按 `MoveMode`（`MOVE`/`COPY`/`HARDLINK`/`SYMLINK`）分派，默认 `MoveMode.MOVE`（`Library.move_mode`，`db/models.py:288`）。**碰撞策略：绝不静默覆盖**——`_already_at_dest()`（:63-71）用 `samefile` 判断源与目标已是同一文件（含硬链）则跳过；否则 `_resolve_collision()`（:74-85）对被其它文件占用的目标追加 `(1)`、`(2)` 后缀，从不覆盖。`organize/link.py` 里 strm/软链接写入同样显式拒绝覆盖不匹配的已存在路径（`"Refusing to overwrite {link_path}"`）。

**是否手动触发：手动，独立任务类型。** `OrganizeHandler` docstring（`file.py`）明确「依据已有 Metadata 整理范围内的 MediaFile；不刮削，不修改 Metadata，不扫描磁盘」；全仓库检索确认 `TaskType.ORGANIZE` 从未被 `scheduler/cron.py`、`scheduler/feeds.py`、`scheduler/watcher.py`、`ScrapeHandler` 自动派生，必须显式 `POST /tasks` 提交。

**结论：我们的插件只需返回结构正确的 `MediaMetadata`（含 `poster_urls`/`thumb_urls`/`extrafanart`/`trailer_urls` 等 URL 字段与标量字段），资源下载、裁剪、水印、NFO 写入、路径模板渲染、复制/移动/建链与碰撞安全全部由 Amane 核心（`ScrapeHandler` + `OrganizeHandler`）完成，与调用方是内置爬虫还是插件无关。** 唯一需要 Adapter 层注意的是字段形状差异：Amane `MediaMetadata`（`src/amane/crawlers/models.py:44-61`）用单数 `external_id: str | None` 与 `source_url: str | None`，没有独立的 `fanart_urls` 字段（只有 `poster_urls`/`thumb_urls`/`extrafanart`/`trailer_urls`）；这与规格书 Phase 1 草案里 `NormalizedMetadata` 的复数 `source_urls`/`external_ids`/`fanart_urls` 不同构，Adapter 在 Phase 5 把 `NormalizedMetadata`→`MediaMetadata` 时必须做字段收窄映射，Phase 1 设计模型时应提前意识到最终要收敛到这个目标形状。

---

## 0.5 v0.15.0 vs main

`git log --oneline v0.15.0..origin/main -- src/amane/plugin src/amane/plugins` 输出为空；`git diff v0.15.0 origin/main -- src/amane/plugin src/amane/plugins | wc -l` = `0`——**两个插件目录在 v0.15.0 与当前 main（v0.16.1，领先 14 个提交）之间逐字节相同**。`origin/main:src/amane/plugins/models.py` 中 `PLUGIN_API_VERSION` 仍为 `"1"`，与 v0.15.0 一致。

领先的 14 个提交内容为：0.16.0/0.16.1 版本号提交、`organize/template.py` 的 UNC/盘符路径修复（与插件契约无关）、`agent/*` 工具重构、若干 API 模型的文档/字段命名调整、桌面端启动 URL 修复、新增 Android 客户端、文档/CI 文件。**未触及 `SearchQuery`、`MediaMetadata`、`SourceDescriptor`、`FilmSourcePlugin` 任何一个契约类型。**

**结论：截至勘察当日（2026-09-19），v0.15.0 的插件契约相对 main 完全稳定，未发现破坏性变更。**

---

## Phase 0 退出条件核对

| 条件 | 状态 | 证据 |
|---|---|---|
| 外部插件可提供 Film Metadata | ✅ | `plugins/manager.py` discover/build 全链路 + `test_plugin_manager_discovers_dropins` 单测，从真实目录加载 |
| FC2 parser 可复用或可在 adapter 层补足 | ✅ | `file_info.py` 现有归一化对全部 5 种脏文件名形态均正确（3 种有单测，2 种经源码执行验证，无专门回归测试——已记入 Phase 1 待办） |
| batch task queue 可复用 | ✅ | REFRESH→SCRAPE fan-out、`asyncio.Semaphore` 有界并发、`POST /tasks/batch` RETRY-only-FAILED、`TaskLink` 父子链、`EventBus` 进度，全部现成 API |
| NFO / images / organize 可由 Amane 负责 | ✅ | `write_nfo()` + `materialize_images()` + `execute_organize()`，插件只需返回 `MediaMetadata` |
| 无需修改 Amane 核心 | ✅ | 全部经 `amane.plugin` 公开契约与热加载机制；zip 安装含路径穿越/体积校验；v0.15.0↔main 插件契约零差异 |

四项条件均有源码 + 测试 + 文档三重证据支撑，且未发现需要修改 Amane 主程序源码才能达成的功能缺口。

## GO / BLOCKED

```text
GO
```

## 非阻塞性观察（供独立复查者与后续 Phase 参考，不构成 Phase 0 阻塞项）

1. Amane 已内置字段级多源聚合引擎与 3 个内置 FC2 爬虫，但其官方开发文档已记录这些内置源当前不稳定（fc2ppvdb 易被 Cloudflare 拦截、fc2club 因跳转不稳定被排除出默认路由）。这与规格书对现状的判断一致，但意味着 Phase 1-3 设计「独立 FC2 Metadata Core」时，其增量价值应聚焦在"提供并验证新的/替代的 FC2 数据源"，而具体这些新源是经我们自己的聚合引擎再由薄 adapter 转一次、还是各自独立作为 Amane 插件直接挂进 `content_routes` 让 Amane 自带聚合器处理，是 Phase 1/5 需要明确回答的架构选择点，本报告不代为决定。
2. `[广告]FC2PPV-1234567` 与 `xxx@FC2PPV-1234567` 两种脏文件名形态目前在 Amane 现有测试里没有专门回归用例，虽经源码直接执行验证行为正确，Phase 1 补充我们自己的番号归一化模块测试时应把这两种连同规格书列出的其余 3 种一起纳入表测试。
3. Amane `MediaMetadata`（`external_id`/`source_url` 为单数）与规格书草案 `NormalizedMetadata`（`external_ids`/`source_urls` 为复数字典）字段形状不同构，Phase 5 Adapter 做类型转换时需要显式收窄映射；Phase 1 设计模型字段时建议提前对照这一目标形状，避免 Phase 5 出现无法弥合的字段级落差。
4. Worker 任务并发实际默认值为 10（`WorkerConfig.concurrency`，校验范围 1-64），而非 `AsyncWorker` 构造函数签名里作为兜底默认值出现的 3；引用并发配置时应以 `HotSettings.worker.concurrency` 为准。
